"""v0.30 校准：随机 build 塞满模块、起始 80 生命；怪物伤害按目标胜率二分，生命按目标回合二分。

目标（用户 2026-11-18 16:33）：塞满的普通随机 build 打精英胜率≈80%、小 Boss≈50%、终极 Boss≈20%；
回合区间沿用 小怪 5~10 / 精英 8~15 / 小 Boss 13~20 / 终极 ~25（取胜局的平均回合）。
"""
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

START_HP = float(os.environ.get("START_HP", 80))
N_DECKS = 90
TARGET_WIN = {"mob": 0.97, "elite": 0.80, "mini": 0.50, "final": 0.20}
TARGET_TURN = {"mob": 7.5, "elite": 11.5, "mini": 16.5, "final": 25.0}


def run_one(deck, kind, hp, avg, seed):
    f = Fight(deck[0], R.encounter(kind, hp, avg), random.Random(seed), deck[1])
    f.hp = START_HP
    t, w = f.run()
    return t, w, min(f.hp_lost, START_HP)


def ev(decks, kind, hp, avg, reps=3, seed0=0):
    ts, wins, loss = [], 0, []
    for i, d in enumerate(decks):
        for r in range(reps):
            t, w, hl = run_one(d, kind, hp, avg, seed0 + i * 13 + r)
            wins += 1 if w else 0
            loss.append(hl)
            if w:
                ts.append(t)
    n = len(decks) * reps
    return (statistics.mean(ts) if ts else 0.0), wins / n, statistics.mean(loss), ts


def solve_hp(decks, kind, avg, seed0):
    lo, hi = 20.0, 3000.0
    for _ in range(12):
        mid = (lo + hi) / 2
        t, w, _l, _ts = ev(decks, kind, mid, avg, 1, seed0)
        if w < 0.05 or t < TARGET_TURN[kind]:
            lo = mid if w >= 0.05 else lo
            if w < 0.05:
                hi = mid
        else:
            hi = mid
    return (lo + hi) / 2


def calibrate(decks, kind, seed0):
    lo, hi = 2.0, 60.0
    best = None
    for _ in range(9):
        avg = (lo + hi) / 2
        hp = solve_hp(decks, kind, avg, seed0)
        t, w, loss, ts = ev(decks, kind, hp, avg, 3, seed0 + 777)
        best = dict(avg=avg, hp=hp, turns=t, win=w, loss=loss,
                    p10=sorted(ts)[len(ts) // 10] if ts else 0, p90=sorted(ts)[len(ts) * 9 // 10] if ts else 0)
        if w > TARGET_WIN[kind]:
            lo = avg
        else:
            hi = avg
    return best


def main():
    global START_HP
    cp = D.Pools()
    out = []

    def log(s):
        print(s, flush=True)
        out.append(s)

    rng = random.Random(4242)
    full = [R.make_deck(cp, rng, 3, 1, full=True)[:2] for _ in range(N_DECKS)]
    rng2 = random.Random(4242)
    spec_fill = []
    for _ in range(N_DECKS):
        sp = R.sample_spec(cp, rng2, 3, 1, full=True)
        spec_fill.append(sum(m["size"] for m in sp["mods"]) / (D.weapon_vol(sp["cat"], sp["form"])))
    log(f"【v0.30 校准】起始生命 {START_HP:.0f}/100；随机 build 塞满：平均填充 {statistics.mean(spec_fill):.0%}，模块 {statistics.mean(len(R.sample_spec(cp, random.Random(i), 3, 1, full=True)['mods']) for i in range(60)):.1f} 个；强化 7 张。")
    res = {}
    for kind in ("mob", "elite", "mini", "final"):
        r = calibrate(full, kind, 100)
        res[kind] = r
        log(f"{R.KIND_NAME[kind]}：每回合伤害 {r['avg']:.1f}，总生命 {r['hp']:.0f}，胜率 {r['win']:.0%}（目标 {TARGET_WIN[kind]:.0%}），胜局回合 {r['turns']:.1f}（P10~P90 {r['p10']}~{r['p90']}，目标 {TARGET_TURN[kind]}），平均损失 {r['loss']:.0f}/{START_HP:.0f}")
    log("\n== 满血 100 生命验证（同样的怪物）==")
    START_HP = 100.0
    for kind, r in res.items():
        t, w, loss, _ts = ev(full, kind, r["hp"], r["avg"], 3, 5000)
        log(f"{R.KIND_NAME[kind]}：胜率 {w:.0%}，胜局回合 {t:.1f}，损失 {loss:.0f}")
    START_HP = 80.0
    log("\n== 熟练 build（每位三选一）与 80%容积随机 build，同样的怪物（80 生命）==")
    rng3 = random.Random(4243)
    skill = [R.make_deck(cp, rng3, 3, 3, full=True)[:2] for _ in range(N_DECKS)]
    rng4 = random.Random(4244)
    loose = [R.make_deck(cp, rng4, 3, 1, full=False)[:2] for _ in range(N_DECKS)]
    for kind, r in res.items():
        a = ev(skill, kind, r["hp"], r["avg"], 3, 6000)
        b = ev(loose, kind, r["hp"], r["avg"], 3, 7000)
        log(f"{R.KIND_NAME[kind]}：熟练 胜率 {a[1]:.0%}（回合 {a[0]:.1f}）｜80%容积 胜率 {b[1]:.0%}（回合 {b[0]:.1f}）")
    json.dump(res, open(os.path.join(HERE, "monster_calib_v0.30_result.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(os.path.join(HERE, "monster_calib_v0.30_report.txt"), "w", encoding="utf-8").write("\n".join(out) + "\n")


if __name__ == "__main__":
    main()
