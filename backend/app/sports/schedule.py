"""Fixture calendar generation for the mock world (round robins, kick-off slots, UCL format)."""

from __future__ import annotations

import random
from datetime import date, datetime, time, timedelta

# International breaks (no domestic league football) as (month, day) windows.
_BREAKS = (((9, 3), (9, 9)), ((10, 8), (10, 14)), ((11, 12), (11, 18)), ((3, 24), (3, 30)))
_WINTER = {"BL1": ((12, 22), (1, 9)), "LL": ((12, 24), (1, 2)), "SA": ((12, 24), (1, 2))}
_SEASON_START = {"PL": (8, 15), "LL": (8, 15), "BL1": (8, 22), "SA": (8, 22)}

# (day offset from Saturday anchor, kick-off "HH:MM")
_WEEKEND_SLOTS = {
    "BL1": [(-1, "20:30"), (0, "15:30"), (0, "15:30"), (0, "15:30"), (0, "15:30"), (0, "15:30"),
            (0, "18:30"), (1, "15:30"), (1, "17:30")],
    "PL": [(0, "12:30"), (0, "15:00"), (0, "15:00"), (0, "15:00"), (0, "15:00"), (0, "15:00"),
           (0, "17:30"), (1, "14:00"), (1, "14:00"), (1, "16:30")],
    "LL": [(-1, "21:00"), (0, "14:00"), (0, "16:15"), (0, "18:30"), (0, "21:00"), (1, "14:00"),
           (1, "16:15"), (1, "18:30"), (1, "21:00"), (2, "21:00")],
    "SA": [(-1, "20:45"), (0, "15:00"), (0, "18:00"), (0, "20:45"), (1, "12:30"), (1, "15:00"),
           (1, "15:00"), (1, "18:00"), (1, "20:45"), (2, "20:45")],
}
_MIDWEEK_TIMES = ("19:00", "19:30", "20:00", "20:30", "21:00")


def _hm(text: str) -> time:
    h, m = text.split(":")
    return time(int(h), int(m))


def _in_window(d: date, window: tuple[tuple[int, int], tuple[int, int]]) -> bool:
    (m1, d1), (m2, d2) = window
    key = (d.month, d.day)
    if (m1, d1) <= (m2, d2):
        return (m1, d1) <= key <= (m2, d2)
    return key >= (m1, d1) or key <= (m2, d2)  # wraps over new year


def first_weekday_on_or_after(d: date, weekday: int) -> date:
    return d + timedelta(days=(weekday - d.weekday()) % 7)


