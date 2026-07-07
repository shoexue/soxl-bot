# SOXL Bot

Research and paper-trading project for a systematic SOXL mean-reversion strategy.

## Layout

- `HANDOFF.md` records the current research state, frozen candidate, and next engineering priorities.
- `research/` contains the numbered exploratory scripts from the research phase.
- `strategy/` is reserved for reusable strategy logic such as signals, regime filters, exits, and sizing.
- `paper/` is reserved for the production-like paper-trading bot and portfolio accounting.
- `reports/` is reserved for performance and equity-curve reporting code.
- `tests/` is reserved for parity and regression checks.
- `data/` contains historical market data and research outputs.
- `data/paper/` contains stateful paper-trading logs and account state.

## Daily Paper Bot

Run manually after the market close:

```bash
python3 -m paper.paper_bot --source yahoo
```

The GitHub Actions workflow in `.github/workflows/paper-bot.yml` runs the same
bot on weekdays after the market close, validates the implementation, and commits
paper-trading state/log changes under `data/paper/`.

## Dashboard API

Run the read-only dashboard API from the repository root:

```bash
uvicorn api.server:app --reload
```

Useful endpoints:

- `GET /api/dashboard`
- `GET /api/state`
- `GET /api/daily-log`
- `GET /api/trades`
- `GET /api/signals`
- `GET /api/market-history`
- `GET /api/historical-summary`
- `GET /api/performance`
- `GET /api/health`

## Frontend Dashboard

Run the React dashboard in a second terminal:

```bash
cd frontend
npm run dev
```

By default the dashboard reads from `http://127.0.0.1:8000`. To point it at a
different API host, set `VITE_API_BASE_URL`.

## Hosted Dashboard

The production dashboard is designed for GitHub Pages. Local development reads
from FastAPI, while production builds read a static JSON export at
`data/dashboard.json`.

Generate the static dashboard payload:

```bash
python3 reports/export_dashboard_json.py
```

Build the Pages version:

```bash
cd frontend
GITHUB_PAGES=true npm run build
```

After each successful scheduled paper-bot run, the Pages workflow exports the
dashboard JSON and deploys the frontend. The manual Pages workflow can also
deploy the current committed data without running the paper bot.

Before the first deploy, enable GitHub Pages in the repository:

```text
Settings -> Pages -> Build and deployment -> Source -> GitHub Actions
```

## Notes

The research scripts still use repo-root-relative paths such as `data/SOXL_features.csv`.
Run them from the repository root to preserve their original behavior.

`research/step17_paper_bot.py` is the legacy 20-day paper bot from the research phase.
The frozen fast paper bot should be implemented under `paper/` after signal parity is verified.
