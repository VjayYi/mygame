# -*- coding: utf-8 -*-
"""模块审计与调整 v0.26：把 184 个模块套进新预算模型（6伤/费、6盾/费，+20%容差，占模补偿，升级）"""
import re, json, os, sys, math
sys.path.insert(0, os.path.dirname(__file__))
from card_value_engine import *
import power_supply_v027 as PS
SUPPLY_E = 0.02  # 每点供能需求的占模负担（E）

# 引擎解析不了的机制类，手工给"卡效果总价值 E"（逐条按 v0.26 锚点估）
MECH = {
    "吸血": 0.30, "充能刃": 0.50, "余烬": 0.60, "献祭刃": 0.60, "复刻": 0.50, "守势": 0.35,
    "连斩": 0.40, "战意": 0.50, "速射": 0.80, "弹道标记": 0.50, "三连发": 0.70, "连射": 0.40,
    "复装": 0.40, "跳弹": 0.60, "过热散热": 0.45, "血刃祭坛": 0.70, "架势延伸": 0.40,
    "连剑连携": 0.85, "震颤屏息": 0.35, "拳意回响": 0.50, "狂拳连击": 0.75, "双枪连射": 0.70,
    "弹药拆解": 0.80, "弹匣拆解": 0.80, "猎杀标记": 0.35, "百步穿杨": 1.90, "三段连发": 0.67,
    "镜甲扣": 0.40, "全自动模式": 1.30, "崩岳连拳": 1.30, "回旋斩": 0.95, "连击拳": 0.60,
}

# 0 费白名单（修订1：0费模块控制在 15 个，且全部是 2 格；其余一律最低 1 费，升级后才可能变 0 费）
ZERO_OK = {"护刃", "拾荒", "瞄准镜", "消音器", "轻装甲", "保险丝", "磨刃鞘", "镜甲扣", "倒刺垦", "配重垛",
           "护拳垫", "轻型握把", "稳定支架", "快拔皮套", "轻量弓臂"}

ZERO_UP_TYPES = {"控制", "状态", "节奏", "加速", "保留", "标记", "特殊", "陷阱", "复刻", "献祭", "防御", "回复"}

# 新增：洗牌（弃牌堆洗回牌库）与冷却类模块。全部 4 格及以上（占模），建议只放怪物产出池
NEW_MODS = [
    dict(name="回炉重铸", size=4, type="特殊", lean="终强", cost=1, card="将弃牌堆洗回牌库；抽 1 张",
         ult="打出终极卡后，将弃牌堆洗回牌库（本场 1 次）", facing="否", limit="—", major="近战", origin="洗牌冷却", src="怪物产出"),
    dict(name="磨砺轮转", size=5, type="特殊", lean="终强", cost=2, card="将弃牌堆洗回牌库；抽 2 张；本回合下一张攻击 +7",
         ult="打出终极卡后，本回合已打出的牌（不含终极卡）洗回牌库", facing="否", limit="—", major="近战", origin="洗牌冷却", src="怪物产出"),
    dict(name="过载冷却", size=5, type="特殊", lean="卡强", cost=1, card="本卡冷却 2 回合（打出后移出战斗，2 回合后回到手牌）；伤害 +12",
         ult="终极卡冷却 2 回合，回到手牌时伤害 +4", facing="是", limit="—", major="近战", origin="洗牌冷却", src="怪物产出"),
    dict(name="弹匣重装", size=4, type="特殊", lean="终强", cost=1, card="将弃牌堆洗回牌库；下一张攻击 +5",
         ult="打出终极卡后，抽 1 张并将弃牌堆洗回牌库（本场 1 次）", facing="否", limit="—", major="远程", origin="洗牌冷却", src="怪物产出"),
    dict(name="全弹补给", size=5, type="特殊", lean="终强", cost=2, card="将弃牌堆洗回牌库；本回合能源 +1；抽 2 张",
         ult="终极卡费用 -1；打出终极卡后弃牌堆洗回牌库（本场 1 次）", facing="否", limit="—", major="远程", origin="洗牌冷却", src="怪物产出"),
    dict(name="重炮冷凝", size=6, type="特殊", lean="卡强", cost=2, card="本卡冷却 2 回合（打出后移出战斗，2 回合后回到手牌）；伤害 +17",
         ult="终极卡冷却 2 回合，回到手牌时伤害 +6", facing="是", limit="—", major="远程", origin="洗牌冷却", src="怪物产出"),
]

