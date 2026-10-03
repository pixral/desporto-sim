"""Headless batch runs for calibration and research.

    python -m app.tools.batch --days 730 --seeds 1 2 3 --styles all

Prints one line per run plus a per-style summary. Uses the mock AI provider (free).
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from concurrent.futures import ProcessPoolExecutor

from app.ai.mock_provider import MockAgentModelProvider
from app.domain.world import CEO_STYLES, RunConfig
from app.economy import valuation as val
from app.economy.config import preset
from app.providers import make_sports_provider
from app.simulation.engine import SimulationEngine
from app.simulation.factory import create_world


def run_one(args: tuple[str, int, int, float | None, str]) -> dict:
    style, seed, days, capital, difficulty = args
    t0 = time.perf_counter()
    config = RunConfig(ceo_style=style, seed=seed, difficulty=difficulty,
                       starting_capital=capital if capital else preset(difficulty)["capital"])
    sports = make_sports_provider(config)
    world = create_world(config, sports)
    engine = SimulationEngine(world, sports, MockAgentModelProvider())
    asyncio.run(engine.run_days(days))
    staked = sum(b.stake for b in world.bets.values() if b.status != "open")
    profit = world.finances.totals.betting_pnl
    return {
        "style": style, "seed": seed, "days": world.clock.day_index, "ended": world.ended,
        "capital": world.config.starting_capital,
        "reason": world.end_reason or "", "value": val.valuation(world), "peak": world.finances.peak_value,
        "dd": world.finances.max_drawdown, "bets": world.stats.bets_placed,
        "roi": profit / staked if staked else 0.0, "turnover": staked, "betting": profit,
        "subs": world.finances.subscribers, "hired": world.stats.hired, "fired": world.stats.fired,
        "resigned": world.stats.resigned, "depts+": world.stats.departments_created,
        "depts-": world.stats.departments_closed, "headcount": len(world.active_employees()),
        "secs": time.perf_counter() - t0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--styles", nargs="+", default=["all"])
    ap.add_argument("--capital", type=float, default=None, help="default: the difficulty's preset")
    ap.add_argument("--difficulty", choices=["easy", "normal", "hard"], default="normal")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--quiet", action="store_true", help="only print the per-style summary")
    a = ap.parse_args()
    styles = list(CEO_STYLES) if a.styles == ["all"] else a.styles
    jobs = [(st, seed, a.days, a.capital, a.difficulty) for st in styles for seed in a.seeds]
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        results = list(ex.map(run_one, jobs))
    for r in [] if a.quiet else results:
        print(f"{r['style']:<24} seed {r['seed']:<3} days {r['days']:<4} {'BANKRUPT' if r['ended'] else 'alive   '} "
              f"value {r['value']:>9,.0f} peak {r['peak']:>9,.0f} dd {r['dd']:>5.0%} bets {r['bets']:>5} "
              f"turnover {r['turnover']:>9,.0f} ROI {r['roi']:+6.2%} subs {r['subs']:>4} hc {r['headcount']:>2} "
              f"hired {r['hired']:>2} fired {r['fired']:>2} quit {r['resigned']:>2} "
              f"desks +{r['depts+']}/-{r['depts-']} ({r['secs']:.0f}s)")
    print()
    for st in styles:
        rows = [r for r in results if r["style"] == st]
        alive = [r for r in rows if not r["ended"]]
        grew = sum(1 for r in rows if not r["ended"] and r["value"] > r["capital"])
        print(f"{st:<24} bankrupt {len(rows) - len(alive):>2}/{len(rows)}  grew {grew:>2}/{len(rows)}  "
              f"median value {statistics.median(r['value'] for r in rows):>9,.0f}  "
              f"mean value {statistics.mean(r['value'] for r in rows):>9,.0f}  "
              f"median days {statistics.median(r['days'] for r in rows):>5.0f}  "
              f"mean ROI {statistics.mean(r['roi'] for r in rows):+.2%}")


if __name__ == "__main__":
    main()
