"""Router + the 4 duel-validated market-layer overlays (v9 transforms).
Wraps the public-state router and applies: contested-value sell ordering,
protect feed-wheat, terminal liquidation (step 718), endgame premium dump (day>=28).
Market-order-only; the router's routing/physical actions are untouched.
"""
import importlib.util, os
_here=os.path.dirname(os.path.abspath(__file__))
def _load(name,path):
    s=importlib.util.spec_from_file_location(name,os.path.join(_here,path)); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
ROUTER=_load("router_core","router_main.py")
V9=_load("v9_transforms","main_v9_single.py")  # provides _reorder_sells,_protect_feed,_liquidate,PRODUCTS,PREMIUM,_get
def agent(observation, configuration=None):
    try:
        act=ROUTER.agent(observation, configuration)
        if not isinstance(act,dict): return act
        obs=observation
        act=V9._reorder_sells(obs,act)
        act=V9._protect_feed(obs,act)
        raw=V9._get(obs,"step",None); day=int(V9._get(obs,"day",0) or 0); hour=int(V9._get(obs,"hour",0) or 0)
        step=int(raw) if raw is not None else day*24+hour
        if step==718: act=V9._liquidate(obs,act,V9.PRODUCTS)
        if day>=28: act=V9._liquidate(obs,act,V9.PREMIUM)
        return act
    except Exception:
        return ROUTER.agent(observation, configuration)
