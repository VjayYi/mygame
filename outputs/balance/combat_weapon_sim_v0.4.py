"""首版武器粗模拟 v0.4。

相对 v0.3 的变化（用户 2026-11-16 23:00 方向）：
1. 晕眩规则改为"打掉怪物一个动作"：敌人每回合有多个预告动作，
   一次晕眩取消其中最大的一个；普通敌人只有 1 个动作，等同于取消整回合。
   v0.3 的"精英晕后免疫 2 回合"取消，由动作数自然限制。
2. 加入"纯晕眩构筑"：基础攻击、武器全部换成晕眩卡，观察是否过强或不可用。
3. 加入进阶梯度（类杀戮尖塔）：用 生命倍率 / 每动作加伤 / 治疗折减 三项逐级叠加，
   观察难度斜率是否平滑。（敌人数量、精英占比属于路线层，单场模拟无法覆盖。）

仍未模拟：供能分配及冷却、校准、调取、模块、100% 供能附加效果、套装真实效果
（套装继续用三档近似，数值是占位）。结果只用于比较趋势。
"""
import random
import statistics

PLAYER_HP = 60
ENERGY = 3
DRAW = 5
RUNS = 3000
TYPE_BONUS = 0.2

# 敌人: (名称, 生命, 动作列表, 嘲讽周期)
ENEMIES = [
    ("普通(HP50, 动作[8])", 50, [8], 0),
    ("精英(HP120, 动作[6,6])", 120, [6, 6], 0),
    ("小Boss(HP240, 动作[5,5,4], 每3回合嘲讽)", 240, [5, 5, 4], 3),
]

# 构筑强度近似：(名称, 伤害加成, 每张防御牌额外护盾, 额外生命, 额外能源)
TIERS = [
    ("裸装", 0.00, 0, 0, 0),
    ("半套", 0.10, 1, 10, 0),
    ("整套", 0.25, 2, 20, 1),
]

# 进阶：(名称, 生命倍率, 每动作加伤, 治疗倍率)
ASC = [
    ("A0", 1.00, 0, 1.0),
    ("A1 生命+10%", 1.10, 0, 1.0),
    ("A2 治疗-50%", 1.10, 0, 0.5),
    ("A3 动作+1伤", 1.10, 1, 0.5),
    ("A4 生命+20%", 1.20, 1, 0.5),
    ("A5 动作+2伤", 1.20, 2, 0.5),
    ("A6 治疗-75%", 1.30, 2, 0.25),
]

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
# 纯晕眩构筑：把两张基础攻击换成晕眩卡（手部、脚部芯片提供）
BASE_STUN = [
    ("电击拳", "atk", 1, 2, 0, "stun1", True),
    ("绊倒", "atk", 1, 1, 0, "stun1", False),
] + BASE[2:]

ARMOR = [
    ("轻甲格挡", "def", 1, 0, 4, "", False),
    ("轻甲减伤", "def", 2, 0, 0, "reduce20", False),
] * 3

# (类型, 武器卡, 基础卡)
WEAPONS = {
    "短刃(单手,近)": ("m", [
        ("劈刺", "atk", 1, 4, 0, "", True),
        ("连刺", "atk", 2, 4, 0, "", True),
        ("割裂", "atk", 2, 3, 0, "bleed2", True),
    ], BASE),
    "长刀(双手,近)": ("m", [
        ("斩击", "atk", 1, 7, 0, "", True),
        ("旋斩", "atk", 2, 4, 0, "", True),
        ("斩破", "atk", 3, 10, 0, "", True),
    ], BASE),
    "重斧(单手,近,1张晕眩)": ("m", [
        ("劈砍", "atk", 2, 8, 0, "", True),
        ("震地", "atk", 2, 5, 0, "stun1", True),
        ("碎甲", "atk", 3, 6, 0, "", True),
    ], BASE),
    "手枪(单手,远)": ("r", [
        ("点射", "atk", 1, 4, 0, "", False),
        ("双发", "atk", 1, 4, 0, "", False),
        ("校准射击", "atk", 2, 6, 0, "", False),
    ], BASE),
    "突击步枪(单手,远)": ("r", [
        ("连射", "atk", 2, 6, 0, "", False),
        ("压制", "atk", 2, 3, 0, "", False),
        ("精确打击", "atk", 3, 9, 0, "", False),
    ], BASE),
    "霰弹枪(双手,远)": ("r", [
        ("散射", "atk", 2, 6, 0, "", False),
        ("近距离", "atk", 2, 10, 0, "", False),
        ("贯穿", "atk", 3, 8, 0, "", False),
    ], BASE),
    "电击警棍(纯晕眩,近)": ("m", [
        ("电击", "atk", 1, 3, 0, "stun1", True),
        ("连锁电击", "atk", 2, 4, 0, "stun1", True),
        ("麻痹脉冲", "atk", 3, 4, 0, "stun2", True),
    ], BASE_STUN),
}


