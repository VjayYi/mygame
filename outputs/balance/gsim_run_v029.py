"""贪心模拟主程序 v0.29：估算各档怪物的生命/伤害水平，并检查极端 build 的通关回合。

目标回合（用户 2026-11-18 14:37）：小怪 5～10、精英 8～15、小 Boss 13～20、终极 Boss 分阶段合计约 25；
极端 build 几回合通关也合理。校准取各区间中值：7.5 / 11.5 / 16.5 / 25。
"""
# ruff: noqa: E501
import json
import os
import random
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gsim_data as D  # noqa: E402
import gsim_meme as M  # noqa: E402
from gsim_core import Enemy, Fight, comp_e  # noqa: E402

LAYER_MODS = {1: 3, 2: 4, 3: 5}
LAYER_UPG = {1: 2, 2: 4, 3: 7}
FORM_W = {"改装": 4, "均衡": 4, "强攻": 2}
TARGET_TURNS = {"mob": 7.5, "elite": 11.5, "mini": 16.5, "final": 25.0}
TARGET_LOSS = {"mob": 10.0, "elite": 22.0, "mini": 35.0, "final": 65.0}
KIND_NAME = {"mob": "小怪（2 体）", "elite": "精英", "mini": "小 Boss", "final": "终极 Boss（3 阶段）"}
PATTERN = {
    "mob": [1.0],
    "elite": [0.75, 0.75, 1.5],
    "mini": [0.8, 0.8, 1.5, 0.8, 1.6],
}
ENRAGE = {"mob": 14, "elite": 20, "mini": 26, "final": 40}


def _norm(pat, avg):
    m = sum(pat) / len(pat)
    return [x / m * avg for x in pat]


def encounter(kind, hp, avg):
    """hp: 总生命；avg: 每个敌人每回合平均伤害（终极 Boss 为三阶段平均）。"""
    rate = 0.10
    if kind == "mob":
        return [Enemy(hp / 2, [avg], enrage_turn=ENRAGE[kind], enrage_rate=rate, name="怪甲"),
                Enemy(hp / 2, [avg], enrage_turn=ENRAGE[kind], enrage_rate=rate, name="怪乙")]
    if kind in ("elite", "mini"):
        return [Enemy(hp, _norm(PATTERN[kind], avg), boss=True, enrage_turn=ENRAGE[kind], enrage_rate=rate, name=KIND_NAME[kind])]
    phases = [(hp * 0.30, _norm(PATTERN["mini"], avg * 0.9)), (hp * 0.35, _norm(PATTERN["mini"], avg * 1.0)),
              (hp * 0.35, _norm(PATTERN["mini"], avg * 1.15))]
    first = phases.pop(0)
    return [Enemy(first[0], first[1], boss=True, phases=phases, enrage_turn=ENRAGE[kind], enrage_rate=rate, name="终极 Boss")]


# ---------------------------------------------------------------- build 采样
def score_card(it):
    c = it["cards"][0][0]
    return comp_e(c.v) / max(c.cost, 0.5)


def pick(rng, options, k):
    """随机抽 k 个候选，取评分最高的（k=1 即纯随机）。"""
    cand = [rng.choice(options) for _ in range(k)]
    return max(cand, key=score_card)


def pick_many(rng, options, n, k):
    out = []
    pool = list(options)
    while len(out) < n and pool:
        it = pick(rng, pool, k)
        out.append(it)
        pool = [x for x in pool if x is not it]
    return out


def sample_spec(P, rng, layer, skill=1):
    cat = rng.choice(D.CATS)
    form = rng.choices(list(D.FORM_B), weights=[FORM_W[f] for f in D.FORM_B])[0]
    cap = D.weapon_vol(cat, form) * D.FILL
    ms = D.modules_for(P.mods, cat)
    base = [m for m in ms if m["pool"] == "基地" and not m["locked"]]
    mon = [m for m in ms if m["pool"] == "怪物"]
    locked = [m for m in ms if m["locked"]]
    mods, used = [], 0
    tries = 0
    while len(mods) < LAYER_MODS[layer] and tries < 60:
        tries += 1
        if layer == 1:
            src = base
        elif layer == 2:
            src = mon if rng.random() < 0.35 else base
        else:
            r = rng.random()
            src = locked if r < 0.15 else (mon if r < 0.55 else base)
        src = [m for m in src if m not in mods]
        if not src:
            continue
        m = pick(rng, src, skill)
        if used + m["size"] <= cap:
            mods.append(m)
            used += m["size"]
    return dict(cat=cat, form=form, mods=mods, hands=pick_many(rng, P.hands, 2, skill), feet=pick_many(rng, P.feet, 2, skill),
                brain=pick(rng, P.brains, skill), torso=pick(rng, P.torsos, skill),
                armor=[pick(rng, P.armor[k], skill) for k in ("头", "躯干", "四肢")], pools=P)


