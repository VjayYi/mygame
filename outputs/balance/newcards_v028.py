"""新机制候选卡 v0.28：50 个模块 + 50 个义体 + 副产品卡。
数值由脚本按预算自动调到 85%～120%（含占模补偿、供能负担），文本里的 {n} 是被调的主数值。"""
# ruff: noqa: E501
import importlib.util
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import power_supply_v027 as PS  # noqa: E402
from card_value_engine import DOT_E, base_budget, footprint  # noqa: E402


def D(n):
    return n / 6.0           # 伤害/护盾 E
def HEAL(n):
    return 1.3 * n / 6.0   # 回复生命 E
def NXT(n):
    return 0.8 * n / 6.0    # 下一张攻击 +n E
def DRAW(n):
    return 0.4 * n
UNDER, OVER = 0.85, 1.20
SUP_E = 0.02
EX_BONUS = 0.4                   # 消耗牌给 +0.4E（杀戮尖塔 消耗≈-0.5 能量 的口径）
COND_BASE = 3.3                  # 高费条件减费卡：按“常态减到 3 费”+10% 估价

spec = importlib.util.spec_from_file_location("ma", os.path.join(os.path.dirname(__file__), "module_audit_v0.26.py"))
MA = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MA)

# ======================= 模块（50） =======================
# M(名称, 格数, 大类, 类型, 名义费用, 卡效果模板, 价值函数(n), 终极模板, 朝向, 来源, 限定品类, (升级类型, 升级模板|None), 机制标签, 模式, n 范围, 终极系数)
MODS = []


def M(name, size, major, typ, cost, tmpl, vf, ult, facing, pool, limit, up, mech, mode="normal", nr=(1, 40), uk=0.3, lean="均衡"):
    MODS.append(dict(name=name, size=size, major=major, type=typ, cost=cost, tmpl=tmpl, vf=vf, ult=ult, facing=facing, pool=pool,
                     limit=limit, up=up, mech=mech, mode=mode, nr=nr, uk=uk, lean=lean))


# ---- A. 3 费模块（19）：能力牌、群攻、处决、成长、过载 ----
M("处刑重斩", 6, "近战", "伤害", 3, "伤害 +{n}；目标生命低于 40% 时，本卡伤害 +50%", lambda n: D(n) * 1.25, "伤害 +{u}；击杀时抽 1 张", "是", "怪物产出", "—", ("数值", None), "斩杀线", lean="卡强")
M("狂暴连锁", 5, "近战", "伤害", 3, "伤害 +{n}；本场战斗每打出过一次本卡，本卡伤害永久 +4", lambda n: D(n) + 0.67, "伤害 +{u}", "是", "怪物产出", "—",
  ("机制核心", "伤害 +{n}；【核心·狂暴】本卡每次打出后伤害永久 +4，且本卡打出后回到手牌（每回合 1 次）"), "成长", lean="卡强")
M("绝对防御", 5, "近战", "防御", 3, "消耗；本场战斗每回合开始护盾 +{n}", lambda n: 4 * D(n), "终极卡打出时护盾 +{u}", "否", "怪物产出", "—", ("数值", None), "能力", mode="exhaust", nr=(1, 20))
M("血怒觉醒", 5, "近战", "节奏", 3, "消耗；本场战斗每受到 1 次伤害，下一张攻击牌 +{n}（本回合上限 +24）", lambda n: 3 * NXT(n) * 0.9, "终极卡伤害 +{u}", "是", "怪物产出", "—", ("持续", "消耗；本场战斗每受到 1 次伤害，接下来 2 张攻击牌各 +{n}（本回合上限 +24）"), "能力", mode="exhaust", nr=(1, 25))
M("千刃领域", 6, "近战", "伤害", 3, "全体敌人各 -{n}；命中 2 名以上敌人时抽 1 张", lambda n: D(n) * 1.6 + 0.26, "全体敌人各 -{u}", "否", "怪物产出", "—", ("数值", None), "群攻")
M("铁壁堡垒", 6, "近战", "防御", 3, "护盾 +{n}；本回合受到的伤害 -2；回合结束时保留 50% 护盾", lambda n: D(n) + 0.8, "终极卡护盾 +{u}", "否", "怪物产出", "—", ("数值", None), "护盾保留")
M("魔剑觉醒", 4, "近战", "节奏", 3, "消耗；本场战斗你的所有攻击牌伤害 +{n}", lambda n: 8 * D(n), "终极卡伤害 +{u}", "否", "怪物产出", "—", ("降费", None), "能力", mode="exhaust", nr=(1, 6), lean="卡强")
M("嗜血狂欢", 5, "近战", "回复", 3, "伤害 +{n}；回复造成伤害的 50% 生命", lambda n: D(n) * 1.65, "终极卡伤害 +{u}，回复 25% 生命", "是", "怪物产出", "—", ("数值", None), "吸血")
M("屠戮盛宴", 6, "近战", "特殊", 3, "伤害 +{n}；本场战斗每击杀 1 名敌人，抽 1 张并回复 1 能源（至多 3 次）", lambda n: D(n) + 1.27, "击杀时抽 1 张；伤害 +{u}", "是", "怪物产出", "—", ("追加", "伤害 +{n}；本场战斗每击杀 1 名敌人，抽 1 张并回复 1 能源（至多 3 次）；护盾 +4"), "击杀联动", lean="卡强")
M("轨道炮击", 6, "远程", "伤害", 3, "伤害 +{n}；忽略护盾", lambda n: D(n) + 0.3, "伤害 +{u}；无视护盾", "是", "怪物产出", "—", ("数值", None), "穿透", lean="卡强")
M("火力覆盖", 6, "远程", "伤害", 3, "全体敌人各 -{n}；护盾为 0 的敌人额外 -3", lambda n: D(n) * 1.6 + 0.4, "全体敌人各 -{u}", "否", "怪物产出", "—", ("数值", None), "群攻")
M("无尽弹链", 5, "远程", "伤害", 3, "伤害 +{n}；本场战斗每打出过一次本卡，本卡额外结算 1 段（至多 4 段）", lambda n: D(n) * 1.75, "伤害 +{u}；额外结算 1 段", "是", "怪物产出", "—",
  ("机制核心", "伤害 +{n}；【核心·弹链】每段命中后下一段伤害 +2；段数上限提高到 6"), "成长")
