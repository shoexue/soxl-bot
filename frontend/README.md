# SOXL Paper Dashboard

Read-only React dashboard for SOXL paper-trading status, signals, paper
performance, historical context, and data health.

Start the API from the repo root:

```bash
uvicorn api.server:app --reload
```

Start the frontend:

```bash
cd frontend
npm run dev
```

The default API base URL is `http://127.0.0.1:8000`. Override it with:

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

Production builds read static dashboard data from `public/data/dashboard.json`.
Generate it from the repo root before previewing the production build:

```bash
python3 reports/export_dashboard_json.py
cd frontend
GITHUB_PAGES=true npm run build
npm run preview
```
