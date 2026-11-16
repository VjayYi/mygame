"""整局爬塔粗模拟 v0.6（进阶改为难度级别 1..10，1=基础难度）。

基于 v0.5。用户 2026-11-16 23:15 目标：成熟 build 1 级 ≥90%、2 级 ~80%，递减到 10 级 ~20%；
新手初始状态一级难度 ~60%。


用户 2026-11-16 23:07 要求：加入"不可打断动作"与"狂暴计时"的计算；
目标：内容解锁完整时，标准完整构筑 + 一路模块与商店加持，在进阶 10 级的整局通关率约 20%。

【本脚本的结构假设（全是我定的，未经你确认，会在文档里列出）】
- 一局 3 层。每层战斗节点顺序：N N N R E N N S N E R B（N 普通 / E 精英 / R 休息 / S 商店 / B 层Boss）。
  事件节点不模拟（只影响资源，不影响战斗）。
- 玩家生命跨战保留；战后回复 10% 最大生命；休息回复 35%；商店买 2 个模块。
- 模块槽 9 个（武器2、防具3、手2、脚2），新模块替换当前最弱的槽（若更强）。
  每个模块只有一种效果：伤害+6% / 每张防御牌护盾+1.0 / 最大生命+7，乘以强度。
  掉落强度 = 层系数(1.0/1.5/2.0) × U(0.6,1.4)，Boss 额外 ×1.3。普通战 50% 掉一次，精英和Boss 必掉。
- 精英：2 个可打断动作 + 1 个不可打断小动作；Boss：2 个可打断 + 1 个"蓄力"（隔回合出现、可打断）
  + 1 个不可打断；Boss 每 3 回合嘲讽（没先出防御则第一张攻击牌减半）。
- 狂暴：精英第 9 回合起、Boss 第 12 回合起，每多一回合所有动作伤害 +0.2×基础单动作伤害。
- 晕眩：一次取消一个可打断动作（取最大）。晕眩卡基础费用按 v0.8 建议提高到 2。
- 进阶 10 级按 v0.8 第 3.2 节：A1 双怪概率↑；A2 一个普通节点换成精英；A3 休息-25%；
  A4 生命+5%；A5 精英+1 可打断动作；A6 商店只买 1 个；A7 生命再+5%；
  A8 战后回复-50%；A9 精英与Boss 再+1 不可打断动作；A10 掉落三选一变二选一。
- 出牌是贪心策略。攻击全部打在最前面的敌人（范围卡的群攻优势未模拟，范围武器会被低估）。
- 未模拟：供能分配及冷却、校准、调取、事件、套装的真实效果（用三档近似）。
- 怪物伤害系数 S 只乘伤害（生命保持基础表，只受进阶影响），用二分法反推到目标通关率。
  早期版本让 S 同时乘生命和伤害，掉血近似平方增长，通关率在 S 0.5→0.7 之间从 95% 跳到 0%，无法校准。
  结果是"第一轮校准起点"，不是最终数值。
"""
import random
import statistics
import sys

PLAYER_HP = 60
ENERGY = 3
DRAW = 5
TYPE_BONUS = 0.2
SLOTS = 9
FLOOR_PATTERN = ["N", "N", "N", "R", "E", "N", "N", "S", "N", "E", "R", "B"]
FLOOR_STRENGTH = [1.0, 1.5, 2.0]

NORMAL_HP = [26, 32, 38]
NORMAL_D = [6, 7, 8]
ELITE_HP = [60, 72, 84]
ELITE_D = [5, 6, 7]
BOSS_HP = [100, 120, 140]
BOSS_D = [5, 6, 7]

BUILDS = {
    "裸装": (0.00, 0, 0, 0),
    "半套": (0.10, 1, 10, 0),
    "标准": (0.25, 2, 20, 0),
    "完整套装(+1能源)": (0.25, 2, 20, 1),
}

BASE = [
    ("徒手攻击", "atk", 1, 2, 0, "", True),
    ("踢击", "atk", 1, 2, 0, "", False),
    ("格挡", "def", 1, 0, 3, "", False),
    ("闪避", "def", 1, 0, 2, "", False),
    ("瞄准", "aux", 1, 0, 0, "next+2", False),
    ("急救", "aux", 2, 0, 0, "heal4", False),
    ("强化格挡", "def", 2, 0, 6, "", False),
    ("突袭", "atk", 2, 5, 0, "", False),
    ("超频", "aux", 1, 0, 0, "next+3", False),
    ("加固", "aux", 1, 0, 3, "", False),
]
BASE_STUN = [
    ("电击拳", "atk", 2, 2, 0, "stun1", True),
    ("绊倒", "atk", 2, 1, 0, "stun1", False),
] + BASE[2:]
ARMOR = [
    ("轻甲格挡", "def", 1, 0, 4, "", False),
    ("轻甲减伤", "def", 2, 0, 0, "reduce20", False),
] * 3

