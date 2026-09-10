"""Score a Kaggriculture replay's winning-signature metrics WITHOUT the engine.

Reads any replay JSON (a real ladder game, or the self-play validation replay
Kaggle generates for a fresh submission) and reports, for each seat:
  - max herd size reached (cows/sheep/geese on the board)
  - total hire spend, feed (BUY_PRODUCT) spend, animal/seed/land spend
  - premium $/unit received (strawberry/milk/wool/melon)
  - end-of-game unsold inventory value (scores zero in this engine)

Then flags the seat against the winning signature derived from 29 loss replays:
blowout losses ran <=12 animals; coinflip losses 13-14; winners 16-17. Winners
also hired LESS and bought more feed off-market.

Usage:
    python score_replay.py <replay.json> [replay2.json ...]
    python score_replay.py --dir C:\\path\\to\\replays        # score a folder
    python score_replay.py --name-substr harshini <files...>  # tag your seat
"""
import argparse
import glob
import json
import os
from collections import defaultdict

SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
ANIMAL_COST = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
LAND_COST = (1000, 2000, 4000)
PREMIUM = ("STRAWBERRY", "MILK", "WOOL", "MELON")

TARGET_HERD = 15
MAX_HIRE_SPEND = 152000


def _fib(n):
    a, b = 1, 1
    for _ in range(max(0, n)):
        a, b = b, a + b
    return a


def score_seat(steps, seat):
    hire = buyprod = seed = animal = land = 0.0
    prem_u = defaultdict(int)
    prem_v = defaultdict(float)
    max_herd = 0
    herd_at = {}
    for s in steps:
        obs = s[seat]["observation"]
        farm = obs["farms"][seat]
        prices = obs["market"]["prices"]
        day = obs.get("day", 0)
        ht = int(farm.get("hires_today", 0))
        unlocked = len(farm.get("unlocked_quadrants", []))
        herd = 0
        for row in farm.get("tiles", []):
            for t in row or []:
                if isinstance(t, dict) and t.get("animal"):
                    herd += 1
        max_herd = max(max_herd, herd)
        herd_at[day] = herd
        act = s[seat].get("action") or {}
        priv = obs.get("private", {})
        held = {}
        for o in act.get("market") or []:
            if not o:
                continue
            k = o[0]
            if k == "HIRE":
                hire += _fib(ht)
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
                prem_u[g] += n
                prem_v[g] += n * float(prices.get(g, 0))
    fobs = steps[-1][seat]["observation"]
    fp = fobs["market"]["prices"]
    fshed = fobs.get("private", {}).get("shed", {})
    unsold = sum(fshed.get(g, 0) * float(fp.get(g, 0)) for g in fp)
    return {
        "max_herd": max_herd,
        "herd_day25": herd_at.get(25, herd_at.get(max(herd_at) if herd_at else 0, 0)),
        "hire": round(hire),
        "buyprod": round(buyprod),
        "animal": round(animal),
        "seed": round(seed),
        "land": round(land),
        "prem_ppu": {g: round(prem_v[g] / prem_u[g], 1) if prem_u[g] else 0.0 for g in PREMIUM},
        "prem_units": dict(prem_u),
        "unsold": round(unsold),
    }


def verdict(sig):
    flags = []
    if sig["max_herd"] < TARGET_HERD:
        flags.append(f"herd {sig['max_herd']}<{TARGET_HERD}")
    if sig["hire"] > MAX_HIRE_SPEND:
        flags.append(f"hire {sig['hire']}>{MAX_HIRE_SPEND}")
    return "OK" if not flags else "WEAK: " + ", ".join(flags)


def name_seat(info, substr):
    if not substr:
        return None
    for i, a in enumerate(info.get("Agents", [])):
        if substr.lower() in (a.get("Name", "") or "").lower():
            return i
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--dir")
    ap.add_argument("--name-substr", default="harshini", help="substring to tag YOUR seat")
    args = ap.parse_args()
    files = list(args.files)
    if args.dir:
        files += sorted(glob.glob(os.path.join(args.dir, "*.json")))
    if not files:
        ap.error("no replay files given")

    agg = {"me": defaultdict(float), "opp": defaultdict(float)}
    n = 0
    print(f"{'episode':<11}{'who':<5}{'herd':>5}{'hire$':>8}{'feed$':>7}{'straw$/u':>9}{'milk$/u':>8}{'wool$/u':>8}  verdict")
    for f in files:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        info = d.get("info", {})
        me = name_seat(info, args.name_substr)
        steps = d["steps"]
        rew = d.get("rewards") or [p.get("reward") for p in steps[-1]]
        seats = [(me, "me"), (1 - me, "opp")] if me is not None else [(0, "p0"), (1, "p1")]
        ep = os.path.basename(f)[:-5]
        for seat, tag in seats:
            sig = score_seat(steps, seat)
            won = "W" if rew[seat] == max(rew) and rew[seat] != min(rew) else ("L" if rew[seat] == min(rew) and rew[seat] != max(rew) else "T")
            print(
                f"{ep:<11}{tag:<5}{sig['max_herd']:>5}{sig['hire']:>8}{sig['buyprod']:>7}"
                f"{sig['prem_ppu']['STRAWBERRY']:>9}{sig['prem_ppu']['MILK']:>8}{sig['prem_ppu']['WOOL']:>8}"
                f"  {won} {verdict(sig)}"
            )
            if tag in ("me", "opp"):
                agg[tag]["herd"] += sig["max_herd"]
                agg[tag]["hire"] += sig["hire"]
                agg[tag]["feed"] += sig["buyprod"]
                n += 0.5
        if me is not None:
            print()
    if n:
        n = int(n)
        print(f"=== averages over {n} games (your seat tagged '{args.name_substr}') ===")
        for tag in ("me", "opp"):
            a = agg[tag]
            print(f"  {tag:<4} herd {a['herd']/n:5.1f}  hire ${a['hire']/n:7.0f}  feed ${a['feed']/n:6.0f}")


if __name__ == "__main__":
    main()
