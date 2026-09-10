"""Fast, EXACT market forward-model for Kaggriculture.

Reuses the engine's own market_price and constants, and reimplements the
per-unit lockstep sell/buy processing + town consumption exactly as
kaggriculture.py does, on a lightweight copyable state so search can roll
thousands of candidate sell schedules forward within the 1s/step budget.

Validated to reproduce real replays' market inventory step-for-step.
"""
from kaggle_environments.envs.kaggriculture.kaggriculture import (
    market_price, MARKET_PARAMS, PRODUCTS, SHOPS, TOWN_CENTER_PRODUCTS,
    CROPS, ANIMALS,
)

BUYABLE = ("WHEAT", "FERTILIZER")


def new_market():
    I0 = MARKET_PARAMS["WHEAT"]["I0"]
    inv = {it: MARKET_PARAMS[it]["I0"] for it in PRODUCTS}
    return {"inventory": inv, "prices": {it: MARKET_PARAMS[it]["base"] for it in PRODUCTS}}


def refresh_prices(market):
    for it in PRODUCTS:
        market["prices"][it] = market_price(it, market["inventory"][it])


def _parse(order):
    if not isinstance(order, (list, tuple)) or not order:
        return None
    op = order[0]
    if op in ("HIRE", "BUY_LAND"):
        return {"type": op}
    if op in ("BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL") and len(order) >= 3:
        try:
            n = int(order[2])
        except (TypeError, ValueError):
            return None
        return {"type": op, "item": order[1], "remaining": n} if n > 0 else None
    return None


def process_orders(market, players, orders_by_player, max_orders=10, shed_cap=100):
    """players: list of dicts {money, shed:{item:int}}.  orders_by_player: list of order-lists.
    Mutates market + players exactly as the engine's _process_market does (SELL/BUY_PRODUCT only;
    HIRE/BUY_LAND/BUY_SEED/BUY_ANIMAL affect money/shed but not market inventory for search purposes).
    Returns per-player realized proceeds (money delta from market ops).
    """
    inv = market["inventory"]
    queues = [list(o)[:max_orders] for o in orders_by_player]
    start_money = [p["money"] for p in players]
    max_len = max((len(q) for q in queues), default=0)
    for i in range(max_len):
        ostates = [_parse(q[i]) if i < len(q) else None for q in queues]
        # atomic ops (BUY_SEED/ANIMAL affect money+shed once; HIRE/BUY_LAND handled by caller's econ model)
        for pid, os_ in enumerate(ostates):
            if os_ is None:
                continue
            t = os_["type"]
            if t == "BUY_SEED" and os_["item"] in CROPS:
                cost = CROPS[os_["item"]]["seed"]
                for _ in range(os_["remaining"]):
                    if players[pid]["money"] < cost:
                        break
                    players[pid]["money"] -= cost
                ostates[pid] = None
            elif t == "BUY_ANIMAL" and os_["item"] in ANIMALS:
                cost = ANIMALS[os_["item"]]["cost"]
                for _ in range(os_["remaining"]):
                    if players[pid]["money"] < cost or sum(players[pid]["shed"].values()) >= shed_cap:
                        break
                    players[pid]["money"] -= cost
                    players[pid]["shed"][os_["item"]] = players[pid]["shed"].get(os_["item"], 0) + 1
                ostates[pid] = None
            elif t in ("HIRE", "BUY_LAND"):
                ostates[pid] = None  # econ handled elsewhere; no market-inventory effect
        # per-unit lockstep for SELL / BUY_PRODUCT
        guard = 0
        while True:
            guard += 1
            if guard >= 100000:
                break
            quoted = [None, None]
            for pid, os_ in enumerate(ostates):
                if os_ is None or os_["remaining"] <= 0:
                    continue
                t, it = os_["type"], os_.get("item")
                if t == "SELL" and it in PRODUCTS:
                    quoted[pid] = ("SELL", it, market_price(it, inv[it]), os_)
                elif t == "BUY_PRODUCT" and it in BUYABLE:
                    quoted[pid] = ("BUY_PRODUCT", it, market_price(it, inv[it] - 1), os_)
                else:
                    ostates[pid] = None
            if all(q is None for q in quoted):
                break
            committed = False
            for pid, q in enumerate(quoted):
                if q is None:
                    continue
                op, it, price, os_ = q
                pl = players[pid]
                if op == "SELL":
                    if pl["shed"].get(it, 0) <= 0:
                        ostates[pid] = None
                        continue
                    pl["shed"][it] -= 1
                    pl["money"] += price
                    if price > 1:
                        inv[it] += 1
                    os_["remaining"] -= 1
                    committed = True
                else:  # BUY_PRODUCT
                    if pl["money"] < price or sum(pl["shed"].values()) >= shed_cap:
                        ostates[pid] = None
                        continue
                    pl["money"] -= price
                    pl["shed"][it] = pl["shed"].get(it, 0) + 1
                    inv[it] -= 1
                    os_["remaining"] -= 1
                    committed = True
            if not committed:
                break
        refresh_prices(market)
    return [players[p]["money"] - start_money[p] for p in range(len(players))]


def town_consume(market, shops, step, shop_interval=4, center_interval=24):
    inv = market["inventory"]
    if step % shop_interval == 0:
        for shop in shops:
            products = SHOPS.get(shop, ())
            mult = 2 if len(products) == 1 else 1
            for it in products:
                inv[it] -= mult
    if step % center_interval == 0:
        for it in TOWN_CENTER_PRODUCTS:
            inv[it] -= 1
    refresh_prices(market)
