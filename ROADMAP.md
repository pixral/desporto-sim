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

## Next

1. Visual polish pass with fresh eyes on a long run (label overlap at small zoom, crowded Bench).
2. Run a short real Claude session (a few simulated days) to check prompt quality and cost per day.
3. Performance: cache team ratings across LAB backtests (data-driven runs are ~3× slower at max speed).
4. Economy tuning: slightly more upside for well-run companies; difficulty presets in the New company dialog.
5. Summer leagues (e.g. MLS/Brasileirão desk) so June–July is not dead time.
6. Real sports provider (`ISportsDataProvider`) and a wall-clock "live" mode.
7. More drama: tipster arguments/rivalries visible in the office, poaching, bonus schemes, CEO replaced by
   the board after a disastrous year.
8. Accessibility: keyboard navigation for the office (tab through people), table views for every chart.
