# Coordination solver — status (v1 baseline, WORK IN PROGRESS)

`sim/coordinator.py` — a from-scratch agent that executes a target farm strategy by
assigning the worker fleet to tasks each turn via **optimal (Hungarian) matching**,
with committed multi-turn supply chains. This is the attempt at the one open wall:
turning a good *strategy* into an *executable* agent (the path to SpaTaro's ~2900).

## Architecture (working)
- **Strategy**: fixed tile layout (animals ringed near the shed for short feed walks,
  quadrant-unlock-aware; crops fill the rest) + herd targets + land schedule.
- **Task generation** each turn: FEED / WATER / HARVEST / CARE / COLLECT_FERTILIZER /
  BUILD / PLACE / PLANT / DIG, from the live board vs the target.
- **Assignment**: committed animal-placement pipeline (fetch→walk→place) and committed
  feeding (carry a wheat stack, feed a route), then `scipy` Hungarian on the rest.
- **Economy**: conservative — feed-wheat first, one animal at a time with a cash
  reserve, crop seeds early, modest hiring.

## Where it stands (measured on the exact engine vs `random`)
- **~26k -> ~48k median (10 seeds: median 48.1k, min 44.7k, max 51.3k).** The jump came
  from fixing how the engine actually PAYS OUT, not from the coordination layer.
- Coverage: NW+NE worked in full (~40 tiles), SW barely (2-3), SE=0. The layout only
  TARGETS ~51 tiles (NW+NE+part of SW); extending it into SW/SE is the next scale lever.
- **Feeding reliability: SOLVED.** Once placed, an animal never starves. Feed-wheat is a
  top spending priority; the herd build is phased so it never outruns wheat supply.
- **Best strategy = LIGHT herd + melon focus: 2cow/1sheep/3goose/32melon/2straw/12wheat.**
  A heavy herd (4/2/6) actually scores *worse* (~26k) — 12 animals need ~48 tend-tasks/day
  and steal labor from melons (crops 37->26). Pure crops with zero animals is also worse
  (~28k): a few animals help, but melons dominate per tile. Exactly the planner's finding.

## Bugs found & fixed (the real levers — all engine-mechanics, not routing)
1. ~~Feeding reliability~~ — SOLVED.
2. ~~Herd-build timing~~ — FIXED (interleaved NW layout + phased build).
3. **HARVEST-on-immature-crops (the big one: ~26k -> ~46k).** Non-ongoing crops
   (WHEAT/CARROT/MELON) get `yield_units=1` the instant they're PLANTED, but can't be
   harvested until age >= `first_yield_day` (MELON=10 days), and their yield GROWS via
   daily WATER between age 6-12 up to 6 units. The old task-gen fired a HARVEST task the
   moment `yield_units>0`, so workers CAMPED on immature melons issuing ~4000 no-op
   HARVESTs/game (banked only 88 melon!). Fix: `_crop_ready()` gates harvest on maturity
   (non-ongoing: wait for full growth). This freed the whole fleet -> crops 11->37.
4. **Herd over-buy / stuck-animal deadlock.** An animal *carried* by a worker was invisible
   to both the shed and board counts -> a spurious extra buy -> a 5th cow with no empty
   pasture, stuck forever, and the `pending==0` gate then froze all buying. Fix: count
   placed+shed+carried per kind; never buy a kind past target.
5. **Wheat over-buy pinned cash at ~$50.** We grow ~20 wheat/day (herd needs ~12) yet also
   BOUGHT wheat every turn down to a $60 floor, flooding the shed with low-value wheat that
   crashed its sale price. Fix: buying is an emergency backstop only, with a real reserve.
6. **No end-game logic.** After ~day 27 stop all capital spend (animals/land/new crops that
   can't mature) and liquidate — BUT keep re-hiring the crew daily (hands are cleared every
   night), or there's nobody to harvest the final days.

7. **COLLECT_FERTILIZER emitted as ["COLLECT"] (~48k -> ~57k).** `_do()` returned
   `kind.split("_")[0]` = "COLLECT", not the real op "COLLECT_FERTILIZER" — so ~650
   collects/game were no-ops and we banked ZERO fertilizer (a sellable good, market
   base 100). Emit the full op name (like BUILD_COOP). Median 48.1k -> 56.9k.

## What the top-3000 replays actually do (analyzed 82 games, winners 130k-183k)
Extracted every winner's full fingerprint (`scratchpad/replay_fingerprint.py`). The recipe,
consistent across "feel the agi", "ymg_aq", "SpaTaro":
- **STRAWBERRY is the dominant crop, not melon** (22-42 straw tiles; melon minor/zero).
  Strawberry is ONGOING (plant once, harvest every 2 days all game) so PLANT is only ~180-240
  actions/game — almost no replant labor, which is what frees the fleet to tend a big herd.
- **Big cow+sheep herd: 15-36 animals** (milk + wool + FERTILIZER byproduct). They sell 7-9
  DIFFERENT goods each game, so no single good's dynamic price crashes (base prices: melon
  250, wool 200, milk 160, straw 120, fert 100, egg 50, wheat 25).
