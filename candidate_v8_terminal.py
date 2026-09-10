"""v8: v4 + full terminal liquidation at step 718 (sell every shed product;
unsold scores $0). Ranks additions by revenue via the engine price curve in V1.
"""
import candidate_v4_feedprotect as V4
import candidate_v1_contested as V1
PRODUCTS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER")
def agent(obs, config=None):
    try:
        act=V4.agent(obs)
        if not isinstance(act,dict): return act
        raw=obs.get("step",None); day=int(obs.get("day",0) or 0); hour=int(obs.get("hour",0) or 0)
        step=int(raw) if raw is not None else day*24+hour
        if step!=718: return act
        priv=obs.get("private",{}) or {}; shed=dict(priv.get("shed",{}) or {})
        inv=(obs.get("market",{}) or {}).get("inventory",{}) or {}
        already={}
        for o in act.get("market") or []:
            if len(o)>=3 and o[0]=="SELL": already[o[1]]=already.get(o[1],0)+max(0,int(o[2] or 0))
        cands=[]
        for it in PRODUCTS:
            q=max(0,int(shed.get(it,0) or 0)-already.get(it,0))
            if q<=0: continue
            base_inv=int(inv.get(it,10000) or 10000)
            rev=sum(V1._price(it,base_inv+k) for k in range(q)) if it in V1.PARAMS else q
            cands.append((rev,it,q))
        cands.sort(reverse=True)
        mkt=[list(o) for o in (act.get("market") or [])]
        for _,it,q in cands:
            ex=next((o for o in mkt if len(o)>=3 and o[0]=="SELL" and o[1]==it),None)
            if ex is not None: ex[2]=int(ex[2])+q
            elif len(mkt)<10: mkt.append(["SELL",it,q])
        act=dict(act); act["market"]=mkt[:10]; return act
    except Exception: return V4.agent(obs)
