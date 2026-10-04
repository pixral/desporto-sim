# Economy

Constants live in `backend/app/economy/config.py`. Everything is in fictional "simulation euros".

## Money locations

| Pot | Notes |
|---|---|
| Cash | Pays costs. Receives subscription revenue, bankroll withdrawals, loans. |
| Desk bankrolls | Stakes come out of them, payouts go back in. The CEO moves money between cash and desks. |
| Exposure | Stakes of open bets. |
| Payables | Costs accrued daily, paid at month close. |
| Debt | Credit line (2 %/month interest at a 3 % central bank rate; follows the rate). |

**Equity** = cash + bankrolls + exposure − debt − payables.
**Valuation** = equity + subscribers × price × 6 × *betting sentiment* + 1.5 × max(0, trailing 3-month net).
Betting sentiment = listed bookmakers' shares vs. their 120-day average (×0.75–1.25, see *The city* below).
Sandbox investor money goes into cash and is tracked as `invested`; it is not profit.

## Founding (defaults)

Capital from the difficulty preset (Normal €20,000): 70 % split across four desks (Germany, Premier League,
Europe, Markets), 30 % cash. 8 tipsters (random levels), 1 LAB researcher, a CEO.

## Difficulty presets

| | Easy | Normal | Hard |
|---|---|---|---|
| Starting capital | €30,000 | €20,000 | €14,000 |
| Salaries, rent, data feeds | ×0.85 | ×0.95 | ×1.10 |
| Starting subscribers | 75 | 65 | 45 |
| Subscriber acquisition / base churn | 0.50 / 6 % | 0.45 / 6.5 % | 0.38 / 7.5 % |
| Bookmakers' use of xG | −0.15 (softer) | −0.06 | +0.08 (sharper) |

The football (fixtures, results, news) is identical across difficulties for a given seed; only prices and the
company's economics change. Presets live in `economy/config.py` (`DIFFICULTY`).

## Costs (accrued daily, paid on the 1st)

| Line | Default |
|---|---|
| Salaries | junior €42, tipster €52, senior €68, head €88, researcher €58, CEO €95 per month × difficulty cost multiplier (hires negotiate) |
| Bonuses | 10 % of a tipster's positive monthly profit |
| Severance | 1 month of salary when fired |
| Rent | €60 + €8 per employee, plus leased east-wing space (below) |
| Sports data | €12 per covered competition (×1.15–1.25 while a data price rise lasts) |
| Marketing | CEO-set budget (default €80) |
| LAB | CEO-set budget (default €60): more budget = faster and more parallel experiments |
| AI | Real cost of every AI call (mock: estimated tokens priced at the reference model), converted at 0.92 €/$ and charged immediately |
| Interest | 2 % of debt per month at a 3 % base rate; +/− 0.25 %/12 per rate step |
| One-offs | Office fit-outs, lease break fees, sandbox disasters |

## Revenue

- **Betting P&L** (into desk bankrolls).
- **Subscriptions** (cash, monthly): price €12. Churn = base churn − 0.6 × company 90-day ROI − 0.01 × consumer
  confidence (clamped 2.5–30 %). New subscribers = acquisition × √marketing × (1 + clamp(6 × ROI, −0.5, +0.6)) ×
  reach, where reach = ad-ban factor (0.7) × rival-collapse factor (1.3) × (1 + 0.15 × consumer confidence) ×
  studio (1.5). The public track record matters.
- **Other income**: sandbox windfalls.

## Office space (east wing)

| Space | Fit-out | Monthly | Effect |
|---|---|---|---|
| The Canteen | €700 | €90 + €3 per employee | Stress target −0.04 for everyone |
| East Desk Wing | €700 | €100 | A seventh desk room |
| Media Studio | €1,200 | €120 | +50 % new subscribers |

All × the difficulty's cost multiplier. Leases are signed only at monthly reviews and never by a company in
distress; giving one up costs one month's bill. Constants: `FACILITIES` in `economy/config.py`.

## The city

`simulation/city.py` simulates Portavia's market and news on its own random stream; `economy/market.py` is
the only place where it reaches the books (pure functions of the world): `betting_sentiment`, `modifier`
(ad ban, data prices, subscriber boost), `loan_rate_monthly`, `economy` (consumer confidence) and the
facility costs. Rare stories are staggered at founding and have long cooldowns (ad ban ≥ 500 days, data price
rise ≥ 400, rival collapse ≥ 360), so a two-year run usually sees each at most once or twice.

## Liquidity

If cash goes negative, desk bankrolls are pulled proportionally, then the credit line is drawn (30 % of
starting capital, 10 % in distress, nothing when insolvent). Every emergency is logged in history.

## Status

| Status | Rule |
|---|---|
| thriving | not burning cash (3-month trailing), value ≥ 105 % of capital |
| stable | otherwise, runway ≥ 12 months or not burning |
| strained | runway < 12 months |
| distress | runway < 4 months or equity < 25 % of capital |
| bankrupt | run ended |

Runway = (cash + bankrolls − payables − debt) / average monthly net burn of the last 3 closed months
(estimated fixed costs before the first close).

## Calibration snapshot (2 years, mock AI)

Measured 2026-10-04 after the city, office-space and drama rounds. Normal and Hard: 16 seeds per CEO style;
Easy: 8 seeds. "Grew" = alive and worth more than the starting capital. Medians are the honest number: a few
runaway companies dominate the means.

| CEO style | Easy (from €30k): bankrupt · grew · median | Normal (from €20k): bankrupt · grew · median | Hard (from €14k): bankrupt · grew · median |
|---|---|---|---|
| Conservative operator | 0/8 · 6/8 · €33.7k | 0/16 · 6/16 · €15.2k | 3/16 · 0/16 · €3.4k |
| Aggressive expansionist | 0/8 · 4/8 · €32.6k | 1/16 · 5/16 · €13.8k | 11/16 · 0/16 · €3.6k |
| Data-driven | 0/8 · 6/8 · €40.1k | 0/16 · 6/16 · €16.2k | 8/16 · 2/16 · €2.6k |
| Chaotic founder | 0/8 · 4/8 · €50.5k | 0/16 · 3/16 · €13.7k | 10/16 · 0/16 · €3.4k |

Same build without the city and office features (Normal, 16 seeds): bankrupt 0/2/0/1, grew 5/3/5/5, medians
€16.6k/€10.8k/€13.4k/€14.6k — so this round is neutral to slightly positive. The drop against the previous
snapshot (Normal means €20–24k) came from the drama round (raises, poaching, board changes).

Easy has runaway winners: seed 7 is an unusually soft market, ROI reaches 9–17 % and stakes grow with the
bankroll, ending at €0.7M+. Bookmakers limiting winning accounts would be the realistic brake (roadmap).
Hard is a survival game: most companies end at a fraction of their capital.

Re-run with `python -m app.tools.batch --days 730 --seeds 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 --styles all --difficulty normal --quiet`.
