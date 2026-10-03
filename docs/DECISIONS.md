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
