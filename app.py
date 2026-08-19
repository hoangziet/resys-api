from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from api.admin import router as admin_router
from api.auth import router as auth_router
from api.courses import router as courses_router
from api.debug import router as debug_router
from api.history import router as history_router
from api.recommendations import router as recommendations_router
from core import database
from core.config import settings
from core.monitoring import RecommendationMetricsMiddleware
from core.rate_limit import limiter
from models.catalog import catalog


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        if request.url.path.startswith("/api/v1/recommendations"):
            response.headers["Cache-Control"] = "private, max-age=60"
        return response


def create_app() -> FastAPI:
    database.init_db()

    # Load the localized course catalog from SQLite (display layer)
    catalog.load()

    # Pre-load recommendation model at startup
    from api.recommendations import load_recommendation_model

    load_recommendation_model()

    app = FastAPI(title=settings.app_name)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(CacheControlMiddleware)
    # Measures every /recommendations request, including failures.
    app.add_middleware(RecommendationMetricsMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(courses_router, prefix=settings.api_prefix)
    app.include_router(history_router, prefix=settings.api_prefix)
    app.include_router(recommendations_router, prefix=settings.api_prefix)
    app.include_router(admin_router, prefix=settings.api_prefix)
    app.include_router(debug_router, prefix=settings.api_prefix)

    app.mount("/assets", StaticFiles(directory="assets"), name="assets")

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "app": settings.app_name}

    @app.get("/", response_class=HTMLResponse)
    def read_root():
        index_path = Path("assets/index.html")
        if index_path.exists():
            return index_path.read_text(encoding="utf-8")
        return "<h3>Index file not found in assets/</h3>"

    return app


app = create_app()
