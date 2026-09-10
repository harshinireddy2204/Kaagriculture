"""Candidate v2: fscore_cad + adaptive seller RE-ENABLED in mirror matches.
Hypothesis: in near-mirror (coinflip) games, selling the extra premium tranches
(which CAD disables) helps. Monkeypatches only the mirror caps; nothing else.
"""
import importlib.util, os
_p=os.path.join(os.path.dirname(__file__),"baseline_fscore_cad.py")
_s=importlib.util.spec_from_file_location("cad_v2",_p); _B=importlib.util.module_from_spec(_s); _s.loader.exec_module(_B)
_B._AM_CONFIG["mirror_max_extra_per_item"]=_B._AM_CONFIG["max_extra_per_item"]      # 0 -> 18
_B._AM_CONFIG["mirror_urgent_max_extra_per_item"]=_B._AM_CONFIG["max_extra_per_item"]
def agent(obs, config=None):
    return _B.agent(obs)
