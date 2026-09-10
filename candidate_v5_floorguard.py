"""Candidate v5: v4 + don't sell premium at a crashed price (below 25% of base),
except in the endgame (day>=27) when unsold scores $0 so we must liquidate.
Market-layer only.
"""
import candidate_v4_feedprotect as V4
BASE={"STRAWBERRY":120,"MILK":160,"WOOL":200,"MELON":250,"EGG":50,"TOMATO":60,"CARROT":35}
def agent(obs, config=None):
    try:
        act=V4.agent(obs)
        if not isinstance(act,dict): return act
        day=int((obs.get("day",0) or 0)) if isinstance(obs,dict) else 0
        if day>=27:  # endgame: must liquidate (unsold=0)
            return act
        prices=(obs.get("market",{}) or {}).get("prices",{}) or {}
        mkt=[]
        for o in act.get("market") or []:
            if len(o)>=3 and o[0]=="SELL" and o[1] in BASE:
                p=float(prices.get(o[1],0) or 0); base=BASE[o[1]]
                if p < 0.25*base:  # crashed -> hold (don't dump at floor)
                    continue
            mkt.append(list(o))
        act=dict(act); act["market"]=mkt
        return act
    except Exception:
        return V4.agent(obs)
