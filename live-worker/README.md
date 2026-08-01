# Free SOXL 30-Minute Live Worker

This Cloudflare Worker is the small live companion to the local Python research
system. It fetches completed SOXL and QQQ 30-minute bars from Twelve Data,
stores them in D1, applies `fast_30m_validated_v4`, and runs a forward-only
$10,000 paper account. The paper account uses 50% sizing, causal next-bar-open
entries, 0.1% slippage each way, a three-bar hold, and no overnight carry.
It exposes:

- `GET /api/health`
- `GET /api/dashboard`
- `POST /api/refresh` with the Twelve Data key in `X-Admin-Key`
- `POST /api/paper/activate` with the same protected header

The full pandas backtests remain local. This Worker performs only the current
incremental signal calculation.

## One-time deployment

From the repository root:

```bash
cd live-worker
npm install
npx wrangler login
npm run deploy
npm run db:migrate:remote
npx wrangler secret put TWELVE_DATA_API_KEY
npm run deploy
```

The first deploy automatically provisions the D1 binding and writes its ID into
`wrangler.jsonc`. The first deployment exists only to provision D1; apply the
migration and secret immediately afterward.

Do not put the Twelve Data key in `wrangler.jsonc`, `.dev.vars`, the frontend,
Git, or chat. `wrangler secret put` prompts for it securely.

## First refresh

The scheduled job runs at minutes 1 and 31 on weekdays. To populate the
database immediately, load the key into a temporary shell variable:

```zsh
read -s "TWELVE_DATA_API_KEY?Paste Twelve Data key: "; echo
```

Use the Worker URL printed by `npm run deploy`:

```zsh
curl -sS -X POST \
  -H "X-Admin-Key: ${TWELVE_DATA_API_KEY}" \
  "https://soxl-live-api.YOUR-SUBDOMAIN.workers.dev/api/refresh"

unset TWELVE_DATA_API_KEY
```

Then check:

```bash
curl -sS "https://soxl-live-api.YOUR-SUBDOMAIN.workers.dev/api/health"
```

## Local tests

The strategy and timestamp tests have no third-party dependencies:

```bash
npm test
```

For local Worker development after `npm install`:

```bash
npm run db:migrate:local
```

Create `live-worker/.dev.vars` containing the key only for local development:

```text
TWELVE_DATA_API_KEY=replace-locally
```

The file is ignored by Git. Run:

```bash
npm run dev
```

## Frontend

The existing Vite dashboard can read the live response without code changes.
For a Cloudflare Pages production build, set:

```text
VITE_API_BASE_URL=https://soxl-live-api.YOUR-SUBDOMAIN.workers.dev
```

The production `ALLOWED_ORIGIN` is
`https://soxl-live-dashboard.pages.dev`. Update it if the frontend hostname
changes, then deploy the Worker again.