def double_round_robin(team_ids: list[str], rng: random.Random) -> list[list[tuple[str, str]]]:
    """Circle method. Returns rounds of (home, away); second half mirrors the first."""
    teams: list[str | None] = list(team_ids)
    rng.shuffle(teams)
    if len(teams) % 2:
        teams.append(None)
    n = len(teams)
    fixed, rot = teams[0], teams[1:]
    first_half: list[list[tuple[str, str]]] = []
    for r in range(n - 1):
        order = [fixed] + rot
        pairs: list[tuple[str, str]] = []
        for i in range(n // 2):
            a, b = order[i], order[n - 1 - i]
            if a is None or b is None:
                continue
            pairs.append((a, b) if (r + i) % 2 == 0 else (b, a))
        first_half.append(pairs)
        rot = [rot[-1]] + rot[:-1]
    second_half = [[(b, a) for a, b in rnd] for rnd in first_half]
    return first_half + second_half


def _evenly_pick(items: list[date], k: int) -> list[date]:
    if k <= 0:
        return []
    if k >= len(items):
        return list(items)
    if k == 1:
        return [items[len(items) // 2]]
    return [items[round(i * (len(items) - 1) / (k - 1))] for i in range(k)]


def ucl_league_dates(year: int) -> list[date]:
    """Tuesdays of the eight league-phase matchdays (Wednesday is the second night)."""
    anchors = [(year, 9, 15), (year, 9, 29), (year, 10, 20), (year, 11, 3), (year, 11, 24),
               (year, 12, 8), (year + 1, 1, 19), (year + 1, 1, 26)]
    return [first_weekday_on_or_after(date(*a), 1) for a in anchors]


def ucl_knockout_dates(year: int, stage: str) -> list[date]:
    if stage == "final":
        return [first_weekday_on_or_after(date(year + 1, 5, 29), 5)]
    anchors = {"r16": [(3, 3), (3, 10)], "qf": [(4, 6), (4, 13)], "sf": [(4, 27), (5, 4)]}[stage]
    return [first_weekday_on_or_after(date(year + 1, m, d), 1) for m, d in anchors]


def league_anchor_dates(comp: str, year: int, n_rounds: int, blocked: set[date]) -> list[date]:
    """Saturday anchors (plus midweek Wednesdays when needed) for each league round."""
    start = first_weekday_on_or_after(date(year, *_SEASON_START[comp]), 5)
    end = date(year + 1, 5, 24)
    winter = _WINTER.get(comp)
    sats: list[date] = []
    d = start
    while d <= end:
        if not any(_in_window(d, w) for w in _BREAKS) and not (winter and _in_window(d, winter)):
            sats.append(d)
        d += timedelta(days=7)
    if len(sats) >= n_rounds:
        return _evenly_pick(sats, n_rounds)
    need = n_rounds - len(sats)
    weds: list[date] = []
    d = first_weekday_on_or_after(date(year, 10, 1), 2)
    while d <= date(year + 1, 4, 30):
        clash = any(abs((d - b).days) <= 1 for b in blocked)
        if not clash and not any(_in_window(d, w) for w in _BREAKS) and not (winter and _in_window(d, winter)):
            weds.append(d)
        d += timedelta(days=7)
    return sorted(sats + _evenly_pick(weds, need))


def spread_kickoffs(comp: str, anchor: date, pairs: list[tuple[str, str]],
                    rng: random.Random) -> list[tuple[str, str, datetime]]:
    out: list[tuple[str, str, datetime]] = []
    shuffled = list(pairs)
    rng.shuffle(shuffled)
    if anchor.weekday() == 5:  # weekend round
        slots = list(_WEEKEND_SLOTS[comp])
        while len(slots) < len(shuffled):
            slots.append((0, "15:00"))
        for (home, away), (offset, hm) in zip(shuffled, slots):
            out.append((home, away, datetime.combine(anchor + timedelta(days=offset), _hm(hm))))
    else:  # midweek round: Tuesday + Wednesday
        half = len(shuffled) // 2
        for i, (home, away) in enumerate(shuffled):
            day = anchor - timedelta(days=1) if i < half else anchor
            out.append((home, away, datetime.combine(day, _hm(rng.choice(_MIDWEEK_TIMES)))))
    return out


def ucl_league_phase(teams: list[str], rng: random.Random, matchdays: int = 8) -> list[list[tuple[str, str]]]:
    """Eight rounds of random pairings, no repeated opponent, home/away balanced where possible."""
    for _attempt in range(500):
        faced: dict[str, set[str]] = {t: set() for t in teams}
        homes: dict[str, int] = {t: 0 for t in teams}
        rounds: list[list[tuple[str, str]]] = []
        ok = True
        for _md in range(matchdays):
            pool = list(teams)
            rng.shuffle(pool)
            pairs: list[tuple[str, str]] = []
            while pool:
                a = pool.pop()
                partner = next((b for b in pool if b not in faced[a]), None)
                if partner is None:
                    ok = False
                    break
                pool.remove(partner)
                faced[a].add(partner)
                faced[partner].add(a)
                if homes[a] < homes[partner] or (homes[a] == homes[partner] and rng.random() < 0.5):
                    pairs.append((a, partner))
                    homes[a] += 1
                else:
                    pairs.append((partner, a))
                    homes[partner] += 1
            if not ok:
                break
            rounds.append(pairs)
        if ok:
            return rounds
    raise RuntimeError("could not generate a Champions League league phase")
