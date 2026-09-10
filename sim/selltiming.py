"""Sell-timing optimizer + gap analysis.

Uses the EXACT market_price to answer: for a good produced over a game, what is
the revenue-maximizing schedule of when/how-much to sell, and how much revenue
does the actual (tape) schedule leave on the table?

Per-good optimization is a water-filling problem: price(inv) is decreasing in
inventory, so revenue is concave in units-sold-this-turn. Against a fixed
"background" inventory trajectory (town drain + opponent sells + own buys), the
optimum assigns each unit to the still-available turn where its marginal price is
highest. Selling all of a turn's units at once crashes the price across them;
spreading lets the town drain recover the price between turns.
"""
import heapq
from kaggle_environments.envs.kaggriculture.kaggriculture import market_price, PRODUCTS


def optimize_good(background_inv, availability, total_units):
    """background_inv[t] = market inventory of the good at turn t WITHOUT my sells.
    availability[t] = cumulative units of the good I have produced (can sell) by turn t.
    total_units = units I must sell over the horizon (== my production, since unsold=0).

    Returns (schedule, revenue): schedule[t] = units to sell at turn t (revenue-max), and
    the total revenue. Greedy water-filling: repeatedly place the next unit at the turn
    whose *next* marginal price is highest, respecting availability (can't sell before produced)
    and the running count already placed at each turn (which lowers that turn's next price).
    """
    T = len(background_inv)
    placed = [0] * T
    # sold-so-far per turn drives the marginal price for the NEXT unit at that turn.
    # Max-heap of (marginal_price, t). We push each turn's current next-unit price.
    heap = []
    for t in range(T):
        # a unit sold at t adds (placed[t]) already-sold to inventory before it
        price = market_price_good(background_inv[t] + placed[t])
        heapq.heappush(heap, (-price, t))
    revenue = 0
    remaining = total_units
    # availability cap per turn = max units that could be sold by turn t (produced by then)
    # We enforce it as: total placed at turns <= t must be <= availability[t]. Simplest:
    # place greedily then repair; but a clean way is to track cumulative and skip turns whose
    # prefix is saturated. For tractability we use the common case where production completes
    # early enough that availability rarely binds; we still guard it.
    while remaining > 0 and heap:
        neg, t = heapq.heappop(heap)
        # availability guard: units placed at turns [0..t] must stay <= availability[t]
        prefix = sum(placed[:t + 1])
        if prefix >= availability[t]:
            continue  # nothing producible yet to sell at/through this turn
        placed[t] += 1
        revenue += -neg
        remaining -= 1
        nxt = market_price_good(background_inv[t] + placed[t])
        heapq.heappush(heap, (-nxt, t))
    return placed, revenue


# module-level current-good price closure (set by analyze)
_CUR_PARAMS_ITEM = ["WHEAT"]


def market_price_good(inv):
    return market_price(_CUR_PARAMS_ITEM[0], inv)


def analyze_replay(d, my_seat, goods=("STRAWBERRY", "MILK", "WOOL", "MELON", "WHEAT")):
    """For each good, compute my actual sell revenue vs the water-filling optimum,
    holding the opponent+town background fixed. Returns per-good {actual, optimal, gap}."""
    steps = d["steps"]
    T = len(steps)

    def held(obs, g):
        p = obs.get("private", {})
        return p.get("shed", {}).get(g, 0) + sum(iv.get(g, 0) for iv in p.get("inventories", []))

    out = {}
    for g in goods:
        _CUR_PARAMS_ITEM[0] = g
        # recorded market inventory of g at each step
        rec_inv = [steps[s][my_seat]["observation"]["market"]["inventory"].get(g, 10000) for s in range(T)]
        # my sells per turn (capped by holdings) and my revenue, plus my inventory-adds
        my_sells = [0] * T
        actual_rev = 0.0
        for s in range(T):
            obs = steps[s][my_seat]["observation"]; pr = obs["market"]["prices"]
            rem = held(obs, g)
            for o in (steps[s][my_seat].get("action") or {}).get("market", []) or []:
                if o and o[0] == "SELL" and o[1] == g:
                    q = min(int(o[2]), max(0, rem)); rem -= q
                    my_sells[s] += q
                    actual_rev += q * float(pr.get(g, 0))
        total = sum(my_sells)
        if total == 0:
            continue
        # background inventory WITHOUT my sells (sells at price>1 add +1 each)
        my_cum = 0; background = []
        for s in range(T):
            background.append(rec_inv[s] - my_cum)
            my_cum += my_sells[s]  # approx: each of my sold units added 1 (ignores $1 floor)
        # availability: cumulative production I had = cumulative units I eventually sold
        avail_cum = []; c = 0
        # produced-by-turn proxy: units become sellable when they appear in shed; use cumulative sells shifted
        # (a unit sold at t was available at t). cumulative availability = cumulative my_sells.
        for s in range(T):
            c += my_sells[s]; avail_cum.append(c)
        sched, opt_rev = optimize_good(background, avail_cum, total)
        out[g] = {"units": total, "actual": round(actual_rev), "optimal": round(opt_rev),
                  "gap": round(opt_rev - actual_rev), "actual_ppu": round(actual_rev / total, 1),
                  "optimal_ppu": round(opt_rev / total, 1)}
    return out