# 修订2：矛盾词条修复。卡本身没有伤害来源，却依赖“本卡伤害/击杀/命中”的，改成“本回合”范围的持续型触发，
# 这样靠别的攻击牌触发；没有自身伤害的纯增益/附带卡去掉“朝向”。
FIX_CARD = {
    "吸血": "本回合你造成伤害的 25% 回复生命",
    "拾荒": "本回合击杀敌人时抽 1 张",
    "余烬": "本回合击杀敌人时返还 2 能源",
    "嗜血回流": "本回合击杀敌人时回复 3 生命",
    "脉冲刃格": "本回合你的攻击命中流血目标时回复 1 能源（本回合上限 1）",
    "血契爪痕": "本回合你的攻击命中异常状态目标时回复 2 生命",
    "战术核心": "本回合能源+2；本回合你的攻击命中 2 名以上敌人时额外回复 1 能源（本回合上限 1）",
    "瞬息步": "本回合你的攻击命中后回复 1 能源（本回合上限 1）",
    "跳弹": "本回合你的攻击打在护盾为 0 的目标上时，弹射另一名敌人，伤害 50%",
}
FIX_FACING_NO = {"连斩", "连射", "狙击校准", "跳弹", "倒刺垦"}

# 终极数值（修订2）：机制比较一般的终极效果补一点数值；机制很强的不补
STRONG_ULT = re.compile(r"必定|回到手牌|无视护盾|先移除|终极卡费用\s*-1|费用\s*-1（最低|费用变为 0|费用为0|费用为 0|结算两次|分\s*[3-5]\s*段|N 段|穿透身后所有|不再随回合衰减|持续到死亡|洗回牌库|转移|能源上限|冷却|打断|额外结算 X|额外结算X|牌库")
ULT_HAS_NUM = re.compile(r"(?:伤害|护盾|攻击|流血|中毒|灼烧|层数)\s*[+＋]\s*\d|回复\s*\d+\s*生命|\d+\s*伤害|\d+\s*护盾|各\s*-\d|额外\s*[-+]?\s*\d|(?:敌人|目标)\s*\+\d|伤害\s*=|×\s*\d")


def add_ult_numeric(mod, r):
    u = r["new_ult"]
    if ULT_HAS_NUM.search(u):
        return u, "已有数值"
    if STRONG_ULT.search(u) or mod["name"] in CORE:
        return u, "强机制免补"
    e_add = min(0.8, max(0.17, 0.22 * r["v1"]))
    x = max(1, round(e_add * 6))
    n = main_num(r["new_text"])
    if n and x >= n:
        x = max(1, n - 1)
    if mod["type"] == "状态":
        dot = "中毒" if "中毒" in mod["card"] else "灼烧" if "灼烧" in mod["card"] else "流血"
        k = max(1, round(e_add / DOT_E))
        return u.rstrip("。") + f"；**{dot} +{k}**", "补数值"
    kind = "伤害" if mod["facing"] == "是" else "护盾"
    return u.rstrip("。") + f"；**{kind} +{x}**", "补数值"


