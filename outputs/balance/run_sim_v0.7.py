"""整局爬塔粗模拟 v0.7：真实卡组（初始 build / 成熟 build）+ 杀戮尖塔/月圆之夜式难度阶梯。

与 v0.6 的区别
1. 不再用 f×标准 的抽象加成，改为真实逐张卡组 + 大脑/躯干被动 + 套装效果（用被动近似）。
2. 难度阶梯改为参考杀戮尖塔 Ascension 的"逐类怪物拆开"思路：
   精英更多 / 普通怪伤害 / 精英伤害 / Boss伤害 / Boss战后回复减少 / 开局掉血 /
   怪物生命 / 月圆式激怒（怪物每回合永久加伤）/ 开局塞坏牌 / 商店与掉落收紧 / Boss 多一个不可打断动作。
3. 战斗结构、校准方式沿用 v0.6：只用 S 乘怪物伤害。

卡牌 tuple = (名称, 类型 atk/def/aux, 费用, 伤害, 护盾, 备注, 是否近战)
备注 token（空格分隔）：stunN 打掉 N 个可打断动作；bleed2；reduceNN 本回合受伤 -NN%；
  next+N 下一张攻击 +N；healN；drawN 抽牌；refundN 返还能量；
未模拟（沿用 v0.6 的声明）：供能比例/冷却、范围攻击的群攻优势、事件节点、套装真实效果（以被动近似）。
"""
import random
import statistics

PLAYER_HP = 60
ENERGY = 3
DRAW = 5
SLOTS = 9
FLOOR_PATTERN = ["N", "N", "N", "R", "E", "N", "N", "S", "N", "E", "R", "B"]
FLOOR_STRENGTH = [1.0, 1.5, 2.0]
NORMAL_HP = [26, 32, 38]
NORMAL_D = [9, 11, 13]
ELITE_HP = [60, 72, 84]
ELITE_D = [7, 8, 10]
BOSS_HP = [100, 120, 140]
BOSS_D = [4, 5, 6]

# ---------------------------------------------------------------- 卡组
GENERAL_STARTER = [
    ("瞄准", "aux", 1, 0, 0, "next+2", False),
    ("急救", "aux", 2, 0, 0, "heal6", False),
    ("强化格挡", "def", 2, 0, 6, "", False),
    ("突袭", "atk", 2, 9, 0, "", False),
]
ARMOR_STARTER = [  # 3 件普通轻甲，每件 2 张
    ("轻甲格挡", "def", 1, 0, 5, "", False),
    ("轻甲减伤", "def", 2, 0, 0, "reduce20", False),
] * 3

# 初始 build：近战短刃，基础义体，没有套装
STARTER = dict(
    kind="m",
    cards=[
        ("直拳", "atk", 1, 5, 0, "", True),          # 左手 基础臂
        ("架拳", "def", 1, 0, 5, "", False),         # 右手 基础臂
        ("踢击", "atk", 1, 5, 0, "", False),         # 左脚
        ("闪避", "def", 1, 0, 4, "", False),         # 右脚
        ("瞄准", "aux", 1, 0, 0, "next+2", False),   # 大脑（基础芯片）
        ("急救", "aux", 2, 0, 0, "heal6", False),    # 躯干（基础芯片）
        ("劈刺", "atk", 1, 8, 0, "", True),          # 短刃
        ("连刺", "atk", 2, 10, 0, "", True),
        ("割裂", "atk", 2, 6, 0, "bleed2", True),
    ] + GENERAL_STARTER[2:] + [("超频", "aux", 1, 0, 0, "next+3", False),
                                 ("加固", "aux", 1, 0, 4, "", False)] + ARMOR_STARTER,
    pas=dict(type_bonus=0.15, dmg=0.08, shield=0, hp=10, first_atk=1, turn_shield=1, energy=0),
    mod_q=0.85,
)

