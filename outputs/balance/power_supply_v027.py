# -*- coding: utf-8 -*-
"""供能参数 v0.27：每个模块的 (攻击供能需求 A, 防御供能需求 D)，以及武器整体供能门槛"""
import re, os, math

OUT = os.path.join(os.path.dirname(__file__), "..")
LEVEL = {2: 1, 3: 1, 4: 2, 5: 3, 6: 4}


def parse_ad_tables():
    ad = {}
    p16 = os.path.join(OUT, "combat-module-catalog-v0.16.md")
    for ln in open(p16, encoding="utf-8"):
        if ln.startswith("|"):
            c = [x.strip() for x in ln.strip().strip("|").split("|")]
            if len(c) >= 10 and c[1].isdigit() and c[8].isdigit() and c[9].isdigit():
                ad[c[0]] = (int(c[8]), int(c[9]), "v0.16", int(c[1]))
    p21 = os.path.join(OUT, "combat-module-catalog-v0.21.md")
    sec = False
    for ln in open(p21, encoding="utf-8"):
        if ln.startswith("## 5."): sec = True
        elif ln.startswith("## 6."): sec = False
        if sec and ln.startswith("|"):
            c = [x.strip() for x in ln.strip().strip("|").split("|")]
            if len(c) >= 6 and c[1].isdigit() and c[4].isdigit():
                ad[c[0]] = (int(c[4]), int(c[5]), "v0.21", int(c[1]))
    return ad


ATK_WORDS = re.compile(r"伤害|攻击|击杀|命中|流血|中毒|灼烧|击晕|穿透|暴击|溢出|弹射")
DEF_WORDS = re.compile(r"护盾|受伤|防御牌|受到攻击|减伤|反击|保留")


def infer_ad(mod):
    sz, t, txt = mod["size"], mod["type"], mod["card"]
    L = LEVEL[sz]
    if t in ("伤害", "距离", "献祭", "复刻"):
        return (L, 0)
    if t in ("状态", "节奏", "标记", "陷阱"):
        return (max(1, L - 1), 0)
    if t == "防御":
        return (0, L)
    if t == "回复":
        return (max(1, L - 1), 0) if ATK_WORDS.search(txt.split("；")[0]) else (0, max(1, L - 1))
    if t == "控制":
        if re.search(r"敌人.*攻击.*-|受伤|下一次攻击|下回合攻击", txt):
            return (0, max(1, L - 1))
        return (max(1, L - 1), 0)
    if t in ("特殊",):
        return (max(1, L - 1), 0) if ATK_WORDS.search(txt) else (0, max(1, L - 1))
    # 能源 / 过牌 / 加速 / 辅助 / 保留 等功能件：偏防御侧，若效果挂在攻击上则偏攻击侧
    lv = 1 if sz <= 4 else 2
    if re.search(r"攻击|击杀|命中", txt.split("；")[0]):
        return (lv, 0)
    return (0, lv)


def get_ad(mod, table):
    if mod["name"] in table and table[mod["name"]][3] == mod["size"]:
        a, d, src, _ = table[mod["name"]]
        return a, d, src
    a, d = infer_ad(mod)
    return a, d, "规则"


# 武器基础供能需求（v0.23 三形态 + 品类修正：爪攻需+1；其余品类修正不改供能）
FORM_BASE = {"改装": (2, 1), "均衡": (3, 1), "强攻": (4, 2)}


def threshold(A, D):
    """终极卡所需的主功能侧供能比（10% 一档，向上取整）；A==D 时两侧各 50%"""
    T = A + D
    if A == D:
        return ("均衡", 0.5)
    main = max(A, D)
    return ("攻" if A > D else "防", math.ceil(main / T * 10) / 10)


def card_mod(own_supply):
    """某侧的卡（攻击卡看攻击供能比，防御卡看防御供能比）受到的修正：
    本侧供能 100% → +2；≥80% → +1；≤20%（对侧≥80%）→ -1；0%（对侧100%）→ -2；其余 0"""
    p = round(own_supply * 10) / 10
    if p >= 1.0: return 2
    if p >= 0.8: return 1
    if p <= 0.0: return -2
    if p <= 0.2: return -1
    return 0


# ================= v0.27 修订：供能参数重新分布（一半一半为主，优质卡有倾向/极端） =================
# 目标分布（可灵活浮动）：≈50% 均衡，≈20% 偏攻，≈20% 偏防，≈10% 极端；越优质/越突出的卡越有变化，一般的卡一半一半。
# 注意：攻击卡不一定偏攻，防御卡不一定偏防——方向看卡的“玩法”，不是看卡的类型。
BAL = {2: (1, 1), 3: (1, 1), 4: (2, 2), 5: (3, 2), 6: (3, 3)}     # 均衡；5 格奇数，多的一点给自然方向
LEAN = {2: (2, 1), 3: (2, 1), 4: (3, 1), 5: (4, 2), 6: (5, 2)}    # 偏向（偏攻写法，偏防取反）
EXT = {4: (4, 0), 5: (5, 1), 6: (6, 0)}                           # 极端（只给 4 格及以上）

# 玩法方向覆盖：攻击卡但需要防御姿态（反击/防反/受伤触发）→ 偏防；防御/功能卡但靠打击触发 → 偏攻
FLIP_TO_D = {"格挡反击", "反刺刃纹", "守势回斩", "回剑斩", "裂空连斩", "破云裂剑", "连剑连携", "共鸣刃", "剑意回环", "震颤屏息",
             "献祭刃", "战意", "镜甲扣", "反震", "游猎步伐", "保险丝", "地雷布设", "压制射击", "压制火力", "镇慑刃", "猎息", "消音器"}
