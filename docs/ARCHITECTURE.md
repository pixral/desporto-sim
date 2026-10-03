# Architecture

Desporto & Cia. is a **paper-betting management simulation**. Nothing in this codebase
talks to a real-money betting platform. All bankrolls, stakes and salaries are simulated.

```
┌──────────────────────────── frontend (React + TS + Vite) ────────────────────────────┐
│  Office canvas (isometric pixel renderer, procedural sprites, A* walking)            │
│  Top bar / KPIs · Event feed · Employee panel · Dashboard · Staff · LAB · History    │
│  zustand store  ◄── WebSocket /ws (state pushes)      REST /api/* (commands, detail) │
└──────────────────────────────────────────────────────────────────────────────────────┘
                                         │
┌──────────────────────────── backend (Python 3.13 + FastAPI) ─────────────────────────┐
│ api/          REST routes, WebSocket hub, DTO builders                               │
│ simulation/   engine (phases), runner (pause/speed), factory, history, summary, views │
│ agents/       context builders, prompts, psychology, relationships, hiring,          │
│               management (CEO action validation), policies/ (mock "brains")          │
│ ai/           IAgentModelProvider, MockAgentModelProvider, AnthropicProvider,         │
│               AIGateway (validation, retries, cost + prompt logging), output schemas  │
│ analysis/     Poisson math, strategy models (observable data only), backtester        │
│ sports/       ISportsDataProvider, MockSportsDataProvider, schedules, team data       │
│ economy/      accounting, monthly close, valuation, runway, insolvency               │
│ domain/       pure pydantic models (World aggregate and its parts)                   │
│ persistence/  SQLAlchemy (SQLite now, PostgreSQL-ready): saves + AI call log          │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## Key decisions

See [DECISIONS.md](DECISIONS.md) for the full log. The short version:

| Topic | Choice | Why |
|---|---|---|
| Backend | Python + FastAPI | Fast iteration, pydantic gives structured LLM output validation for free, first-class Anthropic SDK, native WebSockets. |
| State model | One in-memory `World` aggregate (pydantic) | Fast-forwarding thousands of days needs in-memory state. Save/load = serialize the aggregate. |
| Persistence | SQLAlchemy 2.0; compressed world snapshots + an append-only `ai_calls` table | Swap the URL to move to PostgreSQL. Snapshots keep save/load trivial and exact (RNG state included). |
| Time | Discrete simulated clock: 4 phases per day | Decoupled from wall-clock; supports pause, speeds, fast-forward, deterministic replay. |
| Randomness | Separate RNG streams for the sports world and for agents | Same seed → same football season regardless of who runs the company, so CEO styles can be compared fairly. |
| AI | `IAgentModelProvider` interface; mock provider consumes the *same structured context* the LLM prompt is rendered from | Run for free, test deterministically, then switch to Claude without changing the simulation. |
| LLM vs code | Arithmetic, settlement, accounting, metrics, backtests, probability models are plain code | LLM (or mock policy) only makes judgement calls: bet/no-bet & stake, CEO management actions, LAB hypotheses. |
| Real-time | WebSocket pushes a compact view model after each step (throttled at max speed) | Simple and robust; details are fetched on demand via REST. |
| Frontend rendering | Hand-written canvas renderer with procedurally generated pixel sprites | Original visual identity, no copyrighted assets, no heavy game engine. |

## Simulation step

Each simulated day has four phases (see [SIMULATION_RULES.md](SIMULATION_RULES.md)):

1. **08:00 morning** – month close (payroll, costs, subscriptions) on the 1st, CEO monthly review,
   CEO weekly review on Mondays, sync fixtures/odds/news from the sports provider, LAB work.
2. **11:00 analysis** – assign today's matches, run strategy models, share leanings with coworkers,
   tipsters decide BET / NO_BET (one AI call per tipster per day), paper bets are recorded.
3. **16:00 matches** – kick-offs, closing odds captured, tipsters watch.
4. **23:30 settlement** – results fetched, bets settled, psychology & relationships updated,
   daily accounting, insolvency check, milestone detection.

## Data flow for one tipster decision

```
sports provider ──► World.matches (odds, results, news)          observable data only
                         │
                 analysis.models.estimate_match(strategy)          deterministic
                         │  probabilities, fair odds, edges
                 agents.context.build_tipster_context()            deterministic
                         │  + company/department/career/coworker situation
                 AIGateway.run(provider, schema=TipsterDayOutput)  judgement (LLM or mock)
                         │  validated JSON, retries, cost + prompt logged
                 engine applies decision: clamps stake to limits,  deterministic
                 uses the real best price, records Bet / DecisionLog
```

## Extending

* **Real sports data:** implement `ISportsDataProvider` (`sports/provider.py`). The engine only pulls
  fixtures, odds, results and news through that interface.
* **Claude:** set `DESPORTO_AI_PROVIDER=anthropic` and `ANTHROPIC_API_KEY`. Model per purpose is
  configurable (`ai/anthropic_provider.py`).
* **PostgreSQL:** set `DESPORTO_DATABASE_URL=postgresql+psycopg://...`.
