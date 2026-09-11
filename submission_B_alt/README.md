# Submission B (alternative / backup) — multi-file tape-router

Backup for `../submission_B` (the single-file agent). This is the public
**"kaggriculture-structured-economic-policy-v2"** agent: a tape-router that forks its plan on
the town shop-draw (~step 144) and reserves/spreads sells inside 72-turn shop blocks.

## Files (all required — upload together as the tarball)
- `main.py` — entry point; loads `policy.build_agent(settings)`, exposes `agent()`
- `router.py` — plan selection / routing (44 KB)
- `policy.py` — sale-window overlay
- `actions.json` — the recorded plans/tape (~5 MB)
- `settings.json`

## Measured (exact engine, this repo's harness)
- vs `random`: ~173k coins median.
- vs `main_rescue2800.py`: **10/10 wins, avg margin ~+16k** (both seats, 5 seeds).
- Loses head-to-head to `../submission_B` (most-powerfull-route) 0/10, which is why that one is
  the primary and this is the backup.

## Upload
Multi-file — upload the bundled `../submission_B_alt.tar.gz` (main.py at root + the 4 support
files). A bare `main.py` will NOT work; it needs its siblings and `actions.json`.

Provenance: adopted public competitor agent, not original work.
