"""Shop-router 0908 - single self-contained file (tapes + model embedded)."""
from __future__ import annotations
import base64, json, zlib

# ===== observation packing (inlined) =====

import ctypes
import sys
from collections.abc import Mapping
from pathlib import Path

_ITEMS = (
    "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG",
    "MILK", "WOOL", "FERTILIZER", "GOOSE", "COW", "SHEEP",
)
_PRODUCTS = _ITEMS[:9]
_CROPS = _ITEMS[:5]
_SHOPS = (
    "BAKERY", "BRUNCH_SPOT", "FARMERS_MARKET", "ICE_CREAM_SHOP",
    "PET_CAFE", "PIZZA_SHOP", "SMOOTHIE_SHOP", "YARN_STORE",
)
_SHOP_ID = {name: index for index, name in enumerate(_SHOPS)}
_KIND_ID = {
    None: 0, "EMPTY": 0, "SOIL": 0, "LOCKED": 1, "WEED": 2,
    "COOP": 3, "PASTURE": 4, "PLANT": 5,
}
_UNIT_OPS = (
    "PASS", "NORTH", "SOUTH", "EAST", "WEST", "PICKUP", "DROP",
    "PLACE", "PLANT", "WATER", "HARVEST", "FERTILIZE", "DIG",
    "BUILD_COOP", "BUILD_PASTURE", "FEED", "COLLECT_FERTILIZER", "CARE",
)
_MARKET_OPS = ("PASS", "HIRE", "BUY_LAND", "BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL")
_BOARD = 10
_MAX_UNITS = 40
_MAX_SHOPS = 8
_LIBRARY = None


def _read(value, key, default=None):
    if isinstance(value, Mapping):
        return value.get(key, default)
    getter = getattr(value, "get", None)
    if callable(getter):
        return getter(key, default)
    return getattr(value, key, default)


class _PackedTile(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("kind", ctypes.c_uint8),
        ("what", ctypes.c_uint8),
        ("has_animal", ctypes.c_uint8),
        ("watered_today", ctypes.c_uint8),
        ("fed_today", ctypes.c_uint8),
        ("cared_today", ctypes.c_uint8),
        ("fertilizer_available", ctypes.c_uint8),
        ("yield_units", ctypes.c_int8),
        ("planted_day", ctypes.c_int16),
        ("fertilized_until_day", ctypes.c_int16),
    ]


class _PackedFarm(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("money", ctypes.c_double),
        ("tiles", _PackedTile * _BOARD * _BOARD),
        ("pos_x", ctypes.c_int8 * _MAX_UNITS),
        ("pos_y", ctypes.c_int8 * _MAX_UNITS),
        ("n_units", ctypes.c_int32),
        ("n_quadrants", ctypes.c_int32),
        ("hires_today", ctypes.c_int32),
        ("shed", ctypes.c_int16 * len(_ITEMS)),
        ("seeds", ctypes.c_int16 * len(_CROPS)),
        ("inv", ctypes.c_int16 * len(_ITEMS) * _MAX_UNITS),
    ]


class _PackedObservation(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("step", ctypes.c_int32),
        ("n_shops", ctypes.c_int32),
        ("market_inventory", ctypes.c_int32 * len(_PRODUCTS)),
        ("market_prices", ctypes.c_int32 * len(_PRODUCTS)),
        ("shops", ctypes.c_uint8 * _MAX_SHOPS),
        ("farms", _PackedFarm * 2),
    ]


class _PackedAction(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("unit_ops", ctypes.c_uint8 * _MAX_UNITS),
        ("unit_args", ctypes.c_uint8 * _MAX_UNITS),
        ("unit_ns", ctypes.c_int16 * _MAX_UNITS),
        ("n_units", ctypes.c_int32),
        ("order_ops", ctypes.c_uint8 * 16),
        ("order_items", ctypes.c_uint8 * 16),
        ("order_ns", ctypes.c_int32 * 16),
        ("n_orders", ctypes.c_int32),
    ]


def _library():
    global _LIBRARY
    if _LIBRARY is None:
        extension = "dylib" if sys.platform == "darwin" else "so"
        # Kaggle's source loader does not define ``__file__``.  The compiled
        # function filename still points at the extracted top-level main.py.
        path = Path(_library.__code__.co_filename).resolve().parent / f"agent.{extension}"
        library = ctypes.CDLL(str(path))
        library.kag_submission_abi_version.restype = ctypes.c_uint32
        library.kag_submission_act.argtypes = [
            ctypes.POINTER(_PackedObservation),
            ctypes.c_int,
            ctypes.c_int,
            ctypes.POINTER(_PackedAction),
        ]
        library.kag_submission_act.restype = ctypes.c_int
        if int(library.kag_submission_abi_version()) != 2:
            raise RuntimeError("ShopForge SixDay Guard submission ABI mismatch")
        _LIBRARY = library
    return _LIBRARY


def _fill_counts(target, mapping, names):
    for index, name in enumerate(names):
        target[index] = int(_read(mapping, name, 0) or 0) if mapping else 0


def _fill_tile(dst, tile):
    if tile is None:
        return
    if isinstance(tile, str):
        dst.kind = _KIND_ID.get(tile, 0)
        return
    kind = _read(tile, "kind")
    crop = _read(tile, "crop")
    animal = _read(tile, "animal")
    for key in ("watered_today", "fed_today", "cared_today", "fertilizer_available"):
        setattr(dst, key, int(bool(_read(tile, key, False))))
    dst.yield_units = int(_read(tile, "yield_units", 0) or 0)
    # Native Tile uses one slot for a crop's planting or an animal's placement.
    dst.planted_day = int(_read(tile, "planted_day", _read(tile, "placed_day", 0)) or 0)
    dst.fertilized_until_day = int(_read(tile, "fertilized_until_day", -1))
    if kind == "PLANT" or crop:
        dst.kind = _KIND_ID["PLANT"]
        if crop in _ITEMS:
            dst.what = _ITEMS.index(crop)
        return
    dst.kind = _KIND_ID.get(kind, 0)
    if animal in _ITEMS:
        dst.what = _ITEMS.index(animal)
        dst.has_animal = 1


def _pack_observation(observation, seat):
    packed = _PackedObservation()
    step = int(_read(observation, "step", 0) or 0)
    packed.step = step
    market = _read(observation, "market", {}) or {}
    _fill_counts(packed.market_inventory, _read(market, "inventory", {}) or {}, _PRODUCTS)
    _fill_counts(packed.market_prices, _read(market, "prices", {}) or {}, _PRODUCTS)
    shops = list(_read(_read(observation, "town", {}) or {}, "unlocked_shops", []) or [])
    packed.n_shops = min(len(shops), _MAX_SHOPS)
    for index, shop in enumerate(shops[:_MAX_SHOPS]):
        packed.shops[index] = _SHOP_ID[str(shop)]

    farms = list(_read(observation, "farms", []) or [])
    if len(farms) != 2:
        raise ValueError("ShopForge needs exactly two public farms")
    for player, farm in enumerate(farms):
        dest = packed.farms[player]
        dest.money = float(_read(farm, "money", 0) or 0)
        positions = [_read(farm, "farmer", [0, 0]), *list(_read(farm, "hands", []) or [])]
        dest.n_units = max(1, min(len(positions), _MAX_UNITS))
        for unit, position in enumerate(positions[:_MAX_UNITS]):
            dest.pos_x[unit], dest.pos_y[unit] = map(int, position)
        dest.n_quadrants = len(list(_read(farm, "unlocked_quadrants", []) or []))
        dest.hires_today = int(_read(farm, "hires_today", 0) or 0)
        tiles = list(_read(farm, "tiles", []) or [])
        for y, row in enumerate(tiles[:_BOARD]):
            for x, tile in enumerate(list(row or [])[:_BOARD]):
                _fill_tile(dest.tiles[y][x], tile)

    private = _read(observation, "private", {}) or {}
    own = packed.farms[seat]
    _fill_counts(own.shed, _read(private, "shed", {}) or {}, _ITEMS)
    _fill_counts(own.seeds, _read(private, "seeds", {}) or {}, _CROPS)
    inventories = list(_read(private, "inventories", []) or [])
    for unit, carried in enumerate(inventories[:_MAX_UNITS]):
        _fill_counts(own.inv[unit], carried or {}, _ITEMS)
    return packed


def _unit_order(op, arg, quantity):
    name = _UNIT_OPS[op] if 0 <= op < len(_UNIT_OPS) else "PASS"
    if name in {"PLANT", "PICKUP", "PLACE"}:
        item = _ITEMS[arg] if 0 <= arg < len(_ITEMS) else _ITEMS[0]
        return [name, item] if quantity == 1 else [name, item, int(quantity)]
    return [name]


def _market_order(op, item, quantity):
    name = _MARKET_OPS[op] if 0 <= op < len(_MARKET_OPS) else "PASS"
    if name == "PASS":
        return None
    if name in {"HIRE", "BUY_LAND"}:
        return [name]
    item_name = _ITEMS[item] if 0 <= item < len(_ITEMS) else _ITEMS[0]
    return [name, item_name, int(quantity)]


def _unpack_action(packed):
    n_units = max(1, min(int(packed.n_units), _MAX_UNITS))
    farmer = _unit_order(packed.unit_ops[0], packed.unit_args[0], packed.unit_ns[0])
    hands = [
        _unit_order(packed.unit_ops[index], packed.unit_args[index], packed.unit_ns[index])
        for index in range(1, n_units)
    ]
    market = []
    for index in range(max(0, min(int(packed.n_orders), 16))):
        order = _market_order(packed.order_ops[index], packed.order_items[index], packed.order_ns[index])
        # Market queues resolve by index across both seats. A no-op still owns
        # its slot; dropping it changes the prices of later simultaneous orders.
        market.append(order if order is not None else [])
    return {"farmer": farmer, "hands": hands, "market": market}


def _native_agent(observation, configuration=None):
    seat = int(_read(observation, "player", 0) or 0)
    packed = _pack_observation(observation, seat)
    episode_steps = int(_read(configuration or {}, "episodeSteps", 720) or 720)
    output = _PackedAction()
    status = _library().kag_submission_act(
        ctypes.byref(packed), seat, episode_steps, ctypes.byref(output)
    )
    if status != 0:
        raise RuntimeError("ShopForge native policy failed")
    return _unpack_action(output)

