# Submission B — single-file tape-router

`main.py` is a self-contained (stdlib-only, no external files) Kaggriculture agent, adopted
from the public notebook **"most-powerfull-route" / "kaggriculture-v35-reactive-sales-sheep-
expansion"** (the two are byte-identical). It embeds its plan data compressed in-file
(base64+zlib) and exposes `agent(observation, configuration=None)` as the last callable, with a
safe fallback that returns a valid dict on a malformed/empty observation.

## Measured (exact engine, this repo's harness)
- vs `random`: ~150–161k coins median.
- vs `main_rescue2800.py` (our current 2418 ladder agent): **16/16 wins, avg margin +89,542**
  (both seats, 8 seeds).
- Beats the alternative multi-file tape-router (structured-economic-policy) 10/10 head-to-head.

## Role
Intended as **active submission B**, paired with **A = main_rescue2800.py**. Kaggle scores the
better of two active submissions, so B is the stronger primary and A is the safe fallback.

## Upload
Single file: upload `main.py` directly, or the bundled `../submission_B.tar.gz` (contains
`main.py` at root). Validate in an interactive session before making it active.

Provenance: public competitor notebook; not original work. Adopted per the two-submission
hedge strategy (same approach used for rescue2800 / shoprouter0909).
