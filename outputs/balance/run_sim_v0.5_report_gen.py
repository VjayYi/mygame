"""整局模拟 v0.5 的校准与报告生成。输出写入 run_sim_v0.5_report.txt。"""
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("s", "run_sim_v0.5.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

out = []


def P(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    out.append(line)


P("【一】校准：标准构筑，A10，6 把非晕眩武器平均通关率 → 目标 20%（每次 150 场）")
S = m.calibrate(0.20, m.NON_STUN, "标准", 10, 150, lo=0.25, hi=0.45, iters=7)
P(f"校准结果 S* = {S:.3f}（怪物伤害系数）\n")

RUNS = 400
levels = (0, 2, 4, 6, 8, 9, 10)
P(f"【二】进阶梯度：标准构筑，每格 {RUNS} 场，S*={S:.3f}（通关率）")
P(f"{'武器':<22}" + "".join(f"A{l:<7}" for l in levels))
for w in m.WEAPONS:
    row = f"{w:<22}"
    for l in levels:
        row += f"{m.clear_rate(w, '标准', l, S, RUNS):<8.1%}"
    P(row)

P(f"\n【三】构筑强度对比：A10，每格 {RUNS} 场")
P(f"{'武器':<22}" + "".join(f"{b:<18}" for b in m.BUILDS))
for w in m.WEAPONS:
    row = f"{w:<22}"
    for b in m.BUILDS:
        row += f"{m.clear_rate(w, b, 10, S, RUNS):<18.1%}"
    P(row)

P(f"\n【四】A10 标准构筑死亡位置分布（长刀，{RUNS} 场；键=(层,节点)）")
r, d = m.clear_rate("长刀(双手近)", "标准", 10, S, RUNS, want_deaths=True)
P(f"通关 {r:.1%}；死亡：", dict(sorted(d.items())))

# 机制对照：去掉不可打断 / 去掉狂暴
orig = m.make_enemies


def no_unbreakable(kind, floor, asc, rng, S_):
    es = orig(kind, floor, asc, rng, S_)
    for e in es:
        e["acts"] = [(dm, "n" if k == "u" else k, p) for (dm, k, p) in e["acts"]]
    return es


def no_enrage(kind, floor, asc, rng, S_):
    es = orig(kind, floor, asc, rng, S_)
    for e in es:
        e["er"] = (999, 0)
    return es


def run_variant(fn, label):
    m.make_enemies = fn
    P(f"\n【五】机制对照 - {label}（标准构筑，S*={S:.3f}，每格 {RUNS} 场）")
    P(f"{'武器':<22}{'A5':<10}{'A10':<10}")
    for w in ("长刀(双手近)", "手枪(单手远)", "重斧(单手近,1晕眩)", "纯晕眩(测试件)"):
        P(f"{w:<22}{m.clear_rate(w, '标准', 5, S, RUNS):<10.1%}{m.clear_rate(w, '标准', 10, S, RUNS):<10.1%}")


run_variant(orig, "基线（有不可打断 + 有狂暴）")
run_variant(no_unbreakable, "去掉不可打断（全部动作可晕眩）")
run_variant(no_enrage, "去掉狂暴计时")
m.make_enemies = orig

open("run_sim_v0.5_report.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
