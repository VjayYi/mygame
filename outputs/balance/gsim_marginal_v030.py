"""模块边际贡献：单个模块加入随机满 build 后，对小 Boss（80 生命起手，校准伤害）胜率与回合的变化（配对种子）。"""
# ruff: noqa: E501
import json
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gsim_data as D  # noqa: E402
import gsim_run_v029 as R  # noqa: E402
from gsim_core import Fight  # noqa: E402

HP, AVG = 230, 18.9
N, REPS = 140, 3


def add_mod(deck, mod):
    cards, passive = deck
    cs = [c.clone() for c in cards]
    for c in cs:
        if c.kind == "ult":
            for k, v in mod["ult_v"].items():
                if k in c.v:
                    c.v[k] += v
    cs.append(mod["cards"][0][0].clone())
    return cs, passive


def fight(cards, passive, seed):
    f = Fight(cards, R.encounter("mini", HP, AVG), random.Random(seed), passive)
    f.hp = 80.0
    t, w = f.run()
    return t, w


def main():
    cp = D.Pools()
    rng = random.Random(777)
    decks = [R.make_deck(cp, rng, 3, 1, full=True)[:2] for _ in range(N)]
    base = {}
    for i, d in enumerate(decks):
        for r in range(REPS):
            base[(i, r)] = fight(d[0], d[1], 3000 + i * 11 + r)
    bw = statistics.mean(1.0 if v[1] else 0.0 for v in base.values())
    print(f"基线：小 Boss 胜率 {bw:.1%}")
    rows = []
    for m in cp.mods:
        dw, dt = [], []
        for i, d in enumerate(decks):
            cards, passive = add_mod(d, m)
            for r in range(REPS):
                t, w = fight(cards, passive, 3000 + i * 11 + r)
                b = base[(i, r)]
                dw.append((1.0 if w else 0.0) - (1.0 if b[1] else 0.0))
                dt.append(t - b[0])
        c = m["cards"][0][0]
        rows.append(dict(name=m["name"], size=m["size"], cost=c.cost, dwin=statistics.mean(dw), dturn=statistics.mean(dt),
                         locked=m["locked"], pool=m["pool"], text=c.text[:40]))
    json.dump(rows, open(os.path.join(HERE, "module_marginal_v0.30.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("按格数：平均胜率变化（百分点）/ 每格 / 平均回合变化 / 数量")
    for s in (2, 3, 4, 5, 6):
        rs = [r for r in rows if r["size"] == s]
        print(f"  {s}格 n={len(rs):3d}  胜率 {100 * statistics.mean(r['dwin'] for r in rs):+.2f}  每格 {100 * statistics.mean(r['dwin'] for r in rs) / s:+.2f}  回合 {statistics.mean(r['dturn'] for r in rs):+.2f}")
    print("按格数×费用：")
    for s in (2, 3, 4, 5, 6):
        for c in (0, 1, 2, 3):
            rs = [r for r in rows if r["size"] == s and r["cost"] == c]
            if rs:
                print(f"  {s}格 {c}费 n={len(rs):3d}  胜率 {100 * statistics.mean(r['dwin'] for r in rs):+.2f}  回合 {statistics.mean(r['dturn'] for r in rs):+.2f}")
    top = sorted(rows, key=lambda r: -r["dwin"])[:15]
    print("边际最强 15：")
    for r in top:
        print(f"  {r['name']:8} {r['size']}格 {r['cost']}费 胜率 {100 * r['dwin']:+.1f} 回合 {r['dturn']:+.2f}  {r['text']}")
    two = sorted([r for r in rows if r["size"] == 2], key=lambda r: -r["dwin"])
    print("2 格最强 12：")
    for r in two[:12]:
        print(f"  {r['name']:8} {r['cost']}费 胜率 {100 * r['dwin']:+.1f} 回合 {r['dturn']:+.2f}  {r['text']}")


if __name__ == "__main__":
    main()
