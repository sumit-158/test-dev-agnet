"""App factory: routers registered (from v2), static frontend served."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.config import Settings, load_settings

STATIC_DIR = Path(__file__).parent / "static"


def create_app(
    settings: Settings, volume_repository=None, parse_repository=None, gateway=None
) -> FastAPI:
    """App factory; dependencies default to the real implementations added in later features."""
    logging.basicConfig(level=settings.LOG_LEVEL)
    app = FastAPI(title="SCO-001 PIR / SL chat")
    app.state.settings = settings
    app.state.volume_repository = volume_repository
    app.state.parse_repository = parse_repository
    app.state.gateway = gateway

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

    return app


def __getattr__(name: str) -> FastAPI:
    """Build the module-level ``app`` (``uvicorn backend.main:app``) on first access.

    Equivalent to ``app = create_app(load_settings())`` guarded by ``if __name__ != "test"``, but
    lazy (PEP 562) so that importing ``create_app`` in tests does not require the environment.
    A missing setting still raises ValueError when uvicorn loads ``app`` at start-up.
    """
    if name == "app" and __name__ != "test":
        application = create_app(load_settings())
        globals()["app"] = application
        return application
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