# 成熟 build：近战重击（长刀 + 4 件近战义体套装 + 3 件防具套装）
MATURE_MELEE = dict(
    kind="m",
    cards=[
        ("冲击拳", "atk", 1, 5, 0, "", True),                 # 左手 液压臂
        ("破防拳", "atk", 2, 4, 0, "stun1", True),            # 右手 战术义手
        ("飞踢", "atk", 1, 4, 0, "refund1", True),            # 左脚（返还1能量）
        ("滑步", "def", 1, 0, 4, "draw1", False),             # 右脚
        ("战术预载", "aux", 1, 0, 0, "next+3", False),        # 大脑
        ("应急修复", "aux", 2, 0, 4, "heal8", False),         # 躯干
        ("斩击", "atk", 1, 9, 0, "", True),                   # 长刀（高周波）
        ("旋斩", "atk", 2, 10, 0, "", True),
        ("斩破", "atk", 3, 16, 0, "", True),
        ("强化格挡", "def", 2, 0, 6, "", False),
        ("超频", "aux", 1, 0, 0, "next+3", False),
        ("加固", "aux", 1, 0, 3, "", False),
        ("突袭", "atk", 2, 5, 0, "", False),
    ] + [("复合装甲", "def", 1, 0, 5, "", False),
         ("反应装甲", "def", 2, 0, 0, "reduce30", False)] * 3,
    pas=dict(type_bonus=0.20, dmg=0.10, shield=1, hp=10, first_atk=2, turn_shield=1, energy=0),
    mod_q=1.0,
)

# 成熟 build：远程压制（突击步枪 + 速射/扰乱）
MATURE_RANGED = dict(
    kind="r",
    cards=[
        ("速射机构", "atk", 1, 5, 0, "", False),              # 左手
        ("扰乱射击", "atk", 2, 4, 0, "stun1", False),         # 右手 战术义手
        ("蹬射", "atk", 1, 4, 0, "refund1", False),           # 左脚
        ("后撤步", "def", 1, 0, 4, "draw1", False),           # 右脚
        ("火控锁定", "aux", 1, 0, 0, "next+3", False),        # 大脑
        ("相位力场", "aux", 2, 0, 4, "heal8", False),         # 躯干
        ("连射", "atk", 1, 8, 0, "", False),                  # 突击步枪（改良）
        ("压制", "atk", 2, 10, 0, "", False),
        ("精确打击", "atk", 3, 16, 0, "", False),
        ("强化格挡", "def", 2, 0, 6, "", False),
        ("超频", "aux", 1, 0, 0, "next+3", False),
        ("加固", "aux", 1, 0, 3, "", False),
        ("突袭", "atk", 2, 5, 0, "", False),
    ] + [("复合装甲", "def", 1, 0, 5, "", False),
         ("反应装甲", "def", 2, 0, 0, "reduce30", False)] * 3,
    pas=dict(type_bonus=0.20, dmg=0.10, shield=1, hp=10, first_atk=2, turn_shield=1, energy=0),
    mod_q=1.0,
)

DEAD_CARD = ("过热回路", "aux", 9, 0, 0, "", False)   # 坏牌：打不出，只占手牌
BUILDS = {"初始·短刃": STARTER, "成熟·近战": MATURE_MELEE, "成熟·远程": MATURE_RANGED}

# ---------------------------------------------------------------- 难度阶梯
BASE_P = dict(
    elite_p=0.0,          # A1 每层多一个精英的概率（把一个普通节点换成精英）
    nd=1.0, ed=1.0, bd=1.0,   # A2/3/4 普通/精英/Boss 伤害
    nh=1.0, eh=1.0, bh=1.0,   # A7/8/9 生命
    boss_heal=1.0,        # A5 Boss 战后回复已损失生命的比例
    start_loss=0.0,       # A6 开局损失生命比例
    max_hp_mult=1.0,      # A14 最大生命
    enr=0.0,              # 月圆式激怒：每回合起所有怪物伤害 +enr×基础
    dead=0,               # A10 坏牌张数
    pick=3, shop=2, rest=1.0, after=1.0,
    pair=0.25,
    boss_extra_u=False,   # A19 Boss 多一个不可打断动作
)

