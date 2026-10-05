"""Golden runs: fingerprints of watch-mode companies, to prove a change leaves the AI-CEO game untouched.

    python -m app.tools.golden            # compare against tests/golden_watch.json
    python -m app.tools.golden --write    # regenerate it (only after an intended balance change)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from app.ai.mock_provider import MockAgentModelProvider
from app.domain.world import CEO_STYLES, RunConfig
from app.economy import valuation as val
from app.providers import make_sports_provider
from app.simulation.engine import SimulationEngine
from app.simulation.factory import create_world

SEEDS = (1, 2, 3)
DAYS = 120
FIXTURE = Path(__file__).resolve().parents[2] / "tests" / "golden_watch.json"


def fingerprint(args: tuple[str, int, int]) -> dict:
    style, seed, days = args
    cfg = RunConfig(ceo_style=style, seed=seed)
    sports = make_sports_provider(cfg)
    world = create_world(cfg, sports)
    engine = SimulationEngine(world, sports, MockAgentModelProvider())
    asyncio.run(engine.run_days(days))
    events = "\n".join(f"{e.time.isoformat()}|{e.kind}|{e.title}" for e in world.events)
    return {
        "key": f"{style}:{seed}",
        "value": round(val.valuation(world), 2),
        "cash": round(world.finances.cash, 2),
        "bets": world.stats.bets_placed,
        "employees": len(world.employees),
        "events": len(world.events),
        "events_sha": hashlib.sha256(events.encode()).hexdigest()[:16],
    }


def run_all(days: int = DAYS, workers: int = 6) -> dict[str, dict]:
    jobs = [(style, seed, days) for style in CEO_STYLES for seed in SEEDS]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        rows = list(ex.map(fingerprint, jobs))
    return {r.pop("key"): r for r in rows}


if __name__ == "__main__":
    got = run_all()
    if "--write" in sys.argv:
        FIXTURE.write_text(json.dumps(got, indent=1, sort_keys=True))
        print(f"wrote {FIXTURE}")
    else:
        want = json.loads(FIXTURE.read_text())
        bad = [k for k in want if want[k] != got.get(k)]
        print("identical" if not bad else f"DIFFERENT: {bad}")
        sys.exit(1 if bad else 0)
