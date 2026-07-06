# Paper

Production-like paper-trading code belongs here.

The next paper bot should implement the frozen fast strategy from `HANDOFF.md`, with idempotent daily runs and mark-to-market accounting.

Run the daily bot after the market close:

```bash
python3 -m paper.paper_bot --source yahoo
```

For offline checks against local CSVs:

```bash
python3 -m paper.paper_bot --source local --dry-run
python3 reports/validate_paper_bot.py
```
