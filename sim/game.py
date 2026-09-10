"""Full-game forward-model: composes the engine's exact turn pipeline on a
lightweight, copyable state so search can roll candidate plans forward.

Reuses the engine's own interpreter sub-steps (_apply_unit_action, _process_market,
_town_consume, _decay_plants, _end_of_day) via a thin state adapter, so it is exact
by construction. Validated to reproduce real replays' final money.
"""
import copy
import random
import kaggle_environments.envs.kaggriculture.kaggriculture as K


class _Obs:
    """Attribute-access view the engine functions expect (obs.market, obs.farms, ...)."""
    def __init__(self, player, farms, market, town, private):
        self.player = player
        self.farms = farms
        self.market = market
        self.town = town
        self.private = private
        self.day = 0
        self.hour = 0
        self.step = 0


class _St:
    def __init__(self, obs, action):
        self.observation = obs
        self.action = action


class _Env:
    def __init__(self, configuration, seed):
        self.configuration = configuration
        self.info = {"seed": seed}


class Game:
    """Holds shared market/town + per-player farms/privates; steps the exact pipeline."""

    def __init__(self, farms, privates, market, town, configuration, seed=0, step=0):
        self.farms = farms                 # [farm0, farm1] plain dicts
        self.privates = privates           # [private0, private1]
        self.market = market               # {"inventory":..., "prices":...}
        self.town = town                   # {"unlocked_shops": [...]}
        self.cfg = configuration
        self.seed = seed
        self.step = step
        self.tpd = int(K.get(configuration, "turnsPerDay", 24))
        self.board = int(K.get(configuration, "boardSize", 10))

    def clone(self):
        return Game(copy.deepcopy(self.farms), copy.deepcopy(self.privates),
                    copy.deepcopy(self.market), copy.deepcopy(self.town),
                    self.cfg, self.seed, self.step)

    def _state(self, actions):
        # both engine-view states share the same farms/market/town objects
        states = []
        for i in (0, 1):
            obs = _Obs(i, self.farms, self.market, self.town, self.privates[i])
            obs.step = self.step
            obs.day = self.step // self.tpd
            obs.hour = self.step % self.tpd
            states.append(_St(obs, actions[i] if actions[i] else {}))
        return states

    def step_turn(self, action0, action1):
        """One turn, exactly as K.interpreter: physical -> market -> town -> decay -> (end of day)."""
        env = _Env(self.cfg, self.seed)
        states = self._state([action0, action1])
        day = self.step // self.tpd
        # 1. physical actions
        for i in (0, 1):
            act = states[i].action if isinstance(states[i].action, dict) else {}
            farmer = act.get("farmer", ["PASS"])
            hands = act.get("hands", []) or []
            K._apply_unit_action(self.farms[i], self.privates[i], 0, farmer,
                                 self.board, day, self.tpd,
                                 int(K.get(self.cfg, "shedCapacity", 100)))
            for h, hact in enumerate(hands):
                K._apply_unit_action(self.farms[i], self.privates[i], h + 1, hact,
                                     self.board, day, self.tpd,
                                     int(K.get(self.cfg, "shedCapacity", 100)))
        # 2. market  3. town
        K._process_market(states, env)
        K._town_consume(env, states, self.step)
        # 4. decay
        for farm in self.farms:
            K._decay_plants(farm, self.step)
        # 5. end of day
        if (self.step + 1) % self.tpd == 0:
            K._end_of_day(states, env, day)
        self.step += 1


def from_replay_step(d, s):
    """Reconstruct a Game from replay `d` at step index `s` (deep copies)."""
    steps = d["steps"]
    cfg = d.get("configuration", {})
    seed = d.get("info", {}).get("seed", 0)
    obs0 = steps[s][0]["observation"]
    farms = copy.deepcopy(obs0["farms"])
    market = copy.deepcopy(obs0["market"])
    town = copy.deepcopy(obs0["town"])
    privates = [copy.deepcopy(steps[s][i]["observation"]["private"]) for i in (0, 1)]
    return Game(farms, privates, market, town, cfg, seed, step=obs0.get("step", s))
