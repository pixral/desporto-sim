# Roadmap / TODO

## Status (2026-10-03, end of day 2)

**First playable version: done.**

- Backend: mock football world, tipsters, CEO (4 styles), LAB, psychology, relationships, hiring/firing,
  departments, economy, bankruptcy, Claude provider, AI call log, saves (monthly + weekly autosave), REST +
  WebSocket, pause/step/day/speeds. 39 tests.
- Frontend: isometric pixel office (procedural sprites, A* walking, status bubbles, P/L floaters, monitor
  glows, day/night), top bar with controls, KPI strip, live feed + bet slip + CEO memo, employee panel (6 tabs),
  department panel, Money dashboard (validated chart palette), Staff, LAB, History, CEO log, AI log with prompt
  viewer, Saves, New company dialog, bankruptcy end screen. 9 tests (layout reachability, actor behaviour).
- Docs: README, ARCHITECTURE, SIMULATION_RULES, AGENT_MODEL, ECONOMY, DECISIONS. Launcher: `start.ps1`.

## Done since (2026-10-03, evening)

From a real run that "went downhill": CEO now fires on career evidence too, rebuilds a shrunken company,
and replaces proven losers with better-tested applicants (with winner's-curse shrinkage and a quarterly limit);
LAB requires an out-of-sample holdout before recommending deployment; strategies go only to losing tipsters,
never twice per review, with a 60-day cooldown (fixed a double-deploy bug); "promising" LAB results no longer
flood the history; colleague influence and desk familiarity actually happen now. 44 backend tests.

## Done since (2026-10-03, night)

Economy tuning: near-flat "unit" staking (sizing by perceived edge was losing money), Easy/Normal/Hard
presets (capital, costs, subscribers, bookmaker sharpness) in the New company dialog, calibrated with 16 seeds
per CEO style. Office drama: speech bubbles on events (fired, promoted, I quit, refusals, big wins with
confetti), influence lines between colleagues, quieter idle bubbles, collapsible legend, themed scrollbars.

## Done since (2026-10-03, late night)

Drama & story: desk arguments and celebrations (with red clash / green lines in the office), rival
syndicates poaching stars (CEO counter-offers by style), raise demands and resentment, the board firing a CEO
who wrecked the company, season awards with an "Awards night" screen; names are unique across a company's
history; big wins/swings rate-limited so the timeline stays readable.

## Done since (2026-10-04)

From the playtest feedback: chairs face their desks and tables, continuous rugs and doormats, staff go home at
night and walk back in each morning, CEO reviews gather the affected people plus each desk's lead (one-to-ones
in the CEO's office). New: *The Portavia Ledger* (a small stock market, news arcs and a daily paper whose stories
really affect the company), office expansion into the east wing (canteen, seventh desk room, media studio,
leased by the CEO), and sandbox tools (investors, disasters, market shocks, planted headlines, morale, star
applicant, CEO swap, free space, difficulty). Recalibrated: studio and canteen costs/effects tuned after an
ablation, rare stories made rarer; Normal is neutral-to-better vs. the previous build (see ECONOMY.md).
A second dev stack (`backend-dev`/`frontend-dev`, ports 8001/5174, `dev.db`) keeps a running game untouched.

Later the same day: bookmakers limit winning desks (soft books cut stakes for desks that win their money, the
sharp book only reins in runaways; shown in the desk panel, the history, the paper and as office bubbles), so
Easy no longer compounds into €0.7M companies (best run now €176k), and Hard was softened (€16k capital, lower
costs) so disciplined CEOs can survive it. Calibration table in ECONOMY.md.

Mood events: burned-out people call in sick (empty chairs, no bets), shaken tipsters lose their nerve and pass on
everything, heavy losers go on tilt and chase it the next day, cocky winners brag and start arguments; the CEO
can give time off or throw a team night out (each style differently). Chaotic companies feel it most.

CEO mode, phases 0 and 1 ([plan](docs/CEO_MODE_PLAN.md)): you can found a company and run it yourself, with the
AI CEO as your advisor. Briefings stop the clock (monthly by default), office menus on people and desks,
office hours with weekly limits, a queue for review-only decisions, the LAB brief and chosen applicant tests,
the board's warning and firing, five seasons to retirement, ironman. Watch mode is guarded by golden runs.

## Next

0. CEO mode phase 2: decisions that come to you (poaching, raises, investors, the press, tilt, regulators,
   takeover bids), pilots and stopping experiments.
1. Visual polish pass with fresh eyes on a long run (label overlap at small zoom, crowded Bench).
   Also show colleague influence and refusals visibly in the office (speech lines between desks).
2. Run a short real Claude session (a few simulated days) to check prompt quality and cost per day.
3. Performance: cache team ratings across LAB backtests (data-driven runs are ~3× slower at max speed).
5. Summer leagues (e.g. MLS/Brasileirão desk) so June–July is not dead time.
6. Real sports provider (`ISportsDataProvider`) and a wall-clock "live" mode.
7. More drama, round two: bonus schemes, mentoring juniors, office romances/feuds that span seasons,
   journalists covering the company, the board injecting money with strings attached.
8. Accessibility: keyboard navigation for the office (tab through people), table views for every chart.
