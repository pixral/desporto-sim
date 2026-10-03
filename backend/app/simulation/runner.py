"""Drives the engine in the background: pause/resume, speeds, autosave, live broadcasting."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any

from app.ai.gateway import AICallRecord
from app.ai.provider import IAgentModelProvider
from app.domain.world import RunConfig, World
from app.persistence.repository import Repository
from app.sports.provider import ISportsDataProvider

from . import views
from .engine import SimulationEngine
from .factory import create_world

log = logging.getLogger("desporto.runner")

# seconds between phases (4 phases per simulated day)
SPEEDS: dict[str, float] = {"1x": 6.0, "2x": 3.0, "4x": 1.5, "16x": 0.35, "64x": 0.08, "max": 0.0}
MAX_PUBLISH_INTERVAL = 0.2  # throttle websocket pushes at high speed


class SimulationRunner:
    def __init__(self, repo: Repository, make_sports: Callable[[RunConfig], ISportsDataProvider],
                 make_ai: Callable[[RunConfig], IAgentModelProvider]) -> None:
        self.repo = repo
        self.make_sports = make_sports
        self.make_ai = make_ai
        self.engine: SimulationEngine | None = None
        self.running = False
        self.speed = "4x"
        self.subscribers: set[asyncio.Queue[str]] = set()
        self.lock = asyncio.Lock()
        self._wake = asyncio.Event()
        self._pending_ai: list[AICallRecord] = []
        self._last_publish = 0.0
        self._task: asyncio.Task | None = None
        self._last_month = ""
        self.providers: dict[str, str] = {}

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="simulation-loop")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self.flush_ai()

    @property
    def world(self) -> World | None:
        return self.engine.world if self.engine else None

    def _attach(self, world: World, sports: ISportsDataProvider, config: RunConfig) -> None:
        ai = self.make_ai(config)
        self.providers = {"ai": f"{ai.name} ({ai.model_for('tipster_day')})", "sports": sports.name}
        self.engine = SimulationEngine(world, sports, ai, ai_sink=self._pending_ai.append)
        self._last_month = world.today.strftime("%Y-%m")

    async def new_run(self, config: RunConfig) -> World:
        async with self.lock:
            self.running = False
            await self.flush_ai()
            sports = self.make_sports(config)
            world = await asyncio.to_thread(create_world, config, sports)
            self._attach(world, sports, config)
            await self._save("Founding", "auto")
        await self.publish(force=True)
        return world

    async def load(self, save_id: int) -> World:
        async with self.lock:
            self.running = False
            await self.flush_ai()
            world = await asyncio.to_thread(self.repo.load_world, save_id)
            sports = self.make_sports(world.config)
            sports.import_state(world.provider_state)
            self._attach(world, sports, world.config)
        await self.publish(force=True)
        return world

    async def save(self, label: str) -> int:
        async with self.lock:
            return await self._save(label, "manual")

    async def _save(self, label: str, kind: str) -> int:
        assert self.engine is not None
        self.engine.sync_provider_state()
        await self.flush_ai()
        world = self.engine.world
        return await asyncio.to_thread(self.repo.save_world, world, label, kind)

    # ------------------------------------------------------------------ control
    async def control(self, action: str, speed: str | None = None) -> None:
        if speed:
            if speed not in SPEEDS:
                raise ValueError(f"unknown speed {speed}")
            self.speed = speed
        if action == "pause":
            self.running = False
        elif action == "resume":
            if self.engine and not self.engine.world.ended:
                self.running = True
        elif action == "step":
            self.running = False
            await self._do_step()
        elif action == "day":
            self.running = False
            if self.engine:
                target = self.engine.world.clock.day_index + 1
                while self.engine.world.clock.day_index < target and not self.engine.world.ended:
                    await self._do_step(publish=False)
        self._wake.set()
        await self.publish(force=True)

    def runner_state(self) -> dict[str, Any]:
        return {"running": self.running, "speed": self.speed, "speeds": list(SPEEDS),
                "phase_seconds": SPEEDS.get(self.speed, 1.5)}

    # ------------------------------------------------------------------ loop
    async def _do_step(self, publish: bool = True) -> None:
        if self.engine is None or self.engine.world.ended:
            return
        async with self.lock:
            try:
                await self.engine.step()
            except Exception:
                log.exception("simulation step failed; pausing")
                self.running = False
                raise
            world = self.engine.world
            month = world.today.strftime("%Y-%m")
            if world.ended:
                self.running = False
                await self._save(f"Final — {world.end_reason or 'ended'}", "final")
            elif month != self._last_month and world.clock.phase_index == 1:
                self._last_month = month
                await self._save(f"Autosave {month}", "auto")
            elif world.today.weekday() == 0 and world.clock.phase_index == 1:
                # weekly safety net: a hard kill of the server loses at most a week
                await self._save(f"Autosave {world.today.isoformat()}", "auto")
            if len(self._pending_ai) >= 50:
                await self.flush_ai()
        if publish:
            await self.publish()

    async def _loop(self) -> None:
        while True:
            if not self.running or self.engine is None:
                self._wake.clear()
                await self._wake.wait()
                continue
            t0 = time.perf_counter()
            try:
                await self._do_step()
            except Exception:
                await self.publish(force=True)
                continue
            delay = SPEEDS.get(self.speed, 0.6) - (time.perf_counter() - t0)
            if delay > 0:
                try:
                    await asyncio.wait_for(self._wake.wait(), timeout=delay)
                    self._wake.clear()
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(0)

    async def flush_ai(self) -> None:
        if not self._pending_ai:
            return
        batch, self._pending_ai[:] = list(self._pending_ai), []
        try:
            await asyncio.to_thread(self.repo.insert_ai_calls, batch)
        except Exception:
            log.exception("failed to persist AI call log")

    # ------------------------------------------------------------------ broadcasting
    def snapshot(self) -> dict[str, Any] | None:
        if self.engine is None:
            return None
        return views.state_view(self.engine.world, self.runner_state(), self.providers)

    async def publish(self, force: bool = False) -> None:
        now = time.perf_counter()
        if not force and now - self._last_publish < MAX_PUBLISH_INTERVAL:
            return
        self._last_publish = now
        snap = self.snapshot()
        if snap is None or not self.subscribers:
            return
        message = json.dumps({"type": "state", "data": snap}, default=str)
        for q in list(self.subscribers):
            if q.full():
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(message)

    def subscribe(self) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=4)
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[str]) -> None:
        self.subscribers.discard(q)