LADDER = {
    1: {},
    2: dict(elite_p=1.0),
    3: dict(nd=1.40),
    4: dict(ed=1.05),
    5: dict(bd=1.20, boss_heal=0.75),
    6: dict(start_loss=0.10, max_hp_mult=0.91),
    7: dict(nh=1.03, eh=1.03, bh=1.03),
    8: dict(enr=0.010),
    9: dict(dead=1, shop=1, after=0.95),
    10: dict(pick=2, boss_extra_u=True, rest=1.0),
}
LADDER_NOTES = {
    2: "精英更多：每层多 1 个精英节点（StS A1）",
    3: "普通怪伤害 +40%（A2）",
    4: "精英伤害 +5%（A3）",
    5: "Boss 伤害 +20%（A4）+ Boss 战后只回复 75% 已损失生命（A5）",
    6: "开局损失 10% 生命（A6）+ 最大生命 -9%（A14）",
    7: "普通/精英/Boss 生命 +3%（A7/8/9）",
    8: "月圆式激怒：怪物每回合永久 +1.0% 基础伤害",
    9: "开局塞 1 张坏牌（A10 诅咒）+ 商店只买 1 个（A16）+ 战后回复 -5%",
    10: "掉落三选一→二选一 + Boss 多一个不可打断动作（A19）",
}
DMG_X = {}
LUCK = 0.12   # 每局运气/操作/事件选择的差异：该局怪物伤害系数再乘 lognormal(0, LUCK)，用来压平通关率曲线


def params(level):
    p = dict(BASE_P)
    for L in range(1, level + 1):
        p.update(LADDER.get(L, {}))
    p["dmg_x"] = DMG_X.get(level, 1.0)
    return p


# ---------------------------------------------------------------- 战斗
def parse(note):
    d = dict(stun=0, bleed=0, reduce=0.0, nxt=0, heal=0, draw=0, refund=0)
    for t in note.split():
        if t.startswith("stun"):
            d["stun"] = int(t[4:])
        elif t.startswith("bleed"):
            d["bleed"] = int(t[5:])
        elif t.startswith("reduce"):
            d["reduce"] = int(t[6:]) / 100
        elif t.startswith("next+"):
            d["nxt"] = int(t[5:])
        elif t.startswith("heal"):
            d["heal"] = int(t[4:])
        elif t.startswith("draw"):
            d["draw"] = int(t[4:])
        elif t.startswith("refund"):
            d["refund"] = int(t[6:])
    return d


def make_enemies(kind, floor, p, rng, S):
    f = floor - 1
    enr = p["enr"]
    if kind == "N":
        d = NORMAL_D[f] * S * p["nd"] * p["dmg_x"]
        hp = NORMAL_HP[f] * p["nh"]
        if rng.random() < p["pair"]:
            return [dict(hp=hp * 0.6, acts=[(d * 0.7, "n", 1)], er=(1, enr * d * 0.7), taunt=0) for _ in range(2)]
        return [dict(hp=hp, acts=[(d, "n", 1)], er=(1, enr * d), taunt=0)]
    if kind == "E":
        d = ELITE_D[f] * S * p["ed"] * p["dmg_x"]
        acts = [(d, "n", 1), (d, "n", 1), (0.5 * d, "u", 1)]
        er = (1, enr * d) if enr else (9, 0.2 * d)
        er = (1, enr * d + 0.0) if enr else er
        return [dict(hp=ELITE_HP[f] * p["eh"], acts=acts, er=er, taunt=0, rage_from9=0.2 * d)]
    d = BOSS_D[f] * S * p["bd"] * p["dmg_x"]
    acts = [(d, "n", 1), (d, "n", 1), (1.6 * d, "n", 2), (0.5 * d, "u", 1)]
    if p["boss_extra_u"]:
        acts.append((0.2 * d, "u", 1))
    er = (1, enr * d) if enr else (12, 0.2 * d)
    return [dict(hp=BOSS_HP[f] * p["bh"], acts=acts, er=er, taunt=3, rage_from12=0.2 * d)]


