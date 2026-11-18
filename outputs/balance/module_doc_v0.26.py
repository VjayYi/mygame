# -*- coding: utf-8 -*-
import json, re, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from collections import Counter, defaultdict
from card_value_engine import SHAPES, footprint, UNDER, OVER

rows = json.load(open(os.path.join(os.path.dirname(__file__), "module_audit_v0.26.json"), encoding="utf-8"))
UNLOCK = json.load(open(os.path.join(os.path.dirname(__file__), "module_unlock_v0.27.json"), encoding="utf-8"))
OUT = os.path.join(os.path.dirname(__file__), "..", "combat-module-catalog-v0.26-modules-rebalanced.md")

# 通用模块来源（基地 / 怪物产出）
src = {}
mode = None
for ln in open(os.path.join(os.path.dirname(__file__), "..", "combat-module-catalog-v0.25-weapon-exclusive-modules.md"), encoding="utf-8"):
    if ln.startswith("### 1.2"): mode = "近战"
    elif ln.startswith("### 1.3"): mode = "远程"
    elif ln.startswith("## 2."): mode = None
    if mode and ln.startswith("|"):
        c = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(c) == 3 and re.match(r"\d 格", c[0]):
            for n in c[1].split("、"): src[n] = "基地"
            for n in c[2].split("、"): src[n] = "怪物产出"

TAG = {"保持": "不变", "亏模，数值上调": "数值↑", "亏模，补助效果": "补助", "亏模，费用-1": "费↓", "亏模，费用-1并补助": "费↓+补助",
       "亏模，费用-2并补助": "费↓↓+补助", "手工重设（大块强化）": "大块重做", "补助效果": "补助", "升至1费": "升至1费", "超模削减": "数值↓"}

def cost_s(r):
    return f"{r['cost']}" if r['cost'] == r['new_cost'] else f"{r['cost']}→**{r['new_cost']}**"

def up_s(r):
    t = r["up_text"] or "—"
    if r["up_cost"] != r["new_cost"]:
        t = f"（费用{r['new_cost']}→**{r['up_cost']}**）" + (t if t != r["new_text"] else "效果不变")
    return f"【{r['utype']}】{t}"