M("战场预判", 5, "远程", "节奏", 3, "消耗；本场战斗每回合开始抽 1 张，每回合首张牌费用 -1（至多 4 回合）", lambda n: 4.4, "终极卡打出后抽 1 张", "否", "怪物产出", "—", ("持续", "消耗；本场战斗每回合开始抽 1 张，每回合首张牌费用 -1（至多 6 回合）"), "能力", mode="exhaust", nr=None)
M("重炮齐射", 6, "远程", "伤害", 3, "伤害 +{n}；下回合你的攻击牌费用 +1（过载）", lambda n: D(n) - 0.4, "伤害 +{u}", "是", "怪物产出", "—", ("降费", None), "过载", lean="卡强")
M("毁灭之矛", 5, "远程", "伤害", 3, "伤害 +{n}；追加 2 费：改为 1～3 号位全体各 -{n}", lambda n: D(n) * 1.3, "伤害 +{u}", "是", "怪物产出", "—", ("数值", None), "追加")
M("弹幕风暴", 6, "远程", "特殊", 3, "随机攻击 5 次，每次 {n} 伤害（可重复命中同一敌人）", lambda n: 5 * D(n), "随机攻击 2 次，每次 {u} 伤害", "否", "怪物产出", "—", ("数值", None), "随机多段", nr=(1, 10))
M("死线预告", 5, "远程", "控制", 3, "所有敌人下回合攻击 -{n}；各 30% 击晕", lambda n: D(n) * 2 + 1.0, "所有敌人下回合攻击 -{u}", "否", "怪物产出", "—", ("数值", None), "控制")
M("全域屏障", 6, "远程", "防御", 3, "护盾 +{n}；本回合敌人对你的首次攻击被打断", lambda n: D(n) + 0.6, "终极卡护盾 +{u}", "否", "怪物产出", "—", ("数值", None), "打断")
M("雷霆手雷", 4, "远程", "伤害", 3, "伤害 +{n}；全体敌人各 30% 击晕", lambda n: D(n) + 1.2, "伤害 +{u}", "是", "怪物产出", "—", ("降费", None), "群控")

# ---- B. 高费·条件减费（8）：卡面写明减费条件 ----
M("烈焰风暴", 5, "近战", "伤害", 5, "费用 5；本回合每已打出 1 张牌，本卡费用 -1。全体敌人各 -{n}", lambda n: D(n) * 1.6, "全体敌人各 -{u}", "否", "怪物产出", "—", ("降费", None), "条件减费", mode="cond")
M("墓土召回", 4, "近战", "特殊", 5, "费用 5；弃牌堆每有 4 张牌，本卡费用 -1。将弃牌堆全部洗回牌库；抽 3 张；护盾 +{n}", lambda n: 0.6 + 1.2 + D(n), "打出终极卡后，弃牌堆洗回牌库（本场 1 次）", "否", "怪物产出", "—",
  ("机制核心", "费用 5；弃牌堆每有 3 张牌，本卡费用 -1。将弃牌堆全部洗回牌库；抽 3 张；护盾 +{n}；【核心·掘墓】洗回的牌本回合各回复 1 点护盾"), "条件减费·洗牌", mode="cond")