WEAPONS = {
    "短刃(单手近)": ("m", [
        ("劈刺", "atk", 1, 4, 0, "", True),
        ("连刺", "atk", 2, 4, 0, "", True),
        ("割裂", "atk", 2, 3, 0, "bleed2", True),
    ], BASE),
    "长刀(双手近)": ("m", [
        ("斩击", "atk", 1, 7, 0, "", True),
        ("旋斩", "atk", 2, 4, 0, "", True),
        ("斩破", "atk", 3, 10, 0, "", True),
    ], BASE),
    "重斧(单手近,1晕眩)": ("m", [
        ("劈砍", "atk", 2, 8, 0, "", True),
        ("震地", "atk", 2, 5, 0, "stun1", True),
        ("碎甲", "atk", 3, 6, 0, "", True),
    ], BASE),
    "手枪(单手远)": ("r", [
        ("点射", "atk", 1, 4, 0, "", False),
        ("双发", "atk", 1, 4, 0, "", False),
        ("校准射击", "atk", 2, 6, 0, "", False),
    ], BASE),
    "突击步枪(单手远)": ("r", [
        ("连射", "atk", 2, 6, 0, "", False),
        ("压制", "atk", 2, 3, 0, "", False),
        ("精确打击", "atk", 3, 9, 0, "", False),
    ], BASE),
    "霰弹枪(双手远)": ("r", [
        ("散射", "atk", 2, 6, 0, "", False),
        ("近距离", "atk", 2, 10, 0, "", False),
        ("贯穿", "atk", 3, 8, 0, "", False),
    ], BASE),
    "纯晕眩(测试件)": ("m", [
        ("电击", "atk", 2, 3, 0, "stun1", True),
        ("连锁电击", "atk", 2, 4, 0, "stun1", True),
        ("麻痹脉冲", "atk", 3, 4, 0, "stun2", True),
    ], BASE_STUN),
}
NON_STUN = [k for k in WEAPONS if not k.startswith("纯晕眩")]


def stun_count(note):
    return int(note[4:]) if note.startswith("stun") else 0


DMG_X = {}      # 每级怪物伤害微调倍率（校准时填充）
MOD_Q = 1.0     # 模块品质系数：新手阶段只有基础模块，品质更低


LADDER_KNOBS = {}   # 级别 -> 该级的修正旋钮取值（由 ladder 搭建脚本填充）


def asc_params(level):
    """难度级别 1..10；1 = 基础难度。旋钮取值由 LADDER_KNOBS 给出，未给出的级别用基础值。"""
    p = dict(hp=1.0, pair=0.25, elite_swap=False, rest=1.0, elite_extra_n=False,
             shop=2, after=1.0, extra_u=False, pick=3, dmg=1.0, xn=0.25, xu=0.20)
    p.update(LADDER_KNOBS.get(level, {}))
    p["dmg"] = DMG_X.get(level, 1.0)
    return p


def make_enemies(kind, floor, asc, rng, S):
    f = floor - 1
    hpm = asc["hp"]  # 生命只受进阶影响；校准旋钮 S 只乘伤害
    if kind == "N":
        hp, d = NORMAL_HP[f] * hpm, NORMAL_D[f] * S * asc["dmg"]
        if rng.random() < asc["pair"]:
            return [dict(hp=hp * 0.6, acts=[(d * 0.7, "n", 1)], er=(999, 0), taunt=0)
                    for _ in range(2)]
        return [dict(hp=hp, acts=[(d, "n", 1)], er=(999, 0), taunt=0)]
    if kind == "E":
        d = ELITE_D[f] * S * asc["dmg"]
        acts = [(d, "n", 1), (d, "n", 1), (0.5 * d, "u", 1)]
        if asc["elite_extra_n"]:
            acts.append((asc["xn"] * d, "n", 1))
        if asc["extra_u"]:
            acts.append((asc["xu"] * d, "u", 1))
        return [dict(hp=ELITE_HP[f] * hpm, acts=acts, er=(9, 0.2 * d), taunt=0)]
    d = BOSS_D[f] * S * asc["dmg"]
    acts = [(d, "n", 1), (d, "n", 1), (1.6 * d, "n", 2), (0.5 * d, "u", 1)]
    if asc["extra_u"]:
        acts.append((asc["xu"] * d, "u", 1))
    return [dict(hp=BOSS_HP[f] * hpm, acts=acts, er=(12, 0.2 * d), taunt=3)]