# ===== routing =====
_MODEL = {"kind": "mmpq_multi_entry_v1", "default": 0, "stages": [{"step": 144, "tree": {"feature": 23, "threshold": 0.5, "left": {"choice": 0}, "right": {"choice": 1}}}, {"step": 648, "tree": {"feature": 71, "threshold": 9888.0, "left": {"choice": 2}, "right": {"choice": 3}}}]}
_TAPES_B85 = 'c-ri}OOIUHlBGAVUvY8AF<^K+NNUDRdS?=snL+R&$5o+`C_pU;5L$zhW`h2^n4PJc5&j6bWBXgSY@hH!KZ<qI<2-EJwr#c^|Nd`(``f>N|382G+yC=F{_ns2?eG8FfBffv|8M{K_y6h7fBzr<_UYZ1FMt2@fBdgk|NoW$`+xkO|Lgzt`-Ok~(|`Yu|NKAx+yDLKKmP0g_x*qW!?%C__UZG(`)@yf{rlD9|Hba-?YpP{bba%$|KY!09sjj2+m9cCpGn@-zdinc|KF?gZ}HcM&tHE=USs`(-<|!jpFe!w{(ai3et#A3e*N&vyS?}N<HPRBKWx&!^yTO6_S31~S{zGX9=<&rOULi+(}y4b@$J*$6P|sj#|hx{RZjwZ__Fgid+_*wt(*9pJoqzzeyOGJHu_YCH~GW24<FzE_Wdt^{q|%nh~D2H*<<PZJ9U$tBJ$(AAGh*=Jhx3G@2%oJ?zUgPp1<nHcYG8+{>!bGZ0r>s%Y9GM((~`_^v?8UyM6!kXMfp#eE1dHmyWJt&j<OwB7XgP>{*rn<&p39BpoWh+x5VA+fN_KO>p4Ng}&+T-Pi4B?y{$A5lKY<<@XP@^tA==H~5Z18Aew+_=5QH#u9(`v4kv6Il;R)+~lX&6;iu%lU$O&jmN2=ao&IObWfkHa{>$g$#}83<Rctuw~Q>0$Bz<z=TBMyg3PsFw~T$Q@K$U544EuNZXfxKl>1h)jCAAANb=o-Oj3cHT~XpfHw$^<+Pm47-{H)B=90Nes@&99Q0J-YTA1l6r{Wn+D`?N}l0&}u^ZowEl6{2^IVAW_dgPD=9n$sXklf4ly`uVOPhDl2ZN{^S5aWO&Qwkc*3$nAi?--cjT;cy|n^{Egd+jwh3!f_0<&WL&UbC?Bp&mYd-2V9WxBs&J{Pn}f5C2QzSRK3h(|^c>AITw^GLLa&da~p{AFdw{QG1X6{E0Gt9Jx2ri`%|S<j-JVI)|4?741=QCpkYKSjcdkie79un(L24p?Yy4-V8azR|KN&jU^X$_oGViu`U5HQr^xM6tT0-<NfhvhD7ifFj@B^Q(ewds0iQMJ9s0VsFO8YetXGX$9UGhe5%W*x_qjB{rA8A;Z{SZOgCoi{KmxvL8?jYU|&hL*i<vwfWsFwAKAe*(7-mlRz)j6$=@?PykZ{`rjr!XcrD3<B|a&>d|3wAD+>E%fZW)5Epgy4C}>K;8Z$u88MY$~6l)+U&w&O)=;?oc_xXRGfSM!BDY4z88Mx7(XAT2rX7F=a>WY%~Dp1a19LQ=4n&+?`p-xo!AX1m?!>zJgOmZuRhLY1G4qB0q<aIm;-CkRgwC#b?%N037`ShqN&i)3Z$&kXeL59LA$4i$XRL@b>O>@?Wbqb}_Z)<UxQCvznhpKAA59r|b6qIWIzDtkJFYJva*>+^xPk2@LM28-(oZa?RZX$yyxYFXC!U-DDK(<Tr4Q$FQqy5{+Casj!FKTm>X{B%~GlKa^wS~h<mr%S8OMaJh&y=#U!OOIHsr%R~iJ2Nr8w=WTFJL;xMrz5P*8>w^sVO9_<OXjECb0WPk~cHFM*IjhIJmq~3@)b!B(Rvv>LuYs4k^c4B@!exUDNtk?wb`UhsD7+q%{IlytJ~6ctm~$RTQRQ;Y6bmbbxJn*)z?;rH){p8T#ESX6QBW=k<)ery0XqB;p)ri{>v^U5dq&PE2ei5C1onqNGxR-Dj~WvC&nszNC<i?z~U*;d5jr-vkRKU-cWVns@0~hDpz=BqP(80PV;Rrc%OmeTG@=NPyQPwJP%oF>kRn%L}14Jd>dO5ojw}9$Z&1U|)(S(-F07#cow{icb}rnf(Lx8J$H%StvMwzE2IE&n~u&KfE=Vnkge0BTFbGpq$2c4J_g7eE<33Q|nn#2my7sCNgS?BE#ek1v7paVHG&19bGQ1oiwL7G2*Dwdtdq{32l=72j6J?(nt(OdxhKFfh%;>rD8X8yjv+zeKr}`*!_~rvMU>0Xw_KR(G;c&maEisC>%S_3HK=@z9jbSIlrC4hkx>?>47-0*NH0s<8AmaUq8Rw{jmM~`JY%xl0+}*-rSmK47un<i82b2)gJDzdD((T%g6)rNrgqMohH>LS&OiB5Hlo!_?*b$O(#vRa5BG9zc_X}y-&uJLaB|xRNs9LC02}SpT$SFY~P{v@gBW)QT@!+sMDY)ts=A}7N;|<?yseP?!>w}CEWQ`b*W*5p`AZqP;XPLU1T-7JOuW(6k4V&|H5m-EY>HMJWhwwHTL*Qp50Z!z~kA*rm=7imvzeVUNe_kaam4IP|(Fg{z-kj=g!GT1XLa#o^E^hweK@n@@6I@IWhx*ZrOjQ*RRgs2Iq9X04%r({n+=jS|H}5;%l4y0|;hGsdW_0VVRiKO#ovzO{r8>*WXjcPg>*))dZ|Z@5f!8$jnwWy#L|bhmY@n`~D)negjE#<m-=(Iu}02^DMtJpQLNQF37PMBsiAaOd^D9xu0X|vnD0gq=wZ)Keligp1Qmzf+zKj(bHZB&!Vh6pmN`gi7c03=u$y~wylC)A9C3b4#xKGShxDiKP)Op<WTrZ-C5C6U;YXA!t_XxstRY_;hWtPQs?b5?AD-8$)+iM7seGdcK}Nied5l>!nLf{k1P4iZM>>cguCNpR3+xSC~4kcN%OkNhC7%f<qmM_f;tKusKmXd7CietY3hs3wl2>?f7|m^gPwg@lc<JO?xsh=PPQ>Unb{%tYt78Y_DAmgqlFNU=6Wd%x@ix4MBC+sqN!_e(xV93$N%&i>*_<O+Nv|sGcrg<_eH;aO&YsFLP+s(ui8<=-i>9IjYVtOCvQV)x<t=?TU8&w3r06bARhyj1ZB-wDxdy_C7QRXR3;R`X$Bb0!xfe;DICUm<viXAy@udVQh+(k;W5^vJA`6Q$bO-;5x906c;zY&?%_$uV-VY_^`S0{miqOst7}Qr5~(A@f6N00)rN&7UYD~2*kp?i=fw#@0gsTj(AjU0Q??wg|1|Rv6WXkPxgv%3vIK^X;0E*(lHjQR>)HZ*%C=Ba>=mOh^3DLfW50W<bM_K4s1lllVyQhVx7SWv^mS23&k|iiDW27scv~Uf*>#%xuqz_98kBF@Un?;tSBpfk>eq&Bm7_7Ph&gPaZ=*j}G(@rR7@jQjkzEf(x}pQ}*q|)Y5U$Fb6CqYn7kO(dWCH)l3mBE_B$5GH3`wmOj2-n4DJfF`r-wN9Uf$~+_zSVxQ!4G!-g3zzSrZN~R8eJds_=ch*jSYPC_ypo!*RhcA3pwLp^U52Yz|M+2hVpsAR~GhaQ6t&;mgn4?We|CrzyQ=QWhCi=Q);2{`dlFd}Q!3%Cwk<gnW31aviiuC;gL`y$yz3ZV1^`{wX=C$d{3sZ_2`b3`~7JLq!UXA>SBUjHP@k{gTEb3pPbXA|dJM5GCw)x4+8=lQk~<G^6h(>feB_Op<w0#BT5@u$sGAeoJ#QrqE-~==q>541|ngx>@Duwx?#eT?>UAM533sJUIe{)qQ(%&V!#XZGziqvF5}Hx~|q#VHY;H7+QoVLR2}eFZ8hn>M09?9>vT^RSH*DM3ELvboP$j8~s=Jl2=QNTMjNoGI9r#cNDf;aWA<2v$_^0zoP^6CjFZ}-5&PgNdaUs$>&OHiI(z+hEC2^(Xt`M&$QZRH2&pVe60bk`EoDx<||YH9!LR79J^4iBin3)9Q@F?7p>!Iud12%4&XE761yo}x}mTN-TIBsCwm;z*vo%Abrvvua*F*>EF%tb3tBqD!|nL-{w~UdAXS}%&~z~6#^>XU=%-JPVSgWiHiS+Eah`<?HXFQ3ht!y4_ASIYkdQ+izL}I0$d0<5dY|s^KY%Z%5i+qMajG%0DvT^U&MXn`7AAV%#x6VupxE;xU-&@m_O|x8jXRU8?VZRO4GSBxFnRT$GO6%AS#%8MPfKfhD;LjxBRU_Gt)wDnxO!D4T}?05vt1FehJ8;$@|Z;pw<DFMg93P$@&7boxt2;p*Dcc;qAL-yZ7JoB`9JEegd)il2kYF5q}x%3fd|a|0b1ZaH_8EsmU@eInJWdCtEolaqbieXilPI4q2s5Nrh}yay+q!dr(`gIpjAT3m6RI`k{h_D!_~4H880r!q(#rrd__Fq><O^WA?wB3=tOmM<sk)h1K;0uEub94v$fFE&K;vJc=%Nbyw_Kg?DXIMCl{wzGGtB-D}Q=;__7si`QG#lRSSs0a#;*ae^<LY>TvTnBrf3Y63pJq&_lIPbRk*RP9F^QeC1&)>19c>5_mAun9g=QrLeG0e#(T_-Ds01mF$e7FyRL?Y3%X$NB8T3*!Ij6&nJR`Hr(Q&Lk=<7%SZ$UF_2qHXt2m5_K%VaTP!;KvZ5iJPYezkNw?Gk+pO)!hhG=^X2nvJV33%(*(EjeE#BZ7=?NS#wf7(YUbBXvC~+)U=+;Z$z+%A^)a^mCDmS-X`f6!FAMyRsy1sS=^li)$uyaY!UvKK;RPM$Gg%e92MLR>JyJK#__b-g@49!H3r}G~}&zAALGi&JNoq3-NPE+s){B`R+WQrsNYkLSkeEab6{ck@$L=cX3+ydNpcRz6`XFGQ-=nLs7QRpKt37gtlhRoJ^94A_kq<Tq#{9>$ZBGJETn&Cahars!3^WVq<CHHcR(s@}D{v*A9`u;AyaZ`n0&NG0Vg?UhUe(VXmKkQ3CEuF77K))^6#)t*xl41gNT66fg>VjAho(HF{w=HVh$3b8*3qP_Vf~^U;t4J(XVH}h2%y%?7v{WZZMJ0-aBqgxvK+1<SDSUt}Zwc@AX5Q>d7MH;`kJgS5J|ZPDA1QmUv2t$^cLT>_GJfj$qvW4NRr&=gyt#~2{~qVQDs?g$=g^mc-gQ`ltHGoG_4!SIt!(C`q8?c2p$4d|TGo6-_vdQX@4NJSlItw>_*ztZpKxLy8D0#T85ZcOg1?pPY>5oY>RG2veZ`0cFme(|8J&bX5$LoeA50Xm7&D_hJV`zJv|ZNdnH)>@x`&MRbZ#%~Oik?$6>N(O+bF?P_ts$n<*qaUKS(ryKyyZ+VMTP>0k$y_z(dL2osvq4DJ-HLouEk|i@hz_V2k1@uz%jKv^w3fczKO2@>r~)$1-%pS@Zmwafx69&sjn`ly+qUuxX4=JSM~LY?(R<q3~&z4Md_5Ivu&$?sZ*wjh|pxF|x5wD$J&itUvlTrahEjw?OjbSP;UKGh5{4iA5}r6kS;gi!3D@hLvPOfsVlj%vg?M6;dXs5m}<vfl18ayEhSZOKLN+zr=!s2O9{()ub~ha}vK6b8dURSg-f%sS1mVuUHV#%6Dyj$?6U|Wk*~mvLD=RNztgrhvxJ-7ljmYhEg)*fBk;TZYreeIg4s@6bu^g^vvK)s?rY60SpIbwg*m>R^^*m(pGfK$~q?VGumRxA8lE-8}|oVMxfN#&@!5|{84GTl<;%kmLCV%4?|-0&=GBiR&z;Ls=>x5->cO2zUp~xlat$mjJ8To-VQEK>p6Q}Jb#;9)d_BT2N7}Zswes_?<zS77SaQ6+v>-X-DA|{z!DOYjGsGjkjM(!VGnJq+7`9gh%2bllBk+c-CO$&;2qHch0fi>!{dy8+X%6D1U$EQw}0JlQ6fjfplDcpq`S2L7T=UBsh}Gt$*Qmaiz!VDBpGDuEEEC>k<-ZOX#Ll1RE4=WaUnPdoeiXBc-Cbr+^P*{D%jE4iriw+f9F)#@15srhv=}uzM@(0-G3mL_R1}AEZcDSM9Xc{0_T|nTA6E(0fBJcp30sz*9&gZg$2rekprYq2`@$ODU}+6y)tsEG6aWft*h6jyMjPb9gea61fbYvJ3dN<OWi;^gVRH+IX3;ORt74#ZG!pB;nPzjoE(r0Y+}frUFz);op6EN2nn4+kgt-Aq2Oo1txJ0l=ydzPK}Xew)bx-Ja+Y+m5AH7u%T09@BjeOpMdf2tn%a~5aJ?uet96-YHAB$H0lcp-2>LRdea?O`@BbmKDl6E=l!3{xM8z|fRINP8Q0N89UnlQB78bWWD9wuN@!H>9xw2COhK3QFfqry!A|3pEunl}l&9FVT2AzJQ17dQrmU4d;c>O-Mg7HW}kppV9$P*4<lX9J;r{zsWpGpU8b_@bs`>Jp3Bqh4!tdk1R*fD!7a*tkdFtl|MGe{5ut~_Grux8$|K__t8%Xe$*=9t<@1(7lml4CW59ISe#6kxa|HsUpc>H()AOZDea<3qQ_3D8gt3|7#V!6c=~6jf?6HX2~oD>6l)*%VTRq{>T+yeg}MgSNU;XJcOxX;4>ft+<#v%`%^FyaqFAKhlJH{zBk5>SL(MMQzb#I~N%~_vq{4xp;E%cJ^&TqM@MlJ0}4(>=B+tcNMK?HMU(@%B|oslo~A%(0H!P=jhFOq>M;pkV8c^P*wPF^NkHT8`ygq#ps8?AQz?jt_b>6afUXQf=WXWytZDVlDhN5%}ytY_4a&q5$3}j2l-zu^!Yun-BqTR4_6(A#e^PIgZICOhw27FIj8-2<DDO{<s=-z?7?}lQAoRkP3DjrgA4B1_AyBbHn2~JN6F$q$PtIjkE$f<m86fy?n}W;Az(uWcf?qiAeL!R_;nCX5(Xfq{TlAek;`oFIri;RR0xOxif#ibev=sKco0)Jh9d~uiW;Dtk~@q?XHG&*RU(eUPe#hI#xgki1#_I8mLqKC*sF(guTWP~3141iwFoc*u4XH0*<F8jSc^funQcte5qXR{oNWFR&J)#cF{o~dq92e$FrjG>^#JSZ`ZC%Bh-U6hbv0)h2mC7+SPM9GdFxd#>NtaH+4}ils>7JIipotsH_q>*?3fU3+XyEX#u`q}RTpG>!|tEIJ>$348UVDFFep2qwJh#(s{96pIH^~9NoPj@P-oc+$`*}@(iq#)d7@(O_MpT2-rj>tkf|FVC`q6%8&R?ICoPXIyaC_dPf`+YHPZjvpMF{hi?|RLPFz*9DW`m2DjZVs$O{ypwW}f)=*=-GX2ETF;b>?DQg#r>e&@t{y{V;5ppws#<+>J#*+6Qd7*B>ksC7{(ccSr4Ls6xDa0e#;qQeD7@qtqV&XkWt0jiYzix%k*2|yJXasuWP6%v)Ca)N1KD~W)|i39F)3tJR8BcR4)2ga;RsNhG2<mXGYig~+IqJZyoqva^t`BlUC;s&1cVK-Q-xb!QImOSBUyHsfsMH)zWo|!_|F?dDaBnl<f`8f%uL8+Q&!D`wUkvJn#F_`pa5D@nKQVROlb*`^RwjEqu#NiykL(#&afnp35)KDW}Nm$O1>gcGpWl%E=Nyl;?=CK8%kTMw(ZY=}Fqu6A$`{Ov-ITasssM&hfxv<^TnxPSI{ijpL^<7_ai#m&<0!6-h4W>R$JG!QFRGRR^PiR?7(yx`VxDt0Bd4UEC8ngp&c9|$fQ)PG|YR7PmSg~16po`&4L7lcBV1q${o~1dqY0GHRdP~pG!itq4YP!;TWV_ftP$P38q4uPj?=HbheEItM-R_6&=g<Fq^6zh6nDKSz%Sf?l_|A$vc+U4=NFLPY!f<NFmO4+7+i=8yWuc%4zt{S+D1T?sZaT<3J2RLROx9mbLkb(&l5^t}ht)S~icKD)s3jIeLKZTheBE~or-2nd(94{Y<I2>!X%BbQ&a)d0?sa2FV_+0ov7(}KXulM;Y*n&Oe4&yZ>XVBLJ+PD92{g_k=(QV5hb$f~Pu3@&OO&HjGb_S@T+8NgM$G37MEYKnacB#1RG`0z?1(}xeOg~Bb_c6oOXe02<1n6k*}0*b)sfgbE9Nv>=ZLO}&0}FDqpB?sGF3;0Nmi7mf(f@8PaUA^p5L~}V>ySEa;sYhbVh8#LB5_D(18uyS3G;6{jiHx9TF(|cpDSe$2J@r90S7`H0(%2>jZ}C*1&x_5M8_;Q2<SyMb!e{tUnN|`ySpS4G(c7a3jv*_05b9OvuiDk(P(xwUwU>zQHrVraI@b_>d+PFFBxj;6Zyw_CY}2mp9ie_ITNS=tKc^-xH6G4jKe4mUKB<(_+c`*r0Jk;u8#hSSCe>+&EVk(kG-no$;Nt>M`{FSjBlXb=uJlQ*c6)I)H3zsI#wIND;%(+!6s#p48G$E9o}P8xoY?*C|dQ?y#N9du|>6ZWEG4o5+u%vVA)p_w%{?ybv}OR~1?1g{Vt+9qC~~RnWLs*=_BZVd<L(vdun&`+Nf+3`}{G_^E@=cCE8!_}T87b|u;2FGaU>jHDf6tr8qyDv6^+lzP%I>$U-HXy`lb6DkH7O1N2JxHr<rOcDxNnx3Cg6?(H4JfBdFnhuowy!CZgg$uNsK8tsXUA?*!g_tA-@V;*gxDB)%C_7d!fqwMmR>5=;b;EzxcG!e^mPsV5%P^K~xk9dE3n^48jZvxf8Bi{ZCb}Dk(FPbIC}nCP;Cg(c&1Y$0g(jW98ab-)@xMVSJr78-a(hkpAPg-4hmsg7UZrf~%~fpSrjjmqOms^X3et7T9jtB~+VZh%Cej6zW?i*x7v!|c(58xkQ^K~GJW@ns<?d_|r<^@i^xk=hCn?UzQ3#C!in<vT8VP7tjLNct>Wj%cn?YIAL91~<oT?-ilV=Uz$*Z1`3eWV*K}+n>qh-IF(-~;W-ij$pqw&zyk^|LguWCpihzK7I<bREAXmXdqNX#KwW^ltO<N9B3>JM}o%S13y1!)tp;NDiV6m^Zwy(czu0vr1nl7Ca^FdDkepp0EOEV3k=5#hNZ!@mn3aHgwj3g-c?&<XO?ruZloBY@lt{7!>gSoVT>`OH&>iF!-e4&IKbm1Q_aqQ?NC@-$BHEm>^7Zk<CN2!*d$R72TTvZT!~jfQP~Taz4KI;KoH5~vjtV{vX3!c*Aifx)Qh+;j1aX#|HAhGoibasua0i)ef`Rhv%(fPtj1&S1eH25TNW+Z}~GWR=O(^9_$HqCeH6JD2pwbp4-A3&cQn>+?vE><s$Us00Q~7abn{mZ(>!wD#myJ_g>mAE2jGw^k6NQjue!wUG)w=zeBZ^N60*CNt-B6!*fMu*8KE1TL9Gsy+HoDQiy8=^(%Jb~u2*{3*acyNiD({dMFOnn5Nx26IvlbV8ZSX=PVj%{#`oFsF|j@(T4lB=j0({cdPB(mf9nI!|+F6vw$31>s&KY|vS;MpzKBk}=y7N<v==L>rNt1s8<V0D6=gK#B5v;>mgr7FlQ7qBZS&1vXdXyxf3<;Vvy}TVl!Ds!c(=kn$Hw4NJ$QH&R@pa*x!74mNK_B6YkW5{AJQXl2R|$U$DA8{L&6Z%Vqo8^ch&GyhpHeKw8fqQc7Xo=B*-I-bsj|2WfC%ek?S@-FO$*wX}!VnSI&0!w+;0Y2e!24WZ`cbmwICw^)~M}CMquGgtpKrz0-4z-{NPQ6#?ZBHa<Q5!RO>LiKlBh9~hdo*f$AP0^f(rv0+N#cY^7=Tcp&|tNwn9-#=fI6T~W0`RSGF0-x#~W#6l0(Ugbjulr+~&ZV{Xw-t6-rVbjqT9qZIZ~F&GJiLoJ*k)PmMOjTbNmlXES3ds(dqkcu&33(2)W9L4)@u@rr%rD=nK5o)@lTgq=E|$u^vgcc{#JUFqTYTLWc+PO%cLch-wk>H%-TqsrYn=_pCr;WPyi?j;Zpt876YGo1gWwO`6E$EcKTFij^<>-B{$Zh)h}joeiCX~-}_iB^RGpn7fC7%gx)nJ<+|mK3k_E<*Rg9A<!9n|Ex^?<#x%2?Fak<rqS?>_wpuxgR4AH~Z*8hl~{3VnE$m4AzP)ue^*5kl_NH;uUZ|byr;&p+!Pmts@l89l+K?^7<q;+RAeqS$YILmBbB4v@+WjxMjEDhb$<kqj0#s_I)wQmRws&w`Yz}-}a;QX^eVQ%$AVkK({<8tRAi96b1XHd@piX-!;xX!GP%^$8(CrP{jJW)^MFJSEZ9cPPCl2y}KuW?6wTtk8UdznNI&ZQsUXYd;w9Wc&rua0OZ7Amd7fxJioSUIRYdV=e8-OXSa1*GA@xEw)<eA@rACOHk#|<{vzy=#(FOBV@T46DRpj!aMxL^Q55q7&y!7aL39`dkb^|<whZC^Di685FYj{D(~@NhQW9{z-DIm|$xOg$N^P$eg<G^>rsauoDds|~UmMd>eollUV+^3H32d+Zjx{q7oM5(!*pf+Cf{heUDJ~scdY}hE)QA`42*8vBg+p>rW}I8|1*OvHL{zj+%09ZLRKmZ#(trK-2D=8ZT$#QAK7;?e#Z&?nv|!H&l1e<8ezumDXt2ke7wId7_tsSXbHD+mNy+6v8DtXO*FHfW@+@S+dJ)O>dmHJP;W@1eNfuQIc4Zrztq^p_s(dy;OMILWD}kP7^yOpF{^=b;J=R{S*wR%%8UKs(23S|KofQWPaDJMDcD;9S>33V*t}xQ}b2x2ON(U}&$X0>6c6Vh|b*}LU&q~#i4H{GEWW2&@>aNB1m`iCnP+V*OKDwz+E^1bg0-t%eX{OQW1qVxU8kH?Eosv*u^H`#u_o%wlFg;ITPp&iGT?eoAJX7t$2R(6BjqVLaIIQ;oyG#9!*jG*TfKyU6$=FunChL`I*aFVMU2|e+Q^-bG*Bm`JI-o`9Ny8cq<Jd+Le~KQuJaVZ*CXkUCo1KwMAuqxysM7wUBnWDZNg^D^*X1Zz6C;}kdBdp*?fvG)z};y;o!__vvC0ArCebPtmdLE?Kj<{vV}^z9lw)|X{D#+K$W&I@H>jU^B1(Ry)xxt%H(<K1cLAG)#AdM}BLPUsI>cAg+3*=C*B?Lc);DB!Ypv?Km;sWdp5M4vOg-q*8AaU-bYEjkqUk&krDQ(y{=-k5j;R^I&fsBTgiS6sWuO&{EPXq4Xr(p~sX6<eH$|#}VZa(;U<qj1k?R5GecHTqMl!VGcC+;1ig;9Q4+ms@r~RBg$RzZ6Sm!32N3PD@@ujn80W|>K)X{|!JCY=meakGW^;8L;J+JRuHhxKZwfdA1UVcx5TsU{QZ;@kDH7T9TP^O<nq7*%%gz~K7K-{)4h4F-4zo}5)x|&zrGxo*{N|@oP)BKE@!HWBK7CjURvOJ}F11ncGcM``>TQRe}6eU){8htAzd~P&^&j2pw!opNsRfIN@axq$1>fKZ$nZS3j(PpHK5*O<A+rgkSI}9f6BX3f_!&ms^Gcmri7077?gG|~Rbd2!HVIDdrPQDDL>fdY9?q|oFDFOhU=8|+OZDU7g#dG~Cv9X@|t+wr3l<n03SBXAP_TGG=2c+njY4lz1AjPMip8ZN83<KQ?gdBN#;V&pi9vzs<jyE1Ti6c|*1Ng~pdFK*Ew)+r<TEBOf>DzAGRg@wJln~{Covz1$7EY`Zxd$Gb9Bb(gByXz^5r$GM77?fp1i3G~bn0P;QZ(p2ue$+@ZB7|DW8(#96u<-LQ429~)D|Io#l;O;{Hy)q=#C0o!jfJtE*+bZ?4<NaL;LPwAT{<mS!)`hWtR@jeOGV!X+Sifl{G8Zwv_?Mjk98yXeaEP22W;greAKfp-US#Ehr$;1mw`IGNhKyb|=vo8WBR1f??1yO3ASRsUZA;R05BY<_;3Jgi7zL4~*)g<`iU|>{v72p&|KQu^)>?p~LGlYlxu$Ex%cWBo4?KjDUyt*W%NaSkRi(S!ZT`IoLq&YN0{3o=m|g-EQd_skBwDMH4ow=J9r=0ug&Rz!JG|yoUPBN(xGb_TeYauw*k&U9@k}_ohj>cc66T#)0+J6|ymHu?ciZk_loa*P}wejhqkXF_M!%mV-+xVC&=}kZdh9&~8K*lu6gKr_W%$W-B`DegFC4Q)3TOUnevrA-yv%V3=emlt7aD*OY8T6AJCqC5Qo=;&F#g)qyPmzqx7%7GUdzcJZtVqTOjNmSP`-ox798R_M<B=Fr2%QWzL@+XEPtD%`0#RMWK9iDO|a$<BvuQLxQ|QbISP9FYz!30s~Mlhfg1i{kRUhSDq8%k(8xuE-9qFw&#0UVV&aQl)=SfuXu-(H+QTBy}Nz`*YmZqR2Uw_I@((5guO;+C;juUv4WvBBasHl<mA0dJ1j)fYOd85TrndM>!5d_8Zw1Y`fX5s}cMnF%JNx*@4qixrC^k8bez8sls8Q<(QZwz=`$bTeT;oaBz=)2Yh?VtQJLw_M9j-c2$>~ILVoYnFu!4PDz`{k&EbZxbX(1=nllJiwF2x<;X3^YObXx2E&ELZ?S)rueA=h!nemmxfg5DWDRG$Q2S!$BLqH|F)vI&#Z}9Djymtk0p`mIVCxN3RYr^Fn91azJJ&ElNJn(p=NaA)1Z@XyV9q9y;=Z!6Nv@g&KX%Ip>bO||_a`$1B;-(<3(XyiGPk%h1ZVotCq{Ap5q4uwVSi<~VfiwO;S7f@Dj3s2>qL@@l+YZ9HT;4A5klnQW?nB!Dk^bC??Ui870N_Lj{;B6C5m3@6nJ%$b&o@I6vnNN@*ZZ#tfNkr3o_QCOF2PE@~Ro=4qCQgjzJaQ)mR<@sLF_5CFeI#Xi8KvoD?%}fPbmdXB6-v4l~Z1iHQ+aA0pb)p|hP1-6s|MH?{`RV=22Q`A<+}v!YQCM(j`DM-a+FCzymqBG%n;aAp_mC&7(EMoIvP3{X^kf5y)b+?nd2oc{Coz3xElW%gnO=0r%uhcly`k_Z*!dXJEPgAh|8L~L8GNUUsY`ut!Ac+Fsqw4i?*-Vj4b^J-h6Vu#=kKANi|@K<E6VZ+7D#xtRE04sfq<DIwl$^ht|Cp-DI4MeDUPCHZYr>>`GkfNf6&G_uEX^xT|2D=_XIrcJEIgjr4J-s`pJat&K;QCeKxBOt2T238`xs$8?sgEK9yGZ0eHOX291RB~Jf%hgb&vcniXy*DF4ngyejHs0y;M>m@$BIq#g;6Ox*(Gku!NimyB10~datv=1%lpI{*-RDu6hU%Ry=X|ims+kR+9VoSTe>GKvtJyEy2tGw7^@3QWjX9P9j={TV&h0GJ?{R%7+<uB=&|F3t=H%rwBR$J?1M-lvoRyWm~Mm+-pFPaA9K+NCdp3X@XDW*TCqtjHRK7jD2g$I`cRb2U%eP%Z>Jh#O>M`8l)s@E>|Ls4S!pK2)+2kK134~4Q_FriG>UC5Eux{~!i7{y=(Ja?q|Gs+gGCe|CB>buyLi_+$XB>+pol!Q;W0d`EQuVcPJDe$Mz-ds#Iqsu<Td0hQoAAeCqpF`+P2oWOJ88tDw7sS6Bxo}mII?Rf;Z!Jz7BdzcZQVJSs9Dn<vdP3eB20{U&5{`=~pQy9W3FWX77aDi7S#)0M^}jUu~?sVmJ>Bgl!)=Owebs$#Fx9=vKNcI*{UqzgdxHU%wEQ8QOo*ac0dm6ML3^#Zoe;q2g?()KKZSrg_s$?9zDcPojV-P8<v}NYU=S<La-Q2E5Ve2N4>qV+}43W7BnS0!`Z!d-ZFAG55CXVdFv{r7jas*Jy7-0T64%;O;`b{MUC|OpvW8$x*81t@U@7Y~p+)fpmpzPN2NvfSs)@+IC$zal0DUblK{4@GsXIw6Thu6o5uMN5u}7DOmg^KJ^0toq9CtYQ^@YV{2D%AQ8k+imvW3zLe7Q;Ho>;ZArC3S432|Aa%>FLh5nS65c4lQAekxBuNzaaxL?go0`~?EMFYWMIjxl7j8KRRnWy(z4;tV1(#MW;U7m$ezja?tMzxTuy;`?(dj)2GtS+Z9DKVHmnigu!d5OMkq;m@zrcNo?c0Ej#g=f7qH-sasopk$QfKx}OM=ri6)oi8+~i5Y4|v@dum}g5tTGoHiPhI#6Ec^&NSL7NlQa~!c2iDL(3^3{VPkMskWw%2V+g^Xb$n`cW}@$8R;wX#^%Cis$^_)Pe0<l1JQP){({<+^oXQqrLI#JMt0qM$Fc7ssg3*bW*q9VuZlY2%B?;-sD;7?A8){yvabis{slc-NZL*u2>CfiWD;I}Seh*{4YjXe$d0$0sn%P7F7wr$ktHCBj$IE4c<B6!mQF=taKnmgnq{mciYk;8y<MS0%sV;1<WjvID=h;6m2*{Qok0#@^`P}3)QLd?JnTOy1z6TE})jkZOMndc0u53M#T+@k7L?xy~X+N2oAO}qPV)OZW*)|yXONM{$Id#$awnsGP2HaARIZB<6{aDcVsM=yoP&vU~ThDGFMZpLM7Kv3wxyLYk%jg;?4?=@&1o>rTfK=KRpq0(((<BZ-ec0H_@`;4V1YF-2RABw|@!gNxGZX!r@+VxdE5{?_(fhEuDto}j>M4y{Jp%ds2Mn>CHXMwPK+lHx?+lA-r0*mA-imgjO<#Tmc?xpa7NB=F5czoN4cf|dD7#UEVY00TSK8#QCDZA;Ol^DUDHvQ0I-C(CO$FA)FH?_)-apAF9<b~zk-;NvHWcz67#}dWougGnzTAz%&)8tVs-UT@w6zXnDAxYv0P7@TA3ZvULWvYKO(lD8o&M;81k}P1*3lKTTt+q{B$}9KEIld|uj`#sVH5~@#Gl&&rjv{S>aE+jyWJ-*y#M_0$!kWdw0v#6Ng25^1_x`t_kfCK_D886><Ae<ZG<JC_T;ww6!MyGtCj6YR2e$=&bMXA%v|p?EQGPWdi4rf%DLY;*06f=OGP~^yR4##Nlp)c+L^?xExb>$QvdpgdyU=Zi5+fp{<T~PszX;z=sHMV6=Q<kH@v4iJ!&D4xo#3^E5o#lr{rrUk*3I```p*-7qDhSgYDS#8(c%I;|O|!M%n83-M#R#!@7E#TGC@Q7*`<Ijt#!Ozv=7X8kA6BAmR_-K74%t+m8>CPBh7!Vgq9DZ?+EzFfWujtCTa#VA1X8?m*$Gu&Ev!O2uX?)SHDM#G($6WVR^gTC<rL^~*&~>`*iG)St8(-Lc=#VTj-t--F$Z!bJ-)sGQPJgD#0>RS>!lqB$sA_cS8*c-Ye@=qUI}(LKspv+U~u?5CzTYudh8I1EW3I3mk%q?rr~GsG*Nf#&y3wZu9bRf73+Q-CM=7xnv?($+z(Y|_Y00<B(hJGzK{-vkArb%{XnxopVL+}O-<0JhvwHzoT<aY}F8v=N&e{LoTR>^!^fU{$*1@jjpXCI2DtV^d7i0B6_IWBH|U&?mL7CmJQjmsGe~cZ}w+V1{g^Wu(_Iw9wb~q6z}3I0#%3#8qDo3WwYW=p3cmX49oeK)xm0HaHU4BZL`rC?It|zZAXcf`Z+)ae1!&c;0u}3cY;;tv}7;zLdsknglNbe!fh&#d3Ej_|U6PJzwp5YFtgTY}4mcS2wln*vE?ryBJ~{ynFbSO;d6Aj{fIySnLbDInO)2@S2CNsu4V4)djaRgG^Fai9k*n?lK}Ww4amSlrDh^TirJ9j287%2dj8z&@|5hk%T<u>!z9AFuChIRYYSo9$o4)jzvV+V0vbePE0k)tn3Su=GJb08$5J|p$G{vVU&i=?dox<t^F7!YPC|+F1YZta0A)eQ|=1XU&7e4zo2s{a`dIVu^9>p+xF68UoYB+;&Fkf;T4TATcb-XNCEUgQ`0IW<um|$I_OS(Dl}|C3YWhY49p9QR~--oQ<2-Y$VN{!LPkT^0bid?Q?K?&UWL{cv7#Y%l`X-Xp92=FM(>YaZ!>qY&-NS1nU6mpyiQC4b#y|HEf*4>6@G%f)u#}-L@a*ZnpR4?<=;W;#xu!r$VQ@nlWY}Mba7Ou_V6!#efZ_w*9YR4PT7wo-EX!ZAAZ$CJImd84n+Wj_}6AEowk`u-2bh}qL*ZKNmiF+)ihb5Fs<DsQ(ZFEB~#6msj@SDbaDvu$@F?z+0|H2!n>rjOG<lTDJ=(NtY_q+u5LYZl<=xcCc9*^wP&((9tn?rKAh+37jCeneVD;=ADL4ryJW&kCcI?A9+@y>ci2@JB_zO{O?9~+dNG-fOHf$OJoCw(u9biL^Oyg9c+JG$;z_}UBd_3wd6VaVCV5kMD<9r=(Fea<xfssxuj1XWAAWhazsMhU3z0Ube(B54+wCWe+>+}|eERU?KfZlBe8O6}{OHu??9DRnar=Mf&o3pCJaD|pKYZ7}|K+dW1lHvT@9&9(Vfg)>y2(xvd89SQ2V`#Id-mS?7-7WaCVNQM7+%q_-1j6cWlGrJccw4Di`bqyg^uh?M^~}ugM42RzkWUTtjhoL$amXUbd`O#YqCF>+XM&RoWa*rLH0>mjj?_(By=WGI{1P(=bQy<F6F~NJ)4_iS4i#7O>#;8Hbw>Gi}L=Hr+fNrofBA*Q_%5`aHQQ*t|QK>+8;)FREfSs#<t`$Y-K!Mbw<j4D_KUm@n<CY?tvQpoxj-?B`$QckSDIVK%VbAq-L6z%mr7uxyiCPPgU2#Oiwu#&uCgfdw!Q3^2ML;_dk~GD|E;q!FSRlhb-ujt}ln=Uas#I%@6QV&Nk!Oq?46T((O-4b@xpLBQu;U{6B3oiwJ(Nz2;`&Q>D86vD@8i7FIsgNlUu$BgSt2S?@asek6xv$~?yN-pu;?5fp`5fZQt=bz&8fh=YF=+)2*Q2Np6Mr*4JAO;51?LcAGrhOY=j-5X0T?CwXEq^SA}41j_1cDA5MsTjY&kO&?FChJ~gs>@jl72#WZ2XCYkb+Ts5Z!fv)sIbAie5%W*y7cm^`tN`J!>xu+nQqM3`HhPUf>e{(!M>7gv8iUV0f#SWKC**rpn+|8t%_EDlD}toc*Q;>Oead^*!IbUB|a&>d|3u)Z!MP_JFg`U`~`*2>T8}1&~t|E2!lQj=xiYHX5T(=sxYUZrmR)qMt`13Tb#Cxud>t?CGAz9oW(eh)f6<(VLL*dsPaLiF4>1$Ww#*=Q$%trhK7>UBMw@TkK}bc2i;y<lC<rC(#sV&LizMkzd}uh6s`?26jnK2x(uOuj;d~&vqr2_D5ZW|i_47SQU*s#ya_*`gWFS3s`>jaJvzUzH<o1E)!Qrj`sl($haRq+-S$*&B7-Qn(y|_UYi$%J`35%SmC^ofWRq6P>KC=S$+S{9l^MbOq}sw^rAsJYhb6yDx@St+*x+T_ywrW{#hP4))5d~!+zXhFv5{J`=k>q@SZWGME4jg2f(h)tk>t$`uMs~&4Gu1E6obp@0SPSTvU*84kweO{R*3{jP1m&kmHTEz%3*Qv4QY+Q6fdnTBc62qrA!?9IP>;g<RnPOI1ska!ljO2o*DYxDrV?4@aOf6y{8$&S|s8eXN%@9S6zz5luk@+B@h2Mm7=6lf!$}ZDY4O2vc9B{jqbcp^x<=4Cf@`LC13R$u9|o0ScXZ@sw5-RmjLa^52jMWbbW?d>_~vuBeg2?2{CW6G|LO2HawG{{1Ip?Ssq+hFJNDaC({wNY{hO>a*9tCo0<Is^%<Q-MOi2~fWA)+ozE_|jX%6Kn3^dg86!(5B%qwecMUAz>wN$D;Zy5bQ3wHbw<a=bi6X<~4h1uQ7-1DSryX4`t(`QdI5Fa=(tBU}CJAkl{RiJ@{L)AaMtg<Z+<_}})TLrKbG%zAQGGTU*x3D&%d#sQTxiu;+0hiH3zn<YbSNA<&k6S_Bfcc|>^Z-k!iRtIr|E$>vDb+z|Kn}=FJC{u+x@Wp{P~|)Ns>e_>E7I$XbidNMTs&Bk<}jVuX)*mN6W|q@=1k7teqy+CRvNHbr3Tof%u%r;Y}w^u5dEHQNK8LI=xTEltQVE!BpRU4kcEMX`jVMw`|{`_3<9Pc2WJz)Tq;-C#@p1Bo?PLt?sX-f9}M(IwjosRCTFggrS{3U{G&UtX*U^x;zB-wiH^XE&sx6!z|V(mOM^}(lz$@N}k<S!NB9$#-_1w4wrSx@m@2RT5(xUPEgRrL;gv9yywozM+8(J9-eM{_qFdcSn_5jBRMhyfo|D<r`NB}-v;M&z5pz^3H{jjvsxhLqvC6u`~wJPNvU-d%wd_B)lC3nH%+NjRoCBB#ZOw~3)KXyNAJg7oyg2qG`#=e+lP<ufBXI-zJ3EqbmZ%gjXD=T$MY<|GoPeuzb?qJ7$i8B+e{*aYq_6e>a!*#)ue{iLqE1~8J@blCxR#SjnUIy2hXCcJfL#ljEO9lVCYgog0`)KT_1AU4-Urm?pU|_%RekCNaRrXO5It}QeXZF_rml@kg5u2-Qk<v6H@2xGVIo%PRXVzd>6(QG<N_?6n)~(#=^C%){iUs%x%1?QG~nWWK<>QyC`YiU`g}3$%Z?aB;^ip>Vi579H_*-rWQQ=K56QU&9*MjLVw%yRD+&<Sd*xRRqm!o!cMj^J(<}d_iN3}#`Z_<{G){skLG$Q47zC#`-Ha31ww5BM>~u!`lFi3&w2{r^X2F5_LEmVRSXa2|5JT{>2GeO`a}k(uXM8MQ%-6N&n1P7jIJhSg5Ln>dFUMnuM(=K2)<sbzpi`7gJ7mAu<PJ$;@=xbpk5hIrp>_6$4Zz#ip{2m@+QAH#o?Cp>>gXP%0{Fn$)t2}+|hE=<ouTdUk6uc-nk^0cWSmLX}5MorYd>BC0}1Tz(qFd`~d@Q!@^3tMp6U6%qt^&N+Z{+9G49A;etDY6l=r|{AU3lPQLmLDSmKWm-vg$l@U5rYO7Hpg+o1AyDMv|j<mhrdAb2eB39U=OT0#-vCas(OZ~3&-?Q$y(z>z#ZXNq#ggN(B0p`9)q`xivkzA$q?D{;O5qH0s3U}_%pjSS?iYWK>3z8J2$t|mwmUP*jHik8j?b-vFa-U)Dl&-5K&I7h@a#6#UUsWcU9MdztgLIK^iaU%gF6&wH<eHHrgw(;vcC{Y$3z-Cqvgh{JJ>db=*DoJF{^QaAe7z~bt0w*%M;nIh9gGrW5A*5Xr+f7A5ar<ea#E30H~1=zY`K2*N<bp~>mP25;g%MFbpfW+<xbAQGK-*;d4G}2nw<z9<BgaiVYd|j&Y{dXc?MC4Mx{u4j&iwgE1&*&*0oIV0~v}|5P^e!B$Mh<T?Cb&Eu?geSnkoj`Wf&#h{Ll-0Q$OTEmDKwK@(Nlf)?e~t;}590P#bspH2a4%2F?&Eb>cm4c%FijO|ld2;MNMB43Y=A<aT(S^BApBKA5_uZXtM;8Vm-ZSQE?0v1DL^R@8k)41dt-^m-X?8va84+~yKDT|Wy!$J(ZKpq&0>aR!`CaGPWM5^xEZVNhhWd-UocZ46m`98~()vZd!xI|cg<K5-a6ZGVZ-3O}9ZM<=V*_(OSy`5;&6T$MF4BZGs>O!7q8Z5UuVmP~@1<;fk$<7NsWZ6|k^K6Rx5&NCn(%vmak3sv%gQ}OE3=L8fh}df)rRvGQXc$0r5$GnR<;fQmJPPJ@?pFCVb;9%Lw{;U{oX!+wGWs>dhzmKih#Z=V8!3gav4;$eT<g9+qhlNt44X$0q4Wg_Rws8hBU!<0-0RF*)Gm+C&soG6cIdmIKZfIX<&u5|hsNMnM)N)HlDnVq4>-tgwBr45S}4M1RU?Ayr0<q*&<odq{$a7RJw(e{`(1s*hDKcp_cbY5!MMrjIyP!^_4=z)qv^>?LzKGX*h<i8Z=ZD<`!29QA1V8e!Xk5n|CZZwwoEgyETUDKeHTsv)7D(Hk(e+~X~zOR$t*L6wvlqz=~x~1ttlG$2%Uzqc$v@zN|izY=~|4TKp^fcB|)DriCD23!QSji#IstB+qE`m>Vf#-Fuj{RFAT=aU3rNYE0orS$G_MoT&_BPRgJrz5c}E3L0kDJMF984!7$CIxo|7;Qa#sG$KDDqBMBmSW?LiPsPkngw2;bdtqf+gVmLLXBz9qt@T4S%SocB4!w*K!ifDZ@{zA0vl|#k(;sS*-(61aFAd;i1x<>m-BEx}XLT}CBG_i=;U{xkn&d1QN7*0@Zh(#5z7-Huy+m8>wF7!J~r9Hyv?YVm$SKQhE`FoLvIP($EP>-7g5VsEfOz?F>f+jhvq$KJ$BicbpSs3P%v87yX)YglO=rj>Z!j!e)ybk@CUgU<8Rbtu9wcASlge#VRQEh;dRdT<^MZz1{W6LDJ5LsXp-0_wX@PjCmh1q8<OR1-VJ30><Sd;9E`Qh7#kMDo`^u6l;29k+|$8AoDOvZ587?OM}I{*0EKR!Hs0!=Fl&oF5tjo{isE1gs`DUcW1HGP!%6z%7#y)N?qB}(}qCn&83><c$5L+n@}0PZ?<3frE;&h&?m|9JF2|EsYw(!L8GdSZdOFxqqU%tlu1x-b@SQum@K+?bPx`J*U+Ne}5sOmJ1GcW2rt+1+nGl^=Sh-%MPhkVBH$Lx)m6s2yq}=U4c8LXac}lb&%+l4T}uks7*tS0Sg9RGbVP8ZSOU%N9uLDqm!*i{Duh1w|6Rqb%kHbB{MYeW_CLg1Ef?dHm1ZWZ4A)aF;wBo^ZY1G#N?nbW&{;#LUXatRd!3xNI{1?$7+(_u}jQ-wjhYR9tD${(bB}??_ulVN(Mb6@~1nkPu>F1jdeQr~+=Ih}Q_7pWpmj*%sB?38Kv});eX@;8Kp*?nQwYwmuq37g`3<$ero@1GU3K#T4#dR(%#Jkl39a27{3;K3KS69`uhFismvP6`OE2ASDjwt3IWoD}74@W#BbBHI!5&4zIsl-LSHFM8TRh+p@4=(3PL454^$r#9o04b<YTbY(*-<OT&>>h-$D%kl8sRE(!y!Ij6^I?ouj=!$!6&6^@)xl7UF(gvPFJ!O~)DHlrvb1{fj@4USz4l&CIV)OXHjK6U)4dl7z^Xa1(x9wM9V9bBhL&k=@Gvhu{(lm(JIQ>=>nuA`UL91GD9%61;vN+QdT@nLJ&iBuCN_`rA8oeE%A<_T<Tg<vm-{g=|dkUYQ_+AOvVyQD4$S!$6^g=BFjZ~u{M)uL@u>46OIrlhpNR4v_H-d@ipXz@ykg`1(Ft2^kV^0cvihEiBr1t5|z-mujg-8luJlH0J_a-t2y;0E_EH4MBH&Veo@zEzpdQY1B%lbuRm)_GS+Y=+KX{QB0=uC8}8KmoLtkdRDnbN!LnTZ$D^v|SrIEw?Rd@tHEHA0s<O2~|DO8^~c-7@?hgCgJYk;c-U4UHr|Z!@qsH(B9qtb-zW4oP`V4;HwY!?1Q)XrX1ykZk%NQy8bWHTxEToMQ+rwdU{hj#IOIljjAyBCT_>plHXNQn`M`+aH}?)sp4kd+X=}|BbK$eS_HXsI+TYEwiEgPQj#+K2l7nv2`_OAVK;}#(zV=r$mFM5#_pP<7R_flYt8_x%8em)VSxe><RBUr)~J9*Wl{r5=OK@OtDvE(*QUFI2;zD`5}#BRq-WOdwd11@i&~rzJ+zu*)30h}<nUFapNb_(%GobdBpjjo3h8Au@UcLsqn6BTM5>}w2=Y~uF@*X{NrY{Zhc@&6k4hIi9848s;e#yww%nIa_QCySVY%IpVq~29s;r50Ia$E(5cZ-xw$^3q#eBMbki<c*zSH<vokI7%zQF5W1_-~Sd(EzV?BCR$swR|3YzL~^X3?;hLixS$Ag~LLPHj*)EsFOy9=mfr6TkS3RCchbMp&Z&(2|GBh0GoM39bt#X62xR>fN@jQ69?vGb)7(saNcGiM`73qzuKcpg{i_#;6TJ;XQN}(~61p%ma<fRR`%amJ#RvPI8U2HQECPXo%OZUX@3tp*k{@wyfkboz0BY7FbQdAZ^XUk6o?+>BMuRU_H1}Sg!Q%iBUATJ`439s@Og+Lo~UTZ$oEq6s(T}0(^1xcvpk#FN<*r$KmXYCq$~U$EltkH=)%HTkIPOFC%>Dbmr~QYpN&ukTUIcI9FeX8ulm^PM$i@#QUxP2D>}hU4f?(^`O)ldd0%J06mU0@d6~(@n2q{;3&sfd*+yOJy<6WTQ0WbkZ6Y|^*SJShpD0#1=8%5w`i3iX=p4Ns5#_S5&({pDC2OIo19RiAwwN7YK~G}ZZEDC^ATop$XHlUGFbCLlo*39waN%XCy@6xQ9Ya@z(JvY(t_u_#$OSS>`;R}f&FoG@uiYlqg|!6($7k<TUL%EOAvz*MYPaRWI^9xe{89^`$`XuO5SA$c(XwXD_Eo;+t+BXeZ@hFT3br}>pSGb*pklu7&PSjbJf?h?6=jvEfGth`{GPSf)e(AOW_rCU#{GzUhjzrKw;8scGNAzXMb4{YB%LgAhhPPe=zbYbP+13Ap=_%dt!4`G4(rX4qEZTZ3pCtVgs=Vt#WcABK`F=92zR<sk}k|fGt1T5^c~kqTftUu4^u=ai*wC*bhNl5I7V^oZ>BYwFEq`b|`M4+g;sAExL7V%8##Vw=;B^vVK(^{apIULphwx90Wg;Ez1mK40RpimkfmQ)ahl<R`7ky+=Ryj)U<;Y>p_P&KII&x`C>Thk~BHAe9+N!)8Z2?%TghbWx#72<jt|=2#saYTZ(&lUP=!smOf>WSvA<vN{Wu0KA*0itRu`h*gI&EuJEwQt#Jdx39e?ytLlPrZrh^mPd`2RhuaIUYCgN76BL-c;?ab|VjzbN(J`kw+I=mhPTiJw<JphBV2Kp-H}0nUopmf$7Mhz$+w2>1B;?q!33j?zOp7A1558_98wRmsF^ZcDnpTrNg4k1Lu>ihUIG9HDiU*xNxp1(h6x*{p6T*$MaOC-Cl?L@wYc5g3UeJLNjguqm5Zy4#=lgI33$Y0u5xe?s@o7k|YF=L?kqbLpNwoy?<nkmsjx^ZyRn=SJ<WA<}z`9(Ec=wXrw>9r&Y*WHyOR3+^g12lSp4In(guGv;Zqz9$wEBH)LH>CE;ivK@OV>I{>;2slua?^E3IM|4_#JS{nzN*0gS0|EFC!}nOE-ykZHKh6-7Cl-iy`3)Wo>cc5*>X}=u{_m)%(v6pGa=WSrMY^+ZNgF`p%!;av|)Xf$W+Vh?YTpBNVX%#I*x$a+^&Wr7ZACcD-4OB8&DWSz;;JaLRKbnnYlg2UG#9e&d|N200a5Y~qbVO2wl<vd)2R9qH8L3%C8V#NWSs{rqnC!}jy%e?I!xH==-~z17)yp{%yj%Ua<?Jzs=Mk8k-`Ot&PfYIM}t4Q0*=`VmKy*<b0*i~Z?9Y3yN2ODjOsJJv~>6=zC8lHzzC4R@h94qdgpFdJdN)@)gZNr;{lM-j`;lk0?_idQROT-F0a7&8}@v!TgPa#3vwJvvH7kqYWhpdD`aXQ-eyD3Os3$5=@KH`u<V8$9@NTGqTlnSwLY>A=CHrRozlWZ1&Fe;&#W!X^Rbo5bu%RtO4QkWAXOS;$b<kcVQj_7Q*+wl<!LbS6N~ueAaUT?bd_Y+nK3$i)w<TyOF3o@MW)dGrEKd7?Fxm@3T$n$>9sn2a8Hp_wT51qRTU$Ulo!f6(1090F{mO_m@Ihp#GRNqE+A+hUd<gHheeCU$C(e7=uIiVi8U>cZ-4J@`{K&y>}$VYNs6=6n6m>yOhDz1`b;`1BbK9-qO5WG>hgdbQUhn#_;$4%~D^KQnr+N2^b%Wk^HUv(tIT(|`=?LY?Odzo|Y`)vK3inNVUm?!kl2rYRlCpiZN1mQ<nmSHmEQXmySV)6ZFXdJYII*O%sYRcZD}oAigj^6J&A#1EYW{-%EI1Wo4Yuho>;S_&pzN}YOfn^FKk^#ou#682?%iViet3V29=(d615h24OsWTk2GWgWWK;bVp&UZRGAw8_?>bFmD*hI)2sjn~0t?eua>rH@8#li1iV2diwCR={Q5FzW`rD!|BmTYE?4S6%j-M(gGbZmn1u`l7Zlbd}GXIzx&!s4XC@@nv8=QiyQzn+LMtzOc$Ymk8ewsPI}Z`|z{f)w@|4sC|@kuhd$)B4s3{8=Qu-I&;*5(FHplpF!or7b+<8og5R<eCB!%>x4XIJIgZmX4%n*-L?@Al>A}%b$Mmu5TVdPVPFSEH&djOk_(A5<q1LxjwY+hg9_cR);1XSjnB_2`<je4pnLk{fP}6j^9z3HN~D22tP|!A2$x0^-HpKzaaT_$4+A{TvOw<1jkXp+FE=cya#zn98l%Vm2BkE*yRy}saeGboAPg-4wndGmOtRWC>UWkETPA!hPjE)JR9(lTRqkLpL1@dzvYBY*9<uPk6&W`<+yj+<q>c7Rvd6Nbh*Qp<DthlejXJI7R3qhB-3$ti1T-tMLi=Rzasl{T9T=^N+75_Ql>mZM2}Y=TALkg~SI_jzK}#k%g35k3r}0uQ`4`;%L1qw|^}34r2OqMkAsy2-{nywAuDMZyjODUe0Qo(xgd@F8{ejL*VI+x;yD7wUQ%~H9d-na+e11TF>FdKU@4h~iG1$Vt_RIF;!>_~-?K51m_p?uTOa9I=-vb%@u$9NRV|PUV=KIeNpPYpB*x%=~7E5$JvjA$1r!NH9nXa0P0E@P>sGIT_G@+DRftJRp47X{xCMtc&b84i9u73Ry#xgf;Pwhx)Xx8JIgUvvQ{_Gg*TLP-7jJ=T4NH#La=B;DmrWE|JV#;tLvJSfCFuAb!*X1a?M$mh2uWu4lv}>w|%?q-N3u#nv0)<j3RRVAjna4SE(O6zwV58gsm<x!qT!lW~7V6KXf}X4vGHu`K-_!NZHZ7n+sRl55DCYGeV1a@#3ytP2$vvSQ);cvUR<dKpHZoJw&uZ7Nt5)ZHP1{UYC(>_|)haZ7>IS}MEz_H+_=Hus$nz72n5`k#u?w%ghFuQAY06IirNOsr9OGkAvqo6k!A&icUeLF{(%x1108@6Oa8(|{>Qy^zsx86bI#ufoU(_bjpU4!g@z#A#QvH~%HViX1HmoHF=$%k~hMaj!Wcwy)A#OeH4U@GCS@juH+goq?iSFDe^TgnNTT|SjBxAJS-K8mQ@OsZ#S~id;xHUH_N!?2Hi=syt5=HNz@%cKH`41R4n!l-6%GZ^iLGNEsl>rSgv_>GW8Z9Iu-S-gzg&hAlUPDe{Jl)ofm%M6^%&h30-V<r{{z6T@Ty_2`A2s>BL+MQXWP@ukb?Y7Mdv6md&zvm6h|*i`r*8bSunsIDjNrO$Vd|Rx*ra|i&obhG*i!~6$>?@COp}7cP70e6O3#wh>J5!`Bo?98aGxmQ72$Q#fsWZbyNad@4;Eoz|K<v#Sh9lQxr)A_WLENlJchymv+zJrJH8~#nl#X4MYh8@LYkDO(N5OP<<h`X>0*;-v3J&0rt5QOo52$gCLlW~ajuG~%BUlO^)K4K)K!U20K&mTF_=&(Jn|xF0Ee&nl3J=By-zbQdo`cdRm&@@F%;EW=t)*)>sUco5>)Woo<s1X#k>L>g*JK!k#61|KBs*0ob@@T_f&M~LvO0+oIxqqa|u#m2Of<A3pX-V_9=UUM)O;?`=qPOU~LCn*HdOL&Fd)~W~I&>r)BCycL%j1SM4gi6P%t5rRNkqi2JGgrbl6PR<$ih5W})ED3)ysR(mS8NDEZ*!?4W9bZdhI%Q<Vkn5FZZ{?S9GuZi^Lc3Y3v?ujjMgeLpAsYaWlhUwmz-;}V9M@haio@MSf6{nJsdF|udgM%_<ID1vI4DL(s%fc{@2i}a7)bq!h3)yt&sv2#n0jk*v!qPoe{nT<&(I+Giu^o7+_YIfJQX}2l>H}_gKt>PVrLuY@HWUu)G;*Ewh%Cn-H%j-Ur6kc&pVsxcf81=VyC(E>f@J_FPO!qZrBB*k!F=<x{_3p>QDA5m_ODYcNWo7IHrkO{S4zti9#xjR=;DjcLVN`B!CH-!wC)!*p~CVo2KXp$bK41^%6LLS6?iNFln!eBigGYV8Z)hW_(;**)<6n)))j#x<(pKt%B={bMZ{H*HsIBqEak+aHIlO~iKc_AL6^_9P4vje&`$MUP^Of{eQ?1-$=CI@4E5dC(dC=WBZfw@w{h0BY|(~xWxQrAZHMrhBCPW%m|)QZ1&V?;bnD{8i+X)$I(MLx0yH8GCwi$Ok#8u=nognzJ^BEI9?^9LTdvLHiy*~W6~$BR`qoplYFcXjF>Q{N_Y&KV(zVSN`02f>=geBzh*2F*yycsQ^oM`ybqM|0Qwg@QNG86a%VmmVg-VQ%LFm>RGc{YgxTR!aAix|{v_6Lpv?7CRD6*yuazD)B6K-XVwTKbV#l*(z5~0fF*#(v6t-q&Ts_{9SNh#joHj>v<JYmz94*yvLL%Hcy>K=K*B~ol!Zlf}vKrCG&=9}l`9WI3D6IT_<4waf_iYUGnu9_DP^K@i>at`Rgy3S7`mT)~&up3x+Id?=Y35Q)h9MKvL<Iowh!;+gqv=VF-vP*M~c`G?c+EEaC#~H9P4ySB^$nrrU_PQ@{%A&%)U?OJGl4XI53KdXcIotV-!|X%U89m#|TMshb;88>Jjs=t*8Kf?%!DMo|yK8|rDXZ)o)XzK=F+W4I$Z6Gi8C>6#mvaq>u?85v0etNQo+$N3`MnJlpAcg-d!g4StLoS_-9uuAO+Z@A$kukq1nMV}@GSfq%OJWzIMbWr`ONzdKXp2$W>7qXhlLRpfoyx%<gsY!+o3}%%%#|R_C4=PQUk+aQ^~Gerx4zeQ5&c2Ty0)DBN<w8yIJ~hxo+Kh4hLj?r~RDdTF-A?9;Rf0k?fnbbbRUTnU58^WZcy&!pDvz$z<O$i{?y`<IR&OmFB)><CoRv)}Aurq>Cp(E}T2ux5%+ts{<6<Lrw-f<#O=HLU~qkAZ}Zj!g#{2-&AP1qArDp2exao86eM6!hx~6Z)Xv7mLSW8R<!&)7yi2@0<4nl+?F*u#_G56M)N8F7s}_*Rm+7RwmNe>c5qSaaa(T;<RE?~L`~ZHT@RSsy7ICT4i;4yfw<i$i&0znIk>MrQmez`rF=|yhQ;5~3U^VryYx8g!0vVsWn#(GbqraZB~?TiHvC%#<dz3?47Y<|+dczLSHabmD$NRUs5oEWL8}zn*G}No&00Lw8+@`>?_{x8NAT*2qGC%bnAjM-w=m9LH|NN0tX=AFPt~G(&kipOxYJNYl(=r%!d+iMRF6~gv7Aqw$lkVv2su>kJQyJd>}0{dw@R!!>&yf4koy3MrR}&vobP55V36Bl9WBx17B@kQ3JS%9oC|WO@fJv_iZ%jTwV{G!f_kihIXVotLMt(ne{UK6fGx4%S}lC^ysIwOqF_{^Z%GN;$}Ahkr@5XbR4`85!`t4Lt=Sn!jU~B}5|wJMp&2ej7D4wh`1C?|fAaPHXz)e@?xwn`Ljz9D0x95E%MYwdv1uP>a7S*q<VaI3)Lc<q=3I=|N}b!4bAI5lxO}q``aeWzs!uHkyO5*~e&mKg^xu{%LoASdxT#$!x>Jy)uPL;sRIG`OJDhW7z!oCsi}B}e6P?#ccuvY|Jq2+;&pNztQANELiWZ7?Q0yF2fhp*lY2$K$AzGvGih{veml<evIoK!Od)LAD%EJ@wZ`3DH8Y5*u9~LtI%7aVje^U<iH8^IHI7A71y@A*PsAy_&4YNzZP0^HYVErwhJGsd^sN%m*hV}gBcQrNsIF_XfVCO9I6i%z5gpUp=ojR=!2OZ&X3PXWZ5VZCCg3|98DFai71Bd**qYU)3F>@Qc4*qxB0{xddyEtsoYb#2N3$U6mToTJQry38`h4$gWxF8N)Gh88QZm;!3l98i7(LOG_Mo<c}kq08zZ|h6*GFgwvT7VMU*aVa>aolymR8mJCgS1ZU#G_OOkfUT_@#GT!*=Knr#zWDgaPgdp`h=AQ&MGZPTDBkezvI)d2p@~MR&K>-_E-=JJ(!WYGlyXIw?Yg$>*$S@VL5conm38M@x)KPZt4_2jcu8!e~z9OE3Brj-}nzZx~kAb{xr2mX@78<g4~_zH&K6}w5+AW*`qiiABUkhPen_$uCzrHO!y0vuxYde4ytLVu<}H=Xg@c-smZs2I~l2iQ%0*U3soJx+M|M<8r!)HSP!>&q~hpMC+N(E>#x$qRBwCb3Tn1LRL?14pgUZx&*+80ogwBQMcUts)PhP0pVVKYoLJ9zVRn86dh+^x=`yM$oFDiu(co$&-mQ^8qLQv#Nw>`P2OLJYu{R#QD(pT+g1pq!@}3?*O2aAP43=!**pJ!$jau^?lS3>d^9_VeRjFuq9S&5zZFy#D!H|mb4B?#%y*ryc2`gwQ#h{}*Mp+&*KoaTE_5|FS{3ck-=!1hDRg6O2Zdq*41Q96RSmjvRs&u$y7uF?mwVEwcsR>Vi9-4p&U>09I`%Kt_;^?jHtRNZ8zEPmK3ioCbrfq1Ps%<o@C36aGRiwLVC3&;#%<Ayx%O+~0;Va$C(M4Q{Ey^P8-KuxP{f*w+nL5)?=c&Vzij_nxC=$P?-_H+|oH^6lhJQX}?IDEUDoKR8Q!FWiaVd%36!p&T<LjuP3~b?nbuCi2)=oL;y;I3?b_>~{8|{p9PGxhu6-g-gprm!Oqwq3{yogV+aE%rDvDmpat1A=Tgmyigj{!BW$pSi;c-4x`@Z5DIFb#kJw9K5rqarms6IM*MgITtUaX^;qvMcCW5!S1@el@4_tiiT^XBaFC^8nh(RFK;fQiyX9CR5yAgG+H=|72W3H(9vpB*`|{u3*>v$i08rohif=`}7NAE7#P<(TO2MR7E?XHUhDLUwfNa(kB+mX65T-DLHrq6YwNn=|zRYybLh7mPXmh!>{gq**5$P@Jf=gj7Hy_UelZMPQffgQk1IfwirGmOkyD?XN_st-Xt3{tr*Pg8z>S9FM$^wsJ=d((9lhw)|48U5$bSu?Sm27R(l7a#R&@DL0f%QPAc&^O*yW^O(#HSedxJWXMSL`WlN75!yD+PK7?UTW)^3m3m6n<OD@Y1zpjJV+Ow#Wrd0!&Mt9^ugP}|_PUDgW2cg_;l`I}%sA!tg4CCX-p3D@-*%Vu5;5*DwW3uNIVcU{d5)onxK*+HiVUSJ61s<qushZ<Ylz3^eO-K`Fz9u6(xXd25h(k7-t4<_f$~#A%D=+>Wb7eF+!jzIr!!r0rNgAPWw9M|Eg`(7woE9K6tmIJ6@P492A?-2DawOQLl75ITetzfkv2$tU;9>gMjZ0Ag!i*?^o_#>20)QmvzaE2SJo%c(*UoEei=QkLl^8cPSC<;cuc-!hG&IpOmdD)z?ch%_H)@9oF?p3&^i&%RRwa;;gKqvES7YAzyZN~#B9>!z9oY(0M$n_<wo&u-M0N0*;MKmJcj~2fKB)0{M%nM|lTJ0~)vGQX_!RFSChtng;kEX(Yh{oNg<D|`Qwv7;T@#p6H}~cyWbZ2ut=-Du)iHlZ0R$HC2}(oXRImkJKq&9(b%zX`U(02@4OQ<jeVn1-+Qknt6#`SGQHSy#OL$p}<L+@jq2taX4bG<SddKD5)TXCM$LV$7I>kB6D(n6Ii1`gdchA8<EQpBMCr4@J-8-XG7*YwVt0gSLUOFx$UvyyjD5rnwLUL1Hc(KiX!zq#6=LSNgoCu2Slt4Y@;Q1JObPhEcAic|x@U0vx=u(92puv8;9oUaO_rX+YR^TYB<f9i;Hay<aHnq{i4EVMO-vQXZ+Za4K>IgPHN=pPW0jL+mx9>!^u{MEG-t9TdrmNYyG>)%=j%sO=1Dd}<S7t@vmQTJ+P1~v>lN5)8X*pFYtToL)U@%thmtL~_qj_4+)2TX%Pi61b0N<_jk}{B|W5w>0(aKrk`t_#xKv`q*JJmvZTXQEfsp{nhxrT-Si4@T9;V3jI_qr8Jxd9<gdCD-&PlPI?h7+#O-C^aay6%i4KMd&X8|Z#Q&b6kY+x^t%o8!y$$YkEXN|PE~F$S}vVcEAyx)V>V|A?;^UQ~VQ^1+Imb)GjoK}EfC)4tIYf7}<yub+U?pOq7d(O_>ol8IuseqZ)GyK;X<LAQKgPyi%--V#ahHSr^N(4wu-EXYJ+2_G_NXLE9`c@1z2h7NrhlKZdB>5Etrx(5ojdl}+(X;`C1nLI;?Y_ZeyVwg3xtFrifJ8>4S_rG-OF^6uFEX~sG%6_J_AyphuP;Rq0oQushg9VG!mm+V!OW!>VNuO^ubaf!hfBU?x!wJz=tbbsjKGK{Zi7_4<l_~6qLF5DFNsxMBX;wC#oWs#325O*QarBT^S9kJfIUi}J6wn~V&V<ea9f~*7O)s30_ILDzUBT1)mhEtxrgfJ(`GaTK*v{DJ5RscQ^>R&IU8$C)*93zIE#El9y6bCMnKrdYlCV6K^55#AzGNF+PT&#@iCBB>96rwuSY<CmnHdgH-+~;chUQ6095o|7m=4F1U)Cd<nFU{=(j4Kh7&<?Y!VLp^lSQ3QQ)aPs|Nc9DT1?aYsn~ZW`xVk=TW9-{1$CBs14O}^B(R(A|H8tpu56^PmC?2V-RdVBUKTE}>lD^el_GhTv&@)w<q$lJxx6!7Nw+VLs+g{=WJ8&1Y_*%XW9+!2mBCQQft|O_YEEE~zVAq{5dOu}A8Ivvbf`zP*k-0>?>7(D<jxE4sW5%mz`3^2r1!2`f3%**mfvg4$`7C9JmdSqeIB~1=uC+kI5y=R)>^I$NXsYE(k8>VJvJJ;OZ*PfRymb#TRXF7c;2O!!*g}Dz>_C<JVl)w9p_HeCjP#Hv2^QQ4CixE+1%XFLD4x<27^DecG2-hWApCepuMSgh#^}MFqkO#rGNPL;p6+?etdZNRJ)6?@ml5wURv<In0$>6UF%O#LS9oe{>8SM;A%*4k2>q4f{PnInMh5~&^;}e<cH2fTEb;JzZ8K;O?Kb#XblCmYILQ3>;??JetfA9ro;-Ju)S^IjcAPPU>;cJv%*D$o6ollY3FGm1!S;*3Sd^v&VW5e^SJ*AP!nuCz<@1MW!ytU1;H1rJs?#tXD^O&x%QdyM<%8>vXl&Dr_}wH?5HU*2R2w-;<Ko#riJ#C-BiWO3iNkp>lIYB105ri2G6{KU&5F^@FR##$!$48f>vlmqYd{#FHgETAJ6uMor!D8q7sxwNU%w!lL_Ye)VfA8I+N&4V{Nl}u!Rpg$1-3`&<Ip)9l2;QJUqU^z{!prnl*09w`zaG)gY>q-I<I9U~r6OidJcUMCvla?}~lMDC`=H9k!O1lrC9-1iK}q1LhDN6$uz&;cEyVV?#T)ULzp4K|1E6_iNiBkL9<7ziDTh@2MxOT}^z^wyL;>Kl=O65fnZdwd7T?yN6$y8uidMTrubG5byoGJMD$iK6DlR{R<Ga_4IiAeTi@inF-y#rT3fG?D0(x=x>e@VUgo%pxV_K0x5(uUN=q3=r@F$*oJ%C31@o!?FkGM4M*+JV!~_f1+r*Rcmm-FRu3$Q-+oStu9cTJJUG+=+4BG*VaW!G&T=j)EJjBjp$xX5MS(XWQRQ51;;?P;aClHCm=cLKLv3Q)U*On5gCg$h^f@8SBeC(@%nkvce@jE3(`UPTFj6UxEal;#gn(cH`nBK5dZ70#m5rffiE{=Ln4rCVPcwNL+0w*lKspc5fT!U7Ie?(!COnEwZY0*!NJ4`IuVdEa0bui)Oex0qdTKE~SV1pUPc&Y1sl#N&I*;9$>nwZ_nr{KXhFSRgrLGhMFVgX2O=M&DgMLJz`|;|heHKEArEi3hLw8m>ABT@0ImKnN@w09ZQ`amh9J^rw)Pp%m6nmzn0Vu<17SR3N3+UiSZYN!ZI%$bmP?JlNtmsozr9lZRaba}Kkn9>+hIiFbn~BF*q@fAhU`i6Zf3$O7Ls)pprBZ!G0`pHv^%;6xklLqubyU&mwy>B-2RN~-=&@qV4y3#g;luM7c@%6Paz4+HHEZgJzCQf&?&|~aL#O?)GyC55<HN7O@9cNdk{@ls2KsM*{_wvKr>S`8pX3!DiMAUiXwUyl@}_Vo6AR~KAN;(B*W7gN-(SVMUqAfvZa;fH>=qJTPyN!DpSRmj7-Ap?`akB2`}-5titY@U_&&W^1XFhKXa4+BB4(fCP5xm4`u#6|{l<&C9=^XPIyT|=cj_iPMdT411wJ5ih}X0CR-(q{lNc5<vkkB4Snhk0mNMs#-*=`jzw4NtDPTwTrK79Z^Fh9^h+n@RdsgLtdD3{k;JcxwdAUt+;LV{x(iGklNkl0(7*x`2$Ge9wDjj@5oU>YCMg5ZDpH}glVpmA*&P{Sj{x(K6LyPkMlc#(7Y@HKWkt+G|k8q^jQcg8t8~le+9+e|45n3zx3@MT{xP9a^Qtn&HGSZDdBguCUGD!t)c14Mcl>=8NuDE22?>h*A4lgWoZK}V5I!{&C!c0$Ds6pSrq~el89Ql5MiS^i5=#WE#@1#c#S<oR}Uk=H=T;D6|>Q1nCm1(va&nBJ3=5r%QDWTCf6^zVquJHe~%`77Ly<)a=il<6-`D3@6f=)9Jb&_Ne=V^@VqB!s)IV4l&F^)`6mi*_#^&<#NUx3^j>BT8o|3&h2OTeAv{Cr>`!*N>1Bs%X6Qgj>&)r$-9X2==7A`o?NEV;0|A61e<pD!=~2Flynf+D5M@d864cnp}Vd*M)Wm_HVRr>9kRvS!O~FS+Ze@c+4ds>`Rk^zy6v?|=Qnt%gpSZp_SQG@EJ?JJ?r}EjHCmHsJ6D%|~`{4K%O~uT{~?PxAK+53ksVgz01_v^H#?OjzQR;>(w1fc7>exv}$F;=o@}(3FHVW`LeEY)2UM@#Hj^sVp*}^np`_IR$n1sscCq^Nhmt))!x8sVhp_t3Wx6aUiQHXr9A%ggQ~>gGgPn54Xy0Ll~xr<W>v~C8tLmv?3qL>v#^jy|yH2+XJPSD{_SL>7{DanhYsi8)PV~a=dgILiHR~-85&7Sf@}*{k9gD8O5dAx__1owVDb_HGkiwN9Pyz#*%D1vh63ls(YeC4_D4^dnz}PK_qr%UTdQ;$v3bmuZ;F@Bb&5RR==ptO{SH?smuuGC)E}XD_uhIIxP8J(mhkk#s)9b=B4gquOw!Q_RV_P(=j$uOZL1Tm;g&nA!#KycuO#W-8YiFnc+3!N2tNU<&9!+IXxhO#avb|2`6$$Io2wXAgSq^*1vM!tVlU54!$9+5t!nom1V>u@++vKF#QTA8jYX>Y|G1@X%;SZ1oO<$?^ZEGuYo_WXY4)A7}g>Y=Qvw5f4S;XET(i~Vk>$0zo`@@l?v=Wi%p4*u9Ed7g=}=^eWDMaBQyCXSSb0b-*DBuOUE)ydR8SFnZ5*QM}9Ds5~k}j%wk6ZydJ4lnNNs$i=|m!2({sv1m%xFTgmd^x_SZoQaqWCsAVg5tCCZEs@TlzAE?jhEGo)E!2$GrYUq4+v2Fa}t-;hx8Oaz~LLmX=G`?$K318>?&kvtk&x%3_sJk_hQA-pVCU+>9@xutKz&Y*ca%t_PImL+)N0r|D(l<$Hlk7kEM&p-8Vldh(+~y8kp`$JpyP4zNN{Q;T$-u_$mt2-z+2BH}#>$SSFkP@*rKUsS*m+L4PZ{wgv1iZu?G!%zlRr%l#EHF5RQVro!+-hu`Q7e^?dQ+`#7dGRdP(=@)<k2-MK4N}QHZSeaDUCq7Cc%;9*|EeEMo06sW!=4gsp>^Aqm9iL=JB{X>x^=`HlL;vD4{&GNu$tZ49RR?sF)yVoduiKDuT54y}*(=(UULXQoD-20dvNp(U|6ooRJ{E&X#R*3~KD&ZnwN4I>Qg`~ib{n_}%EtI_2lu(zeqGHv-6UK?hyKC$F+I+U)l$5-;~t_lVo&o(xVg>$&9Q;zqVxzviwa&m%#E*|nv>f=3kPCg=_^6>C<+q<uQpTUwhGa1Q|83=UC{yV*Xb^bOur}G71!A<DLzMs_sF&`CQ+vFcWFiT3UqhJop#H?-t7`tgorK-CAo+^IQB44N`U_E+2?&?HlwxZ$v58pm~eE-|`7xDEQNTMTOe{9sb@Hw7m`JMSBUHf%Gj>RCsvD{`7AzaJ-98;e)DXAtktRDKYh0E~N<vkHRsc(#)_BwbLW#s{t`({jJxdcO(3KFz!73}(u%YJY$ws*(6)nEQ$Q9&Yy!dL3fikABFPq-JRM}kyUIO`7I?4FQ1Z<k@W26aj{P2syRuAsRCSfc0?cQzKTWwm}>$!BikRgEIt9VeqIG2cZ=^9D<r*G)Fu!6YenfKwOLQQ$x&?lraG+4o6PUu?E@c^3NHo~Ii0?8BNwHLP+sJrZ`Zjp@nE4!K`zW;V7za_1i{gm^U9OJUGWd)On|E-w^KU4xSzMaVw>r`K3lA41huospiAK{C28`sHiV*bNdwijRBMjvDrEEURoRTFX9p8&cCHdhXk*`uJTix;X;*7^oyDYsOOf^fxTgyiKJtp$JYhz-S(>uyje`FwQII@lNP91b>nO%wZ0Xu_oOi6l+5E3#E;~wcEfeS9x#`PeLAp*jB9%by>93uXkNtOQM!Y9U1;(9x$jjEG+T5oE^X>TXZ-tP6!HkgtUdueuJE{<#7F{nU9#zX7$SzDYTa*FmwbrpqG#YNA+LV7T{C1g_2^g7=@8{2H+k0-BX>jmykh~&?FQ~?OD0KcG{w^i#mFi=n_ittj5IK3h~aa)7*z$5vkRne9Qh?i7~laB#KqPHe{<Djd4ZHVFP^|{js7UiiOAUWTB7jdMMHr9gxQcWr>DxRo<Kkv5LCLTU#L$_(xvAs9YzJ49H?gYOP@GsDDUFnF2UH#Ig7CUhlwPh}E7_X_xkvOBTtRaCo7LDvMKv@8iYBqU=WrieVp)3x4_V@gECiT$N^Xc#1xFzUu)Q(ZhhdM~Dtze%@|BHP$*!={1wG$f!Ecu~hQM7f|CPgO5?B#WW=3!#kAgpiMgIpS<jCFywMW$gc8F$x%hVjLdvf7VcwU>gyRQQg96U#?WFc<x}aGG#**7DJl{PNk@k$VZXcmT|Stsap9*KeK%4626SbT%#$K^gHM6g+{N-+nv*ew9&<*|2W4R(WE9iQDo3|HHN)*%DC8g#y}aeg5g@GY+mmx1{CsH>+(wHvCr;3HwWbQYu(`$1B193Q%4vO}k2O$FSrGInW=5(~xUwROv}mHUckJHizq*&aT4LOCa4C|JJD9wqu-%G#!R?>bwJ`Y|9iTVq-}LGBun$iPAd^WxS5ix~lt(mla;}P&4Jm%6)i$H?FW=&84QS1md!aX9p#tzg3Q*$Mg>oI)W*g+-hrYdN9Z!2z&AfL2pCOmnP2tiFg;nU*Z+t%4<Cw-?{@baufZ>x<?1y3*agbZk(h(kR$B*}SQ6>bb>KufogDE#YA74a2eR2%@`v|llbSjAREM&0R;8i-L#w4?EA<lt>9P04Rq?|x@)a}&!bbtQ=d^wGfi4BQUjgeJhWZ7|MiEy_t(fc-b;W+@so*((b2V%Fkwa0DTnOtq}M9yef*pP+Es|S@yh40CtV=#YOTGLy(c=j97`Iu}a6*<Gzt1{_oda0i6ihwojdlHhzENZwNsVp57z`Kn9rwPloR2sT&nbr_piI8neDR<2OQFkR2Nv1eh=T;=$jxr29VCE0d0`Iv|4nVZjTdd1mDY#rsE%F{!nN(909q<bsKczGsB>nFt^4>fpg8>As5>l?D+*pv@z%?DNmet63aXBU}dWPmJ;sIw*fOQU8FV;pUs+%hhDWDtp{;q2Q<shD|g`Rfq7<IwJuS(#(zM5pG|Mow*IK7e~b81-m)5F7;tys(Vre~;HKn#}4Vqp5a+SO5qo4+A(0e6>R_Fje_s(qph$+C9(V5sLS4_iquOOlnqgOSE`w&N*<g>~{%CbaHGn>?vxXB34AKbT2lkH0^<Ul+u-XQp^Q5e&5977rbAh{;|?A~1-7+)6@&MINz#lw8<i(czaB4dHxZaL`D)r5@O3Z9hKzy3jW(mZAiM#LUeushMx_2G>YW;DD*U|M>TsH3UV8W5GhVUit<W3#OoM50X{6x$V+dO9T3d?~m5?wJV@+V~&8GOM?D-Qy-^tH#R7oSn?>^86w>sa|^zIVRUC`CVD)b{}_6<jOU$MLnrUd`&@9Ef<NG|Tkj!LBq3PaL-^s_hmY@n`|%-yaIE7N;J&;2i9<QtxobgRNKc7EA9+dG)YdX&w$9@?(Sjt^OA6!{V`USG{!P;i?=g<c$D*A7MiwZ!ms^z1%aZUP>Gjk1ckzvzDg<+$0pu*qgUa(`PuTroU;1h3e7ynsZNWB1EHIZ86R6Xg!^c$@#DefVICZ^kQQJNa0*hJrkrfeaO~_qEVzCP2n1pA(qsgJAIzcKbQ6wZOflUWeKBP(E18jLqc(*t6W>>Pf47Pc+c7*T|DUta|*?WzZdxN+eI2M!fQ_mkI|0Jr?FHqslWu*G|IQLbllgT)Tz6A8H!xCH#9`&!!Z~ALxGba`Gz(Nl-KxNgk<|Dd4SF?WKrQefWXQ{{6qT2g}6Z^>UV#v&}Kvxy~tz2hIWKdSmI&JDJMl67llR(PoB;1KWrzQDdqJYJi8Rg+g>d~j|vPRG3ShCkWWVEMqdtqm4YImq$TU^*i37)#Q4htxEr2+Usq5%Y&GYSnWqSFqrjfnsrO7`xQR7y-?5$)&%O#)f$ZNUax6i<Qu^M0k(>5j$AYiyCnVhuf(p(D<k=huu&1RHqH64IfxD;t1KV|3y%8FpvO)JX`1PqS<w5{=O5$jx@I>%wdN1jCAvjeSyKHg#nE(YG<}q5Qf9k|)Q45T2abA}>!YVtJ(K%2HTlDcLZrBohjB3^riKaulnOGC_^V615IYVh-QEiJ)6jo00t`79>2_Kp3tjok5wC__dgG+v~-8y<bmNSX6w)f{0eWYwJr^chD(2;yRK2;ATsTMm0V(r_Z@4q=++=k|F==_gi*TAyv;=RGXt<(0He324_;0c6bh8I54w4aH6y--^7x(qFYwhF`1vy7E}Ic%d*|LKhQD)rN)Mq(WK>%O4Fr;pZm7_ILLk&603)fXgjo;OS)1GHa_`YrMCA~&ug2U+!kcCReJJvaB*7C+3Vu@+vKWFaML@8h;vsx(QkQI$w{z~9(dbUKbGtsqb>)QkdS2j+<}8cR?rT6Xj|2`sKrKHL6w$7)r9Ka+HU~whz=-p?j9Z<XY|`fh`l4=xxKsn>wb$8IT{8<!{Q^|rTw?~rd&w{-8e~Bef?idX<8u3AX{gl5J-reMovfTziy){%)N;V!8zz`AT`6YE?ePNZ8%fGj?Px(7K{Enr^0^kJXbqJhYj`>&3f<t1G%(UZh>RjhQlXXZkrZ3&m7RoTyqQvgzNTH_N=*HaEmT1Q0|KyAcabJDSA(-)DY~Ikz17^I9zL8y*Awy1d8f#jO`}?#WvgVQ7T;O2GSXv9$L+@=~uNfP{C~z%wG<lo+9DofMj43L+<QSZ<pwV3*<&f=oEr{m1GPBKMQVM+Jiu++y4zZsy3vihjfs$q?3Jce_2>=s-qYgr@ksGADhzDp4^A)MLAim%RH+Yf<6x5eSJaDm*MPl_Jeu<4{23d!8WE0Ook;Yp0T8A<w=G@FHrtEdH=DnxaC1<R$PzQ{^rV+of<GSjMxnHqoWh);OB#F;8SXb?XflJ^b;KrlasZS`>Vj~_pud>M+%A@P@_ejaQK>(>m)rbZz}p!I$*P75a8NZePbsn(Isb{RDi~g*<+D=^ooO_t&5mJf)H@!5j%%9^NtNVfy-XLTU$5B)J7_Zl#!4et0ClI)ib34!!5B9uMt!aI1O2<KZhD0x-CwChH7B2g0>7MDMhBJQj@XK0JC0^DGJS|kSZiqURvZ;Ssfg-)tx#U`-(_|x@v31#nfq*`F!Iwm`VGQCe-s60>@DwLrpGfi!R%_$nd#GUk}g4lZ&^rZxa#?1*P9P38-O@@GQEkXg#a3?aESa1(%`JXn}ynb6q}1Z_XoSL?VM6Dyo61!iSr0Y{=Qb-qR>XKLiH3DAjjG(5H$sw6PRa8iL@p^%9lTogZ#?I!Uaz=c|h_ALcm7|7xMn?|JR6GPQiT>M$%O^q?BN|2;fZHwel(?Z+GM{D3Vd;Rt3A&Wnvg+8t~%huj!kaL2ZfNlLJReL6f!76(F(I9z^IB~h;=eLQww3T6rc8#1^f#<~QtOoPI&gJ_a405R>?a9@sGW_!=EZ<nG%KnzfH8%Xh+#7M`3n7T0>LD*K*0Oge2VLUo>5^AavaTI<sQjRs2!O<_6<LtB?VJpX8J)C=mx{^xx@+zxEfDv#tTT#pI`m@7Y4C>8nW1^18W7Oef^Pg~@sCJ7%bxRcefE<DeO@pWhSYOwd(H=lFb8o7vIm<ZUU%9|qz@f`quX<6(8C1*G&j(W-#;jFTZt}TtekWzeglOAFII%F+aB{A?Ak!Om|NQM4zpd5)psj>K*#WI(ahFr&Hz>qOz0ylMI|6_@%T`dfXiSvG*p|){6?3--9p3l$9$bP<-S|LB0)5$tik&}cd350o`1XF1l5ne${@?!e(?VFpg|Kkqs+vtX<@-|MkdjAUpa8916|q2XjzKXCZp#ZtLo1N7gE;m(C*JE#Eo}moe2y&FwLr`UQWM2^G6X`ci%Pi@jc*!?D(!<iF!>i9E-;D@oEmVZd?X4`rQ~0<NPkEGs=$yFFrTQ9s3esWOaog<1Uyb0aGzV)qQDseH6}YSW?e!BKQbggU!qma+m#Xpe5V^NN72r&8panl@SG33!CJ+oUvaeL2~XRlN|PwkK*ICP6uOSVEBYo;D5=iRNiYpc)jSJU)4qtr8Ig*?q%VVju;-Uj(7&#8eLb@6;OZg{=Kvmx77h&*W2m5p8Uahfa)wk#N3|`3nqf#fmh&)=Ef|HA$&hes87LmbCZpXS$H~sA_?Sb@*0auq?WWcYjd<%noieWP`ifiBSrip0^3`iF^>NzKHI<{%gdcuF%UY6tt&GK$xbw&hG+5A}9e}gTL@}Bw!wXS6hHJ!%&1wQ&3||WBv;_eh3<~rt&9O~eMw8ZCdVUsGtPD}pmDVHM#rA<3nF|TEC)Ip+30~sM*U#^EKWsmL{^yf_fAhkOuRC8xicQ0JR^-8Rz6V3{pf(qVQ!}>Id5YYIBL*xB1wHt^)}KZBJBxPHLFU<+!K7fa{%RUh*vOWg8>cv|zEM+b@)$)eu^<w%kOAfEzFRmAtnh(e=A0Z?rq)e+xTAKS-Dq&H8#@{UqtJ>K6_rE#rLbkIl6B$>mF!TTTwLgZo#alSaTY<Z-B>zg@o0InKKWdt9Hp9B5f0>9Hit7}K4&1(_nM4DTZp3q{Y7L)6msd)`bx1oSoK;mw|E$b@!ZSK4b`lU#MW6cr_nk`bWLm?3o98_ZGn)fIx<YMqBIpuxYc;-0A2U|wnZMxIi!?Z-8!H%ViOMX^~`_{Y~a4)*$eH5U9{?uK+(tBn6N&!;n?697{;JsM;cluFjTh&?$d$j;`N9EXzDDg7Vu{Mfmq%5@E&P+h$Dd;aTc#{W^`aecJ_<3JOr<;{9N!2o&h%1IgiDMG@*FO0nGys+B>oj0`k7Rxn{A)%kD!b3aI;@cx-ggAZW3q%h8$^OV-B*jT;i5VDQ5-DLUlFxw?=(A?@jm@1#|aq3_2k&ZDW*j&7KO6PnZkWLra>eceKe7>4GS2zc_OmVR1Ew`tyxp!~j0aRPCN?Ofh->+pA*kSy9neiW7M+v&KU&)w&Ru&KDJ$SN;HUApT?4-2Y-#=XjJYsU;r-#n0Q_8Hvg8vtQo%A3Sb9dx#9oi)SHcGt8k$qs)hx}{?z?GS5~-~dxe93`UElZIKh4QN9{-)WyvG00HD%?iW4kv?XUP{`8s{EVv5o3-Higlg1upycPRue&N-pxyLYyi@Gz)txBBBq@OReOth7pyfc>v3d#gqc67#ri-W>{=2rrCe*V`B3WIAv1H2?avfVpp;Bp#O0Ca;a#=Ld-8hUkzz{(xQwsst;~Q;0OA9MB>HO8mQH78H4NB>GK$4Z)Yq|$vXaP8s#8B}nWgBm<VhcBwbh%@qTdGiyu2b${b>q;Mk7YBFE}%5)s%5(%r&WeFRScXGw#DR;A{r}qXNx%H?5U#n&O<y&aYl|pXcSP?&7jaoK(k_0mK9WAOy1cH%9;*ZjRWFTC9#-1YxquH^^8<_re6+PVvimz``w(*KvVWsOj#O@hpv_!s7`xTL;65O_-G*iYivW4y9`ER4#_fu8%7z||9Vq@pvzb$f{7|fn}`MXwwk4=Yi#a4v5^zl*vF9kn?i@t&}{}~?80G@CE<(+&kY&=UHE`AT~$*!4{(J}kf%1qN2wSA<YwS^8r;IN7tG6No-$0-Tf%nmc1*1-!!Z&)1_+g>ae{BjV)J$D9O^(Qe8r*~%C?dvZGLGqZ0p;a<nYolWy+C2t&kXtbE^=Z!affSMos6Qi)TzDIIJ)%Q+AURICok^<EyFKd>Q}@Bz<)T3kES*^Vr$$DC8llOs1Z1cw7<vsUF?Aq(7$X|7=<y2C`e9M}lN$(5FTvFkrgq@bI@py*j0}C%5u3@V@;3J)OF>f*6&G91E?DRPaIfGpm|M^rSYKIj5tz7v_W|E}S56$s|(k(SJ%=b9zn(`JK1J0R-kx0sh%t{5$EdBd^d5GRZNRlX9RF%3Mw>yW(ozF}{U4ecX^&sOKS}*C^|EL$i_Yd63X~nmeO7&c!GQ_ab3~&Wbg{f{2xj*_Kce`br?$h}<l=Ae;u!quc;Wl;;yq)^o7PI@1=dY3D1jxf<u?1|$r3X<6G6OV(Cx3fhH~zffveIwrl5;u4j6q%L%@c{38J;|-B846Z;cQ+_}W@(SJPt`vDw((T<ChU%U9&wA;zX*?GdR)+UPLcP`TbT0hInXX#SjeV4NVL!y4CTJ8B$|4e2%Cipe370bv!zj7iL|#1cQzJU^L)>w_PQ?O>@eOvU1x0Y`y+Ut$B0-DVn88ygNn9Uk{?*%~QQHGKaP*LFQ{74uCq%*kg!+UAt3}0(F4Y0l0d*S7j2n=lk`F%KNF$RRN>-#>&M@RQ2iEKlsuikGlJaP5hdytUMBZ$cU-IHy3Wa!Tv?1QY%wjy78B0;+oAJYY>Xn9$4A2i6yf=wg>?>bs*^KbKa2+G;)B#Pl;cUD^W!~#b569mcC=+ywm1w=QUZheFcncm??$$|1Ny-kVDTr_{fp}PD3-XxZ{4cHjQg%5;rEG&~I(b^JFLZGO90hLVrn*l<h7n4%Dg*%4Ys1E9fy>E!sZ6q@c%^p{x)0_s1KirYV{?92;R8qzSidR95VB=23Vq1^7;(7SM-Mt=q|g=v>egbgR%ChQWn_R17vL1HfcvSt>cR*u65?tdp=j;^wic4tC$Z61p4-UMBj~9lZaAWq*{;AXyA3~NK{*|T!}YcAi%GWR+Df`TbA<Y~AEi%Y)T3gygd_*L<w;@nXf3BG*f-^Sk;D3~aqbBQOcyzxQzV8W*4MR$>vXv)odj~C<-G0PJ^5p|W#E2vTcOBw`rnZf&+g?5h%&`vtw;wTCkC@TR*~iTwOz{*AgMUFO({LQt=p1uiR7@|2Mdiabmg?sTo3mbVUIM{bAca2l0HnSb2Egy&SH(Cm>+naY?=$A!ytehB!ahP2=`Zc$mM-`mxG>`EK`t@fa~ohTO~_o0!~wEd$lOsq6IT8PmD`37h?U|n3nQ$A`}^809{RBd+m3unStO0vsJ{FOu7<mq<Bhk>EO}>JqV&kydXyarW`07l6x}a+?p>al}0C`qIFXC(KV$K{_U0i>$f-9HGt*H^ab!4{NF965~!dBdq$8{;>q;0wX{ToJ?6YfUn#t|rs|&q4k%4ZE(gjWljy$o3G$F<Arsb%NUq=8NXHD%X;nzFs6wzS+t_S{pgUIOvjJM-<BV7d^faR{AA|N!?-1&-_DaQ;t^&&VUz|6<x|;2*I8cD|(;T$xy@N}?+v;|Ok+z@1X`@m)aA`xf3e>f`E2FA&jYoJ^s*Y^Xm_jGx6;4xkEw;y8O3Q)bTKo6WO?7fnvw{@(%)3o9jYcmxSc=oAY>DZVgc6&_67{@C)t!dvc>;TKo$>BEc&+D|Y8O7}iK}XKZz#fHy$9G`>UYGxYN7|6lB!9@wh}j4uT;Ypa1QR86GNLqHp05*=(*7WEkaKk)@T^VHj?;L^w8yzOBFJKjLg{Vj9dzN5l%ss_8%odP-9FI;V`}~N4c69**wS_PEBa<H#Y|EP6O)v#vO=N7GN-mR;jQ=W>x<|r{NwmEOe(F!-M5FydFcQvdX?e{mc_l@-wX#o>jU5({;TI*eoPAiwzkGKuXpjzM9U4&p^5U_<6U!A+uX+RoBG~kSz85#=T<dL6^=b>RzDx8e<Yo=Yc3C^O^S_e(H2g%>Z@=4+|q~a<M4`typB~+o3}%wSh>@+4sCDQVk3P)(8VjK+BF?4>0f3=A|=|p%u5Ar4LucqiTCNAnQBr=j=fyq0hrQH`zRLb?%NYojnVv0qCZVE|l1jB$@16W>KxDO8D$~ec!V2OVX>=r;PCOdm7}zxx;;n9Gj|1>0E{~{VWot=n*B9XB7wHwuLE-C+zx7h5FXjyy~8@H(pS}3{RcrXVeT<+_$snp-7PBDb*WTxvII7IDXoSneC-0u?p7cTPfjlqal0-a4{DarsAq1w2_pH(ZW*irW(lvzJrZ6BW0AhP_N$(2A$bqFlirollmRL!Y7}J@tv(ePAeE>(%ztBgij9h&@plHWiVC$UXyk|JKjtY0O&NAq*G}dJ31?#>sN`5_0(^*ZQr77uLihE^m(%P<`X?2MaN8|?|KI*KK1nMR|;Vm=vE-)$kPjdK|%89z*Kg;@yJOWnR*|<Pj1UQmngE`hcMLoy}L}`cH6F^6gi-TC=cv(Jr1;RVwK1}@Yv*7OLri7TYZQylwz@nKy@I<ec`234?C2iLGO9p4Onb*%D@>LFF2zB9ypI$h>4@N2-zzxZqVXi?H5OPRM--h^m1|O*o<T+rAHdtcMk)pvCqj`(+DlQbYSkgddp7(q5-X}S-G~Y3_xz26~jb3Vdpe>GIKNia-$7h+PG;!0g)ykhi;W2wRE;SiN?@~5SkPWgO*WBjs-{s;SZz|c#Jf6kgz3GdS88DR39~`AnRnun(+<|$?uB&SS$)1UY}V*3<YTU%_1amK+a$UJiNaapRUA$)}+olGxN*A26|Tu4XX8I3P$O6OV3E9t#U1zuvs;aw<{Hh*t-Fi$c5uI)Mr*wP%^X+KXHa7n|bP@eT%*~O~Sncr7JfMtf#J!jcJQbpi7cW5Hq<R75Z)Dd^nGhocysITv`EJCl`TaYoUR5Bf6kWx}H6K2J1Cj(OK{N&kvs(dyx7%p(zRJop}MnBtxMDlGMMZWFwkTXrC@Y4A>NpJ9MfJYzg?yRYR}<TQ9VWXH^jGPHV9g`ylMxoh-IOcjh;T9xj%`z^L0Ez^GK=PR*g3rnOES3tLHcK5UDEZ5EUgx)J4wbZAM~@|>8Q4i{S#m*+K<Ucp|bFR5}xc5sD}9(DEVV>FX0{d)=w)lG};KrSPx3lZF(<F*z>&Z)HblYx)$_<GPL(w+TsTLBUwjc%rF=e5vNXyXTzb~J$?1v)&+aTv1S$gW`9&2C+d;1`K`04U84oR-QZMCH^N($Y^A4ht>E#2f)mtS8^9Jt2jId-OZt+f!z>C_1#~M6t1}y4=J`&NR$Ku(5VZ+C+|AM3=*jHz-ASAZA@Wz}G5AZaG$SEj=+9E-ZeF{iA%Xb+{G2Js!%vSc4{OIOB!d7c(Cr@VSh6VFD_yTHbTic~=fFUrqp9Z=k9&T0F;0CI{WQh6zGCqRT$d@O~g@J8%PYHi;DXm5ohu)hzh2TRu?7%>uYTnIRw{htgbV?pTz$#hoEI(}zAWit~@K8+!`-E5i-Tmr)F7IBZeDm=0Pel2oLG<~Xe37X*k9A`dt7dQnnQi8Fc^g4d}~CNg>yczP~T^h&3|tDCHQ9HOHzZgrIRFgs=)b+TNLu@+s*2||)r%|Lh1vITPts`#$P@(4gxM)WE<zkxziqLSgHn0W*IOO-yOfERI?ao$W!jHvn$(UuOK?R4lqso1}<HHaQd**(dBf+Cw0je0O*fBHUxP!>ADBrFoK?v8^qyI?;FZWJ<70zhPdqU!rIetzK2R0rkspTF;Q2VyU?7b7qyLLxq#8Re8js2JCKg!CJPm<l0c+j2!>Wn0td2Rp!P25Y1R{oC+{7($v?+X@vs1b6V!TpfYGB6AHJE@n2K36%p_>02D{yscLTK=(Y^$**l7Ld|p9nR-8UJw1aI6)kMWXMas|l<Y9r^$5zbm$Axubhq#6-8to{!=eS(uM)rI2fNgA>QKy`T<uSN6dBk>BLAsL)+!*-(AEgNH-UMk%XC6B*Vk|entx<Ot>ggTezrJPY@#oWO4-RSaZ?T^rVJ4oa+#E4c$-+>C)UVjs^F&xlAG#9L+ZWMaxKv&(ZJf$Jz<&s;z-mzZvVhoU05p1VaMrk?er2GM`G!5_Xo!KqD@4P9VcwPM(3afpZR1TL<*UW84<>GBZTlqHnaGci$*X>b`pnI{-o53O=_tjPoPCnj2YC2qGbN+#Rz*l)fj7PJ1(UB4aH#ZQYFhuGa0rX+4CI8aUq&o_RFDBY;$Q54HXwIq*6ksy<#P8ju9O!q5vr=?tI<FyVgOz!fgXZ<e?3Z;aO!#<Vbbm>uWNyH9sYu4VfpeA!m`=4Z%MdDzVVEwZ2{Y0<%_`v_P7`5H7PE7@ZNk8L#to&|A7Qq^!=$SnMw6aq8jYM$r5cc2!BgN;&CZ3I8;EC*)3Ck(2_k?#BCSW91dYd0-%H`^aH}K8sC`8&X8K(q++s6gT|MiZuKBg{aKX{)>(?Yp$8tv-B&Ll0gj>XFH{aO20MDn`UB{#%q5P1yph3V30wIcJCcmf88|TjYdC+&|n>FaCsP;u6q+`+Md{}UlWYEw_Oh#7y2l5nRvQJdlL$PSR)2^7wYA|zT0AgY(+_qQY~+-zq4c$=Nk#6D`ay5<rN3)Y-Q25>&l7S)v%_^R<DD9xz?bKRpg`qG}<{TcCbvr;xF;39{}joqfu8Ywl5u9yMhCWAcj(Ob%*h#l%5Ay-LY;<stvj#qPhjCTW%FnkCT@0MgfjGIxQthqPUl9nYY~3#Fk|F;%F`k=~%sR%Q>imF23r`=U6JZv}y_eIBN2%<uY5XzjKAXi$aM`?@5?(?#ATc+m*OPp&t~sav_O)0J-@E?n`Xn25c<0gnJZ~JCRKFwh5Fvvu|1woUW;8AqVFsPYQm(>%M?RIM8I3x!6dozV4ckxzt6%1XZ7;p}4i1a*~4Hj6)6^gR_E^dU+p12==VwQ=>BzeJ8V84T-ClNY7LzAlK#NyDsFRs9K$_JMZ9Bwh$9CINV${DN2EXs09*?PQ1j%r08-Jm6|C@NJn0=aMIgQ^HPlyYl2Aymd$UI-P}xnHm6>>IF#~x80%e|17OJeDr(crCJMM{e;{5BHX%A*E)yJ2L?w>WBk~1O5GNo#rdnGA3?&$!ub@hGVS7pVHT!1+0kIO~%w$|OpPO<fN;5SD^YB~W_uw3*T7^M`NGRs-%GM6aE1lRdRANAs_Kv9ua=?%;HjA&9XoEq%WcX(rfVy~m+an%x<7_FU93{%fek|y6RBb3GsGVSEt!KB8qF{sri$tcPOk)_VW%LM?2cf|vg8VWv_$h4y(8|>GX%dHkJ#1`c*+W7c0<Pu@>aBkI`0mH;nfd)q`4cYKmE)1|=zZ8cls(X5^-M;s6@h&I13p+z2@XCCp{K+AcZMZ2()SU5Z$&%NrZ1a<JOw#S3eY<nh<v>C22Er-l-;PEFxgmxD{b=DlIe6^7PdXq6AT^(9nJ`nrUL8Pm#N1?@1JB34;XZoh~AN=8VWHFjQtnf&e5tOU+zZ1W^6EERnXMN*;+p_6j}drV002`j~<;vp&$yHrjot4PJeVk0%~FZ>gWnuE+d-}5(UgN1|Ajq*7d%qFb)Jg;?HgP(n&M`b<%Cz-R_eY-hY1h<h7nv8oV~%q>RiMgI_h@dq5>J`{Ps(c7%+1Ho}QdJ8)Zm3VBVp)jD=0stlcb=i4%5X0CS?meh2wUcCZgy}4gIHsO2qs=Q@o*HARk#_8FQ%@O8>ME5BM>R<nGud&uVvA>-sAziqrLsv~`Fi2h%BZA#Gyr(-oWFe3RZ;+%#+Pr0o>*w_f^VHYt7qDhSQ|;L38(c%Ixd?iEMv3Y7-EHr(le&6GTGCE57*`<Cjt#!Ozv*k=8bnWF6yguxK74%t+m8>CHZ)0_Vgq9DZ?+EzFfWvusFc&nV14c9?m%ImaQCWuXebqytx#$fLJ*4@K$6L#m}$+XV$>TKHLOF8&r^TWYHG)RKZp5&UuX|@E(%vI#F%nQ^9;HsmX$&1K8WU^Y~j<0*5lz$qmZNECq?%tXU(#&2C$!+-mGc+V!<#Zec*^F!;x+>D9aG9cm}%PH`Q|LY*Y!x(@o)><X_b9V@eALwXR7c=LocV$?fPO?tKabag38ThJw&KLZIkeHe_gKZ00xs+v}*il6|8%r7dpSh)r&NXelUmnO%3VDxL9oPtX05{}B1HDJE%v!)xiW{8BjRlUmmkjS}KZ>RWY+Q5G+J2E|+iEHh+2Ew{af>xI6y#>GYNke5o9z?Di|i{_x9$$iYu5wC56T~<lE4hq{EIkHGbJ^?!Tkh-}~SlF+zXktqfT+D2LZS1>}h2FhE1R>3NzZ@kxtO|kr`uS4m7TZ%ofs9^t>iKHd=H>KJdisFN@|dQMA-KW2hhN#{Siyw<^C&p>4c?rm{a$G0Ls!*^&9KUj+nFIgJCp0<F^Jg>l1~ypvVSyrQ@R8yOpV((V_KAF9i;A^K~Fvh0~6B3ubXCe!`!s<Oc#yScyy@`ITitDgW;S-wldXnvvOZdf@iz=EeO%+iXtS$bX^*>xT{A6xAwx6C<RLm)8N9>!pvlAPq`ygfB9(7{(?@m$U&O&#%3raY}-qVeZ6QOipK>aMp!h&Y>j)d;119SO^vINl+yqn>mZx)snD<mDI6AC@Lw++YIQ&iOhs<nVlF+^2pJ7s2Yh`pO}*G=*C>e946&<h`Q`i=uvoKufAV^pxs!dW<w(kW`~l%*Vp0dR?8YQKEBpX^i%+32ikK_CH7%5OtG|QJkY|qLknBYNCfO*g=;5dc;o)EU`tZxUuMfm8oict)0y4KBAATi%D8=v4*(x0hFbLtV%@{wIOr^TBORBo0s!OVBnyOHU)+JS4Qq?6@&6TRM1ATOC2(!tu-H#!4;?P&Er{G;u+9jpEu#}cVG1l{O>mBtbx$2UnE=g+bN$Q;Q#G{`Nr?C2k8*Ek|7Erm5e93Z`EO*IrGiAAqL1b4olaOTfC5>Iu*d>k4l*az;&)@&|;dB;X11I$>jx2>61ZxubndD93(-An8pbvhxa&4jCU&Xs$Km77;KeImU7DAU!{nD48x7$w`S18x(`Sjt(e|-CN_=L6I579Z;*_&mo5cmJgpI=I(AmMnEKYaV}@%?Y#|MJ&wQRT#u_xD5-GW`Bd-DIbTJTegB12Q*6KYMR|TwUV&ojnwQ46o=|?t7A!G6#^~ccw4DD-55htVi~xqpR5SLB6kuU%wuER^@+r<h$)l<jTI=HQAQUZGr=D&S283;7+A{^H_5u5+{`?9ehEYvw<V$jOp-Co5xMDE2MVkCb=Yk8>4FeMS1_p(>;B*&Izo@s_OVhIMQw@*JWpI0uG}*D(zpQ3S9CTwldnYIwR%2l`JFO_%o7x_ds1M&)@8d5*NBz$P-swZ_xK0Qsd@J=7Ou-+|XZ~r>bjVrl*{WXEd##J-<s1`Qp#_`yWg86*}aQ;5+G&Ll$&M*Ox<bFW2{q=7(n~XPfbC(#aVqX`iUn4)9F{BQu;U{6B3oiwJ(Nz2;`&Q>D86vD@8i7FIsgNsGVmBgSt2Sua5cek6xv$~?yNCfxe^5meb)fZQur$zs(Ih=YF=+)2*Q2Np6Mr*6f_O-~-hLcAGrhOY=j-5X0T?CwXEq(=P<41j_1cDA5M37o#bkO&?FChJ~gs>@jl72#WZ2XCYkb+Ts5Z!fv)sBjg$e5%W*y7cm^`tN`J!>xu+nQqM3`HhPUf>e{(!M>7gv8iUV0f#SWKC**rpn+|8t%_EDlD}toc*Q;>Oead)uJ*}<B|a&>d|3u)@6?wYJFg`U`~`*2Ic=T{&~t|E2!lR`@@ydR-swJYsxYUZ9=BECMt`13JI1z*ud>t?CGAz9oW(eh)f6<(VLL*dsPaLiF4>1$Ww#*=Q$%trhK7>UBMw@TkK}bc2i;y<lC<rC(#sV&LizMkTQyCF6s`?26jnK2x(uOuj;d~&vqr2_D5ZW|i_47SQU;4pya_*`gWFS3s`>jaJvzUzH<o1Ek!?TWRoxREdbo0S+f%uT45Hvli+2hqXhZ|qF3C5rDX)z7ZzG$uQdYmH%}u72!l}#%<|ow_4l7+k@j5K|UD7>M%EksS)8?h_V=vY>Je)QbwBugDbc~JEl0B~nCcsitNLtAa-V#h;_l+cPW_XSG5o&O7d7~IyP7g?6F_+a#!igMGj<rf8NNT#K^{?DFD^d=NgKtP{1g3atWf}39-6^Rk+{kUT=OQOTGRA?heHJct1oO<$?^ZEGuYo_WXY4)A7}g>Y=Qvw5f4S;XET(i~Vk>$0zo`@@l?v=Wi%p4*u9Ed7g=}=^eWDMaBQyCXSSb0b-*DBuOUE)ydR8SFnZ5*QM}9Ds5~k}j%wk6ZydJ4lnNNs$i=|m!2({sv1m%xFTgmd^x_SZoQaqWCsAVg5tCCZEs@TlzAE?jhEGo)E!2$GrYUq4+v2Fa}t-;hx8Oaz~LLmX=G`?$K318>?&kvtk&x%3_sJk_hQA-pVCU+>9@xutKz&Y*ca%t_PImL+)N0r|D(l<$Hlk7kEM&p-8Vldh(+~y8kp`$JpyP4zNN{Q;T$-u_$mt2-z+2BH}#>$SSFkP@*rKUsS*m+L4PZ{wgv1iZu?G!%zlRr%l#EHF5RQVro!+-hu`Q7e^?dQ+`#7dGRdP(=@)<k2-MK4N}QHZSeaDUCq7Cc%;9*|EeEMo06sW!=4gsp>^Aqm9iL=JB{X>x^=`HlL;vD4{&GNu$tZ49RR?sF)yVoduiKDuT54y}*(=(UULXQoD-20dvNp(U|6ooRJ{E&X#R*3~KD&ZnwN4I>Qg`~ib{n_}%EtI_2lu(zeqGHv-6UK?hyKC$F+I+U)l$5-;~t_lVo&o(xVg>$&9Q;zqVxzviwa&m%#E*|nv>f=3kPCg=_^6>C<+q<uQpTUwhGa1Q|83=UC{yV*Xb^bOur}G71!A<DLzMs_sF&`CQ+vFcWFiT3UqhJop#H?-t7`tgorK-CAo+^IQB44N`U_E+2?&?HlwxZ$v58pm~eE-|`7xDEQNTMTOe{9sb@Hw7m`JMSBUHf%Gj>RCsvD{`7AzaJ-98;e)DXAtktRDKYh0E~N<vkHRsc(#)_BwbLW#s{t`({jJxdcO(3KFz!73}(u%YJY$ws*(6)nEQ$Q9&Yy!dL3fikABFPq-JRM}kyUIO`7I?4FQ1Z<k@W26aj{P2syRuAsRCSfc0?cQzKTWwm}>$!BikRgEIt9VeqIG2cZ=^9D<r*G)Fu!6YenfKwOLQQ$x&?lraG+4o6PUu?E@c^3NHo~Ii0?8BNwHLP+sJrZ`Zjp@nE4!K`zW;V7za_1i{gm^U9OJUGWd)On|E-w^KU4xSzMaVw>r`K3lA41huospiAK{C28`sHiV*bNdwijRBMjvDrEEURoRTFX9p8&cCHdhXk*`uJTix;X;*7^oyDYsOOf^fxTgyiKJtp$JYhz-S(>uyje`FwQII@lNP91b>nO%wZ0Xu_oOi6l+5E3#E;~wcEfeS9x#`PeLAp*jB9%by>93uXkNtOQM!Y9U1;(9x$jjEG+T5oE^X>TXZ-tP6!HkgtUdueuJE{<#7F{nU9#zX7$SzDYTa*FmwbrpqG#YNA+LV7T{C1g_2^g7=@8{2H+k0-BX>jmykh~&?FQ~?OD0KcG{w^i#mFi=n_ittj5IK3h~aa)7*z$5vkRne9Qh?i7~laB#KqPHe{<Djd4ZHVFP^|{js7UiiOAUWTB7jdMMHr9gxQcWr>DxRo<Kkv5LCLTU#L$_(xvAs9YzJ49H?gYOP@GsDDUFnF2UH#Ig7CUhlwPh}E7_X_xkvOBTtRaCo7LDvMKv@8iYBqU=WrieVp)3x4_V@gECiT$N^Xc#1xFzUu)Q(ZhhdM~Dtze%@|BHP$*!={1wG$f!Ecu~hQM7f|CPgO5?B#WW=3!#kAgpiMgIpS<jCFywMW$gc8F$x%hVjLdvf7VcwU>gyRQQg96U#?WFc<x}aGG#**7DJl{PNk@k$VZXcmT|Stsap9*KeK%4626SbT%#$K^gHM6g+{N-+nv*ew9&<*|2W4R(WE9iQDo3|HHN)*%DC8g#y}aeg5g@GY+mmx1{CsH>+(wHvCr;3HwWbQYu(`$1B193Q%4vO}k2O$FSrGInW=5(~xUwROv}mHUckJHizq*&aT4LOCa4C|JJD9wqu-%G#!R?>bwJ`Y|9iTVq-}LGBun$iPAd^WxS5ix~lt(mla;}P&4Jm%6)i$H?FW=&84QS1md!aX9p#tzg3Q*$Mg>oI)W*g+-hrYdN9Z!2z&AfL2pCOmnP2tiFg;nU*Z+t%4<Cw-?{@baufZ>x<?1y3*agbZk(h(kR$B*}SQ6>bb>KufogDE#YA74a2eR2%@`v|llbSjAREM&0R;8i-L#w4?EA<lt>9P04Rq?|x@)a}&!bbtQ=d^wGfi4BQUjgeJhWZ7|MiEy_t(fc-b;W+@so*((b2V%Fkwa0DTnOtq}M9yef*pP+Es|S@yh40CtV=#YOTGLy(c=j97`Iu}a6*<Gzt1{_oda0i6ihwojdlHhzENZwNsVp57z`Kn9rwPloR2sT&nbr_piI8neDR<2OQFkR2Nv1eh=T;=$jxr29VCE0d0`Iv|4nVZjTdd1mDY#rsE%F{!nN(909q<bsKczGsB>nFt^4>fpg8>As5>l?D+*pv@z%?DNmet63aXBU}dWPmJ;sIw*fOQU8FV;pUs+%hhDWDtp{;q2Q<shD|g`Rfq7<IwJuS(#(zM5pG|Mow*IK7e~b81-m)5F7;tys(Vre~;HKn#}4Vqp5a+SO5qo4+A(0e6>R_Fje_s(qph$+C9(V5sLS4_iquOOlnqgOSE`w&N*<g>~{%CbaHGn>?vxXB34AKbT2lkH0^<Ul+u-XQp^Q5e&5977rbAh{;|?A~1-7+)6@&MINz#lw8<i(czaB4dHxZaL`D)r5@O3Z9hKzy3jW(mZAiM#LUeushMx_2G>YW;DD*U|M>TsH3UV8W5GhVUit<W3#OoM50X{6x$V+dO9T3d?~m5?wJV@+V~&8GOM?D-Qy-^tH#R7oSn?>^86w>sa|^zIVRUC`CVD)b{}_6<jOU$MLnrUd`&@9Ef<NG|Tkj!LBq3PaL-^s_hmY@n`|%-yaIE7N;J&;2i9<QtxobgRNKc7EA9+dG)YdX&w$9@?(Sjt^OA6!{V`USG{!P;i?=g<c$D*A7MiwZ!ms^z1%aZUP>Gjk1ckzvzDg<+$0pu*qgUa(`PuTroU;1h3e7ynsZNWB1EHIZ86R6Xg!^c$@#DefVICZ^kQQJNa0*hJrkrfeaO~_qEVzCP2n1pA(qsgJAIzcKbQ6wZOflUWeKBP(E18jLqc(*t6W>>Pf47Pc+c7*T|DUta|*?WzZdxN+eI2M!fQ_mkI|0Jr?FHqslWu*G|IQLbllgT)Tz6A8H!xCH#9`&!!Z~ALxGba`Gz(Nl-KxNgk<|Dd4SF?WKrQefWXQ{{6qT2g}6Z^>UV#v&}Kvxy~tz2hIWKdSmI&JDJMl67llR(PoB;1KWrzQDdqJYJi8Rg+g>d~j|vPRG3ShCkWWVEMqdtqm4YImq$TU^*i37)#Q4htxEr2+Usq5%Y&GYSnWqSFqrjfnsrO7`xQR7y-?5$)&%O#)f$ZNUax6i<Qu^M0k(>5j$AYiyCnVhuf(p(D<k=huu&1RHqH64IfxD;t1KV|3y%8FpvO)JX`1PqS<w5{=O5$jx@I>%wdN1jCAvjeSyKHg#nE(YG<}q5Qf9k|)Q45T2abA}>!YVtJ(K%2HTlDcLZrBohjB3^riKaulnOGC_^V615IYVh-QEiJ)6jo00t`79>2_Kp3tjok5wC__dgG+v~-8y<bmNSX6w)f{0eWYwJr^chD(2;yRK2;ATsTMm0V(r_Z@4q=++=k|F==_gi*TAyv;=RGXt<(0He324_;0c6bh8I54w4aH6y--^7x(qFYwhF`1vy7E}Ic%d*|LKhQD)rN)Mq(WK>%O4Fr;pZm7_ILLk&603)fXgjo;OS)1GHa_`YrMCA~&ug2U+!kcCReJJvaB*7C+3Vu@+vKWFaML@8h;vsx(QkQI$w{z~9(dbUKbGtsqb>)QkdS2j+<}8cR?rT6Xj|2`sKrKHL6w$7)r9Ka+HU~whz=-p?j9Z<XY|`fh`l4=xxKsn>wb$8IT{8<!{Q^|rTw?~rd&w{-8e~Bef?idX<8u3AX{gl5J-reMovfTziy){%)N;V!8zz`AT`6YE?ePNZ8%fGj?Px(7K{Enr^0^kJXbqJhYj`>&3f<t1G%(UZh>RjhQlXXZkrZ3&m7RoTyqQvgzNTH_N=*HaEmT1Q0|KyAcabJDSA(-)DY~Ikz17^I9zL8y*Awy1d8f#jO`}?#WvgVQ7T;O2GSXv9$L+@=~uNfP{C~z%wG<lo+9DofMj43L+<QSZ<pwV3*<&f=oEr{m1GPBKMQVM+Jiu++y4zZsy3vihjfs$q?3Jce_2>=s-qYgr@ksGADhzDp4^A)MLAim%RH+Yf<6x5eSJaDm*MPl_Jeu<4{23d!8WE0Ook;Yp0T8A<w=G@FHrtEdH=DnxaC1<R$PzQ{^rV+of<GSjMxnHqoWh);OB#F;8SXb?XflJ^b;KrlasZS`>Vj~_pud>M+%A@P@_ejaQK>(>m)rbZz}p!I$*P75a8NZePbsn(Isb{RDi~g*<+D=^ooO_t&5mJf)H@!5j%%9^NtNVfy-XLTU$5B)J7_Zl#!4et0ClI)ib34!!5B9uMt!aI1O2<KZhD0x-CwChH7B2g0>7MDMhBJQj@XK0JC0^DGJS|kSZiqURvZ;Ssfg-)tx#U`-(_|x@v31#nfq*`F!Iwm`VGQCe-s60>@DwLrpGfi!R%_$nd#GUk}g4lZ&^rZxa#?1*P9P38-O@@GQEkXg#a3?aESa1(%`JXn}ynb6q}1Z_XoSL?VM6Dyo61!iSr0Y{=Qb-qR>XKLiH3DAjjG(5H$sw6PRa8iL@p^%9lTogZ#?I!Uaz=c|h_ALcm7|7xMn?|JR6GPQiT>M$%O^q?BN|2;fZHwel(?Z+GM{D3Vd;Rt3A&Wnvg+8t~%huj!kaL2ZfNlLJReL6f!76(F(I9z^IB~h;=eLQww3T6rc8#1^f#<~QtOoPI&gJ_a405R>?a9@sGW_!=EZ<nG%KnzfH8%Xh+#7M`3n7T0>LD*K*0Oge2VLUo>5^AavaTI<sQjRs2!O<_6<LtB?VJpX8J)C=mx{^xx@+zxEfDv#tTT#pI`m@7Y4C>8nW1^18W7Oef^Pg~@sCJ7%bxRcefE<DeO@pWhSYOwd(H=lFb8o7vIm<ZUU%9|qz@f`quX<6(8C1*G&j(W-#;jFTZt}TtekWzeglOAFII%F+aB{A?Ak!Om|NQM4zpd5)psj>K*#WI(ahFr&Hz>qOz0ylMI|6_@%T`dfXiSvG*p|){6?3--9p3l$9$bP<-S|LB0)5$tik&}cd350o`1XF1l5ne${@?!e(?VFpg|Kkqs+vtX<@-|MkdjAUpa8916|q2XjzKXCZp#ZtLo1N7gE;m(C*JE#Eo}moe2y&FwLr`UQWM2^G6X`ci%Pi@jc*!?D(!<iF!>i9E-;D@oEmVZd?X4`rQ~0<NPkEGs=$yFFrTQ9s3esWOaog<1Uyb0aGzV)qQDseH6}YSW?e!BKQbggU!qma+m#Xpe5V^NN72r&8panl@SG33!CJ+oUvaeL2~XRlN|PwkK*ICP6uOSVEBYo;D5=iRNiYpc)jSJU)4qtr8Ig*?q%VVju;-Uj(7&#8eLb@6;OZg{=Kvmx77h&*W2m5p8Uahfa)wk#N3|`3nqf#fmh&)=Ef|HA$&hes87LmbCZpXS$H~sA_?Sb@*0auq?WWcYjd<%noieWP`ifiBSrip0^3`iF^>NzKHI<{%gdcuF%UY6tt&GK$xbw&hG+5A}9e}gTL@}Bw!wXS6hHJ!%&1wQ&3||WBv;_eh3<~rt&9O~eMw8ZCdVUsGtPD}pmDVHM#rA<3nF|TEC)Ip+30~sM*U#^EKWsmL{^yf_fAhkOuRC8xicQ0JR^-8Rz6V3{pf(qVQ!}>Id5YYIBL*xB1wHt^)}KZBJBxPHLFU<+!K7fa{%RUh*vOWg8>cv|zEM+b@)$)eu^<w%kOAfEzFRmAtnh(e=A0Z?rq)e+xTAKS-Dq&H8#@{UqtJ>K6_rE#rLbkIl6B$>mF!TTTwLgZo#alSaTY<Z-B>zg@o0InKKWdt9Hp9B5f0>9Hit7}K4&1(_nM4DTZp3q{Y7L)6msd)`bx1oSoK;mw|E$b@!ZSK4b`lU#MW6cr_nk`bWLm?3o98_ZGn)fIx<YMqBIpuxYc;-0A2U|wnZMxIi!?Z-8!H%ViOMX^~`_{Y~a4)*$eH5U9{?uK+(tBn6N&!;n?697{;JsM;cluFjTh&?$d$j;`N9EXzDDg7Vu{Mfmq%5@E&P+h$Dd;aTc#{W^`aecJ_<3JOr<;{9N!2o&h%1IgiDMG@*FO0nGys+B>oj0`k7Rxn{A)%kD!b3aI;@cx-ggAZW3q%h8$^OV-B*jT;i5VDQ5-DLUlFxw?=(A?@jm@1#|aq3_2k&ZDW*j&7KO6PnZkWLra>eceKe7>4GS2zc_OmVR1Ew`tyxp!~j0aRPCN?Ofh->+pA*kSy9neiW7M+v&KU&)w&Ru&KDJ$SN;HUApT?4-2Y-#=XjJYsU;r-#n0Q_8Hvg8vtQo%A3Sb9dx#9oi+cz_Rem%k>rNL_xmh!Vf|QRUv74UV1Y?I7;K=cAn*ScNq}HuOP0lEeTRo7_uXRA({6RMSS<4Vgn!#()2<{t{H5rYj*+xOtW|;oOeJxYh*D1)X5BWR4Gn##eL}?`LkTx449`aTm`Oq*OVjf+szPtpg69*eQPY8vpSOPPs&IjJ(`WHcv8z{iq7aj$0N(d)0k?sc17*kRCD4z)+$xwZqHg$~+76pg&oYT*bs5HzEmz2OY$1h8r7<eCJ_E{S(L}d%7;S(df>Ndy0<On5+I*H4R%p`stC6D$AO9Pa((`~ME4SBl55mv_a43nP;#JBv-dx2NZYt?=$3(YOp&(tS+`;O`p)DWFW+GicY1UQCc0o?73~j0yI3;Y0$s<KHR_@Lgamv|KMem)5c#`6b9EH#*ps1Tcp^<=Q#i%SRsJ@tdvKf>$9kdz;#HmVRF?rVToxJK9sqjp{9JIt9JzDm=Ih}!~?5&uxG#U?GEjdt~_Ns>Tg^2LGf&Ay#h9-9zjKmz0Wd=8lGOqt-TYsR-SSEsrDoC4%1^2O<rKoFcp8aAYC$O=PA^A6j4x^#R49eJr!y-$<84;cvGW=WlfHPfHQ#cQBg|3jNw#7%O7y)EAaGwT`u<Ql%@|o8R6ZMv`9lRY=E6Z?<M2`VN<!PMYTe8@E-8zRl5DH(hsD`qwWJ#M}8V$$#wkA2ebWE9YBv30P#^T&6gr~5-2L_|2bI<A-(+CbL49k?=<OI&07SZ@>sy3en00T*1oxy@Z4Awk$wmS-W$SRYm=NleZM1QJBcP{D8bp4-g3&cQn>+?vEoDBNZs00Q~7abn{mZ(>!wD#myJ_g>mAE2jGw^k6NQjue!wUG)w=zeBZ^N60*CNt-B6!*fMu*8KE1TL9Gsy+HoDQiy8=^(%Jb~u2*{3*acyNiD({dMFOnn5Nx26IvlbV8ZSX=PVj%{#`oFsF|j@(T4lB=j0({cdPB(mf9nI!|+F6vw$31>qnPHt4KaBP@tm$(UmaC84hbqK(MSf(ycF06oeLphS5-@nk&*i>xzk(VBL?0-LLGUT#3b@RXLdEwN;6)uy0bNcjt;hNWZD8!0YPxku_k2b-snNF8s8gkf+6TAA_#a*$W(Mt7yio04wt)-Y7>%zxHPpH1VrsIW3T5D9g!<LRvY$C<8L&W(MQcVR!oo+fA%6UrhISjw{w@ClbQ5W^_BeIhSjxz&h{{1A6suT!yrV!Xo+wV()2y;tbICla)%jTt<3lEn3q=3l)%8nr!;14j?(Hr1^paY7^vK&Ve>uv%2i=u#a(9Z;vS%(wv=D*52!jWjaJp=3q6<qSh^b70N>pjx2{B`J@_cIfjqN#w(3`6ZvurBH~cMjPTS%q+&UnXwdAz8OEfr(S93odNnqgLjvB#lG^Dmdyyy3-4ouojRb&Hk_?@sLXp^>EZZC17(6vu@bF!){9i?0dK*h%H2BYC`sAjGzAf!B@hp*Y(X9~od2b@U&=1WsFZCmO(#$5^@T2OfTO^T?5g`TWEi1Dt3m)!y*6x&7Py?um&zndidT9Uq5EJCGr*(GJ2vNc6+VCjf%V&R3?W<gqR@xj&4|OzIeO3`BZamYP`4I?wIa(aFCznFxB%C91>CJ3s|zEvNQkR-grd0v*jh+lpTtI6d2S<1kD#ZLxZ#LaW~TzT>^A(61?6-U4%gSdFDBWNYb)vY%n|C_d6d45QICq*5|SL~mM4YPqqUr(VBePSMGot`#<?dLFkR$$u8|muSYI0r*J-^fodj~C<-G0PfxOwi4BU@yD-@Yde;+CF>>yu2lqnu-MLGaEF_`7CiYy<m?OKiiNyXVWrSzPRZcD}`lEZc%EHu8*mD5IZJ=|Y}J<?du1%3=k`Y@%=%@FQ7i#3X3e&BhsX)cHkg8*`n2;P<<+<(bKE)V5h4tiR$OhHNluD6?Pl`NSFI8CYT)uM2V7R<CfF)qbii1lk@TFTFfP-Kh&bTxtPwcoL327(jJRuNk==}NGX;wi<YgG&$eAcz|Af*b*ua-eWX?#YaEYrddV8l8xW)=Ak%*OW^5w^#bF-`-%?0G2D$7r<xmf47)Qpn?|c89`EsC)3Z-(h?2!nDZiirSRUGs(%hRpfoAD94LcKqC@R3$U~lmOjs`>xqfdW9Wy+qRUyfu3c;>yW3v^4?pT%2255<oGh!vs(~Q1+4B9`vL#W5vD-~P13Mk`$aoYgv%WP-GfdZVL=Ad2g6I}Z3tJ@Vu+I|kFjY{djr489CP}lCRjH=Ex9^qN3I<i4y3Z0BsI88ma*dB8!EeDEg?cYZ?)yYN83R2)R?>5ae8ol6PDNduZC8kpnN^BlW)Y~3aj~b@u73|3-<K1=fT5mJeRzB#Jt7>#_D8gaA2iRlkK4M=r(GQ%Gs!7JS5;s||RKpf<4(^&0Lz_Z2!n)?@xzPbFLQfjjXc)&flK4~f(B+X!6*7U0%-HOVTnc#+PC=FSA0<IhV@wj^Fn%pZxtbW+JjfePO=#~oHwNxb1M2+79f(yHU@(bRsjx(5RsTV!;T|(Abf+A{gXK589z&+G%DzGU%o9=aGp!b$Rk{Jwrrrf?780AqhKvLtCF>AhO=rVrpj?0ayj$OpIo)ej*ToEwEcN`xy<+M?m(D2aUZDFLV-iibfhZ;OnQy=UwbL;*1K1fnER3+p#ik6jVv(h9hYqdO1|l_Q-`l20H82cVBMdA7Ejw~Oz`ReJm(ECrR@`ZpK3oxxs_o%`tnaj+vj>@kJ`d~MWb???xjVje_AH<Vpqo0nP+~`tWU_CWMYWzP;j`!F(6aGM(yP^{jPUY%8|1>d!=XivP1U4yE<>4q7Ku{yh!V=PiUV=m!W706cKxP8ed}sob<fxvFDPM#r%v-TY6dIr+gbEbB*^lV>J6-1)!a!OKW)X#_EMBs1#9$KO8DGr2%iC5%*w)4TvdcNl5#OxSnBPnkxbw_*lIIUMu`jc`t4xQnH>g`_K~~PefSEW{7sDSYz1;!!61|N1|1`Oa+rsXiIXpbsrt{FwCCAzH$?!T(_E5HrETo!tavsLiH-Hzz1p^KQMOkDTqXK@vd`udJs?HLOr!652Pr=F^z2s(VHoIEAmqr?3x7dD^6J1;cD(V(NxU=lzJQ<X%R84SvfYO;)cU=<Oy5q&uA&q<poAz7oOC@7v~XgT$UX4b<XB60AbGAnL>Nl3SVW*Y5ahn_*{O#eO3|SAyzT)kwmD_sjI9@(Q2-B|M=iv}QCo!U6&E*X@vruaqdO{W2}^ppxO8krvXjyy4eh&!fz;UNWUXn0mR&k9_hY@~rvcG`R@SUs+ffD}H_nP-qMfjF8a$b~nSQy^hAwUFT2Mfw3CN*aWk@ZZ?M|XGG$Mp11;e0al#*isQbG6wsRSM)%^f6c36<Vg9~jj~%_+z_*|BE4LqqbrVmFILp~LGlYlxu$Ek7+n5(nfAM!>`8Yw_($END&YtTQur4mQxcT4+$MCsQy=w_AEfDs7c((S*&adAwbzK*T-{utZjl*HE8XNkPfbKK#TPmTcy!i_R_jo|=Sv2TE6N99U0XAsf>cn?RQ&nIL9zJu39u$oX&{BRToca&Tz{Y@J*LlC6aX+KuRfGU<Bu^ck$zY(;0i-+sRQXzW4i>x8Bxq)+Ar43i9n5=c`2nv#uZLZN-S1TkP!Jnqn`I<O_+H&+e80&Km|E}m6Ev^%ZEQtX4Ub9b`X3O$+M9D2A|3In6|J%CZE!kwB!HBD=sI2N{&>~`1|1=}nrC3GXo5$Vv9u;n>1IUO#xC@#-yD7}KcOkYyvitOMDBR%Ts)yHTiRr-Dk4ArhhcOaLM)P)G{&#|vXk#j2T{bb-HJiZ>ZiF9Yb+*W`@NTZu6+j%YY6x#X$r5#NmNP!NIavX;2H?k|(cC%YoBltyP9so+S1E-~O2~jyUhP3okg~LM2F)>Gg6YI&hYEMYv;2!-B`0<okEs759IZ<rvsxCKik~0l65p1lTk~Wbe7t!T#;|)sD9f(;M5Ae0hkz0<{TuV<3h6{_|V*e;#Yh7-I&+mtFFV>*R8qRp3_QlLc2>d8xu1rA1Rm*#hI`7H>=F1ge>kg_aqs4Q~WOC4*YnULUBf6aP3=acA+kqRHvq_}5uWW3Rt7gH?_I#j@n+0%xGDAQ@4yC!!Jh3Qqi#tPbrVo8$6z3mdH}(|vSB4vwFQXXFaM+@PF&(r{B&kRV&2d=6F9;AJL>_MD^`fMr5@+--1g}$}Ol0&Z@b+Ay=#@@^S2tPrI7CNb-0CRrVRp<q>SVbfV=cOr6NDtMnt|@1WeesQRPkMn<q?3YjObNzeglQ3L?y#XG4lramnwZm0Wab*<2+4FjHvn$(UuOK?R4lqso1}<HHaQd**(dBf+Cw0je0O*fBHUxP!>ADBrFoK?v8^qyI?;FZWJ<70zhPdqUt}t@#hP7rn)Gn|95|{I}m%By%>Qx5fbs?%qXWMLdCe=cSyfMh^Y`Fb}UyUR<<>Ley{_)X0S$D(7z3Dh#{nTwXIOGLvRNl&ATJ;S7feX!^O<TGof+-D}9UOosad(0O+14JNdN@M5uXAJ5!&huD559qN0V(`0U*@N68L@U5}s~dl{>oM|b<)KAlsZIxJeSc}U#L4|b{L)S;L=x!RxlC^E2%ME<Es)+!*-(AEgNH-UMk%XC6Bn++U-=9`SDm0aN4Zx+XjP4tsdDLdIEZp*>Mlp!KRE|YQ$_lf0wWsPj73Vw<pxvgF_q~1#{*Ai_K4XiEQFD$cP9ErNu?H?Gc3rl4=>^L2+onB(&NG!eX{=gVtw2A1k<Akl(=p3}*Ghgk4NFlQ^Bf^+&gb?1yW)>fF(Fi8VPU7&&pOjj$Ni8+x3A8ARF@yS0l+0hf7-4VM8e>gu$Ay%?p&0C4s$^MdCd1Zu_B;o2T!^NY-8nRhZ7waMq2j`YR7&WySFEJXF`|P-6d)zVo!@uyu62;FaN9r;d1%99cve{wIZ~bY`kIVv%}<GEL*~i%kh4hbhTxwJl~`!oTHh}HgjuUhS|Cke2$xw7jLrz&jMw?P=q)`OQdVbWEOwXkIQ8&xBWQjJyQ-vLrJQuIgnycS5^^W5NJ;@%cjJAvvGR)HJTMTpedI7fpT#D}4Jo2q>9XiRiW~lBMVkHkNmOQN|3$}{HP=k+S^5=A$)JXcvz<~yrQbcxn`UB{#%q5P1yph3V30wIcJCusf9)FZMx!4@Xt0hoxIBza*Ru&UZLjRrUkS$CbJxShN*|>z6HnJ@Z$beOYsBDgrC$E|-4+vMD@t;dYPq-GXUQhcHxfu!$mRsfFC4J5l||dBD<|$$!<sHzy$=56y#{TpA}0l)(auq^gJlX9zs9G20H9NkMqRDgzI1Hu3JxTK7)sIA9mbbZdLCSL$GR=4Hs~D@)h$Tfa;uPfoV0{D3UJiXX(>q(#l2k1yyd1Qwj|3JM{`j~$LfV!&OsG)@l|g=$5O$iRZIBhsL8LE%WSp&&K3493MD$dCt=392a|(u@5Chv{h+Xw3rXYy$jzT{Ut;?<U}Lc*+@q-6iDathCQ$0kzG+Etx~8Iq9GsgxDfj_j`vMl>K$BJGVk5Eox@$t_QWpsmRDF_$;?{1;NeX&14moTL&I(fM<$Vkx*t3pLjm}K;oy=-AB(7c}JyV&0Y|6)XUC2XGwK`pQ-odGCAtq#SxcSngC<O+h7DzBU@e&)8qRUNGYNjM19eKsVNpC~VOEpfc2__X-Hor}Fb2I(foO<QrP|ELNtaoh=fFbXzs7*7QDBz;~fp|68gy^_lCODpmN*tv}<R_#cPC$B0wYCNrN-#cOL6z#l_FBe68TdWt=LG@T66DcjoHjq2d?v~@H7)b<`yYDnkW%f#AZjGE4j#+a6UjB5*hExfN|g4KsR?qxq%Ss~ua|9ufxl$<=YFRy8lQVaV{X7L1(~DN`Pj{ZzDLy-V}i;F_S*Vz11SndIIu{pD#|^E;af)6KzR@vY$M1oBLk$;wg9bcPTwYR2<pSeR+djBL?+<+zMul@kMF<!cDyms-<AKu1-o)QGG4t8o2#-1Y^<KrsMRBo&ws%X%W1>G_z3iDnE%eOs7CrZ!tbqUC))PqSCFS5hiw7+WCM|pm)@YQOoy@?H5ew_YH+1ZK3X!J-j}Iu4?P8gt3ih|f~2Xyy7*=4@zDDx`NRX3oh34Oq|Jsx-UH(U2Dfvxs>qkSQTQ1f3|JL3wUxHkVGPCEe;#0+MC_wS=TIn-f~Kit@2%4xU66oU7{WTbf|kq3W`sl&^M<8Ih2nL+Q!0!CL67)zTflUZ5kS3l8+W(+<b`iPUw(MaXqA?)jW;PHSH|FA&G#Nq(aioR)r%b=W2cR<<kOzqmRljOX<w~uN21Emxp%%TLuTfBpJ5@4?cw18S<1Qlyw|XLbEl%7m0ecR#3ZMOKkZCn?k&8pu~Ps4KMoqZ&1*Z{?bosrREMsb&~=c!D#ipmG<>E<J!&D4xps-Pm0{Y&Q}TvMq$x7#Irnw@@Cg=eXtEs}e}jvNwH!f@&?sH~(A^9#JFTntsU=NDgK-6t?bzTu`<uQNu0aYFMk4;@AHRS9_OIVwBCTkWI>iRW+23p*5MW*?vsNjmmcgpqA3cG>RAE~^H<YT)R>(ICQHVt?Ajxo1Otxk-F>08Ly4ay^=&3(xb-H7}pTiNsuf7M{8HI}$Vp2J!qXu0P%c>xBA4GFdw(e=f?D5d2QPffJlcIZ+vt~IL1UOGkPxrKav3MAgLGX?)!#mw%P?;fK@eFjochwr}Y*Yyb)J+kd<X_b9V@h8KwX{hiI|;OU$?fPO`h61^gw`ek1?aLNLz81O#{t-LN8Oa{8^tNXannX@vhYJoL9zAheFv-3E{`|*JTLh#MiZNDF;4@WT}zMUYvG_zYF$q>N{}xpadqD@n!|z_vXz#SUPIABU)!fD2&C#Da77T8eYq$cavz{`lxmwzYmtC_OSWzBPGFBPX3(L4)c$-edea33yKUq8T<7t8ZnG77`vzWrn#R4B#%Y=auL6F%OxR<&I~08ARo8xB?RsilO|x{<k5gASx$M}-iz&MpVjFyV_?1mlarch?k8xP+3*6l%p032^p{r^XPgr@u<IEtF)KwyoQ--{Zs0^Lwq^Hs)P~ofF#-7n4f9hZrpA4erIUtgdr@U#J*$tDs&QnD+R^!p7KI2$agbl7|7VX4Tlg!G#Fo|xR=J&xvXBdi*5EDje*xacem)hEpQ6g6>b?t%+PYXAYtv%(oK>an0J^KqfhayK`$_JaFkg#npE%x=IeJCCmh#X$g2(vZ1#DWw+e`so2g`}JYU{43#iBE-wEl6SW*Mfn$vUt@2F)$U`w?#I3su408x(@jIWSV-lNAfDPwuluCv8!we=Jp)0ST_26^t#VH$vN9^Bxk<<fbcpo3DnUEJ+@p(d{+1uoUJ~E$R*<O^K4ov?UsKBtsBoI#~~Yu{!Ow~Skc8%q1wZD`s3wqzy9$;-07-2OV0l0`2FSYdT3|49nYl*fDr%MjHS~yQ;GY(6<KsmR%^0alU37Xg~GH>Yo=N=)taeh%2e5zJ~}ys`DA*%tn6y6C*iFrZB1#PET!dujP;CM)YYwLjuKwAX0kPt-Fqgx<&p5}_TfBNzi@*s?aK_7`^cP1*_sL0Ot@yk9+@y>ci2@JB_zO{O?9~&eVR<iB`7Rs-uPs1*UB&d{jY!i@^AiTj#U'

