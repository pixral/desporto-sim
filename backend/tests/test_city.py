"""The city: market, morning paper, and how the news reaches the company."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from app.domain.city import CityState, Modifier
from app.economy import accounting, market
from app.economy import valuation as val
from app.simulation import city


def test_market_exists_from_founding_with_history(fresh):
    world, _, _ = fresh()
    c = world.city
    assert len(c.stocks) == len(city.LISTINGS)
    assert len(c.days) == city.WARMUP_DAYS and all(d < world.today for d in c.days)
    assert all(len(s.history) == len(c.days) for s in c.stocks.values())
    assert market.betting_sentiment(world) > 0


def test_city_is_deterministic_and_independent_of_the_agents(fresh):
    a, _, ea = fresh(seed=9)
    b, _, eb = fresh(seed=9)
    b.employees[next(iter(b.employees))].psyche.stress = 0.9  # agents differ, the city must not
    asyncio.run(ea.run_days(20))
    asyncio.run(eb.run_days(20))
    assert a.city.index == b.city.index
    assert [p.headline for p in a.city.press if p.section in ("business", "city")] == \
           [p.headline for p in b.city.press if p.section in ("business", "city")]


def test_one_edition_per_morning_and_morning_is_idempotent(fresh):
    world, _, engine = fresh()
    asyncio.run(engine.run_days(10))
    eds = world.city.editions
    assert len(eds) == len(set(eds)) == 10
    before = len(world.city.press)
    assert city.morning(world) == []  # already printed today
    assert len(world.city.press) == before
    leads = [p for p in world.city.press if p.lead]
    assert len(leads) == len(eds)


def test_edition_view_has_markets_results_and_navigation(fresh):
    world, _, engine = fresh()
    asyncio.run(engine.run_days(12))
    ed = city.edition_view(world)
    assert ed["available"] and ed["day"] == world.today.isoformat()
    assert ed["next"] is None and ed["prev"] is not None
    assert len(ed["stocks"]) == len(city.LISTINGS) and ed["index"]["value"] > 0
    assert any(i["lead"] for i in ed["items"])
    older = city.edition_view(world, world.today - timedelta(days=5))
    assert older["day"] == (world.today - timedelta(days=5)).isoformat()
    assert older["next"] is not None


def test_ad_ban_cuts_subscriber_growth(fresh):
    world, _, _ = fresh()
    world.city.economy = 0.0
    world.finances.subscribers = 100
    snapshot = world.model_copy(deep=True)
    gained_free, _, _ = accounting.subscriptions_update(world)
    snapshot.city.modifiers.append(Modifier(kind="ad_ban", value=0.7, since=snapshot.today,
                                            until=snapshot.today + timedelta(days=90), label="ban"))
    gained_ban, _, _ = accounting.subscriptions_update(snapshot)
    assert gained_ban < gained_free


def test_data_price_hike_raises_the_data_bill(fresh):
    world, _, _ = fresh()
    before = val.estimated_operating_cost(world)
    world.city.modifiers.append(Modifier(kind="data_prices", value=1.25, since=world.today,
                                         until=world.today + timedelta(days=30), label="hike"))
    assert val.estimated_operating_cost(world) > before


def test_betting_shares_move_the_valuation(fresh):
    world, _, _ = fresh()
    base = val.valuation(world)
    city.shock_prices(world, "betting", -0.3)
    assert market.betting_sentiment(world) < 1.0
    assert val.valuation(world) < base


def test_rates_drive_the_credit_line(fresh):
    world, _, _ = fresh()
    world.city.base_rate = 3.0
    normal = market.loan_rate_monthly(world)
    world.city.base_rate = 4.2
    assert market.loan_rate_monthly(world) > normal


def test_old_saves_get_a_city_on_the_next_morning(fresh):
    world, _, engine = fresh()
    world.city = CityState()  # a save from before the city existed
    asyncio.run(engine.run_days(2))
    assert world.city.stocks and world.city.editions


def test_construction_stories_come_back(fresh):
    world, _, _ = fresh()
    c = world.city
    city.ensure_city(world)
    rng = city._rng(world)
    d = world.today
    while d.weekday() >= 5:
        d += timedelta(days=1)
    city._ev_tender(world, rng, d, {})
    story = c.stories[-1]
    jumps: dict[str, float] = {}
    out = city._story_outcome(world, rng, story.due, story, jumps)
    assert out and "BRKH" in jumps and out[0].tickers == ["BRKH"]
