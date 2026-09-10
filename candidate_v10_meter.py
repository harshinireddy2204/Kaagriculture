"""v10: v9 + meter premium sells to avoid self-crashing the price.
Before day 27, cap total units sold per turn per premium good (excess stays in
shed for later / terminal liquidation). Milk/Wool cap 5, Strawberry cap 8.
"""
import importlib.util, os
_s=importlib.util.spec_from_file_location("v9full","main_v9_single.py"); V9=importlib.util.module_from_spec(_s); _s.loader.exec_module(V9)
CAP={"MILK":5,"WOOL":5,"STRAWBERRY":8}
def agent(obs, config=None):
    try:
        act=V9.agent(obs)
        if not isinstance(act,dict): return act
        day=int(obs.get("day",0) or 0)
        if day>=27: return act
        mkt=[]
        for o in act.get("market") or []:
            oo=list(o)
            if len(oo)>=3 and oo[0]=="SELL" and oo[1] in CAP:
                oo[2]=min(int(oo[2]),CAP[oo[1]])
                if oo[2]<=0: continue
            mkt.append(oo)
        act=dict(act); act["market"]=mkt; return act
    except Exception: return V9.agent(obs)
