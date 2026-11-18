# SHOPMATE AI — System Architecture

> Stage 1 deliverable. This document is the implementation blueprint for the whole project.

## 1. High-level topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│  FRONTEND  (Next.js App Router · TypeScript · Tailwind · Framer/GSAP)  │
│  Landing · Login/Signup · Dashboard · Chat · Explore · Compare ·       │
│  Saved · Watchlist · History · Settings · R3F 3D scenes                │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │  REST + SSE (JSON, JWT in httpOnly cookie)
┌───────────────────────────────▼─────────────────────────────────────────┐
│  BACKEND  (FastAPI · Pydantic · SQLAlchemy 2.0 · Alembic)              │
│                                                                         │
│  api/        auth · chat · products · compare · recommendations ·      │
│              reviews · conversations · watchlist · health               │
│  services/   auth · product · pricing · recommendation · review ·      │
│              conversation · llm                                         │
│  providers/  base(ABC) · mock_provider(sample dataset) ·               │
│              merchant_provider(authorized/affiliate HTTP API)           │
│  agents/     query · search · price · review · specification ·         │
│              recommendation · shopping_advisor                          │
│  graph/      state(TypedDict) · nodes · routing · shopping_graph       │
│  utils/      embeddings · ranking · validators · security               │
└──────┬───────────────────────────┬──────────────────────┬───────────────┘
       │                           │                      │
┌──────▼──────┐          ┌─────────▼────────┐   ┌─────────▼─────────┐
│ PostgreSQL  │          │ Redis (optional) │   │ LLM abstraction   │
│ (SQLAlchemy │          │ cache + rate     │   │ HF Inference API  │
│  + Alembic) │          │ limit, in-mem    │   │ Ollama (local)    │
└─────────────┘          │ fallback         │   │ rule-based fallback│
                         └──────────────────┘   └───────────────────┘
```

## 2. Agentic AI (LangGraph)

Typed graph state (`graph/state.py`) carries the whole research run:

```
START → understand → route ─┬─(product_search)──→ search ─┐
                            ├─(product_compare)→ compare ─┼→ spec → recommend → advise → END
                            ├─(review_analysis)→ review ──┤
                            └─(general/shopping advice)───┘
```

* **Conditional router** (`routing.py`) classifies intent from the structured
  understanding and picks *only* the branches needed — no agent is invoked
  for every query.
* **Parallel fan-out** with `langgraph.types.Send`: when a query needs both
  discovery and review analysis, both branch nodes run in the same super-step
  and converge on specification analysis.
* **Retry/fallback**: every node catches its own errors, records them in
  `state["errors"]`, and degrades to a documented fallback so the graph always
  reaches the advisor node.
* **Checkpointing**: custom `BaseCheckpointSaver` persisted through SQLAlchemy
  (`graph/checkpointer.py`) → conversation context survives restarts on
  PostgreSQL (and SQLite in tests).
* **Agents are independently testable**: each agent is a class with a pure
  `run()`/`invoke()` method taking typed input and returning typed output.

## 3. LLM provider abstraction

`services/llm_service.py` exposes one interface:

```python
class LLMClient(ABC):
    def complete_json(self, system: str, user: str, schema: type[BaseModel]) -> LLMResult
```

Implementations: `HuggingFaceProvider` (HF Inference API, `HF_TOKEN`), `OllamaProvider`
(`OLLAMA_BASE_URL`/`OLLAMA_MODEL`), and `NullProvider`. If no provider is
configured, reachable, or returns invalid structured output, agents fall back
to deterministic rule-based extractors (regex/heuristics) and mark
`llm_mode: "rule-based-fallback"` in the output — responses are never
hardcoded answers, they are computed from real input + real data.

## 4. Data providers

* `providers/base.py` — `ProductProvider` ABC + normalized `Product` schema
  shared by every adapter.
* `providers/mock_provider.py` — **sample dataset** (clearly labelled
  `source_type="sample"` and surfaced in the UI with a "Sample data" badge).
  Used for local dev/tests so the product search works without merchant
  credentials. Prices/reviews come from this dataset and are never presented
  as live.
* `providers/merchant_provider.py` — HTTP adapter for authorized merchant /
  affiliate APIs. Configured via env (`MERCHANT_API_URL`, `MERCHANT_API_KEY`);
  returns an explicit "provider not configured" status instead of fabricating
  data when absent.
* Provider registry merges, dedupes (by title+brand+merchant) and stamps
  `last_verified_at`.

## 5. Recommendation engine

Hybrid, explainable, category-configurable weights:

```
final = 0.35·spec_match + 0.25·budget_suitability
      + 0.20·preference_similarity + 0.20·review_quality
```

* `utils/embeddings.py` — Sentence-Transformers when installed
  (`requirements-ml.txt`), otherwise a deterministic TF-IDF/hashing embedder so
  semantic search still works offline.
* Missing reviews ⇒ neutral-low review score (never a perfect score).
* Every ranked product returns per-factor scores + human-readable reasons.

## 6. Auth

* JWT (HS256) issued by FastAPI, stored in **httpOnly, SameSite=Lax cookie**
  (plus returned in body for API clients).
* Passwords hashed with **bcrypt** (never plain text).
* `GET /api/auth/me`, logout, register, forgot-password endpoints.
* **Google OAuth 2.0 authorization-code flow** handled server-side:
  `/api/auth/google/login` → Google consent → `/api/auth/google/callback`
  → id_token verified against Google's JWKS → session created. Returns 503
  `google_oauth_not_configured` when credentials are absent (never faked).
* Backend authorization dependency validates JWT independently of any
  frontend route protection; all user-scoped queries filter by `user_id`.

## 7. Streaming

`POST /api/chat` supports `?stream=true` → Server-Sent Events streaming of
graph node progress + token deltas; non-streaming returns the full payload.

## 8. Testing strategy

* **Backend (pytest)**: auth (register/login/me/logout/google), product
  search/filter/compare, recommendation ranking determinism, review analysis,
  conversation persistence, graph routing (incl. parallel fan-out and
  fallback), provider failure handling, watchlist isolation between users.
* **Frontend (Vitest + Testing Library)**: landing, login, signup, dashboard,
  product card, comparison table, responsive smoke tests.
* **Integration**: query → LangGraph → provider → recommendation; auth-guarded
  API calls; conversation memory across requests.
* Tests use SQLite so they run without Docker; production uses PostgreSQL.

## 9. Environment & deployment

* `docker-compose.yml`: postgres + redis + backend + frontend.
* `backend/Dockerfile`, `frontend/Dockerfile` (standalone Next.js output).
* Frontend deployable to Vercel; backend to any Docker host.
* All secrets via `.env` (see `.env.example`); nothing committed.
