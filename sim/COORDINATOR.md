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
- Herd now builds to ~13 and holds; coins ~6,600 (consistent) — vs the animal-meta
  tapes' ~100k. Functional and stable, but still far from competitive.

## The bottlenecks to crack next (in order)
1. ~~Feeding reliability~~ — SOLVED (see above).
2. **Herd-build timing / throughput** — the herd doesn't start until ~day 16 and only
   reaches 13, so it produces little milk. Pastures build late (workers busy planting
   crops) and animals are bought/placed slowly. Need earlier structure-building and a
   faster, wheat-secured ramp so the herd is large and producing by mid-game.
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
