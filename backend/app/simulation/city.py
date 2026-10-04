"""The city around the company: a small stock market, news arcs and the morning paper.

Every morning (08:00) the paper reports what happened since the last edition: yesterday's market
session, business and city news, last night's football, and the company's own news. The city has
its own random stream, so it never changes the football or the agents' dice.

Some stories reach the company (see economy/market.py):
- listed bookmakers' share prices move the value of the subscriber business,
- an advertising ban on betting cuts marketing reach, a rival's collapse sends customers our way,
- a data-feed price hike raises the data bill, the central bank rate sets the credit line's interest,
- consumer confidence nudges subscriber growth and churn.
"""

from __future__ import annotations

import math
import random
from bisect import bisect_left
from datetime import date, datetime, time, timedelta
from typing import Any

from app.domain.city import CityState, Modifier, PressItem, Stock, Story
from app.domain.world import World
from app.economy import market

from . import history
from .rng import dump_rng, load_rng

HISTORY_DAYS = 400  # market days of prices kept
PRESS_RETENTION_DAYS = 150
WARMUP_DAYS = 120

# ticker, name, sector, listing price, annual volatility, annual drift
LISTINGS: list[tuple[str, str, str, float, float, float]] = [
    ("ATLS", "Atlas Sportsbook", "betting", 42.0, 0.30, 0.06),
    ("NORD", "Nordbet Group", "betting", 18.5, 0.36, 0.04),
    ("KICK", "Kicko Gaming", "betting", 7.8, 0.46, 0.03),
    ("PVTV", "Portavia TV & Media", "media", 24.0, 0.30, 0.03),
    ("BRKH", "Brickhall Construction", "construction", 31.0, 0.32, 0.04),
    ("STRD", "Stride Athletics", "sportswear", 55.0, 0.28, 0.07),
    ("NEUR", "Neuralis AI", "tech", 120.0, 0.52, 0.12),
    ("STAT", "Statlane Data", "tech", 36.0, 0.34, 0.06),
    ("PBNK", "Banco Portavia", "banking", 14.2, 0.24, 0.04),
    ("VOLT", "Voltara Energy", "energy", 22.0, 0.30, 0.03),
    ("SKYP", "SkyPorta Airlines", "airlines", 9.4, 0.44, 0.02),
    ("MESA", "Mesa Foods", "food", 27.0, 0.22, 0.05),
]
SECTOR_LABEL = {
    "betting": "betting", "media": "media", "construction": "construction", "sportswear": "sportswear",
    "tech": "tech", "banking": "banking", "energy": "energy", "airlines": "airline", "food": "food",
}
VENUES = ("the new Riverside Arena", "the Northgate stadium roof", "the Harbour Line tram bridge",
          "the Eastbank training complex", "Terminal 3 at Portavia airport", "the Old Docks concert hall",
          "the city's new aquatics centre", "the Ferreira Street tower")
RIVALS = ("Nordic Edge Syndicate", "Kopa Analytics", "Lisbon Value Club", "Danube Quant Fund",
          "Red Card Partners", "Atlas Capital Betting")
LEAGUES = ("the Bundesliga", "the Premier League", "La Liga", "Serie A", "the Champions League")
CLUBS_FOR_KIT = ("a Premier League giant", "a Bundesliga champion", "a Serie A club", "the national team")


# ---------------------------------------------------------------------------------- setup
def ensure_city(world: World) -> None:
    """Create the market (with some price history) for new companies and for saves made before the city existed."""
    city = world.city
    if city.stocks:
        return
    rng = _rng(world)
    first_earnings = world.today + timedelta(days=5)
    for i, (ticker, name, sector, price, vol, drift) in enumerate(LISTINGS):
        p = price * math.exp(rng.gauss(0, 0.08))
        city.stocks[ticker] = Stock(ticker=ticker, name=name, sector=sector, price=round(p, 2), base=round(p, 2),
                                    anchor=round(p, 2), vol=vol, drift=drift,
                                    next_earnings=first_earnings + timedelta(days=i * 7))
    city.economy = round(rng.uniform(-0.2, 0.3), 3)
    for key, _w, _m, cooldown, _h in EVENTS:  # stagger the rare stories so they don't all land in the first weeks
        if cooldown >= 180:
            city.recent_templates[key] = world.today.toordinal() - rng.randint(0, cooldown)
    city.next_rate_meeting = world.today + timedelta(days=rng.randint(10, 40))
    # warm up: some market history before the company existed
    d = world.today - timedelta(days=1)
    days: list[date] = []
    while len(days) < WARMUP_DAYS:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    for day in reversed(days):
        _session(city, rng, day, {})
    city.rng_state = dump_rng(rng)