M("收割者", 5, "近战", "伤害", 5, "费用 5；本场战斗每击杀 1 名敌人，本卡费用 -1（最低 1）。伤害 +{n}；击杀时回到手牌", lambda n: D(n) + 0.5, "伤害 +{u}", "是", "怪物产出", "—", ("数值", None), "条件减费·击杀", mode="cond")
M("以血为价", 4, "近战", "伤害", 4, "费用 4；生命低于 50% 时，本卡费用 -2。伤害 +{n}；回复 6 生命", lambda n: D(n) + 1.3, "伤害 +{u}", "是", "怪物产出", "—", ("降费", None), "条件减费·残血", mode="cond")
M("孤注一掷", 6, "远程", "伤害", 6, "费用 6；本回合每已花费 1 点能源，本卡费用 -1（最低 1）。伤害 +{n}", lambda n: D(n), "伤害 +{u}", "是", "怪物产出", "—", ("数值", None), "条件减费·能源", mode="cond")
M("蓄势待发", 5, "远程", "伤害", 4, "费用 4；保留。本卡在手牌中每保留 1 回合，费用 -1（最低 1）。伤害 +{n}，1 号位全体", lambda n: D(n) * 1.3, "伤害 +{u}", "是", "怪物产出", "—", ("数值", None), "条件减费·保留", mode="cond")
M("万毒之主", 5, "远程", "状态", 5, "费用 5；敌人身上每有 3 层异常状态，本卡费用 -1（全体计算）。全体敌人当前所有中毒/流血/灼烧层数翻倍", lambda n: 3.9, "全体敌人异常状态层数 +1", "否", "怪物产出", "—",
  ("机制核心", "费用 5；敌人身上每有 2 层异常状态，本卡费用 -1。全体敌人当前所有中毒/流血/灼烧层数翻倍；【核心·蔓延】异常状态致死时，层数转移给相邻敌人"), "条件减费·状态", mode="cond", nr=None)
M("终局审判", 6, "远程", "伤害", 6, "费用 6；本回合已打出 1/2/3 张及以上攻击牌，本卡费用 -1/-2/-3。伤害 +{n}；目标已有 3 层以上异常状态时伤害翻倍", lambda n: D(n) * 1.3, "伤害 +{u}",
  "是", "怪物产出", "—", ("机制核心", "费用 6；本回合每已打出 1 张攻击牌，本卡费用 -1（最低 1）。伤害 +{n}；目标已有 2 层以上异常状态时伤害翻倍；【核心·审判】击杀时本卡回到手牌并费用 -2"), "条件减费·连击", mode="cond")

# ---- C. 战斗内成长（6） ----
M("磨砺之刃", 3, "近战", "伤害", 1, "伤害 +{n}；本场战斗每打出过一次本卡，本卡伤害永久 +2", lambda n: D(n) + 0.33, "伤害 +{u}", "是", "基地", "—", ("两段", "伤害 +{m} ×2 段；本场战斗每打出过一次本卡，本卡伤害永久 +2"), "成长")
M("积怨", 4, "近战", "伤害", 1, "伤害 +{n}；本场战斗每受到 1 次伤害，本卡伤害永久 +1（至多 +8）", lambda n: D(n) + 0.5, "伤害 +{u}", "是", "基地", "—", ("数值", None), "成长")
M("滚雪球", 3, "近战", "防御", 1, "护盾 +{n}；本场战斗每打出过一次本卡，本卡护盾永久 +2", lambda n: D(n) + 0.33, "终极卡护盾 +{u}", "否", "基地", "—", ("数值", None), "成长")
M("越战越勇", 4, "近战", "节奏", 1, "伤害 +{n}；本场战斗每打出 1 张攻击牌，你的攻击牌伤害永久 +1（至多 +6）", lambda n: D(n) + 0.9, "伤害 +{u}", "是", "怪物产出", "—", ("持续", "伤害 +{n}；本场战斗每打出 1 张攻击牌，你的攻击牌伤害永久 +1（至多 +9）"), "成长")
M("蓄能炮", 5, "远程", "伤害", 2, "保留。本卡每在手牌中保留 1 回合，伤害 +4（打出后重置）；伤害 +{n}", lambda n: D(n) + 1.0, "伤害 +{u}", "是", "基地", "—", ("数值", None), "成长·保留")
M("滴水穿石", 3, "远程", "状态", 1, "附加中毒 {n}；本场战斗每打出过一次本卡，附加层数永久 +1", lambda n: n * DOT_E + 0.5, "中毒 +{u}", "否", "基地", "—", ("数值", None), "成长", nr=(1, 12))

# ---- D. 递减 / 次数（4） ----
M("用尽即弃", 3, "近战", "伤害", 1, "伤害 +{n}；每次打出后，本卡伤害 -2（最低 2）", lambda n: D(n) - 0.17, "伤害 +{u}", "是", "基地", "—", ("两段", "伤害 +{m} ×2 段；每次打出后，本卡伤害 -2（最低 2）"), "递减")
M("残存弹药", 4, "远程", "伤害", 1, "共 3 发：伤害 +{n}；打出 3 次后消耗", lambda n: D(n), "伤害 +{u}", "是", "基地", "—", ("追加", "共 4 发：伤害 +{n}；打出 4 次后消耗"), "次数", mode="exhaust")
M("一次性护符", 3, "近战", "防御", 1, "护盾 +{n}；每次打出后，本卡护盾 -2（最低 2）", lambda n: D(n) - 0.2, "终极卡护盾 +{u}", "否", "基地", "—", ("数值", None), "递减")
M("衰变光环", 4, "远程", "控制", 1, "目标下回合攻击 -{n}；每次打出后，本卡减益 -1（最低 1）", lambda n: D(n) + 0.1, "目标下回合攻击 -{u}", "否", "基地", "—", ("数值", None), "递减")

