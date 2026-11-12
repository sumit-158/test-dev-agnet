"""FastAPI app factory: health route (API-04), error handlers and the built frontend."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.config import Settings, load_settings, make_connection_factory

logger = logging.getLogger(__name__)


def create_app(settings: Settings, connection_factory: Callable[[], Any]) -> FastAPI:
    """Build the FastAPI app: state.settings, state.connection_factory, API-04, static files,
    error handlers."""
    app = FastAPI(title="MRPX-002 Shortage Rebalancing", docs_url=None, redoc_url=None)
    app.state.settings = settings
    app.state.connection_factory = connection_factory

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "catalog": settings.catalog, "schema_gold": settings.schema_gold}

    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

        @app.exception_handler(404)
        async def spa_fallback(request: Request, exc: StarletteHTTPException) -> Response:
            if request.url.path.startswith("/api/"):
                return await http_exception_handler(request, exc)
            return FileResponse(static_dir / "index.html")
    else:
        logger.info("No frontend build at %s; serving the API only", static_dir)

    return app


def get_app() -> FastAPI:
    """Factory for uvicorn --factory: create_app(load_settings(), make_connection_factory(...))."""
    settings = load_settings()
    return create_app(settings, make_connection_factory(settings))
