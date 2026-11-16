# -*- coding: utf-8 -*-
"""从 balance_data.py 导出CSV（UTF-8 BOM，便于表格软件直接打开）。"""
import csv, sys
sys.path.insert(0, ".")
import balance_data as D

R = D.PLAYER["turn_base_rolls"]

def fmt(x):
    if isinstance(x, float):
        return ("%.2f" % x).rstrip("0").rstrip(".")
    return x

rows = []
for d in D.M + D.E + D.B + D.FINAL:
    ehp = d["hp"] + d["shield"] + d["extra_ehp"]
    dps = d["dmg"] * d["hits"] / d["interval"] + d["bonus_dps"]
    note = ""
    if d["tier"] == "小Boss":
        note = "长局第一层基准；第二层HP×1.75、伤害×1.3"
    elif d["tier"] == "大Boss":
        note = "第三层三阶段顺序战斗，阶段间不回血；模块为额外目标"
    elif d["tier"] == "精英":
        note = "街区Boss池；随行单位见机制"
    rows.append([
        d["id"], d["name"], d["tier"], fmt(d["hp"]), fmt(d["shield"]), fmt(d["dmg"]), d["hits"], fmt(d["interval"]),
        fmt(d["extra_ehp"]), fmt(d["bonus_dps"]), fmt(ehp), fmt(round(dps, 2)), fmt(round(dps * 2 * R, 1)),
        d["special"], note,
    ])

with open("enemy_balance_v0.1.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["ID", "名称", "层级", "生命", "护盾", "单段伤害", "段数", "实时行动间隔(秒)", "额外有效耐久",
                "持续伤害DPS", "有效耐久", "实时DPS", "回合制每回合折算伤害(基础3投)", "特殊机制", "备注"])
    w.writerows(rows)

params = []
params.append(["玩家技能", "剑", "伤害8", "无限贴面基础技能，单体"])
params.append(["玩家技能", "盾", "护盾6", "无限贴面基础技能，护盾本场战斗结束时清空"])
params.append(["玩家技能", "心", "治疗8", "无限贴面基础技能，不超过最大生命"])
params.append(["玩家技能", "枪击", "伤害11", "局外解锁；P0建议最多贴3面"])
for k, d in D.LOADOUTS.items():
    params.append(["模拟骰面配置", k, str(d), "用于验证没有单一配置压倒其他配置"])
for key, val, desc in D.PARAMS:
    params.append(["规则参数", key, fmt(val), desc])
for pid, name, c, b, a, s, desc in D.PLUGINS:
    params.append(["插件", pid + " " + name, "C %s / B %s / A %s / S %s" % (c, b, a, s), desc])
params.append(["模拟结论", "回合基础投数", "3投", "空转回合约8.6%，2投约19.2%；平均回合数2.8 vs 4.0，选择次数更多"])
params.append(["模拟结论", "实时街区(均衡配置)", "有成长近似：街区1约100%，街区3约75%，街区4约33%", "仅入口增益，不继承前区成长；需用原型验证累计成长"])
params.append(["模拟结论", "精英单战", "失血20~28，用时13~44秒", "满血均衡配置，街区1；维修母机最长"])
params.append(["模拟结论", "小Boss", "L1约80~90%，L2约58~75%，平均8~10回合", "单战，玩家带1.5x/2.2x成长倍率"])
params.append(["模拟结论", "大Boss", "胜率约67%，约14回合", "玩家带2.8x成长倍率，三阶段连续"])
params.append(["模拟边界", "已模拟", "实时街区基础战斗、精英单战、回合制普通战斗和小Boss/大Boss耐久", "简化模型，不含具体减益/反射/召唤细节"])
params.append(["模拟边界", "未模拟", "形态、五种概率被动、完整事件池、第二层普通战斗、跨街区累计成长、真实玩家决策", "原型阶段必须实测，不能直接当最终平衡"])

with open("params_balance_v0.1.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["分类", "项目", "数值", "说明"])
    w.writerows(params)

print(len(rows), len(params))
