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
- **Feeding reliability: SOLVED.** Herd trajectory is monotonic (0 deaths) — once an
  animal is placed it never starves. Root cause was economic, not coordination: the
  shed ran out of wheat and the agent was too broke to buy more. Fixed by making
  feed-wheat the top spending priority (6-day buffer early, down to a tiny cash
  floor), skipping the doomed pre-income herd (no animals until ~day 6), and phasing
  the herd build so it never outruns the wheat supply.
- Herd/crop production now works: coins ~20,000 (median), a 3x jump from the first
  stable ~6,600. Strategy sweep found the optimum is 4cow/2sheep/6goose/22melon/
  4straw/14wheat — MELON + glut-proof EGGS, less strawberry/animals, exactly the
  planner's finding. Still below the animal-meta tapes' ~100k (this is vs `random`).

## The bottlenecks to crack next (in order)
1. ~~Feeding reliability~~ — SOLVED (see above).
2. ~~Herd-build timing~~ — FIXED. Root causes were (a) wheat crops assigned to LOCKED
   outer quadrants so no early feed (deadlock), fixed by an INTERLEAVED layout that puts
   a balanced wheat/animal/melon mix on the unlocked NW tiles; (b) the animal-heavy mix
   itself — a melon+egg mix earns far more per tile. Coins 6.6k -> 20k.
3. **Labor routing / throughput (the scale wall, now the binding constraint)** —
   even with ~12 workers the agent works only ~16 tiles (NW+NE); SW/SE sit empty and
   even NW/NE are half-filled. Coins rose 20k->~26k just by hiring more, but the wall
   is movement: workers spawn at the shed and the per-turn Hungarian re-plans every
   step with NO multi-turn routes, so they zigzag and never service distant tiles.
   The tapes work 50+ tiles via pre-optimized routes. Fixing this needs committed
   multi-turn worker routes (a worker services several nearby tiles per shed trip),
   not per-turn greedy assignment. This is the deep remaining problem.
3. **Labor throughput / movement** — tending N animals + M crops requires ~N+M daily
   visits; with ~9 workers and Manhattan movement, the schedule saturates. The
   Hungarian minimizes per-turn distance but there's no multi-turn route planning.
3. **Economy pacing** — balance building the herd vs funding it from crop/animal
   income (melons don't pay until ~day 10). Currently over- or under-spends.

## How to iterate (the loop is set up)
Measure any change on the exact engine: run `coordinator.agent` vs an opponent,
score herd (via `score_replay.score_seat`) and final coins. Target intermediate
milestone: **herd 15 that SURVIVES + coins > 50k** (matching the animal-meta) before
attempting the melon/care superior strategy the planner identified.

Honest scope: this is the multi-week research problem. v1 establishes the
architecture + a measured baseline; it is not yet a submittable agent.
