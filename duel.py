"""Faithful head-to-head: candidate vs the current champion (baseline_fscore_cad).

Both sides are real, fully-guarded agents, so neither desyncs -- this is the one
local test that does NOT lie. A change that reliably beats the current champion
across many seeds and both seats is a real improvement worth submitting.

It still doesn't PROVE a ladder gain (opponents there aren't fscore_cad), but it
is a sound "not worse, and adds value vs a strong reference" gate, paired with a
signature/crash check.

Usage:
    python duel.py <candidate.py> [--champ baseline_fscore_cad.py] [--seeds N]
"""
import argparse
import importlib.util
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))


def load(path):
    spec = importlib.util.spec_from_file_location("ag_" + os.path.basename(path).replace(".", "_"), path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    for n in ("agent", "kaggriculture_agent"):
        if hasattr(m, n):
            return getattr(m, n)
    raise RuntimeError(f"{path}: no agent()")


def run(cand_path, champ_path, seeds):
    from kaggle_environments import make

    cand = load(cand_path)
    champ = load(champ_path)
    margins = []
    for sd in range(1, seeds + 1):
        for seat in (0, 1):
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": sd}, debug=False)
            ags = [None, None]
            ags[seat] = cand
            ags[1 - seat] = champ
            env.run(ags)
            rew = [s.reward for s in env.steps[-1]]
            mine, theirs = rew[seat], rew[1 - seat]
            if mine is None or theirs is None:
                continue
            margins.append(mine - theirs)
    return margins


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--champ", default=os.path.join(HERE, "baseline_fscore_cad.py"))
    ap.add_argument("--seeds", type=int, default=6)
    args = ap.parse_args()
    m = run(args.candidate, args.champ, args.seeds)
    n = len(m)
    wins = sum(1 for x in m if x > 0)
    print(f"\n{os.path.basename(args.candidate)}  vs  {os.path.basename(args.champ)}")
    print(f"  games {n} (both seats, {args.seeds} seeds)")
    print(f"  candidate wins: {wins}/{n} = {100*wins/n:.0f}%")
    print(f"  avg margin: {statistics.mean(m):+.0f}   median {statistics.median(m):+.0f}")
    verdict = "IMPROVEMENT" if wins > n * 0.55 and statistics.mean(m) > 0 else (
        "NO CLEAR GAIN" if wins >= n * 0.45 else "REGRESSION")
    print(f"  verdict: {verdict}")
