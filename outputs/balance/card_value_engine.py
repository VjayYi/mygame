# -*- coding: utf-8 -*-
"""卡牌价值引擎 v0.1（v0.26 预算模型）
单位 E = 1 费等价。锚点：6 伤害 = 1E，6 护盾 = 1E，1 层流血/灼烧/中毒 = 1.5 伤害 = 0.25E。
容差：超模最多 +20%，低于 -15% 视为亏模。
"""
import re, os

OUT = os.path.join(os.path.dirname(__file__), "..")

DMG_PER_E = 6.0
SHD_PER_E = 6.0
DOT_E = 1.5 / 6.0
OVER = 1.20
UNDER = 0.85

# ---------- 占模（尺寸 / 重量操作 / 形状难拼度） ----------
W_BY_SIZE = {2: 1, 3: 1, 4: 2, 5: 4, 6: 5}
O_BY_SIZE = {2: 0, 3: 1, 4: 1, 5: 3, 6: 4}
SHAPES = {  # 形状: (格数, 难拼度 d)
    "直2": (2, 0),
    "直3": (3, 0), "弯3": (3, 1),
    "直4": (4, 0), "方4": (4, 0), "L4": (4, 1), "T4": (4, 1), "Z4": (4, 2),
    "直5": (5, 0), "P5": (5, 1), "L5": (5, 1), "T5": (5, 2), "U5": (5, 2), "Z5": (5, 2), "W5": (5, 3), "十5": (5, 3),
    "矩6": (6, 1), "L6": (6, 2), "T6": (6, 2), "U6": (6, 3), "阶6": (6, 3),
}


def footprint(size, shape):
    """占模补偿 E：尺寸 + 重量操作 + 形状难拼度"""
    w, o = W_BY_SIZE[size], O_BY_SIZE[size]
    d = SHAPES[shape][1]
    return 0.06 * (size - 2) + 0.02 * (w + o) + 0.04 * d * (size - 2)


def base_budget(cost):
    """费用对应的价值预算。0 费 = 0.4E（手牌位补偿），其余 = 费用本身。"""
    return 0.4 if cost == 0 else float(cost)


# ---------- 文本效果估值 ----------
COND = re.compile(r"击杀|若|低于|带|已破盾|异常状态|距离\s*3|每打出|当|上一张|之前|目标有")


def seg_value(seg):
    """返回 (E, 剩余未解析文本)"""
    s = seg
    v = 0.0
    dmg_acc = 0.0

    def take(pat, fn):
        nonlocal s, v
        for m in list(re.finditer(pat, s)):
            v += fn(m)
        s = re.sub(pat, "", s)

    # 群体先于单体
    take(r"(?:所有|全体)敌人各\s*-?(\d+)", lambda m: int(m.group(1)) * 1.6 / DMG_PER_E)
    take(r"随机(?:两|2)名敌人各\s*-?(\d+)", lambda m: int(m.group(1)) * 1.7 / DMG_PER_E)
    take(r"1\s*号位全体", lambda m: 0.0)  # 倍率在下方单体伤害里处理
    mult = 1.3 if "1 号位全体" in seg or "1号位全体" in seg else 1.0
    m = re.search(r"伤害\s*\+(\d+)", s)
    if m:
        d = int(m.group(1)) * mult
        dmg_acc = d
        v += d / DMG_PER_E
        s = s.replace(m.group(0), "", 1)
    take(r"护盾\s*\+(\d+)", lambda m: int(m.group(1)) / SHD_PER_E)
    take(r"(?:附加)?(?:流血|中毒|灼烧)\s*(\d+)", lambda m: int(m.group(1)) * DOT_E)
    take(r"抽\s*(\d+)\s*张", lambda m: 0.4 * int(m.group(1)))
    take(r"弃\s*(\d+)\s*张", lambda m: -0.15 * int(m.group(1)))
    take(r"(?:本回合)?能源\s*\+(\d+)", lambda m: 0.9 * int(m.group(1)))
    take(r"回复\s*(\d+)\s*能源", lambda m: 0.9 * int(m.group(1)))
    take(r"下一张(?:\S{0,3})?攻击\s*\+(\d+)", lambda m: 0.8 * int(m.group(1)) / DMG_PER_E)
    take(r"下一张(?:\S{0,3})?牌?(?:费用)\s*-1", lambda m: 0.7)
    take(r"(\d+)%\s*击晕", lambda m: {20: 0.6, 30: 0.9, 50: 1.2}.get(int(m.group(1)), 0.9))
    take(r"必定击晕", lambda m: 2.0)
    take(r"(?:目标|敌人)?下(?:回合|一次)攻击(?:伤害)?\s*-(\d+)", lambda m: int(m.group(1)) / DMG_PER_E)
    take(r"本回合敌人(?:首次)?攻击伤害\s*-(\d+)", lambda m: int(m.group(1)) / DMG_PER_E)
    take(r"回复\s*(\d+)\s*生命", lambda m: 1.3 * int(m.group(1)) / DMG_PER_E)
    take(r"额外结算\s*1\s*段（伤害减半）", lambda m: 0.5 * dmg_acc / DMG_PER_E)
    take(r"忽略护盾\s*(\d+)|护盾吸收\s*-(\d+)", lambda m: int(m.group(1) or m.group(2)) * 0.5 / DMG_PER_E)
    take(r"无视护盾", lambda m: 0.15)
    take(r"穿透[，,]?\s*身后一?名?\+?(\d+)", lambda m: 0.8 * int(m.group(1)) / DMG_PER_E)
    take(r"洗回牌库", lambda m: 0.6)
    take(r"攻击距离\s*\+1", lambda m: 0.1)
    take(r"击退\s*1\s*格", lambda m: 0.15)
    take(r"拉近\s*1\s*格", lambda m: 0.1)
    if COND.search(seg) and v > 0:
        v *= 0.65
    # 兜底：剩余文本里的条件数值（额外+N / 追加+N / 裸 +N / 造成N伤害）按 0.55 折条件伤害估值
    cond_total = 0.0
    for m in re.finditer(r"(?:额外|追加)\s*\+?(\d+)|(?<![\d×段])\+(\d+)(?!\s*[段])|造成\s*(\d+)\s*伤害|受\s*(\d+)\s*伤害", s):
        n = int(next(g for g in m.groups() if g))
        cond_total += 0.55 * n / DMG_PER_E
    if cond_total:
        v += cond_total
        s = re.sub(r"(?:额外|追加)\s*\+?\d+|(?<![\d×段])\+\d+|造成\s*\d+\s*伤害|受\s*\d+\s*伤害", "", s)
    rest = re.sub(r"[\s，,。；、（）()：:]+", "", s)
    rest = re.sub(r"^(?:额外|并|同时|再|且|，)+", "", rest)
    return v, rest


