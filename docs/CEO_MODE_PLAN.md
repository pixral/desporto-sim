# Build plan: play as CEO

Status: **phases 0 and 1 implemented (2026-10-04, milestone B: playable).** Phases 2–4 not started.
Sketches discussed on 2026-10-04: Monday briefing, office click menus, event cards, fired screen, hiring screen,
new company dialog.

### What phase 0 + 1 delivered
- New company dialog: "Who runs it?", your name, advisor style, pause mode (monthly / every review / hands off),
  ironman, difficulty.
- Engine split (`_ceo_review` → proposals, `resolve_review`, `office_action`); the clock waits for the player;
  open briefings are saved; golden-run test keeps watch mode identical.
- Briefing screen: KPIs, the board's rule, the morning paper, advisor suggestions (accept / edit the number /
  skip, accept all), your decisions in a side column (remove = undo before sign-off), memo, Ctrl+Enter, tabs for
  People, Hire (CV vs LAB test, desk fit), Desks, Money, LAB (budget, slots, research brief, roll out / shelve,
  audit fixes) and Office (leases). Results screen after sign-off.
- Office menus on people and desks (advisor one-liner, trust in you, costs, limits, review-only items queued).
- TALK, weekly limits, the queue, CEO page (season, stats, queue, applicants, log "You" vs "Advisor acted").
- Board warning then firing (Easy: warning only), five-season career with retirement, player end screens.
- LAB: research brief, LAB slots shared with chosen applicant tests (results next Monday), shelving.
- Not yet: phase 3's board targets (the briefing shows the board's actual rule instead), score, shadow CEO;
  tooltips on every number.

### Open questions: decided for phase 1
1. Default pause mode: **monthly** (listed first, "recommended"); weekly stand-ups go to the advisor.
2. The player's CEO has **no personality of its own** for now (neutral); the founding CEO's traits only inform the
   advisor.
3. Talks: **three a week, once per person** (talks in a briefing count too).
4. Easy: the board **only warns**.
5. Shadow CEO: still open (phase 3).

**Goal:** the player takes the CEO's chair. Tipsters, the LAB, rivals, the board and the city stay autonomous.
The current AI CEO becomes the player's *advisor* (suggestions with reasons) and the *shadow CEO* the player is
compared against at the end. The watch mode stays exactly as it is today.

## Objective (decided 2026-10-04): a five-season career

Grow the company over five seasons (August → June) without being fired or going bankrupt, and do better than
your advisor would have.

| Ending | When | Score |
|---|---|---|
| Retire | five seasons completed | full score |
| Sell | you accept a takeover bid (only offered once the company is worth something) | scored on the sale price |
| Fired | two missed board targets | scored to that point, with a penalty |
| Bankrupt | the money runs out | lowest |

- **Board targets** each season (value, subscribers, or staying solvent) keep every season tense.
- **Beat your shadow**: the advisor's plan on the same football, compared on the end screen.
- **Score** = final (or sale) value ÷ starting capital × difficulty factor, + targets met, + a bonus for beating
  the shadow. Local high scores per difficulty and scenario. Sandbox use → no score.
- **Scenarios** replace the career goal with their own; **endless mode** lets you keep playing after season five
  with the score frozen.

Phase placement: the season counter and endings (retire, fired) arrive in phase 1; sell in phase 2 (takeover
bids); board targets, shadow, score and high scores in phase 3.

## Principles

1. **One decision pipeline.** Player decisions go through the same `CEOAction` → `management.apply_actions`
   validation as the AI CEO's. Nothing the player does bypasses the rules; refusals come with the same reasons.
2. **The advisor is the existing CEO policy.** `agents/policies/ceo_policy.review()` (or Claude, when enabled)
   produces proposals; the player accepts, edits or skips them.
3. **Watch mode is untouched.** With `player_ceo = False`, a given seed and style must produce exactly the same
   company as before. A golden-run test guards this.
4. **No new randomness in the player's path.** The player's choices change the company, never the football
   (same seed = same matches, as now).
5. **Saves stay compatible.** All new world fields have defaults; pending reviews and decisions are saved.

## Phase 0 — Foundations (no visible change)