# 机制核心型升级（修订1：占比 ≈10%，必须 4 格及以上）：升级后额外获得一条改变玩法的机制，追加在新卡效果之后
CORE = {
    "献祭刃": "【核心·盾刃】消耗全部护盾造成等量伤害，并把消耗量的 50% 作为下回合护盾返还",
    "毒刃": "【核心·毒爆】中毒不再每回合衰减；回合结束时对全体敌人各造成其中毒层数一半的伤害",
    "复刻": "【核心·复刻】本回合每张攻击牌（不再限首张）效果各再结算 50%（不能复刻复刻）",
    "守势": "【核心·保留】保留的每张防御牌护盾 +3，且可保留任意回合",
    "循环斩": "【核心·洗手】弃掉全部手牌后抽等量 +1 张，并将弃牌堆洗回牌库（本场 1 次）",
    "余烬": "【核心·击杀】击杀敌人时本卡回到手牌（每回合 1 次）",
    "战意": "【核心·受击】本回合每受到 1 次伤害，本回合所有攻击各 +1（不再只加下一张）",
    "惯性切斩": "【核心·连击】本回合每连续打出 1 张攻击牌，之后的攻击 +2 递增（打出非攻击牌清零）",
    "连斩": "【核心·连斩】本回合每次攻击后，下一次攻击 +3（可叠加，上限 +12）",
    "三连发": "【核心·速射】本回合每已打出 1 张攻击牌，本卡多结算 1 段（至多 3 段，每段为本卡伤害的一半）",
    "连射": "【核心·连射】叠加的攻击加成延续到下回合（不清零，上限 +6）",
    "跳弹": "【核心·跳弹】弹射次数不限，每次弹射伤害递减 20%（不会弹回同一目标）",
    "连锁引线": "【核心·连锁】击杀连锁可无限传递，每次传递伤害 +2",
    "弹药拆解": "【核心·拆解】消耗的每张手牌使本卡额外结算 1 段（至多 3 段）",
    "血刃祭坛": "【核心·血祭】消耗流血后，对目标重新附加其中 50% 的流血",
    "噬魂爪": "【核心·噬魂】击杀异常状态目标时本卡回到手牌，本回合下一张爪牌费用 -1",
    "崩岳连拳": "【核心·多段】每一段独立计为一次拳套攻击（可触发连打连锁、拳意回响等）",
    "山崩斧意": "【核心·群斩】命中 3 名以上敌人时本卡回到手牌（每回合 1 次）",
    "连环处决": "【核心·处决】击杀时本卡回到手牌且费用 -1（每回合 1 次）",
}

# 大块弱机制模块：手工重设（名称 -> (费用, 新卡效果)），体现"越大越难拼越强"
MANUAL = {
    "战术速写": (1, "抽 1 张，弃 1 张；护盾 +2"),
    "守势": (1, "本回合未打出的防御牌保留到下回合；护盾 +3"),
    "连斩": (1, "本回合第 2 次攻击 +6；护盾 +3"),
    "侦测扫描": (1, "抽 2 张；护盾 +1"),
    "连锁引线": (1, "伤害 +6；攻击击杀目标时，相邻敌人受 6 伤害"),
    "震颤屏息": (1, "本回合未打出的防御牌保留到下回合；护盾 +5；下一张剑攻击 +2"),
    "千锤拳意": (1, "每打出1张拳套攻击牌，下一张费用-1（可叠加，最低0）；护盾 +6"),
    "连锁殉爆": (1, "伤害 +6；击杀目标时相邻敌人受 6 伤害"),
    "快速装填": (1, "抽 1 张；护盾 +2"),
    "过热散热": (1, "本回合攻击费用 -1；护盾 +5；下回合攻击 -2"),
    "压制火力": (1, "目标下回合攻击-2；护盾 +6"),
}

# 形状候选（按类型分调色板，同尺寸内按出现顺序轮换）
COMPACT = {2: ["直2"], 3: ["弯3", "直3"], 4: ["方4", "L4"], 5: ["P5", "L5"], 6: ["矩6"]}
LONG = {2: ["直2"], 3: ["直3", "弯3"], 4: ["直4", "L4"], 5: ["直5", "L5", "P5"], 6: ["矩6", "L6"]}
IRREG = {2: ["直2"], 3: ["弯3"], 4: ["T4", "Z4"], 5: ["T5", "Z5", "U5", "W5", "十5"], 6: ["T6", "U6", "阶6", "L6"]}
COMPACT_TYPES = {"防御", "回复", "能源", "过牌", "辅助"}
LONG_TYPES = {"伤害", "距离"}