import importlib.util
import json
import math
from pathlib import Path

FEATURE_NAMES = (
    [f"first_shop_{i}" for i in range(8)]
    + [f"last_shop_{i}" for i in range(8)]
    + [f"shop_count_{i}" for i in range(8)]
    + ["money", "units", "land"]
    + [f"shed_{i}" for i in range(12)]
    + [f"seed_{i}" for i in range(5)]
    + [f"crop_count_{i}" for i in range(5)]
    + [f"crop_yield_{i}" for i in range(5)]
    + [f"animal_count_{i}" for i in range(9, 12)]
    + [f"price_{i}" for i in range(9)]
    + [f"market_stock_{i}" for i in range(9)]
)


def features(shops, money, units, land, shed, seeds, tiles, prices, stock):
    """Use only shops already revealed, own farm, and current public market."""
    shops = list(shops)
    tiles = list(tiles)
    values = [int(bool(shops) and shops[0] == i) for i in range(8)]
    values += [int(bool(shops) and shops[-1] == i) for i in range(8)]
    values += [shops.count(i) for i in range(8)]
    values += [float(money), units, land, *list(shed)[:12], *list(seeds)[:5]]
    values += [sum(t[0] == 5 and t[1] == i for t in tiles) for i in range(5)]
    values += [sum(t[3] for t in tiles if t[0] == 5 and t[1] == i) for i in range(5)]
    values += [sum(bool(t[2]) and t[1] == i for t in tiles) for i in range(9, 12)]
    values += list(prices)[:9] + list(stock)[:9]
    if len(values) != len(FEATURE_NAMES):
        raise ValueError("incomplete routing observation")
    return values


