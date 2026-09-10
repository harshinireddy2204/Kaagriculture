"""Cloned tape agent: Mengfei Li seat 1, episode 106106170 vs keiz
Herd 17, hire $60891, margin 15471 in the source game.
Guards: weed-repair (DIG then resume), hand alignment, terminal liquidation, fallback.
"""
import base64
import json
import zlib

_ACTIONS = json.loads(zlib.decompress(base64.b85decode(b'c-rk<TW?%va{McXp8deNkdpF7OS87HvMEqh1{;Gg4D1F0g3W`Iw;=yLl*pNLtM0149L84mNh8kXeD|-ry1M%3|9<hWzy9|3zy0>&pT7C|#fR&UA79*m`^}4g`}IHm`k$Zw^!Y!3|Mj<j|J#3k`QQJ1`%UNzKfn0y(_eo1aC`Ii)0?{&4{sfRI9z{zvDw`(e(a~4+q)n9U;B7?|9<>4uOB|}_>7N-!`tyYFBk9pczA#F)8|KTzr6LsyW7Ky(5ufscKy@4AFsbO;mytQ;h!yd=i?8D!-p^LExLF-e7u|X@L>$!z4`N}52v5}@_VO`jmBjB$Jsa7AYEwf7(Hruz++$LO&PuX?$f*XZ-04M2X~)7j}vRl<~&|#Q7jw!;r;bbcf;(>nml{>wCRt(I&UxR+QU=c90KDR>%;N-?r^)9^~od6Nr&BebFB>ZHrh<ECLW&z=J{JVH{(t`zIxvEFxn!g;T_HLc^<&F>TV~T^U+iP^!ZSljTji>bsBfL2B#31%whKZft`Q%Ioj(@=4^l;KiS==)8OFs2ir6s&+da}c^l(-9iK0!w@1gzWU`%!l}?b+Ji+q<Pa~Q#ZCMQG5B%lj%dmx$8dLO@`R7(0-Q~-!(LH@|vT(kPT4iWQV>dj&9og~Ul*hM?=VSXaoqhV7F`UEO`Qe=Xgg;>Ij~Wl>N}VxZu?H*-E8Fc*JOpih9hQ3q+4b6q030U6VuTlyb^x9(((yBf%M~B3kMENoMi;1SZ;l>-Ea2q>Zr;B?yt(`3PlwyPckkc*%hDjjpCC3F`cmR7JsVQ?!-pmP@#fQVss@8$^b^F80dDuxZwr>p`IAQL>&@Fkiyw`XG>yaYGithTd+BZ6Y6jS_q%&@v^oY?7Ji4Ijm+{-%n-B9#Y1sM==lFO;I`4<I?j5u>f5*-JqYdv$rq4f`TQrqge%3r<scH84T2MgY$?sl-q1`!xe0eX~LcU3-Ir`fuyrA225**AeC5UH)ZAoabvY*!6RWvoO-><hCO~tZ(DJPo`JoF3+d?~pi*l37$z~2#YYNZyF<&Rq|{V*SK(tK%Lpiw<GLXn~N!}aYyD}6wNK1?T^*dW$~h99^7+~&?jKYG;E=U4z2+72cFa%BS`_hf!y87pa+C}ZM{t8H&aBi+mNDbPflm0vaRc*naoxMc7zlMsN0%gy3&wCThtm$s5`J&6l%C1Y=4eC^86SjyIl!)Favmule27n^2&#cjRlbs917@XJLr`nGJvIMWRfc*y51K-!hb%_u%6ax>x%!GK;q;A36%=wwvQ7jjKFJs^R$%u<1a=#Fw?tzgUD7+djLp-TnYfyA6D7`Ma#UACd?ArSAX7;iiKXhcsX9*AMY?IK2;5Xm^B%%d6hmR(|GBqJSf9b}5>fRG<4GMt4OOqU9!%}u>;zkzhU;IsH_4nH_R@N!rvZGq;W5C}cbNN@9=hON`f7V8w-r1N(k2J-gCh@$mCgK5)HwL<AuD<gq{=U?1w`w)iE!W6#kVm?3K-CiHRJKWy>1rG+A)6q!~Fk91Z0PK3)ehnB4@V3()Ls-Se<aNNi*w9c7Qh(r)ah8G90>C3O%}9_tV@*LTezD?IMt^w!49jb2G_>K9qraLcTY&T#FvKRbHB9yJmymvH`&fx%wD!&|wwGG175#^Mr?sVPkOt)caCx5mXAb6N6efh8)8$%G;=Rv=b}#nb{qHcMeYs9V8`-h@Dz?guYVB-*LH%b9pF`GS{;3yXdopr+^nkE1r^hfPdY+gv)S?f`%x=HUjBRsp?dF4&0<*E3<8L9@2+od2+3e9A5erXN(P%&UZ?KM2dZ)UBiF@kC7-XLxKg3uG*dL9uA_9?H*e}igflq-B0b&)%iw)-9E%L$K1(jem`010_Ik6Y?A=^*k#3-y2bYKwRe?dYmGG{z9S<n4(Q*wdniJ$6Htf?sr51nn)T16&&bU0SewpnhDI*&lLf44S{+jIdeZQG3rsN2~-C&YRF*}zqX2ZHr!blCa5+6ldac};GQv=aa&Orz&3pCivV#sg+UgBIX~k605Twjg}UI9Dq1J=L5$-rRg%i<=8Ixd{)6Lkts|H*(EJ&B>+okhA&p_QSpXRuKgmJ%eEc#1==lEXvBUKbOyV(%}t2qC-uC{X)oTUmv`zEqHuWP<I&z9`%LqIlpT)rvSBbdNrXT#sB~wcpZRTWKbFl9AsL8KS2VB%?nN(Y3>r9l8<JwY%GytBzb!5u~pJM5im2XYts`!+gC_k_2gp4k7%WYaM#DpFJ|fnAt-*EM_r*ql}P=O8h{;BM6$y^sz5(%(790MatI?l43J?L8{s|VKs}-evW8{^AY2eZE?{Wd?}(F%1`;lBM`FW6hD4R0*Z1LFp~O-B4V>VDKp)7aD~faGFeM9<Z8981*yY?RYi{9iCl>-EATeW*xE|Y8APj;Tg(G~}(&I3OVV|gCiJPb(;<O#nzk5)N`psiD9}f<;rkm146NC>N?ylkO;gu87YK)eRo@d-+!)HgYxJ%UztxW7=Z1S34HU6$3BLUp64Qk-NtLyMG)_Kgc$;1!Mfn|&{^NZz<?5Zar(cT$Y)Z8KSk}^7JXUIdgw-teeT5`?^*@HBJ*~=Nb7pwGm+lxl;S_rzwgE$-JpycVXY@k#gag`FGryVVJp+1u0Y>^>B&}q=H&*yskk`l441lKtMUMdTSJP(gyTIG@80noqn5zQhQ5wwxfvb=c_0?q;V%N;<Ch1)NE1%1(xaX9?Vw)&n+a}&LSh*j|U0d;;iGQFZ7T#0R88V=z;7?H|!k9C3s#F<y=Dvl&VQRkcQ$9M1l{P6FU>FF^#t94B*ex6>Q!{U4T)}qRT87UD%zDpB6RQZ94nh{eF0+JBVlYnS3h_Mq1Ffd3oE3|MLOGZ~<@yIkH0~aHFT3fp!0~?8GEp1P|A6=qokwj5|qu{y>7+9y&#ZY9fvZ#%$K*wWsQS16r&U$AgVKVOduC>(Z<Z}#Hcjnj0s5L0s2URaa*UgGdf)4^t9mD08J%mHlL0v9Y;|`j(HjW-s@vkmwPYlDn)qQEeRJsgZta|bc3}g#uk3aoVP8T$TNid$rfSA84%ey$yTzH17@eFIfvBkBT;^sj{CFy`R=|y^hafgI!%i9|pFDJ+!*W70o5s#oTN={U4P*S-RXemB`L-S>Fxx<MSHPYQ7a}lh2(wH)lVhU902{idv%#hf*c#BdU<%HQ3MR2w*apB~<UUbD-{Y(Y)u5V$5<aT0=QPh0I6+q1zd3>ngVp<OgM(-&{0Je~Fr&IbqC5~={o1hR0YA>@GzMRRxNH8?e7gcl#FLIbQDgzrH|1(AR_kq<h&zTZhLW)UcEG5d4VR1S5$1t-NMhpo_4ttr*Z=WYjy<#a$uQbehxTwCrx%qeq#Xv^Gr7v?r3{c|-GlP`fFc#M{Ess!j_6aXM5(e}WyHM<N&3qxOoW)kU-?s9=QYZ~2ctF}$)bBC24obW;c1~!8rc!^m_rV?JdCPpy;Z%G_jyKIN^Or(ykLfG9Ko=5d#qi;N24v8GBt$0Ulk>r4gXX*C(==OkF~g1!n&H{ML@qf#MAU(Hxt`g~4u`J7Q}51>aA|T<xf}CpfC(669V&{AjdX$^t<_(pIuBK*I8W6$8Iqh?zAL1iB)Yv4{^R=Smpz#^k(US-3fKF}cs7xjm{4X+P+3RTu)-)sAi@r|ZoG*Zw16fOXq7FhhC5+@-dAK3w0wgxVI-x?TyQQ^QPVY+Tg+S>_)(Impz2E#Q;aL1(NYT(Bz!Dle<IV(=fULCO}=Gq*gd@|E}e{?@iPq8FYbh#*E9W^@n=smV~1T!Hfq~_@M^)K6Wm_B>3H}3SObU0#lCO0;mFXV;bF>bn3M0@QYh_^2^R)8z-57Uys?vTN8_Ou9nhfPiPGkLaQR3S3dmdi$Nd8W4|vrJ>6`OW6^#*nYUjEXZ*D;07P^)F5&$@(m!@luEUWg(CA?Eb4#WgO9ObC?>6=d)=@&IUBfBtylestPi1`k0kkN@U^l#pCMjFNmXtcW_)_x^h$Q3Lajex&MEmCacsvM7OBDse!8@VV3tRh12@!3EzBu~`VM_?mLpOWXq8gdl5eSDQ*?ZJ#IA(1Nyhe6SUFR!{X)+(>UItMz~C`n}r2B)q0xG^)zz+0+1?CZ5)Lhg#F@Yt#edQ$+=Qp7wFs8Yg`H2fw|`xX5%iZNoYGh#LcbSgXeSS)K9UL7#98yY7m1WkBAKK~6~RG7XZwl6Z&EXC2H0MWb~8nv8%ms8pTWz`n;)|H5FhbR|jUtH-5CxIJKtI9kBxl|nt+Gh8X2cg%rJ3<>-ShI{NMn%DDa{(PfWsNB!pma+)!i2TRi%`Xb<=QCHoStw@GqVr6gUU%rDp5nCMxmfFsc=Gz2g3Fs4z!-gxZX_osaen+<Q?$8-!mcpX&UndiHHg<_g+8Oh$4-gx<)b^WmaF6?50!_;5yRoHH6n@yre5kz3}yo8624?%F42TOTkS>_fa@p=={^UU#Xh2zGO1uJROzlyH>bXT`)|b*ePfvEGTlD$?{2#jIqArVF$?l#t(t{93}ua93Vva8A<BQ2{J*KvrtY-g#a_jg!Kwf6x!X{fZA&x8N2MI($%X|>BB@-dX}Hq&cGl*3-u7at^4<a?xoS9t*wsXb-{RZ6FOuK3xjJrg7^#C*$GXF;Rh$N6YeAW=U}PgJb$=d@29TQ9Lb?nqnUXnQcQT>sPfTtk?8pd#^NPfBL~rVZq?U*`i!z_65A-0S_G|4TfeBJw2n;1F4=Hj9)n50t}CxKn{bsaRD<s=m}JtF(dXa3`#yU=%zl(fpu|E!nH9&u2gW=Vl~2?~$5L9FH2lX$$z)0#w_p3*dR2;bDIaO>p>7HCS{E2xs)WOI^uPmWA5q4;z6@lCCA{JTeu|JNO>6D0l>F1_v2c(2DVF!z_SY`M9Z2{=d(Tg}REyuzN-f}LnOeQ&x@3-<ifW4(U@Qqj5_>BhP7dl<gd`r(vqP!sf{_=FPh?fcHkxuDj3Cp350SLCcy){jzb>TQQ80mgpFJn+L$Z`w);jmbs4dO7J!0$f9zR@zkc4iV{cf18RAU0$ylF`gPu8%sMxC*70RywZUGTo}mnY+jP5v0M<ue9%eyv)$iHiHrRz`T;vV#_dv7|v{Sx>=gB_ySPesYmR$~@?f*+K)M(x=ELp$biGkn@}$7H{*lKG5JTxihsGxanL9Lu?~X73WWvqy{lR%HTPwGOke!$kD!$l%Mg+Jr8i=csDmCY@iL_4JxP*_9&K*3jqy*A_37LYa1l-<cRM=nFx0`KVIM6JiL1O$3`P$Bw-g<OFFRdDN9JSLZMat29o6p0<TQOFb{-=-0LG%k%(8SfUVNYAPA<K-^Efz0n31l5bhcj*P}{@PQ~7o&Cnblj%eKDx=$=YKbFTp{3&7%qRB~^un_vOk~l3LkXks|2(<Z>OM{jBbb--=78zKRdwZ}Mupe!MhxRS?C;7H<!?vB_V!c|CFl4%+$}dxvRNsY&gsxBP`H1m3UV~lC56a3$k?(OsY&RYbp+2E%i5^dax0Y?A??kaaIo^kzo6pTPXe{;2Qbg<nezICL>o5<KK-EpSoyaO@+p)LyEBm8UKBTW~FVoT>(eGEbE4uqS0^?^N@xu1VUrpXReE<DYOW=uVu(@a%0qDWXyxp<oBiB^fsNzdecCt$fCROf7iBtViAh%)0n|tq0^vk0)_{kO?XYqVZYnyn4>$R1LC1PTNqPhu9<UY!IR0LGdR}WB@<xH&X^?_rQ_FbRp1QWw&)J0OjBY-R;-egRmKoBSe$Af1|x$aG;i3#Jlj+k0_N(D*UT4*Z5TyjSF(2=-GGFoexXd;PM+CC|{<J?KgygMmW$US>_*QG1T3TUqx>{KhbdCZCo@0&P4upS#JGeK!5Q!a%fMiwcIoYdqHjxB3`<GVbuQHY+2ALW-w7qo70^nN+22-E1v(8oRMn$_5N^40pDT-(b~0TD7ElLaz#3TC1+evp7?qFq$$i$W)2JbhA(Tsa*Q8-)mDkURs*_^@Ip7$72=H5rTM;EUs0NgUQHg6$TTT%qKkeH^h=b-ohuq@mw^+?C`|a0DRt5YLG#wlpby8a1U?<E5OSmaENV8~_@qpR>FBKS+-M9NfDS*Fv7SVo?7mbtMnTxS9JFYVTrXEsT_q$>uXsvWcUll<faOcD6MgD$yiUAUUszhkS*!*JW1>E%1Lz^hnbMb(kQX4p0^dZSqQ3<sL`2D8+lRYzb6xhe<%}(v|EukYVjnVI!#s7}_5UEjLpLCcLRFH<U8T$3|(QHh3w-1`fpV^VM?EA!S7ZT2e12KTd=Iqdk<1vJ1y>C`3^fd60xI(svSER6^}rb)N^wVt&A@N!|y#Cc=(Z`>T5;6Zd0t<&frGq4ZZ@RTBSZ2lxnAS!x0ISoQ&`{hqVi<(PlbkN{>0#6%6^74w0%p(T&$gh)&fM)uihP?9{$YBdSWPYYeMWu9^ugO+9=iu;8=Tnk0(cAijP^JuV7&GG3EqqB7z%fDV%pdnZ;!a*VC&UvR3exS}MiLgd139y*7e+Uuw_$p*)mN8+gE%Yq4jO0q>=rPt>UP>~u))-q0)~t}t-&{C2X#Gc0{@aAZLk=;b?^Vb$EWg+%4*K^?QP!JP3}>m&;p7+N(4aDiA?-dMtgF#ba1(X4_oyH=O+K{Nh`+K>)Ld&1Jt&~%F~sX*N+0HQrt<_s!W4P&?`LtpCmEQA-+lFU_}wTye-<3XE_sRB&zSjJk<h+(nf>9Dl+b`=mn6jrmF4!>(;dzKGEkmP9VBArrN|D=5H$G7$WfO#;GMp3q_BiiU%6YAU2qL8d9QV|cun|)hq0Pi+FT4U8b|8_xS-uBC{+dZsdykUTkma=<5SW_H&!kezi5iLGiN1+B=rYEY&JMmG%H<hG?PeZV?Np_|9CV>sw<z5fV)w@mC%3{_|;{LWFCL;lRIq0qojmGid2T;f>D`se;6PNKvEwQ<j{%lvyYL<Y2cm@pEY@N^0{PZLC@_K@?*C5UGCy6p?VypG`z*9Wb{9{x>>Vg`qnFJCJUtR6lu^_4RqHT_0l?Ml_{1<lBRjktClA~vYV;G2!T&2=i_E7J+3F_h%36&NQD^wRYh=%a_L#EY)#p{Yl&wS^*fktDRnG3W|p~y4WtHqnR<nS{5=`MylPx3rPo|~zKUg8lFE&&3j^ImsFgDCnMkz9A*$u^LUT68zw{HQ%X@;=rm&@h*)f;qQ3N8JA#P{C@M@SvE=T7zP>60*q6ru#fLA>+Cxb7iXrlP;B(A#1+^lVRCi4U9vgR8TU|$T*CrJ7?&&hn-kl!ZMJIew8{Y~x43Vp5s@1DnUXKyy9d;Z>7*82{U^}-*KGcsNO*{@(G>94)yV1g|bw`PdgrCYm6@Iebzmm-hIS*I$FwY8K+A}O1wL$OG(Jw>IaqR<SBsLY-gk|HlxLdzB2;pvgV&|;Q}&-_moPdrL;vZVlDpy&=9K4{HwBcc-I@=LW^5C??KypB>odGuHTU|3~`%fskLs_1;@c62(BWgkD*S!rdR+j5@0N6XQtc<M=?tEm5(H;l#iS24~M#W@0C<>~*Wtr2s0@quET>3IfWK*PZ0>4<ZkNYaJ#O*jb@)3)%ELoZ<iQ;7)30~mn`AJ_@UM~aj~4PnWT+p2m-zzGu+fPA+<RRx{%)uoO*y}MdB^uO`L{2PiSd|mn4TN6oG%s``L{7$46@X~5QWZ^PY;LK0_?ozQRXuWH|L`X2o{iV0>zRyzlXz^~>iu4O^fpG(Mo*w5=fn$m>cBb0Jv!jvuY}rG7g!_=jSAv>Ri={>CYZZw0f(7cWyGQ}TS|WQk42ClAK@=;NXBf@2D1^--iFQ)y@{mw=$tX@$tmA}cBi`kz7I#*zrgw@tAsFimDKL~m$u{0WPGEs-jkaPw8G@&_N7yq*a-#Q;0;#8N4?hldkfnX>PUx3Xql8rvThSF1$_C23#1KaA)41%#f^LkSYHm;=+aWQ!JSm@MB?c-Ll2NYd!U^{`d^XMLp`h>@`HIex(2Mp&VZl&3mbp@6r-q2YYaKw~0&R|cTbo1|0xIPj8%$Brajv*t`wXY+LZ)_GjpA~ub~pt*z7{}gr<OXL;8F?|#_1_Cch%Z}geWqdB_iS%ErjR_3P+;^ZsvEcTH^5Pj2wynhhJ+|08?aW3E@L|Cn?IAr8Xt=Sqrsmv)%(t_VIxaeNf>dm8$p}ZZONz=&uAEBuj@<F?c<>G!zlwwkZ6bP|1XraThWS5K;MjG^r&MGmZ}4Df3fN&L~@)Sb4O8g=%sAu`!s=lH17!)N`O%41uF#?1F$ht)NONw1YdcVOXI<&_PW&u~sw;f)uCP^N3tvcG5DmhJ|CbWf2&y#Aczt*P5t8grO#=^gy!&>F6z^hc%v+F_=E_+Rmf^!(EWvOjAsUbxNIFeLF?UH3(CV#%j!#F|&q~f<$;QA?m>75+R73&Z41}(Cn2NNe)tlHBKV@UM0CUxMD97Y36vv*F~UtIT`Dx!iML3B>~6KAd573VG(CWd1W&BX6wky${5Bjs{!SE+eejA0h_O)9A3oSS8JGkp}Bj|C1=piv4O!OB=8*l*fb(_8s2#!BPoPg#6&Viwj(0Ye7Vmv*E57LfPL-4ZBhD*qdhvg@skWAiAmyE=SR1!EM#~c9a|=0*fB-xU?Ds^LTk$Q6ssc;TNG8tK&4!;;_C7645?2H+vCpM@(d^|WlHoNj_uHm>x<x*JQd8UAZY|X80F_(_GO5ihfSebMgZYHc4ZP$V|S{7dIwPeJ!w{2=l+Ey9g&4>F};EX9$fzla**7ro{0izB#T!vLP79;*9D%4N(c=)x~_dG*FSzt;})J*IM0nMkrm-uhESGu^7&`=05UM89=%lU(Wg)`MG?9r;13KPA+1LWBPtD<BWem`B?b@0sVa~p!Mer)Aq(`mpxIN~mnJTB`E}qzQ%8S`)NL;@X5^^SE|UE^h9#l+x=SZl?KA0Gf=W#0n_~9V6~(wVYh*n|L}mnq_alL4vTPzwsShgtF`IW}N%~nGDWOGQF~Bb$sGE@<u_sd}&(aZqta+M$O$niXf=9jHCCA;udI>UzRgg!>>-y+b0c=jQ#&(toIJxaj^*&fhfJho+tzLq^&xPq$vV+hoE(F%O)fI|~xrijaNw}GwW3$V+Bo)5(a|udrq$AmdG171%3)eAi*vs~+N@kW34>=wHB>P!y13Zf7`3!DEA)GwoZfE;OBDRE>A7XEQYyMZ;+Sv1#M6MB^i0BP>#CQTaHK+)TCJEVBZO|?e#*?;`lpZAms7r#~Jt~wsycwC~#1RDO!{#&$2jPJioP`{v;8q1Ek8qS2gT=pS48A5I+?j$GjZ(-tVlGBkmOjp_67BzA!D^dV2v*x%gmJYd;EWf_-SgT(B9bNj;-!EtNl9hfq_HN-Ogn5O%EjW0Rku&mla1-1JSVLSflXc!5BvQl%|k9@DV7_lw$!j1kXIiK=*2QdCLd8^zfir%tXjMzSG!VIme&9QOx?-oR4a<P1QgJU()AKvzhH0poKlEc@Z<!Ws+E##hOCxRrke>XMPZ2qdxPqbnTB+9$|KS(>Fpd^;>cUziWgQUM2x)w#d_4mtY|SqAH9A5dH9tH#RUY6y(u}AH)M>v!;cVB#6sJVF#Fo&dMaj$H&NEd3WTaiNepFOM+(pdcOsEwNQ;vB8!&Mj!iE~0oN^MmpBI@|K)1K~Kp8RzAD4R<ju7oWF^U=>(-vZ(lr-fN0;2psKViXyg~ZJ-l@L#?;^=`v=xGKRG%P0m*$C*deI}_P8%x@3zN*~4D+w<Gz{)e{?rj5TP6|sZs%md+;AQxJU&&ZtcaX!`9S$dsS<Z+%s=gjMslBL2ssj26PngP!u^=kTD3sy|nkD)aDq)ce-=_1EWxNwQk*>0A9$(9z-iV|zNl0erc|NPFQTera8jha4gbY}roRO1FP~V|`fD12`NdJsqNK?shW*|8!5fLIJ(cV=gjyWzYGlZN0g##y_vMP{UrN8_7cBRvY7r*w3Qu{~i;<#$mB4IpMk{^n>t<v6;!JD9LT2Lk~M$4+9JAufJE2hL?fqas16!vxaDl$3SO*|@d<RdlUY5NHJRysiho5`;NPQyFSO<c?ZMS~nHykN7V8pxy^ToCT+QPiB+gy?Dcnx(2ouF@6V3^*-;vH~U$CJ@ch^Yihb$ni{G2f+@F_0KL4b>{T~@_E=Fw>P7tzCS$XbH+Me*%@^UDCo*l(yAaqP36-33Pe$5rwA~FB%ldg;i6VGx~r<+G%5?`a)W%ET*)EN6G|D#q6$Ao?SvIsP?4f50f|<LI?rQvn%ANyfdD7Lmz(wiyb<x&qJmlo-{5XB5dJ({CQr8uFCks4d~!Sl6ypsS6t-C?-ys)4p?ibJ8_g&-Q>)?}%Jk+Sd0avJ`xs!uba}=eawi()D8f2kM?wJf*h8uc7O_4?P^`fI4oc?0{mn8=ne?u{x2@A*@x9L61;(af3yC5Ienr9JPBHlt5(LWke7;H+Y&pXc38yBsshQq#jVt6!t+~la>P|*lLFj(aOC_;6acfvwpwVPA9};`r7i6w#SPPK@T!r1g0#V)ifF$i^udx$YKVZh1EEM1%GO68-8aoUWkXi>BdgdkI!9)2fS6eXxJKxP<`r(o%Zx6rY-*_en<6n&ckJ)O-khV%fU|!3@OX6@_h{Nr;fY#TA#_choO3f$ZidCBk47G_sLwSmjN~7Ya)?QI3DQZ-i;cclXOy9$oToxg72JT^n^+LE8ak)(b8LUNh_cF(z@k{ik0}6?1e!n3#?N<u#LL`K0CyD7Y`P{hF6s14~SOa~c%Df($gN}DqbKnVcJxMOHbR5=@#Kf3OhJ+v_S+IO~R}fXulkQ3wdnm8uP@qyN<~GA?+Li@dtShexb5&9~9KI+@^Fiq(yjpD6Y~(tfQIZnQ2!VRxx3@SM#LtR}ZnwE!CxwtH#R3r{Jm2f`>+-#J7flofiOjI@r38;i$U5OZ(l#x<5@J8JbRm3Y%GF+o(u$AJ5zV#Q4VMgn(t<IhAQ*K9I!sz_KW59*3VeY@lFy|k=CeF0E(^joLX_0;^@yPZaUJr+&N{w|Zm$yK4XG`+U@X?6iBhb&f9BLU@URIL!eKCkU^6L-4`j`0P>S*U4gQF=$ZFwOL5ZL%&nC77Sgba@NvYmdLPk_m{k3+A`30dEQ{dW3orWYkAwu=%3)hi@$hu3?>Ez9Z{J~?Yic`aZkkYV~1bR6vnBu`jsvgNxBS^Q<qc2!Wjh+O2{7AC9Qn#C=7-@MFB&N=Dm(=DQpP}72u0}5FOuLbm3@JpVumYB@`sTjUb4uSxjS`eDZlAS9g|A@KM-&i1n^=4>G;LF%6`pHyPPBQgs*arTo1L~OPJNuHR=XpB-t}K8MaqJDH+wuxyDK;t`<M3cS>ts7zi=a0H2')).decode("utf-8"))
_MAX = len(_ACTIONS)
_FINAL_EXEC_STEP = 718
_WEED_REPLAY_STEPS = 8
_PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
_I0 = 10000
# engine 1.32.7 price curve, for revenue-ranked terminal liquidation
_PARAMS = {
    "WHEAT": (25, 400, "sqrt", 0.80, "log", 0.20), "CARROT": (35, 450, "log", 0.20, "sqrt", 0.70),
    "TOMATO": (60, 200, "linear", 0.40, "sqrt", 0.60), "STRAWBERRY": (120, 100, "sqrt", 0.70, "linear", 1.60),
    "MELON": (250, 300, "log", 0.20, "sq", 3.60), "EGG": (50, 332, "linear", 0.40, "log", 0.20),
    "MILK": (160, 122, "sqrt", 0.60, "linear", 1.60), "WOOL": (200, 105, "log", 0.20, "sq", 3.20),
    "FERTILIZER": (100, 200, "linear", 0.40, "linear", 0.40),
}
_WEED_STATE = {0: {}, 1: {}}