def _rng(world: World) -> random.Random:
    return load_rng(world.city.rng_state, world.config.seed * 7919 + 1013)


# ---------------------------------------------------------------------------------- the morning
def morning(world: World) -> list[PressItem]:
    """Simulate everything since the last edition and print today's paper. Idempotent per day."""
    ensure_city(world)
    city = world.city
    today = world.today
    if city.editions and city.editions[-1] >= today:
        return []
    rng = _rng(world)
    since = city.editions[-1] if city.editions else today - timedelta(days=1)
    items: list[PressItem] = []
    d = since
    while d < today:  # usually one day; more after a gap
        items += _day(world, rng, d)
        d += timedelta(days=1)
    items += _sports_items(world, since, today)
    items += _company_items(world, since)
    for it in items:
        it.day = today
    if items:
        lead = max(items, key=lambda p: (p.importance, p.kind not in ("wrap", "roundup"), _SECTION_RANK[p.section],
                                         abs(p.move or 0)))
        lead.lead = True
    city.press.extend(items)
    city.editions.append(today)
    _prune(world)
    city.rng_state = dump_rng(rng)
    return items


_SECTION_RANK = {"company": 4, "business": 3, "city": 2, "sports": 1, "front": 5}


def _day(world: World, rng: random.Random, d: date) -> list[PressItem]:
    city = world.city
    trading = d.weekday() < 5
    jumps: dict[str, float] = {}
    items: list[PressItem] = []
    city.economy = max(-1.0, min(1.0, 0.985 * city.economy + rng.gauss(0, 0.025)))
    for m in [m for m in city.modifiers if m.until < d]:
        items.append(_press(world, d, "business", f"{m.label}: over", "", importance=1, tone="neutral",
                            effect=f"No longer in force: {m.label.lower()}."))
        city.modifiers.remove(m)
    items += _scheduled(world, rng, d, jumps, trading)
    n = _poisson(rng, 1.7 if trading else 0.8)
    for _ in range(n):
        it = _random_event(world, rng, d, jumps, trading)
        if it:
            items += it
    if trading:
        _session(city, rng, d, jumps)
        items.append(_market_wrap(world, d))
    return items


def _poisson(rng: random.Random, lam: float) -> int:
    k, p, limit = 0, 1.0, math.exp(-lam)
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def _session(city: CityState, rng: random.Random, d: date, jumps: dict[str, float]) -> None:
    mkt = rng.gauss(0.0003, 0.008) + jumps.get("market", 0.0) + 0.0005 * city.economy
    sectors = {s.sector for s in city.stocks.values()}
    sec = {s: rng.gauss(0.0, 0.006) + jumps.get(f"sector:{s}", 0.0) for s in sorted(sectors)}
    for s in city.stocks.values():
        # random walk around a fair value that grows with the company's drift (so nobody goes to zero for good)
        s.anchor = (s.anchor or s.base) * math.exp(s.drift / 252)
        pull = 0.004 * math.log(s.anchor / s.price)
        r = pull + mkt + sec[s.sector] + rng.gauss(0.0, s.vol * 0.75 / math.sqrt(252)) + jumps.get(s.ticker, 0.0)
        s.price = round(max(0.5, s.price * math.exp(r)), 2)
        s.history.append(s.price)
        if len(s.history) > HISTORY_DAYS:
            s.history = s.history[-HISTORY_DAYS:]
    city.days.append(d)
    city.index.append(round(1000 * sum(s.price / s.base for s in city.stocks.values()) / len(city.stocks), 1))
    if len(city.days) > HISTORY_DAYS:
        city.days = city.days[-HISTORY_DAYS:]
        city.index = city.index[-HISTORY_DAYS:]


def _market_wrap(world: World, d: date) -> PressItem:
    city = world.city
    idx = city.index
    chg = idx[-1] / idx[-2] - 1 if len(idx) >= 2 else 0.0
    movers = sorted(city.stocks.values(), key=lambda s: s.history[-1] / s.history[-2] - 1 if len(s.history) >= 2 else 0)
    lo, hi = movers[0], movers[-1]
    lo_chg = lo.history[-1] / lo.history[-2] - 1
    hi_chg = hi.history[-1] / hi.history[-2] - 1
    return _press(world, d, "business", f"PVX 12 {'gains' if chg >= 0 else 'slips'} {abs(chg):.1%} to {idx[-1]:,.1f}",
                  f"{hi.name} led the board ({hi_chg:+.1%}); {lo.name} lagged ({lo_chg:+.1%}).",
                  [hi.ticker, lo.ticker], chg, 1, "good" if chg > 0.004 else "bad" if chg < -0.004 else "neutral",
                  kind="wrap")


