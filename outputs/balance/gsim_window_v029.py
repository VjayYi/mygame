"""怪物生命窗口：把推荐伤害固定，求平均回合落在用户给定区间下沿/中值/上沿时对应的总生命。"""
# ruff: noqa: E501
import json
import random

import gsim_data as D
import gsim_run_v029 as R

WINDOW = {"mob": (5.0, 7.5, 10.0), "elite": (8.0, 11.5, 15.0), "mini": (13.0, 16.5, 20.0), "final": (20.0, 25.0, 30.0)}
REC_AVG = {"mob": 6, "elite": 11, "mini": 10, "final": 12}


def main():
    P = D.Pools()
    out = []

    def log(s):
        print(s)
        out.append(s)

    res = {}
    decks = {}
    for layer in (1, 2, 3):
        rng = random.Random(100 + layer)
        decks[layer] = [R.make_deck(P, rng, layer)[:2] for _ in range(80)]
    log("== 生命窗口（总生命；平均回合落在下沿/中值/上沿）==")
    for kind in ("mob", "elite", "mini", "final"):
        for layer in ((1, 2, 3) if kind != "final" else (3,)):
            hps = [R.solve_hp(decks[layer], kind, REC_AVG[kind], t, 1000 * layer) for t in WINDOW[kind]]
            res[f"{kind}_{layer}"] = hps
            log(f"  {R.KIND_NAME[kind]} 层{layer}（伤害 {REC_AVG[kind]}）：{WINDOW[kind][0]:g} 回合 → {hps[0]:.0f}；{WINDOW[kind][1]:g} → {hps[1]:.0f}；{WINDOW[kind][2]:g} → {hps[2]:.0f}")
    log("\n== 终极 Boss 伤害细分（层3，生命按 25 回合）==")
    for avg in (12, 13, 14, 15, 16):
        hp = R.solve_hp(decks[3], "final", avg, 25.0, 3000)
        t, win, loss, ts = R.evaluate(decks[3], "final", hp, avg, 3500, reps=3)
        log(f"  伤害 {avg}：生命 {hp:.0f}，回合 {t:.1f}（{sorted(ts)[len(ts) // 10]}～{sorted(ts)[len(ts) * 9 // 10]}），胜率 {win:.0%}，损失 {loss:.0f}")
        res[f"final_fine_{avg}"] = [hp, t, win, loss]
    log("\n== 单场损失随怪物伤害的变化（层3，生命按各档 25/50/75 目标回合标定，仅列胜率≥80%）==")
    for kind, grid in (("mob", (4, 6, 8, 10, 12)), ("elite", (8, 11, 14, 17, 20)), ("mini", (8, 10, 12, 14, 16))):
        for avg in grid:
            hp = R.solve_hp(decks[3], kind, avg, R.TARGET_TURNS[kind], 3000)
            t, win, loss, _ts = R.evaluate(decks[3], kind, hp, avg, 3500, reps=2)
            if win >= 0.8:
                log(f"  {R.KIND_NAME[kind]} 伤害 {avg}：生命 {hp:.0f}，回合 {t:.1f}，胜率 {win:.0%}，损失 {loss:.0f}")
    with open("monster_greedy_sim_v0.29_window.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    with open("monster_greedy_sim_v0.29_window.txt", "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