def _get(v, k, d=None):
    if isinstance(v, dict):
        return v.get(k, d)
    g = getattr(v, "get", None)
    return g(k, d) if callable(g) else getattr(v, k, d)


def _seat(obs):
    return 1 if int(_get(obs, "player", 0) or 0) == 1 else 0


def _farm(obs, seat):
    fs = list(_get(obs, "farms", []) or [])
    return fs[seat] if seat < len(fs) else {}


def _copy(a):
    a = a if isinstance(a, dict) else {}
    return {"farmer": list(a.get("farmer") or ["PASS"]),
            "hands": [list(h or ["PASS"]) for h in (a.get("hands") or [])],
            "market": [list(o) for o in (a.get("market") or [])]}


def _align(a, obs):
    a = _copy(a)
    exp = len(_get(_farm(obs, _seat(obs)), "hands", []) or [])
    h = list(a.get("hands") or [])
    if len(h) < exp:
        h.extend([["PASS"]] * (exp - len(h)))
    a["hands"] = [list(o or ["PASS"]) for o in h[:exp]]
    return a


def _tile(farm, pos):
    try:
        x, y = int(pos[0]), int(pos[1])
        return (_get(farm, "tiles", []) or [])[y][x]
    except Exception:
        return "LOCKED"


def _trace(step, actor):
    t = _ACTIONS[min(max(int(step), 0), _MAX - 1)] or {}
    if actor == "farmer":
        return list(t.get("farmer") or ["PASS"])
    hs = t.get("hands", []) or []
    return list(hs[actor] if actor < len(hs) else ["PASS"])


