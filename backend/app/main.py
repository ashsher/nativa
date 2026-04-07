"""
app/main.py — FastAPI application entry point.

Creates the FastAPI application, registers middleware, mounts all API routers,
and exposes a startup event that ensures the database schema is up-to-date.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.middleware.auth_middleware import AuthMiddleware
from app.middleware.quota_middleware import QuotaMiddleware

# ---------------------------------------------------------------------------
# Import all models so Base.metadata is populated before create_all is called.
# ---------------------------------------------------------------------------
import app.models  # noqa: F401 — side-effect import registers ORM metadata

# ---------------------------------------------------------------------------
# Import routers
# ---------------------------------------------------------------------------
from app.routers.auth import router as auth_router
from app.routers.user import router as user_router
from app.routers.video import router as video_router
from app.routers.reading import router as reading_router
from app.routers.vocabulary import router as vocabulary_router
from app.routers.ai import router as ai_router
from app.routers.speaking import router as speaking_router
from app.routers.payment import router as payment_router


# ---------------------------------------------------------------------------
# Lifespan context — runs startup and shutdown logic.
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    On startup: create any missing database tables using the ORM metadata.
    This is safe to run on every startup; SQLAlchemy skips existing tables.
    In production you should prefer Alembic migrations over create_all, but
    create_all serves as a convenient safety net.
    """
    # Create all tables that are registered in Base.metadata.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield  # Application runs here.

    # On shutdown: dispose the connection pool cleanly.
    await engine.dispose()


# ---------------------------------------------------------------------------
# FastAPI application instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Nativa API",
    version="1.0.0",
    description=(
        "Nativa — Telegram WebApp orqali til o'rgatish platformasi uchun backend API."
    ),
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------
# Must be added before custom middleware so it runs first on the way in and
# last on the way out (Starlette middleware stack is LIFO).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Custom middleware
# ---------------------------------------------------------------------------
# QuotaMiddleware logs quota-affecting requests (passive observer).
app.add_middleware(QuotaMiddleware)

# AuthMiddleware validates Telegram InitData on every protected endpoint.
app.add_middleware(AuthMiddleware)

# ---------------------------------------------------------------------------
# API routers — all mounted under /api
# ---------------------------------------------------------------------------
API_PREFIX = "/api"

app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(user_router, prefix=API_PREFIX)
app.include_router(video_router, prefix=API_PREFIX)
app.include_router(reading_router, prefix=API_PREFIX)
app.include_router(vocabulary_router, prefix=API_PREFIX)
app.include_router(ai_router, prefix=API_PREFIX)
app.include_router(speaking_router, prefix=API_PREFIX)
app.include_router(payment_router, prefix=API_PREFIX)


# ---------------------------------------------------------------------------
# Root health-check endpoint
# ---------------------------------------------------------------------------
@app.get("/", tags=["health"], summary="API salomatlik tekshiruvi")
async def root() -> dict:
    """
    Simple health-check endpoint.

    Returns a JSON object confirming the service is running.
    Used by load balancers and uptime monitors.
    """
    return {"status": "ok", "app": "Nativa"}
