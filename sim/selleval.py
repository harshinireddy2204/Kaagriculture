"""Trustworthy sell-timing evaluation via the EXACT simulator.

Instead of an analytic optimizer (which mis-models the coupling between my own
cumulative sells and future prices), this replays a real game through the verified
game.py, replacing ONLY my SELL orders with a candidate schedule, and reports the
real final-money delta. Any gain here is exact, not estimated.
"""
import copy
import sys
sys.path.insert(0, ".")
from sim.game import from_replay_step
from kaggle_environments.envs.kaggriculture.kaggriculture import PRODUCTS

PREMIUM = ("STRAWBERRY", "MILK", "WOOL", "MELON")


def _run(d, my_seat, transform):
    """Replay d, applying `transform(step, my_action)->my_action` to my market orders."""
    steps = d["steps"]
    g = from_replay_step(d, 0)
    for s in range(1, len(steps)):
        a = [steps[s][0].get("action") or {}, steps[s][1].get("action") or {}]
        my = copy.deepcopy(a[my_seat]) or {}
        my = transform(s, my)
        a[my_seat] = my
        g.step_turn(a[0], a[1])
    return g.farms[my_seat]["money"]


def baseline(d, my_seat):
    return _run(d, my_seat, lambda s, a: a)


def cap_premium_per_turn(d, my_seat, caps):
    """Candidate: cap each premium good's SELL to `caps[g]` units/turn (spread, avoid crash);
    the shed still holds the rest and the tape's own later sells / terminal liquidation clear it."""
    def tf(step, a):
        m = []
        for o in (a.get("market") or []):
            oo = list(o)
            if len(oo) >= 3 and oo[0] == "SELL" and oo[1] in caps:
                oo[2] = min(int(oo[2]), caps[oo[1]])
                if oo[2] <= 0:
                    continue
            m.append(oo)
        a = dict(a); a["market"] = m
        return a
    return _run(d, my_seat, tf)


def sell_all_end(d, my_seat, from_step=690):
    """Candidate: suppress premium sells until near the end, then dump (tests hold-vs-spread)."""
    def tf(step, a):
        if step >= from_step:
            return a
        m = [list(o) for o in (a.get("market") or []) if not (len(o) >= 3 and o[0] == "SELL" and o[1] in PREMIUM)]
        a = dict(a); a["market"] = m
        return a
    return _run(d, my_seat, tf)