def table(rs):
    out = ["| 名称 | 格·形状 | 供能 攻/防·档 | 类型 | 费用 | 卡效果（新） | 升级后 | 终极效果（新） | 朝向 | 调整 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(rs, key=lambda x: (x["size"], 0)):
        lk = f"；**需成就：{UNLOCK[r['name']]}**" if r["name"] in UNLOCK else ""
        out.append(f"| {r['name']} | {r['size']}·{r['shape']} | {r['A']}/{r['D']}·{r['supply_tier']} | {r['type']} | {cost_s(r)} | {r['new_text']} | {up_s(r)} | {r['new_ult']} | {r['facing']} | {TAG.get(r['status'], r['status'])}{lk} |")
    return "\n".join(out)

gen = [r for r in rows if r["origin"] == "通用"]
for r in gen: r["src"] = src.get(r["name"], "基地")
L = []
L.append("# 模块目录 v0.26（修订 3）：按新预算模型重算（6 伤/费、6 盾/费 + 占模补偿 + 升级）\n")
L.append("> 状态：草案，供评审。全部 190 个模块（184 个原有 + 6 个新增洗牌/冷却类）的费用、卡效果、终极数值按 v0.26 预算模型重新核算并**直接调整**；名称、倾向、终极机制文字、朝向沿用 v0.22/v0.25。预算规则见 `combat-budget-v0.26-model.md`。\n")
L.append("**修订 1（2026-11-18 11:30，你的新要求）**：①0 费模块砍到 **15 个**，且全部是 2 格，其余一律最低 1 费，原来偏便宜的模块改为 1 费后用护盾/抽牌补足预算，**升级后才可能变 0 费**；②新增 6 个洗牌/冷却类模块（见第 4 节），全部 4 格以上；③升级不再只有数值：新增「两段」「持续」「降费」「机制核心」类型，机制核心占 10%，全部 4 格及以上。\n")
L.append("**修订 2（2026-11-18 11:50）**：①**矛盾词条已修**：卡自身没有伤害来源、效果却依赖“本卡伤害/击杀/命中”的 9 个模块（吸血、拾荒、余烬、嗜血回流、脉冲刃格、血契爪痕、战术核心、瞬息步、跳弹）改成“**本回合**”范围的持续触发，靠其他攻击牌触发；没有自身伤害的 5 个增益卡（连斩、连射、狙击校准、跳弹、倒刺垦）去掉“朝向”。②**终极效果补了数值**：机制很强的（必定击晕、回手、无视护盾、多段、洗牌、冷却、终极卡降费等）不补，机制一般的补一点（朝向“是”补伤害，“否”补护盾，状态类补层数），**加粗**部分就是本次新增，补数值 %d 个、原来就有数值 %d 个、强机制免补 %d 个。\n" % (sum(1 for r in rows if r.get("ult_class") == "补数值"), sum(1 for r in rows if r.get("ult_class") == "已有数值"), sum(1 for r in rows if r.get("ult_class") == "强机制免补")))
L.append("**修订 3（2026-11-18 13:10）**：①每个模块新增 **供能 攻/防** 列（攻击供能需求 / 防御供能需求），规则见 `combat-power-allocation-v0.27.md`，并计入预算（每点供能需求 −0.02E 的占模负担，190 个模块重新核算后全部仍在 85%～120% 内）；②**取消成就币**，改为“基地池 5～6 格模块约一半用成就直接解锁”，共 30 个，条件写在「调整」列里（**需成就：…**）。\n")
L.append("**修订 4（2026-11-18 13:50）**：供能参数**整体重新分布**：约一半模块是“一半一半”（均衡），≈25% 偏攻、≈16% 偏防、≈10% 极端（攻/防各约一半，只给 4 格以上、效果突出的卡）；攻击卡不再默认攻高、防御/功能卡不再默认防高。随机搭配的终极门槛均值从约 79% 降到约 64%。详见 `combat-power-allocation-v0.27.md`。\n")
L.append("**怎么读**：费用列 `旧→**新**` 表示费用有调整；「调整」列：数值↑ = 卡面数值上调以对齐新锚点；费↓ = 原费用相对效果偏贵，降费；补助 = 原效果亏模，补了一条小效果；大块重做 = 5～6 格弱机制模块手工加强（越大越难拼越强）。")
L.append("形状为**候选**（按类型分配：防御/回复/能源/过牌=紧凑易拼；伤害/距离=长条；状态/控制/节奏/特殊等=不规则难拼），最终拼图轮廓等美术阶段再定。\n")
cc0 = Counter(r["cost"] for r in rows); cc1 = Counter(r["new_cost"] for r in rows)
L.append("## 0. 核算结果\n")
L.append("| | 旧 v0.22/v0.25 | 新 v0.26 |\n|---|---|---|")
in0 = sum(1 for r in rows if UNDER <= r["r0"] <= OVER); in1 = sum(1 for r in rows if UNDER <= r["r1"] <= OVER)
L.append(f"| 落在 85%～120% 预算内 | {in0} / 190 | {in1} / 190 |")
L.append(f"| 亏模（<85%） | {sum(1 for r in rows if r['r0']<UNDER)} | {sum(1 for r in rows if r['r1']<UNDER)} |")
L.append(f"| 超模（>120%） | {sum(1 for r in rows if r['r0']>OVER)} | {sum(1 for r in rows if r['r1']>OVER)} |")
L.append(f"| 0 / 1 / 2 / 3 费数量 | {cc0[0]} / {cc0[1]} / {cc0[2]} / {cc0[3]} | {cc1[0]} / {cc1[1]} / {cc1[2]} / {cc1[3]} |")
st = Counter(TAG.get(r["status"], r["status"]) for r in rows)
L.append("\n调整类型分布：" + "，".join(f"{k} {v}" for k, v in st.most_common()) + "。\n")
L.append("**结论**：旧数值按 4.5 伤/费、5 盾/费定，换成 6/6 后几乎全部亏模（190 个里只有 %d 个落在区间内），所以这次是**整体上调**：纯数值模块按预算放大；机制型模块不再靠“降到 0 费”补预算（0 费被限制在 15 个 2 格模块），改为保持 1 费并补一条小效果/护盾。5～6 格大块弱机制模块在占模补偿下尤其亏，手工做了加强。没有模块超模，因此本轮没有触发“削减、余量放升级”。\n" % in0)
L.append("**风险提示**：（1）升级成 0 费的卡 %d 张（含能源/抽牌的已排除），建议约定：升级成 0 费的卡若带资源效果，只生效“每回合第一次”；（2）整体伤害上调约 +30%%～+100%%，怪物生命/伤害需要按预算模型文档第 7 节重校；（3）机制核心 19 个与洗牌/冷却 6 个的价值是手估，需要逐卡模拟。\n" % sum(1 for r in rows if r["utype"] == "降费" and r["up_cost"] == 0))

def sec(title, rs):
    L.append(f"### {title}（{len(rs)}）\n")
    L.append(table(rs) + "\n")

L.append("## 1. 通用模块 · 基地直接改装（38）\n")
for m in ("近战", "远程"):
    sec(m, [r for r in gen if r["major"] == m and r["src"] == "基地"])
L.append("## 2. 通用模块 · 怪物产出（38，精英/小Boss 掉落）\n")
for m in ("近战", "远程"):
    sec(m, [r for r in gen if r["major"] == m and r["src"] == "怪物产出"])
L.append("## 3. 品类限定模块 · 基地直接改装（108）\n")
for cat in ["刀", "剑", "爪", "斧", "拳套", "步枪", "炮筒", "手枪", "弓"]:
    sec(cat, [r for r in rows if r["origin"] == "品类限定" and r["limit"] == cat])
L.append("## 4. 新增：洗牌 / 冷却类模块（6，全部 4 格及以上，建议只放怪物产出）\n")
L.append("**关键词**：**洗回牌库** = 把弃牌堆全部洗回牌库（价值 0.6E，因为 10 张左右的牌组里洗牌会直接提升下一轮抽到强牌的概率）；**冷却 N 回合** = 本卡打出后移出战斗，N 回合后回到手牌（不占用洗牌循环，预算按 +0.25E×N 加成）。洗牌是“占模的东西”：必须占 4 格以上，且每把武器最多装 1～2 个。远程武器“补充弹药/冷却”的主题落在这两类：弹匣重装、全弹补给是**装填**，过载冷却、重炮冷凝是**冷却**。\n")
sec("新增洗牌 / 冷却类", [r for r in rows if r["origin"] == "洗牌冷却"])
L.append("## 5. 升级类型速查\n")
from collections import Counter as _C
_ut = _C(r["utype"] for r in rows)
L.append("| 类型 | 做法 | 数量 |\n|---|---|---|")
for k, d in [("数值", "伤害/护盾/状态层数等数字上调"), ("两段", "单次伤害变成 2 段结算（每段 0.75 倍，总量约 ×1.5，可分别触发效果）"), ("持续", "“下一张”变成“接下来 2 张”，“下回合”变成“接下来 2 回合”"), ("降费", "升级后费用 −1；原来偏便宜、被抬到 1 费的模块多数在升级后变 0 费"), ("追加", "没有可放大的数字时追加抽牌/护盾"), ("机制核心", "升级后获得一条改变玩法的机制，成为流派核心；只给 4 格及以上模块，占比 10%")]:
    L.append(f"| {k} | {d} | {_ut.get(k, 0)} |")
L.append("")
L.append("## 6. 占模补偿速查\n")
L.append("占模补偿（E，价值单位=1费）= 0.06×(格数−2) + 0.02×(重量+操作) + 0.04×形状难拼度×(格数−2)；重量/操作按格数取默认（2格1/0，3格1/1，4格2/1，5格4/3，6格5/4）。\n")
L.append("| 格数 | 易拼形状补偿 | 中等形状补偿 | 难拼形状补偿 |\n|---|---|---|---|")
for sz, shp in [(2, ("直2", "直2", "直2")), (3, ("直3", "弯3", "弯3")), (4, ("直4", "T4", "Z4")), (5, ("直5", "T5", "W5")), (6, ("矩6", "T6", "U6"))]:
    L.append(f"| {sz} | {footprint(sz, shp[0]):.2f} | {footprint(sz, shp[1]):.2f} | {footprint(sz, shp[2]):.2f} |")
open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("written", len("\n".join(L)))
