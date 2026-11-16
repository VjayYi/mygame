"""首版武器粗模拟 v0.3。

相对 v0.2 的变化（用户 2026-11-16 22:53 方向）：
- 敌人整体调强（主打玩家自定义快感，怪强度高是应该的）。
- 精英、Boss 加机制：被击晕后 N 回合免疫；Boss 每 3 回合"嘲讽"，
  嘲讽回合玩家若没有先出防御牌，第一张攻击牌伤害减半。
- 套装效果：用三档构筑强度近似（裸装 / 半套 / 整套），观察"强怪要求多强的 build"。
- 手部义体按"与武器类型匹配"处理：近战武器配近战加成手，远程武器配远程加成手，
  各 +20%，消除 v0.2 里远程没有加成的不公平。远程身份缺口仍然存在，本脚本不解决它。

未模拟：供能分配及冷却、校准、调取、模块、100% 供能附加效果。仍是相对比较，不是校准值。
"""
import random
import statistics

PLAYER_HP = 60
ENERGY = 3
DRAW = 5
RUNS = 3000
TYPE_BONUS = 0.2

# 敌人: (名称, HP, 攻, 击晕免疫回合, 嘲讽周期)
ENEMIES = [
    ("普通(HP50/攻8)", 50, 8, 0, 0),
    ("精英(HP120/攻12,晕后免疫2)", 120, 12, 2, 0),
    ("小Boss(HP240/攻14,晕后免疫2,每3回合嘲讽)", 240, 14, 2, 3),
]

# 构筑强度：(名称, 伤害倍率, 每张防御卡额外护盾, 额外生命, 额外能源)
TIERS = [
    ("裸装", 0.00, 0, 0, 0),
    ("半套(2件套)", 0.10, 1, 10, 0),
    ("整套(4件套)", 0.25, 2, 20, 1),
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
ARMOR = [
    ("轻甲格挡", "def", 1, 0, 4, "", False),
    ("轻甲减伤", "def", 2, 0, 0, "reduce20", False),
] * 3

WEAPONS = {
    "短刃(单手,近)": ("m", [
        ("劈刺", "atk", 1, 4, 0, "", True),
        ("连刺", "atk", 2, 4, 0, "", True),
        ("割裂", "atk", 2, 3, 0, "bleed2", True),
    ]),
    "长刀(双手,近)": ("m", [
        ("斩击", "atk", 1, 7, 0, "", True),
        ("旋斩", "atk", 2, 4, 0, "", True),
        ("斩破", "atk", 3, 10, 0, "", True),
    ]),
    "重斧(单手,近)": ("m", [
        ("劈砍", "atk", 2, 8, 0, "", True),
        ("震地", "atk", 2, 5, 0, "stun", True),
        ("碎甲", "atk", 3, 6, 0, "", True),
    ]),
    "手枪(单手,远)": ("r", [
        ("点射", "atk", 1, 4, 0, "", False),
        ("双发", "atk", 1, 4, 0, "", False),
        ("校准射击", "atk", 2, 6, 0, "", False),
    ]),
    "突击步枪(单手,远)": ("r", [
        ("连射", "atk", 2, 6, 0, "", False),
        ("压制", "atk", 2, 3, 0, "", False),
        ("精确打击", "atk", 3, 9, 0, "", False),
    ]),
    "霰弹枪(双手,远)": ("r", [
        ("散射", "atk", 2, 6, 0, "", False),
        ("近距离", "atk", 2, 10, 0, "", False),
        ("贯穿", "atk", 3, 8, 0, "", False),
    ]),
}


def play_battle(deck, rng, enemy, tier, weapon_kind):
    _, ehp, eatk, immune_len, taunt_every = enemy
    _, t_dmg, t_shield, t_hp, t_energy = tier
    draw_pile = deck[:]
    rng.shuffle(draw_pile)
    discard, hand = [], []
    php = PLAYER_HP + t_hp
    max_hp = php
    turns = 0
    stunned = False
    immune = 0
    next_bonus = 0
    bleed = 0
    while ehp > 0 and php > 0 and turns < 60:
        turns += 1
        taunted = taunt_every and turns % taunt_every == 0
        defended_first = False
        shield = 0
        reduce = 0.0
        for _ in range(DRAW):
            if not draw_pile:
                rng.shuffle(discard)
                draw_pile.extend(discard)
                discard.clear()
                if not draw_pile:
                    break
            hand.append(draw_pile.pop())
        energy = ENERGY + t_energy

        def key(c):
            name, typ, cost, dmg, sh, note, melee = c
            if "stun" in note and immune == 0:
                return (0, 0)
            if taunted and typ == "def":
                return (1, cost)   # 嘲讽回合先出一张防御
            if typ == "atk":
                return (2, -(dmg / max(cost, 1)))
            if typ == "aux":
                return (3, cost)
            return (4, -(sh / max(cost, 1)))

        order = sorted(hand, key=key)
        played = []
        for c in order:
            name, typ, cost, dmg, sh, note, melee = c
            if cost > energy:
                continue
            if typ == "def" and stunned:
                continue
            if "stun" in note and immune > 0:
                # 免疫期内击晕无效，只当普通攻击
                pass
            # 嘲讽回合：只先出一张防御，之后不再出防御
            if taunted and typ == "def" and defended_first:
                continue
            energy -= cost
            played.append(c)
            if typ == "atk":
                d = dmg + next_bonus
                mult = 1.0 + t_dmg
                if (weapon_kind == "m" and melee) or (weapon_kind == "r" and not melee):
                    mult += TYPE_BONUS
                d *= mult
                if taunted and not defended_first:
                    d *= 0.5
                if "stun" in note and immune == 0:
                    stunned = True
                    immune = immune_len
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
                    php = min(max_hp, php + 4)
                shield += sh
        for c in played:
            hand.remove(c)
            discard.append(c)
        if bleed > 0 and ehp > 0:
            ehp -= bleed
        if ehp <= 0:
            break
        if immune > 0 and not stunned:
            immune -= 1
        if stunned:
            stunned = False
        else:
            php -= max(0, eatk - shield) * (1 - reduce)
        discard.extend(hand)
        hand.clear()
    return turns, php


def run(kind, cards, enemy, tier, runs=RUNS, seed=11):
    rng = random.Random(seed)
    deck = BASE + ARMOR + cards
    turns, hp, win = [], [], 0
    for _ in range(runs):
        t, p = play_battle(deck, rng, enemy, tier, kind)
        turns.append(t)
        hp.append(max(p, 0))
        if p > 0:
            win += 1
    return statistics.mean(turns), win / runs, statistics.mean(hp)


def main():
    for enemy in ENEMIES:
        print(f"== {enemy[0]} ==")
        header = f"{'武器':<18}" + "".join(f"{t[0]:>16}" for t in TIERS)
        print(header + "    (胜率 / 平均回合)")
        for wname, (kind, cards) in WEAPONS.items():
            row = f"{wname:<18}"
            for tier in TIERS:
                t, w, _ = run(kind, cards, enemy, tier)
                row += f"{w:>9.1%}/{t:>5.1f}  "
            print(row)
        print()


if __name__ == "__main__":
    main()