def _weed_repair(obs, action, step):
    action = _align(action, obs)
    seat = _seat(obs)
    g = _WEED_STATE[seat]
    if step == 0 or step < int(g.get("last_step", -1)):
        g = {"last_step": step, "active": {}}
        _WEED_STATE[seat] = g
    g["last_step"] = step
    farm = _farm(obs, seat)
    positions = [_get(farm, "farmer"), *list(_get(farm, "hands", []) or [])]
    units = [action.get("farmer", ["PASS"]), *list(action.get("hands") or [])]
    active = g.setdefault("active", {})
    for actor, tx in list(active.items()):
        idx = 0 if actor == "farmer" else int(actor) + 1
        if idx >= len(units):
            active.pop(actor, None)
            continue
        age = step - int(tx["start"])
        if age == 1:
            units[idx] = list(tx["intended"])
        elif 2 <= age <= 1 + _WEED_REPLAY_STEPS:
            units[idx] = _trace(step - 1, actor)
        else:
            active.pop(actor, None)
    for idx, (pos, intended) in enumerate(zip(positions, units)):
        actor = "farmer" if idx == 0 else idx - 1
        if actor in active or not isinstance(intended, list) or not intended:
            continue
        if intended[0] not in ("BUILD_PASTURE", "BUILD_COOP", "PLANT"):
            continue
        t = _tile(farm, pos)
        if not isinstance(t, dict) or t.get("kind") != "WEED":
            continue
        active[actor] = {"start": step, "intended": list(intended)}
        units[idx] = ["DIG"]
    action["farmer"] = units[0] if units else ["PASS"]
    action["hands"] = units[1:]
    return _align(action, obs)


