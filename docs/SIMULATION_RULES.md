# Simulation rules

All money is simulated. Nothing is placed with a real bookmaker.

## Time

The clock is simulated and decoupled from wall-clock time. One `step()` = one phase:

| Phase | Time | What happens |
|---|---|---|
| morning | 08:00 | Day reset. On the 1st: **month close**, the **board review** (may replace a CEO who wrecked the company), **raise demands**, **season awards** on 1 June, LAB audit, candidate refresh, LAB backtests of applicants, **CEO monthly review**. On Mondays: **CEO weekly review**. Fixtures (next 7 days), odds and team news are synced. LAB researchers progress/finish experiments and start new ones. |
| analysis | 11:00 | Today's matches are assigned (desk competitions ∩ strategy competitions, max 6 per tipster). Strategies compute probabilities/edges. Each tipster's top pick is shared as a *leaning* with colleagues. One AI call per tipster returns BET/NO_BET per match. Valid bets are booked at the best available price. |
| matches | 16:00 | Kick-offs; closing prices captured; tipsters with open bets watch. |
| settlement | 23:30 | Results (goals + xG) fetched, bets settled, psychology/relationships updated, **workplace drama** (desk arguments and celebrations, rival syndicates' poaching offers, resentment after refused raises), daily costs accrued, liquidity check, valuation snapshot, milestones, insolvency check. |

Runner speeds (seconds per phase): 1× 6 s, 2× 3 s, 4× 1.5 s, 16× 0.35 s, 64× 0.08 s, max = as fast as possible.
Autosaves: founding, every month close, every Monday, bankruptcy (final).

## Honesty guarantees

- Tipsters decide at 11:00 using only matches finished **before** that time, news already published,
  and the matchday prices. Closing prices and results are revealed only after kick-off / the final whistle.
- Stakes are clamped to the CEO's limit and to the desk bankroll; the booked price is always the real best
  price at decision time, whatever the agent quoted.
- Backtests are walk-forward with the same rule.

## The football world (mock provider)

- Leagues: Bundesliga (18), Premier League, La Liga, Serie A (20 each), double round robin with realistic
  weekend slots, international breaks and winter breaks. Champions League: 36-team league phase (8 matchdays),
  then a 16-team knockout (two legs) and a neutral final.
- Hidden truth per team: attack/defence quality, latent form (AR(1) per match), injuries (severity 1–3, known
  through news), manager sackings (form bounce). League goal levels drift weekly. Scores are Poisson; xG is a
  noisy view of the true scoring rates.
- Three bookmakers (Atlas sharp 4 %, Nordbet 5.5 %, Kicko soft 7 % margin) rate teams from results (Atlas leans
  on xG most), price injuries only partially until kick-off, shade towards popular clubs, carry a
  favourite–longshot margin, and the soft books copy part of the sharp line. Each season the books' reliance
  on xG drifts, so xG edges wax and wane.
- Calibration (several seeds): blind betting at the best price loses 1.3–5.6 % per market; well-tuned xG
  strategies made +1.5 to +5 %; goal-based strategies lost ~3 %.
- The provider owns its RNG: **same seed = same football**, regardless of what the company does.

## Settlement & stats

Win pays stake × odds into the desk bankroll; loss pays nothing; void returns the stake. A bet on a desk that
has since closed pays back into company cash. Closing-line value (CLV) = taken odds / best closing odds − 1.

## Bankruptcy (a real ending)

The run ends when any of these is true:
- equity (cash + bankrolls + open stakes − debt − payables) ≤ 0;
- cash is still negative after pulling every desk bankroll and maxing the credit line;
- month close cannot pay payroll;
- no tipsters, no candidates and no bankroll left.

Nobody bails the company out. A final save and an end-of-run summary are written.
