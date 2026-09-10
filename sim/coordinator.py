"""Coordination solver: execute a target farm strategy with a fleet of workers,
assigning workers to tasks each turn via optimal (Hungarian) matching.

This is the piece that beats the naive greedy controller (v0-v2): instead of each
unit greedily grabbing the nearest job (which clumps and deadlocks), we build the
full task set and solve the global min-cost worker->task assignment, with explicit
supply chains (carry wheat before feeding, carry an animal before placing).

Layout: animals cluster on a ring around the central shed (short feed walks);
crops fill the rest. Parameterized by herd targets + crop plan + land schedule.
Driven through sim/game.py to measure herd/coins on the exact engine.
"""
from scipy.optimize import linear_sum_assignment
import kaggle_environments.envs.kaggriculture.kaggriculture as K

def _g(v, k, d=None):
    try:
        return K.get(v, k, d)
    except TypeError:
        return (v.get(k, d) if hasattr(v, 'get') else getattr(v, k, d))


SHED = [(4, 4), (5, 4), (4, 5), (5, 5)]
MOVES = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
ANIMAL_STRUCT = {"COW": "PASTURE", "SHEEP": "PASTURE", "GOOSE": "COOP"}
SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
ANIMAL_COST = {"GOOSE": 300, "COW": 400, "SHEEP": 500}

# tiles ordered by quadrant-unlock (NW always open; then NE, SW, SE as land is bought),
# and within each quadrant nearest-to-shed first (short feed walks).
_QORDER = {"NW": 0, "NE": 1, "SW": 2, "SE": 3}


def _ring(board=10):
    cx, cy = 4.5, 4.5
    tiles = [(x, y) for y in range(board) for x in range(board) if (x, y) not in SHED]
    tiles.sort(key=lambda p: (_QORDER.get(K._quadrant_of(p[0], p[1], board), 9),
                              abs(p[0] - cx) + abs(p[1] - cy)))
    return tiles


class Strategy:
    """A fixed target: which tiles hold which animal / crop, herd targets, land days."""
    def __init__(self, cows=4, sheep=2, geese=6, melons=22, straw=4, wheat=14,
                 land_days=(4, 5, 6)):
        self.cows, self.sheep, self.geese = cows, sheep, geese
        self.melons, self.straw, self.wheat = melons, straw, wheat
        self.land_days = land_days
        ring = _ring()
        # Build a queue of what to place, then assign to ring tiles in order. INTERLEAVE
        # so the ~21 unlocked NW tiles get a balanced early mix (a few animals to produce +
        # wheat to feed + melon for income), instead of 15 animals crowding out all crops.
        pools = {
            "COW": ["COW"] * cows, "SHEEP": ["SHEEP"] * sheep, "GOOSE": ["GOOSE"] * geese,
            "WHEAT": ["WHEAT"] * wheat, "MELON": ["MELON"] * melons, "STRAWBERRY": ["STRAWBERRY"] * straw,
        }
        # weighted round-robin: for every animal placed, also place ~1 wheat + ~1 melon early
        order = ["WHEAT", "COW", "MELON", "WHEAT", "SHEEP", "MELON", "COW", "WHEAT",
                 "GOOSE", "MELON", "COW", "STRAWBERRY"]
        queue = []
        while any(pools.values()):
            progressed = False
            for k in order:
                if pools[k]:
                    queue.append(pools[k].pop()); progressed = True
            if not progressed:
                break
        self.animal_tiles = {}
        self.crop_tiles = {}
        for idx, kind in enumerate(queue):
            if idx >= len(ring):
                break
            if kind in ("COW", "SHEEP", "GOOSE"):
                self.animal_tiles[ring[idx]] = kind
            else:
                self.crop_tiles[ring[idx]] = kind


def _dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _step_toward(pos, tgt):
    x, y = pos; tx, ty = tgt
    if x < tx: return "EAST"
    if x > tx: return "WEST"
    if y < ty: return "SOUTH"
    if y > ty: return "NORTH"
    return "PASS"