def _shape(f, v, s):
    import math
    v = max(0.0, v)
    return {"linear": v, "sq": v * v, "sqrt": math.sqrt(v), "log": math.log1p(v)}.get(f, v)


def _price(item, inv):
    base, sc, bf, bt, af, at = _PARAMS[item]
    if inv < _I0:
        amp = bt * base / _shape(bf, sc, sc)
        val = base + amp * _shape(bf, _I0 - inv, sc)
    else:
        amp = at * base / _shape(af, sc, sc)
        val = base - amp * _shape(af, inv - _I0, sc)
    return max(1, round(val))


def _terminal_liquidation(obs, action):
    """Step 718: sell every shed product (unsold scores $0), best-revenue first."""
    seat = _seat(obs)
    priv = _get(obs, "private", {}) or {}
    shed = dict(_get(priv, "shed", {}) or {})
    market = _get(obs, "market", {}) or {}
    inv = _get(market, "inventory", {}) or {}
    action = _copy(action)
    already = {}
    for o in action.get("market") or []:
        if len(o) >= 3 and o[0] == "SELL":
            already[o[1]] = already.get(o[1], 0) + max(0, int(o[2] or 0))
    cands = []
    for item in _PRODUCTS:
        qty = max(0, int(shed.get(item, 0) or 0) - already.get(item, 0))
        if qty <= 0:
            continue
        base_inv = int(_get(inv, item, _I0) or _I0)
        rev = sum(_price(item, base_inv + k) for k in range(qty))
        cands.append((rev, item, qty))
    cands.sort(reverse=True)
    for _, item, qty in cands:
        mk = [list(o) for o in (action.get("market") or [])]
        ex = next((o for o in mk if len(o) >= 3 and o[0] == "SELL" and o[1] == item), None)
        if ex is not None:
            ex[2] = max(0, int(ex[2])) + qty
        elif len(mk) < 10:
            mk.append(["SELL", item, qty])
        else:
            continue
        action["market"] = mk[:10]
    return action


def agent(obs, config=None):
    try:
        fb = int(_get(obs, "day", 0) or 0) * 24 + int(_get(obs, "hour", 0) or 0)
        raw = _get(obs, "step", None)
        step = min(max(0, int(raw if raw is not None else fb)), _MAX - 1)
        action = _copy(_ACTIONS[step])
        action = _weed_repair(obs, action, step)
        if step == _FINAL_EXEC_STEP:
            action = _terminal_liquidation(obs, action)
        return _align(action, obs)
    except Exception:
        farm = _farm(obs, _seat(obs))
        return {"farmer": ["PASS"],
                "hands": [["PASS"] for _ in (_get(farm, "hands", []) or [])],
                "market": []}