def sample_meme(P, rng, layer, name, skill=1):
    items = M.meme_items(name) + list(P.generic)
    items += pick_many(rng, P.hands, 2, skill) + pick_many(rng, P.feet, 2, skill)
    brain, torso = pick(rng, P.brains, skill), pick(rng, P.torsos, skill)
    items += [brain, torso] + [pick(rng, P.armor[k], skill) for k in ("头", "躯干", "四肢")]
    passive = {"shield": 0.0, "draw": 0.0, "energy": 0.0, "turnatk": 0.0}
    for it in (brain, torso):
        for key, val in it["passive"].items():
            passive[key] += val
    # 升级：随机把部分非梗牌换成升级版
    flat = []
    for it in items:
        flat.extend((c, u, it["part"]) for c, u in it["cards"])
    idx = [i for i, (_c, _u, part) in enumerate(flat) if part != "梗"]
    chosen = set(rng.sample(idx, min(LAYER_UPG[layer], len(idx))))
    cards = [u if i in chosen else c for i, (c, u, _p) in enumerate(flat)]
    return cards, passive


def make_deck(P, rng, layer, skill=1):
    spec = sample_spec(P, rng, layer, skill)
    cards, passive = D.assemble(spec, LAYER_UPG[layer], rng)
    return cards, passive, spec


# ---------------------------------------------------------------- 战斗评估
def fight_once(deck, kind, hp, avg, seed):
    cards, passive = deck
    f = Fight(cards, encounter(kind, hp, avg), random.Random(seed), passive)
    turns, win = f.run()
    return turns, win, f.hp_lost


def evaluate(decks, kind, hp, avg, seed0=0, reps=1):
    ts, wins, loss = [], 0, []
    for i, d in enumerate(decks):
        for r in range(reps):
            t, w, hl = fight_once(d, kind, hp, avg, seed0 + i * 7 + r)
            ts.append(t)
            wins += 1 if w else 0
            loss.append(min(hl, 100.0))
    return statistics.mean(ts), wins / len(ts), statistics.mean(loss), ts


