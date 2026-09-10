"""Replay-faithful harness: play a candidate against each real loss-replay
opponent UNDER THAT EPISODE'S ORIGINAL SEED AND CONFIG, so the opponent's tape
reproduces its own farm/weeds and plays at (near) full strength.

The target to beat is the opponent's ACTUAL ladder coin count. If the candidate,
on the same seed, out-scores what the opponent really scored, that's a strong
"you would have won this game" signal.

Calibration: run fscore_cad first. It should LOSE most of these (they are its
real losses). If it wins most locally, the harness is not faithful -> do not
trust it.

Usage:
    python harness_replay.py <candidate.py> [--limit N]
    python build: (auto-builds _loss_manifest.json from Downloads on first run)
"""
import argparse
import glob
import importlib.util
import json
import os

DOWNLOADS = r"C:\Users\harsh\Downloads"
HERE = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(HERE, "_loss_manifest.json")

SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}


def _my_seat(info):
    for i, a in enumerate(info.get("Agents", [])):
        if "harshini" in (a.get("Name", "") or "").lower():
            return i
    return None


def _fib(n):
    a, b = 1, 1
    for _ in range(max(0, n)):
        a, b = b, a + b
    return a


def _hire_spend(steps, seat):
    tot = 0
    for s in steps:
        farm = s[seat]["observation"]["farms"][seat]
        ht = int(farm.get("hires_today", 0))
        for o in (s[seat].get("action") or {}).get("market") or []:
            if o and o[0] == "HIRE":
                tot += _fib(ht); ht += 1
    return tot


def build_manifest():
    """Collect fscore_cad losses (hire>120k separates them from the clone)."""
    files = sorted(glob.glob(os.path.join(DOWNLOADS, "10[567]*.json")))
    out = []
    for f in files:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        info = d.get("info", {})
        seat = _my_seat(info)
        if seat is None:
            continue
        opp = 1 - seat
        rew = d.get("rewards") or []
        if len(rew) < 2 or rew[seat] >= rew[opp]:
            continue  # losses only
        if _hire_spend(d["steps"], seat) <= 120000:
            continue  # skip clone games
        out.append(
            {
                "file": f,
                "episode": os.path.basename(f)[:-5],
                "my_seat": seat,
                "opp_seat": opp,
                "opp_name": info["Agents"][opp]["Name"],
                "seed": info.get("seed"),
                "config": d.get("configuration"),
                "opp_orig_coins": rew[opp],
                "my_orig_coins": rew[seat],
            }
        )
    json.dump(out, open(MANIFEST, "w"), indent=2)
    return out


def load_agent(path):
    spec = importlib.util.spec_from_file_location("ag_" + os.path.basename(path).replace(".", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for n in ("agent", "kaggriculture_agent"):
        if hasattr(mod, n):
            return getattr(mod, n)
    raise RuntimeError(f"{path}: no agent()")


def opp_tape_agent(file, opp_seat):
    d = json.load(open(file, encoding="utf-8"))
    tape = [(s[opp_seat].get("action") or {"farmer": ["PASS"], "hands": [], "market": []}) for s in d["steps"]]

    def a(obs, config=None):
        s = int(obs.get("step", 0) or 0)
        return tape[s] if s < len(tape) else {"farmer": ["PASS"], "hands": [], "market": []}
    return a


def run(candidate_path, limit=None):
    from kaggle_environments import make

    manifest = json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else build_manifest()
    if limit:
        manifest = manifest[:limit]
    cand = load_agent(candidate_path)
    rows = []
    for m in manifest:
        opp = opp_tape_agent(m["file"], m["opp_seat"])
        cfg = dict(m.get("config") or {})
        cfg["seed"] = m.get("seed")
        cfg.setdefault("episodeSteps", 720)
        env = make("kaggriculture", configuration=cfg, debug=False)
        ags = [None, None]
        ags[m["my_seat"]] = cand
        ags[m["opp_seat"]] = opp
        env.run(ags)
        rew = [s.reward for s in env.steps[-1]]
        mine = rew[m["my_seat"]] or 0
        opp_sim = rew[m["opp_seat"]] or 0
        rows.append(
            {
                "episode": m["episode"],
                "opp": m["opp_name"],
                "mine": mine,
                "opp_sim": opp_sim,
                "opp_orig": m["opp_orig_coins"],
                "beat_sim": mine > opp_sim,
                "beat_orig": mine > m["opp_orig_coins"],
                "opp_fidelity": (opp_sim / m["opp_orig_coins"]) if m["opp_orig_coins"] else 0,
            }
        )
    return rows


def report(rows, label):
    n = len(rows)
    bs = sum(r["beat_sim"] for r in rows)
    bo = sum(r["beat_orig"] for r in rows)
    fid = sum(r["opp_fidelity"] for r in rows) / max(1, n)
    print(f"\n[{label}]  {n} replay opponents")
    print(f"  beat opponent's SIM score : {bs}/{n} = {100*bs/n:.0f}%")
    print(f"  beat opponent's REAL score: {bo}/{n} = {100*bo/n:.0f}%   <- the honest 'would have won' rate")
    print(f"  opponent fidelity (sim/real coins): {fid:.2f}  (1.00 = opponent reproduced exactly)")
    worst = sorted(rows, key=lambda r: r["mine"] - r["opp_orig"])[:6]
    print("  biggest losses vs real score:")
    for r in worst:
        print(f"    {r['episode']} {r['opp'][:22]:<22} me {int(r['mine']):>7} vs real {int(r['opp_orig']):>7} (fid {r['opp_fidelity']:.2f})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args()
    if args.rebuild or not os.path.exists(MANIFEST):
        print("building loss manifest...", len(build_manifest()), "fscore_cad losses")
    rows = run(args.candidate, args.limit)
    report(rows, os.path.basename(args.candidate))
    json.dump(rows, open(os.path.join(HERE, "replay_" + os.path.basename(args.candidate) + ".json"), "w"), indent=2, default=float)
