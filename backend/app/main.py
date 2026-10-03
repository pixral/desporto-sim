"""FastAPI application. Run with:  uvicorn app.main:app --port 8000"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router, ws_router
from app.config import Settings, get_settings
from app.persistence.repository import Repository
from app.providers import make_ai_provider, make_sports_provider
from app.simulation.runner import SimulationRunner


def create_app(settings: Settings | None = None, autostart_run: bool = True) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        repo = Repository(settings.database_url)
        runner = SimulationRunner(repo, make_sports_provider, lambda cfg: make_ai_provider(settings, cfg))
        app.state.runner = runner
        app.state.settings = settings
        runner.start()
        if autostart_run:
            saves = repo.list_saves(limit=20)
            resumable = next((s for s in saves if not s["ended"]), None)
            if resumable:
                await runner.load(resumable["id"])
            else:
                from app.domain.world import RunConfig

                await runner.new_run(RunConfig(ai_provider=settings.ai_provider))
        yield
        if runner.engine is not None and not runner.engine.world.ended:
            await runner.save("Autosave on shutdown")
        await runner.stop()

    app = FastAPI(title="Desporto & Cia.", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)
    app.include_router(ws_router)

    dist = settings.frontend_dist
    if dist.exists() and (dist / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            target = dist / path
            if path and target.is_file():
                return FileResponse(target)
            return FileResponse(dist / "index.html")

    return app


app = create_app()
