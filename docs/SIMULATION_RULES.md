# Simulation rules

All money is simulated. Nothing is placed with a real bookmaker.

## Time

The clock is simulated and decoupled from wall-clock time. One `step()` = one phase:

| Phase | Time | What happens |
|---|---|---|
| morning | 08:00 | Day reset; staff arrive through the front door. On the 1st: **month close**, the **board review** (may replace a CEO who wrecked the company), **raise demands**, **season awards** on 1 June, LAB audit, candidate refresh, LAB backtests of applicants, **CEO monthly review**. On Mondays: **CEO weekly review**. Fixtures (next 7 days), odds and team news are synced, and **the morning paper** is printed (yesterday's markets, city news, football, the company's own story). Reviews are held with the people they affect plus each desk's lead (the LAB joins monthly): one or two people meet in the CEO's office, more in the meeting room. LAB researchers progress/finish experiments and start new ones. With a media studio, the two in-form tipsters record the morning show. |
| analysis | 11:00 | Today's matches are assigned (desk competitions ∩ strategy competitions, max 6 per tipster). Strategies compute probabilities/edges. Each tipster's top pick is shared as a *leaning* with colleagues. One AI call per tipster returns BET/NO_BET per match. Valid bets are booked at the best available price. |
| matches | 16:00 | Kick-offs; closing prices captured; tipsters with open bets watch. |
| settlement | 23:30 | Results (goals + xG) fetched, bets settled, psychology/relationships updated, **workplace drama** (desk arguments and celebrations, rival syndicates' poaching offers, resentment after refused raises), daily costs accrued, liquidity check, valuation snapshot, milestones, insolvency check. Everyone goes home for the night. |

Runner speeds (seconds per phase): 1× 6 s, 2× 3 s, 4× 1.5 s, 16× 0.35 s, 64× 0.08 s, max = as fast as possible.
Autosaves: founding, month closes and Mondays (at most one per minute of real time, so fast-forwarding stays
fast), shutdown, bankruptcy (final).

## Honesty guarantees

- Tipsters decide at 11:00 using only matches finished **before** that time, news already published,
  and the matchday prices. Closing prices and results are revealed only after kick-off / the final whistle.
- Stakes are clamped to the CEO's limit and to the desk bankroll; the booked price is always the real best
  price at decision time that the desk's bookmaker limits allow, whatever the agent quoted.

## Bookmaker limits

Each desk has an account with each bookmaker. A fresh account may stake up to €2,000 a bet at Atlas, €600 at
Nordbet and €350 at Kicko. On the 1st of each month the books look at the last 120 days: a desk that won at
least €300 from a soft book on 40+ bets at ≥4% ROI gets its limit cut (Kicko to 35%, Nordbet to 50%, floors €10
and €25); a desk that lost money there gets 30% back, up to the normal limit. Atlas is sharp, has the tightest
prices and welcomes winners: it only cuts (to 60%, floor €300) a runaway that took €5,000+ from it at ≥6% ROI. Bets go to the best price whose limit takes the whole stake; if none does, the most
generous book takes what it allows. Every change is in the history; the desk panel shows the limits.
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

## The city and the morning paper

The company lives in Portavia, a fictional city with a small stock market (12 fictional listed companies,
including three bookmakers named after the ones in the football world) and a daily paper, *The Portavia
Ledger*. The city has its own random stream: it never changes the football or the agents' dice.

- Prices follow a random walk with market and sector moves, pulled slowly towards a fair value that grows
  with each company's drift. Quarterly results, central bank meetings (every ~6 weeks) and random news move
  them; some stories are arcs (a construction firm wins a tender; weeks later the site has an accident, a
  delay, or a ribbon cutting).
- Stories that reach the company (each is also written into the history):
  - **listed bookmakers' share prices** set how much investors pay for our subscriber business (×0.75–1.25 on
    the subscriber goodwill in the company value, vs. their 120-day average);
  - **advertising ban on betting** (rare, 3–5 months): marketing brings 30% fewer subscribers;
  - **a rival tipster syndicate collapses**: +30% new subscribers for 45 days;
  - **sports-data price rise**: data feeds cost 15–25% more for six months;
  - **central bank rate**: the credit line's interest follows it (2%/month at a 3% base rate);
  - **consumer confidence** nudges subscriber growth and churn; a tram strike makes staff a little more stressed.
- The paper also reports last night's football (upsets, goal-fests, sackings and long injuries from the
  provider's news) and the company's own notable events. The CEO's report includes the latest headlines.

## Office space

The east wing next door can be leased in three lots. Each costs a one-off fit-out and a monthly bill (rent,
plus food per head for the canteen; both scale with the difficulty's cost level). Leases are signed at monthly
reviews and refused to a company in distress; giving one up costs a month's rent.

| Space | Effect |
|---|---|
| The Canteen | Everyone's stress settles 4 points lower; idle staff take late lunches there. |
| East Desk Wing | A seventh desk room (and a corridor). |
| Media Studio | +50% new subscribers; two tipsters record a morning show. |

## Sandbox tools

The player can intervene: investors, windfalls, disasters (fire, flood, lawsuit, data breach, tax audit, in
three severities), stock-market shocks, planted headlines, morale swings, a star applicant, viral or bad press,
replacing the CEO, free office space, changing difficulty. Every intervention goes through the normal books
(investor money is equity, not profit; disasters and windfalls are one-off costs/income), is written into the
history, and is counted on the end screen ("sandbox run").

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
