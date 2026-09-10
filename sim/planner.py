"""Production strategy planner: optimal tile allocation under land, labor, and
market-saturation constraints — using the exact per-tile yields and market_price.

Answers the SpaTaro question: given ~100 tiles and a labor budget, what crop/animal
mix maximizes revenue, once you account for prices crashing as you sell more?
"""
from kaggle_environments.envs.kaggriculture.kaggriculture import market_price, MARKET_PARAMS

# Measured exact per-tile lifetime economics (26-day horizon, one dedicated worker,
# animals with CARE, crops with watering; from engine simulation).
# tile -> (product, units_per_tile, worker_actions_per_tile)
TILE = {
    "MELON":      ("MELON", 12, 33),
    "COW":        ("MILK", 30, 36),      # with care
    "SHEEP":      ("WOOL", 30, 34),      # with care
    "GOOSE":      ("EGG", 46, 49),       # with care
    "STRAWBERRY": ("STRAWBERRY", 8, 23), # with fertilizer
    "CARROT":     ("CARROT", 24, 63),
    "WHEAT":      ("WHEAT", 24, 63),
    "TOMATO":     ("TOMATO", 8, 18),
}

# Town drains inventory over the season, letting price recover (approx units/season).
# Town center: 1 each of 8 non-fert products every 24 turns * 30 days = ~30 each.
# Shops add more for popular goods; rough per-good season drain estimate:
TOWN_DRAIN = {"WHEAT": 120, "CARROT": 60, "TOMATO": 45, "STRAWBERRY": 80, "MELON": 30,
              "EGG": 60, "MILK": 70, "WOOL": 45, "FERTILIZER": 0}


def revenue(product, units):
    """Revenue from selling `units` of product, aggressively, into a market drained by
    the town. Effective inventory when selling my k-th unit ~ I0 + k - town_drain
    (town recovers price as it consumes)."""
    if units <= 0:
        return 0.0
    I0 = MARKET_PARAMS[product]["I0"]
    drain = TOWN_DRAIN.get(product, 40)
    total = 0.0
    for k in range(int(units)):
        inv = I0 + k - drain
        total += market_price(product, inv)
    return total


def marginal(product, units_already):
    """Revenue of the next unit given some already sold."""
    I0 = MARKET_PARAMS[product]["I0"]
    drain = TOWN_DRAIN.get(product, 40)
    return market_price(product, I0 + units_already - drain)


def optimize(n_tiles=100, labor_actions=None, tile_types=None):
    """Greedy: repeatedly add the tile whose NEXT unit(s) give the best revenue per
    worker-action, until tiles or labor run out. Captures saturation (each added tile
    of a good lowers the marginal price of that good's output).
    labor_actions: total worker-actions available over the season (workers*24*days*efficiency)."""
    tile_types = tile_types or list(TILE)
    counts = {t: 0 for t in tile_types}
    sold = {}  # product -> units sold so far (drives saturation)
    used_tiles = 0
    used_labor = 0
    while used_tiles < n_tiles:
        best, best_score = None, -1
        for t in tile_types:
            product, upt, apt = TILE[t]
            # revenue of this tile's units at the current saturation of its product
            s = sold.get(product, 0)
            rev = sum(marginal(product, s + k) for k in range(upt))
            score = rev / apt  # revenue per worker-action
            if score > best_score:
                best_score, best, best_rev = score, t, rev
        if best is None or best_rev <= 0:
            break
        product, upt, apt = TILE[best]
        if labor_actions is not None and used_labor + apt > labor_actions:
            # skip this type; try others that fit
            fits = [t for t in tile_types if used_labor + TILE[t][2] <= labor_actions]
            if not fits:
                break
            # pick best-scoring among those that fit
            best = max(fits, key=lambda t: sum(marginal(TILE[t][0], sold.get(TILE[t][0], 0) + k) for k in range(TILE[t][1])) / TILE[t][2])
            product, upt, apt = TILE[best]
            best_rev = sum(marginal(product, sold.get(product, 0) + k) for k in range(upt))
            if best_rev <= 0:
                break
        counts[best] += 1
        sold[product] = sold.get(product, 0) + upt
        used_tiles += 1
        used_labor += apt
    total_rev = sum(revenue(TILE[t][0], sold.get(TILE[t][0], 0)) for t in set(TILE[t][0] for t in tile_types) for t in [t] ) if False else sum(revenue(p, u) for p, u in sold.items())
    return counts, sold, round(total_rev), used_labor


if __name__ == "__main__":
    for name, labor in [("unlimited labor", None), ("~11 workers", 11 * 24 * 26 * 1.0), ("~7 workers", 7 * 24 * 26)]:
        counts, sold, rev, used = optimize(n_tiles=100, labor_actions=labor)
        mix = {k: v for k, v in counts.items() if v}
        print(f"\n[{name}] optimal 100-tile mix: {mix}")
        print(f"  revenue ~${rev:,}  labor-actions used {int(used)}")
