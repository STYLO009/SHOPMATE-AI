"""FastAPI application entry point.

Run locally:  uvicorn app.main:app --reload --port 8000
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    auth,
    chat,
    conversations,
    offers,
    products,
    recommendations,
    reviews,
    watchlist,
)
from app.core.config import settings
from app.database.connection import init_db
from app.providers.art import ensure_product_art

# --- logging ---------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("shopmate")


# --- lifespan --------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()                 # create tables for dev/tests (Alembic for prod)
    logger.info(
        "ShopMate AI started env=%s provider=%s google_oauth=%s",
        settings.environment,
        settings.llm_provider,
        settings.google_oauth_configured,
    )
    yield


app = FastAPI(
    title="ShopMate AI API",
    version="1.0.0",
    description="Autonomous agentic AI shopping intelligence platform.",
    lifespan=lifespan,
)

# --- CORS ------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,  # httpOnly session cookie
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- rate limiting ---------------------------------------------------------
# In-memory sliding window per IP; Redis-backed limiter is layered on top
# automatically when REDIS_URL is reachable (see _redis_rate_limited).
_rate_buckets: dict[str, list[float]] = {}


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _redis_rate_limited(ip: str) -> bool:
    """Redis fixed-window rate limit; returns False when Redis is unavailable."""
    if not settings.redis_url:
        return False
    try:
        import redis.asyncio as aiored

        client = aiored.from_url(settings.redis_url,
                                 socket_connect_timeout=0.5, socket_timeout=0.5)
        try:
            key = f"ratelimit:{ip}"
            count = await client.incr(key)
            if count == 1:
                await client.expire(key, settings.rate_limit_window_seconds)
            return count > settings.rate_limit_requests
        finally:
            await client.aclose()
    except Exception:
        return False  # Redis down → fall back to in-memory limiter


@app.middleware("http")
async def rate_limit_and_timing(request: Request, call_next):
    ip = _client_ip(request)
    now = time.monotonic()
    window = settings.rate_limit_window_seconds

    if await _redis_rate_limited(ip):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": {"code": "rate_limited",
                                "message": "Too many requests. Slow down."}},
            headers={"Retry-After": str(window)},
        )
    else:
        bucket = _rate_buckets.setdefault(ip, [])
        bucket[:] = [t for t in bucket if now - t < window]
        if len(bucket) >= settings.rate_limit_requests:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": {"code": "rate_limited",
                                    "message": "Too many requests. Slow down."}},
                headers={"Retry-After": str(window)},
            )
        bucket.append(now)

    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    started = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = str(
        int((time.perf_counter() - started) * 1000)
    )
    return response


# --- error handlers --------------------------------------------------------
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Never leak internals (stack traces / secrets) to clients.
    logger.exception("unhandled_error path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": {"code": "internal_error",
                            "message": "An unexpected error occurred."}},
    )


# --- routes ----------------------------------------------------------------
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(products.router)
app.include_router(recommendations.router)
app.include_router(reviews.router)
app.include_router(conversations.router)
app.include_router(watchlist.router)
app.include_router(offers.router)


@app.get("/api/health", tags=["system"])
async def health():
    """Liveness + dependency checks (used by Docker healthchecks)."""
    from sqlalchemy import text

    from app.database.connection import SessionLocal
    from app.providers import get_registry

    checks: dict[str, str] = {}
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            checks["database"] = "ok"
        finally:
            db.close()
    except Exception as exc:
        checks["database"] = f"error: {type(exc).__name__}"

    try:
        registry = get_registry()
        checks["providers"] = ",".join(registry.provider_names)
        checks["merchant_provider"] = (
            "configured" if registry.merchant.configured else "not_configured"
        )
    except Exception as exc:
        checks["providers"] = f"error: {type(exc).__name__}"

    checks["google_oauth"] = (
        "configured" if settings.google_oauth_configured else "not_configured"
    )
    checks["llm_provider"] = settings.llm_provider
    checks["affiliate_providers"] = {
        "amazon_creators": "configured" if settings.amazon_creators_configured else "not_configured",
        "flipkart_affiliate": "configured" if settings.flipkart_affiliate_configured else "not_configured",
    }

    healthy = checks["database"] == "ok"
    return {
        "status": "ok" if healthy else "degraded",
        "app": settings.app_name,
        "version": "1.0.0",
        "checks": checks,
    }


# --- static assets (sample product illustrations) --------------------------
# Written eagerly at import time so StaticFiles has its directory.
from app.providers.art import PRODUCTS_DIR  # noqa: E402

ensure_product_art()
app.mount("/static", StaticFiles(directory=str(PRODUCTS_DIR.parent)), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
