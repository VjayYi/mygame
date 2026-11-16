"""按 StS/月圆结构自动解各级修正的"强度"，让成熟 build（近战+远程均值）命中目标曲线。
每级的修正种类固定（参考 StS Ascension / 月圆噩梦），只二分求该级的一个强度旋钮。"""
import importlib.util
spec = importlib.util.spec_from_file_location("s", "run_sim_v0.7.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

S0 = 0.74
TARGET = {1: 0.905, 2: 0.80, 3: 0.72, 4: 0.64, 5: 0.56, 6: 0.48, 7: 0.39, 8: 0.32, 9: 0.26, 10: 0.20}
MAT = ["成熟·近战", "成熟·远程"]
RUNS = 500
out = []
def P(*a):
    line = " ".join(str(x) for x in a); print(line, flush=True); out.append(line)

def mature(L, runs=RUNS):
    return sum(m.clear_rate(b, L, S0, runs) for b in MAT) / len(MAT)

# (级, 旋钮范围, 构造函数 value -> 该级的 params 更新)
KNOBS = {
    2: (0.0, 1.0, lambda v: dict(elite_p=v)),
    3: (1.0, 2.2, lambda v: dict(nd=v)),
    4: (1.0, 2.2, lambda v: dict(ed=v)),
    5: (1.0, 2.2, lambda v: dict(bd=v, boss_heal=0.75)),
    6: (1.0, 0.7, lambda v: dict(start_loss=0.10, max_hp_mult=v)),
    7: (1.0, 1.8, lambda v: dict(nh=v, eh=v, bh=v)),
    8: (0.0, 0.4, lambda v: dict(enr=v)),
    9: (1.0, 0.1, lambda v: dict(dead=1, shop=1, after=v)),
    10: (0.9, 0.1, lambda v: dict(pick=2, boss_extra_u=True, rest=v)),
}
P(f"【StS/月圆式阶梯自动求解】S0={S0}，成熟 build=近战/远程均值，每评估 {RUNS} 场/build")
base = mature(1)
P(f"L1 基础难度 成熟均值 {base:.1%}（目标约 {TARGET[1]:.0%}）")
solved = {}
for L in range(2, 11):
    lo, hi, mk = KNOBS[L]
    # 难度随 v 向 hi 方向单调增加；二分求命中目标的 v
    a, b = lo, hi
    for _ in range(7):
        mid = (a + b) / 2
        m.LADDER[L] = mk(mid)
        r = mature(L)
        if r > TARGET[L]:
            a = mid
        else:
            b = mid
    v = (a + b) / 2
    m.LADDER[L] = mk(v)
    solved[L] = (v, mature(L, 800))
    P(f"L{L}: 旋钮 {v:.3f} -> 成熟均值 {solved[L][1]:.1%}（目标 {TARGET[L]:.0%}）  {m.LADDER[L]}")

P("\n【最终阶梯】")
for L in range(1, 11):
    P(f"L{L}: {'基础难度' if L == 1 else m.LADDER_NOTES[L]}  {m.LADDER[L] if L > 1 else ''}")
RUNS2 = 1000
P(f"\n【验证】每格 {RUNS2} 场")
P(f"{'':<12}" + "".join(f"L{L:<6}" for L in range(1, 11)))
for b in m.BUILDS:
    P(f"{b:<10}" + "".join(f"{m.clear_rate(b, L, S0, RUNS2):<7.0%}" for L in range(1, 11)))
P(f"{'目标(成熟)':<10}" + "".join(f"{TARGET[L]:<7.0%}" for L in range(1, 11)))
P("\n【死亡位置（成熟·近战）】")
for L in (1, 4, 7, 10):
    r, d = m.clear_rate("成熟·近战", L, S0, RUNS2, want_deaths=True)
    P(f"L{L}: 通关 {r:.0%}；死亡(层,节点) {dict(sorted(d.items()))}")
open("run_sim_v0.7_ladder_report.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
