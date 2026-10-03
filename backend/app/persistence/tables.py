from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, LargeBinary, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RunRow(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    company_name: Mapped[str] = mapped_column(String(120))
    ceo_style: Mapped[str] = mapped_column(String(40))
    seed: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    sim_date: Mapped[str] = mapped_column(String(10))
    ended: Mapped[bool] = mapped_column(Boolean, default=False)
    end_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class SaveRow(Base):
    __tablename__ = "saves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), ForeignKey("runs.id"), index=True)
    label: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(16), default="manual")  # manual | auto | final
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    sim_date: Mapped[str] = mapped_column(String(10))
    day_index: Mapped[int] = mapped_column(Integer)
    valuation: Mapped[float] = mapped_column(Float)
    size_bytes: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[bytes] = mapped_column(LargeBinary)


class AICallRow(Base):
    __tablename__ = "ai_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(32), index=True)
    sim_time: Mapped[datetime] = mapped_column(DateTime)
    agent_id: Mapped[str] = mapped_column(String(32))
    agent_name: Mapped[str] = mapped_column(String(80))
    purpose: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    system: Mapped[str] = mapped_column(Text)
    prompt: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    ok: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    used_fallback: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_ai_calls_run_agent", "run_id", "agent_id"),)
