"""Herd-builder v2: STATELESS reactive agent with a CENTRALIZED task planner.

Each turn: census the board, build a prioritized global task list (feed, water,
harvest, build, place, plant, care, weed, logistics), then assign each task to
the nearest distinct unit. A unit executes its task if it's standing on the
target, else steps toward it. Being stateless, it can never desync.

Design goals from the replay analysis: ~16-animal herd near the central shed,
bulletproof daily feeding (losing an animal is catastrophic), and a build
pipeline that keeps empty pastures ready so buy->pickup->place never deadlocks.
"""
CENTER = [(4, 4), (5, 4), (4, 5), (5, 5)]
ANIMAL_STRUCT = {"COW": "PASTURE", "SHEEP": "PASTURE", "GOOSE": "COOP"}
SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
ANIMAL_COST = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
LAND_COST = (1000, 2000, 4000)
PREMIUM = ("MILK", "WOOL", "STRAWBERRY", "MELON", "EGG")
HERD_TARGET = 16
COW_TARGET, SHEEP_TARGET = 10, 6
CROP_SEEDS = ("STRAWBERRY", "MELON")


def _get(v, k, d=None):
    if isinstance(v, dict):
        return v.get(k, d)
    g = getattr(v, "get", None)
    return g(k, d) if callable(g) else getattr(v, k, d)


def _seat(obs):
    return 1 if int(_get(obs, "player", 0) or 0) == 1 else 0


def agent(obs, config=None):
    try:
        return _act(obs)
    except Exception:
        farm = (_get(obs, "farms", []) or [{}, {}])[_seat(obs)]
        return {"farmer": ["PASS"], "hands": [["PASS"] for _ in (_get(farm, "hands", []) or [])], "market": []}


def _dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _step_toward(pos, target):
    x, y = pos
    tx, ty = target
    if x < tx:
        return ["EAST"]
    if x > tx:
        return ["WEST"]
    if y < ty:
        return ["SOUTH"]
    if y > ty:
        return ["NORTH"]
    return ["PASS"]


def _fib(n):
    a, b = 1, 1
    for _ in range(max(0, n)):
        a, b = b, a + b
    return a