# ---- E. 指定过牌：检索 / 发现 / 预知（5） ----
M("精准检索", 3, "近战", "过牌", 1, "从牌库中选择 1 张攻击牌加入手牌；护盾 +{n}", lambda n: 0.7 + D(n), "终极卡打出时检索 1 张攻击牌", "否", "基地", "—", ("追加", "从牌库中选择 1 张攻击牌加入手牌，该牌本回合费用 -1；护盾 +{n}"), "检索")
M("战术发现", 4, "远程", "过牌", 1, "发现：查看牌库顶 3 张，选 1 张加入手牌，其余放回牌库底；护盾 +{n}", lambda n: 0.9 + D(n), "终极卡打出后，发现 1 张", "否", "基地", "—", ("追加", "发现：查看牌库顶 4 张，选 1 张加入手牌，其余放回牌库底；护盾 +{n}"), "发现")
M("防御检索", 3, "近战", "防御", 1, "从牌库中选择 1 张防御牌加入手牌；护盾 +{n}", lambda n: 0.7 + D(n), "终极卡护盾 +{u}", "否", "基地", "—", ("数值", None), "检索")
M("名册索引", 4, "远程", "过牌", 2, "从牌库中选择 1 张武器基础卡加入手牌，该卡本回合费用 -1；抽 1 张；护盾 +{n}", lambda n: 1.4 + 0.4 + D(n), "终极卡打出后抽 1 张", "否", "怪物产出", "—", ("降费", None), "检索")
M("预知扫描", 3, "远程", "过牌", 1, "预知 4：查看牌库顶 4 张，可弃置其中任意张；抽 1 张；护盾 +{n}", lambda n: 0.5 + 0.4 + D(n), "预知 +1", "否", "基地", "—", ("追加", "预知 5：查看牌库顶 5 张，可弃置其中任意张；抽 1 张；护盾 +{n}"), "预知")

# ---- F. 消耗 / 副产品 / 复制（8） ----
M("火种引信", 4, "近战", "特殊", 2, "将 2 张【火种】加入手牌；护盾 +{n}", lambda n: 1.66 + D(n), "终极卡打出时将 1 张【火种】加入手牌", "否", "怪物产出", "—", ("追加", "将 3 张【火种】加入手牌；护盾 +{n}"), "衍生")
M("弹壳回收", 4, "远程", "特殊", 1, "本回合你每打出 1 张攻击牌，将 1 张【弹壳】加入弃牌堆（上限 3 张）；护盾 +{n}", lambda n: 1.0 + D(n), "终极卡打出时将 1 张【弹壳】加入手牌", "否", "基地", "—", ("追加", "本回合你每打出 1 张攻击牌，将 1 张【弹壳】加入手牌（上限 3 张）；护盾 +{n}"), "衍生")
M("碎刃", 3, "近战", "伤害", 1, "消耗；伤害 +{n}；将 2 张【碎片】加入手牌", lambda n: D(n) + 0.8, "伤害 +{u}", "是", "基地", "—", ("数值", None), "衍生·消耗", mode="exhaust")
M("战场拾荒", 4, "近战", "特殊", 1, "击杀敌人时，将 1 张【零件】加入手牌（本场战斗每回合 1 次）；护盾 +{n}", lambda n: 0.78 + D(n), "终极卡击杀时将 1 张【零件】加入手牌", "否", "怪物产出", "—", ("数值", None), "衍生")
M("紧急补给", 3, "近战", "回复", 1, "消耗；回复 {n} 生命；抽 2 张", lambda n: HEAL(n) + 0.8, "终极卡打出时回复 {u} 生命", "否", "基地", "—", ("数值", None), "消耗", mode="exhaust", nr=(1, 20))
M("一次性爆弹", 4, "远程", "伤害", 1, "消耗；全体敌人各 -{n}", lambda n: D(n) * 1.6, "全体敌人各 -{u}", "否", "基地", "—", ("数值", None), "消耗", mode="exhaust")
M("过热废料", 4, "远程", "能源", 1, "将 1 张【过热】加入弃牌堆；本回合能源 +1；抽 1 张；护盾 +{n}", lambda n: 0.8 + D(n), "终极卡打出时将 1 张【过热】加入弃牌堆，抽 2 张", "否", "怪物产出", "—", ("追加", "将 1 张【过热】加入弃牌堆；本回合能源 +1；抽 2 张；护盾 +{n}"), "废牌")
M("暗影分身", 5, "近战", "特殊", 2, "复制手牌中 1 张攻击牌，本回合有效（复制牌打出后消耗）；伤害 +{n}", lambda n: 1.2 + D(n), "终极卡伤害 +{u}", "是", "怪物产出", "—", ("降费", None), "复制")

