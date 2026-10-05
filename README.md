# Desporto & Cia.

A paper-betting management simulation: a fictional sports betting company run by AI tipsters, a CEO and a
research LAB, shown as a living pixel-art office. **No real money, no real bookmakers.** All bankrolls, stakes
and salaries are simulated. The company can thrive, slowly decline, panic, recover or go bankrupt.

## Quick start (Windows)

```powershell
.\start.ps1
```

First run creates the Python environment and builds the UI, then opens http://localhost:8000.
After changing frontend code use `.\start.ps1 -Rebuild`. The game opens on the **title screen**: your company's
building on a city street, by day and by night. It grows when the company does well and dims, empties or burns
when it doesn't. From there: Continue (the latest save is loaded in the background), New game (you as CEO, or an
AI CEO), Load game, and the language (**English / Español**). In the game, press **space** to run/pause and
**Esc** to close panels; the top bar's **Menu** button goes back to the title screen (the game pauses).

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

## Play as CEO

When founding a company, choose **You** under "Who runs it?". You take the CEO's chair for five seasons; the
AI CEO becomes your advisor. The clock stops for your briefings (monthly by default): accept, edit or skip the
advisor's suggestions, hire with the LAB's evidence, set desk limits and budgets, lease space, write the memo,
sign off. Between reviews, click people and desks to talk, warn, give time off, move or fire them; everything
else can be queued for the next monthly review. Don't get fired by the board, don't go bankrupt. Choose
**An AI CEO** to watch the company run itself as before. Rules: [SIMULATION_RULES](docs/SIMULATION_RULES.md#playing-as-ceo-player-mode).

## What you see

- **Office**: departments as rooms, tipsters as pixel characters who walk between desks, the lounge
  ("The Bench"), the meeting room, the LAB and the exit depending on what they are doing. Bubbles show status,
  floating numbers show the day's P/L, desks glow while people work, and night falls during settlement.
  Click anyone for their panel, click a room for its department.
- **Money**: company value, cash and bankroll over time, monthly results, cost breakdown, desks, reports.
- **Paper**: *The Portavia Ledger*, the city's morning paper — stock market, business and city news, football
  results, and the company in the press. Some stories really change the company (ad bans, rates, data prices,
  rival collapses, bookmaker share prices).
- **Sandbox** (top bar): investors, disasters, market shocks, planted headlines, morale, a star applicant, a new
  CEO, free office space, difficulty. Everything is logged and counted on the end screen.
- **East wing**: the CEO can lease a canteen, a seventh desk room and a media studio; they appear on the map.
- **Staff**, **LAB** (experiments, audits, strategies), **History** (timeline of landmarks),
  **CEO** (every review: thought, memo, actions done/rejected; as a player also your queue, applicants and
  "You" vs "Advisor acted"), **AI log** (every prompt and response), **Saves**.

## Languages

The interface is available in English and Spanish (chosen on the title screen, remembered per browser; the
default follows the browser's language). Texts the simulation writes itself (history entries, the morning paper,
AI thoughts and memos, decision results) are still in English.

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
- [Build plan: play as CEO](docs/CEO_MODE_PLAN.md)
- [Roadmap](ROADMAP.md)
