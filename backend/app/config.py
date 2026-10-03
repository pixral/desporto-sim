"""Runtime settings from environment variables (all optional)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

PURPOSES = ("tipster_day", "ceo_review", "lab_hypothesis")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: _env(
        "DESPORTO_DATABASE_URL", f"sqlite:///{(BACKEND_DIR / 'data' / 'desporto.db').as_posix()}"))
    ai_provider: str = field(default_factory=lambda: _env("DESPORTO_AI_PROVIDER", "mock"))
    default_model: str = field(default_factory=lambda: _env("DESPORTO_MODEL", "claude-opus-5-5"))
    default_effort: str = field(default_factory=lambda: _env("DESPORTO_EFFORT", "medium"))
    mock_failure_rate: float = field(default_factory=lambda: float(_env("DESPORTO_MOCK_FAILURE_RATE", "0") or 0))
    frontend_dist: Path = field(default_factory=lambda: Path(_env("DESPORTO_FRONTEND_DIST",
                                                                  str(PROJECT_DIR / "frontend" / "dist"))))

    def model_overrides(self) -> dict[str, str]:
        """DESPORTO_MODEL_TIPSTER_DAY=claude-haiku-4-5, DESPORTO_MODEL_CEO_REVIEW=..., etc."""
        out = {}
        for p in PURPOSES:
            v = _env(f"DESPORTO_MODEL_{p.upper()}")
            if v:
                out[p] = v
        return out

    def effort_overrides(self) -> dict[str, str]:
        out = {}
        for p in PURPOSES:
            v = _env(f"DESPORTO_EFFORT_{p.upper()}")
            if v:
                out[p] = v
        return out


def get_settings() -> Settings:
    return Settings()
