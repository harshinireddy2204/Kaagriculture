# Submission B — PRIMARY (more-yield-smarter-labor)

`main.py` is the strongest agent we've found: the public **"more-yield-smarter-labor"**
notebook agent. Single-file, **stdlib-only**, self-contained; last callable is
`agent(observation, configuration=None)` with a dict safe-fallback on a malformed observation.

## Measured (exact engine, this repo's harness)
- vs `random`: ~172k median.
- vs our previous live agent **v35** (rating 2562): **12/12 wins, +2,525** avg margin.
- vs `master-engine-v2`: 16/16, +1,272.  vs `rescue2800`: 16/16, +89,725.
- Why it should climb: our live losses were photo-finishes (median ~-2.9k on ~100k totals);
  an agent +2.5k stronger than v35 should flip a large share of them.

## Action-contract guard (ported Sep 12)
`main.py` now ends with the **EXP-173H final submission guard** (from the EXP-173H2 build).
It validates/repairs every unit + market command, clamps to 10 orders, and pads hands to the
real count. It is **behavior-neutral**: guarded-vs-plain moreyield is 0W/0L/16D (mean +0.0,
every game exactly 0 margin), and over a full game it logs `guard_repairs=0` — a pure
pass-through in normal play. Its only job is to fail closed if an overlay ever emits malformed
output on Kaggle's live engine. Pure robustness insurance, no rating cost.

## Rollout (safe)
Two active slots. Recommended:
- Keep the proven **v35 (2562)** — saved at `../submission_B_v35/main.py` — in one slot.
- Put **this (moreyield)** in the other slot (replacing the weak rescue2800/2051). It gets a
  live trial without giving up 2562; if it rates higher it becomes our score, else v35 holds.
- Once moreyield proves out live, swap `../submission_B_alt` (master-engine-v2) in for v35.

## Upload
Single file — upload `main.py` (or `../submission_B.tar.gz`). Rename the download to `main.py`.
Validate on Kaggle's engine + first-callback time before making active.

Provenance: adopted public competitor agent, not original work.
