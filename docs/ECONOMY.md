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

€20,000 capital: 70 % split across four desks (Germany, Premier League, Europe, Markets), 30 % cash.
8 tipsters (random levels), 1 LAB researcher, a CEO. 50 subscribers.

## Costs (accrued daily, paid on the 1st)

| Line | Default |
|---|---|
| Salaries | junior €42, tipster €52, senior €68, head €88, researcher €58, CEO €95 per month (hires negotiate) |
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
- **Subscriptions** (cash, monthly): price €12. Churn = 7 % − 0.6 × company 90-day ROI (clamped 2.5–30 %).
  New subscribers = 0.4 × √marketing × (1 + clamp(6 × ROI, −0.5, +0.6)). The public track record matters.

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

## Calibration snapshot (24 runs × 2 years, mock AI)

| CEO style | Bankrupt | Median value after 2 years |
|---|---|---|
| Conservative operator | 0/6 | €13.1k |
| Aggressive expansionist | 3/6 | €4.4k (peaks up to €53k) |
| Data-driven | 0/6 | €10.9k (peaks up to €57k) |
| Chaotic founder | 0/6 | €10.2k (peaks up to €64k) |

Re-run with `python -m app.tools.batch --days 730 --seeds 1 2 3 4 5 6 --styles all`.
