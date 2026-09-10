"""Build a submittable, self-contained Kaggriculture agent by cloning ONE seat's
tape from a replay and wrapping it in the minimal set of guards that have ever
helped on this ladder (per Harshini's own log): weed-repair, hand alignment,
terminal liquidation, and a crash-proof fallback.

This is the proven "adopt the newest strong public agent" loop, made repeatable:
point it at the current #1's replay, screen the emitted file with score_replay.py,
then submit.

Usage:
    python build_candidate.py <replay.json> <seat> [-o out_main.py]
"""
import argparse
import base64
import json
import os
import zlib

TEMPLATE = r'''"""Cloned tape agent: {desc}
Herd {herd}, hire ${hire}, margin {margin} in the source game.
Guards: weed-repair (DIG then resume), hand alignment, terminal liquidation, fallback.
"""
import base64
import json
import zlib

_ACTIONS = json.loads(zlib.decompress(base64.b85decode({blob!r})).decode("utf-8"))
_MAX = len(_ACTIONS)
_FINAL_EXEC_STEP = 718
_WEED_REPLAY_STEPS = 8
_PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
_I0 = 10000
# engine 1.32.7 price curve, for revenue-ranked terminal liquidation
_PARAMS = {{
    "WHEAT": (25, 400, "sqrt", 0.80, "log", 0.20), "CARROT": (35, 450, "log", 0.20, "sqrt", 0.70),
    "TOMATO": (60, 200, "linear", 0.40, "sqrt", 0.60), "STRAWBERRY": (120, 100, "sqrt", 0.70, "linear", 1.60),
    "MELON": (250, 300, "log", 0.20, "sq", 3.60), "EGG": (50, 332, "linear", 0.40, "log", 0.20),
    "MILK": (160, 122, "sqrt", 0.60, "linear", 1.60), "WOOL": (200, 105, "log", 0.20, "sq", 3.20),
    "FERTILIZER": (100, 200, "linear", 0.40, "linear", 0.40),
}}
_WEED_STATE = {{0: {{}}, 1: {{}}}}


def _get(v, k, d=None):
    if isinstance(v, dict):
        return v.get(k, d)
    g = getattr(v, "get", None)
    return g(k, d) if callable(g) else getattr(v, k, d)


def _seat(obs):
    return 1 if int(_get(obs, "player", 0) or 0) == 1 else 0


def _farm(obs, seat):
    fs = list(_get(obs, "farms", []) or [])
    return fs[seat] if seat < len(fs) else {{}}


def _copy(a):
    a = a if isinstance(a, dict) else {{}}
    return {{"farmer": list(a.get("farmer") or ["PASS"]),
            "hands": [list(h or ["PASS"]) for h in (a.get("hands") or [])],
            "market": [list(o) for o in (a.get("market") or [])]}}


def _align(a, obs):
    a = _copy(a)
    exp = len(_get(_farm(obs, _seat(obs)), "hands", []) or [])
    h = list(a.get("hands") or [])
    if len(h) < exp:
        h.extend([["PASS"]] * (exp - len(h)))
    a["hands"] = [list(o or ["PASS"]) for o in h[:exp]]
    return a


def _tile(farm, pos):
    try:
        x, y = int(pos[0]), int(pos[1])
        return (_get(farm, "tiles", []) or [])[y][x]
    except Exception:
        return "LOCKED"


def _trace(step, actor):
    t = _ACTIONS[min(max(int(step), 0), _MAX - 1)] or {{}}
    if actor == "farmer":
        return list(t.get("farmer") or ["PASS"])
    hs = t.get("hands", []) or []
    return list(hs[actor] if actor < len(hs) else ["PASS"])


def _weed_repair(obs, action, step):
    action = _align(action, obs)
    seat = _seat(obs)
    g = _WEED_STATE[seat]
    if step == 0 or step < int(g.get("last_step", -1)):
        g = {{"last_step": step, "active": {{}}}}
        _WEED_STATE[seat] = g
    g["last_step"] = step
    farm = _farm(obs, seat)
    positions = [_get(farm, "farmer"), *list(_get(farm, "hands", []) or [])]
    units = [action.get("farmer", ["PASS"]), *list(action.get("hands") or [])]
    active = g.setdefault("active", {{}})
    for actor, tx in list(active.items()):
        idx = 0 if actor == "farmer" else int(actor) + 1
        if idx >= len(units):
            active.pop(actor, None)
            continue
        age = step - int(tx["start"])
        if age == 1:
            units[idx] = list(tx["intended"])
        elif 2 <= age <= 1 + _WEED_REPLAY_STEPS:
            units[idx] = _trace(step - 1, actor)
        else:
            active.pop(actor, None)
    for idx, (pos, intended) in enumerate(zip(positions, units)):
        actor = "farmer" if idx == 0 else idx - 1
        if actor in active or not isinstance(intended, list) or not intended:
            continue
        if intended[0] not in ("BUILD_PASTURE", "BUILD_COOP", "PLANT"):
            continue
        t = _tile(farm, pos)
        if not isinstance(t, dict) or t.get("kind") != "WEED":
            continue
        active[actor] = {{"start": step, "intended": list(intended)}}
        units[idx] = ["DIG"]
    action["farmer"] = units[0] if units else ["PASS"]
    action["hands"] = units[1:]
    return _align(action, obs)


def _shape(f, v, s):
    import math
    v = max(0.0, v)
    return {{"linear": v, "sq": v * v, "sqrt": math.sqrt(v), "log": math.log1p(v)}}.get(f, v)


def _price(item, inv):
    base, sc, bf, bt, af, at = _PARAMS[item]
    if inv < _I0:
        amp = bt * base / _shape(bf, sc, sc)
        val = base + amp * _shape(bf, _I0 - inv, sc)
    else:
        amp = at * base / _shape(af, sc, sc)
        val = base - amp * _shape(af, inv - _I0, sc)
    return max(1, round(val))


def _terminal_liquidation(obs, action):
    """Step 718: sell every shed product (unsold scores $0), best-revenue first."""
    seat = _seat(obs)
    priv = _get(obs, "private", {{}}) or {{}}
    shed = dict(_get(priv, "shed", {{}}) or {{}})
    market = _get(obs, "market", {{}}) or {{}}
    inv = _get(market, "inventory", {{}}) or {{}}
    action = _copy(action)
    already = {{}}
    for o in action.get("market") or []:
        if len(o) >= 3 and o[0] == "SELL":
            already[o[1]] = already.get(o[1], 0) + max(0, int(o[2] or 0))
    cands = []
    for item in _PRODUCTS:
        qty = max(0, int(shed.get(item, 0) or 0) - already.get(item, 0))
        if qty <= 0:
            continue
        base_inv = int(_get(inv, item, _I0) or _I0)
        rev = sum(_price(item, base_inv + k) for k in range(qty))
        cands.append((rev, item, qty))
    cands.sort(reverse=True)
    for _, item, qty in cands:
        mk = [list(o) for o in (action.get("market") or [])]
        ex = next((o for o in mk if len(o) >= 3 and o[0] == "SELL" and o[1] == item), None)
        if ex is not None:
            ex[2] = max(0, int(ex[2])) + qty
        elif len(mk) < 10:
            mk.append(["SELL", item, qty])
        else:
            continue
        action["market"] = mk[:10]
    return action


def agent(obs, config=None):
    try:
        fb = int(_get(obs, "day", 0) or 0) * 24 + int(_get(obs, "hour", 0) or 0)
        raw = _get(obs, "step", None)
        step = min(max(0, int(raw if raw is not None else fb)), _MAX - 1)
        action = _copy(_ACTIONS[step])
        action = _weed_repair(obs, action, step)
        if step == _FINAL_EXEC_STEP:
            action = _terminal_liquidation(obs, action)
        return _align(action, obs)
    except Exception:
        farm = _farm(obs, _seat(obs))
        return {{"farmer": ["PASS"],
                "hands": [["PASS"] for _ in (_get(farm, "hands", []) or [])],
                "market": []}}
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("replay")
    ap.add_argument("seat", type=int)
    ap.add_argument("-o", "--out", default=None)
    args = ap.parse_args()
    d = json.load(open(args.replay, encoding="utf-8"))
    seat = args.seat
    info = d.get("info", {})
    names = [a.get("Name", "") for a in info.get("Agents", [])]
    steps = d["steps"]
    tape = [
        (s[seat].get("action") or {"farmer": ["PASS"], "hands": [], "market": []})
        for s in steps
    ]
    rew = d.get("rewards") or [p.get("reward") for p in steps[-1]]

    # signature for the header
    import score_replay
    sig = score_replay.score_seat(steps, seat)

    blob = base64.b85encode(zlib.compress(json.dumps(tape).encode("utf-8"), 9))
    ep = os.path.basename(args.replay)[:-5]
    desc = f"{names[seat]} seat {seat}, episode {ep} vs {names[1-seat]}"
    src = TEMPLATE.format(
        desc=desc,
        herd=sig["max_herd"],
        hire=sig["hire"],
        margin=int(rew[seat] - rew[1 - seat]),
        blob=blob,
    )
    out = args.out or f"candidate_{names[seat].split()[0].lower()}_{ep}_main.py"
    open(out, "w", encoding="utf-8").write(src)
    print(f"wrote {out}")
    print(f"  source: {desc}")
    print(f"  herd {sig['max_herd']}  hire ${sig['hire']}  margin {int(rew[seat]-rew[1-seat])}")
    print(f"  size: {os.path.getsize(out)/1024:.0f} KB")


if __name__ == "__main__":
    main()
