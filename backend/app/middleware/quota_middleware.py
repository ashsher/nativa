"""
app/middleware/quota_middleware.py — Request-level quota tracking middleware.

This middleware is intentionally lightweight: it does NOT enforce limits
(that is done inside individual service functions via quota_service).
Its sole responsibility is to record which quota-affecting endpoint was
called so usage can be inspected in logs or metrics systems.

Quota enforcement lives in the services layer because it requires knowledge
of whether a user is premium, which is only available after DB lookup.
"""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = logging.getLogger("nativa.quota")

# ---------------------------------------------------------------------------
# Map path prefixes to the quota type they affect.
# Used for logging/observability only.
# ---------------------------------------------------------------------------
_QUOTA_PATH_MAP: dict[str, str] = {
    "/api/vocabulary/review": "srs_count",
    "/api/ai/explain": "ai_count",
    "/api/speaking/connect": "speaking_count",
}


class QuotaMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs quota-affecting requests and their latency.

    This is a passive observer — it never modifies the request or response.
    Active quota enforcement is handled inside each service function.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # --- Identify which quota type (if any) this request affects ---
        quota_type: str | None = None
        for path_prefix, q_type in _QUOTA_PATH_MAP.items():
            if request.url.path.startswith(path_prefix):
                quota_type = q_type
                break

        # --- Record start time for latency logging ---
        start = time.monotonic()

        # --- Pass through to the actual handler ---
        response = await call_next(request)

        # --- Log quota-relevant requests with their outcome ---
        if quota_type:
            elapsed_ms = round((time.monotonic() - start) * 1000)
            # Safely extract user_id from request state set by AuthMiddleware.
            user_id = (
                request.state.user.get("id", "unknown")
                if hasattr(request.state, "user") and isinstance(request.state.user, dict)
                else "unknown"
            )
            logger.info(
                "quota_request quota_type=%s user_id=%s status=%d latency_ms=%d",
                quota_type,
                user_id,
                response.status_code,
                elapsed_ms,
            )

        return response
