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
    """A fixed target: which tiles hold which animal / crop, herd targets, land days.

    Mix mirrors the top-3000 replays: a BIG cow+sheep herd (milk + wool + fertilizer) and
    STRAWBERRY as the dominant crop. Strawberry is ONGOING (plant once, harvest every 2 days
    all game) so it needs almost no replant labor -- that freed labor is what lets the fleet
    tend a large herd, which is why melon (constant 12-day replant cycles) scored far worse."""
    def __init__(self, cows=3, sheep=1, geese=3, melons=15, straw=15, wheat=12,
                 land_days=(3, 5, 8)):
        self.cows, self.sheep, self.geese = cows, sheep, geese
        self.melons, self.straw, self.wheat = melons, straw, wheat
        self.land_days = land_days
        ring = _ring()
        # Proportional interleave: place every kind at evenly-spaced fractional positions so
        # animals are spread through the whole worked area (short feed walks everywhere) while
        # the dominant crop fills the rest, instead of clumping animals in one quadrant.
        counts = [("COW", cows), ("SHEEP", sheep), ("GOOSE", geese),
                  ("WHEAT", wheat), ("MELON", melons), ("STRAWBERRY", straw)]
        total = sum(n for _, n in counts) or 1
        seq = []
        for k, n in counts:
            for i in range(n):
                seq.append(((i + 0.5) * total / n, k))
        seq.sort()
        queue = [k for _, k in seq]
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


