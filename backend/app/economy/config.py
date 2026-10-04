"""Economic constants. Simulation euros (€) — one consistent fictional scale, tuned for drama.

AI tipsters are cheap to run but not free; the company lives on thin betting edges plus a tip
subscription business whose growth depends on its public track record.
"""

RENT_BASE = 60.0  # per month
RENT_PER_HEAD = 8.0  # per active employee per month
DATA_PER_COMPETITION = 12.0  # sports data feed per covered competition per month
BONUS_RATE = 0.10  # share of a tipster's positive monthly profit
SEVERANCE_MONTHS = 1.0
SALARY_CUT_STRESS = 0.12

SUBSCRIPTION_PRICE = 12.0
# starting subscribers, acquisition (new/month = sub_acq * sqrt(marketing) * quality) and base churn
# depend on the difficulty preset below

LOAN_INTEREST_MONTHLY = 0.02
CREDIT_LINE_RATIO = 0.30  # of starting capital, while not in distress
DISTRESS_CREDIT_RATIO = 0.10

USD_TO_EUR = 0.92

DEFAULT_MARKETING = 80.0
DEFAULT_LAB_BUDGET = 60.0
DEFAULT_STAKE_LIMIT = 0.05
BANKROLL_SHARE = 0.7  # share of starting capital put into desk bankrolls at founding

# Difficulty presets. cost_mult scales salaries, rent and data feeds; market_xg shifts how much the
# bookmakers already use expected goals (negative = softer market, bigger edges for good analysts).
DIFFICULTY: dict[str, dict[str, float]] = {
    "easy": {"capital": 30000.0, "cost_mult": 0.85, "start_subs": 75, "sub_acq": 0.50, "sub_churn": 0.060,
             "market_xg": -0.15},
    "normal": {"capital": 20000.0, "cost_mult": 0.95, "start_subs": 65, "sub_acq": 0.45, "sub_churn": 0.065,
               "market_xg": -0.06},
    "hard": {"capital": 16000.0, "cost_mult": 1.05, "start_subs": 50, "sub_acq": 0.40, "sub_churn": 0.070,
             "market_xg": 0.05},
}


def preset(difficulty: str) -> dict[str, float]:
    return DIFFICULTY.get(difficulty, DIFFICULTY["normal"])

# Office space the CEO can lease in the empty east wing next door. Rent and food scale with cost_mult.
FACILITIES: dict[str, dict[str, object]] = {
    "canteen": {
        "name": "The Canteen", "fit_out": 700.0, "rent": 90.0, "per_head": 3.0,
        "effect": "Hot lunches every day: everyone's stress settles lower.",
    },
    "desk_wing": {
        "name": "East Desk Wing", "fit_out": 700.0, "rent": 100.0, "per_head": 0.0,
        "effect": "Room for a seventh betting desk.",
    },
    "studio": {
        "name": "Media Studio", "fit_out": 1200.0, "rent": 120.0, "per_head": 0.0,
        "effect": "Tipsters record a daily tips show: +50% new subscribers.",
    },
}
CANTEEN_STRESS_RELIEF = 0.04  # lower stress target for everyone
STUDIO_ACQUISITION = 1.5
LEASE_BREAK_MONTHS = 1.0  # rent owed when a lease is given up early

# Bookmakers' maximum stake per bet for a fresh account, and how soft books treat desks that win from them.
# Kicko (soft, best prices for analysts) limits fastest; Atlas (sharp, tightest prices) welcomes winners and
# only reins in blatant runaways.
BOOK_LIMITS: dict[str, float] = {"Atlas": 2000.0, "Nordbet": 600.0, "Kicko": 350.0}
BOOK_LIMIT_POLICY: dict[str, dict[str, float]] = {
    "Atlas": {"cut": 0.6, "floor": 300.0, "restore": 1.2, "min_profit": 5000.0, "min_roi": 0.06},
    "Nordbet": {"cut": 0.5, "floor": 25.0, "restore": 1.3},
    "Kicko": {"cut": 0.35, "floor": 10.0, "restore": 1.3},
}
BOOK_REVIEW_DAYS = 120  # results at that book the review looks at
BOOK_LIMIT_MIN_BETS = 40
BOOK_LIMIT_MIN_PROFIT = 300.0  # books act on money won, not on lucky streaks of small bets
BOOK_LIMIT_MIN_ROI = 0.04