# ---------------------------------------------------------------------------------- scheduled news
def _scheduled(world: World, rng: random.Random, d: date, jumps: dict[str, float], trading: bool) -> list[PressItem]:
    city = world.city
    out: list[PressItem] = []
    if trading:
        for s in city.stocks.values():  # quarterly results
            if s.next_earnings and s.next_earnings <= d:
                s.next_earnings = d + timedelta(days=rng.randint(85, 95))
                beat = rng.random() < 0.55 + 0.1 * city.economy
                move = rng.uniform(0.03, 0.09) if beat else -rng.uniform(0.04, 0.12)
                jumps[s.ticker] = jumps.get(s.ticker, 0.0) + move
                extra = {"betting": " on record betting volumes" if beat else " as punters' winnings bite",
                         "tech": " as AI demand surges" if beat else " amid slowing contracts"}.get(s.sector, "")
                out.append(_press(world, d, "business",
                                  f"{s.name} {'beats' if beat else 'misses'} forecasts{extra}",
                                  f"Quarterly results sent {s.ticker} {'up' if beat else 'down'} {abs(move):.0%}.",
                                  [s.ticker], move, 2 if abs(move) > 0.07 else 1, "good" if beat else "bad"))
        if city.next_rate_meeting and city.next_rate_meeting <= d:
            out += _rate_meeting(world, rng, d, jumps)
    for st in [s for s in city.stories if s.due <= d]:
        city.stories.remove(st)
        if trading:
            out += _story_outcome(world, rng, d, st, jumps)
        else:
            st.due = d + timedelta(days=1)
            city.stories.append(st)
    return out


def _rate_meeting(world: World, rng: random.Random, d: date, jumps: dict[str, float]) -> list[PressItem]:
    city = world.city
    city.next_rate_meeting = d + timedelta(days=42)
    eco = city.economy
    roll = rng.random()
    hike = roll < max(0.0, 0.1 + 0.5 * eco) and city.base_rate < 7.0
    cut = not hike and roll > 1 - max(0.0, 0.1 - 0.5 * eco) and city.base_rate > 0.5
    if not hike and not cut:
        return [_press(world, d, "business", f"Central bank holds rates at {city.base_rate:.2f}%", "", importance=1)]
    city.base_rate = round(city.base_rate + (0.25 if hike else -0.25), 2)
    jumps["market"] = jumps.get("market", 0.0) + (-0.01 if hike else 0.01)
    jumps["sector:banking"] = jumps.get("sector:banking", 0.0) + (0.02 if hike else -0.015)
    rate = market.loan_rate_monthly(world)
    it = _press(world, d, "business",
                f"Central bank {'raises' if hike else 'cuts'} rates to {city.base_rate:.2f}%",
                "Borrowing gets dearer across Portavia." if hike else "Cheaper money for businesses and households.",
                ["PBNK"], -0.01 if hike else 0.01, 2, "bad" if hike else "good",
                effect=f"Our credit line now costs {rate:.2%} a month.")
    if world.finances.debt > 0:
        history.record(world, "city_rates", it.headline, it.effect, 1, "bad" if hike else "good")
    return [it]


def _story_outcome(world: World, rng: random.Random, d: date, st: Story, jumps: dict[str, float]) -> list[PressItem]:
    stock = world.city.stocks.get(st.ticker)
    if stock is None:
        return []
    roll = rng.random()
    if roll < 0.3:
        hurt = rng.randint(2, 9)
        move = -rng.uniform(0.09, 0.18)
        jumps[st.ticker] = jumps.get(st.ticker, 0.0) + move
        return [_press(world, d, "business", f"Accident at {st.subject} site: {hurt} workers hurt, work halted",
                       f"Months after winning the contract, {stock.name} faces an inquiry. Shares fell {abs(move):.0%}.",
                       [st.ticker], move, 3, "bad")]
    if roll < 0.55:
        move = -rng.uniform(0.04, 0.07)
        jumps[st.ticker] = jumps.get(st.ticker, 0.0) + move
        return [_press(world, d, "business", f"{st.subject[0].upper() + st.subject[1:]} delayed and over budget",
                       f"{stock.name} blames suppliers.", [st.ticker], move, 2, "bad")]
    move = rng.uniform(0.03, 0.06)
    jumps[st.ticker] = jumps.get(st.ticker, 0.0) + move
    return [_press(world, d, "business", f"{st.subject[0].upper() + st.subject[1:]} opens on time",
                   f"A ribbon, a speech, and a {move:.0%} rise for {stock.name}.", [st.ticker], move, 1, "good")]


