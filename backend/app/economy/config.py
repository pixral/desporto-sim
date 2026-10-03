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
START_SUBSCRIBERS = 50
SUB_ACQUISITION = 0.40  # new subscribers per month = SUB_ACQUISITION * sqrt(marketing) * quality
SUB_BASE_CHURN = 0.07

LOAN_INTEREST_MONTHLY = 0.02
CREDIT_LINE_RATIO = 0.30  # of starting capital, while not in distress
DISTRESS_CREDIT_RATIO = 0.10

USD_TO_EUR = 0.92

DEFAULT_MARKETING = 80.0
DEFAULT_LAB_BUDGET = 60.0
DEFAULT_STAKE_LIMIT = 0.05
BANKROLL_SHARE = 0.7  # share of starting capital put into desk bankrolls at founding