def _crop_ready(t, day):
    """True only when a crop tile is actually worth harvesting.

    Non-ongoing crops (WHEAT/CARROT/MELON) get yield_units=1 the moment they're planted
    but CANNOT be harvested until age >= first_yield_day, and their yield GROWS via daily
    watering up to max_yield around max_yield_day. Harvesting the instant yield_units>0
    (as the old code did) means workers camp on immature crops issuing no-op HARVESTs for
    days, and any early success grabs 1 unit instead of the full 6. So for non-ongoing crops
    we wait until fully grown; ongoing crops (TOMATO/STRAWBERRY) are harvested whenever
    mature yield is present."""
    cd = K.CROPS.get(t.get("crop"))
    if not cd or int(t.get("yield_units", 0) or 0) <= 0:
        return False
    age = day - int(t.get("planted_day", day) or 0)
    if age < cd["first_yield_day"]:
        return False
    if not cd["ongoing"]:
        return age >= cd["max_yield_day"] or int(t.get("yield_units", 0) or 0) >= cd["max_yield"]
    return True


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

        market = self._market(farm, shed, seeds, money, quads, hires, prices, day, hour, herd, invs)

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
            if _crop_ready(t, day): tasks.append(("HARVEST", (x, y), None))
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
        if base in ("BUILD", "COLLECT"):
            return [kind]   # BUILD_COOP / BUILD_PASTURE / COLLECT_FERTILIZER are full op names
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

    def _market(self, farm, shed, seeds, money, quads, hires, prices, day, hour, herd, invs=None):
        st = self.st
        orders = []
        cash = money
        invs = invs or []
        wheat = int(shed.get("WHEAT", 0) or 0)
        wprice = max(1, int(prices.get("WHEAT", 25) or 25))
        feed_need = max(2, herd)  # 1 wheat/animal/day; keep ~2 days buffer below
        # end-game: an animal/tile bought now can't pay back before turn 720, so stop all
        # capital spend and just keep the herd fed while we liquidate inventory into cash.
        endgame = day >= 27

        # 1. SELL products (never sell wheat below feed buffer)
        for g in ("MILK", "WOOL", "EGG", "STRAWBERRY", "MELON", "FERTILIZER", "CARROT"):
            have = int(shed.get(g, 0) or 0)
            if have > 1:
                orders.append(["SELL", g, have - 1])
        # keep enough wheat to feed the herd we're GROWING toward, not just today's herd,
        # so the herd-growth gate below is never starved (that deadlocked herd at 4-7).
        target_herd = st.cows + st.sheep + st.geese
        grow_need = max(2, min(target_herd, herd + 3))
        if wheat > 3 * grow_need + 12:
            orders.append(["SELL", "WHEAT", wheat - 3 * grow_need])

        # 2. FEED WHEAT IS SURVIVAL — but we GROW 14 wheat tiles (~20/day, herd needs ~12),
        #    so buying is an EMERGENCY backstop only: top up just enough for a couple of feed
        #    days when the shed runs low, and keep a real cash reserve. The old code bought a
        #    big buffer every turn down to a $60 floor, which pinned cash at zero and flooded
        #    the shed with low-value wheat that crashed the wheat price on sale.
        if herd > 0:
            survival = feed_need + max(2, herd // 2)   # ~1.5 days of feed
            if wheat < survival and cash >= 400:
                buy = min(survival - wheat, 20, int((cash - 300) / wprice))
                if buy > 0:
                    orders.append(["BUY_PRODUCT", "WHEAT", buy]); cash -= buy * wprice
                    wheat += buy

        # 3. crop seeds — stock enough to FILL every open target tile of each crop. STRAWBERRY
        #    is the income engine now (ongoing: plant once, harvest every 2 days) so we keep it
        #    stocked; WHEAT feeds the herd + early income. A crop is only worth planting if it
        #    can still pay back before day 30: wheat ~4 days, strawberry needs ~10 to first yield.
        def open_crop(kind):
            return sum(1 for tile, k in self.st.crop_tiles.items()
                       if k == kind and _tile(farm, *tile) is None)
        SEED_PRICE = {"WHEAT": 10, "MELON": 80, "STRAWBERRY": 100, "CARROT": 20, "TOMATO": 50}
        for ck, batch, dmax, floor in (("WHEAT", 10, 26, 100), ("STRAWBERRY", 12, 20, 500),
                                       ("MELON", 8, 18, 300)):
            if day > dmax:
                continue
            want = min(open_crop(ck), batch)
            have = int(seeds.get(ck, 0) or 0)
            if want > have and cash >= floor:
                price = SEED_PRICE[ck]
                buy = min(want - have, int((cash - floor) / price))
                if buy > 0:
                    orders.append(["BUY_SEED", ck, buy]); cash -= buy * price

        # 4. hire the crew — the top agents run 13-14. Hands clear nightly so we RE-HIRE the
        #    whole crew every day, endgame included (no harvesters = no income/liquidation).
        if hour < 4:
            open_targets = 0
            for tile, kind in list(self.st.crop_tiles.items()) + list(self.st.animal_tiles.items()):
                cell = _tile(farm, *tile)
                if cell is None or (isinstance(cell, dict) and cell.get("kind") in ("PASTURE", "COOP") and not cell.get("animal")):
                    open_targets += 1
            want = min(13, max(4, 4 + herd + open_targets // 6))
            reserve = 700 if day < 8 else 200
            for _ in range(max(0, want - hires)):
                c = self._fib(hires)
                if cash >= c + reserve:
                    orders.append(["HIRE"]); cash -= c; hires += 1
                else:
                    break

        # 5. GROW the herd (cow+sheep+goose) toward target. Count each kind ROBUSTLY as
        #    placed-on-board + in-shed + carried-by-a-worker; a carried animal was once
        #    invisible to both counts -> spurious over-buy -> a stuck animal that deadlocked
        #    buying. Phase it so it never outruns wheat/income, but allow a real pipeline so a
        #    big herd (~15-20, like the top agents) actually gets built, not one-at-a-time.
        placed = {"COW": 0, "SHEEP": 0, "GOOSE": 0}
        for row in farm.get("tiles", []):
            for t in (row or []):
                if isinstance(t, dict) and t.get("animal") in placed:
                    placed[t["animal"]] += 1
        in_shed = {a: int(shed.get(a, 0) or 0) for a in placed}
        carried = {a: 0 for a in placed}
        for iv in invs:
            for a in placed:
                carried[a] += int(iv.get(a, 0) or 0)
        total = {a: placed[a] + in_shed[a] + carried[a] for a in placed}
        pending = sum(in_shed[a] + carried[a] for a in placed)   # animals not yet placed
        phase_cap = 0 if day < 5 else (6 if day < 9 else (12 if day < 14 else target_herd))
        wheat_ok = wheat >= herd + 3   # enough to feed current herd + the incoming animal(s)
        reserve = 1200 if day < 12 else 500
        # up to 2 in flight so build isn't serialized; never buy a kind past its target.
        if not endgame and sum(total.values()) < min(target_herd, phase_cap) and pending <= 2 and wheat_ok:
            for kind in ("COW", "SHEEP", "GOOSE"):
                target_kind = {"COW": st.cows, "SHEEP": st.sheep, "GOOSE": st.geese}[kind]
                if total[kind] < target_kind and cash >= ANIMAL_COST[kind] + reserve:
                    orders.append(["BUY_ANIMAL", kind, 1]); cash -= ANIMAL_COST[kind]; break

        # 6. land — expand FAST (the top agents unlock quad 2 by ~day 5, quad 3 by ~day 7-11).
        #    Buy the nq-th quadrant once day >= land_days[nq-1]. Stop at 3 quadrants (75 tiles):
        #    that already fits the whole target layout, and the 4th (SE) costs 4000 for tiles
        #    we don't use.
        nq = len(quads)
        ld = st.land_days if st.land_days else (3, 6, 12)
        if not endgame and 1 <= nq < 3 and day >= ld[nq - 1]:
            cost = (1000, 2000, 4000)[nq - 1]
            if cash >= cost + 800:
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
