# Desporto & Cia.

A paper-betting management simulation: a fictional sports betting company run by AI tipsters, a CEO and a
research LAB, shown as a living pixel-art office. **No real money, no real bookmakers.** All bankrolls, stakes
and salaries are simulated. The company can thrive, slowly decline, panic, recover or go bankrupt.

## Quick start (Windows)

```powershell
.\start.ps1
```

First run creates the Python environment and builds the UI, then opens http://localhost:8000.
After changing frontend code use `.\start.ps1 -Rebuild`. A company is founded on first start; afterwards the
latest unfinished save is resumed. Press **space** to run/pause, **Esc** to close panels.

## Development

```bash
# backend (API + simulation) on :8000
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev,anthropic]"
.venv/Scripts/python -m uvicorn app.main:app --port 8000

# frontend with hot reload on :5173 (proxies /api and /ws to :8000)
cd frontend
npm install
npm run dev
```

Tests: `backend/.venv/Scripts/python -m pytest -q` (backend) and `npm test` (frontend).
Calibration runs: `python -m app.tools.batch --days 730 --seeds 1 2 3 --styles all` (from `backend/`).
API docs: http://127.0.0.1:8000/docs

## What you see

- **Office**: departments as rooms, tipsters as pixel characters who walk between desks, the lounge
  ("The Bench"), the meeting room, the LAB and the exit depending on what they are doing. Bubbles show status,
  floating numbers show the day's P/L, desks glow while people work, and night falls during settlement.
  Click anyone for their panel, click a room for its department.
- **Money**: company value, cash and bankroll over time, monthly results, cost breakdown, desks, reports.
- **Staff**, **LAB** (experiments, audits, strategies), **History** (timeline of landmarks),
  **CEO** (every review: thought, memo, actions done/rejected), **AI log** (every prompt and response),
  **Saves**.

## Using Claude instead of the mock brains

Choose "Claude" when founding a company (or set `DESPORTO_AI_PROVIDER=anthropic`) and provide credentials
(`ANTHROPIC_API_KEY` or an `ant auth login` profile). Default model `claude-opus-5-5`; override per purpose with
`DESPORTO_MODEL_TIPSTER_DAY`, `DESPORTO_MODEL_CEO_REVIEW`, `DESPORTO_MODEL_LAB_HYPOTHESIS` (and
`DESPORTO_EFFORT_*`). This spends real API credits; the mock provider is free.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Simulation rules](docs/SIMULATION_RULES.md)
- [Agent model](docs/AGENT_MODEL.md)
- [Economy](docs/ECONOMY.md)
- [Decision log](docs/DECISIONS.md)
- [Playtest checklist](docs/PLAYTEST.md)
- [Roadmap](ROADMAP.md)
