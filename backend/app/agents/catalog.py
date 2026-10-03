"""Static catalog: specialties, department kinds, titles, CEO styles."""

from __future__ import annotations

from typing import Any, NamedTuple

ALL_COMPS = ["BL1", "PL", "LL", "SA", "UCL"]
ALL_MARKETS = ["home_win", "draw", "away_win", "over_2_5", "under_2_5"]
MARKETS_1X2 = ["home_win", "draw", "away_win"]


class Specialty(NamedTuple):
    key: str
    label: str
    role: str
    competitions: list[str]  # empty = whatever the department covers
    params: dict[str, Any]
    home_departments: list[str]  # department kinds this specialty naturally belongs to


SPECIALTIES: dict[str, Specialty] = {s.key: s for s in [
    Specialty("bundesliga", "Bundesliga specialist", "tipster", ["BL1"],
              dict(model_weight=0.55, window=14, half_life=8, news_weight=1.0, markets=ALL_MARKETS, min_edge=0.03),
              ["germany"]),
    Specialty("premier_league", "Premier League specialist", "tipster", ["PL"],
              dict(model_weight=0.55, window=14, half_life=8, news_weight=1.0, markets=ALL_MARKETS, min_edge=0.03),
              ["england"]),
    Specialty("la_liga", "La Liga specialist", "tipster", ["LL"],
              dict(model_weight=0.55, window=14, half_life=8, news_weight=1.0, markets=ALL_MARKETS, min_edge=0.03),
              ["spain", "europe"]),
    Specialty("serie_a", "Serie A specialist", "tipster", ["SA"],
              dict(model_weight=0.55, window=14, half_life=8, news_weight=1.0, markets=ALL_MARKETS, min_edge=0.03),
              ["italy", "europe"]),
    Specialty("champions_league", "Champions League specialist", "tipster", ["UCL"],
              dict(model_weight=0.45, window=20, half_life=10, news_weight=0.9, markets=MARKETS_1X2, min_edge=0.03),
              ["europe"]),
    Specialty("statistical", "Statistical analyst", "tipster", [],
              dict(model_weight=0.85, window=30, half_life=25, shrinkage=6, opponent_adjust=True, news_weight=0.3,
                   markets=ALL_MARKETS, min_edge=0.04),
              ["germany", "england", "spain", "italy", "goals"]),
    Specialty("form", "Form analyst", "tipster", [],
              dict(model_weight=0.8, window=8, half_life=3, shrinkage=3, news_weight=0.6, markets=MARKETS_1X2,
                   min_edge=0.04),
              ["germany", "england", "spain", "italy"]),
    Specialty("market", "Odds/market analyst", "tipster", [],
              dict(model_weight=0.0, news_weight=0.0, markets=ALL_MARKETS, min_edge=0.015, max_odds=5.0),
              ["markets"]),
    Specialty("underdog", "Underdog specialist", "tipster", [],
              dict(model_weight=0.6, window=16, half_life=8, underdog_bias=0.02, markets=["home_win", "away_win"],
                   min_odds=3.0, max_odds=9.0, min_edge=0.04),
              ["markets"]),
    Specialty("goals", "Goals (over/under) specialist", "tipster", [],
              dict(model_weight=0.75, window=12, half_life=6, news_weight=0.7, markets=["over_2_5", "under_2_5"],
                   min_edge=0.03, max_odds=3.0),
              ["goals"]),
    Specialty("value", "Conservative value bettor", "tipster", [],
              dict(model_weight=0.6, window=18, half_life=10, news_weight=0.8, min_edge=0.06, min_odds=1.5,
                   max_odds=3.6, kelly_fraction=0.15, markets=ALL_MARKETS),
              ["markets"]),
    Specialty("contrarian", "Contrarian bettor", "tipster", [],
              dict(model_weight=0.5, window=14, half_life=8, fade_popular=True, markets=MARKETS_1X2, min_edge=0.02),
              ["markets"]),
    Specialty("quant_research", "Quantitative researcher", "researcher", [], {}, ["lab"]),
    Specialty("market_research", "Market microstructure researcher", "researcher", [], {}, ["lab"]),
    Specialty("behavioral_research", "Behavioural researcher", "researcher", [], {}, ["lab"]),
]}


class DepartmentKind(NamedTuple):
    key: str
    name: str
    competitions: list[str]
    specialties: list[str]  # preferred hires
    color: str


DEPARTMENT_KINDS: dict[str, DepartmentKind] = {k.key: k for k in [
    DepartmentKind("germany", "Germany Desk", ["BL1"], ["bundesliga", "form", "statistical", "goals"], "#d8232a"),
    DepartmentKind("england", "Premier League Desk", ["PL"], ["premier_league", "statistical", "form"], "#6a2c91"),
    DepartmentKind("europe", "Europe Desk", ["UCL", "LL", "SA"], ["champions_league", "la_liga", "serie_a"], "#24318f"),
    DepartmentKind("spain", "Spain Desk", ["LL"], ["la_liga", "form", "statistical"], "#f08c00"),
    DepartmentKind("italy", "Italy Desk", ["SA"], ["serie_a", "statistical", "form"], "#1f6fd1"),
    DepartmentKind("markets", "Markets Desk", ALL_COMPS, ["market", "value", "contrarian", "underdog"], "#18a058"),
    DepartmentKind("goals", "Goals Desk", ALL_COMPS, ["goals", "statistical"], "#c2410c"),
    DepartmentKind("lab", "LAB", [], ["quant_research", "market_research", "behavioral_research"], "#0e9aa7"),
]}

BETTING_KINDS = [k for k in DEPARTMENT_KINDS if k != "lab"]
MAX_DESK_ROOMS = 6  # office slots for betting departments
MAX_DESK_SIZE = 5

TIPSTER_TITLES = {0: "Junior Tipster", 1: "Tipster", 2: "Senior Tipster", 3: "Head of Desk"}
LEVEL_SALARY = {0: 42.0, 1: 52.0, 2: 68.0, 3: 88.0}
LEVEL_BANKROLL_WEIGHT = {0: 0.8, 1: 1.0, 2: 1.25, 3: 1.5}
RESEARCHER_SALARY = 58.0
CEO_SALARY = 95.0

CEO_STYLE_INFO: dict[str, dict[str, str]] = {
    "conservative_operator": {
        "label": "Conservative operator",
        "description": "Protects the bankroll first. Small stakes, slow hiring, quick to cut costs when things look shaky.",
    },
    "aggressive_expansionist": {
        "label": "Aggressive expansionist",
        "description": "Growth at all costs. Hires, opens desks, raises limits after wins and doubles down when behind.",
    },
    "data_driven": {
        "label": "Data-driven manager",
        "description": "Trusts sample sizes and the LAB. Fires and promotes on statistical evidence, deploys tested strategies.",
    },
    "chaotic_founder": {
        "label": "Chaotic founder",
        "description": "Brilliant on a good day. Impulsive hires and firings, dramatic memos, unpredictable risk appetite.",
    },
}
