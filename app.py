from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from api.admin import router as admin_router
from api.auth import router as auth_router
from api.courses import router as courses_router
from api.debug import router as debug_router
from api.history import router as history_router
from api.recommendations import router as recommendations_router
from core.config import settings
from core import database


def create_app() -> FastAPI:
    database.init_db()

    app = FastAPI(title=settings.app_name)
    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(courses_router, prefix=settings.api_prefix)
    app.include_router(history_router, prefix=settings.api_prefix)
    app.include_router(recommendations_router, prefix=settings.api_prefix)
    app.include_router(admin_router, prefix=settings.api_prefix)
    app.include_router(debug_router, prefix=settings.api_prefix)
    
    app.mount("/assets", StaticFiles(directory="assets"), name="assets")

    @app.get("/", response_class=HTMLResponse)
    def read_root():
        import os
        index_path = os.path.join("assets", "index.html")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                return f.read()
        return "<h3>Index file not found in assets/</h3>"

    return app


app = create_app()

