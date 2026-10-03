# Agent model

Three kinds of agents: **tipsters**, the **CEO** and **LAB researchers**. Each judgement call is one AI call
through `AIGateway` with a pydantic output schema (`backend/app/ai/schemas.py`). Plain code does everything
else (probabilities, accounting, metrics, backtests, psychology updates).

## What an agent sees

`agents/context.py` builds a structured dict; `agents/prompts.py` renders it to text for an LLM; the mock
policies (`agents/policies/`) read the same dict. The prompt, response, tokens, cost, retries and failures of
every call are stored in the `ai_calls` table and visible in the UI (AI log, employee Decisions tab).

### Tipster context (one call per tipster per matchday)

- Self: name, title, specialty, personality traits, tenure, stress, confidence, risk tolerance, reputation,
  mood, streak, recent and career results, pass rate, review status, salary.
- Situation notes, e.g. *"The Germany Desk has lost €170 this month. Management is reviewing staff. Your recent
  ROI is −4.2% over your last 30 settled bets. … A poor decision may hurt your career, but refusing every bet
  may also be viewed negatively."*
- Department: bankroll, month P&L, max stake, allocation, colleagues' recent ROI and trust.
- Company: status, runway, month net, recent layoffs, hiring freeze, CEO style and **latest CEO memo**.
- Matches: form, goals, team news, best odds per market (and book), the strategy's probabilities and edges,
  which candidates fit the strategy, and **colleagues' leanings** on the same match with trust scores.
- Output: a one-line inner thought + per match `BET` (market, stake, confidence, reason, who influenced them)
  or `NO_BET` (reason). Passing is always allowed.

### CEO context (weekly light review, monthly full review)

Finances, runway, drawdown, last 3 months, department and employee 90-day stats (with z-scores, i.e. how far
results are from luck), LAB results and audit findings, hiring candidates (with LAB backtests of their methods
when the LAB has budget), and the allowed action list. Output: thought, memo to staff, actions.

Actions: FIRE, HIRE, PROMOTE, WARN, CLEAR_REVIEW, TRANSFER_EMPLOYEE, SET_STAKE_LIMIT, FUND_DEPARTMENT,
WITHDRAW_BANKROLL, CREATE_DEPARTMENT, CLOSE_DEPARTMENT, SET_LAB_BUDGET, SET_MARKETING_BUDGET, DEPLOY_STRATEGY,
ADJUST_STRATEGY, FREEZE_HIRING, UNFREEZE_HIRING, CUT_SALARIES, TAKE_LOAN, REPAY_LOAN.
`agents/management.py` validates every action (ids, limits, cash, freeze, desk space) and logs rejections.

### LAB context

Live strategies and their results, past experiments, audit hints and parameter bounds. Output: a named
hypothesis with strategy parameters. The engine clamps parameters and backtests walk-forward over the past
year **excluding the last 4 months**, then checks those 4 months as an out-of-sample **holdout**. DEPLOY needs a
strong in-sample result (≥120 bets, ROI ≥ ~4%, drawdown < 30%; bolder researchers accept a bit less) **and** a
profitable holdout (≥30 bets). Ideas that look great in-sample but lose on fresh data "collapse on fresh data".
Overfitting is still possible (many ideas are tried), which is part of the drama.

## Hidden talent

Each tipster's strategy parameters are randomised around their specialty template (e.g. how much they rate
teams on xG, recency weighting, minimum edge). Some are genuinely good, most aren't. CV ratings are only weakly
related. Nobody, including the CEO, sees true quality; it has to be inferred from noisy results.

## Personality and psychology

Traits (cautious, analytical, aggressive, ambitious, stubborn, collaborative, independent, risk-seeking,
skeptical) are stable. State moves daily (`agents/psychology.py`):

- **Stress** drifts towards a target driven by company distress, being under review, losing streaks, the desk's
  month, recent layoffs and low reputation; sensitivity depends on traits. Salary cuts and colleagues being fired
  add stress.
- **Confidence** moves with results; analytical people partly judge process (closing-line value) instead of
  outcomes; stubborn people update less.
- **Risk tolerance** rises with desperation (under review + stress + ambition) and hubris, falls with fear.
- **Reputation** tracks recent ROI (weighted by sample size), level, promotions and warnings.
- Burned-out or poached employees may **resign**; good people leave a sinking ship more often.

## How the mock tipster decides (no LLM)

A multi-factor stochastic model, not a script. Derived pressures: desperation, fear, hubris, inactivity
pressure. They shift the edge threshold, the perceived edge (overconfidence, longshot chasing when desperate,
skepticism of longshots), social influence (trust × collaborative − independent, damped by stubbornness),
judgement noise (more under stress), discipline about strategy filters, and stake size (units of the CEO's limit,
scaled by conviction, risk tolerance, confidence and mood). The same pressure makes a cautious analyst freeze and
an ambitious risk-seeker swing for the fences.

## CEO styles (mock)

| Style | Character |
|---|---|
| Conservative operator | Small stakes, slow hiring, quick cost cuts, needs big samples. |
| Aggressive expansionist | Hires and opens desks, raises limits after wins, doubles down and borrows when behind. |
| Data-driven | Decides on z-scores, sizes desks to evidence, follows the LAB, backtests applicants. |

Shared management rules (all styles, with style-specific thresholds):
- Firing needs evidence: a bad 90-day record (z-score) **or** a bad career record (e.g. data-driven: ≥150 bets
  with career z ≤ −2), usually after a warning.
- **Upgrade swaps**: a proven loser can be replaced by an applicant whose method tests better (LAB backtest for
  data-driven/conservative CEOs, a shiny CV for the others).
- **Rebuild**: a company that shrank below a minimum headcount but still has runway hires back (up to 3 per desk)
  and may reopen a desk, instead of fading out.
- LAB strategies go only to people who are losing, never twice in one review, and a tipster keeps a strategy at
  least 60 days (90 for the mock CEO's choice) before it can be swapped again.
| Chaotic founder | Impulsive firings and hires, random limits, dramatic memos. |

## Relationships

Trust (from following a colleague's call and the outcome), respect (from observed results) and rivalry (same
desk, ambition, promotions). Trust decides whose leanings a tipster sees and how much they sway them.

## Using Claude

`DESPORTO_AI_PROVIDER=anthropic` (plus credentials). Default model `claude-opus-5-5` with structured outputs
(`messages.parse` with the pydantic schema), server-side refusal fallback, effort configurable. Per-purpose
overrides: `DESPORTO_MODEL_TIPSTER_DAY`, `DESPORTO_MODEL_CEO_REVIEW`, `DESPORTO_MODEL_LAB_HYPOTHESIS`,
`DESPORTO_EFFORT_*`. Invalid outputs are retried twice with the validation error; then a safe fallback
(no bets / no actions) is used and the failure is logged.
