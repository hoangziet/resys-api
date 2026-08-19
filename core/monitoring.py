"""Recommendation request monitoring.

Latency is measured in middleware rather than inside each handler so that every
recommendation request produces exactly one ``recommendation_logs`` row -
including the ones that fail. A handler that raises, or a request rejected by the
rate limiter, never reaches its own logging call, and percentiles built only from
successful requests hide precisely the incidents monitoring exists to catch.

Handlers contribute the parts middleware cannot know (which strategy ran, the
input history, the returned item ids) by setting ``request.state.rec_log``.
"""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core import database
from core.config import settings

log = logging.getLogger(__name__)

REC_LOG_STATE_ATTR = "rec_log"


def record(
    request: Request,
    *,
    strategy: str,
    history: list[int] | None = None,
    results: list[int] | None = None,
    username: str | None = None,
) -> None:
    """Attach recommendation detail for the middleware to persist.

    Called by handlers instead of writing a log row themselves, so a request that
    later fails still yields a single row with the real status code.
    """
    setattr(
        request.state,
        REC_LOG_STATE_ATTR,
        {
            "strategy": strategy,
            "history": list(history or []),
            "results": list(results or []),
            "username": username,
        },
    )


class RecommendationMetricsMiddleware(BaseHTTPMiddleware):
    """Time every /recommendations request and persist one row per request."""

    def __init__(self, app, prefix: str | None = None):
        super().__init__(app)
        self.prefix = prefix or f"{settings.api_prefix}/recommendations"

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith(self.prefix):
            return await call_next(request)

        start = time.perf_counter()
        status_code = 500
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            latency_ms = (time.perf_counter() - start) * 1000
            self._persist(request, status_code, latency_ms)

    def _persist(self, request: Request, status_code: int, latency_ms: float) -> None:
        detail = getattr(request.state, REC_LOG_STATE_ATTR, None) or {}
        try:
            database.log_recommendation(
                username=detail.get("username"),
                # A request that failed before the handler picked a strategy still
                # gets a row, labelled so it is distinguishable in the breakdown.
                strategy=detail.get("strategy") or f"unhandled_{status_code}",
                latency_ms=latency_ms,
                history=detail.get("history") or [],
                results=detail.get("results") or [],
                endpoint=request.url.path,
                status_code=status_code,
            )
        except Exception:
            # Monitoring must never take down the request path.
            log.exception("Failed to record recommendation metrics")
