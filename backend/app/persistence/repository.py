"""Save/load worlds and store the AI call log."""

from __future__ import annotations

import zlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.ai.gateway import AICallRecord
from app.domain.world import World
from app.economy import valuation as val

from .tables import AICallRow, Base, RunRow, SaveRow


class Repository:
    def __init__(self, url: str) -> None:
        if url.startswith("sqlite:///"):
            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        self.engine: Engine = create_engine(url, future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(self.engine, expire_on_commit=False)

    # ------------------------------------------------------------------ runs & saves
    def upsert_run(self, s: Session, world: World) -> None:
        row = s.get(RunRow, world.run_id)
        if row is None:
            row = RunRow(id=world.run_id, company_name=world.config.company_name, ceo_style=world.config.ceo_style,
                         seed=world.config.seed, sim_date=world.today.isoformat())
            s.add(row)
        row.updated_at = datetime.now(UTC)
        row.sim_date = world.today.isoformat()
        row.ended = world.ended
        row.end_reason = world.end_reason
        row.summary_json = world.summary.model_dump_json() if world.summary else None

    def save_world(self, world: World, label: str, kind: str = "manual") -> int:
        blob = zlib.compress(world.model_dump_json().encode("utf-8"), level=6)
        with self.Session.begin() as s:
            self.upsert_run(s, world)
            if kind == "auto":  # keep only the latest few autosaves per run
                old = s.scalars(select(SaveRow.id).where(SaveRow.run_id == world.run_id, SaveRow.kind == "auto")
                                .order_by(SaveRow.id.desc()).offset(4)).all()
                if old:
                    s.execute(delete(SaveRow).where(SaveRow.id.in_(old)))
            row = SaveRow(run_id=world.run_id, label=label, kind=kind, sim_date=world.today.isoformat(),
                          day_index=world.clock.day_index, valuation=round(val.valuation(world), 2),
                          size_bytes=len(blob), snapshot=blob)
            s.add(row)
            s.flush()
            return row.id

    def load_world(self, save_id: int) -> World:
        with self.Session() as s:
            row = s.get(SaveRow, save_id)
            if row is None:
                raise KeyError(save_id)
            return World.model_validate_json(zlib.decompress(row.snapshot))

    def list_saves(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.Session() as s:
            rows = s.execute(
                select(SaveRow.id, SaveRow.run_id, SaveRow.label, SaveRow.kind, SaveRow.created_at, SaveRow.sim_date,
                       SaveRow.day_index, SaveRow.valuation, SaveRow.size_bytes, RunRow.company_name, RunRow.ceo_style,
                       RunRow.ended)
                .join(RunRow, RunRow.id == SaveRow.run_id).order_by(SaveRow.id.desc()).limit(limit)).all()
            return [dict(r._mapping) for r in rows]

    def delete_save(self, save_id: int) -> bool:
        with self.Session.begin() as s:
            return s.execute(delete(SaveRow).where(SaveRow.id == save_id)).rowcount > 0

    def list_runs(self) -> list[dict[str, Any]]:
        with self.Session() as s:
            rows = s.scalars(select(RunRow).order_by(RunRow.updated_at.desc())).all()
            return [{"id": r.id, "company_name": r.company_name, "ceo_style": r.ceo_style, "seed": r.seed,
                     "sim_date": r.sim_date, "ended": r.ended, "end_reason": r.end_reason,
                     "created_at": r.created_at, "updated_at": r.updated_at} for r in rows]

    # ------------------------------------------------------------------ AI log
    def insert_ai_calls(self, records: list[AICallRecord]) -> None:
        if not records:
            return
        with self.Session.begin() as s:
            s.add_all(AICallRow(**r.model_dump()) for r in records)

    def ai_calls(self, run_id: str, limit: int = 100, agent_id: str | None = None,
                 purpose: str | None = None, failures_only: bool = False) -> list[dict[str, Any]]:
        with self.Session() as s:
            q = select(AICallRow.id, AICallRow.sim_time, AICallRow.agent_id, AICallRow.agent_name, AICallRow.purpose,
                       AICallRow.provider, AICallRow.model, AICallRow.ok, AICallRow.error, AICallRow.retries,
                       AICallRow.input_tokens, AICallRow.output_tokens, AICallRow.cost_usd, AICallRow.latency_ms,
                       AICallRow.estimated, AICallRow.used_fallback).where(AICallRow.run_id == run_id)
            if agent_id:
                q = q.where(AICallRow.agent_id == agent_id)
            if purpose:
                q = q.where(AICallRow.purpose == purpose)
            if failures_only:
                q = q.where(AICallRow.ok.is_(False))
            return [dict(r._mapping) for r in s.execute(q.order_by(AICallRow.id.desc()).limit(limit)).all()]

    def ai_call(self, call_id: int) -> dict[str, Any] | None:
        with self.Session() as s:
            row = s.get(AICallRow, call_id)
            if row is None:
                return None
            return {c.name: getattr(row, c.name) for c in AICallRow.__table__.columns}

    def ai_call_count(self, run_id: str) -> int:
        with self.Session() as s:
            return s.scalar(select(func.count()).select_from(AICallRow).where(AICallRow.run_id == run_id)) or 0
