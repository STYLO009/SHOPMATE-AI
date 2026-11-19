# ShopMate AI

ShopMate AI is a shopping research app with a Next.js frontend and a FastAPI backend. Its research workflow classifies a query, searches product providers, analyzes available specifications and reviews, ranks results, and returns an explanation. The included product catalogue is sample data and is labelled as such.

## Run with Docker Compose

1. Copy `.env.example` to `.env`.
2. Start the app with `docker compose up --build`.
3. Open the frontend at <http://localhost:3000> and the API docs at <http://localhost:8000/docs>.

Compose starts PostgreSQL and Redis, applies Alembic migrations, and starts the API and frontend. The default database credentials and signing key are for local development only. Set a strong `SECRET_KEY` and non-development configuration before any deployment.

## Run locally

Backend (Python 3.12):

```powershell
cd backend
Copy-Item ..\.env.example .env
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The backend defaults to a local SQLite database when `DATABASE_URL` is unset. For a production-like PostgreSQL setup, configure `DATABASE_URL` and run `alembic upgrade head` from `backend` before starting the API.

Frontend (Node.js 22):

```powershell
cd frontend
npm ci
npm run dev
```

Set `NEXT_PUBLIC_API_URL` in `frontend/.env.local` if the API is not at `http://localhost:8000`.

## Optional integrations

- Authorized merchant feed: `MERCHANT_API_URL` and `MERCHANT_API_KEY`.
- Flipkart affiliate feed: `FLIPKART_AFFILIATE_ID` and `FLIPKART_AFFILIATE_TOKEN` from the Flipkart Affiliate program.
- Amazon.in offers: `AMAZON_CREATORS_CLIENT_ID`, `AMAZON_CREATORS_CLIENT_SECRET`, and `AMAZON_ASSOCIATE_TAG` from Amazon Associates / Creators API. Access depends on Amazon approval and qualifying account activity.
- Model: set `LLM_PROVIDER=ollama` with an Ollama URL/model, or `LLM_PROVIDER=huggingface` with `HF_TOKEN`. Use `none` for deterministic local extraction and ranking.
- Password reset email: configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USE_TLS`, `SMTP_USER`, `SMTP_PASSWORD`, and `EMAIL_FROM`.
- Google sign in: configure the Google OAuth client values and register the callback URL in Google Cloud.

The public `/deals` page and read-only `/api/offers/search` and `/api/offers/featured` routes expose only live affiliate offers; they never return sample listings. Affiliate credentials stay on the backend. The frontend also links each offer to its retailer, shows price freshness, and includes an affiliate disclosure. Without configured affiliate credentials, the deals page explains that no live feed is available. The general catalogue remains available with its clearly labelled sample fallback. Without a configured model, the deterministic rule based workflow remains available.

For public hosting, deploy the frontend and API behind HTTPS, set `NEXT_PUBLIC_API_URL` to the public API origin, set `FRONTEND_URL` and `CORS_ORIGINS` to the public frontend origin, and provide the affiliate credentials through the hosting platform's secret manager (not source control). Configure Amazon's public website / tracking requirements and refresh offer prices according to the applicable affiliate terms.

For a single-domain Linux VPS deployment, see [`deploy/PUBLIC-HOSTING.md`](deploy/PUBLIC-HOSTING.md) and `docker-compose.public.yml`. Caddy routes frontend and API traffic over HTTPS; only ports 80 and 443 are public.

For hosting the frontend on **Vercel** with the backend on **Render**, see [`deploy/VERCEL-RENDER.md`](deploy/VERCEL-RENDER.md): the Blueprint [`render.yaml`](render.yaml) provisions the FastAPI service + free PostgreSQL, and `next.config.ts` proxies `/api/*` to the backend so the session cookie stays same-origin. Local `docker compose up` is unaffected.

## Checks

```powershell
cd backend
pytest            # 89 tests: unit + config + graph memory + integration + offers/reset + featured feed
cd ..\frontend
npm run lint
npm test          # Vitest: landing, login, product card, format helpers
npm run build
```

Database schema changes are versioned with Alembic:

```powershell
cd backend
alembic upgrade head            # apply migrations
alembic revision --autogenerate -m "change description"  # after model edits
```
