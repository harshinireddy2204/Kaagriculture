"""Candidate v3: fscore_cad + MORE conservative premium selling overall.
Hypothesis: you already out-sell opponents on premium and lose; holding a larger
reserve and gating harder should raise $/unit. Raises reserves + price_gate.
"""
import importlib.util, os
_p=os.path.join(os.path.dirname(__file__),"baseline_fscore_cad.py")
_s=importlib.util.spec_from_file_location("cad_v3",_p); _B=importlib.util.module_from_spec(_s); _s.loader.exec_module(_B)
c=_B._AM_CONFIG
c["reserve_early"]+=4; c["reserve_mid"]+=3; c["reserve_late"]+=2
c["price_gate"]=0.78; c["max_extra_per_item"]=10
def agent(obs, config=None):
    return _B.agent(obs)
