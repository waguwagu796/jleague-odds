#!/usr/bin/env python3
"""Collect J1/J2 fixtures and results from the official J.League Data Site.

The source is its public HTML search table, not a documented API. The parser
validates the club count and 38-match schedule and fails closed on layout changes.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from html.parser import HTMLParser

BASE = "https://data.j-league.or.jp/SFMS01/search?competition_years={year}&competition_frame_ids={frame}&competition_ids={competition}&tv_relay_station_name="
HERE = os.path.dirname(os.path.abspath(__file__))
KST = dt.timezone(dt.timedelta(hours=9))
# Official competition IDs. 2026 is the regular 2026/27 season, not the 2026 special season.
LEAGUES = {"j1": {"frame": 1, "competitions": {2025: 651, 2026: 725}, "teams": 20}, "j2": {"frame": 2, "competitions": {2025: 655, 2026: 727}, "teams": 20}}

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.rows=[]; self.row=None; self.cell=None; self.in_cell=False
    def handle_starttag(self, tag, attrs):
        if tag == "tr": self.row=[]
        elif tag in ("td", "th") and self.row is not None: self.cell=[]; self.in_cell=True
    def handle_data(self, data):
        if self.in_cell and self.cell is not None: self.cell.append(data)
    def handle_endtag(self, tag):
        if tag in ("td", "th") and self.in_cell and self.row is not None:
            self.row.append(" ".join(" ".join(self.cell or []).split())); self.cell=None; self.in_cell=False
        elif tag == "tr" and self.row is not None:
            if self.row: self.rows.append(self.row)
            self.row=None; self.cell=None; self.in_cell=False

def halfwidth(s):
    return s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))

def fetch_rows(league, year):
    competition = LEAGUES[league]["competitions"].get(year)
    if competition is None: raise RuntimeError(f"No verified official competition ID configured for {league} {year}.")
    url = BASE.format(year=year, frame=LEAGUES[league]["frame"], competition=competition)
    req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 (compatible; jleague-odds/1.0)", "Accept-Language":"ja,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=45) as response:
        raw = response.read().decode("utf-8", "replace")
    parser = TableParser(); parser.feed(raw)
    rows=[]
    for row in parser.rows:
        if len(row) < 8 or not re.match(r"^20\d{2}/\d{2}$", row[0]): continue
        if not any(x in row[1] for x in ("Ｊ１", "Ｊ２", "J1", "J2")): continue
        rows.append(row)
    if not rows: raise RuntimeError(f"No fixture rows parsed for {league}; official source layout may have changed.")
    return rows, url

def parse_date(value):
    m=re.search(r"(\d{2})/(\d{2})/(\d{2})", halfwidth(value))
    if not m: return None
    yy,mm,dd=map(int,m.groups())
    return f"{2000+yy:04d}-{mm:02d}-{dd:02d}"

def parse_round(value):
    m=re.search(r"第\s*(\d+)\s*節", halfwidth(value))
    return int(m.group(1)) if m else None

def parse_score(value):
    m=re.search(r"(\d+)\s*[-–－]\s*(\d+)", halfwidth(value))
    return (int(m.group(1)), int(m.group(2))) if m else None

def standings(teams, results):
    t={name:{"team":name,"p":0,"w":0,"d":0,"l":0,"gf":0,"ga":0,"pts":0} for name in teams}
    for date,rnd,h,a,hs,as_ in results:
        H,A=t[h],t[a]; H["p"]+=1; A["p"]+=1; H["gf"]+=hs; H["ga"]+=as_; A["gf"]+=as_; A["ga"]+=hs
        if hs>as_: H["w"]+=1; A["l"]+=1; H["pts"]+=3
        elif hs<as_: A["w"]+=1; H["l"]+=1; A["pts"]+=3
        else: H["d"]+=1; A["d"]+=1; H["pts"]+=1; A["pts"]+=1
    out=sorted(t.values(),key=lambda x:(x["pts"],x["gf"]-x["ga"],x["gf"],x["w"]),reverse=True)
    for i,row in enumerate(out,1): row["rank"]=i
    return out

def collect(league, year):
    rows,source_url=fetch_rows(league,year); teams=set(); results=[]; fixtures=[]
    for row in rows:
        # Official columns: season, competition, round, date, kickoff, home, score, away, stadium, ...
        date=parse_date(row[3]); rnd=parse_round(row[2]); home=row[5].strip(); away=row[7].strip()
        score=parse_score(row[6]); teams.update((home,away))
        if score and date: results.append([date,rnd,home,away,score[0],score[1],""])
        elif date: fixtures.append([date,rnd,home,away,""])
        else: fixtures.append([f"{year+1}-06-30",rnd,home,away,""])
    expected=LEAGUES[league]["teams"]
    if len(teams)!=expected: raise RuntimeError(f"{league}: parsed {len(teams)} clubs, expected {expected}; refusing to publish.")
    fmt={"teams":expected,"gamesPerTeam":38,"zones":f"{league}-{year}-{year+1}"}
    now=dt.datetime.now(KST)
    doc={"league":league,"season":year,"seasonLabel":f"{year}/{str(year+1)[-2:]}","asOf":now.date().isoformat(),"updatedAt":now.isoformat(timespec="seconds"),"source":"J.League Data Site official schedule/results","sourceUrl":source_url,"format":fmt,"standings":standings(sorted(teams),results),"results":results,"fixtures":fixtures,"injuries":[],"note":""}
    counts={name:0 for name in teams}
    for r in results: counts[r[2]]+=1; counts[r[3]]+=1
    for f in fixtures: counts[f[2]]+=1; counts[f[3]]+=1
    problems=[f"{name}: played+scheduled {n}, expected 38" for name,n in counts.items() if n!=38]
    for r in doc["standings"]:
        if r["pts"]!=3*r["w"]+r["d"]: problems.append(f"{r['team']}: points mismatch")
    if problems: doc["note"]="Schedule validation warning: "+"; ".join(problems[:5])
    return doc

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--season",type=int,default=2026); ap.add_argument("--history",type=int,help="collect a completed season for backtesting"); ap.add_argument("--out",default="data"); args=ap.parse_args()
    year=args.history or args.season
    out=os.path.join(HERE,args.out) if not os.path.isabs(args.out) else args.out; os.makedirs(out,exist_ok=True)
    failed=False
    for league in ("j1","j2"):
        try:
            doc=collect(league,year)
            suffix=f"-{year}" if args.history else ""
            path=os.path.join(out,league.replace("j","k")+suffix+".json")
            with open(path,"w",encoding="utf-8") as f: json.dump(doc,f,ensure_ascii=False,separators=(",",":"))
            print(f"{league.upper()} {year}: clubs={len(doc['standings'])} results={len(doc['results'])} fixtures={len(doc['fixtures'])}; {doc['note'] or 'schedule checks passed'}")
            if doc["note"]: failed=True
        except Exception as exc:
            print(f"[{league}] ERROR: {exc}",file=sys.stderr); failed=True
    sys.exit(1 if failed else 0)
if __name__=="__main__": main()