def _tile(farm, x, y):
    try:
        return farm["tiles"][y][x]
    except Exception:
        return "LOCKED"


class Coordinator:
    def __init__(self, strategy=None):
        self.st = strategy or Strategy()

    def act(self, obs):
        seat = 1 if int(_g(obs, "player", 0) or 0) == 1 else 0
        farms = _g(obs, "farms", []) or []
        farm = farms[seat] if seat < len(farms) else {}
        priv = _g(obs, "private", {}) or {}
        shed = dict(_g(priv, "shed", {}) or {})
        seeds = dict(_g(priv, "seeds", {}) or {})
        invs = [dict(iv or {}) for iv in (_g(priv, "inventories", []) or [{}])]
        day = int(_g(obs, "day", 0) or 0)
        hour = int(_g(obs, "hour", 0) or 0)
        money = float(_g(farm, "money", 0) or 0)
        quads = list(_g(farm, "unlocked_quadrants", []) or [])
        hires = int(_g(farm, "hires_today", 0) or 0)
        prices = _g(_g(obs, "market", {}) or {}, "prices", {}) or {}

        positions = [tuple(_g(farm, "farmer") or (4, 4))] + [tuple(p) for p in (_g(farm, "hands", []) or [])]
        n = len(positions)
        while len(invs) < n:
            invs.append({})

        # census of current board vs target
        cur_animals = {}   # tile -> kind
        cur_crops = {}
        weeds = []; empties = set()
        for y in range(len(farm.get("tiles", []))):
            for x in range(len(farm["tiles"][y])):
                t = _tile(farm, x, y)
                if t is None:
                    empties.add((x, y))
                elif isinstance(t, dict):
                    k = t.get("kind")
                    if k == "WEED": weeds.append((x, y))
                    elif k == "PLANT": cur_crops[(x, y)] = t
                    elif k in ("PASTURE", "COOP"):
                        if t.get("animal"): cur_animals[(x, y)] = t
        herd = len(cur_animals)

        market = self._market(farm, shed, seeds, money, quads, hires, prices, day, hour, herd)

        # ---- build task list: (kind, tile, needs) ----
        tasks = []
        # basic needs first
        for (x, y), t in cur_animals.items():
            if not t.get("fed_today"): tasks.append(("FEED", (x, y), "WHEAT"))
        for (x, y), t in cur_crops.items():
            if not t.get("watered_today"): tasks.append(("WATER", (x, y), None))
        for (x, y), t in cur_animals.items():
            if int(t.get("yield_units", 0) or 0) > 0: tasks.append(("HARVEST", (x, y), None))
        for (x, y), t in cur_crops.items():
            if int(t.get("yield_units", 0) or 0) > 0: tasks.append(("HARVEST", (x, y), None))
        for (x, y), t in cur_animals.items():
            if not t.get("cared_today"): tasks.append(("CARE", (x, y), None))
        for (x, y), t in cur_animals.items():
            if t.get("fertilizer_available"): tasks.append(("COLLECT_FERTILIZER", (x, y), None))
        # build/place/plant toward the target layout
        for tile, kind in self.st.animal_tiles.items():
            cell = _tile(farm, *tile)
            if cell is None:
                tasks.append(("BUILD_" + ("COOP" if kind == "GOOSE" else "PASTURE"), tile, None))
            elif isinstance(cell, dict) and cell.get("kind") in ("PASTURE", "COOP") and not cell.get("animal"):
                tasks.append(("PLACE", tile, kind))   # needs the animal carried
        for tile, kind in self.st.crop_tiles.items():
            if _tile(farm, *tile) is None and seeds.get(kind, 0) > 0:
                tasks.append(("PLANT_" + kind, tile, None))
        for w in weeds:
            tasks.append(("DIG", w, None))

        cmds = self._assign(positions, invs, tasks, shed, cur_animals)
        return {"farmer": cmds[0], "hands": cmds[1:], "market": market[:10]}

    def _assign(self, positions, invs, tasks, shed, cur_animals):
        n = len(positions)
        cmds = [None] * n
        free = set(range(n))

        n_hungry = sum(1 for t in tasks if t[0] == "FEED")
        # ---- committed animal pipeline (multi-turn: fetch -> walk -> place) ----
        # empty structures that still need an animal, with the kind they want
        place_tasks = [(t[1], t[2]) for t in tasks if t[0] == "PLACE"]  # (tile, kind)
        shed_avail = {a: int(shed.get(a, 0) or 0) for a in ("COW", "SHEEP", "GOOSE")}
        # 1. workers already carrying an animal -> go place it at the nearest matching empty struct
        for i in list(free):
            carried = next((a for a in ("COW", "SHEEP", "GOOSE") if invs[i].get(a, 0)), None)
            if not carried:
                continue
            targets = [tile for tile, kind in place_tasks if kind == carried]
            if not targets:
                continue
            tile = min(targets, key=lambda c: _dist(positions[i], c))
            place_tasks = [(t, k) for (t, k) in place_tasks if t != tile]
            cmds[i] = ["PLACE", carried] if positions[i] == tile else [_step_toward(positions[i], tile)]
            free.discard(i)
        # 2. for remaining empty structures whose animal is in the shed, send a worker to fetch it
        need_fetch = [(tile, kind) for tile, kind in place_tasks if shed_avail.get(kind, 0) > 0]
        for tile, kind in need_fetch:
            # reserve workers for feeding the EXISTING herd before fetching NEW animals
            if shed_avail.get(kind, 0) <= 0 or len(free) <= max(2, (n_hungry + 4) // 5):
                continue
            i = min(free, key=lambda w: _dist(positions[w], min(SHED, key=lambda c: _dist(positions[w], c))))
            if positions[i] in SHED:
                cmds[i] = ["PICKUP", kind, 1]; shed_avail[kind] -= 1
            else:
                cmds[i] = [_step_toward(positions[i], min(SHED, key=lambda c: _dist(positions[i], c)))]
            free.discard(i)
            place_tasks = [(t, k) for (t, k) in place_tasks if t != tile]

        # ---- committed feeding (life-or-death): keep animals fed before anything else ----
        hungry = [t[1] for t in tasks if t[0] == "FEED"]  # tiles of unfed animals
        if hungry:
            # workers already carrying wheat -> feed the nearest hungry animal (stay committed)
            for i in list(free):
                if invs[i].get("WHEAT", 0) <= 0 or not hungry:
                    continue
                tile = min(hungry, key=lambda c: _dist(positions[i], c))
                hungry.remove(tile)
                cmds[i] = ["FEED"] if positions[i] == tile else [_step_toward(positions[i], tile)]
                free.discard(i)
            # not enough wheat-carriers for the remaining hungry animals -> send fetchers
            carriers_incoming = sum(1 for i in range(n) if cmds[i] and cmds[i][0] in ("FEED", "PICKUP") )
            need_feeders = max(0, len(hungry) - 0)
            # send up to a few free workers to grab a wheat stack (covers many animals each)
            fetchers = min(need_feeders, 3, len(free))
            for _ in range(fetchers):
                if not free:
                    break
                i = min(free, key=lambda w: _dist(positions[w], min(SHED, key=lambda c: _dist(positions[w], c))))
                sp = min(SHED, key=lambda c: _dist(positions[i], c))
                if positions[i] in SHED and shed.get("WHEAT", 0) > 0:
                    cmds[i] = ["PICKUP", "WHEAT", min(10, int(shed.get("WHEAT", 0)))]
                else:
                    cmds[i] = [_step_toward(positions[i], sp)]
                free.discard(i)

        # ---- Hungarian on the remaining workers x non-PLACE, non-FEED tasks ----
        rest_tasks = [t for t in tasks if t[0] not in ("PLACE", "FEED")]
        idxs = sorted(free)
        for i in range(n):
            if cmds[i] is None and i not in free:
                cmds[i] = ["PASS"]
        if not rest_tasks or not idxs:
            for i in idxs:
                p = positions[i]
                cmds[i] = [_step_toward(p, min(SHED, key=lambda c: _dist(p, c)))] if p not in SHED else ["PASS"]
            return [c or ["PASS"] for c in cmds]
        INF = 10 ** 6
        cost = [[INF] * len(rest_tasks) for _ in range(len(idxs))]
        for r, i in enumerate(idxs):
            p = positions[i]
            wheat = invs[i].get("WHEAT", 0)
            for j, (kind, tile, need) in enumerate(rest_tasks):
                base = _dist(p, tile)
                if need == "WHEAT":
                    base = base if wheat > 0 else base + _dist(p, min(SHED, key=lambda c: _dist(p, c))) + 5
                pr = {"FEED": 0, "WATER": 1, "HARVEST": 2, "CARE": 3}.get(kind.split("_")[0], 4)
                cost[r][j] = base + pr
        rows, cols = linear_sum_assignment(cost)
        got = {}
        for r, j in zip(rows, cols):
            if cost[r][j] < INF:
                got[idxs[r]] = rest_tasks[j]
        for i in idxs:
            if i in got:
                cmds[i] = self._do(positions[i], invs[i], got[i], shed)
            else:
                p = positions[i]
                cmds[i] = [_step_toward(p, min(SHED, key=lambda c: _dist(p, c)))] if p not in SHED else ["PASS"]
        return [c or ["PASS"] for c in cmds]

    def _do(self, pos, inv, task, shed):
        kind, tile, need = task
        wheat = inv.get("WHEAT", 0)
        carry_animal = any(inv.get(a, 0) for a in ("COW", "SHEEP", "GOOSE"))
        # prerequisites: fetch wheat / animal at shed first
        if kind == "FEED" and wheat <= 0:
            return self._go_shed_pickup(pos, shed, "WHEAT")
        if kind == "PLACE" and inv.get(need, 0) <= 0:
            return self._go_shed_pickup(pos, shed, need)
        if pos != tile:
            return [_step_toward(pos, tile)]
        base = kind.split("_")[0]
        if base == "PLANT":
            return ["PLANT", kind.split("_", 1)[1]]
        if base == "BUILD":
            return [kind]
        if kind == "PLACE":
            return ["PLACE", need]
        return [base]

    def _go_shed_pickup(self, pos, shed, item):
        target = min(SHED, key=lambda c: _dist(pos, c))
        if pos in SHED:
            if shed.get(item, 0) > 0:
                return ["PICKUP", item, min(10, shed.get(item, 0)) if item == "WHEAT" else 1]
            return ["PASS"]
        return [_step_toward(pos, target)]

    def _fib(self, k):
        a, b = 1, 1
        for _ in range(max(0, k)):
            a, b = b, a + b
        return a

    def _market(self, farm, shed, seeds, money, quads, hires, prices, day, hour, herd):
        st = self.st
        orders = []
        cash = money
        wheat = int(shed.get("WHEAT", 0) or 0)
        wprice = max(1, int(prices.get("WHEAT", 25) or 25))
        feed_need = max(2, herd)  # 1 wheat/animal/day; keep ~2 days buffer below

        # 1. SELL products (never sell wheat below feed buffer)
        for g in ("MILK", "WOOL", "EGG", "STRAWBERRY", "MELON", "FERTILIZER", "CARROT"):
            have = int(shed.get(g, 0) or 0)
            if have > 1:
                orders.append(["SELL", g, have - 1])
        if wheat > 3 * feed_need + 10:
            orders.append(["SELL", "WHEAT", wheat - 3 * feed_need])

        # 2. FEED WHEAT IS SURVIVAL — animals die without it. Keep a 3-day buffer,
        #    and buy it before ANYTHING discretionary, down to a tiny cash floor.
        if herd > 0:
            # bigger buffer early (before wheat crops mature ~day 4-6), tapering later
            days_buffer = 6 if day < 12 else 3
            target_wheat = days_buffer * feed_need
            if wheat < target_wheat and cash >= 60:
                buy = min(target_wheat - wheat, 25, int((cash - 30) / wprice))
                if buy > 0:
                    orders.append(["BUY_PRODUCT", "WHEAT", buy]); cash -= buy * wprice
                    wheat += buy

        # 3. crop seeds — buy enough to actually FILL the empty target tiles (they sit empty
        #    otherwise). WHEAT = free feed; MELON = income engine (top per-tile value).
        def open_crop(kind):
            return sum(1 for tile, k in self.st.crop_tiles.items()
                       if k == kind and _tile(farm, *tile) is None)
        if seeds.get("WHEAT", 0) < min(8, open_crop("WHEAT")) and cash >= 150:
            orders.append(["BUY_SEED", "WHEAT", 8]); cash -= 80
        if seeds.get("MELON", 0) < 4 and day <= 14 and cash >= 600:
            orders.append(["BUY_SEED", "MELON", 4]); cash -= 320
        if seeds.get("STRAWBERRY", 0) < 1 and 3 <= day <= 16 and cash >= 900:
            orders.append(["BUY_SEED", "STRAWBERRY", 1]); cash -= 100

        # 4. hire enough workers to actually WORK the tiles — the tapes run ~10-12.
        #    Scale with the number of unmet tasks (empty target tiles + animals to tend),
        #    keeping a cash reserve early. Too few workers = tiles sit empty = no income.
        if hour < 4:
            open_targets = 0
            for tile, kind in list(self.st.crop_tiles.items()) + list(self.st.animal_tiles.items()):
                cell = _tile(farm, *tile)
                if cell is None or (isinstance(cell, dict) and cell.get("kind") in ("PASTURE", "COOP") and not cell.get("animal")):
                    open_targets += 1
            want = min(12, max(4, 4 + herd + open_targets // 6))
            reserve = 700 if day < 8 else 200
            for _ in range(max(0, want - hires)):
                c = self._fib(hires)
                if cash >= c + reserve:
                    orders.append(["HIRE"]); cash -= c; hires += 1
                else:
                    break

        # 5. GROW the herd only when wheat supply + income can sustain it.
        #    Phase it: don't over-extend before milk/melon income arrives (~day 8-10).
        target_herd = st.cows + st.sheep + st.geese
        pending = sum(int(shed.get(a, 0) or 0) for a in ANIMAL_COST)
        # skip the doomed pre-income herd: build only once melons/wheat sustain it
        phase_cap = 0 if day < 6 else (4 if day < 10 else (9 if day < 16 else target_herd))
        wheat_ok = wheat >= 3 * max(1, herd + 1)   # a comfortable buffer incl the next animal
        reserve = 1000 if day < 14 else 500
        if herd + pending < min(target_herd, phase_cap) and pending == 0 and wheat_ok:
            for kind in ("COW", "SHEEP", "GOOSE"):
                have_kind = sum(1 for row in farm.get("tiles", []) for t in (row or [])
                                if isinstance(t, dict) and t.get("animal") == kind)
                target_kind = {"COW": st.cows, "SHEEP": st.sheep, "GOOSE": st.geese}[kind]
                if have_kind < target_kind and cash >= ANIMAL_COST[kind] + reserve:
                    orders.append(["BUY_ANIMAL", kind, 1]); cash -= ANIMAL_COST[kind]; break

        # 6. land only after income flows, with a healthy reserve
        nq = len(quads)
        if nq < 4 and day >= max(8, (st.land_days[0] if st.land_days else 8)) and 1 <= nq <= 3:
            cost = (1000, 2000, 4000)[nq - 1]
            if cash >= cost + 1500:
                orders.append(["BUY_LAND"]); cash -= cost
        return orders


def agent(obs, config=None):
    if not hasattr(agent, "_c"):
        agent._c = Coordinator()
    try:
        return agent._c.act(obs)
    except Exception:
        farm = (_g(obs, "farms", []) or [{}, {}])[1 if int(_g(obs, "player", 0) or 0) == 1 else 0]
        return {"farmer": ["PASS"], "hands": [["PASS"] for _ in (_g(farm, "hands", []) or [])], "market": []}
