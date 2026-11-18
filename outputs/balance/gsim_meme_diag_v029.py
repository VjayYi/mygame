"""梗武器诊断：每张牌的出牌率；带 3 个模块（无终极）后的回合数。"""
# ruff: noqa: E501
import random
import statistics
import sys
from collections import Counter

import gsim_data as D
import gsim_meme as M
import gsim_run_v029 as R
from gsim_core import Fight

ELITE = (173, 11)
FINAL = (332, 12)


def run_group(decks, kind, hp, avg, count=None, seeds=60):
    plays = Counter()
    turns = []
    for i, (cards, passive) in enumerate(decks[:seeds]):
        f = Fight(cards, R.encounter(kind, hp, avg), random.Random(900 + i), passive)
        orig = f.play

        def logged(c, f=f, orig=orig):
            plays[c.name] += 1
            orig(c)

        f.play = logged
        t, _w = f.run()
        turns.append(t)
    return statistics.mean(turns), plays, len(decks[:seeds])


def main():
    P = D.Pools()
    out = []

    def log(s):
        print(s)
        out.append(s)

    for name, fn in M.MEME.items():
        rng = random.Random(300)
        decks = [R.sample_meme(P, rng, 3, name) for _ in range(80)]
        t, plays, n = run_group(decks, "elite", *ELITE)
        names = [c.name for c in fn()]
        log(f"[{name}] 打精英 {t:.1f} 回合；每场平均出牌次数：" + "，".join(f"{nm} {plays[nm] / n:.1f}" for nm in names))
    log("")
    for name in M.MEME:
        rng = random.Random(400)
        decks = []
        for _ in range(80):
            cat = rng.choice(D.CATS)
            ms = [m for m in D.modules_for(P.mods, cat) if not m["locked"]]
            mods = rng.sample(ms, 3)
            items = M.meme_items(name) + list(P.generic) + mods
            items += rng.sample(P.hands, 2) + rng.sample(P.feet, 2)
            brain, torso = rng.choice(P.brains), rng.choice(P.torsos)
            items += [brain, torso] + [rng.choice(P.armor[k]) for k in ("头", "躯干", "四肢")]
            cards = []
            for it in items:
                cards.extend(c for c, _u in it["cards"])
            passive = {"shield": 0.0, "draw": 0.0, "energy": 0.0, "turnatk": 0.0}
            for it in (brain, torso):
                for key, val in it["passive"].items():
                    passive[key] += val
            decks.append((cards, passive))
        t, _p, _n = run_group(decks, "elite", *ELITE)
        t2, _p2, _n2 = run_group(decks, "final", *FINAL)
        log(f"[{name}+3 模块] 打精英 {t:.1f} 回合，打终极 Boss {t2:.1f} 回合")
    with open("monster_greedy_sim_v0.29_meme_diag.txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")


if __name__ == "__main__":
    sys.exit(main())