def play_battle(deck, rng, enemies, php, max_hp, pas, mod, kind):
    m_dmg, m_sh = mod
    t_dmg = pas["dmg"] + m_dmg
    t_shield = pas["shield"] + m_sh
    draw_pile = deck[:]
    rng.shuffle(draw_pile)
    discard, hand = [], []
    turns = 0
    bleed = 0
    taunt_every = max(e["taunt"] for e in enemies)

    def draw_one():
        if not draw_pile:
            rng.shuffle(discard)
            draw_pile.extend(discard)
            discard.clear()
        if draw_pile:
            hand.append(draw_pile.pop())

    while any(e["hp"] > 0 for e in enemies) and php > 0 and turns < 80:
        turns += 1
        taunted = bool(taunt_every) and turns % taunt_every == 0
        defended_first = False
        shield = float(pas["turn_shield"])
        reduce = 0.0
        next_bonus = 0
        first_atk_used = False
        remaining = []
        for e in enemies:
            if e["hp"] <= 0:
                continue
            start, inc = e["er"]
            extra = inc * max(0, turns - start)
            # 激怒存在时仍保留精英/Boss 原有的狂暴计时
            if e.get("rage_from9") is not None and e["er"][0] == 1:
                extra += e["rage_from9"] * max(0, turns - 9)
            if e.get("rage_from12") is not None and e["er"][0] == 1:
                extra += e["rage_from12"] * max(0, turns - 12)
            for (d, k, period) in e["acts"]:
                if turns % period == 0:
                    remaining.append([d + extra, k])
        for _ in range(DRAW):
            draw_one()
        energy = ENERGY + pas["energy"]
        played = []

        def breakable():
            return [a for a in remaining if a[1] == "n"]

        def eligible(c):
            name, typ, cost, dmg, sh, note, melee = c
            if cost > energy:
                return False
            if typ == "def":
                if max(0.0, sum(a[0] for a in remaining) - shield) == 0:
                    return False
                if taunted and defended_first:
                    return False
            return True

        def key(c):
            name, typ, cost, dmg, sh, note, melee = c
            n = parse(note)["stun"]
            if n and breakable():
                return (0, -min(n, len(breakable())) / max(cost, 1))
            if taunted and typ == "def" and not defended_first:
                return (1, cost)
            if typ == "atk":
                return (2, -(dmg / max(cost, 1)))
            if typ == "aux":
                return (3, cost)
            return (4, -(sh / max(cost, 1)))

        while True:
            cands = [c for c in hand if eligible(c)]
            if not cands:
                break
            c = min(cands, key=key)
            name, typ, cost, dmg, sh, note, melee = c
            n = parse(note)
            hand.remove(c)
            energy -= cost
            played.append(c)
            front = next((e for e in enemies if e["hp"] > 0), None)
            if typ == "atk":
                d = dmg + next_bonus
                if not first_atk_used:
                    d += pas["first_atk"]
                    first_atk_used = True
                mult = 1.0 + t_dmg
                if (kind == "m" and melee) or (kind == "r" and not melee):
                    mult += pas["type_bonus"]
                d *= mult
                if taunted and not defended_first:
                    d *= 0.5
                for _ in range(n["stun"]):
                    b = breakable()
                    if b:
                        remaining.remove(max(b, key=lambda a: a[0]))
                if n["bleed"]:
                    bleed = 2
                if front is not None:
                    front["hp"] -= d
                next_bonus = 0
            elif typ == "def":
                shield += sh + t_shield
                if n["reduce"]:
                    reduce = max(reduce, n["reduce"])
                defended_first = True
            else:
                if n["nxt"]:
                    next_bonus = n["nxt"]
                if n["heal"]:
                    php = min(max_hp, php + n["heal"])
                shield += sh
            energy += n["refund"]
            for _ in range(n["draw"]):
                draw_one()
        discard.extend(played)
        if bleed > 0:
            front = next((e for e in enemies if e["hp"] > 0), None)
            if front is not None:
                front["hp"] -= bleed
        if not any(e["hp"] > 0 for e in enemies):
            break
        php -= max(0.0, sum(a[0] for a in remaining) - shield) * (1 - reduce)
        discard.extend(hand)
        hand.clear()
    return php, turns