# ---------------------------------------------------------------------------------- random news
def _random_event(world: World, rng: random.Random, d: date, jumps: dict[str, float],
                  trading: bool) -> list[PressItem] | None:
    city = world.city
    pool = [e for e in EVENTS if (trading or not e[2])
            and d.toordinal() - city.recent_templates.get(e[0], -99_999) >= e[3]]
    if not pool:
        return None
    total = sum(e[1] for e in pool)
    roll = rng.uniform(0, total)
    for key, weight, _needs_market, _cooldown, handler in pool:
        roll -= weight
        if roll <= 0:
            out = handler(world, rng, d, jumps)
            if out:
                city.recent_templates[key] = d.toordinal()
            return out
    return None


def _move(jumps: dict[str, float], key: str, lo: float, hi: float, rng: random.Random) -> float:
    m = rng.uniform(lo, hi)
    jumps[key] = jumps.get(key, 0.0) + m
    return m


def _ev_tender(world, rng, d, jumps):
    venue = rng.choice(VENUES)
    m = _move(jumps, "BRKH", 0.04, 0.08, rng)
    world.city.stories.append(Story(id=world.next_id("st"), kind="construction", ticker="BRKH", subject=venue,
                                    opened=d, due=d + timedelta(days=rng.randint(14, 60))))
    return [_press(world, d, "business", f"Brickhall wins the tender to build {venue}",
                   f"The city council picked Brickhall Construction over three rivals. Shares rose {m:.0%}.",
                   ["BRKH"], m, 2, "good")]


def _ev_ad_ban(world, rng, d, jumps):
    if market.modifier(world, "ad_ban") < 1.0:
        return None
    m = _move(jumps, "sector:betting", -0.10, -0.06, rng)
    days = rng.randint(90, 150)
    world.city.modifiers.append(Modifier(kind="ad_ban", value=0.7, since=d, until=d + timedelta(days=days),
                                         label="Betting advertising ban"))
    it = _press(world, d, "business", "Regulator bans betting adverts on TV and radio",
                f"Listed bookmakers fell sharply ({m:.0%}). The ban runs for {days} days.",
                ["ATLS", "NORD", "KICK"], m, 3, "bad",
                effect=f"Our marketing reaches 30% fewer new subscribers for {days} days.")
    history.record(world, "city_ad_ban", "Advertising ban on betting", it.effect, 2, "bad")
    return [it]


def _ev_ad_ban_lifted(world, rng, d, jumps):
    active = [m for m in world.city.modifiers if m.kind == "ad_ban" and m.until > d and (d - m.since).days >= 30]
    if not active:
        return None
    world.city.modifiers = [m for m in world.city.modifiers if m not in active]
    mv = _move(jumps, "sector:betting", 0.03, 0.06, rng)
    it = _press(world, d, "business", "Court overturns the betting advertising ban",
                "Judges found the ban disproportionate.", ["ATLS", "NORD", "KICK"], mv, 2, "good",
                effect="Our marketing works at full strength again.")
    history.record(world, "city_ad_ban", "Advertising ban overturned", it.effect, 2, "good")
    return [it]


def _ev_fixing(world, rng, d, jumps):
    league = rng.choice(LEAGUES)
    m = _move(jumps, "sector:betting", -0.06, -0.03, rng)
    return [_press(world, d, "business", f"Match-fixing probe opens in {league}",
                   f"Bookmakers suspended markets on two fixtures. Betting shares fell {abs(m):.0%}.",
                   ["ATLS", "NORD", "KICK"], m, 2, "bad")]


def _ev_record_weekend(world, rng, d, jumps):
    m = _move(jumps, "sector:betting", 0.02, 0.05, rng)
    return [_press(world, d, "business", "Bookmakers report a record weekend of bets",
                   f"Favourites lost, margins held. Betting shares up {m:.0%}.", ["ATLS", "NORD", "KICK"], m, 1, "good")]


