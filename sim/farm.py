"""Farm production forward-model — reuses the engine's own pure functions.

The engine's `_apply_unit_action`, `_daily_refresh_plants/animals`, `_decay_plants`
and `_drop_inventories_to_shed` operate on plain farm/private dicts, so we import
and call them directly. That makes this model EXACT by construction (it IS the
engine code), and keeps a clean API for the search layer.
"""
import random
import kaggle_environments.envs.kaggriculture.kaggriculture as K

# re-export constants the search layer needs
CROPS = K.CROPS
ANIMALS = K.ANIMALS
FARMER_MOVES = K.FARMER_MOVES
LAND_ORDER = K.LAND_ORDER
LAND_PRICES = K.LAND_PRICES
SHOPS = K.SHOPS
MAX_SHOP_INSTANCES = K.MAX_SHOP_INSTANCES
new_plant = K._new_plant
new_animal = K._new_animal
shed_access_tiles = K._shed_access_tiles
is_shed_adjacent = K._is_shed_adjacent


def apply_unit_actions(farm, private, farmer_action, hand_actions, day,
                       board_size=10, turns_per_day=24, shed_capacity=100):
    """Apply one turn's physical actions (farmer + hands) exactly as the engine does."""
    K._apply_unit_action(farm, private, 0, farmer_action or ["PASS"],
                         board_size, day, turns_per_day, shed_capacity)
    for h, act in enumerate(hand_actions or []):
        K._apply_unit_action(farm, private, h + 1, act or ["PASS"],
                             board_size, day, turns_per_day, shed_capacity)


def decay_plants(farm, step):
    K._decay_plants(farm, step)


def end_of_day(farm, private, day, board_size=10, turns_per_day=24,
               shed_capacity=100, weed_chance=0.005, rng=None):
    """Engine's end-of-day: plant/animal refresh, weed spawn, drop inventories, respawn units.
    For deterministic search pass weed_chance=0 (or a fixed rng); for exact replay
    reproduction pass an rng seeded like the engine: random.Random((seed*1_000_003)^day)."""
    K._daily_refresh_plants(farm, day, turns_per_day)
    K._daily_refresh_animals(farm, day)
    if weed_chance > 0 and rng is not None:
        K._spawn_weeds(farm, board_size, weed_chance, rng)
    K._drop_inventories_to_shed(private, shed_capacity)
    farm["farmer"] = list(K._default_spawn(board_size))
    farm["hands"] = []
    farm["hires_today"] = 0
    private["inventories"] = [{}]


def herd(farm):
    """(cows, sheep, geese) currently on the board."""
    c = s = g = 0
    for row in farm["tiles"]:
        for t in row:
            if isinstance(t, dict) and t.get("animal"):
                a = t["animal"]
                c += a == "COW"; s += a == "SHEEP"; g += a == "GOOSE"
    return c, s, g


def unlock_shops(town, next_day, rng, shop_interval=3):
    """Engine's shop-unlock draw (with replacement), for exact replay reproduction."""
    if next_day > 0 and next_day % shop_interval == 0:
        if len(town["unlocked_shops"]) < MAX_SHOP_INSTANCES:
            town["unlocked_shops"].append(rng.choice(sorted(SHOPS)))