def _act(obs):
    seat = _seat(obs)
    farms = _get(obs, "farms", []) or []
    farm = farms[seat] if seat < len(farms) else {}
    priv = _get(obs, "private", {}) or {}
    shed = dict(_get(priv, "shed", {}) or {})
    seeds = dict(_get(priv, "seeds", {}) or {})
    invs = [dict(iv or {}) for iv in (_get(priv, "inventories", []) or [])]
    tiles = _get(farm, "tiles", []) or []
    day = int(_get(obs, "day", 0) or 0)
    hour = int(_get(obs, "hour", 0) or 0)
    money = float(_get(farm, "money", 0) or 0)
    quads = list(_get(farm, "unlocked_quadrants", []) or [])
    hires_today = int(_get(farm, "hires_today", 0) or 0)
    prices = _get(_get(obs, "market", {}) or {}, "prices", {}) or {}

    positions = [tuple(_get(farm, "farmer") or (4, 4))] + [tuple(p) for p in (_get(farm, "hands", []) or [])]
    n_units = len(positions)
    while len(invs) < n_units:
        invs.append({})

    H = len(tiles)
    W = len(tiles[0]) if tiles else 0

    def cell(x, y):
        if 0 <= y < H and 0 <= x < W:
            return tiles[y][x]
        return "LOCKED"

    animals, plants, weeds, empties, structs_empty = [], [], [], [], []
    cows = sheep = geese = 0
    for y in range(H):
        for x in range(W):
            t = cell(x, y)
            if t is None:
                empties.append((x, y))
            elif t == "LOCKED":
                continue
            elif isinstance(t, dict):
                k = t.get("kind")
                if k == "WEED":
                    weeds.append((x, y))
                elif k == "PLANT":
                    plants.append((x, y, t))
                elif k in ("PASTURE", "COOP"):
                    if t.get("animal"):
                        animals.append((x, y, t))
                        a = t.get("animal")
                        cows += a == "COW"; sheep += a == "SHEEP"; geese += a == "GOOSE"
                    else:
                        structs_empty.append((x, y))
    herd = len(animals)

    # -------- MARKET --------
    market = _plan_market(farm, shed, seeds, money, quads, hires_today, prices,
                          herd, cows, sheep, day, hour, structs_empty, empties)

    # -------- TASK LIST (target tile, kind, verb) --------
    # priority: feed > water > harvest > place > build > plant > care > weed
    tasks = []
    for x, y, t in animals:
        if not t.get("fed_today", False):
            tasks.append(("FEED", (x, y), 0))
    for x, y, t in plants:
        if not t.get("watered_today", False):
            tasks.append(("WATER", (x, y), 1))
    for x, y, t in animals:
        if int(t.get("yield_units", 0) or 0) > 0:
            tasks.append(("HARVEST", (x, y), 2))
    for x, y, t in plants:
        if int(t.get("yield_units", 0) or 0) > 0:
            tasks.append(("HARVEST", (x, y), 2))
    # place animals into empty structures (need an animal in a unit inv or shed)
    n_place = min(len(structs_empty),
                  sum(inv.get("COW", 0) + inv.get("SHEEP", 0) + inv.get("GOOSE", 0) for inv in invs)
                  + int(shed.get("COW", 0) or 0) + int(shed.get("SHEEP", 0) or 0))
    for i in range(n_place):
        tasks.append(("PLACE", structs_empty[i], 3))
    # build pastures until we have room for the whole target herd
    need_structs = HERD_TARGET - herd - len(structs_empty)
    build_tiles = [e for e in empties if _near_center(e)][:max(0, need_structs)]
    for e in build_tiles:
        tasks.append(("BUILD", e, 4))
    # plant crops on remaining empties
    if any(seeds.get(c, 0) for c in CROP_SEEDS + ("WHEAT",)):
        plant_tiles = [e for e in empties if e not in build_tiles][:8]
        for e in plant_tiles:
            tasks.append(("PLANT", e, 5))
    for x, y, t in animals:
        if not t.get("cared_today", False):
            tasks.append(("CARE", (x, y), 6))
    for w in weeds:
        tasks.append(("DIG", w, 7))

    # -------- ASSIGN tasks to nearest distinct units --------
    cmds = [None] * n_units
    used = [False] * n_units
    hungry_count = sum(1 for x, y, t in animals if not t.get("fed_today", False))

    # feed logistics: a feeder needs wheat in inventory
    tasks.sort(key=lambda z: z[2])
    for kind, tgt, _pri in tasks:
        # choose the nearest free unit that can do this task
        best, bd = None, 1e9
        for ui in range(n_units):
            if used[ui]:
                continue
            if kind == "FEED" and invs[ui].get("WHEAT", 0) <= 0:
                continue  # only wheat-carriers feed
            if kind == "PLACE":
                pass  # any unit; will pickup en route if needed
            d = _dist(positions[ui], tgt)
            if d < bd:
                bd, best = d, ui
        if best is None:
            continue
        used[best] = True
        cmds[best] = _do(kind, positions[best], tgt, invs[best], cell, seeds, shed, structs_empty)

    # -------- idle units: logistics (fetch wheat / animals) or restock --------
    for ui in range(n_units):
        if cmds[ui] is not None:
            continue
        cmds[ui] = _logistics(ui, positions[ui], invs[ui], shed, structs_empty,
                              hungry_count, animals, weeds)

    return {"farmer": cmds[0] or ["PASS"], "hands": [c or ["PASS"] for c in cmds[1:]], "market": market[:10]}


def _near_center(e):
    x, y = e
    return abs(x - 4.5) <= 3.5 and abs(y - 4.5) <= 3.5


def _do(kind, pos, tgt, inv, cell, seeds, shed, structs_empty):
    if pos != tgt:
        # if heading to PLACE but not carrying an animal, detour to shed to grab one
        if kind == "PLACE" and not any(inv.get(a, 0) for a in ("COW", "SHEEP", "GOOSE")):
            if pos in CENTER:
                if shed.get("COW", 0):
                    return ["PICKUP", "COW", 1]
                if shed.get("SHEEP", 0):
                    return ["PICKUP", "SHEEP", 1]
            return _step_toward(pos, min(CENTER, key=lambda c: _dist(pos, c)))
        return _step_toward(pos, tgt)
    # on target tile
    if kind == "FEED":
        return ["FEED"]
    if kind == "WATER":
        return ["WATER"]
    if kind == "HARVEST":
        return ["HARVEST"]
    if kind == "CARE":
        return ["CARE"]
    if kind == "DIG":
        return ["DIG"]
    if kind == "BUILD":
        return ["BUILD_PASTURE"]
    if kind == "PLANT":
        for crop in ("STRAWBERRY", "MELON", "WHEAT", "CARROT"):
            if seeds.get(crop, 0) > 0:
                return ["PLANT", crop]
        return ["PASS"]
    if kind == "PLACE":
        for a in ("COW", "SHEEP", "GOOSE"):
            if inv.get(a, 0):
                return ["PLACE", a]
        return ["PASS"]
    return ["PASS"]


