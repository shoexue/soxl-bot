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

GitHub Actions automation is defined in `.github/workflows/paper-bot.yml`.
It runs on weekdays after the market close and can also be started manually from
the Actions tab.

The workflow commits changes under `data/paper/` back to the repository. In
GitHub, make sure Actions has write access:

`Settings -> Actions -> General -> Workflow permissions -> Read and write permissions`
