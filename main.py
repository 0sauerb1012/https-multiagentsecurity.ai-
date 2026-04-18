from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from routes.web import router as web_router


def create_app() -> FastAPI:
    app = FastAPI(title="Multi-Agent Security Research Hub", version="0.1.0")
    app.include_router(web_router)

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    return app


app = create_app()