def _ev_rival_collapse(world, rng, d, jumps):
    rival = rng.choice(RIVALS)
    m = _move(jumps, "sector:betting", 0.0, 0.02, rng)
    world.city.modifiers.append(Modifier(kind="sub_boost", value=1.3, since=d, until=d + timedelta(days=45),
                                         label=f"{rival}'s customers looking for a new service"))
    it = _press(world, d, "business", f"{rival} shuts down after a disastrous season",
                "Thousands of subscribers are looking for a new tipster service.", [], m, 2, "neutral",
                effect="+30% new subscribers for 45 days while their customers shop around.")
    history.record(world, "city_rival", f"Rival {rival} collapses", it.effect, 2, "good")
    return [it]


def _ev_data_hike(world, rng, d, jumps):
    if market.modifier(world, "data_prices") > 1.0:
        return None
    pct = rng.choice((0.15, 0.2, 0.25))
    m = _move(jumps, "STAT", 0.03, 0.07, rng)
    world.city.modifiers.append(Modifier(kind="data_prices", value=1 + pct, since=d, until=d + timedelta(days=180),
                                         label="Statlane data price rise"))
    it = _press(world, d, "business", f"Statlane raises sports data prices by {pct:.0%}",
                f"Clubs, broadcasters and tipsters will pay more for live feeds. Statlane shares rose {m:.0%}.",
                ["STAT"], m, 2, "bad", effect=f"Our data feeds cost {pct:.0%} more for six months.")
    history.record(world, "city_data", f"Sports data prices up {pct:.0%}", it.effect, 2, "bad")
    return [it]


def _ev_data_outage(world, rng, d, jumps):
    m = _move(jumps, "STAT", -0.08, -0.04, rng)
    return [_press(world, d, "business", "Statlane outage leaves broadcasters without live stats",
                   f"A four-hour blackout of its feeds. Shares fell {abs(m):.0%}.", ["STAT"], m, 1, "bad")]


def _ev_ai(world, rng, d, jumps):
    up = rng.random() < 0.6
    m = _move(jumps, "NEUR", 0.07, 0.15, rng) if up else _move(jumps, "NEUR", -0.12, -0.06, rng)
    jumps["sector:tech"] = jumps.get("sector:tech", 0.0) + m * 0.2
    if up:
        return [_press(world, d, "business", "Neuralis unveils a faster AI model",
                       f"Analysts call it a leap. Shares jumped {m:.0%}.", ["NEUR"], m, 2, "good")]
    return [_press(world, d, "business", "Chip shortage squeezes Neuralis",
                   f"Fewer servers, slower growth. Shares fell {abs(m):.0%}.", ["NEUR"], m, 2, "bad")]


def _ev_rights(world, rng, d, jumps):
    league = rng.choice(LEAGUES)
    if rng.random() < 0.6:
        m = _move(jumps, "PVTV", 0.05, 0.09, rng)
        return [_press(world, d, "business", f"Portavia TV wins the rights to {league}",
                       f"A five-year deal. Shares up {m:.0%}.", ["PVTV"], m, 2, "good")]
    m = _move(jumps, "PVTV", -0.10, -0.05, rng)
    return [_press(world, d, "business", f"Portavia TV loses {league} to a streaming rival",
                   f"Shares fell {abs(m):.0%}.", ["PVTV"], m, 2, "bad")]


def _ev_kit(world, rng, d, jumps):
    if rng.random() < 0.7:
        club = rng.choice(CLUBS_FOR_KIT)
        m = _move(jumps, "STRD", 0.03, 0.06, rng)
        return [_press(world, d, "business", f"Stride Athletics signs a kit deal with {club}",
                       f"Shares rose {m:.0%}.", ["STRD"], m, 1, "good")]
    m = _move(jumps, "STRD", -0.14, -0.07, rng)
    return [_press(world, d, "business", "Fire at Stride Athletics' main factory",
                   f"No one was hurt, but production stops for weeks. Shares fell {abs(m):.0%}.", ["STRD"], m, 2, "bad")]


def _ev_oil(world, rng, d, jumps):
    m = _move(jumps, "sector:energy", 0.04, 0.08, rng)
    a = _move(jumps, "SKYP", -0.09, -0.05, rng)
    world.city.economy = max(-1.0, world.city.economy - 0.05)
    return [_press(world, d, "business", "Oil price spikes on supply fears",
                   f"Voltara up {m:.0%}, SkyPorta down {abs(a):.0%}. Households brace for higher bills.",
                   ["VOLT", "SKYP"], m, 2, "bad")]


def _ev_strike(world, rng, d, jumps):
    m = _move(jumps, "SKYP", -0.12, -0.06, rng)
    return [_press(world, d, "business", "Pilots' strike grounds SkyPorta flights",
                   f"Hundreds of flights cancelled. Shares fell {abs(m):.0%}.", ["SKYP"], m, 2, "bad")]


