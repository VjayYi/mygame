# -*- coding: utf-8 -*-
"""防具 v0.2 贪心 + 穷举 检查脚本（启发式，非战斗模拟）。

规则（v0.2 修订，两张卡都是防御类型）：
- 主防御：护盾按费用分档（0 费 3、1 费 5、2 费 7），可带一个轻量效果，折算约 1 点护盾。
- 副防御：承载主要特效，效果值按费用对齐，使净值 = 3。
- 单卡净值 = 效果值 - 2 * 费用。主防御净值 = 护盾 + 轻量效果 - 2 * 费用。
- 单件 = 防御净值 + 辅助净值。
- 套装加成（按已装套装件数）：2 件 +4，3 件 +8。
- 脚本不给结构性/条件性特效定价，它们的强度需要战斗模拟判断。

元组格式：(名称, 套系, 防御费, 辅助费, 护盾, 辅助效果值)
"""
import itertools
from collections import defaultdict

P = {
 "head": [
  ("铁壁盔","铁壁",1,0,5,3), ("反震盔","反震",0,0,3,3), ("流光目镜","流光",1,1,5,5),
  ("灼炉面罩","灼炉",1,0,5,3), ("猎手目镜","猎手",0,0,3,3),
  ("猎鹰目镜",None,1,0,5,3), ("战术头盔",None,2,1,7,5), ("感应头环",None,1,1,5,5),
  ("伪装面具",None,2,0,7,3), ("过载护目",None,1,0,5,3), ("镜面护额",None,0,0,3,3),
  ("静音护盔",None,1,1,5,5), ("血罩头盔",None,1,1,5,5), ("连线耳机",None,1,1,5,5),
  ("重装头冠",None,2,0,7,3),
 ],
 "torso": [
  ("铁壁甲","铁壁",2,1,7,5), ("反震胸甲","反震",1,1,5,5), ("流光甲","流光",2,0,7,3),
  ("灼炉胸甲","灼炉",1,1,5,5), ("猎手外套","猎手",1,0,5,3),
  ("重装胸甲",None,2,1,7,5), ("轻量胸甲",None,1,0,5,3), ("弹性内甲",None,1,0,5,3),
  ("荆棘胸甲",None,0,0,3,3), ("能量胸甲",None,1,1,5,5), ("猎杀外甲",None,1,1,5,5),
  ("分流甲",None,1,1,5,5), ("回收胸甲",None,1,1,5,5), ("瞬护胸甲",None,2,1,7,5),
  ("残血护甲",None,2,1,7,5),
 ],
 "legs": [
  ("铁壁靴","铁壁",1,0,5,3), ("反震护腕","反震",0,1,3,5), ("流光靴","流光",1,1,5,5),
  ("灼炉护腿","灼炉",1,0,5,3), ("猎手护腿","猎手",1,1,5,5),
  ("疾行护腿",None,1,0,5,3), ("重甲护腿",None,2,1,7,5), ("步进护靴",None,1,0,5,3),
  ("撕裂护腿",None,1,0,5,3), ("弹跳护靴",None,1,1,5,5), ("盾靴",None,1,0,5,3),
  ("静步护腿",None,1,1,5,5), ("战吼护腿",None,1,0,5,3), ("缓冲护靴",None,2,1,7,5),
  ("余力护腿",None,1,1,5,5),
 ],
}

SET_BONUS = {2: 4.0, 3: 8.0}

def card_nets(p):
    _, _, dc, ac, shield, av = p
    return shield - 2 * dc, av - 2 * ac

def piece_score(p):
    d, a = card_nets(p)
    return d + a

def build_score(build):
    total = sum(piece_score(p) for p in build)
    counts = defaultdict(int)
    for p in build:
        if p[1]:
            counts[p[1]] += 1
    for s, n in counts.items():
        if n >= 3:
            total += SET_BONUS[3]
        elif n == 2:
            total += SET_BONUS[2]
    return total

def greedy():
    chosen = []
    for part in ("head", "torso", "legs"):
        best = max(P[part], key=lambda p: build_score(chosen + [p]))
        chosen.append(best)
    return chosen, build_score(chosen)

def exhaustive():
    res = []
    for combo in itertools.product(P["head"], P["torso"], P["legs"]):
        res.append((build_score(list(combo)), combo))
    res.sort(key=lambda x: -x[0])
    return res

def card_audit():
    bad, dset, aset = [], set(), set()
    for part in P:
        for p in P[part]:
            d, a = card_nets(p)
            dset.add(d); aset.add(a)
            if d < 0 or a < 0:
                bad.append((p[0], d, a))
    return bad, dset, aset

if __name__ == "__main__":
    bad, dset, aset = card_audit()
    print("== 单卡净值检查 ==")
    print("  全部 ≥ 0" if not bad else f"  负净值: {bad}")
    print(f"  防御净值取值: {sorted(dset)}    辅助净值取值: {sorted(aset)}")

    g, gs = greedy()
    print("\n== 贪心结果 ==")
    for p in g:
        d, a = card_nets(p)
        print(f"  {p[0]:<6} 套={p[1] or '散件'}  防御净值={d:.1f}  辅助净值={a:.1f}  件分={piece_score(p):.1f}")
    print(f"  总分 {gs:.1f}")

    res = exhaustive()
    scores = [s for s, _ in res]
    n = len(scores)
    print("\n== 穷举 3375 组合 ==")
    print(f"  最高 {scores[0]:.1f}  中位 {scores[n//2]:.1f}  最低 {scores[-1]:.1f}")
    print(f"  最高/中位 = {scores[0]/scores[n//2]:.2f}")
    print("\n  前 10 名:")
    for s, c in res[:10]:
        print(f"    {s:5.1f}  " + " | ".join(p[0] for p in c))

    # 套装分布：前 5% 中各套装件数
    top = res[: max(1, n // 20)]
    set_hits = defaultdict(int)
    for _, c in top:
        sets = [p[1] for p in c if p[1]]
        for s in set(sets):
            set_hits[s] += 1
    print(f"\n== 前 5%（{len(top)} 组）中含各套装的组数 ==")
    for s, cnt in sorted(set_hits.items(), key=lambda x: -x[1]):
        print(f"  {s}: {cnt}")
