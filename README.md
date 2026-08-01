# SOXL Bot

Research and paper-trading project for a systematic SOXL mean-reversion strategy.

## Layout

- `HANDOFF.md` records the current research state, frozen candidate, and next engineering priorities.
- `research/` contains the numbered exploratory scripts from the research phase.
- `strategy/` is reserved for reusable strategy logic such as signals, regime filters, exits, and sizing.
- `paper/` is reserved for the production-like paper-trading bot and portfolio accounting.
- `intraday/` contains the local intraday SOXL/QQQ monitor. This is a separate
  observation lane, not a replacement for the frozen daily paper strategy.
- `reports/` is reserved for performance and equity-curve reporting code.
- `tests/` is reserved for parity and regression checks.
- `data/` contains historical market data and research outputs.
- `data/paper/` contains stateful paper-trading logs and account state.

## Local Daily Paper Bot

Run manually after the market close:

```bash
python3 -m paper.paper_bot --source yahoo
```

This is the official frozen daily paper strategy. It makes decisions after a
completed daily close and writes state/log changes under `data/paper/`.

The GitHub Actions workflow in `.github/workflows/paper-bot.yml` can still run
this later, but local operation does not depend on Actions.

## Local Intraday Monitor

Run one intraday snapshot from the repository root:

```bash
python3 -m intraday.monitor
```

Run it continuously during market hours:

```bash
python3 -m intraday.monitor --loop --sleep-seconds 300
```

This downloads local Yahoo Finance 5-minute SOXL and QQQ bars, records the
current SOXL intraday context, rolls completed windows into a 30-minute shadow
fast-strategy view, and writes ignored local CSVs:

- `data/intraday/soxl_intraday_bars.csv`
- `data/intraday/soxl_intraday_snapshots.csv`
- `data/intraday/soxl_30m_shadow_signals.csv`

The monitor logs watch states like `OBSERVE`, `TREND_DAY`, `PULLBACK_WATCH`,
`BOUNCE_WATCH`, and `EXTREME_RANGE`. It does not place trades and does not
change the daily paper bot rules.

The 30-minute shadow lane is a research-only mean-reversion strategy. It watches
completed 30-minute SOXL bars and looks for a sharper pattern than "buy every
dip":

- SOXL first has to print a 5-bar z-score at or below `-1.25`.
- The bot waits up to 2 completed 30-minute bars for a bounce confirmation.
- The bounce bar must be positive and close above the prior bar.
- QQQ must be no worse than `-1.0%` from the session open.
- There must be enough regular-session time left to exit the same day.
- The research hold is 3 future 30-minute bars.

Treat this as research/observation until it has enough logged evidence to paper
trade.

Backtest the 30-minute research lane over the recent Yahoo intraday sample:

```bash
python3 -m intraday.monitor --backtest --backtest-period 90d
```

Yahoo may only return a shorter intraday window; if 90 days is unavailable, the
command falls back to 60 days. This is cheap to run locally. It writes ignored
research CSVs:

- `data/intraday/soxl_30m_backtest_summary.csv`
- `data/intraday/soxl_30m_backtest_bars.csv`
- `data/intraday/soxl_30m_backtest_trades.csv`
- `data/intraday/soxl_30m_backtest_equity.csv`
- `data/intraday/soxl_30m_parameter_comparison.csv`
- `data/intraday/soxl_30m_validation.csv`
- `data/intraday/soxl_30m_robustness.csv`
- `data/intraday/soxl_daily_shock_context.csv`
- `data/intraday/soxl_daily_shock_latest.csv`

The parameter comparison is the full-sample scan. The validation file is more
important: it ranks rules by training on the older slice of the sample and
checking the chosen rule against the newer held-out slice.

The robustness file is stricter than the headline backtest. It checks both the
completed-signal-close convention and a causal next-30-minute-bar-open fill,
stresses one-way slippage from 0.1% through 0.5%, and reports the full sample,
the prior block, and the most recent 20 sessions separately. It also includes
`fast_30m_stress_guard_v5_research`, which keeps the v4 signal but allows only
one entry per session to avoid repeatedly buying a cascading selloff. This is a
research row only; it does not replace the forward v4 paper account.