def _ev_food(world, rng, d, jumps):
    if rng.random() < 0.5:
        m = _move(jumps, "MESA", -0.15, -0.08, rng)
        return [_press(world, d, "business", "Food safety scare at Mesa Foods",
                       f"A product recall across the region. Shares fell {abs(m):.0%}.", ["MESA"], m, 2, "bad")]
    m = _move(jumps, "MESA", 0.03, 0.05, rng)
    return [_press(world, d, "business", "Mesa Foods wins the school meals contract",
                   f"Shares up {m:.0%}.", ["MESA"], m, 1, "good")]


def _ev_bank(world, rng, d, jumps):
    m = _move(jumps, "PBNK", -0.09, -0.05, rng)
    return [_press(world, d, "business", "Banco Portavia issues a profit warning",
                   f"Bad loans pile up. Shares fell {abs(m):.0%}.", ["PBNK"], m, 2, "bad")]


def _ev_jobs(world, rng, d, jumps):
    good = rng.random() < 0.5 + 0.3 * world.city.economy
    world.city.economy = max(-1.0, min(1.0, world.city.economy + (0.08 if good else -0.08)))
    m = rng.uniform(0.005, 0.012) * (1 if good else -1)
    jumps["market"] = jumps.get("market", 0.0) + m
    return [_press(world, d, "business",
                   "Unemployment falls to a five-year low" if good else "Unemployment rises for a third month",
                   "Shops and bars report busier evenings." if good else "Consumers tighten their belts.",
                   [], m, 1, "good" if good else "bad",
                   effect="Consumer confidence " + ("up" if good else "down") + ": subscriber growth follows.")]


def _ev_tourism(world, rng, d, jumps):
    m = _move(jumps, "SKYP", 0.03, 0.05, rng)
    _move(jumps, "MESA", 0.01, 0.03, rng)
    world.city.economy = min(1.0, world.city.economy + 0.04)
    return [_press(world, d, "business", "Tourists flood Portavia: hotels fully booked",
                   f"SkyPorta up {m:.0%}.", ["SKYP", "MESA"], m, 1, "good")]


def _ev_storm(world, rng, d, jumps):
    world.city.economy = max(-1.0, world.city.economy - 0.02)
    return [_press(world, d, "city", "Storm floods the riverside district",
                   "Basements under water, trams suspended. Clean-up could take a week.", importance=2, tone="bad")]


def _ev_blackout(world, rng, d, jumps):
    if d.weekday() < 5:
        _move(jumps, "VOLT", -0.06, -0.03, rng)
    return [_press(world, d, "city", "Blackout hits half of Portavia for three hours",
                   "Voltara blames a substation fault.", ["VOLT"], None, 2, "bad")]


def _ev_tram_strike(world, rng, d, jumps):
    for e in world.active_employees():
        e.psyche.stress = min(0.98, e.psyche.stress + 0.02)
    return [_press(world, d, "city", "Tram strike snarls the morning commute",
                   "Queues at every bus stop.", importance=1, tone="bad",
                   effect="Staff arrive late and flustered (a little more stress).")]


def _ev_festival(world, rng, d, jumps):
    world.city.economy = min(1.0, world.city.economy + 0.02)
    return [_press(world, d, "city", rng.choice(("Summer festival packs the old town",
                                                 "Marathon closes the city centre for the day",
                                                 "Night market returns to the harbour")),
                   "", importance=1, tone="good")]


def _ev_council(world, rng, d, jumps):
    return [_press(world, d, "city", rng.choice(("Council approves a new cycle lane network",
                                                 "Mayor promises cheaper trams by spring",
                                                 "Old Docks warehouses to become flats")),
                   "", importance=1)]


# key, weight, needs a trading day, cooldown days, handler
EVENTS: list[tuple[str, float, bool, int, Any]] = [
    ("tender", 1.0, True, 25, _ev_tender),
    ("ad_ban", 0.025, True, 500, _ev_ad_ban),
    ("ad_ban_lifted", 0.05, True, 30, _ev_ad_ban_lifted),
    ("fixing", 0.35, True, 90, _ev_fixing),
    ("record_weekend", 0.6, True, 30, _ev_record_weekend),
    ("rival_collapse", 0.03, True, 360, _ev_rival_collapse),
    ("data_hike", 0.04, True, 400, _ev_data_hike),
    ("data_outage", 0.3, True, 60, _ev_data_outage),
    ("ai", 0.6, True, 30, _ev_ai),
    ("rights", 0.35, True, 90, _ev_rights),
    ("kit", 0.5, True, 30, _ev_kit),
    ("oil", 0.35, True, 60, _ev_oil),
    ("strike", 0.3, True, 90, _ev_strike),
    ("food", 0.4, True, 45, _ev_food),
    ("bank", 0.25, True, 120, _ev_bank),
    ("jobs", 0.8, True, 25, _ev_jobs),
    ("tourism", 0.35, True, 60, _ev_tourism),
    ("storm", 0.3, False, 40, _ev_storm),
    ("blackout", 0.2, False, 90, _ev_blackout),
    ("tram_strike", 0.25, False, 60, _ev_tram_strike),
    ("festival", 0.6, False, 10, _ev_festival),
    ("council", 0.6, False, 10, _ev_council),
]


