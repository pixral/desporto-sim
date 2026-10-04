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

## In progress (2026-10-04) — paused here, work in progress

From the playtest feedback. Built and tested (75 backend + 13 frontend tests pass), not yet balanced:

- **Office fixes**: chairs face their desk/table (meeting room, CEO visitors), continuous rugs and doormats
  instead of the tiled "carpets" by the doors, "EMPTY ROOM" instead of "for lease" on unused desk rooms.
- **Night**: everyone goes home at 23:30 (P/L numbers float above the desks) and walks back in at 08:00.
- **Meetings**: CEO reviews now gather the affected people plus each desk's lead (LAB joins monthly);
  1–2 people meet in the CEO's office, more in the meeting room; the CEO no longer sits in meetings alone.
- **City + newspaper** (`simulation/city.py`, `economy/market.py`, Paper view): 12 fictional listed companies,
  news arcs (tender → accident/delay/opening), rate decisions, earnings; ad ban, rival collapse, data price
  hike, rates, consumer confidence and bookmaker shares really affect the company.
- **Office expansion**: CEO can lease the east wing (canteen, 7th desk room, media studio) at monthly reviews;
  shown on the map (lots "for lease" until leased) and in the CEO view.
- **Sandbox tools** (`simulation/god.py`, Sandbox button): investors, windfalls, disasters, market shocks,
  planted headlines, morale, star applicant, CEO swap, free space, difficulty. Logged and counted.
- Dev stack that doesn't touch a running game: `backend-dev` (port 8001, `data/dev.db`) and `frontend-dev`
  (port 5174) in `.claude/launch.json`.

**To finish before calling it done:**
1. Re-run the 16-seed calibration batch (Normal, then Hard/Easy): the city effects, facility costs and CEO
   leasing change the economy; update the snapshot in `docs/ECONOMY.md`. (A run was started and stopped.)
2. Docs: SIMULATION_RULES is updated; still to do — ECONOMY (city effects, facility costs), AGENT_MODEL (CEO
   office decisions, city context, meetings), ARCHITECTURE (new modules), DECISIONS (entries 23+), PLAYTEST
   (paper, sandbox, office space, night), README "What you see".
3. Look again in the browser: canteen/studio at different zooms, sandbox panel at narrow widths (sector select
   is cramped), a full night and morning at 1×.
4. Restart the game server with `.\start.ps1 -Rebuild` to play the new version (old saves load fine; the city
   starts on the next morning).

## Next

1. Visual polish pass with fresh eyes on a long run (label overlap at small zoom, crowded Bench).
   Also show colleague influence and refusals visibly in the office (speech lines between desks).
2. Run a short real Claude session (a few simulated days) to check prompt quality and cost per day.
3. Performance: cache team ratings across LAB backtests (data-driven runs are ~3× slower at max speed).
5. Summer leagues (e.g. MLS/Brasileirão desk) so June–July is not dead time.
6. Real sports provider (`ISportsDataProvider`) and a wall-clock "live" mode.
7. More drama, round two: bonus schemes, mentoring juniors, office romances/feuds that span seasons,
   journalists covering the company, the board injecting money with strings attached.
8. Accessibility: keyboard navigation for the office (tab through people), table views for every chart.
