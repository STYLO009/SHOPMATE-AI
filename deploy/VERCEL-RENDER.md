# Deploying ShopMate AI — Vercel (frontend) + Render (backend)

Vercel hosts the Next.js frontend; it cannot run the FastAPI + PostgreSQL +
Redis backend, so the API runs on Render. The frontend reaches the API
through a **same-origin proxy** (`/api/*` → Render), which keeps the httpOnly
session cookie same-site — no CORS or cookie changes required.

```
Browser ──► https://<app>.vercel.app            (Next.js on Vercel)
                 │  /api/* rewrite (next.config.ts)
                 ▼
            https://shopmate-api.onrender.com   (FastAPI on Render)
                 │
                 ▼
            PostgreSQL (Render, free plan)       (alembic migrations on start)
```

> Local development is unchanged: `docker compose up` still runs everything
> on `localhost:8000` / `localhost:3000`.

---

## Prerequisites

- This repo pushed to GitHub (already: `github.com/STYLO009/SHOPMATE-AI`)
- Free accounts: [Vercel](https://vercel.com), [Render](https://render.com)
- Optional: a Google Cloud project (only for "Continue with Google")

---

## Step 1 — Deploy the backend on Render

1. Render Dashboard → **New → Blueprint** → connect/import this repository.
   Render finds [`render.yaml`](../render.yaml) at the repo root and creates:
   - web service `shopmate-api` (Docker build from `backend/Dockerfile`,
     health check `/api/health`, `alembic upgrade head` runs on start)
   - a free PostgreSQL instance `shopmate-db` wired into `DATABASE_URL`
2. For the variables marked `sync: false`, fill in placeholders now or later:
   | Variable | Value |
   |---|---|
   | `FRONTEND_URL` | your Vercel URL (from Step 2) — used in reset-password emails and OAuth redirects |
   | `CORS_ORIGINS` | same Vercel URL (the proxy makes this mostly redundant) |
   | `GOOGLE_*` | skip for now — leave empty |
3. Click **Apply / Deploy**. Wait until the first deploy is **Live** and note
   the service URL: `https://shopmate-api.onrender.com`.
4. Smoke-test: open `https://shopmate-api.onrender.com/api/health` — expect
   `{"status": ...}` JSON. Also confirm `/api/products/featured` returns the
   labelled sample catalogue.

If your workspace cannot create a free Postgres instance, create the
database elsewhere (e.g. [Neon](https://neon.tech) free tier) and set
`DATABASE_URL` on the service manually — the app rewrites plain
`postgresql://` URLs to the installed psycopg3 driver automatically.

## Step 2 — Deploy the frontend on Vercel

1. [vercel.com/new](https://vercel.com/new) → import the GitHub repo.
2. **Root Directory** (Project → Settings → General): `frontend`
   (the monorepo's Next.js app). Leave build settings on auto-detect.
3. **Environment Variables** (Settings → Environment Variables), add for
   *Production, Preview and Development*:

   | Name | Value |
   |---|---|
   | `API_PROXY_ORIGIN` | `https://shopmate-api.onrender.com` |

   This is read by `next.config.ts` **at build time** and turns on the
   `/api/*` → Render rewrite. **Do not set `NEXT_PUBLIC_API_URL`** — leaving
   it unset makes the browser call same-origin `/api/...` paths.
4. **Deploy**. When finished you get `https://<something>.vercel.app`.

> Every push to `main` now auto-deploys both services (Render and Vercel
> both watch the repo).

## Step 3 — Point the backend at the frontend

Back on Render (service `shopmate-api` → Environment):

1. Set `FRONTEND_URL` = `https://<your-app>.vercel.app`
2. Set `CORS_ORIGINS` = `https://<your-app>.vercel.app`
3. **Save, rebuild, and deploy**.

## Step 4 — Verify the whole path

With the Vercel URL open in a browser:

- `https://<your-app>.vercel.app/api/health` — JSON from the backend
  (proves the proxy works).
- Sign up → redirected to the dashboard (session cookie travels through the
  proxy; you stay on `*.vercel.app` the whole time).
- **Explore** opens with a populated catalogue (backend `/api/products/featured`).
- Theme toggle, sidebar, chat dock all work; Network tab shows API calls
  going to `/<your-app>/api/...` (same origin).

---

## Optional — Google OAuth

1. [Google Cloud Console](https://console.cloud.google.com) → create OAuth
   2.0 credentials; authorised redirect URI:
   `https://<your-app>.vercel.app/api/auth/google/callback`
   (the proxy forwards it to Render, so the session cookie is set for your
   Vercel domain).
2. On Render set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
   `GOOGLE_REDIRECT_URI` (same URI as above) → Save & Deploy.

## Optional — enable a real LLM

The default is graceful: `LLM_PROVIDER=auto` with no Ollama/HuggingFace
configured falls back to the deterministic rule-based engine (every response
is labelled `rule-based-fallback`). To use Hugging Face, set `HF_TOKEN`
(and optionally `HF_MODEL_ID`) on Render.

## Costs & limits (free tier)

- **Vercel**: frontend only — fine on Hobby.
- **Render free web service**: sleeps after ~15 min idle → first request
  after idle takes ~30–60 s (cold start); free instances also rebuild on
  every push. 0.1 CPU / 512 MB — if the container is OOM-killed, switch the
  plan to `1c-2g` in `render.yaml`.
- **Render free Postgres**: 256 MB / 1 GB — demo-scale only.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Vercel build fails on `rewrites`/`API_PROXY_ORIGIN` | Env var missing or misspelled — it must exist **before** the build (Production scope) |
| API calls 404 on Vercel | `API_PROXY_ORIGIN` not set at build time → redeploy after adding it |
| Login works but every request is 401 | `ENVIRONMENT` must be `production` on Render (secure cookie) and the browser must be on `https://` |
| `No module named 'psycopg2'` | `DATABASE_URL` must be a Postgres URL — the app rewrites `postgresql://` → `postgresql+psycopg://` itself |
| Backend crash-loops on start | Check Render logs: Alembic runs first; a migration error prints in full |
| Explore empty / `provider_errors` | Expected only if the DB has no sample data — `/api/products/featured` always serves the labelled sample catalogue |
| Emails link to `localhost:3000` | `FRONTEND_URL` not set on Render (Step 3) |