FLIP_TO_A = {"拾荒", "余烬", "嗜血回流", "吸血", "充能刃", "脉冲刃格", "血契爪痕", "回收弹壳", "连打连锁", "能量回馈", "瞬息步", "战术核心",
             "重心蓄势", "连锁殉爆", "连锁引线", "余火", "磨刀石", "战术速写", "血刃祭坛", "噬魂爪", "连环处决"}


D_CATS = {"剑", "斧", "炮筒"}
A_CATS = {"爪", "拳套", "手枪"}


def natural_side(mod):
    n = mod["name"]
    if n in FLIP_TO_D: return "D"
    if n in FLIP_TO_A: return "A"
    a, d = infer_ad(mod)
    if a > d: return "A"
    if d > a: return "D"
    return "A" if mod["type"] in ("伤害", "状态", "控制", "节奏", "距离", "特殊", "标记", "陷阱", "献祭", "复刻") else "D"


_DMG_FIRST = re.compile(r"^[^；]*(?:\d+\s*伤害|伤害\s*\+|各\s*-\d|段)")


def assign_supply(mods, quality):
    """quality: name -> 分数（越高越突出）。返回 {name: (A, D, 档位)}；档位：均衡/偏攻/偏防/极端攻/极端防"""
    side = {m["name"]: natural_side(m) for m in mods}
    q = dict(quality)
    for m in mods:   # 防御/保留/控制向的大件也有资格成为极端防（否则极端全是大伤害）
        if side[m["name"]] == "D" and m["size"] >= 4:
            q[m["name"]] += 2.5
    n = len(mods)
    order = sorted(mods, key=lambda m: (-q[m["name"]], -m["size"], m["name"]))
    n_ext = round(n * 0.10); n_lean = round(n * 0.40)
    ext, lean, bal = [], [], []
    for m in order:
        if len(ext) < n_ext and m["size"] >= 4: ext.append(m)
        elif len(lean) < n_lean: lean.append(m)
        else: bal.append(m)

    def margin(m):
        a, d = infer_ad(m)
        mg = abs(a - d)
        if "护盾" in m["card"] or "防御牌" in m["card"]: mg -= 1   # 带防御元素的攻击卡更容易被翻到偏防
        return mg

    def flippable(m, src):
        if m["name"] in FLIP_TO_A or m["name"] in FLIP_TO_D: return False
        if src == "A" and _DMG_FIRST.search(m["card"]) and m["size"] >= 4 and m["type"] in ("伤害", "距离"): return False
        return True

    def is_atk(m):
        return bool(_DMG_FIRST.search(m["card"]))

    # 品类性格：剑（防反）、斧（重装稳扎）、炮筒（阵地战）的攻击件偏防；爪/拳套/手枪的功能件偏攻
    for m in lean + ext:
        if m["limit"] in D_CATS and is_atk(m) and m["name"] not in FLIP_TO_A:
            side[m["name"]] = "D"
        if m["limit"] in A_CATS and not is_atk(m) and m["name"] not in FLIP_TO_D:
            side[m["name"]] = "A"

    # 偏向组：攻击卡里 ≥30% 偏防，功能/防御卡里 ≥35% 偏攻（“攻击卡不一定攻高，防御卡不一定防高”）
    for want_atk, share_side, share in ((True, "D", 0.30), (False, "A", 0.35)):
        grp = [m for m in lean if is_atk(m) == want_atk]
        need = round(len(grp) * share)
        have = sum(1 for m in grp if side[m["name"]] == share_side)
        src = "A" if share_side == "D" else "D"
        if want_atk:
            cand = [m for m in grp if side[m["name"]] == src and flippable(m, src)]
            cand.sort(key=lambda x: (margin(x), -q[x["name"]]))
        else:
            kw = re.compile(r"攻击|击杀|命中|伤害|穿透|暴击|溢出")
            cand = [m for m in grp if side[m["name"]] == src and m["name"] not in FLIP_TO_D]
            cand.sort(key=lambda x: (-(1 if kw.search(x["card"]) else 0), margin(x), -q[x["name"]]))
        for m in cand[:max(0, need - have)]:
            side[m["name"]] = share_side
    # 极端组：攻/防各约一半（容忍 ±4）
    grp, tol = ext, 4
    for _ in range(400):
        na = sum(1 for m in grp if side[m["name"]] == "A"); nd = len(grp) - na
        if abs(na - nd) <= tol: break
        src = "A" if na > nd else "D"
        cand = [m for m in grp if side[m["name"]] == src and flippable(m, src)]
        if not cand: break
        m = min(cand, key=lambda x: (margin(x), -q[x["name"]]))
        side[m["name"]] = "D" if src == "A" else "A"
    out = {}
    for m in bal:
        a, d = BAL[m["size"]]
        if m["size"] == 5 and side[m["name"]] == "D": a, d = d, a
        out[m["name"]] = (a, d, "均衡")
    for m in lean:
        a, d = LEAN[m["size"]]
        if side[m["name"]] == "D": a, d = d, a
        out[m["name"]] = (a, d, "偏攻" if a > d else "偏防")
    for m in ext:
        a, d = EXT[m["size"]]
        if side[m["name"]] == "D": a, d = d, a
        out[m["name"]] = (a, d, "极端攻" if a > d else "极端防")
    return out