# ======================= 义体（50） =======================
# 部位 手/脚/脑/躯干；脑/躯干带被动
IMPS = []


def AddImp(part, name, cost, tmpl, vf, wo=None, passive=None, pe=0.0, mech="", mode="normal", nr=(1, 40), uptype="数值"):
    IMPS.append(dict(part=part, name=name, cost=cost, tmpl=tmpl, vf=vf, wo=wo, passive=passive, pe=pe, mech=mech, mode=mode, nr=nr, uptype=uptype))


# 手 15
AddImp("手", "连发手", 2, "伤害 {n} ×3 段（每段独立结算）", lambda n: 3 * D(n), (1, 2), mech="多段")
AddImp("手", "磨损手", 1, "伤害 {n}；每次打出后，本卡伤害 -1（最低 2）", lambda n: D(n) - 0.17, (1, 1), mech="递减")
AddImp("手", "成长手", 1, "伤害 {n}；本场战斗每打出一次，本卡伤害永久 +2", lambda n: D(n) + 0.33, (1, 1), mech="成长")
AddImp("手", "重炮手", 3, "伤害 {n}；击退 1 格", lambda n: D(n) + 0.15, (3, 3), mech="重击")
AddImp("手", "弹仓手", 2, "消耗；伤害 {n}；将 3 张【碎片】加入手牌", lambda n: D(n) + 1.2, (2, 1), mech="衍生·消耗", mode="exhaust")
AddImp("手", "检索手", 1, "伤害 {n}；从牌库中选择 1 张攻击牌加入手牌", lambda n: D(n) + 0.7, (1, 1), mech="检索")
AddImp("手", "过载脉冲手", 5, "费用 5；本回合每已打出 1 张义体卡，本卡费用 -1（最低 1）。全体敌人各 {n} 伤害", lambda n: D(n) * 1.6, (2, 2), mech="条件减费", mode="cond")
AddImp("手", "复制手", 2, "复制手牌中 1 张攻击牌，本回合有效（复制牌打出后消耗）；伤害 {n}", lambda n: 1.2 + D(n), (2, 2), mech="复制")
AddImp("手", "钳制手", 1, "伤害 {n}；目标下回合攻击 -3", lambda n: D(n) + 0.5, (1, 2), mech="控制")
AddImp("手", "吸血爪", 1, "伤害 {n}；回复造成伤害的 50% 生命", lambda n: D(n) * 1.65, (1, 1), mech="吸血")
AddImp("手", "爆发手", 2, "伤害 {n}；本回合每已打出 1 张牌，本卡伤害 +2", lambda n: D(n) + 1.0, (2, 2), mech="连携")
AddImp("手", "点燃手", 1, "伤害 {n}；附加灼烧 3", lambda n: D(n) + 0.75, (1, 1), mech="灼烧")
AddImp("手", "磁力手", 1, "伤害 {n}；将目标拉到 1 号位", lambda n: D(n) + 0.15, (1, 2), mech="位移")
AddImp("手", "千斤手", 3, "消耗；1 号位全体各受 {n} 伤害", lambda n: D(n) * 1.3, (3, 3), mech="重击·消耗", mode="exhaust")
AddImp("手", "反击手", 1, "奥秘：敌人下一次攻击时，对其造成 {n} 伤害，并使该次攻击伤害 -4（本场限 1 次）", lambda n: D(n) + 0.45, (1, 2), mech="奥秘")
# 脚 15
AddImp("脚", "加速腿", 1, "护盾 {n}；抽 1 张", lambda n: D(n) + 0.4, mech="过牌")
AddImp("脚", "钢锚腿", 2, "护盾 {n}；本回合不能被击退", lambda n: D(n) + 0.1, mech="护盾")
AddImp("脚", "反推腿", 1, "后撤 1 格；伤害 {n}", lambda n: D(n) + 0.1, mech="位移")
AddImp("脚", "弹弓腿", 1, "护盾 {n}；本场战斗每打出一次，本卡护盾永久 +2", lambda n: D(n) + 0.33, mech="成长")
AddImp("脚", "蓄力腿", 2, "保留。每在手牌中保留 1 回合，本卡护盾 +4（打出后重置）；护盾 {n}", lambda n: D(n) + 0.7, mech="成长·保留")
AddImp("脚", "拾荒腿", 1, "击杀敌人时，将 1 张【零件】加入手牌（本场战斗每回合 1 次）；护盾 {n}", lambda n: 0.5 + D(n), mech="衍生")
AddImp("脚", "滑翔腿", 1, "从牌库中选择 1 张防御牌加入手牌；护盾 {n}", lambda n: 0.7 + D(n), mech="检索")
AddImp("脚", "虚影腿", 2, "消耗；本回合闪避 2 次攻击；护盾 {n}", lambda n: 1.33 + D(n), mech="闪避·消耗", mode="exhaust")
AddImp("脚", "缓冲腿", 1, "护盾 {n}；每次打出后，本卡护盾 -1（最低 2）", lambda n: D(n) - 0.15, mech="递减")
AddImp("脚", "陷阱腿", 1, "奥秘：敌人下一次攻击时，对其造成 {n} 伤害并使其下回合攻击 -3（本场限 1 次）", lambda n: D(n) + 0.5, mech="奥秘")
AddImp("脚", "震荡腿", 2, "1 号位全体各受 {n} 伤害；20% 击晕", lambda n: D(n) * 1.3 + 0.6, mech="群控")
AddImp("脚", "重甲腿", 3, "护盾 {n}；回合结束时保留 50% 护盾", lambda n: D(n) + 0.5, mech="护盾保留")
AddImp("脚", "疾跑腿", 1, "下一张牌费用 -1；护盾 {n}", lambda n: 0.7 + D(n), mech="减费")
AddImp("脚", "急救腿", 2, "消耗；回复 {n} 生命；护盾 4", lambda n: HEAL(n) + 0.67, mech="回复·消耗", mode="exhaust", nr=(1, 20))
AddImp("脚", "位移腿", 1, "前移或后撤 1 格；护盾 {n}；下一张攻击 +3", lambda n: 0.1 + D(n) + 0.4, mech="位移")
# 大脑 10（被动 + 可打卡）
AddImp("脑", "回响芯片", 1, "弃 2 张，抽 2 张；护盾 {n}", lambda n: 0.5 + D(n), passive="每回合第一次弃牌时，抽 1 张", pe=0.35, mech="弃牌")
AddImp("脑", "检索芯片", 1, "从牌库中选择 1 张攻击牌加入手牌；护盾 {n}", lambda n: 0.7 + D(n), passive="固有：每场战斗开始时，从牌库中选择 1 张牌加入起手牌", pe=0.4, mech="检索·固有")
AddImp("脑", "预知芯片", 1, "预知 3；抽 1 张；护盾 {n}", lambda n: 0.45 + 0.4 + D(n), passive="每回合开始时预知 2", pe=0.3, mech="预知")
AddImp("脑", "成长芯片", 1, "下一张攻击牌 +{n}", lambda n: NXT(n), passive="本场战斗每打出 5 张牌，你的攻击牌伤害永久 +1（至多 +4）", pe=0.5, mech="成长")
AddImp("脑", "熔炉芯片", 2, "消耗手牌中 1 张牌；抽 2 张；护盾 {n}", lambda n: 0.8 - 0.1 + D(n) + 0.4, passive="每当一张牌被消耗，抽 1 张", pe=0.5, mech="消耗联动")
AddImp("脑", "衍生芯片", 1, "将 2 张【碎片】加入手牌；护盾 {n}", lambda n: 0.8 + D(n), passive="每回合开始时，将 1 张【碎片】加入手牌", pe=0.5, mech="衍生")
AddImp("脑", "连携芯片", 1, "本回合每已打出 1 张牌，护盾 +2（基础 {n}）", lambda n: D(n) + 0.9, passive="每回合打出第 3 张牌后，抽 1 张", pe=0.4, mech="连携")
AddImp("脑", "减费芯片", 1, "下一张牌费用 -1（最低 0）；抽 1 张", lambda n: 0.7 + 0.4, passive="每场战斗第一张 3 费以上的牌，费用 -1", pe=0.4, mech="减费", nr=None)
AddImp("脑", "奥秘芯片", 2, "奥秘：本场战斗敌人每攻击你 1 次，对其造成 {n} 伤害（至多 3 次）", lambda n: 3 * D(n) * 0.6, passive="每场战斗开始时，自动埋下 1 个奥秘：敌人第一次攻击时对其造成 4 伤害", pe=0.5, mech="奥秘")
AddImp("脑", "反刍芯片", 1, "闪回：从弃牌堆选 1 张牌打出一次，然后将其消耗；护盾 {n}", lambda n: 1.1 + D(n), passive="每回合结束时，弃牌堆顶 1 张牌放回牌库顶", pe=0.4, mech="闪回")
# 躯干 10（被动 + 可打卡）
AddImp("躯", "逆鳞核心", 1, "护盾 {n}；回复 3 生命", lambda n: D(n) + 0.65, passive="本场战斗每受到 1 次伤害，你的攻击牌伤害 +1（至多 +5）", pe=0.5, mech="受击成长")
AddImp("躯", "弹壳工厂", 1, "护盾 {n}；将 1 张【弹壳】加入手牌", lambda n: D(n) + 0.5, passive="每打出 3 张攻击牌，将 1 张【弹壳】加入手牌", pe=0.4, mech="衍生")
AddImp("躯", "消耗炉芯", 1, "消耗手牌中 1 张牌；护盾 {n}；抽 1 张", lambda n: D(n) + 0.4 + 0.3, passive="每当一张牌被消耗，回复 2 生命", pe=0.3, mech="消耗联动")
AddImp("躯", "递减护盾", 1, "护盾 {n}", lambda n: D(n), passive="每回合开始时护盾 +4，且战斗中每过 1 回合少 1（最低 1）", pe=0.5, mech="递减")
AddImp("躯", "重装核心", 2, "保留；护盾 {n}，每保留 1 回合 +3", lambda n: D(n) + 0.7, passive="手牌上限 +1（保留的牌不占上限）", pe=0.5, mech="保留")
AddImp("躯", "反应装甲", 1, "护盾 {n}；本回合受到攻击时，伤害 -2", lambda n: D(n) + 0.5, passive="受到攻击时，将 1 张【碎片】加入手牌（每回合 1 次）", pe=0.4, mech="衍生")
AddImp("躯", "储备核心", 1, "护盾 {n}；抽 1 张", lambda n: D(n) + 0.4, passive="每场战斗开始时，将 2 张【应急药剂】加入弃牌堆", pe=0.6, mech="衍生")
AddImp("躯", "蓄电核心", 1, "保留；护盾 {n}，每保留 1 回合 +2", lambda n: D(n) + 0.5, passive="手牌中保留的每张牌，每过 1 回合，护盾 +1", pe=0.4, mech="保留")
AddImp("躯", "契约核心", 3, "消耗；本场战斗每回合开始，护盾 +{n}，回复 2 生命", lambda n: 4 * (D(n) + 0.43), passive="每场战斗 1 次：生命将归零时，改为保留 1 点生命", pe=0.7, mech="能力·保命", mode="exhaust", nr=(1, 12))
AddImp("躯", "逆转核心", 1, "回复 {n} 生命；护盾 3", lambda n: HEAL(n) + 0.5, passive="生命低于 30% 时，每回合第一张牌费用 -1", pe=0.5, mech="残血", nr=(1, 20))

