"""
backend.main — the FastAPI application.

On startup (mode-driven):
  * builds the event bus (Redis Streams, or in-memory fallback),
  * starts the inference pipeline (feature engine + World Model loop),
  * starts sensor collectors (live/hybrid) and/or synthetic replay (replay/
    hybrid),
  * starts the WebSocket broadcaster.

Modes (SYSTEM_MODE / config.mode):
    live   -> Zeek + Suricata collectors
    replay -> synthetic generator
    hybrid -> both

Run:
    uvicorn backend.main:app --host 0.0.0.0 --port 8000
    # or: python -m backend.main
"""
from __future__ import annotations

import contextlib

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from core.bus import get_bus
from core.config import get_settings
from core.logging_setup import get_logger
from backend.api.routes import router as api_router
from backend.services.pipeline import InferencePipeline
from backend.services.shared_state import SharedState
from backend.websocket.manager import ConnectionManager

log = get_logger("backend")


def _start_sources(app: FastAPI):
    """Start collectors / replay according to the configured mode and register
    their status providers so the dashboard can show sensor health."""
    s = get_settings()
    bus = app.state.bus
    shared: SharedState = app.state.shared
    mode = s.mode
    collectors = []
    replay = None

    if mode in ("live", "hybrid"):
        from sensor.collectors.zeek_collector import build_zeek_collector
        from sensor.collectors.suricata_collector import build_suricata_collector
        zc = build_zeek_collector(s, bus)
        sc = build_suricata_collector(s, bus)
        for c in (zc, sc):
            if c is not None:
                c.start()
                collectors.append(c)
                shared.register_status(c.name, (lambda c=c: {**c.status, "ok": c.status["present"]}))
        if not collectors:
            log.warning("live mode but no collectors enabled/available.")

    if mode in ("replay", "hybrid"):
        from replay.synthetic_generator import SyntheticReplay
        replay = SyntheticReplay(bus, s)
        replay.start()
        shared.register_status("replay", lambda: {**replay.status, "ok": True})

    # bus + model status providers
    shared.register_status("redis", lambda: {
        "backend": getattr(bus, "backend", "unknown"),
        "ok": (getattr(bus, "backend", "") == "redis") and bus.ping(),
        "note": ("Redis connected" if getattr(bus, "backend", "") == "redis"
                 else "In-memory bus (Redis not connected)"),
    })
    shared.register_status("model", lambda: {
        "ok": app.state.pipeline.forecaster.available,
        "status": "TRAINED" if app.state.pipeline.forecaster.available else "NOT_TRAINED",
    })

    app.state.collectors = collectors
    app.state.replay = replay


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    log.info("Starting %s (%s) — mode=%s", s.app_name, s.app_full_name, s.mode)

    app.state.bus = get_bus()
    log.info("bus backend: %s", getattr(app.state.bus, "backend", "unknown"))

    app.state.shared = SharedState()
    app.state.pipeline = InferencePipeline(app.state.bus, app.state.shared)
    app.state.ws_manager = ConnectionManager(app.state.shared, interval=1.0)

    _start_sources(app)
    app.state.pipeline.start()
    app.state.ws_manager.start()

    try:
        yield
    finally:
        log.info("shutting down...")
        with contextlib.suppress(Exception):
            await app.state.ws_manager.stop()
        with contextlib.suppress(Exception):
            app.state.pipeline.stop()
        for c in getattr(app.state, "collectors", []):
            with contextlib.suppress(Exception):
                c.stop()
        if getattr(app.state, "replay", None):
            with contextlib.suppress(Exception):
                app.state.replay.stop()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title=f"{s.app_name} — {s.app_full_name}",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.get("/")
    def root():
        return {
            "name": s.app_name,
            "full_name": s.app_full_name,
            "team": s.team,
            "docs": "/docs",
            "health": "/api/health",
            "websocket": "/ws/live",
        }

    @app.websocket("/ws/live")
    async def ws_live(ws: WebSocket):
        manager: ConnectionManager = app.state.ws_manager
        await manager.connect(ws)
        try:
            while True:
                # We don't require client messages; keep the socket alive and
                # ignore anything received. Broadcaster pushes updates.
                await ws.receive_text()
        except WebSocketDisconnect:
            await manager.disconnect(ws)
        except Exception:
            await manager.disconnect(ws)

    return app


app = create_app()


def main():
    import uvicorn
    s = get_settings()
    uvicorn.run("backend.main:app", host=s.host, port=s.port, reload=False)


if __name__ == "__main__":
    main()
