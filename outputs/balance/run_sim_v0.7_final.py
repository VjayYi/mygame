"""v0.7 定稿验证：三套 build × 10 级难度，死亡位置。"""
import importlib.util
spec = importlib.util.spec_from_file_location("s", "run_sim_v0.7.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
S0, RUNS = 0.74, 1500
out = []
def P(*a):
    line = " ".join(str(x) for x in a); print(line, flush=True); out.append(line)
P(f"【v0.7 定稿验证】S0={S0}, LUCK={m.LUCK}, 每格 {RUNS} 场")
P(f"{'':<10}" + "".join(f"L{L:<6}" for L in range(1, 11)))
rows = {}
for b in m.BUILDS:
    rows[b] = [m.clear_rate(b, L, S0, RUNS) for L in range(1, 11)]
    P(f"{b:<8}" + "".join(f"{r:<7.0%}" for r in rows[b]))
avg = [(rows["成熟·近战"][i] + rows["成熟·远程"][i]) / 2 for i in range(10)]
P(f"{'成熟均值':<8}" + "".join(f"{r:<7.0%}" for r in avg))
P(f"{'目标':<10}" + "".join(f"{t:<7.0%}" for t in (0.90, 0.80, 0.72, 0.64, 0.56, 0.48, 0.39, 0.32, 0.26, 0.20)))
P("\n【阶梯定义】")
for L in range(2, 11):
    P(f"L{L}: {m.LADDER_NOTES[L]}   {m.LADDER[L]}")
P("\n【死亡位置（成熟·近战 / 初始）(层,节点)】")
for b in ("成熟·近战", "初始·短刃"):
    for L in (1, 5, 10):
        r, d = m.clear_rate(b, L, S0, RUNS, want_deaths=True)
        P(f"{b} L{L}: 通关 {r:.0%}；死亡 {dict(sorted(d.items()))}")
open("run_sim_v0.7_final_report.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
