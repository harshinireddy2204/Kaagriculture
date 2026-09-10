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

## The remaining gap to the tapes (~100k)
Still ~44k vs `random` — roughly half the animal-meta tapes. Coverage tops out around
NW+NE (~35 tiles); SW/SE are unlocked (~day 21) but barely worked. Candidate next levers:
faster early build-out (reach full farm before ~day 15, not ~day 18), higher worker cap /
better labor throughput to actually work SW/SE, CARE bonus exploitation, and market
sell-price management (dynamic prices crash under volume). Zone-based routing was tried and
*hurt* (workers forced to distant empty tiles) — reverted; labor is not yet the binding
constraint, build-out speed and mix are.

## How to iterate (the loop is set up)
`scratchpad/bench_coord.py` runs the agent vs `random` across seeds and reports coins +
per-quadrant coverage; `sweep*.py` vary the strategy mix. Measure every change on >=8 seeds.