What changes:
- `RunConfig`: `player_ceo: bool`, `player_name`, `advisor_style`, `pause_mode` (`every_review` |
  `monthly` | `events_only`), `ironman: bool`, `scenario: str`.
- `World.pending_review`: scope, created time, advisor proposals (`CEOAction` + reason), advisor thought and
  draft memo, status (`open` | `resolved` | `auto`).
- Split `engine._ceo_review` into *propose* (build context, ask the advisor) and *resolve* (apply actions,
  log, memo, gather the meeting). In watch mode both run back to back, as today. In player mode the
  morning phase ends after *propose*; `engine.resolve_review(actions, memo)` finishes it.
- `engine.step()` refuses to advance while a review is open (returns `awaiting_ceo`).
- `pause_mode` decides which reviews wait for the player; the others are resolved with the advisor's
  proposals (`status = auto`, logged as "advisor acted").

Tests:
- Golden run: watch mode, 3 seeds × 4 styles × 120 days, identical company values and event lists before/after.
- Player mode: the clock stops at a review, a save/load keeps the open review, resolving applies actions
  exactly like the AI path (same validation messages), invalid actions are rejected.

Size: **M**.

## Phase 1 — Playable CEO (first playable version)

Backend:
- `GET /api/review` — the open review: KPIs, board target (placeholder until phase 3), flagged people and
  desks, advisor proposals with reasons, candidates, available actions and limits.
- `POST /api/review` — the player's actions + memo → results (applied / refused + reason).
- `POST /api/act` — "office hours" between reviews: WARN, CLEAR_REVIEW, TRANSFER, GIVE_TIME_OFF,
  SET_STAKE_LIMIT, FUND/WITHDRAW, FIRE (one per week), TALK. Review-only actions (HIRE, PROMOTE, leases,
  budgets, team events, desks, loans, salary cuts, LAB deploys) are refused with "at the monthly review".
- New action **TALK** (one-to-one): stress −5, trust in the CEO +3; three per week.
- `queue` for review-only actions chosen between reviews (e.g. "lease at the next review"): they appear
  pre-ticked on the next briefing.
- The runner pauses when a review opens (and notifies the UI), resumes on sign-off.
- Board firing in player mode ends the run (`end_reason = fired`), instead of appointing a new AI CEO.
- `views.state_view` adds `player`: mode, open review flag, weekly limits left.

Frontend:
- **Briefing screen** (sketch 1): KPIs, target, flagged list with Accept / Edit / Skip, "More" drawers (Hire,
  Desks, Budgets, LAB, Office space), decision list, memo, sign-off.
- **Hiring drawer** (sketch 5): CV vs LAB-test evidence, trait chips with tooltips, hire into a chosen desk.
- **Office click menus** (sketch 2): person, desk, lot; costs and consequences shown; advisor one-liner;
  review-only items greyed with when they're available; confirm destructive actions.
- **New company dialog** (sketch 6): "Who runs it?", advisor, pause mode, ironman, difficulty (scenarios
  arrive in phase 3).
- CEO view shows "You" vs "Advisor acted" per review.
- Fired / bankrupt end screen in player wording (shadow comparison arrives in phase 3).

Tests: API flow (open → resolve), office-hours limits, queueing, fired ending, actor menus (vitest),
type-check. Docs: SIMULATION_RULES (player mode), PLAYTEST section, README.

Size: **L**. This is the first version you can actually play.

## Phase 2 — Decisions that come to you

What changes:
- `World.pending_decisions`: id, kind, title, text, options (label, cost, effects), advisor default, expiry in
  simulated days, people involved.
- In player mode, moments that `drama.py` resolves by CEO style become decisions: **poaching counter-offers**
  and **raise demands**. In watch mode they keep resolving automatically.
- New decision kinds:
  - **Investor offer** (money for a share; accepting raises the board's targets),
  - **Journalist after a bad month** (spin / stay quiet / blame a desk → subscribers, morale),
  - **Tilt intervention** (a tipster on tilt places a maxed stake: step in or let it ride),
  - **Regulator inquiry** (pay for lawyers or risk a fine),
  - **Takeover bid** (accept → the run ends with a sale: a second way to "win").
- Expiry applies the advisor's default, so high speeds keep working. Optional auto-pause on big decisions.

Frontend: event cards (sketch 1, bottom) stacked in the sidebar, with a timer in simulated days; a badge on
the top bar.

Tests: each kind's options and defaults; expiry; watch mode unchanged (golden run).

Size: **M**.

## Phase 3 — Goals: board, shadow CEO, score, scenarios

What changes:
- **Board targets**: set at founding and every 1 June from the company's state and difficulty (company value,
  subscribers, or staying solvent); a quarterly board letter (history + a small modal); two misses → fired.