# ======================= 副产品卡 =======================
TOKENS = [
    ("火种", "攻击", 0, "消耗；造成 5 伤害", "0 费、消耗；来源：火种引信、终极卡"),
    ("碎片", "攻击", 0, "消耗；造成 4 伤害", "0 费、消耗；来源：碎刃、弹仓手、衍生芯片、反应装甲"),
    ("弹壳", "防御", 0, "消耗；护盾 5", "0 费、消耗；来源：弹壳回收、弹壳工厂"),
    ("零件", "功能", 0, "消耗；抽 1 张；护盾 1", "0 费、消耗；来源：战场拾荒、拾荒腿"),
    ("应急药剂", "功能", 0, "消耗；回复 6 生命", "0 费、消耗；来源：储备核心"),
    ("过热", "废牌", 0, "不可打出；回合结束时若在手牌，受到 2 伤害并消耗", "负面衍生牌；来源：过热废料。用来换取更强效果"),
    ("灼伤", "废牌", 0, "不可打出；占手牌位；回合结束时消耗", "预留：敌人/事件可塞入的废牌，用来给“消耗/弃牌”流派提供素材"),
]


def tune(sp, B, kind):
    """在 n 范围内选使价值/预算最接近 1.03 的整数 n；返回 (n, V, ratio) 或 (None, V, ratio)"""
    nr = sp["nr"]
    if nr is None:
        V = sp["vf"](0)
        return None, V, V / B
    best = None
    for n in range(nr[0], nr[1] + 1):
        V = sp["vf"](n)
        r = V / B
        if UNDER <= r <= OVER and (best is None or abs(r - 1.03) < abs(best[2] - 1.03)):
            best = (n, V, r)
    if best:
        return best
    # 没有整数满足区间：取最接近的并标记
    cand = [(n, sp["vf"](n), sp["vf"](n) / B) for n in range(nr[0], nr[1] + 1)]
    return min(cand, key=lambda x: abs(x[2] - 1.03))