def pick_shape(mod, counters):
    t = mod["type"]
    pal = COMPACT if t in COMPACT_TYPES else LONG if t in LONG_TYPES else IRREG
    key = (t in COMPACT_TYPES, t in LONG_TYPES, mod["size"])
    i = counters.get(key, 0)
    counters[key] = i + 1
    lst = pal[mod["size"]]
    return lst[i % len(lst)]


NUM_PATS = [r"(伤害\s*\+)(\d+)", r"(护盾\s*\+)(\d+)", r"((?:所有|全体)敌人各\s*-?)(\d+)", r"(随机(?:两|2)名敌人各\s*-?)(\d+)",
            r"(附加(?:流血|中毒|灼烧)\s*)(\d+)"]


def scale_text(text, f):
    """按系数 f 缩放文本中的 伤害+N / 护盾+N / 群体-N（每类只缩放该类首个出现，且取整≥1）"""
    out = text
    for pat in NUM_PATS:
        def rep(m):
            n = max(1, int(round(int(m.group(2)) * f)))
            return m.group(1) + str(n)
        out = re.sub(pat, rep, out, count=1)
    return out


def has_scalable(text):
    return any(re.search(p, text) for p in NUM_PATS)


def eng(text):
    return card_value(text)[0]


def total_v(mod, text):
    base = MECH.get(mod["name"])
    if base is None:
        return eng(text)
    return base + (eng(text) - eng(mod["card"]))


def main_num(text):
    m = re.search(r"(?:伤害|护盾)\s*\+(\d+)", text)
    return int(m.group(1)) if m else None


def ult_scale(ult, old_card, new_card):
    """终极文本里的 伤害/护盾 +N 随卡效果同比缩放，且终极数值必须严格小于卡数值"""
    o, n = main_num(old_card), main_num(new_card)
    if not o or not n or o == n:
        return ult
    f = n / o

    def rep(m):
        v = max(1, int(round(int(m.group(2)) * f)))
        if v >= n:
            v = max(1, n - 1)
        return m.group(1) + str(v)
    return re.sub(r"^((?:伤害|护盾)\s*\+)(\d+)", rep, ult, count=1)


COMP_BY_TYPE = {"防御": "shield", "回复": "shield", "控制": "shield", "辅助": "shield"}


def cd_bonus(text):
    m = re.search(r"冷却\s*(\d)\s*回合", text)
    return 0.25 * int(m.group(1)) if m else 0.0


def top_up(mod, text, b, target=0.97):
    """价值不足时用护盾补足到 target×预算"""
    v = total_v(mod, text)
    if v >= UNDER * b:
        return text
    need = max(1, round((target * b - v) * SHD_PER_E))
    m = re.search(r"护盾\s*\+(\d+)", text)
    if m:
        return text.replace(m.group(0), f"护盾 +{int(m.group(1)) + need}", 1)
    return text + f"；护盾 +{need}"


def compensate(mod, text, gap_e):
    """亏模补助：先补一个小效果，再用护盾补足"""
    m = re.search(r"抽\s*(\d+)\s*张", text)
    if m and gap_e >= 0.38:
        n = int(m.group(1))
        return text.replace(m.group(0), f"抽 {n + 1} 张", 1)
    t = mod["type"]
    if gap_e >= 0.38 and t not in ("防御", "回复"):
        return text + "；抽 1 张"
    return text