def _logistics(ui, pos, inv, shed, structs_empty, hungry_count, animals, weeds):
    at_shed = pos in CENTER
    carrying_animal = any(inv.get(a, 0) for a in ("COW", "SHEEP", "GOOSE"))
    wheat = int(inv.get("WHEAT", 0) or 0)
    # dump premium produce we're carrying
    if at_shed and any(k in PREMIUM and v > 0 for k, v in inv.items()):
        return ["DROP"]
    # grab an animal if there's an empty structure to fill
    if at_shed and structs_empty and not carrying_animal:
        if shed.get("COW", 0):
            return ["PICKUP", "COW", 1]
        if shed.get("SHEEP", 0):
            return ["PICKUP", "SHEEP", 1]
    # fetch wheat if animals still need feeding and shed has wheat
    if hungry_count > 0 and wheat < 8 and shed.get("WHEAT", 0) > 0:
        if at_shed:
            return ["PICKUP", "WHEAT", min(10, int(shed.get("WHEAT", 0)))]
        return _step_toward(pos, min(CENTER, key=lambda c: _dist(pos, c)))
    # otherwise idle toward shed
    if not at_shed:
        return _step_toward(pos, min(CENTER, key=lambda c: _dist(pos, c)))
    return ["PASS"]


def _plan_market(farm, shed, seeds, money, quads, hires_today, prices,
                 herd, cows, sheep, day, hour, structs_empty, empties):
    orders = []
    cash = money

    # sell premium (keep 1 in reserve to avoid flooding tiny amounts)
    for g in PREMIUM:
        have = int(shed.get(g, 0) or 0)
        if have > 2:
            orders.append(["SELL", g, have - 1])
    wheat = int(shed.get("WHEAT", 0) or 0)
    feed_buffer = 2 * max(1, herd)
    if wheat > feed_buffer + 12:
        orders.append(["SELL", "WHEAT", wheat - feed_buffer])
    if int(shed.get("FERTILIZER", 0) or 0) > 2:
        orders.append(["SELL", "FERTILIZER", int(shed["FERTILIZER"]) - 1])

    # hire: scale to herd+crops, but keep money for animals early
    if hour < 3:
        want = min(11, 6 + herd // 3)
        for _ in range(max(0, want - hires_today)):
            c = _fib(hires_today)
            reserve = 400 if herd < HERD_TARGET else 50
            if cash >= c + reserve:
                orders.append(["HIRE"]); cash -= c; hires_today += 1
            else:
                break

    # land when herd fills current space
    nq = len(quads)
    if 1 <= nq <= 3 and cash >= LAND_COST[nq - 1] + 1200 and herd >= 5 * nq:
        orders.append(["BUY_LAND"]); cash -= LAND_COST[nq - 1]; nq += 1

    # buy animals: keep the pipeline full (shed pending < empty structs + 1)
    if herd < HERD_TARGET:
        pending = int(shed.get("COW", 0) or 0) + int(shed.get("SHEEP", 0) or 0)
        room = len(structs_empty) + sum(1 for e in empties if _near_center(e))
        if pending + herd < HERD_TARGET and pending <= len(structs_empty) and room > 0:
            a = "COW" if cows < COW_TARGET else "SHEEP"
            if cash >= ANIMAL_COST[a] + 300:
                orders.append(["BUY_ANIMAL", a, 1]); cash -= ANIMAL_COST[a]

    # keep wheat for feed: grow + buy
    if seeds.get("WHEAT", 0) < 2 and cash >= 40:
        orders.append(["BUY_SEED", "WHEAT", 4]); cash -= 40
    if wheat < max(1, herd) and cash >= 300:
        buy = min(2 * max(1, herd) - wheat, 12)
        if buy > 0:
            orders.append(["BUY_PRODUCT", "WHEAT", buy]); cash -= buy * max(1, int(prices.get("WHEAT", 25)))

    # cash crops
    if day <= 22 and seeds.get("STRAWBERRY", 0) < 2 and cash >= 300:
        orders.append(["BUY_SEED", "STRAWBERRY", 1]); cash -= 100
    if day <= 8 and seeds.get("MELON", 0) < 2 and cash >= 250:
        orders.append(["BUY_SEED", "MELON", 1]); cash -= 80

    return orders
