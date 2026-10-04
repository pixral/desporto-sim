# Decision log

Short records of choices made while building, so they can be revisited deliberately.

| # | Decision | Alternatives | Why |
|---|---|---|---|
| 1 | Python + FastAPI backend | ASP.NET Core | Faster iteration; pydantic gives structured-output validation; mature Anthropic SDK; native WebSockets. |
| 2 | One in-memory `World` aggregate, saved as a compressed JSON snapshot | Fully normalised tables updated per tick | Fast-forwarding needs in-memory state; snapshots make save/load exact (RNG states included). The AI call log is a real table because it is large and queried. |
| 3 | Pydantic models double as domain objects | Separate domain + DTO layers | Less boilerplate for a simulation whose state *is* the save file. Read models for the UI are still separate (`simulation/views.py`). |
| 4 | 4 discrete phases per day | Hourly ticks, event queue | Enough for the decision rhythm, easy to animate, deterministic. |
| 5 | Separate RNG streams for sports and agents | One RNG | Same seed ⇒ same football under any CEO: fair comparisons and replays. |
| 6 | Mock AI consumes the same structured context as the prompt | Hand-written fake text | Mock and LLM decide from identical information; tests are deterministic and free. |
| 7 | One tipster call per day (all matches) | One call per match | ~5× fewer calls/tokens; the agent can budget its bets across the slate. |
| 8 | Strategies are explicit parameter sets | Free-form "LLM picks" | Backtestable, mutable by the LAB, deployable by the CEO; hidden talent lives in parameters. |
| 9 | Bookmakers rate teams from results; xG gives analysts an informational edge | Books peeking at true form | The first design made every analyst lose; this one creates real, contestable, drifting edges (calibrated with probes). |
| 10 | Stakes in units of the CEO's stake limit | Pure Kelly | Kelly on noisy model edges produced absurd stakes; units make the CEO's limits a real lever. |
| 11 | Subscription revenue tied to track record | Betting-only revenue | With realistic edges, betting alone cannot pay a 10-person company; subscriptions give reputation and marketing an economic role. |
| 12 | Costs accrue daily, paid monthly | Daily payment | Payday drama and "couldn't make payroll" as a bankruptcy trigger, while runway stays smooth. |
| 13 | Hand-written canvas renderer, procedural sprites | Game engine, sprite sheets | Original visual identity, no asset licensing, small bundle. |
| 14 | Low internal partition walls, tall outer walls only | Full walls | Everything stays visible in an isometric view without cutaway logic. |
| 15 | Client-side walking adapts to phase length | Fixed walking speed | At high speeds people would never reach their desks. |
| 16 | Claude default `claude-opus-5-5`, configurable per purpose | Hard-coded cheap model | Cost is the user's call; per-purpose overrides make a cheaper tipster model a one-line change. |
| 17 | LAB holdout (last 4 months out-of-sample) before DEPLOY | In-sample only | A real run showed many "deploy" strategies losing live: selection bias from trying many ideas. |
| 18 | CEO rebuild mode, upgrade swaps, career-level firing evidence | 90-day stats only | A real run showed a shrunken company that never hired again and kept a −10% tipster for 360 bets. |
| 19 | Strategy cooldown, deploy only to losing tipsters, one deploy per person per review | Unrestricted deploys | The same tipster received two strategies in one review (the second overwrote the first) and strategies churned monthly. |
| 20 | Near-flat "unit" staking with mild conviction; no smaller stakes for longshots | Stakes scaled strongly by perceived edge, longshots shrunk | Batch analysis: stake-weighted ROI was worse than flat ROI in nearly every seed (the biggest stakes landed on the noisiest bets); near-flat staking raised median company value after 500 days from €10.7k to €17.7k. |
| 21 | Difficulty presets (capital, cost level, subscribers, bookmaker sharpness) | One fixed economy | Lets players pick a relaxed or brutal game; the football stays identical per seed so runs remain comparable. |
| 22 | Calibrate with ≥16 seeds per CEO style | 6 seeds | Small changes cascade into different hires and decisions; 6-seed medians swung by ±€5k between near-identical builds. |
| 23 | The city runs on its own RNG stream and reaches the company only through `economy/market.py` | Mixing news into agent RNG; news as flavour text only | Same seed still gives the same football and the same city; every effect of a headline is in one auditable place, so the paper never shows a story whose consequence is fake. |
| 24 | Bookmaker share prices scale only the subscriber goodwill in the valuation (×0.75–1.25 vs. a 120-day average) | Scale the whole valuation; ignore markets | Comparable-company pricing is how real valuations move with a sector, and it changes value (and board pressure) without touching cash. |
| 25 | Office space as three fixed east-wing lots with fit-out + monthly cost, monthly reviews only | Free-form building; repurposing desk rooms | Gives visible growth on the map without a level editor, keeps the 6 original desk rooms intact, and makes expansion a real cost decision. |
| 26 | Sandbox interventions go through the normal books, the history and the end screen | Hidden cheat menu | Testing tools should not corrupt the record: investor money is equity, disasters are one-off costs, and a sandboxed run says so. |
| 27 | Staff go home at night (client-side) and meetings include desk leads | Overnight lounging; CEO meeting alone | Playtest feedback: an empty meeting room with a lone CEO and a full lounge at midnight read as bugs. |
| 28 | Value milestones measured from the value at founding | From starting capital | Subscriber goodwill already puts the founding value ~20 % above capital, so "+25 %" fired on day one. |
