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
from app.ai.schemas import CEOAction
from app.domain.events import ActionRecord
from app.domain.player import Proposal
from app.domain.world import RunConfig, World
from app.persistence.repository import Repository
from app.sports.provider import ISportsDataProvider

from . import god, player, views
from .engine import SimulationEngine
from .factory import create_world

log = logging.getLogger("desporto.runner")

# seconds between phases (4 phases per simulated day)
SPEEDS: dict[str, float] = {"1x": 6.0, "2x": 3.0, "4x": 1.5, "16x": 0.35, "64x": 0.08, "max": 0.0}
MAX_PUBLISH_INTERVAL = 0.2  # throttle websocket pushes at high speed
AUTOSAVE_MIN_SECONDS = 60.0  # real time between autosaves (saves grow to megabytes after a few years)


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
        self._last_autosave = 0.0
        self._resume_after_review = False  # the clock was running when a briefing stopped it
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
            if world.config.ironman and not world.ended:
                latest = await asyncio.to_thread(self.repo.latest_save_id, world.run_id)
                if latest is not None and save_id != latest:
                    raise PermissionError("Ironman company: only its latest save can be loaded")
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
            self._resume_after_review = False
        elif action == "resume":
            if self.engine and not self.engine.world.ended:
                if player.awaiting(self.engine.world):
                    self._resume_after_review = True  # runs on as soon as the briefing is signed
                else:
                    self.running = True
        elif action == "step":
            self.running = False
            await self._do_step()
        elif action == "day":
            self.running = False
            if self.engine:
                target = self.engine.world.clock.day_index + 1
                while self.engine.world.clock.day_index < target and not self.engine.world.ended:
                    if player.awaiting(self.engine.world):
                        break
                    await self._do_step(publish=False)
        self._wake.set()
        await self.publish(force=True)

    async def god(self, action: str, params: dict[str, Any]) -> str:
        """Apply a sandbox intervention between two simulation steps."""
        if self.engine is None:
            raise god.GodError("no company loaded")
        if self.engine.world.config.ironman:
            raise god.GodError("Ironman company: the sandbox is locked")
        async with self.lock:
            message = god.apply(self.engine.world, self.engine.rng, action, params)
        await self.publish(force=True)
        return message

    # ------------------------------------------------------------------ player mode
    def _player_engine(self) -> SimulationEngine:
        if self.engine is None or not player.active(self.engine.world):
            raise ValueError("you are not running this company")
        return self.engine

    async def resolve_review(self, actions: list[CEOAction], memo: str) -> list[ActionRecord]:
        """Sign off the open briefing; the clock carries on if it was running when the briefing opened."""
        engine = self._player_engine()
        async with self.lock:
            records = await engine.resolve_review(actions, memo)
            if self._resume_after_review and not engine.world.ended:
                self.running = True
            self._resume_after_review = False
        self._wake.set()
        await self.publish(force=True)
        return records

    async def office_action(self, action: CEOAction) -> ActionRecord:
        engine = self._player_engine()
        async with self.lock:
            rec = engine.office_action(action)
        await self.publish(force=True)
        return rec

    async def queue(self, action: CEOAction) -> Proposal:
        engine = self._player_engine()
        async with self.lock:
            p = player.queue(engine.world, action)
        await self.publish(force=True)
        return p

    async def unqueue(self, index: int) -> None:
        engine = self._player_engine()
        async with self.lock:
            player.unqueue(engine.world, index)
        await self.publish(force=True)

    def runner_state(self) -> dict[str, Any]:
        return {"running": self.running, "speed": self.speed, "speeds": list(SPEEDS),
                "phase_seconds": SPEEDS.get(self.speed, 1.5), "resume_after_review": self._resume_after_review}

    # ------------------------------------------------------------------ loop
    async def _do_step(self, publish: bool = True) -> None:
        if self.engine is None or self.engine.world.ended:
            return
        async with self.lock:
            try:
                result = await self.engine.step()
            except Exception:
                log.exception("simulation step failed; pausing")
                self.running = False
                raise
            world = self.engine.world
            if result == "awaiting_ceo" or player.awaiting(world):
                # a briefing is waiting for the player: stop the clock, carry on after the sign-off
                self._resume_after_review = self._resume_after_review or self.running
                self.running = False
            month = world.today.strftime("%Y-%m")
            if world.ended:
                self.running = False
                await self._save(f"Final — {world.end_reason or 'ended'}", "final")
            elif world.clock.phase_index == 1 and (month != self._last_month or world.today.weekday() == 0):
                # month closes and Mondays are save points, but at most once a minute of real time so
                # fast-forwarding isn't slowed down by writing multi-megabyte saves
                if time.perf_counter() - self._last_autosave >= AUTOSAVE_MIN_SECONDS:
                    label = f"Autosave {month}" if month != self._last_month else f"Autosave {world.today.isoformat()}"
                    await self._save(label, "auto")
                    self._last_autosave = time.perf_counter()
                self._last_month = month
            if len(self._pending_ai) >= 50:
                await self.flush_ai()
            stopped = world.ended or player.awaiting(world)
        if publish:
            # the clock stopping (a briefing, the end) must reach the UI even at full speed
            await self.publish(force=stopped)

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
