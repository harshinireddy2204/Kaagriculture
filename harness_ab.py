"""Local A/B harness: play a candidate agent against the 29 extracted ladder
opponents across several seeds and both seats, with a train/holdout split.

IMPORTANT — this is an APPROXIMATE signal, not the ladder. Local weed-spawn RNG
does not reproduce the ladder's, and the extracted opponents are fixed tapes with
no weed-repair, so they desync under fresh seeds and tend to under-perform. Use
this for RELATIVE A/B (does change X beat baseline on the same seeds?), never for
absolute rating claims. Decide on the HOLDOUT split, not the train split.

Usage:
    python harness_ab.py <candidate.py> [--seeds N] [--limit K] [--label NAME]
    python harness_ab.py <cand.py> --vs <baseline.py>   # head-to-head A/B summary
"""
import argparse
import glob
import importlib.util
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
OPP_DIR = os.path.join(HERE, "opponents")
TRAIN = 20   # first 20 opponents = train, last 9 = holdout (matches 20/9 loss split)


def load_agent(path):
    spec = importlib.util.spec_from_file_location(
        "ag_" + os.path.basename(path).replace(".", "_"), path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in ("agent", "kaggriculture_agent"):
        if hasattr(mod, name):
            return getattr(mod, name)
    raise RuntimeError(f"{path}: no agent()")


def opponents(limit=None):
    files = sorted(glob.glob(os.path.join(OPP_DIR, "opp_*.py")))
    return files[:limit] if limit else files


def play(candidate, opp_path, seeds, seat_both=True):
    from kaggle_environments import make

    opp = load_agent(opp_path)
    margins = []
    seats = (0, 1) if seat_both else (0,)
    for sd in seeds:
        for seat in seats:
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": sd}, debug=False)
            ags = [None, None]
            ags[seat] = candidate
            ags[1 - seat] = opp
            env.run(ags)
            rew = [s.reward for s in env.steps[-1]]
            mine, theirs = rew[seat], rew[1 - seat]
            if mine is None or theirs is None:
                continue
            margins.append(mine - theirs)
    return margins


def evaluate(cand_path, seeds, limit=None, seat_both=True):
    cand = load_agent(cand_path)
    opps = opponents(limit)
    rows = []
    for i, op in enumerate(opps):
        m = play(cand, op, seeds, seat_both)
        rows.append(
            {
                "opp": os.path.basename(op),
                "split": "train" if i < TRAIN else "holdout",
                "avg_margin": statistics.mean(m) if m else 0.0,
                "winrate": (sum(1 for x in m if x > 0) / len(m)) if m else 0.0,
                "n": len(m),
            }
        )
    return rows


def summarize(rows, label):
    for split in ("train", "holdout"):
        sub = [r for r in rows if r["split"] == split]
        if not sub:
            continue
        am = statistics.mean(r["avg_margin"] for r in sub)
        wr = statistics.mean(r["winrate"] for r in sub)
        print(f"  [{label}] {split:<8} avg_margin {am:>9.0f}   winrate {100*wr:5.1f}%   ({len(sub)} opps)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--vs", default=None, help="baseline to compare against")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--label", default=None)
    args = ap.parse_args()
    seeds = list(range(1, args.seeds + 1))

    print(f"seeds={seeds}  opponents={args.limit or len(opponents())}  both_seats=True\n")
    rows = evaluate(args.candidate, seeds, args.limit)
    lab = args.label or os.path.basename(args.candidate)
    summarize(rows, lab)
    json.dump(rows, open(os.path.join(HERE, "ab_" + lab + ".json"), "w"), indent=2, default=float)

    if args.vs:
        base_rows = evaluate(args.vs, seeds, args.limit)
        print()
        summarize(base_rows, os.path.basename(args.vs))
        # per-opponent delta on holdout
        bm = {r["opp"]: r["avg_margin"] for r in base_rows}
        print("\n  HOLDOUT per-opponent delta (candidate - baseline):")
        for r in rows:
            if r["split"] != "holdout":
                continue
            d = r["avg_margin"] - bm.get(r["opp"], 0)
            flag = "  <-- improved" if d > 0 else ("  <-- regressed" if d < 0 else "")
            print(f"    {r['opp']:<40} {d:>+9.0f}{flag}")


if __name__ == "__main__":
    main()