- **Shadow CEO**: a second engine runs the advisor's style from the founding snapshot (same seed). It runs in
  a background thread, a little behind the real game, keeping only its daily value series. Cost: roughly
  doubles CPU at max speed; it can pause when the main game is paused.
- **Turning points** (fired/end screen): the times you overruled the advisor and what happened afterwards
  (facts, not invented euro attributions). Exact euros per decision would need branch-and-rerun; optional later.
- **Score**: final value ÷ starting capital × difficulty factor, + targets met; sandbox use or loading saves in
  ironman → no score. Local high scores per scenario (SQLite table).
- **Scenarios** (factory setup functions): free play; turn around a dying desk; survive two seasons on Hard;
  from €20k to €100k; inherit a chaotic founder's mess (pre-simulate ~270 days with a chaotic AI CEO, then hand over).
- **Achievements** (~12, from stats and history): never fired anyone, survived an ad ban, all seven desks, beat
  your shadow by 50 %, …
- End screens: fired (sketch 3), bankrupt, sold (takeover), retired (optional).

Tests: target generation, misses → fired, shadow determinism (same seed ⇒ same shadow), score rules,
scenario setups, ironman.

Size: **L**.

## Phase 4 — Claude in play mode (optional)

- **AI spending cap** (pause when the run's AI cost reaches a set amount) — prerequisite.
- Advisor via Claude: proposals with reasons in the advisor's voice.
- Generated board letters, journalist questions, and "Talk to them" answers in character.
- Cost estimate shown in the New company dialog.

Size: **M**.

## The LAB in CEO mode

The researchers keep doing the science (ideas, backtests, holdout checks, verdicts); the player decides what
they work on, how much capacity they get, and what happens to the results. Works with the mock brains and
with Claude (Claude researchers also explain how they read the brief).

| | Today (AI CEO) | CEO mode |
|---|---|---|
| Research direction | researcher specialty | **research brief** set at monthly reviews (a league, a market, underdogs, a struggling desk); stubborn researchers may still chase their own ideas |
| Capacity | budget sets speed and parallel experiments | budget buys **LAB slots**; strategy experiments and applicant tests share them |
| Applicant tests | automatic monthly | the player chooses who is tested (uses a slot, ready the next Monday) |
| Unpromising experiments | run to the end | the player can **stop** one to free its slot |
| A finished DEPLOY result | CEO deploys to a losing tipster | **roll out** (choose tipsters; 60-day rule and refusals still apply), **pilot** on one tipster for 30 days with real-vs-test comparison, or **shelve** in the strategy library |
| Audit findings | CEO applies some | each is a small briefing decision |

The player can't design a strategy or overrule a test result: the evidence always comes from the simulation.
Tensions: research budget vs. fading edges (books adapt every season), hiring tests vs. research, speed vs.
safety (roll out vs. pilot), morale (forcing strategies on stubborn tipsters). The shadow CEO makes its own LAB
calls on the same football.

Implementation notes: `lab.lab_morning` takes the brief as extra context (mock: biases which knobs/competitions
are mutated; Claude: part of the prompt); `_capacity()` becomes the slot count shared with candidate tests;
`Experiment.status` gains `stopped`; `Strategy` gains `shelved`; a `Pilot` record (tipster, strategy, start,
end, live vs. backtest stats). Placement: brief, slots, chosen applicant tests, roll out / shelve → phase 1;
pilots and stopping experiments → phase 2.

## Feature catalog

Tags: **P1–P4** = planned phase, **Idea** = could have, not scheduled.

**Playing the CEO**
- "Who runs it?" (you or the AI CEO), your name, advisor style, pause mode, ironman — P1
- Monday briefing (flagged items only) and monthly briefing (full): KPIs, board target, advisor suggestions
  with accept / edit / skip, memo to staff, sign-off — P1
- Office click menus on people, desks and lots, with costs and the advisor's one-liner — P1
- Action queue for review-only decisions taken between reviews — P1
- Weekly limits on office-hours actions (or a shared "CEO time" budget) — P1
- Undo before sign-off; keyboard shortcuts; tooltips explaining every number — P1
- CEO log showing "You" vs "advisor acted" — P1
- Guided first week (a short tutorial briefing) — Idea

**People**
- Hiring screen: CV vs LAB test, trait chips, desk fit, salary — P1
- Warn, clear review, promote, transfer, fire (severance), time off, team nights, salary cuts — P1 (existing actions)
- "Talk to them" one-to-ones (stress down, trust in you up) — P1
- Each person's trust in you (affects poaching resistance, raise demands, refusals) — P2
- Poaching counter-offers and raise demands as your decisions — P2
- Appoint a head of desk; mentoring pairs (junior with a senior) — Idea
- Bonus scheme you design (bonus %, team vs individual) — Idea
- Contracts and a summer transfer window — Idea

**Money**
- Desk stake limits, bankroll moves, marketing and LAB budgets, loans, salary cuts — P1 (existing actions)
- Investor offers (money for a share; tougher board targets; your share affects the score) — P2
- Sponsorship deals (e.g. for the studio show) — Idea

**Desks and office**
- Open and close desks; lease the east wing (canteen, seventh desk room, studio) — P1 (existing actions)
- More rooms (gym, analytics room), office upgrades with small effects — Idea

**The LAB** (see the section above)
- Research brief, LAB slots, choosing applicant tests, roll out / shelve — P1
- Pilot deployments, stopping experiments — P2
- Strategy library with old ideas that may work again — P1 (shelving) / Idea (browsing and reviving)

**Decisions that come to you**
- Poaching, raise demands, investor offers, journalists, tilt interventions, regulator inquiries, takeover bids — P2
- A star wants to lead a new desk; a tipster asks for a transfer; a leaked-picks scandal; a data provider offers
  an exclusive deal; a rival proposes a merger — Idea

**Goals and progression**
- Five-season career with season counter; endings: retire, sell, fired, bankrupt — P1 (retire, fired), P2 (sell)
- Board targets each season, quarterly board letters — P3
- Shadow CEO comparison and turning points — P3
- Score, local high scores per difficulty and scenario, achievements — P3
- Scenarios (dying desk, survive Hard, €20k → €100k, inherit a chaotic founder's mess), endless mode — P3
- Career continues at a bigger company ("new game plus") — Idea
- Daily seed challenge (same seed for everyone, compare scores locally) — Idea
- Career timeline / replay of your key decisions — Idea

**The city and the press**
- Morning paper in the briefing; react to ad bans, rate changes, rival collapses — P1 (shown) / existing effects
- The press covers your decisions (journalist events, headlines about your firings and hires) — P2

**Claude**
- AI spending cap — P4 (prerequisite)
- Advisor, board letters, journalists and "Talk to them" answers in character; researchers explain the brief — P4

**Your own CEO character**
- Personality traits for the player's CEO that colour memos and staff reactions — Idea (open question 2)
- Public reputation of the CEO (affects hiring pool quality and the press) — Idea

## Order, milestones, checks

| Milestone | Phases | You can… |
|---|---|---|
| A | 0 | nothing new to see; the game is ready for a player |
| B | 1 | play as CEO with an advisor, briefings and office menus; get fired |
| C | 2 | handle poaching, raises, investors, the press, crises |
| D | 3 | chase board targets, beat your shadow CEO, score, scenarios |
| E | 4 | play with Claude as advisor, board and staff voices |

After each milestone: full test suites, a calibration batch for watch mode (must be unchanged), a short
playtest checklist, docs updated, commit on a feature branch, merge when you're happy.

## Open questions (decide before or during phase 1)

1. Default pause mode: **monthly + big events** (weekly briefings at 64× would interrupt every few seconds)?
2. Does the player's CEO have a personality (traits) that colours memos and staff reactions, or is it neutral?
3. "Talk to them" limit: three per week, or tied to a weekly "CEO time" budget shared with other actions?
4. Should the board ever fire the player in Easy, or only warn?
5. Shadow CEO always on, or only in scenarios / when chosen (to save CPU)?