The daily shock files provide historical context rather than a trade signal.
They combine the local daily history with newer paper-log closes, focus on the
modern 2021+ semiconductor regime, cluster shocks ten sessions apart, and show
1-, 3-, and 5-session outcomes after SOXL five-day falls of 20%, 25%, and 30%.

The local monitor remains log-only by default. If you later want experimental
30-minute paper accounting, run it explicitly with `--paper-trade-30m`.

Each 30-minute backtest also evaluates `adaptive_30m_research_v1` as a separate
research challenger. It does not replace `fast_30m_validated_v4` and is never
used by `--paper-trade-30m`. The challenger combines two causal lanes:

- The v4 mean-reversion bounce must still be at least 1% below the session high.
- A trend-pullback entry can fire after a red 30-minute bar of at least 0.5%
  when SOXL remains at least 2% above its session open, is above VWAP, QQQ is
  nonnegative from its session open, and the next completed bar turns green.

The same 50% sizing, 0.1% slippage, three-bar hold, and no-overnight rule apply.
Research results and a chronological 60/20/20 check are written to ignored
`data/intraday/soxl_30m_adaptive_challenger_*.csv` files and shown separately
on the dashboard. The normal monitor also writes completed challenger decisions
to `data/intraday/soxl_30m_adaptive_challenger_signals.csv` for forward shadow
evidence, but those signals are not passed to paper accounting.

The legacy headline and parameter-scan rows still use the signal-bar close so
they remain comparable with earlier research. Treat those as optimistic. The
robustness output's `next_bar_open` rows are the decision-grade execution check.

The overnight rebound account is a separate paper strategy. At the completed
3:30 p.m. ET bar, it enters 50% long when SOXL is at least 5% below its session
open, applies 0.1% entry slippage, and queues a paper exit for the next session
open with another 0.1% slippage. It intentionally carries overnight gap risk.

Initialize it from an explicitly labeled five-session historical simulation:

```bash
python3 -m intraday.monitor --backfill-overnight-paper --backfill-sessions 5
```

Then continue it as live paper trading alongside the frozen v4 account:

```bash
python3 -m intraday.monitor --loop --paper-trade-30m \
  --paper-trade-overnight --sleep-seconds 300
```

The backfilled rows use `historical_backfill` provenance and are displayed as
simulations on the dashboard. New decisions use `forward_live` provenance.

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

For local use, run three terminals:

```bash
uvicorn api.server:app --reload
python3 -m intraday.monitor --loop --sleep-seconds 300
cd frontend && npm run dev
```

## Optional Hosted Dashboard

Hosting is optional for now. Local development reads from FastAPI, while a future
hosted build can read a static JSON export at `data/dashboard.json`.

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

## Free Live 30-Minute Backend

`live-worker/` contains a Cloudflare Worker and D1 schema for the live
30-minute observation lane. It uses Twelve Data for completed SOXL/QQQ bars,
runs `fast_30m_validated_v4`, and exposes a dashboard-compatible API without
trying to run the pandas backtest workload in a Worker.

The cloud lane also maintains a forward-only $10,000 paper account. It enters
at the next 30-minute bar open after a valid signal, uses 50% sizing and 0.1%
slippage each way, exits after three completed bars, and publishes marked
equity, realized and unrealized P&L, drawdown, win rate, trade statistics,
decisions, trades, and an equity curve to the live dashboard.

See [`live-worker/README.md`](live-worker/README.md) for the free account,
secret, database migration, deployment, and first-refresh commands.

## Notes

The research scripts still use repo-root-relative paths such as `data/SOXL_features.csv`.
Run them from the repository root to preserve their original behavior.

`research/step17_paper_bot.py` is the legacy 20-day paper bot from the research phase.
The frozen fast paper bot should be implemented under `paper/` after signal parity is verified.
