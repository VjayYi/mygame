"""自动搭难度阶梯：从小修正菜单里逐级累加，直到自然通关率将低于目标；
剩余差距用怪物伤害微调补（微调倍率不小于 1，保证阶梯不靠"削弱怪物"凑出来）。
输出 run_sim_v0.6d_report.txt。"""
import importlib.util

spec = importlib.util.spec_from_file_location("s", "run_sim_v0.6.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

TARGET = {1: 0.92, 2: 0.80, 3: 0.72, 4: 0.64, 5: 0.56, 6: 0.48, 7: 0.40, 8: 0.33, 9: 0.26, 10: 0.20}
W = m.NON_STUN
S0 = 0.505
out = []


def P(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    out.append(line)


# 修正菜单：由轻到重，累计应用（后一步覆盖前一步同旋钮的取值）
MENU = [
    ("每层 +1 精英", {"elite_swap": True}),
    ("双怪概率 25%→35%", {"pair": 0.35}),
    ("休息回复 -10%", {"rest": 0.90}),
    ("战后回复 -5%", {"after": 0.95}),
    ("掉落三选一→二选一", {"pick": 2}),
    ("商店只买 1 个", {"shop": 1}),
    ("怪物生命 +2%", {"hp": 1.02}),
    ("精英 +1 可打断小动作(0.15倍)", {"elite_extra_n": True, "xn": 0.15}),
    ("双怪概率 →50%", {"pair": 0.50}),
    ("休息回复 -20%", {"rest": 0.80}),
    ("战后回复 -10%", {"after": 0.90}),
    ("怪物生命 +4%", {"hp": 1.04}),
    ("+1 不可打断小动作(0.10倍)", {"extra_u": True, "xu": 0.10}),
    ("精英小动作增强到 0.25 倍", {"xn": 0.25}),
    ("休息回复 -30%", {"rest": 0.70}),
    ("战后回复 -15%", {"after": 0.85}),
    ("怪物生命 +6%", {"hp": 1.06}),
    ("不可打断小动作增强到 0.20 倍", {"xu": 0.20}),
    ("战后回复 -20%", {"after": 0.80}),
    ("怪物生命 +8%", {"hp": 1.08}),
    ("精英小动作增强到 0.35 倍", {"xn": 0.35}),
    ("战后回复 -25%", {"after": 0.75}),
    ("怪物生命 +10%", {"hp": 1.10}),
]


def knobs_upto(k):
    d = {}
    for _, upd in MENU[:k]:
        d.update(upd)
    return d


def natural(level, knobs, runs=250):
    m.LADDER_KNOBS[level] = knobs
    m.DMG_X.pop(level, None)
    return m.mean_rate(W, "标准", level, S0, runs)


P("【自动搭阶梯】每级累加菜单修正，直到自然通关率将低于目标 1.5 个百分点以上；其余用伤害微调补")
k = 0
chosen = {1: 0}
for L in range(2, 11):
    while k < len(MENU):
        r = natural(L, knobs_upto(k + 1))
        if r >= TARGET[L] - 0.015:
            k += 1
        else:
            break
    chosen[L] = k
    knobs = knobs_upto(k)
    r = natural(L, knobs)
    # 微调：只允许 >= 1.0
    if r > TARGET[L] + 0.015:
        lo, hi = 1.0, 1.5
        for _ in range(7):
            mid = (lo + hi) / 2
            m.DMG_X[L] = mid
            rr = m.mean_rate(W, "标准", L, S0, 250)
            if rr > TARGET[L]:
                lo = mid
            else:
                hi = mid
        m.DMG_X[L] = (lo + hi) / 2
    P(f"  级 {L}: 菜单到第 {k} 项，自然 {r:.0%}，伤害倍率 {m.DMG_X.get(L, 1.0):.3f}")

P("\n【阶梯定稿】")
prev = set()
for L in range(1, 11):
    cur = set(i for i in range(chosen[L]))
    new = [MENU[i][0] for i in sorted(cur - prev)]
    prev = cur
    dm = m.DMG_X.get(L, 1.0)
    P(f"  级 {L}: " + ("基础难度" if L == 1 else "；".join(new) if new else "（仅伤害微调）") +
      (f"；怪物伤害 {(dm - 1) * 100:+.0f}%" if dm > 1.0005 else ""))

RUNS = 500
P(f"\n【验证】成熟构筑（标准，模块×1.0）每格 6 武器 × {RUNS} 场")
P(f"{'':<8}" + "".join(f"L{L:<6}" for L in range(1, 11)))
row = f"{'实际':<8}"
for L in range(1, 11):
    row += f"{m.mean_rate(W, '标准', L, S0, RUNS):<7.0%}"
P(row)
P(f"{'目标':<8}" + "".join(f"{TARGET[L]:<7.0%}" for L in range(1, 11)))

P(f"\n【成熟构筑各武器】{RUNS} 场")
P(f"{'武器':<22}{'L1':<8}{'L5':<8}{'L10':<8}")
for w in m.WEAPONS:
    P(f"{w:<22}" + "".join(f"{m.clear_rate(w, '标准', L, S0, RUNS):<8.1%}" for L in (1, 5, 10)))

P("\n【死亡位置】长刀")
for L in (1, 5, 10):
    r, d = m.clear_rate("长刀(双手近)", "标准", L, S0, RUNS, want_deaths=True)
    P(f"L{L}: 通关 {r:.0%}；死亡 {dict(sorted(d.items()))}")

P("\n【新手初始状态】一级难度，6 武器 × 400 场")
P("构筑 = f × 标准（伤害+25%、每张防御牌护盾+2、生命+20）；模块品质 q")
P(f"{'f \\ q':<8}" + "".join(f"q={q:<8}" for q in (0.6, 0.8, 1.0)))
for f in (0.0, 0.25, 0.5, 0.75, 1.0):
    m.BUILDS["扫描"] = (0.25 * f, 2 * f, 20 * f, 0)
    row = f"{f:<8.2f}"
    for q in (0.6, 0.8, 1.0):
        m.MOD_Q = q
        row += f"{m.mean_rate(W, '扫描', 1, S0, 400):<10.0%}"
    P(row)
m.MOD_Q = 1.0

P("\n【新手初始状态在更高难度】取 f=0.85,q=0.8 与 f=0.55,q=1.0 两个候选")
m.BUILDS["候选1"] = (0.25 * 0.85, 2 * 0.85, 20 * 0.85, 0)
m.BUILDS["候选2"] = (0.25 * 0.55, 2 * 0.55, 20 * 0.55, 0)
P(f"{'':<22}" + "".join(f"L{L:<6}" for L in range(1, 6)))
for name, b, q in (("候选1 f=.85 q=.8", "候选1", 0.8), ("候选2 f=.55 q=1.0", "候选2", 1.0)):
    m.MOD_Q = q
    P(f"{name:<22}" + "".join(f"{m.mean_rate(W, b, L, S0, 400):<7.0%}" for L in range(1, 6)))
m.MOD_Q = 1.0

open("run_sim_v0.6d_report.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