# ---------------------------------------------------------------- 整局
def module_roll(rng, floor, q, boss=False):
    s = FLOOR_STRENGTH[floor - 1] * rng.uniform(0.6, 1.4) * (1.3 if boss else 1.0) * q
    return (rng.choice(["dmg", "shield", "hp"]), s)


def add_module(slots, mod):
    if len(slots) < SLOTS:
        slots.append(mod)
        return
    worst = min(range(len(slots)), key=lambda i: slots[i][1])
    if mod[1] > slots[worst][1]:
        slots[worst] = mod


def module_bonus(slots):
    return (sum(s for e, s in slots if e == "dmg") * 0.06,
            sum(s for e, s in slots if e == "shield") * 1.0,
            sum(s for e, s in slots if e == "hp") * 7)


def run_once(build, level, rng, S):
    p = params(level)
    S = S * rng.lognormvariate(0, LUCK)
    pas = build["pas"]
    q = build["mod_q"]
    deck = build["cards"] + [DEAD_CARD] * p["dead"]
    slots = []
    base_max = (PLAYER_HP + pas["hp"]) * p["max_hp_mult"]
    max_hp = base_max
    php = max_hp * (1 - p["start_loss"])
    for floor in range(1, 4):
        pattern = FLOOR_PATTERN[:]
        if rng.random() < p["elite_p"]:
            pattern[8] = "E"
        for node in pattern:
            if node in ("N", "E", "B"):
                dm, sh, hp = module_bonus(slots)
                new_max = base_max + hp
                php += max(0, new_max - max_hp)
                max_hp = new_max
                enemies = make_enemies(node, floor, p, rng, S)
                php, _ = play_battle(deck, rng, enemies, php, max_hp, pas, (dm, sh), build["kind"])
                if php <= 0:
                    return False, floor, node
                if node == "B":
                    php = min(max_hp, php + (max_hp - php) * p["boss_heal"])
                else:
                    php = min(max_hp, php + max_hp * 0.10 * p["after"])
                if node == "N":
                    if rng.random() < 0.5:
                        add_module(slots, max((module_roll(rng, floor, q) for _ in range(p["pick"])), key=lambda m: m[1]))
                else:
                    add_module(slots, max((module_roll(rng, floor, q, node == "B") for _ in range(p["pick"])), key=lambda m: m[1]))
            elif node == "R":
                php = min(max_hp, php + max_hp * 0.35 * p["rest"])
            elif node == "S":
                for _ in range(p["shop"]):
                    add_module(slots, (rng.choice(["dmg", "shield", "hp"]),
                                       FLOOR_STRENGTH[floor - 1] * rng.uniform(0.8, 1.2) * q))
    return True, 3, "B"


def clear_rate(bname, level, S, runs, seed=21, want_deaths=False):
    build = BUILDS[bname]
    rng = random.Random(seed)
    clear, deaths = 0, {}
    for _ in range(runs):
        ok, fl, nd = run_once(build, level, rng, S)
        if ok:
            clear += 1
        else:
            deaths[(fl, nd)] = deaths.get((fl, nd), 0) + 1
    return (clear / runs, deaths) if want_deaths else clear / runs