def stun_count(note):
    if note.startswith("stun"):
        return int(note[4:])
    return 0


def play_battle(deck, rng, enemy, tier, kind, asc):
    _, ehp, actions, taunt_every = enemy
    _, t_dmg, t_shield, t_hp, t_energy = tier
    _, hp_mult, atk_add, heal_mult = asc
    ehp = ehp * hp_mult
    actions = [a + atk_add for a in actions]
    draw_pile = deck[:]
    rng.shuffle(draw_pile)
    discard, hand = [], []
    max_hp = PLAYER_HP + t_hp
    php = max_hp
    turns = 0
    next_bonus = 0
    bleed = 0
    stun_used_total = 0
    while ehp > 0 and php > 0 and turns < 60:
        turns += 1
        taunted = bool(taunt_every) and turns % taunt_every == 0
        defended_first = False
        shield = 0
        reduce = 0.0
        remaining = sorted(actions, reverse=True)
        for _ in range(DRAW):
            if not draw_pile:
                rng.shuffle(discard)
                draw_pile.extend(discard)
                discard.clear()
                if not draw_pile:
                    break
            hand.append(draw_pile.pop())
        energy = ENERGY + t_energy
        played = []

        def eligible(c):
            name, typ, cost, dmg, sh, note, melee = c
            if cost > energy:
                return False
            if typ == "def":
                if max(0, sum(remaining) - shield) == 0:
                    return False
                if taunted and defended_first:
                    return False
            return True

        def key(c):
            name, typ, cost, dmg, sh, note, melee = c
            if stun_count(note) and remaining:
                return (0, -min(stun_count(note), len(remaining)) / cost)
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
            if typ == "atk":
                d = dmg + next_bonus
                mult = 1.0 + t_dmg
                if (kind == "m" and melee) or (kind == "r" and not melee):
                    mult += TYPE_BONUS
                d *= mult
                if taunted and not defended_first:
                    d *= 0.5
                n = stun_count(note)
                for _ in range(n):
                    if remaining:
                        remaining.pop(0)
                        stun_used_total += 1
                if "bleed" in note:
                    bleed = 2
                ehp -= d
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
                    php = min(max_hp, php + 4 * heal_mult)
                shield += sh
        discard.extend(played)
        if bleed > 0 and ehp > 0:
            ehp -= bleed
        if ehp <= 0:
            break
        php -= max(0, sum(remaining) - shield) * (1 - reduce)
        discard.extend(hand)
        hand.clear()
    return turns, php


def run(kind, cards, base, enemy, tier, asc, runs=RUNS, seed=13):
    rng = random.Random(seed)
    deck = base + ARMOR + cards
    turns, win = [], 0
    for _ in range(runs):
        t, p = play_battle(deck, rng, enemy, tier, kind, asc)
        turns.append(t)
        if p > 0:
            win += 1
    return statistics.mean(turns), win / runs


def main():
    print("【一】晕眩规则 = 打掉一个动作（A0，无进阶）")
    for enemy in ENEMIES:
        print(f"\n== {enemy[0]} ==")
        print(f"{'武器':<22}" + "".join(f"{t[0]:>14}" for t in TIERS) + "    (胜率/回合)")
        for wname, (kind, cards, base) in WEAPONS.items():
            row = f"{wname:<22}"
            for tier in TIERS:
                t, w = run(kind, cards, base, enemy, tier, ASC[0])
                row += f"{w:>8.1%}/{t:>4.1f} "
            print(row)

    print("\n\n【二】进阶梯度：整套构筑 vs 精英（动作[6,6]）")
    elite = ENEMIES[1]
    tier = TIERS[2]
    print(f"{'武器':<22}" + "".join(f"{a[0]:>12}" for a in ASC))
    for wname, (kind, cards, base) in WEAPONS.items():
        row = f"{wname:<22}"
        for a in ASC:
            _, w = run(kind, cards, base, elite, tier, a)
            row += f"{w:>11.1%} "
        print(row)


if __name__ == "__main__":
    main()
