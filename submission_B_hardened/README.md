# Submission B — HARDENED (replay-informed variant)

`main.py` = the guarded **moreyield champion** + three replay-informed changes, validated to
beat everything else we have in faithful head-to-head:

1. **R42 cash-safe opening** — day-0 wheat wash shrunk 13+30 → 8, plus a turn-17 melon guard that
   protects the feed-critical wheat seeds.
2. **R36 per-item sale preemption** — reserve/sell MILK 12 turns early, STRAWBERRY/WOOL 8 turns
   (base tape sells on a 2–4 turn horizon). In a shared market, selling *before* the opponent
   captures the higher price. **This is the driver.**
3. **R54 third-shop cow/sheep conversion** — narrow (rarely fires); near-neutral on its own.

The EXP-173H action-contract guard is still the outermost wrapper (safe fallback verified).

## Measured (faithful live head-to-head, mirror baseline = 0.0)
- vs **moreyield champion**: **52W / 0L / 0D** (mean +2,428 / +2,629), worst game still +428.
- vs **master-engine-v2**: **24W / 0L / 0D**, mean +3,438.
- vs **v35 (2562)**: **24W / 0L / 0D**, mean +3,552.
- vs random: 16W/0/0, ~162k (as strong as champion — no economy sacrificed).
- **100 head-to-head games vs 3 different tapes → 100 wins, zero draws.**

## Why it should climb (and kill the draws)
The ladder is full of the base moreyield/master public tape — that's what causes the exact-tie
**draws** (mirror matchups). This variant front-runs those clones on the shared market, converting
draw → win. It's the first hand-authored change this session to survive the faithful testbed that
killed all prior attempts (which *deferred* sells; this one *advances* them — opposite direction).

## Caveat
Local dominance is necessary but not final — the live ladder (adaptive/unknown opponents) is the
real arbiter. This is the best-evidenced candidate we've had (faithful testbed, 3 distinct tapes,
sound market mechanism), so it's worth a **live trial in the weak slot** while the proven 2673
champion holds the other slot.

## Rollout
- Keep **submission_B (moreyield, 2673)** in one slot (safety).
- Put **this** in the other slot (replacing the weaker one). If the rating rises, promote it.

Single file — upload `main.py` (or `../submission_B_hardened.tar.gz`). Rename download to `main.py`.
Provenance: derived from adopted public tapes + user-supplied replay-informed edits; not original work.
