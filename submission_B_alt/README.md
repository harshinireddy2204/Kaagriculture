# Submission B — ALT (master-engine-v2)

`main.py` is the public **"master-engine-v2"** agent: single-file, **stdlib-only**,
self-contained, last callable `agent()` with a dict safe-fallback. Second-strongest of the set.

## Measured
- vs `random`: ~170k median.
- vs previous live **v35**: 12/12 wins, +1,973.
- Loses to the PRIMARY `../submission_B` (moreyield) 16/16 (−1,272), so it's the backup / a
  strategically-different second slot.

## Role
Backup for the primary, or the eventual replacement for the v35 slot once moreyield is proven
live. Single-file — upload `main.py` (or `../submission_B_alt.tar.gz`).

Provenance: adopted public competitor agent, not original work.
(Previous multi-file structured-economic-policy alt was retired — this single-file agent is
stronger and simpler to submit.)