# ---------------------------------------------------------------------------------- sports & company
def _sports_items(world: World, since: date, today: date) -> list[PressItem]:
    matches = [m for m in world.matches.values() if m.finished and since <= m.kickoff.date() < today]
    out: list[PressItem] = []
    upset = None
    for m in matches:
        won = next(iter(m.winning_markets() & {"home_win", "away_win"}), None)
        if not won:
            continue
        price = m.best_price(won, "odds_close") or m.best_price(won)
        if price and price[1] >= 4.0 and (upset is None or price[1] > upset[1]):
            upset = (m, price[1], won)
    if upset:
        m, odds, won = upset
        w_id, l_id = (m.home_id, m.away_id) if won == "home_win" else (m.away_id, m.home_id)
        comp = world.competitions.get(m.competition)
        out.append(_press(world, today, "sports",
                          f"Shock in {comp.name if comp else m.competition}: {world.team_name(w_id)} stun "
                          f"{world.team_name(l_id)}",
                          f"{world.match_label(m)} finished {m.home_goals}-{m.away_goals}. "
                          f"Bookmakers had the winners at {odds:.2f}.", importance=2, tone="neutral"))
    goals = max(matches, key=lambda m: m.total_goals, default=None)
    if goals and goals.total_goals >= 6:
        out.append(_press(world, today, "sports", f"Goal-fest: {world.match_label(goals)} ends "
                                                   f"{goals.home_goals}-{goals.away_goals}",
                          "", importance=1, tone="neutral"))
    elif matches:
        out.append(_press(world, today, "sports", f"{len(matches)} match{'es' if len(matches) != 1 else ''} played "
                                                   "across Europe", "Full results inside.", importance=1,
                          kind="roundup"))
    t0 = datetime.combine(since, time(8, 0))
    for n in world.news:
        if t0 <= n.published < datetime.combine(today, time(8, 0)) and (n.kind == "manager_change" or n.severity >= 3):
            out.append(_press(world, today, "sports", n.headline, "", importance=2 if n.kind == "manager_change" else 1))
            if len(out) >= 4:
                break
    return out


_COMPANY_HEADLINES = {
    "fire": "{co} lets {who} go",
    "hire": "{co} hires {who}",
    "resignation": "{who} walks out on {co}",
    "poached": "Rival syndicate poaches {who} from {co}",
    "board_fires_ceo": "Board ousts {co}'s CEO",
    "new_ceo": "New boss at {co}",
    "department_founded": "{co} opens a new desk",
    "department_closed": "{co} shuts a desk",
    "bankruptcy": "{co} collapses",
    "big_win": "{co} tipster lands a big one",
    "salary_cut": "{co} cuts salaries",
    "facility_leased": "{co} expands its offices",
    "season_awards": "{co} hands out its season awards",
}


def _company_items(world: World, since: date) -> list[PressItem]:
    t0 = datetime.combine(since, time(8, 0))
    co = world.config.company_name
    out: list[PressItem] = []
    for ev in world.events:
        if ev.time < t0 or ev.importance < 2 or ev.kind.startswith("city_") or ev.kind == "month_close":
            continue
        who = ", ".join(world.employees[i].name for i in ev.employee_ids[:2] if i in world.employees)
        tpl = _COMPANY_HEADLINES.get(ev.kind)
        headline = tpl.format(co=co, who=who or "a tipster") if tpl else ev.title
        out.append(_press(world, world.today, "company", headline, ev.title if tpl else ev.text[:200],
                          importance=3 if ev.importance >= 3 else 2,
                          tone="good" if ev.tone == "good" else "bad" if ev.tone == "bad" else "neutral"))
    return out[-4:]


