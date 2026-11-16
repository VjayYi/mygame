"""成长路径与消融：初始 build 逐组换成成熟件，看通关率台阶；成熟 build 逐组拆掉，看每组贡献。"""
import importlib.util, copy
spec = importlib.util.spec_from_file_location("s", "run_sim_v0.7.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
S0, RUNS = 0.74, 1000
out = []
def P(*a):
    line = " ".join(str(x) for x in a); print(line, flush=True); out.append(line)

ST, MM = m.STARTER, m.MATURE_MELEE
# 卡位：[0:4]手脚 [4:6]大脑躯干 [6:9]武器 [9:13]通用 [13:19]防具
def mix(parts, pas):
    cards = []
    for rng_, src in parts:
        cards += src["cards"][rng_[0]:rng_[1]]
    return dict(kind="m", cards=cards, pas=pas, mod_q=1.0 if pas is not ST["pas"] else ST["mod_q"])

def with_(**kw):
    p = dict(ST["pas"]); p.update(kw); return p

steps = {}
steps["0 初始"] = dict(ST, mod_q=0.85)
steps["1 +防具套装(3件,护盾+1)"] = dict(kind="m", cards=ST["cards"][:13] + MM["cards"][13:], pas=with_(shield=ST["pas"]["shield"] + 1), mod_q=0.85)
steps["2 +手脚义体套装(近战+20%/伤害+10%)"] = dict(kind="m", cards=MM["cards"][:4] + ST["cards"][4:13] + MM["cards"][13:],
    pas=with_(shield=ST["pas"]["shield"] + 1, type_bonus=0.20, dmg=0.10), mod_q=0.85)
steps["3 +大脑躯干芯片与被动"] = dict(kind="m", cards=MM["cards"][:6] + ST["cards"][6:13] + MM["cards"][13:],
    pas=dict(MM["pas"]), mod_q=0.85)
steps["4 +高周波长刀与通用卡=成熟(模块池品质1.0)"] = dict(MM)
P(f"【成长路径】近战，难度 L1/L4/L7，{RUNS} 场，S0={S0}")
P(f"{'阶段':<42}{'L1':<8}{'L4':<8}{'L7':<8}")
for k, b in steps.items():
    m.BUILDS["_t"] = b
    P(f"{k:<40}" + "".join(f"{m.clear_rate('_t', L, S0, RUNS):<8.0%}" for L in (1, 4, 7)))

P(f"\n【消融】成熟·近战，逐组拆回初始件，难度 L1/L4/L7")
abl = {}
abl["成熟(完整)"] = dict(MM)
abl["拆 防具套装"] = dict(MM, cards=MM["cards"][:13] + ST["cards"][13:], pas=dict(MM["pas"], shield=MM["pas"]["shield"] - 1))
abl["拆 手脚义体套装"] = dict(MM, cards=ST["cards"][:4] + MM["cards"][4:], pas=dict(MM["pas"], type_bonus=0.15, dmg=0.0))
abl["拆 大脑躯干被动与卡"] = dict(MM, cards=MM["cards"][:4] + ST["cards"][4:6] + MM["cards"][6:],
    pas=dict(MM["pas"], first_atk=0, turn_shield=0, hp=0))
abl["拆 长刀(换短刃)"] = dict(MM, cards=MM["cards"][:6] + ST["cards"][6:9] + MM["cards"][9:])
abl["拆 击晕/抽牌/返能(换纯数值)"] = dict(MM, cards=[("冲击拳","atk",1,4,0,"",True),("破防拳","atk",2,3,0,"",True),("飞踢","atk",1,3,0,"",True),("滑步","def",1,0,4,"",False)] + MM["cards"][4:])
P(f"{'':<34}{'L1':<8}{'L4':<8}{'L7':<8}")
for k, b in abl.items():
    m.BUILDS["_t"] = b
    P(f"{k:<30}" + "".join(f"{m.clear_rate('_t', L, S0, RUNS):<8.0%}" for L in (1, 4, 7)))
open("run_sim_v0.7_progress_report.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