def snapshot_features(snapshot, seat):
    """Extract the same features from a native evaluator's reached state."""
    farm = snapshot["farms"][seat]
    return features(
        snapshot["shops"], farm["money"], len(farm["units"]), farm["n_quadrants"],
        farm["shed"], farm["seeds"],
        [(tile[0], tile[1], tile[2], tile[8]) for tile in farm["tiles"]],
        [row[1] for row in snapshot["market"]], [row[0] for row in snapshot["market"]],
    )


def packed_features(observation, seat):
    """Seat selects the own farm; its identity is never a model input."""
    farm = observation.farms[seat]
    return features(
        list(observation.shops)[:observation.n_shops], farm.money, farm.n_units,
        farm.n_quadrants, list(farm.shed), list(farm.seeds),
        [(tile.kind, tile.what, tile.has_animal, tile.yield_units)
         for row in farm.tiles for tile in row],
        list(observation.market_prices), list(observation.market_inventory),
    )


def choose(tree, values, active=0):
    """A domain miss or explicit -1 leaf retains the currently executing tape."""
    if len(values) != len(FEATURE_NAMES) or any(not math.isfinite(v) for v in values):
        return active
    if "domain" in tree:
        low, high = tree["domain"]
        if len(low) != len(values) or len(high) != len(values) or any(
            value < minimum or value > maximum
            for value, minimum, maximum in zip(values, low, high, strict=True)
        ):
            return active
    while "feature" in tree:
        tree = tree["left"] if values[tree["feature"]] <= tree["threshold"] else tree["right"]
    choice = int(tree["choice"])
    return active if choice == -1 else choice


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Router:
    def __init__(self):
        
        self.model = _MODEL
        if self.model.get("kind") != "mmpq_multi_entry_v1":
            raise ValueError("unexpected routing model kind")
        self.tapes = json.loads(zlib.decompress(base64.b85decode(_TAPES_B85)))
        
        self.default = int(self.model["default"])
        if not 0 <= self.default < len(self.tapes) or any(len(tape) != 719 for tape in self.tapes):
            raise ValueError("router requires complete 719-action tapes and a valid default")
        self.stages = {int(stage["step"]): stage for stage in self.model["stages"]}
        if len(self.stages) != len(self.model["stages"]) or any(
            step < 0 or step >= 719 or step % 24 for step in self.stages
        ):
            raise ValueError("routing steps must be distinct dawn boundaries")
        self.active = self.default
        self.decisions = []
        self.last_decision_step = None

    def act(self, observation, configuration=None):
        read = _read
        step = int(read(observation, "step", 0))
        if step == 0:
            self.active = self.default
            self.decisions = []
            self.last_decision_step = None
        if step in self.stages and self.last_decision_step != step:
            seat = int(read(observation, "player", 0))
            packed = _pack_observation(observation, seat)
            values = packed_features(packed, seat)
            selected = choose(self.stages[step]["tree"], values, self.active)
            if not 0 <= selected < len(self.tapes):
                raise ValueError("routing choice outside candidate library")
            self.active = selected
            self.last_decision_step = step
            self.decisions.append({"step": step, "features": values, "choice": selected})
        if 0 <= step < 719:
            return self.tapes[self.active][step]
        return {"farmer": ["PASS"], "hands": [], "market": []}


_ROUTER = None


def agent(observation, configuration=None):
    global _ROUTER
    if _ROUTER is None:
        # Kaggle's source loader omits __file__, but preserves the code filename.
        _ROUTER = Router()
    return _ROUTER.act(observation, configuration)


_final_agent = agent
def agent(observation, configuration=None):
    return _final_agent(observation, configuration)