# ---------------------------------------------------------------------------------- helpers
def _press(world: World, d: date, section: str, headline: str, body: str = "", tickers: list[str] | None = None,
           move: float | None = None, importance: int = 1, tone: str = "neutral", effect: str = "",
           kind: str = "") -> PressItem:
    return PressItem(id=world.next_id("p"), day=d, section=section, headline=headline, body=body,  # type: ignore[arg-type]
                     tickers=tickers or [], move=None if move is None else round(move, 4), importance=importance,
                     tone=tone, effect=effect, kind=kind)  # type: ignore[arg-type]


def _prune(world: World) -> None:
    city = world.city
    cut = world.today - timedelta(days=PRESS_RETENTION_DAYS)
    city.press = [p for p in city.press if p.day >= cut]
    city.editions = [d for d in city.editions if d >= cut]
    old = world.today.toordinal() - 500
    city.recent_templates = {k: v for k, v in city.recent_templates.items() if v >= old}


def publish_now(world: World, section: str, headline: str, body: str = "", tickers: list[str] | None = None,
                move: float | None = None, importance: int = 2, tone: str = "neutral", effect: str = "") -> PressItem:
    """Breaking news added to today's paper (used by the sandbox tools)."""
    ensure_city(world)
    it = _press(world, world.today, section, headline, body, tickers, move, importance, tone, effect)
    world.city.press.append(it)
    if world.today not in world.city.editions:
        world.city.editions.append(world.today)
    return it


def shock_prices(world: World, sector: str | None, pct: float, ticker: str | None = None) -> None:
    """Move prices right now (sandbox): the latest close is rewritten so every reader sees it at once."""
    ensure_city(world)
    for s in world.city.stocks.values():
        if (ticker and s.ticker == ticker) or (not ticker and (sector is None or s.sector == sector)):
            s.price = round(max(0.5, s.price * (1 + pct)), 2)
            if s.history:
                s.history[-1] = s.price
    city = world.city
    if city.index:
        city.index[-1] = round(1000 * sum(s.price / s.base for s in city.stocks.values()) / len(city.stocks), 1)


# ---------------------------------------------------------------------------------- read model
def edition_view(world: World, day: date | None = None) -> dict[str, Any]:
    city = world.city
    if not city.editions:
        return {"available": False, "paper": city.paper, "city": city.name}
    eds = sorted(city.editions)
    if day is None or day not in eds:  # the latest edition on or before the requested day
        earlier = [d for d in eds if day is None or d <= day]
        day = earlier[-1] if earlier else eds[0]
    i = eds.index(day)
    items = [p for p in city.press if p.day == day]
    items.sort(key=lambda p: (-int(p.lead), -p.importance, -_SECTION_RANK[p.section]))
    k = bisect_left(city.days, day) - 1  # last session before this morning
    stocks = []
    if k >= 0:
        for s in city.stocks.values():
            hist = s.history
            off = len(city.days) - len(hist)
            j = k - off
            if j < 0:
                continue
            prev = hist[j - 1] if j >= 1 else hist[j]
            stocks.append({"ticker": s.ticker, "name": s.name, "sector": s.sector, "price": hist[j],
                           "change": round(hist[j] / prev - 1, 4), "spark": hist[max(0, j - 29): j + 1]})
    index = None
    if k >= 0:
        prev = city.index[k - 1] if k >= 1 else city.index[k]
        index = {"value": city.index[k], "change": round(city.index[k] / prev - 1, 4),
                 "spark": city.index[max(0, k - 59): k + 1]}
    prev_day = eds[i - 1] if i > 0 else day - timedelta(days=1)
    results = sorted((m for m in world.matches.values() if m.finished and prev_day <= m.kickoff.date() < day),
                     key=lambda m: (m.competition, m.kickoff))
    return {
        "available": True, "paper": city.paper, "city": city.name, "day": day.isoformat(),
        "results": [{"competition": m.competition, "home": world.team_name(m.home_id), "away": world.team_name(m.away_id),
                     "score": f"{m.home_goals}-{m.away_goals}"} for m in results[:24]],
        "edition_no": len([d for d in eds if d <= day]), "prev": eds[i - 1].isoformat() if i > 0 else None,
        "next": eds[i + 1].isoformat() if i + 1 < len(eds) else None, "latest": eds[-1].isoformat(),
        "items": [p.model_dump(mode="json") for p in items], "stocks": stocks, "index": index,
        "base_rate": city.base_rate, "economy": round(city.economy, 3),
        "betting_sentiment": round(market.betting_sentiment(world), 3),
        "loan_rate_monthly": round(market.loan_rate_monthly(world), 4),
        "modifiers": market.active_modifiers(world),
    }
