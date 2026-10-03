# Economy

Constants live in `backend/app/economy/config.py`. Everything is in fictional "simulation euros".

## Money locations

| Pot | Notes |
|---|---|
| Cash | Pays costs. Receives subscription revenue, bankroll withdrawals, loans. |
| Desk bankrolls | Stakes come out of them, payouts go back in. The CEO moves money between cash and desks. |
| Exposure | Stakes of open bets. |
| Payables | Costs accrued daily, paid at month close. |
| Debt | Credit line (2 %/month interest). |

**Equity** = cash + bankrolls + exposure − debt − payables.
**Valuation** = equity + subscribers × price × 6 + 1.5 × max(0, trailing 3-month net).

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
| Rent | €60 + €8 per employee |
| Sports data | €12 per covered competition |
| Marketing | CEO-set budget (default €80) |
| LAB | CEO-set budget (default €60): more budget = faster and more parallel experiments |
| AI | Real cost of every AI call (mock: estimated tokens priced at the reference model), converted at 0.92 €/$ and charged immediately |
| Interest | 2 % of debt per month |

## Revenue

- **Betting P&L** (into desk bankrolls).
- **Subscriptions** (cash, monthly): price €12. Churn = base churn − 0.6 × company 90-day ROI (clamped 2.5–30 %).
  New subscribers = acquisition × √marketing × (1 + clamp(6 × ROI, −0.5, +0.6)). The public track record matters.

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

Normal and Hard: 16 seeds per CEO style; Easy: 6 seeds per style (before the final preset tweak).

| CEO style | Easy: bankrupt / median value (from €30k) | Normal: bankrupt / grew / mean value (from €20k) | Hard: bankrupt / grew (from €14k) |
|---|---|---|---|
| Conservative operator | 0/6 · €36.6k | 0/16 · 7/16 · €21.1k | 0/16 · 0/16 |
| Aggressive expansionist | 0/6 · €33.7k | 4/16 · 5/16 · €20.4k | 12/16 · 2/16 |
| Data-driven | 0/6 · €41.3k | 0/16 · 7/16 · €23.9k | 5/16 · 1/16 |
| Chaotic founder | 0/6 · €30.9k | 1/16 · 6/16 · €21.2k | 9/16 · 0/16 |

Easy is forgiving, Normal is a coin flip that rewards good management, Hard is a survival game.
Re-run with `python -m app.tools.batch --days 730 --seeds 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 --styles all --difficulty normal --quiet`.