def mod_budget(sp, fp, sup):
    c = sp["cost"]
    if sp["mode"] == "cond":
        base = COND_BASE
    else:
        base = base_budget(c) + (EX_BONUS if sp["mode"] == "exhaust" else 0)
    return base + fp + sup


def build_modules():
    # 供能与形状
    counters = {}
    mods = []
    for sp in MODS:
        sp["shape"] = MA.pick_shape(dict(type=sp["type"], size=sp["size"]), counters)
        mods.append(dict(name=sp["name"], size=sp["size"], type=sp["type"], card=sp["tmpl"].format(n=5, u=2, m=7), limit=sp["limit"], lean=sp["lean"],
                         cost=sp["cost"], ult=sp["ult"], facing=sp["facing"]))
    quality = {}
    for m, sp in zip(mods, MODS):
        q = 0
        if sp["up"][0] == "机制核心":
            q += 3
        if MA.STRONG_ULT.search(m["ult"]):
            q += 2
        if sp["size"] >= 5:
            q += 1
        if sp["lean"] == "卡强":
            q += 1
        if sp["cost"] >= 2:
            q += 1
        if sp["size"] == 6:
            q += 1
        q += (sum(map(ord, sp["name"])) % 7) / 10.0
        quality[sp["name"]] = q
    ad = PS.assign_supply(mods, quality)
    out = []
    for sp in MODS:
        a, d, tier = ad[sp["name"]]
        fp = footprint(sp["size"], sp["shape"])
        sup = SUP_E * (a + d)
        B = mod_budget(sp, fp, sup)
        n, V, r = tune(sp, B, "mod")
        text = sp["tmpl"].format(n=n) if n is not None else sp["tmpl"]
        if n is None and r < UNDER:
            k = max(1, round((B - V) * 6))
            text += f"；护盾 +{k}"
            V += k / 6.0
            r = V / B
        u = None
        if n is not None:
            u = max(1, min(n - 1, round(n * sp["uk"]))) if n > 1 else 1
        ult = sp["ult"].format(u=u if u is not None else 1)
        # 升级
        ut, utmpl = sp["up"]
        m_up = None
        if n is not None:
            m_up = int(math.ceil(n * 1.35)) + (1 if n <= 3 else 0)
        up_cost = sp["cost"]
        if ut == "降费":
            up_cost = max(1, sp["cost"] - 1)
            up_text = text if sp["mode"] != "cond" else "条件减费额外 -1：" + text
        elif utmpl:
            up_text = utmpl.format(n=m_up if m_up is not None else 0, m=m_up if m_up is not None else 0)
        else:
            up_text = sp["tmpl"].format(n=m_up)
        if ut == "机制核心":
            assert sp["size"] >= 4
        out.append(dict(name=sp["name"], size=sp["size"], major=sp["major"], type=sp["type"], pool=sp["pool"], limit=sp["limit"], shape=sp["shape"],
                        cost=sp["cost"], text=text, ult=ult, facing=sp["facing"], A=a, D=d, tier=tier, ratio=round(r, 3), utype=ut, up_cost=up_cost,
                        up_text=up_text, mech=sp["mech"], mode=sp["mode"], n=n, budget=round(B, 3), value=round(V, 3), lean=sp["lean"]))
    return out


