# -*- coding: utf-8 -*-
import json, os, random, math, sys
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import power_supply_v027 as PS

rows = json.load(open(os.path.join(os.path.dirname(__file__), "module_audit_v0.26.json"), encoding="utf-8"))
MELEE = ["刀", "剑", "爪", "斧", "拳套"]
CATS = MELEE + ["步枪", "炮筒", "手枪", "弓"]
VOL = {"改装": 26, "均衡": 18, "强攻": 12}
VOL_FIX = {"刀":0,"剑":1,"爪":-1,"斧":-2,"拳套":-1,"步枪":0,"炮筒":-2,"手枪":1,"弓":1}
FILL = 0.8  # 填充率


def pool_for(cat):
    major = "近战" if cat in MELEE else "远程"
    return [r for r in rows if r["major"] == major and r["limit"] in ("—", cat)]


def build(cat, form, rng, mode="random"):
    A, D = PS.FORM_BASE[form]
    if cat == "爪": A += 1
    cap = (VOL[form] + VOL_FIX[cat]) * FILL
    pool = pool_for(cat)[:]
    if mode == "attack":      # 玩家刻意堆攻击侧
        pool.sort(key=lambda r: (-(r["A"] - r["D"]), rng.random()))
    elif mode == "defense":
        pool.sort(key=lambda r: (-(r["D"] - r["A"]), rng.random()))
    else:
        rng.shuffle(pool)
    used, mods = 0, []
    for r in pool:
        if len(mods) >= 6: break
        if used + r["size"] <= cap:
            mods.append(r); used += r["size"]; A += r["A"]; D += r["D"]
    return mods, A, D


def stats(mode, n=1500, seed=7):
    rng = random.Random(seed)
    out = {}
    for form in VOL:
        thr, nm, As, Ds = [], [], [], []
        for _ in range(n):
            cat = rng.choice(CATS)
            mods, A, D = build(cat, form, rng, mode)
            side, t = PS.threshold(A, D)
            thr.append(t); nm.append(len(mods)); As.append(A); Ds.append(D)
        c = Counter(thr)
        tot = len(thr)
        out[form] = dict(mods=sum(nm) / tot, A=sum(As) / tot, D=sum(Ds) / tot,
                         avg=sum(thr) / tot,
                         p50=sum(1 for x in thr if x <= 0.5) / tot,
                         p60_70=sum(1 for x in thr if 0.6 <= x <= 0.7) / tot,
                         p80=sum(1 for x in thr if x == 0.8) / tot,
                         p90p=sum(1 for x in thr if x >= 0.9) / tot)
    return out


if __name__ == "__main__":
    for mode in ("random", "attack", "defense"):
        print("==", mode)
        for f, v in stats(mode).items():
            print(f, {k: round(x, 2) for k, x in v.items()})
    # AD 分布
    print(Counter((r["A"], r["D"]) for r in rows).most_common(12))
    print(Counter(r["ad_src"] for r in rows))
