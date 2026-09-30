"""
backend.websocket.manager — WebSocket connection manager + broadcaster.

Clients connect to /ws/live. A single async broadcaster task reads the latest
snapshot from SharedState on a fixed cadence and pushes it to every connected
client. Dead connections are pruned. The broadcaster never raises out of its
loop, so one bad client cannot stop updates to the others.
"""
from __future__ import annotations

import asyncio
import json
from typing import List, Set

from starlette.websockets import WebSocket, WebSocketState

from core.logging_setup import get_logger

log = get_logger("ws")


class ConnectionManager:
    def __init__(self, shared, interval: float = 1.0):
        self.shared = shared
        self.interval = interval
        self._clients: Set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._task = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
        log.info("ws client connected (%d total)", len(self._clients))
        # send an immediate snapshot so the UI populates instantly
        try:
            await ws.send_text(json.dumps(self.shared.get_snapshot(), default=str))
        except Exception:
            pass

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)
        log.info("ws client disconnected (%d total)", len(self._clients))

    async def _broadcast_once(self) -> None:
        if not self._clients:
            return
        payload = json.dumps(self.shared.get_snapshot(), default=str)
        dead: List[WebSocket] = []
        async with self._lock:
            clients = list(self._clients)
        for ws in clients:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(payload)
                else:
                    dead.append(ws)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    async def run(self) -> None:
        log.info("ws broadcaster started (interval=%.1fs)", self.interval)
        while True:
            try:
                await self._broadcast_once()
            except Exception as exc:  # never die
                log.debug("broadcast error: %s", exc)
            await asyncio.sleep(self.interval)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self.run())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None

    @property
    def client_count(self) -> int:
        return len(self._clients)
