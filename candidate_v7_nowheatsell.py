"""v7: v4 feed-protect + never sell wheat before day 22 (keep it all for feed)."""
import candidate_v4_feedprotect as V4
def agent(obs, config=None):
    try:
        act=V4.agent(obs)
        if not isinstance(act,dict): return act
        day=int((obs.get("day",0) or 0)); 
        if day>=22: return act
        mkt=[list(o) for o in (act.get("market") or []) if not (len(o)>=3 and o[0]=="SELL" and o[1]=="WHEAT")]
        act=dict(act); act["market"]=mkt; return act
    except Exception: return V4.agent(obs)
