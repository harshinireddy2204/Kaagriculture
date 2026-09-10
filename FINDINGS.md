# Kaggriculture — findings, tools, and playbook

Consolidated record of what we established building up from rating 429 → 2442.
Read this before the next attempt so we don't re-learn the same walls.

---

## 1. Current best agents

| agent | file | ladder | notes |
|---|---|---|---|
| **6-block router** | `router_main_submit.py` | **~2442–2538** | adaptive tape router; herd 17; occasionally desyncs (herd 6–8 → −50k/−74k games) |
| **shop-router 0908** | `main_srouter_fixed.py` | (submit to test) | robust: herd 16–17, **never desyncs**; 2 switch points; fixes the disaster games |
| fscore_cad | (v31) | ~1719 | single fixed tape; the old baseline |

**Active-pair recommendation:** 6-block router + shop-router. Two strong, robust
agents; let the ladder decide which is better. Never run the overlay versions
(below) — they test worse.

---

## 2. Hard-won facts (what is TRUE)

- **Fixed single tape caps ~1719.** It can't adapt to shop/market variation across seeds.
- **Tape *routers* reach 2442–2538.** They carry several *compatible* tapes and
  switch between them on public state at safe day-boundaries. Compatibility is the
  key: the tapes must share early structure (same seeds, land timing, hire pattern)
  and diverge only in animal composition / late selling — otherwise switching desyncs.
- **The ladder is the ONLY faithful judge of rank.** Proven repeatedly.
- **A candidate's own herd across seeds IS reliable** (opponent-independent) — use
  it as a robustness gate.
- **`env.run(["main.py","main.py"])` is Kaggle's real validation.** Always run it
  before submitting — it catches loader bugs a plain `import` misses (see §5).

## 3. Hard-won facts (what does NOT work — do not retry)

- **Overlays on a strong router HURT on the ladder** (2538 → 1772). The routers
  already sell adaptively; our feed-protect / liquidation / contested-ordering
  rules override their tuned judgment against the real field. (Overlays *did* help
  the weaker fscore_cad tape in duels: +314 → +5,740 — but that gain did NOT
  transfer to the ladder either; v9 ≈ 1696 ≈ fscore_cad.)
- **Cloning top players fails.** Mengfei / Olympus are ADAPTIVE (their recorded
  actions are responses to a specific game), so replaying their tape collapses the
  herd to ~12 and scores ~⅓. The 569 submission was one of these.
- **From-scratch reactive agents fail** (~1% of tape output — the "v7 trap").
  Coordinating feed logistics + build pipeline + harvest timing + selling reactively
  is far less efficient than a pre-choreographed tape.
- **Synthesizing new compositions by token-substitution desyncs** (COW↔SHEEP swaps
  break feed/harvest choreography → herd drops to 8). Only the tape author's
  hand-built variants are safe.
- **"Lean labor" is a myth (measurement bug).** Everyone — you and the 2800 tier —
  spends ~$4–8k on hires. Hiring is cheap; it is NOT a differentiator.

## 4. What the 2800 tier actually does (corrected)

On the measurable axes, **your router is already on par**: hire ~$5k, herd ~14–17,
land days [6,11]. The real differences are subtle and mostly un-actionable for us:

- **SpaTaro**: variable, aggressive — buys land days 0–4, scales herd up to ~21–24
  when the economy allows. Higher variance, higher ceiling.
- **Mengfei**: fixed herd-17, disciplined land [6,11], but **adapts composition
  widely** (0C3S3G … 12C4S) to shop demand — cows for dairy shops, sheep for Yarn
  Store, geese for bakery. This is the one real edge we could not replicate
  (substitution desyncs; we can't hand-build compatible variants).
- **The decisive gap is per-turn selling / market timing baked into their tapes** —
  which we cannot rewrite better than they did.

**Bottom line:** 2442 is the practical ceiling of the public-tape approach for us.
Reaching 2800 needs either better tapes (can't generate) or adaptive execution that
doesn't desync (proven too hard here).

## 5. The loader gotcha (why a submission Error'd)

Kaggle loads the agent as `[v for v in namespace.values() if callable(v)][-1]` — the
**last callable defined**. If you inline code that defines its own `agent`, then
redefine `agent` later, Python keeps the reassigned key in its ORIGINAL position, so
the genuinely-last callable may be some other class/function → wrong agent called →
crash. Fix: make sure your real `agent` is the last fresh definition (a trailing
`_final = agent; def agent(o,c=None): return _final(o,c)` wrapper guarantees it).

---

## 6. Tools (all in this folder)

| tool | what it does | trust for rank? |
|---|---|---|
| `score_replay.py` | herd / hire / $-per-unit of any replay (`--dir` a folder) | YES (own actions) |
| `duel.py` | candidate vs champion head-to-head, both real agents | partial — no false-negatives on gross regressions, but a duel WIN can still lose on the ladder (overlays did) |
| `build_candidate.py` | clone one seat's tape into a guarded main.py | — |
| `harness_replay.py` / `harness_ab.py` | replay-opponent scoring | **NO** — opponents desync to ~54%, do not trust for rank |
| `extract_opponents.py` + `opponents/` | 29 real ladder opponents as fixed bots | sparring only |

**Correct hire-spend calc** (score_replay's `hire` field is buggy — 14× inflated;
use daily-reset fib):
```python
def hire_spend(steps, seat):
    spend=0; last=-1; today=0
    def fib(n):
        a,b=1,1
        for _ in range(max(0,n)): a,b=b,a+b
        return a
    for s in steps:
        day=s[seat]["observation"]["day"]
        if day!=last: today=0; last=day
        for o in (s[seat].get("action") or {}).get("market") or []:
            if o and o[0]=="HIRE": spend+=fib(today); today+=1
    return spend
```

---

## 7. The loop that works (429 → 2442, and onward)

1. **Find a strong PUBLIC agent** (notebook/tape) — routers beat single tapes.
2. **Screen it** before submitting:
   - `env.run(["main.py","main.py"])` — passes Kaggle validation (no loader crash)?
   - herd across ~10 seeds — robust (never collapses)?
   - fast (<1s/step; routers are ~0ms)?
3. **Submit**, keeping your current best as the other active agent.
4. **Analyze the new loss replays** (`score_replay.py --dir`) — but remember the gap
   is now subtle selling, not herd/labor.
5. **Repeat.** Adopt-and-screen is the only loop that has ever raised the number.

**Do NOT:** write overlays for a strong router, clone adaptive players, or build a
reactive agent from scratch. All three test worse — measured, repeatedly.
