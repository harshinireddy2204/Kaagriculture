"""Kaggriculture local harness: play a candidate agent against the 29 extracted
ladder opponents under each episode's original seed, and report W/L, margins, and
the winning-signature metrics (herd size, hire spend, premium $/unit).

Usage:
    python run_harness.py <candidate.py> [--seat 0|1|both] [--limit N]

The candidate file must expose a top-level `agent(obs)` (or `agent(obs, config)`).
"""
import argparse
import glob
import importlib.util
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OPP_DIR = os.path.join(HERE, "opponents")

SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
ANIMAL_COST = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
LAND_COST = (1000, 2000, 4000)
PREMIUM = ("STRAWBERRY", "MILK", "WOOL", "MELON")

# Winning signature thresholds derived from the 29 loss replays:
#   blowout losses had <=12 animals; coinflip losses had 13-14; winners ran 16-17.
TARGET_HERD = 15          # animals on the board by day 25
MAX_HIRE_SPEND = 152000   # winners in blowouts hired for ~146k vs our ~160k


def load_agent(path):
    spec = importlib.util.spec_from_file_location("candidate_" + os.path.basename(path).replace(".", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in ("agent", "kaggriculture_agent"):
        if hasattr(mod, name):
            fn = getattr(mod, name)
            return (lambda obs, _fn=fn: _fn(obs))
    raise RuntimeError(f"{path} has no agent()/kaggriculture_agent()")


def _fib(n):
    a, b = 1, 1
    for _ in range(max(0, n)):
        a, b = b, a + b
    return a


def signature(steps, seat):
    """Herd size, hire spend, premium $/unit for one seat across an episode."""
    hire_spend = 0.0
    buyprod = seed = animal = land = 0.0
    prem_units = defaultdict(int)
    prem_value = defaultdict(float)
    max_herd = 0
    for s in steps:
        obs = s[seat]["observation"]
        farm = obs["farms"][seat]
        prices = obs["market"]["prices"]
        ht = int(farm.get("hires_today", 0))
        unlocked = len(farm.get("unlocked_quadrants", []))
        herd = 0
        for row in farm.get("tiles", []):
            for t in row or []:
                if isinstance(t, dict) and t.get("animal"):
                    herd += 1
        max_herd = max(max_herd, herd)
        act = s[seat].get("action") or {}
        priv = obs.get("private", {})
        held = {}
        for o in act.get("market") or []:
            if not o:
                continue
            k = o[0]
            if k == "HIRE":
                hire_spend += _fib(ht)
                ht += 1
            elif k == "BUY_LAND":
                idx = unlocked - 1
                if 0 <= idx < len(LAND_COST):
                    land += LAND_COST[idx]
                    unlocked += 1
            elif k == "BUY_SEED" and len(o) >= 3:
                seed += SEED_COST.get(o[1], 0) * int(o[2])
            elif k == "BUY_ANIMAL" and len(o) >= 3:
                animal += ANIMAL_COST.get(o[1], 0) * int(o[2])
            elif k == "BUY_PRODUCT" and len(o) >= 3:
                buyprod += float(prices.get(o[1], 0)) * int(o[2])
            elif k == "SELL" and len(o) >= 3 and o[1] in PREMIUM:
                g = o[1]
                if g not in held:
                    held[g] = priv.get("shed", {}).get(g, 0) + sum(
                        iv.get(g, 0) for iv in priv.get("inventories", [])
                    )
                n = min(int(o[2]), max(0, held[g]))
                held[g] -= n
                prem_units[g] += n
                prem_value[g] += n * float(prices.get(g, 0))
    prem_ppu = {g: (prem_value[g] / prem_units[g] if prem_units[g] else 0.0) for g in PREMIUM}
    return {
        "max_herd": max_herd,
        "hire_spend": round(hire_spend),
        "buyprod": round(buyprod),
        "prem_units": dict(prem_units),
        "prem_ppu": {g: round(v, 1) for g, v in prem_ppu.items()},
    }


def run(candidate_path, seat_mode="both", limit=None):
    from kaggle_environments import make

    cand = load_agent(candidate_path)
    manifest = json.load(open(os.path.join(OPP_DIR, "_manifest.json")))
    if limit:
        manifest = manifest[:limit]
    results = []
    for m in manifest:
        opp = load_agent(os.path.join(OPP_DIR, m["file"]))
        seats = [0, 1] if seat_mode == "both" else [int(seat_mode)]
        for seat in seats:
            cfg = {"episodeSteps": 720}
            if m.get("seed") is not None:
                cfg["seed"] = m["seed"]
            env = make("kaggriculture", configuration=cfg, debug=False)
            agents = [None, None]
            agents[seat] = cand
            agents[1 - seat] = opp
            env.run(agents)
            rew = [st.reward for st in env.steps[-1]]
            mine, theirs = rew[seat], rew[1 - seat]
            sig = signature(env.steps, seat)
            results.append(
                {
                    "episode": m["episode"],
                    "opponent": m["opponent"],
                    "seat": seat,
                    "mine": mine,
                    "theirs": theirs,
                    "margin": (mine or 0) - (theirs or 0),
                    "orig_margin": m["orig_margin"],
                    "sig": sig,
                }
            )
    return results


def report(results):
    w = sum(1 for r in results if r["margin"] > 0)
    l = sum(1 for r in results if r["margin"] < 0)
    t = len(results) - w - l
    print(f"\n{'episode':<11}{'seat':>4}{'margin':>9}{'orig':>9}{'herd':>5}{'hire$':>8}  opponent")
    for r in sorted(results, key=lambda r: r["margin"]):
        print(
            f"{r['episode']:<11}{r['seat']:>4}{int(r['margin'] or 0):>9}"
            f"{int(r['orig_margin']):>9}{r['sig']['max_herd']:>5}{r['sig']['hire_spend']:>8}"
            f"  {r['opponent']}"
        )
    herd = sum(r["sig"]["max_herd"] for r in results) / max(1, len(results))
    hire = sum(r["sig"]["hire_spend"] for r in results) / max(1, len(results))
    print(f"\nRecord: {w}W {l}L {t}T  ({100*w/max(1,len(results)):.0f}% win)")
    print(f"Avg herd {herd:.1f} (target >= {TARGET_HERD})   avg hire spend {hire:.0f} (target <= {MAX_HIRE_SPEND})")
    flag = []
    if herd < TARGET_HERD:
        flag.append(f"UNDER-BUILT HERD ({herd:.1f} < {TARGET_HERD}) -> expect blowout losses")
    if hire > MAX_HIRE_SPEND:
        flag.append(f"HIRE SPEND TOO HIGH ({hire:.0f} > {MAX_HIRE_SPEND})")
    print("Signature: " + ("; ".join(flag) if flag else "OK - matches winning profile"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("candidate")
    ap.add_argument("--seat", default="both", help="0, 1, or both")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    res = run(args.candidate, args.seat, args.limit)
    report(res)
    out = os.path.join(HERE, "last_run.json")
    json.dump(res, open(out, "w"), indent=2, default=float)
    print(f"\nfull results -> {out}")
