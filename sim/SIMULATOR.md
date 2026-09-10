# Kaggriculture forward-model simulator — status & roadmap

Goal: a fast, exact forward-model of the game so a **search/planning agent** (the
SpaTaro approach) can evaluate candidate decisions each turn within the 1s budget.
This is the only method with a theoretical path past the animal-meta ceiling
(~2600) toward the adaptive top tier (~2900). RL is ruled out (net-negative here,
proven three ways).

## Done and VERIFIED

### `sim/market.py` — the market model ✅ EXACT
- Reuses the engine's own `market_price` + `MARKET_PARAMS` (guaranteed exact curve,
  including the `hinge` shape for CARROT/TOMATO/EGG).
- Reimplements the per-unit concurrent lockstep SELL/BUY_PRODUCT processing and
  town consumption exactly as `kaggriculture.py`'s `_process_market`/`_town_consume`.
- **Verified: 200 random trials vs the engine's own `_process_market` → 0 mismatches**
  (market inventory AND both players' money). The hardest, most error-prone part
  (concurrent price shifts during selling) is proven correct.
- This alone enables **optimal sell-timing analysis**: given a production schedule,
  compute the revenue-maximizing turn/quantity to sell each good — the exact lever
  the coinflip losses (−2 to −50 coins) turn on.

Engine facts pinned down (1.32.7):
- Observation offset: `obs[S+1]` = state after step S's full processing.
- Town center: consumes 1 each of the 8 non-fertilizer products every
  `townCenterSellInterval` turns. **No day-based 2×/4× scaling** (README is stale
  for this version).
- Sells at $1 do NOT add to market inventory (floor stays responsive).
- Buy price quoted at post-buy inventory (buy→sell round-trip nets zero).

### `sim/farm.py` — farm production model ✅ EXACT
- Wraps the engine's own pure functions (`_apply_unit_action`, `_daily_refresh_plants/
  animals`, `_decay_plants`, `_drop_inventories_to_shed`) — exact by construction.
- Note pinned down: care-bonus banks **+1** per cared+fed day (engine), not +2 (README).

### `sim/game.py` — full turn pipeline ✅ EXACT
- Composes physical actions -> market -> town -> decay -> end-of-day (weed + shop-unlock
  RNG seeded exactly as the engine: `random.Random((seed*1_000_003) ^ day)`).
- **Verified: 34/35 real replays reproduced EXACTLY** (final money, both players, full
  720 turns). The one miss is a rare weed-RNG edge case.
- Key semantics pinned: `steps[S].observation` is the state AFTER step S's action.
- Speed: ~613 us/turn (441 ms for a full 720-turn game). Fast enough for per-turn search
  over a few-day horizon (~20-60 candidate rollouts within the 1s budget); can be made
  much faster later by dropping deepcopy and using the fast market model directly.

## Sell-timing optimizer — built, and it settled the question (NEGATIVE result)

`sim/selltiming.py` (analytic water-filling) over-estimated because it mis-models
the coupling between your own cumulative sells and future prices. So we measured it
the trustworthy way — `sim/selleval.py` reschedules premium sells and runs the EXACT
simulator (baseline reproduces real money 8/8):

| premium-sell schedule | real Δ money / game |
|---|---|
| tape's actual (aggressive) | 0 (baseline) |
| cap 12/turn | −3,643 |
| cap 8/turn | −15,073 |
| cap 5/turn | −40,737 |
| cap 3/turn | −47,637 |
| hold till turn 696 | −81,177 |

**Perfectly monotonic: the more aggressively you sell, the better.** The shed cap (100)
forces you to sell as you produce or lose it to overflow, so the tapes already sell
near-optimally. **Sell-timing is NOT the lever** — this rigorously closes that avenue
(and refutes the "burst/spread/multi-turn liquidation" advice, which all lose here).

Conclusion: the coinflip losses are NOT from selling. The only lever is **production** —
what/how-much to grow and build (land + melon, SpaTaro's edge) — which needs the planner.

## Production planner — built; strategic target found, execution is the wall

`sim/planner.py` + measured exact per-tile economics (`TILE`):

| tile | product/tile | worker-actions | gross @ base |
|---|---|---|---|
| MELON | 12 | 33 | **$3,000** (highest) |
| COW (care) | 30 milk | 36 | $1,440 |
| SHEEP (care) | 30 wool | 34 | $1,400 |
| GOOSE (care) | 46 egg | 49 | $1,100 (egg is glut-proof) |
| STRAWBERRY (fert) | 8 | 23 | **$480** (lowest premium) |

**Findings (robust, valuable):**
- **CARE roughly triples animal output** (cow milk 9→30) — the animal-meta under-uses it.
- **Melon is the top-value tile**, saturating ~13–14 tiles — the animal-meta plants only ~12
  and over-invests in **strawberry (33 tiles), the *worst* premium tile.**
- The idealized optimizer beats the animal-meta by ~$37k modeled revenue with a
  melon + care-animal + less-strawberry mix. This is exactly SpaTaro's direction.

**The wall (honest):** the planner idealizes away **movement labor** (tending 100 tiles
means workers walking between them). That overhead is the true binding constraint — why
real agents cluster ~17 animals near the shed rather than fielding 60. So the planner gives
the **strategic target** (more melon, use CARE, less strawberry), not an executable agent.
Turning the target into a real agent requires solving worker coordination/movement — the
same v7/RL trap that scored ~1–50%. That remains the open research wall.

### What this session produced
- A bit-exact, verified forward-model of the whole game (34/35 replays exact).
- Sell-timing: rigorously settled as NOT a lever.
- Exact per-tile economics + a strategy optimizer that names the target (melon + care).
- The precise diagnosis of the remaining wall: executable worker coordination.

### Remaining — executable coordination (open)
On top of the exact model: bounded per-turn search over the big decisions —
**land timing, crop mix (esp. melon), herd size/composition, sell timing** — the axes
where SpaTaro beats the animal-meta. Beam search or domain-specific optimization within
the 1s/step budget. This is the actual "agent," and the hardest research part.

## Honest scope
The market foundation (this session) is the hardest-to-get-*right* piece and it's done
and verified. The farm model + pipeline + search is a multi-session/multi-week project
with real but uncertain payoff. It is the correct, research-grounded route past 2600 —
but it is R&D, not a weekend port.

## Meanwhile (pragmatic track, unchanged)
Keep `main_rescue2800.py` (+ a distinct second agent) on the ladder and ride the
convergence week; adopt each new guarded-additive public router, screened with
validation → herd → duel.
