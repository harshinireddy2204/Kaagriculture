"""Candidate v4: v1 contested-ordering + protect feed-wheat from being sold.
Never let a SELL WHEAT order drop shed wheat below 2x current herd (feed buffer).
Market-layer only; cannot desync.
"""
import importlib.util, os
import candidate_v1_contested as V1
_get=V1._get
def _herd(obs):
    seat=V1._seat if hasattr(V1,'_seat') else None
    from candidate_v1_contested import _get
    p=int((obs.get("player",0) or 0)) if isinstance(obs,dict) else 0
    seat=1 if p==1 else 0
    farms=obs.get("farms",[]) or []
    farm=farms[seat] if seat<len(farms) else {}
    h=0
    for row in farm.get("tiles",[]):
        for t in row or []:
            if isinstance(t,dict) and t.get("animal"): h+=1
    return h,seat
def agent(obs, config=None):
    try:
        act=V1.agent(obs)
        if not isinstance(act,dict): return act
        herd,seat=_herd(obs)
        priv=obs.get("private",{}) or {}
        shed=int((priv.get("shed",{}) or {}).get("WHEAT",0) or 0)
        buf=2*max(1,herd)
        mkt=[]
        for o in act.get("market") or []:
            oo=list(o)
            if len(oo)>=3 and oo[0]=="SELL" and oo[1]=="WHEAT":
                allowed=max(0,shed-buf)
                q=min(int(oo[2]),allowed)
                if q<=0: continue
                oo[2]=q
            mkt.append(oo)
        act=dict(act); act["market"]=mkt
        return act
    except Exception:
        return V1.agent(obs)
