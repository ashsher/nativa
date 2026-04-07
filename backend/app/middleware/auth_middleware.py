"""
app/middleware/auth_middleware.py — Telegram InitData authentication middleware.

Every authenticated endpoint requires a valid Telegram WebApp InitData token.
The middleware intercepts requests, extracts the token, validates it, and
attaches the user object to request.state so route handlers can access it
without re-authenticating.
"""

from __future__ import annotations

import json

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp
from fastapi import HTTPException

from app.services import auth_service

# ---------------------------------------------------------------------------
# Paths that do not require authentication.
# ---------------------------------------------------------------------------
_PUBLIC_PATHS = {
    "/",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/auth/validate",
}


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that validates Telegram WebApp InitData on every request.

    Token lookup order:
      1. X-Telegram-Init-Data header (preferred for WebApp clients).
      2. Authorization header with "Bearer <init_data>" format (fallback).

    On success: attaches validated user dict to request.state.user.
    On failure: returns a 401 JSON response immediately.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # --- Skip authentication for public paths ---
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        # Also skip paths that start with known public prefixes (e.g. /static).
        if request.url.path.startswith("/static"):
            return await call_next(request)

        # --- Extract InitData from headers ---
        init_data: str | None = None

        # Preferred header: X-Telegram-Init-Data
        x_init = request.headers.get("X-Telegram-Init-Data")
        if x_init:
            init_data = x_init
        else:
            # Fallback: Authorization: Bearer <init_data>
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                init_data = auth_header[len("Bearer "):]

        # --- Return 401 if no token was provided ---
        if not init_data:
            return JSONResponse(
                status_code=401,
                content={
                    "detail": "Autentifikatsiya talab etiladi. "
                    "Iltimos, Telegram orqali kiring."
                },
            )

        # --- Validate the InitData signature ---
        try:
            user_data = auth_service.validate_init_data(init_data)
        except HTTPException as exc:
            # validate_init_data raises HTTPException with a detail message.
            return JSONResponse(status_code=401, content={"detail": exc.detail})

        # --- Attach validated user dict to request state ---
        # Route handlers can now access: request.state.user["id"], etc.
        request.state.user = user_data

        # --- Pass request on to the next handler ---
        return await call_next(request)
