"""REST + WebSocket API."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.agents.catalog import CEO_STYLE_INFO
from app.domain.world import CEO_STYLES, RunConfig
from app.economy.config import DIFFICULTY
from app.simulation import city, god, views
from app.simulation.runner import SPEEDS, SimulationRunner

router = APIRouter(prefix="/api")


def runner_of(request: Request) -> SimulationRunner:
    return request.app.state.runner


def world_or_404(runner: SimulationRunner):
    if runner.world is None:
        raise HTTPException(404, "no simulation loaded")
    return runner.world


class NewRunRequest(BaseModel):
    company_name: str = Field("Desporto & Cia.", max_length=60)
    ceo_style: Literal["conservative_operator", "aggressive_expansionist", "data_driven", "chaotic_founder"] = "data_driven"
    seed: int = 7
    start_date: date = date(2026, 8, 14)
    starting_capital: float = Field(20000.0, ge=2000, le=1_000_000)
    initial_tipsters: int = Field(8, ge=2, le=16)
    difficulty: Literal["easy", "normal", "hard"] = "normal"
    ai_provider: Literal["mock", "anthropic"] = "mock"


class ControlRequest(BaseModel):
    action: Literal["pause", "resume", "step", "day", "speed"]
    speed: str | None = None


class SaveRequest(BaseModel):
    label: str = Field("Manual save", max_length=120)


class GodRequest(BaseModel):
    action: str = Field(max_length=40)
    params: dict[str, Any] = Field(default_factory=dict)


@router.get("/meta")
def meta(request: Request) -> dict[str, Any]:
    s = request.app.state.settings
    return {
        "ceo_styles": [{"key": k, **CEO_STYLE_INFO[k]} for k in CEO_STYLES],
        "speeds": list(SPEEDS),
        "defaults": NewRunRequest().model_dump(mode="json"),
        "ai_provider_default": s.ai_provider,
        "default_model": s.default_model,
        "paper_trading_only": True,
        "difficulties": [{"key": k, **v} for k, v in DIFFICULTY.items()],
    }


@router.get("/state")
def state(request: Request) -> dict[str, Any]:
    snap = runner_of(request).snapshot()
    if snap is None:
        raise HTTPException(404, "no simulation loaded")
    return snap


@router.post("/runs")
async def new_run(body: NewRunRequest, request: Request) -> dict[str, Any]:
    runner = runner_of(request)
    config = RunConfig(company_name=body.company_name, ceo_style=body.ceo_style, seed=body.seed,
                       start_date=body.start_date, starting_capital=body.starting_capital,
                       initial_tipsters=body.initial_tipsters, difficulty=body.difficulty,
                       ai_provider=body.ai_provider)
    try:
        world = await runner.new_run(config)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"run_id": world.run_id}


@router.post("/control")
async def control(body: ControlRequest, request: Request) -> dict[str, Any]:
    runner = runner_of(request)
    world_or_404(runner)
    try:
        await runner.control("speed" if body.action == "speed" else body.action, body.speed)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return runner.runner_state()


@router.get("/employees/{emp_id}")
async def employee(emp_id: str, request: Request) -> dict[str, Any]:
    runner = runner_of(request)
    world = world_or_404(runner)
    calls = await asyncio.to_thread(runner.repo.ai_calls, world.run_id, 15, emp_id)
    detail = views.employee_detail(world, emp_id, calls)
    if detail is None:
        raise HTTPException(404, "no such employee")
    return detail


@router.get("/employees")
def employees(request: Request, include_former: bool = True) -> list[dict[str, Any]]:
    world = world_or_404(runner_of(request))
    rows = [e for e in world.employees.values() if include_former or e.active]
    return [views.employee_card(world, e) | {"department": world.departments[e.department_id].name
                                              if e.department_id in world.departments else None,
                                              "leave_reason": e.leave_reason, "salary": e.salary,
                                              "hired": e.hired.isoformat()} for e in rows]


@router.get("/departments/{dept_id}")
def department(dept_id: str, request: Request) -> dict[str, Any]:
    detail = views.department_detail(world_or_404(runner_of(request)), dept_id)
    if detail is None:
        raise HTTPException(404, "no such department")
    return detail


@router.get("/finance")
def finance(request: Request) -> dict[str, Any]:
    return views.finance_view(world_or_404(runner_of(request)))


@router.get("/lab")
def lab(request: Request) -> dict[str, Any]:
    return views.lab_view(world_or_404(runner_of(request)))


@router.get("/history")
def history(request: Request, min_importance: int = 1, limit: int = 600) -> list[dict[str, Any]]:
    return views.history_view(world_or_404(runner_of(request)), min_importance, limit)


@router.get("/management")
def management(request: Request) -> list[dict[str, Any]]:
    return views.management_view(world_or_404(runner_of(request)))


@router.get("/recaps")
def recaps(request: Request) -> list[dict[str, Any]]:
    return views.recaps_view(world_or_404(runner_of(request)))


@router.get("/newspaper")
def newspaper(request: Request, day: date | None = None) -> dict[str, Any]:
    return city.edition_view(world_or_404(runner_of(request)), day)


@router.get("/office")
def office(request: Request) -> dict[str, Any]:
    return views.office_view(world_or_404(runner_of(request)))


@router.get("/god")
def god_catalog() -> dict[str, Any]:
    return god.catalog()


@router.post("/god")
async def god_action(body: GodRequest, request: Request) -> dict[str, Any]:
    runner = runner_of(request)
    world_or_404(runner)
    try:
        message = await runner.god(body.action, body.params)
    except (god.GodError, ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "message": message, "god_actions": runner.world.stats.god_actions if runner.world else 0}


@router.get("/summary")
def summary(request: Request) -> dict[str, Any]:
    return views.summary_view(world_or_404(runner_of(request)))


@router.get("/bets")
def bets(request: Request, employee_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    world = world_or_404(runner_of(request))
    rows = [b for b in world.bets.values() if employee_id is None or b.employee_id == employee_id]
    return [views.bet_view(world, b) for b in rows[-limit:]][::-1]


@router.get("/ai/calls")
async def ai_calls(request: Request, limit: int = 100, agent_id: str | None = None, purpose: str | None = None,
                   failures_only: bool = False) -> list[dict[str, Any]]:
    runner = runner_of(request)
    world = world_or_404(runner)
    await runner.flush_ai()
    return await asyncio.to_thread(runner.repo.ai_calls, world.run_id, min(limit, 500), agent_id, purpose, failures_only)


@router.get("/ai/calls/{call_id}")
async def ai_call(call_id: int, request: Request) -> dict[str, Any]:
    row = await asyncio.to_thread(runner_of(request).repo.ai_call, call_id)
    if row is None:
        raise HTTPException(404, "no such call")
    return row


@router.get("/ai/stats")
def ai_stats(request: Request) -> dict[str, Any]:
    world = world_or_404(runner_of(request))
    return world.ai_stats.model_dump() | {"provider": runner_of(request).providers.get("ai")}


@router.get("/saves")
async def saves(request: Request) -> list[dict[str, Any]]:
    return await asyncio.to_thread(runner_of(request).repo.list_saves)


@router.post("/saves")
async def save(body: SaveRequest, request: Request) -> dict[str, Any]:
    runner = runner_of(request)
    world_or_404(runner)
    return {"save_id": await runner.save(body.label)}


@router.post("/saves/{save_id}/load")
async def load(save_id: int, request: Request) -> dict[str, Any]:
    try:
        world = await runner_of(request).load(save_id)
    except KeyError as exc:
        raise HTTPException(404, "no such save") from exc
    return {"run_id": world.run_id, "date": world.today.isoformat()}


@router.delete("/saves/{save_id}")
async def delete_save(save_id: int, request: Request) -> dict[str, Any]:
    ok = await asyncio.to_thread(runner_of(request).repo.delete_save, save_id)
    if not ok:
        raise HTTPException(404, "no such save")
    return {"deleted": save_id}


ws_router = APIRouter()


@ws_router.websocket("/ws")
async def websocket(ws: WebSocket) -> None:
    runner: SimulationRunner = ws.app.state.runner
    await ws.accept()
    q = runner.subscribe()
    try:
        snap = runner.snapshot()
        if snap is not None:
            await ws.send_text(json.dumps({"type": "state", "data": snap}, default=str))
        while True:
            message = await q.get()
            await ws.send_text(message)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        runner.unsubscribe(q)
