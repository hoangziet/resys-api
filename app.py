from __future__ import annotations

from fastapi import FastAPI

from api.admin import router as admin_router
from api.auth import router as auth_router
from api.courses import router as courses_router
from api.history import router as history_router
from api.recommendations import router as recommendations_router
from api.debug import router as debug_router
from core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)
    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(courses_router, prefix=settings.api_prefix)
    app.include_router(history_router, prefix=settings.api_prefix)
    app.include_router(recommendations_router, prefix=settings.api_prefix)
    app.include_router(admin_router, prefix=settings.api_prefix)
    app.include_router(debug_router, prefix=settings.api_prefix)
    return app


app = create_app()