- **Full 3-quadrant board (75 tiles worked)**, land unlocked FAST (quad 2 ~day 5, quad 3
  ~day 7-11). ~13-14 workers. FERTILIZE used (98-206x) for 2x crop yield. Sell aggressively.

Applying the diversification insight (mixed melon+strawberry, herd 7) lifted us 57k -> 61k.
But the big-herd/big-farm recipe itself does NOT work in this agent (tested: herd 16 straw =
~5k coins) — see below.

## The remaining gap to the champion — and the coordinator's ceiling
Measured honestly: **coordinator ~61k vs `random`** (mixed melon+straw, herd 7);
**rescue2800 ~122k vs random**, and the top-3000 replay winners hit **130k-183k**. Head-to-head
the coordinator still loses 0/12 (avg margin ~-116k, improved from -129k).

WHY, precisely (measured, not guessed):
- Same banked VOLUME (~1200 units/game each) but rescue earns ~2.2x per unit: it runs an
  ANIMAL-HEAVY farm (17 animals) whose milk/wool/eggs + FERTILIZER byproduct are far more
  valuable than our melon/wheat mix, and its tapes tend that herd on pre-optimized routes.
- Our agent CANNOT copy that: a herd-size sweep (with fertilizer fixed) is monotonic the
  WRONG way — herd 7 = 56k, 10 = 38k, 12 = 23k, 17 = 0.3k. A big herd starves everything
  because per-turn Hungarian assignment can't feed+care+harvest+collect 17 animals AND tend
  crops; and the fib HIRE cost (paid daily — hands clear nightly) hard-caps the fleet ~13.
- CONFIRMED with strawberry too: a big farm (herd 16, 34 straw) builds fully (3 quads, 44
  crops) but nets ~5k — 13 greedy workers can't HARVEST it (only 121 straw banked from 34
  tiles vs the tapes' ~300), so tiles produce and cap out unharvested, and daily re-hire +
  price-crashing dumps eat the little income. Same wall regardless of crop.
- So within this architecture the optimum is the LIGHT-herd (7) diversified mix (~61k).

**Committed-circuit router (BUILT).** Replaced the per-turn Hungarian with `_route`/`_worker_cmd`:
each worker OWNS a persistent spatial cluster (`_clusters`, serpentine chunks) and loops
shed->sweep cluster (feed/water/harvest/care/collect, accumulating produce)->shed drop. Result:
- It DID break part of the wall — a herd-12 farm went 23k (Hungarian) -> 57k (router).
- But it did NOT raise the overall ceiling: herd-7 still ~62k, and big herds (17+) still crash
  (strawberry banked 73/34 tiles; cash pinned) because 13 workers still can't fully service a
  75-tile + big-herd farm even on circuits. A herd-size sweep stays monotonic-wrong.
- Diagnostics at the ceiling: workers PASS ~17% (spare labor) yet adding crops past ~58 tiles
  overloads and drops coins -> the true limit is per-worker throughput, and the tapes simply
  get ~2x more useful actions per worker.

**FERTILIZE pipeline (BUILT).** Workers now apply collected fertilizer to ONGOING crops
(strawberry) with spare capacity -> +2/production when watered = double harvest. Restricted to
strawberry (melon caps via watering anyway). Lifted the mixed config 58.5k -> 62k.

Current best config: 3cow/1sheep/3goose/15melon/15straw/12wheat, herd 7, ~62k vs random.
Still ~half the top-3000 replays (130k-183k) and loses to rescue2800. The remaining gap is
raw per-worker throughput; the next real levers are opponent/town/market ADAPTATION (relative
score) rather than more absolute coins. **rescue2800 stays the submitted ladder agent.**

## How to iterate (the loop is set up)
`scratchpad/bench_coord.py` runs the agent vs `random` across seeds and reports coins +
per-quadrant coverage; `sweep*.py` vary the strategy mix. Measure every change on >=8 seeds.