def adjust(mod, shape):
    size, cost0, text = mod["size"], mod["cost"], mod["card"]
    nm = mod["name"]
    minc = 0 if nm in ZERO_OK else 1
    cost = max(cost0, minc)
    fp = footprint(size, shape) + SUPPLY_E * (mod["A"] + mod["D"])
    cdb = cd_bonus(text)
    v0 = total_v(mod, text)
    b = base_budget(cost) + fp + cdb
    r0_old = v0 / (base_budget(cost0) + fp + cdb)
    res = dict(v0=v0, b0=b, r0=r0_old, fp=fp)
    new_cost, new_text, status = cost, text, "保持"
    if nm in MANUAL:
        new_cost, new_text = max(MANUAL[nm][0], minc), MANUAL[nm][1]
        status = "手工重设（大块强化）"
    elif UNDER <= v0 / b <= OVER:
        status = "保持" if cost == cost0 else "升至1费"
    elif v0 / b > OVER:
        if has_scalable(text):
            target = 1.10 * b
            best = None
            for f in [x / 100 for x in range(20, 100)]:
                t2 = scale_text(text, f)
                v2 = total_v(mod, t2)
                if v2 <= 1.15 * b and (best is None or abs(v2 - target) < abs(best[0] - target)):
                    best = (v2, t2)
            if best:
                new_text, status = best[1], "超模削减"
            else:
                new_cost, status = min(3, cost + 1), "超模，费用+1"
        elif cost < 3:
            new_cost, status = cost + 1, "超模，费用+1"
    else:
        if has_scalable(text):
            best = None
            for f in [x / 100 for x in range(100, 600, 2)]:
                t2 = scale_text(text, f)
                v2 = total_v(mod, t2)
                if v2 >= UNDER * b and (best is None or abs(v2 - b) < abs(best[0] - b)):
                    best = (v2, t2)
                if v2 > OVER * b:
                    break
            if best:
                new_text, status = best[1], "亏模，数值上调"
        else:
            chosen = None
            for c in range(cost, minc - 1, -1):
                if UNDER <= v0 / (base_budget(c) + fp + cdb) <= OVER:
                    chosen = c
                    break
            if chosen is not None and chosen != cost:
                new_cost, status = chosen, "亏模，费用-%d" % (cost - chosen)
            elif chosen is None:
                c = cost
                while c > minc and v0 / (base_budget(c - 1) + fp + cdb) <= OVER:
                    c -= 1
                new_cost = c
                new_text = compensate(mod, text, base_budget(c) + fp + cdb - v0)
                status = "亏模，费用-%d并补助" % (cost - c) if c != cost else "亏模，补助效果"
    bb = base_budget(new_cost) + fp + cdb
    new_text = top_up(mod, new_text, bb)
    if new_text != text and status == "保持":
        status = "补助效果"
    v1 = total_v(mod, new_text)
    res.update(v1=v1, b1=bb, r1=v1 / bb, status=status, new_cost=new_cost, new_text=new_text, shape=shape,
               new_ult=ult_scale(mod["ult"], text, new_text))
    return res


def up_numeric(mod, new_text, v1, b1):
    if has_scalable(new_text):
        target = min(1.35 * v1, 1.55 * b1)
        best = None
        for f in [x / 100 for x in range(100, 500, 2)]:
            t2 = scale_text(new_text, f)
            v2 = total_v(mod, t2)
            if v2 <= 1.55 * b1 and (best is None or abs(v2 - target) < abs(best[0] - target)):
                best = (v2, t2)
        if best and best[1] != new_text:
            return best[1]
    if "抽" in new_text and re.search(r"抽\s*\d+\s*张", new_text):
        m = re.search(r"抽\s*(\d+)\s*张", new_text)
        return new_text.replace(m.group(0), f"抽 {int(m.group(1)) + 1} 张", 1)
    return new_text + "；护盾 +3"


P_NEXT = re.compile(r"下一张(\S{0,2}?)(攻击|牌伤害)\s*\+(\d+)")
P_NEXTFEE = re.compile(r"下一张(\S{0,3}?牌)费用\s*-1")
P_RETURN = re.compile(r"下回合首次攻击\s*\+(\d+)")