def build_implants():
    out = []
    for sp in IMPS:
        c = sp["cost"]
        if sp["mode"] == "cond":
            base = COND_BASE
        else:
            base = base_budget(c) + (EX_BONUS if sp["mode"] == "exhaust" else 0)
        if sp["part"] == "手":
            base += 0.04 * sum(sp["wo"])
        if sp["part"] in ("脑", "躯"):
            base += sp["pe"]
        n, V, r = tune(sp, base, "imp") if sp["nr"] is not None else (None, sp["vf"](0), sp["vf"](0) / base)
        if sp["nr"] is None:
            n = None
        text = sp["tmpl"].format(n=n) if n is not None else sp["tmpl"]
        if n is None and sp["nr"] is None and r < UNDER:
            k = max(1, round((base - V) * 6))
            text += f"；护盾 +{k}"
            V += k / 6.0
            r = V / base
        # 升级：数值 +35%（取整）或降费
        up_text, ut = None, "数值"
        if n is not None:
            m = int(math.ceil(n * 1.35)) + (1 if n <= 3 else 0)
            up_text = sp["tmpl"].format(n=m)
        else:
            ut = "追加"
            up_text = text + "；抽 1 张"
        up_cost = c
        if c >= 2 and sp["mode"] != "cond" and sp["mech"] in ("重击", "衍生·消耗", "护盾", "护盾保留", "多段"):
            ut = "降费"
            up_cost = c - 1
            up_text = text
        out.append(dict(part=sp["part"], name=sp["name"], cost=c, text=text, passive=sp["passive"] or "", wo=("%d/%d" % sp["wo"]) if sp["wo"] else "",
                        mech=sp["mech"], utype=ut, up_cost=up_cost, up_text=up_text, ratio=round(r, 3), mode=sp["mode"], n=n, budget=round(base, 3), value=round(V, 3), pe=sp["pe"]))
    return out


if __name__ == "__main__":
    mods = build_modules()
    imps = build_implants()
    json.dump(dict(mods=mods, imps=imps, tokens=TOKENS), open(os.path.join(os.path.dirname(__file__), "new_cards_v028.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    print("模块", len(mods), "义体", len(imps), "副产品", len(TOKENS))
    bad = [(m["name"], m["ratio"], m["text"][:30]) for m in mods if not (UNDER <= m["ratio"] <= OVER)]
    print("模块越界", bad)
    bad = [(m["name"], m["ratio"], m["text"][:30]) for m in imps if not (UNDER <= m["ratio"] <= OVER)]
    print("义体越界", bad)
    print("模块费用", sorted(Counter(m["cost"] for m in mods).items()), "供能", Counter(m["tier"] for m in mods))
    print("义体费用", sorted(Counter(m["cost"] for m in imps).items()))
    print("升级类型", Counter(m["utype"] for m in mods), "机制核心", [m["name"] for m in mods if m["utype"] == "机制核心"])