def solve_hp(decks, kind, avg, target, seed0=0):
    lo, hi = 10.0, 4000.0
    for _ in range(14):
        mid = (lo + hi) / 2
        t = evaluate(decks, kind, mid, avg, seed0)[0]
        if t < target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def calibrate(decks, kind, grid, seed0=0):
    rows = []
    for avg in grid:
        hp = solve_hp(decks, kind, avg, TARGET_TURNS[kind], seed0)
        t, win, loss, ts = evaluate(decks, kind, hp, avg, seed0 + 500, reps=2)
        rows.append(dict(avg=avg, hp=hp, turns=t, win=win, loss=loss,
                         p10=sorted(ts)[len(ts) // 10], p90=sorted(ts)[len(ts) * 9 // 10]))
    return rows


# ---------------------------------------------------------------- 极端 build（贪心）
def ref_score(P, spec, rng_seed=7, n=10):
    cards, passive = D.assemble(spec, 7, random.Random(rng_seed))
    ts, hl = [], []
    for i in range(n):
        f = Fight(cards, [Enemy(220, [14], boss=True)], random.Random(i), passive)
        t, w = f.run(40)
        ts.append(t if w else 40)
        hl.append(f.hp_lost)
    return statistics.mean(ts) + 0.02 * statistics.mean(hl)


def greedy_extreme(P, top_weapons=3, log=print):
    rng = random.Random(11)
    base_spec = dict(hands=rng.sample(P.hands, 2), feet=rng.sample(P.feet, 2), brain=P.brains[0], torso=P.torsos[0],
                     armor=[rng.choice(P.armor[k]) for k in ("头", "躯干", "四肢")], pools=P, mods=[])
    ranking = []
    for cat in D.CATS:
        for form in D.FORM_B:
            spec = dict(base_spec, cat=cat, form=form)
            ranking.append((ref_score(P, spec), cat, form))
    ranking.sort()
    results = []
    for _s, cat, form in ranking[:top_weapons]:
        spec = dict(base_spec, cat=cat, form=form, mods=[])
        cap = D.weapon_vol(cat, form)
        cand = [m for m in D.modules_for(P.mods, cat)]
        used = 0
        while True:
            best, best_s = None, ref_score(P, spec) if spec["mods"] else 1e9
            for m in cand:
                if m in spec["mods"] or used + m["size"] > cap:
                    continue
                s = ref_score(P, dict(spec, mods=spec["mods"] + [m]))
                if s < best_s - 1e-9:
                    best, best_s = m, s
            if best is None:
                break
            spec["mods"] = spec["mods"] + [best]
            used += best["size"]
        for _round in range(2):
            for slot, opts, many in (("hands", P.hands, 2), ("feet", P.feet, 2), ("brain", P.brains, 1), ("torso", P.torsos, 1)):
                if many == 2:
                    for j in range(2):
                        cur = list(spec[slot])
                        sc = [(ref_score(P, dict(spec, **{slot: cur[:j] + [o] + cur[j + 1:]})), k) for k, o in enumerate(opts) if o not in cur or o is cur[j]]
                        k = min(sc)[1]
                        cur[j] = opts[k]
                        spec[slot] = cur
                else:
                    sc = [(ref_score(P, dict(spec, **{slot: o})), k) for k, o in enumerate(opts)]
                    spec[slot] = opts[min(sc)[1]]
            arm = list(spec["armor"])
            for j, part in enumerate(("头", "躯干", "四肢")):
                sc = [(ref_score(P, dict(spec, armor=arm[:j] + [o] + arm[j + 1:])), k) for k, o in enumerate(P.armor[part])]
                arm[j] = P.armor[part][min(sc)[1]]
            spec["armor"] = arm
        results.append((ref_score(P, spec), spec))
        log(f"  极端 build：{cat}·{form}，模块 {len(spec['mods'])} 个，参考战 {results[-1][0]:.2f}")
    results.sort(key=lambda x: x[0])
    return results


def build_text(spec):
    f = [f"{spec['cat']}·{spec['form']}"]
    f.append("模块：" + "、".join(m["name"] for m in spec["mods"]))
    f.append("手：" + "、".join(i["name"] for i in spec["hands"]) + "；脚：" + "、".join(i["name"] for i in spec["feet"]))
    f.append(f"脑：{spec['brain']['name']}；躯干：{spec['torso']['name']}；防具：" + "、".join(i["name"] for i in spec["armor"]))
    return "\n    ".join(f)


def stats_line(decks, label):
    """衡量输出：对 HP 极大的靶子 8 回合内的每回合平均伤害与护盾。"""
    dmgs = []
    for i, d in enumerate(decks):
        cards, passive = d
        f = Fight(cards, [Enemy(10000, [12], boss=True)], random.Random(i), passive)
        f.run(8)
        dmgs.append((10000 - f.enemies[0].hp) / 8.0)
    return statistics.mean(dmgs), statistics.median(dmgs), min(dmgs), max(dmgs)


def main():
    t0 = time.time()
    out = []

    def log(*a):
        line = " ".join(str(x) for x in a)
        print(line, flush=True)
        out.append(line)

    P = D.Pools()
    N = 80
    results = {}
    log("【贪心模拟 v0.29】玩家 100 生命、3 能源、抽 5；怪物意图公开；贪心出牌。")
    log(f"卡池：模块 {len(P.mods)}、手 {len(P.hands)}、脚 {len(P.feet)}、大脑 {len(P.brains)}、躯干 {len(P.torsos)}、防具 {sum(len(v) for v in P.armor.values())}")
    decks = {}
    for layer in (1, 2, 3):
        rng = random.Random(100 + layer)
        decks[layer] = [make_deck(P, rng, layer)[:2] for _ in range(N)]
        sk = random.Random(200 + layer)
        decks[(layer, "熟练")] = [make_deck(P, sk, layer, 3)[:2] for _ in range(N)]
        a = stats_line(decks[layer], "")
        b = stats_line(decks[(layer, "熟练")], "")
        log(f"层{layer} 随机 build 每回合输出（对 12 伤/回合的靶，8 回合平均）：均值 {a[0]:.1f}，中位 {a[1]:.1f}，范围 {a[2]:.1f}～{a[3]:.1f}；熟练(三选一择优) 均值 {b[0]:.1f}")
        results[f"dpt_{layer}"] = [a[0], b[0]]
    grids = {"mob": [4, 6, 8, 10, 12, 14], "elite": [8, 11, 14, 17, 20, 24], "mini": [10, 14, 18, 22, 26, 30], "final": [12, 16, 20, 24, 28, 34]}
    layers_of = {"mob": (1, 2, 3), "elite": (1, 2, 3), "mini": (1, 2, 3), "final": (3,)}
    calib = {}
    for kind in ("mob", "elite", "mini", "final"):
        for layer in layers_of[kind]:
            rows = calibrate(decks[layer], kind, grids[kind], seed0=1000 * layer)
            calib[(kind, layer)] = rows
            log(f"\n== {KIND_NAME[kind]} · 层{layer}（目标均值 {TARGET_TURNS[kind]} 回合，目标损失 ≈{TARGET_LOSS[kind]:.0f} 生命）==")
            log("  每回合伤害  对应生命(总)  实际回合  P10~P90  胜率  平均损失")
            for r in rows:
                log(f"  {r['avg']:>6.0f}      {r['hp']:>8.0f}     {r['turns']:>5.1f}   {r['p10']:>2}~{r['p90']:<2}   {r['win']:>4.0%}  {r['loss']:>6.1f}")
            results[f"{kind}_{layer}"] = rows
    rec = {}
    for key, rows in calib.items():
        rec[key] = min(rows, key=lambda r: abs(r["loss"] - TARGET_LOSS[key[0]]))
        results[f"rec_{key[0]}_{key[1]}"] = rec[key]
    log("\n== 推荐档位（按目标损失挑选）==")
    for key, r in rec.items():
        log(f"  {KIND_NAME[key[0]]} 层{key[1]}: 生命 {r['hp']:.0f}，每回合伤害 {r['avg']}，回合 {r['turns']:.1f}（P10~P90 {r['p10']}~{r['p90']}），胜率 {r['win']:.0%}，损失 {r['loss']:.1f}")
    log("\n== 极端 build（贪心优化）==")
    ext = greedy_extreme(P, 3, log)
    for _sc, spec in ext:
        log("  " + build_text(spec))
    results["extreme_specs"] = [build_text(s) for _sc, s in ext]
    best = ext[0][1]
    ex_decks = [D.assemble(best, 7, random.Random(i)) for i in range(40)]
    results["extreme_dpt"] = stats_line(ex_decks, "")[0]
    log(f"极端 build 每回合输出 {results['extreme_dpt']:.1f}")
    log("\n== 各类 build 打推荐档位怪物的回合数（均值 / 最小～最大 / 胜率 / 损失）==")
    meme_decks = {}
    for name in M.MEME:
        rng = random.Random(300)
        meme_decks[name] = [sample_meme(P, rng, 3, name) for _ in range(N)]
    groups = {"层3·随机": decks[3], "层3·熟练": decks[(3, "熟练")], "极端": ex_decks}
    for name, md in meme_decks.items():
        groups["梗·" + name] = md
    table = {}
    for kind in ("mob", "elite", "mini", "final"):
        r = rec[(kind, 3)]
        log(f"  [{KIND_NAME[kind]}·层3：生命 {r['hp']:.0f}，伤害 {r['avg']}]")
        for gname, gd in groups.items():
            t, win, loss, ts = evaluate(gd, kind, r["hp"], r["avg"], 5000, reps=2)
            table[f"{kind}|{gname}"] = [t, min(ts), max(ts), win, loss]
            log(f"    {gname:<14} {t:>5.1f}  {min(ts):>2}～{max(ts):<2}  {win:>4.0%}  {loss:>5.1f}")
    for gname, gd in (("层1·随机", decks[1]), ("层2·随机", decks[2])):
        for kind in ("mob", "elite", "mini"):
            r = rec[(kind, {"层1·随机": 1, "层2·随机": 2}[gname])]
            t, win, loss, ts = evaluate(gd, kind, r["hp"], r["avg"], 6000, reps=2)
            table[f"{kind}|{gname}"] = [t, min(ts), max(ts), win, loss]
    results["table"] = table
    # 极端 build 打层 1、层 2 的怪
    log("\n== 极端 build 打其他层怪物 ==")
    for kind in ("mob", "elite", "mini"):
        for layer in (1, 2):
            r = rec[(kind, layer)]
            t, win, loss, ts = evaluate(ex_decks, kind, r["hp"], r["avg"], 7000, reps=2)
            log(f"  {KIND_NAME[kind]} 层{layer}: {t:.1f} 回合（{min(ts)}～{max(ts)}），胜率 {win:.0%}")
    results["time"] = time.time() - t0
    with open(os.path.join(HERE, "monster_greedy_sim_v0.29_result.json"), "w", encoding="utf-8") as fh:
        json.dump({k: v for k, v in results.items()}, fh, ensure_ascii=False, indent=1, default=str)
    with open(os.path.join(HERE, "monster_greedy_sim_v0.29_report.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    log(f"\n耗时 {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
