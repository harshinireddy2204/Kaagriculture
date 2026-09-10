"""Candidate v1: fscore_cad backbone + contested-value SELL-slot ordering.

Wraps the proven baseline and reorders ONLY the SELL orders among their own
slot positions, so the good whose price would fall most under concurrent
opponent selling is sold first. Non-SELL orders (buys/hire/land) keep their
positions, so buy/sell funding interleaving is untouched and nothing desyncs.

This is v5's _assign_sell_slots idea grafted onto the cad tape via a pure
market-layer post-pass.
"""
import math
import importlib.util
import os

_BASE_PATH = os.path.join(os.path.dirname(__file__), "baseline_fscore_cad.py")
_spec = importlib.util.spec_from_file_location("cad_base", _BASE_PATH)
_BASE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_BASE)

I0 = 10000
# engine 1.32.7 price curve
PARAMS = {
    "WHEAT": (25, 400, "sqrt", 0.80, "log", 0.20),
    "CARROT": (35, 450, "log", 0.20, "sqrt", 0.70),
    "TOMATO": (60, 200, "linear", 0.40, "sqrt", 0.60),
    "STRAWBERRY": (120, 100, "sqrt", 0.70, "linear", 1.60),
    "MELON": (250, 300, "log", 0.20, "sq", 3.60),
    "EGG": (50, 332, "linear", 0.40, "log", 0.20),
    "MILK": (160, 122, "sqrt", 0.60, "linear", 1.60),
    "WOOL": (200, 105, "log", 0.20, "sq", 3.20),
    "FERTILIZER": (100, 200, "linear", 0.40, "linear", 0.40),
}
PRODUCTS = tuple(PARAMS)


def _shape(f, v, s):
    v = max(0.0, v)
    return {"linear": v, "sq": v * v, "sqrt": math.sqrt(v), "log": math.log1p(v)}.get(f, v)


def _price(item, inv):
    base, sc, bf, bt, af, at = PARAMS[item]
    if inv < I0:
        amp = bt * base / _shape(bf, sc, sc)
        val = base + amp * _shape(bf, I0 - inv, sc)
    else:
        amp = at * base / _shape(af, sc, sc)
        val = base - amp * _shape(af, inv - I0, sc)
    return max(1, round(val))


def _contested_value(item, inv, qty):
    """How much the price would fall against you if the rival dumped `qty` too."""
    qty = max(1, min(int(qty), 60))
    first = sum(_price(item, inv + k) for k in range(qty))
    second = sum(_price(item, inv + qty + k) for k in range(qty))
    return float(first - second)


def _get(v, k, d=None):
    if isinstance(v, dict):
        return v.get(k, d)
    g = getattr(v, "get", None)
    return g(k, d) if callable(g) else getattr(v, k, d)


def _reorder_sells(obs, action):
    orders = [list(o) for o in (action.get("market") or [])]
    positions = [
        i for i, o in enumerate(orders)
        if len(o) >= 3 and o[0] == "SELL" and str(o[1]) in PRODUCTS
    ]
    if len(positions) < 2:
        return action
    market = _get(obs, "market", {}) or {}
    inv = _get(market, "inventory", {}) or {}

    def key(o):
        item = str(o[1])
        qty = max(1, int(o[2] or 1))
        cur = int(_get(inv, item, I0) or I0)
        return (_contested_value(item, cur, qty), _price(item, cur), item)

    original = [orders[i] for i in positions]
    ranked = sorted(original, key=key, reverse=True)
    if original == ranked:
        return action
    for pos, o in zip(positions, ranked):
        orders[pos] = o
    out = dict(action)
    out["market"] = orders
    return out


def agent(obs, config=None):
    try:
        action = _BASE.agent(obs)
        if not isinstance(action, dict):
            return action
        return _reorder_sells(obs, action)
    except Exception:
        return _BASE.agent(obs)
