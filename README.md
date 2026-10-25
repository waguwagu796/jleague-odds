# J.League J1/J2 odds

K League odds project adapted for the 2026/27 J1 and J2 seasons. The page keeps the original browser-side Monte Carlo model and daily GitHub Actions refresh workflow, with league rules changed for J.League.

## Included

- J1 and J2 standings, title/promotion/relegation probabilities, remaining-point targets, team detail and probability history.
- Daily data refresh using the official J.League Data Site public fixtures/results search pages.
- Historical 2025 J1/J2 results are included for the original backtest view.
- 2026/27 format: 20 clubs per league, 38 matches per club, double round robin.
- J1: bottom three modelled as directly relegated.
- J2: top two modelled as automatically promoted; places 3–6 enter a single-match promotion playoff, with the higher league finisher advancing on a draw.
- The 2026 special-season competitions are excluded. The collector targets the regular 2026/27 J1/J2 competition frames.

## Run

1. Put this folder in a GitHub repository.
2. In Actions, run **Update J.League data** once manually. It fetches current fixtures/results and writes `data/k1.json` and `data/k2.json`.
3. Enable GitHub Pages for the repository (deploy from the `main` branch/root) to host `index.html`.

The collector uses the official site’s public HTML search results, not a documented API. It checks for 20 clubs and 38 played/scheduled matches per club and fails the workflow if validation finds a problem. The collector supports the verified 2025 and 2026/27 competition IDs. It uses placeholder dates only where the official listing has no date and flags schedule-count mismatches in `note`.

## Model limitations

- Promotion/relegation license exceptions are not modelled.
- ACL qualification places may depend on cup results, so the displayed J1 top-three ACL indicator is illustrative rather than an official qualification guarantee.
- Probabilities are statistical estimates, not betting advice.
- `index.html` is based on the original project page; if changing the simulation logic, keep the embedded `engine-src` block in sync with `engine.js`.