def play_battle(deck, rng, enemies, php, max_hp, bonus, kind):
    t_dmg, t_shield, energy_extra = bonus
    draw_pile = deck[:]
    rng.shuffle(draw_pile)
    discard, hand = [], []
    turns = 0
    next_bonus = 0
    bleed = 0
    taunt_every = max(e["taunt"] for e in enemies)
    while any(e["hp"] > 0 for e in enemies) and php > 0 and turns < 80:
        turns += 1
        taunted = bool(taunt_every) and turns % taunt_every == 0
        defended_first = False
        shield = 0.0
        reduce = 0.0
        remaining = []
        for e in enemies:
            if e["hp"] <= 0:
                continue
            start, inc = e["er"]
            extra = inc * max(0, turns - start)
            for (d, k, period) in e["acts"]:
                if turns % period == 0:
                    remaining.append([d + extra, k])
        for _ in range(DRAW):
            if not draw_pile:
                rng.shuffle(discard)
                draw_pile.extend(discard)
                discard.clear()
                if not draw_pile:
                    break
            hand.append(draw_pile.pop())
        energy = ENERGY + energy_extra
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
            n = stun_count(note)
            if n and breakable():
                return (0, -min(n, len(breakable())) / cost)
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
            hand.remove(c)
            energy -= cost
            played.append(c)
            front = next((e for e in enemies if e["hp"] > 0), None)
            if typ == "atk":
                d = dmg + next_bonus
                mult = 1.0 + t_dmg
                if (kind == "m" and melee) or (kind == "r" and not melee):
                    mult += TYPE_BONUS
                d *= mult
                if taunted and not defended_first:
                    d *= 0.5
                for _ in range(stun_count(note)):
                    b = breakable()
                    if b:
                        remaining.remove(max(b, key=lambda a: a[0]))
                if "bleed" in note:
                    bleed = 2
                if front is not None:
                    front["hp"] -= d
                next_bonus = 0
            elif typ == "def":
                shield += sh + t_shield
                if "reduce" in note:
                    reduce = 0.2
                defended_first = True
            else:
                if "next" in note:
                    next_bonus = int(note.split("+")[1])
                if "heal" in note:
                    php = min(max_hp, php + 4)
                shield += sh
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


def module_roll(rng, floor, boss=False):
    strength = FLOOR_STRENGTH[floor - 1] * rng.uniform(0.6, 1.4) * (1.3 if boss else 1.0) * MOD_Q
    eff = rng.choice(["dmg", "shield", "hp"])
    return (eff, strength)


def add_module(slots, mod):
    if len(slots) < SLOTS:
        slots.append(mod)
        return
    worst = min(range(len(slots)), key=lambda i: slots[i][1])
    if mod[1] > slots[worst][1]:
        slots[worst] = mod


def pick_module(rng, floor, k, slots, boss=False):
    cands = [module_roll(rng, floor, boss) for _ in range(k)]
    add_module(slots, max(cands, key=lambda m: m[1]))


def module_bonus(slots):
    dmg = sum(s for e, s in slots if e == "dmg") * 0.06
    sh = sum(s for e, s in slots if e == "shield") * 1.0
    hp = sum(s for e, s in slots if e == "hp") * 7
    return dmg, sh, hp


def run_once(wkind, cards, base, build, level, rng, S):
    asc = asc_params(level)
    b_dmg, b_sh, b_hp, b_en = BUILDS[build]
    deck = base + ARMOR + cards
    slots = []
    m_dmg, m_sh, m_hp = module_bonus(slots)
    max_hp = PLAYER_HP + b_hp + m_hp
    php = max_hp
    for floor in range(1, 4):
        pattern = FLOOR_PATTERN[:]
        if asc["elite_swap"]:
            pattern[8] = "E"
        for node in pattern:
            if node in ("N", "E", "B"):
                m_dmg, m_sh, m_hp = module_bonus(slots)
                new_max = PLAYER_HP + b_hp + m_hp
                php += max(0, new_max - max_hp)
                max_hp = new_max
                bonus = (b_dmg + m_dmg, b_sh + m_sh, b_en)
                enemies = make_enemies(node, floor, asc, rng, S)
                php, turns = play_battle(deck, rng, enemies, php, max_hp, bonus, wkind)
                if php <= 0:
                    return False, floor, node
                php = min(max_hp, php + max_hp * 0.10 * asc["after"])
                if node == "N":
                    if rng.random() < 0.5:
                        pick_module(rng, floor, asc["pick"], slots)
                else:
                    pick_module(rng, floor, asc["pick"], slots, boss=(node == "B"))
            elif node == "R":
                php = min(max_hp, php + max_hp * 0.35 * asc["rest"])
            elif node == "S":
                for _ in range(asc["shop"]):
                    add_module(slots, (rng.choice(["dmg", "shield", "hp"]),
                                       FLOOR_STRENGTH[floor - 1] * rng.uniform(0.8, 1.2) * MOD_Q))
    return True, 3, "B"


def clear_rate(wname, build, level, S, runs, seed=21, want_deaths=False):
    kind, cards, base = WEAPONS[wname]
    rng = random.Random(seed)
    clear = 0
    deaths = {}
    for _ in range(runs):
        ok, fl, nd = run_once(kind, cards, base, build, level, rng, S)
        if ok:
            clear += 1
        else:
            deaths[(fl, nd)] = deaths.get((fl, nd), 0) + 1
    return (clear / runs, deaths) if want_deaths else clear / runs


def mean_rate(weapons, build, level, S, runs):
    return statistics.mean(clear_rate(w, build, level, S, runs) for w in weapons)


def calibrate(target, weapons, build, level, runs, lo=0.3, hi=2.0, iters=7):
    for _ in range(iters):
        mid = (lo + hi) / 2
        r = mean_rate(weapons, build, level, mid, runs)
        print(f"  S={mid:.3f} 平均通关率={r:.1%}", flush=True)
        if r > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