def card_value(text, extra=None):
    """估算一条"卡效果"文本的价值 E。extra: 手工补充 E（解析不了的机制）"""
    total = 0.0
    leftovers = []
    for seg in re.split(r"；|;", text):
        v, rest = seg_value(seg)
        total += v
        if rest and len(rest) >= 2:
            leftovers.append(rest)
    if extra:
        total += extra
    return total, leftovers


# ---------- 表格解析 ----------
def parse_tables(path):
    rows = []
    for ln in open(path, encoding="utf-8"):
        ln = ln.rstrip("\n")
        if not ln.startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        rows.append(cells)
    return rows


def parse_modules_v022():
    path = os.path.join(OUT, "combat-module-catalog-v0.22-cost.md")
    mods = []
    mode = None
    for ln in open(path, encoding="utf-8"):
        if ln.startswith("## 1."):
            mode = "近战"
        elif ln.startswith("## 2."):
            mode = "远程"
        elif ln.startswith("## 3."):
            mode = None
        if mode and ln.startswith("|"):
            c = [x.strip() for x in ln.strip().strip("|").split("|")]
            if len(c) >= 9 and c[1].isdigit():
                mods.append(dict(name=c[0], size=int(c[1]), type=c[2], lean=c[3], cost=int(c[4]),
                                 card=c[5], ult=c[6], facing=c[7], limit=c[8], major=mode, origin="通用"))
    return mods


def parse_modules_v025():
    path = os.path.join(OUT, "combat-module-catalog-v0.25-weapon-exclusive-modules.md")
    mods = []
    cat = None
    in_sec2 = False
    for ln in open(path, encoding="utf-8"):
        if ln.startswith("## 2."):
            in_sec2 = True
        elif ln.startswith("## 3."):
            in_sec2 = False
        m = re.match(r"### 2\.\d (\S+)（12", ln)
        if m:
            cat = m.group(1)
        if in_sec2 and ln.startswith("|") and cat:
            c = [x.strip() for x in ln.strip().strip("|").split("|")]
            if len(c) >= 8 and c[1].isdigit():
                mods.append(dict(name=c[0], size=int(c[1]), type=c[2], lean=c[3], cost=int(c[4]),
                                 card=c[5], ult=c[6], facing=c[7], limit=cat,
                                 major="近战" if cat in "刀剑爪斧拳套" else "远程", origin="品类限定"))
    return mods


if __name__ == "__main__":
    a, b = parse_modules_v022(), parse_modules_v025()
    print(len(a), len(b))
