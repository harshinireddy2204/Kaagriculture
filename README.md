# Kaggriculture harness

Tools built from 29 fscore_cad loss replays + 18 top-leaderboard replays.

## The finding (why fscore_cad sits at ~1719)

| build | herd | hire spend | record in these replays |
|---|---|---|---|
| Mengfei Li (#1, ~2964) | 16.9 | **$67,229** | 12–6 |
| keiz (#2) | 15.0 | $131,873 | |
| **you (fscore_cad)** | **12.3** | **$159,712** | **0–29** |

The gap is **labor efficiency**: Mengfei fields ~5 more animals on <½ your hire
spend. That is a property of the *route/tape*, not the overlay — which is why
every overlay edit (yours and the ones considered here) can't close it.

- Your **9 close losses** (<3000) are dead even on every measurable axis — genuine
  coinflips. Your endgame already liquidates fully (unsold = $0), so there is no
  "sell later" edge to add.
- Your **20 blowout losses** are herd-size losses: you came up at ≤12 animals
  against 16–17-animal opponents.

## Files

- `score_replay.py` — **the reliable one.** Scores any replay's winning signature
  (herd, hire spend, feed spend, premium $/unit) with no engine. Run it on the
  self-play validation replay Kaggle generates for a fresh submission to screen a
  candidate BEFORE it's rated.
  ```
  python score_replay.py --dir C:\Users\harsh\Downloads
  python score_replay.py <one_replay.json>
  ```
- `build_candidate.py` — clone one seat's tape from a replay into a submittable,
  guarded `main.py` (weed-repair + terminal liquidation + crash-proof fallback).
  This is the "adopt the current #1" loop made repeatable.
  ```
  python build_candidate.py <replay.json> <seat> -o out_main.py
  ```
- `mengfei_106106170_main.py` — **the candidate.** Mengfei Li's +15,471 win over
  keiz (herd 17, hire $60,891), wrapped in the guards. Submittable as-is.
- `run_harness.py` — plays a candidate vs the 29 extracted opponents locally.
  **APPROXIMATE**: local weed-spawn RNG does not reproduce the ladder's, so fixed
  tapes desync and results are directional, not exact. Use for smoke-testing, not
  for deciding.
- `extract_opponents.py` / `opponents/` — the 29 real ladder opponents as fixed bots.

## How to use this to move the number

1. `python build_candidate.py <newest strong replay> <seat>` — clone it.
2. Submit the emitted `main.py`.
3. Download the validation self-play replay, run `score_replay.py` on it, confirm
   herd ≥ 15 and hire ≤ ~152k survived the wrapping.
4. Let the ladder rate it (the only truthful judge — local win-rate lies).

Chasing 2800+ means adopting a route that already has Mengfei's efficient
signature; it cannot be produced by editing fscore_cad's overlay.