def upgrade(mod, r, ctr):
    """返回 (类型, 升级后费用, 升级后卡效果)。类型：机制核心 / 持续 / 两段 / 降费 / 数值 / 追加"""
    nm, t, c = mod["name"], r["new_text"], r["new_cost"]
    if nm in CORE:
        assert mod["size"] >= 4, nm
        return "机制核心", c, t + "；" + CORE[nm]
    m = P_NEXT.search(t)
    if m:
        return "持续", c, P_NEXT.sub(lambda x: f"接下来 2 张{x.group(1)}{x.group(2)}各 +{x.group(3)}", t, 1)
    if P_RETURN.search(t):
        return "持续", c, P_RETURN.sub(lambda x: f"接下来 2 回合每回合首次攻击 +{x.group(1)}", t, 1)
    if P_NEXTFEE.search(t):
        return "持续", c, P_NEXTFEE.sub(lambda x: f"接下来 2 张{x.group(1)}费用各 -1", t, 1)
    forced = mod["cost"] == 0 and nm not in ZERO_OK
    if forced and c >= 1 and "能源" not in t:
        return "降费", c - 1, t
    if c == 1 and mod["type"] in ZERO_UP_TYPES and "能源" not in t and "抽" not in t:
        ctr["z"] = ctr.get("z", 0) + 1
        if ctr["z"] % 2 == 1:
            return "降费", 0, t
    dm = re.match(r"^伤害\s*\+(\d+)", t)
    if dm and not re.search(r"全体|所有|随机|段|1 号位|范围|前后", t):
        ctr["d"] = ctr.get("d", 0) + 1
        k = ctr["d"] % 3
        if k == 0:
            x = math.ceil(int(dm.group(1)) * 0.75)
            return "两段", c, re.sub(r"^伤害\s*\+\d+", f"伤害 +{x} ×2 段（每段独立结算）", t, count=1)
        if k == 1 and c >= 2:
            return "降费", c - 1, t
    if c >= 2 and "能源" not in t and not has_scalable(t):
        return "降费", c - 1, t
    ut = up_numeric(mod, t, r["v1"], r["b1"])
    return ("数值" if has_scalable(t) else "追加"), c, ut


def run():
    mods = parse_modules_v022() + parse_modules_v025() + [dict(m) for m in NEW_MODS]
    for m in mods:
        if m["name"] in FIX_CARD:
            m["card"] = FIX_CARD[m["name"]]
        if m["name"] in FIX_FACING_NO:
            m["facing"] = "否"
    quality = {}
    for m in mods:
        q = 0
        if m["name"] in CORE: q += 3
        if STRONG_ULT.search(m["ult"]): q += 2
        if m["size"] >= 5: q += 1
        if m["lean"] == "卡强": q += 1
        if m["cost"] >= 2: q += 1
        if m["size"] == 6: q += 1
        q += (sum(map(ord, m["name"])) % 7) / 10.0   # 打破平局，保证确定性
        quality[m["name"]] = q
    ad = PS.assign_supply(mods, quality)
    for m in mods:
        m["A"], m["D"], m["supply_tier"] = ad[m["name"]]
        m["ad_src"] = "v0.27重分布"
    counters, rows, ctr = {}, [], {}
    for m in mods:
        shp = pick_shape(m, counters)
        r = adjust(m, shp)
        ut, uc, utx = upgrade(m, r, ctr)
        r.update(utype=ut, up_cost=uc, up_text=utx)
        nu, added = add_ult_numeric(m, r)
        r.update(new_ult=nu, ult_class=added, ult_added=(added == '补数值'))
        r.update(m)
        rows.append(r)
    return rows


if __name__ == "__main__":
    rows = run()
    from collections import Counter
    c0 = Counter("in" if UNDER <= r["r0"] <= OVER else "over" if r["r0"] > OVER else "under" for r in rows)
    c1 = Counter("in" if UNDER <= r["r1"] <= OVER else "over" if r["r1"] > OVER else "under" for r in rows)
    print("模块总数", len(rows), "调整前", dict(c0), "调整后", dict(c1))
    print("费用分布", sorted(Counter(r["new_cost"] for r in rows).items()), "旧", sorted(Counter(r["cost"] for r in rows).items()))
    print("升级类型", Counter(r["utype"] for r in rows))
    print("终极分类", Counter(r["ult_class"] for r in rows))
    print("机制核心占比", sum(1 for r in rows if r["utype"] == "机制核心") / len(rows), "最小格数", min(r["size"] for r in rows if r["utype"] == "机制核心"))
    print(Counter(r["status"] for r in rows))
    for r in rows:
        if not (UNDER <= r["r1"] <= OVER):
            print("仍越界:", r["name"], r["size"], r["cost"], "->", r["new_cost"], f"r1={r['r1']:.2f}", r["new_text"], r["status"])
    json.dump(rows, open(os.path.join(os.path.dirname(__file__), "module_audit_v0.26.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
