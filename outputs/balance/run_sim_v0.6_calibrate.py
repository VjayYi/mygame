"""v0.6 校准：成熟 build 阶梯 + 新手初始状态。输出 run_sim_v0.6_report.txt。"""
import importlib.util
import statistics

spec = importlib.util.spec_from_file_location("s", "run_sim_v0.6.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

TARGET = {1: 0.92, 2: 0.80, 3: 0.72, 4: 0.64, 5: 0.56, 6: 0.48, 7: 0.40, 8: 0.33, 9: 0.26, 10: 0.20}
W = m.NON_STUN
out = []


def P(*a):
    line = " ".join(str(x) for x in a)
    print(line, flush=True)
    out.append(line)


def mean_clear(build, level, S, runs):
    return m.mean_rate(W, build, level, S, runs)


# ---- 第一步：S0，使成熟构筑一级难度 ≈ 92% ----
P("【一】成熟构筑（标准 + 正常模块）一级难度校准到 92%（每次 6 武器 × 200 场）")
lo, hi = 0.3, 1.0
for _ in range(7):
    mid = (lo + hi) / 2
    r = mean_clear("标准", 1, mid, 200)
    P(f"  S0={mid:.3f} 通关率={r:.1%}")
    if r > TARGET[1]:
        lo = mid
    else:
        hi = mid
S0 = (lo + hi) / 2
P(f"S0 = {S0:.3f}\n")

# ---- 第二步：只用离散进阶修正（不微调伤害），看自然曲线 ----
P("【二】只用离散修正（双怪↑、精英↑、休息-20%、生命+5%、精英+1动作、商店-1、战后回复-50%、+不可打断+生命、二选一），不微调伤害")
P(f"{'级':<4}{'目标':<8}{'实际':<8}")
nat = {}
for L in range(1, 11):
    r = mean_clear("标准", L, S0, 300)
    nat[L] = r
    P(f"{L:<4}{TARGET[L]:<8.0%}{r:<8.1%}")

# ---- 第三步：逐级拟合怪物伤害微调倍率 ----
P("\n【三】逐级拟合怪物伤害微调倍率（保持离散修正不变，使成熟构筑通关率贴近目标）")
fit = {}
for L in range(2, 11):
    lo, hi = 0.5, 1.8
    for _ in range(7):
        mid = (lo + hi) / 2
        m.DMG_X[L] = mid
        r = mean_clear("标准", L, S0, 200)
        if r > TARGET[L]:
            lo = mid
        else:
            hi = mid
    fit[L] = (lo + hi) / 2
    m.DMG_X[L] = fit[L]
    P(f"  级 {L}: 伤害倍率 {fit[L]:.3f}（相对一级 {(fit[L] - 1) * 100:+.0f}%）")

# ---- 第四步：验证 + 新手初始状态 ----
P("\n【四】验证（成熟构筑，每格 6 武器 × 500 场）与新手初始状态")
RUNS = 500
kits = [
    ("成熟(标准,模块×1.0)", "标准", 1.0),
    ("初始A(裸装,模块×0.6)", "裸装", 0.6),
    ("初始B(半套,模块×0.6)", "半套", 0.6),
    ("初始C(裸装,无模块)", "裸装", 0.0),
]
P(f"{'构筑':<22}" + "".join(f"L{L:<6}" for L in range(1, 11)))
tab = {}
for name, build, q in kits:
    m.MOD_Q = q
    row = f"{name:<22}"
    for L in range(1, 11):
        r = m.mean_rate(W, build, L, S0, RUNS)
        tab[(name, L)] = r
        row += f"{r:<7.0%}"
    P(row)
m.MOD_Q = 1.0
P(f"{'目标（成熟）':<22}" + "".join(f"{TARGET[L]:<7.0%}" for L in range(1, 11)))

P("\n【五】成熟构筑各武器（500 场）：一级 / 五级 / 十级")
P(f"{'武器':<22}{'L1':<8}{'L5':<8}{'L10':<8}")
for w in m.WEAPONS:
    P(f"{w:<22}" + "".join(f"{m.clear_rate(w, '标准', L, S0, RUNS):<8.1%}" for L in (1, 5, 10)))

P("\n【六】成熟构筑在 L1 / L5 / L10 的死亡位置（长刀，500 场）")
for L in (1, 5, 10):
    r, d = m.clear_rate("长刀(双手近)", "标准", L, S0, RUNS, want_deaths=True)
    P(f"L{L}: 通关 {r:.0%}；死亡 {dict(sorted(d.items()))}")

P("\n【七】新手初始状态：需要多强的起始构筑才能让一级难度通关率约 60%？（L1，6 武器 × 400 场）")
P("构筑 = f × 标准（伤害+25%、每张防御牌护盾+2、生命+20）；模块品质 q（1.0 = 成熟阶段的模块）")
P(f"{'f \\ q':<8}" + "".join(f"q={q:<8}" for q in (0.6, 0.8, 1.0)))
for f in (0.0, 0.25, 0.5, 0.75, 1.0):
    m.BUILDS["扫描"] = (0.25 * f, 2 * f, 20 * f, 0)
    row = f"{f:<8.2f}"
    for q in (0.6, 0.8, 1.0):
        m.MOD_Q = q
        row += f"{m.mean_rate(W, '扫描', 1, S0, 400):<10.0%}"
    P(row)
m.MOD_Q = 1.0

P(f"\n汇总：S0={S0:.3f}；伤害倍率 " + ", ".join(f"L{L}={fit[L]:.3f}" for L in fit))
open("run_sim_v0.6c_report.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
