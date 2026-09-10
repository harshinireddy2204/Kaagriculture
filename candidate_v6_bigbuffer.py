"""v6: like v4 but retain 3x herd wheat buffer (vs 2x)."""
import candidate_v1_contested as V1
def _herd(obs):
    p=int((obs.get("player",0) or 0)); seat=1 if p==1 else 0
    farms=obs.get("farms",[]) or []; farm=farms[seat] if seat<len(farms) else {}
    return sum(1 for row in farm.get("tiles",[]) for t in (row or []) if isinstance(t,dict) and t.get("animal"))
def agent(obs, config=None):
    try:
        act=V1.agent(obs)
        if not isinstance(act,dict): return act
        herd=_herd(obs); shed=int(((obs.get("private",{}) or {}).get("shed",{}) or {}).get("WHEAT",0) or 0)
        buf=3*max(1,herd); mkt=[]
        for o in act.get("market") or []:
            oo=list(o)
            if len(oo)>=3 and oo[0]=="SELL" and oo[1]=="WHEAT":
                q=min(int(oo[2]),max(0,shed-buf))
                if q<=0: continue
                oo[2]=q
            mkt.append(oo)
        act=dict(act); act["market"]=mkt; return act
    except Exception: return V1.agent(obs)
