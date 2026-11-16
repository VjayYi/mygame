"""首版武器粗模拟 v0.2。

相对 v0.1 的修正：
- 卡组加入大脑、躯干各 1 张辅助卡（用户 2026-11-16 22:45 拍板）。
- 增加三种敌人档位（普通/精英/小Boss），v0.1 敌人过弱，胜率全是 100%，无区分度。
- 击晕类卡可让敌人跳过一次预告行动（用户拍板：允许打断）。
- 手部加成不给定数，这里用 MELEE_BONUS 作为参数扫描，默认 +20%，再对 0%/+20%/+40% 比较。
- 未模拟：供能分配、100% 供能附加效果、校准/调取、模块。结果只用于比较武器之间的相对强弱。
"""
import random
import statistics
import sys

PLAYER_HP = 60
ENERGY = 3
DRAW = 5
RUNS = 4000

ENEMIES = {
    "普通(HP40/攻6)": (40, 6),
    "精英(HP80/攻9)": (80, 9),
    "小Boss(HP140/攻11)": (140, 11),
}

# 卡: (名称, 类型, 费用, 伤害, 护盾, 备注, 是否近战)
BASE = [
    ("徒手攻击", "atk", 1, 2, 0, "", True),
    ("踢击", "atk", 1, 2, 0, "", False),
    ("格挡", "def", 1, 0, 3, "", False),
    ("闪避", "def", 1, 0, 2, "", False),
    # 通用 4
    ("瞄准", "aux", 1, 0, 0, "next+2", False),
    ("急救", "aux", 2, 0, 0, "heal4", False),
    ("强化格挡", "def", 2, 0, 6, "", False),
    ("突袭", "atk", 2, 5, 0, "", False),
    # 大脑、躯干各 1 张辅助
    ("超频", "aux", 1, 0, 0, "next+3", False),
    ("加固", "aux", 1, 0, 3, "", False),
]
ARMOR = [
    ("轻甲格挡", "def", 1, 0, 4, "", False),
    ("轻甲减伤", "def", 2, 0, 0, "reduce20", False),
] * 3

WEAPONS = {
    "短刃(单手,近)": [
        ("劈刺", "atk", 1, 4, 0, "", True),
        ("连刺", "atk", 2, 4, 0, "", True),
        ("割裂", "atk", 2, 3, 0, "bleed2", True),
    ],
    "长刀(双手,近)": [
        ("斩击", "atk", 1, 7, 0, "", True),
        ("旋斩", "atk", 2, 4, 0, "", True),
        ("斩破", "atk", 3, 10, 0, "", True),
    ],
    "重斧(单手,近)": [
        ("劈砍", "atk", 2, 8, 0, "", True),
        ("震地", "atk", 2, 5, 0, "stun", True),
        ("碎甲", "atk", 3, 6, 0, "", True),
    ],
    "手枪(单手,远)": [
        ("点射", "atk", 1, 4, 0, "", False),
        ("双发", "atk", 1, 4, 0, "", False),
        ("校准射击", "atk", 2, 6, 0, "", False),
    ],
    "突击步枪(单手,远)": [
        ("连射", "atk", 2, 6, 0, "", False),
        ("压制", "atk", 2, 3, 0, "", False),
        ("精确打击", "atk", 3, 9, 0, "", False),
    ],
    "霰弹枪(双手,远)": [
        ("散射", "atk", 2, 6, 0, "", False),
        ("近距离", "atk", 2, 10, 0, "", False),
        ("贯穿", "atk", 3, 8, 0, "", False),
    ],
}


def play_battle(deck, rng, ehp, eatk, melee_bonus):
    draw_pile = deck[:]
    rng.shuffle(draw_pile)
    discard = []
    hand = []
    php = PLAYER_HP
    turns = 0
    stunned = False
    next_bonus = 0
    bleed = 0
    while ehp > 0 and php > 0 and turns < 40:
        turns += 1
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
        energy = ENERGY
        # 贪心：击晕优先（能打断敌人），其次高效率攻击，再防御/辅助
        def key(c):
            name, typ, cost, dmg, sh, note, melee = c
            if "stun" in note:
                return (0, 0)
            if typ == "atk":
                return (1, -(dmg / max(cost, 1)))
            if typ == "aux":
                return (2, cost)
            return (3, -(sh / max(cost, 1)))
        order = sorted(hand, key=key)
        played = []
        for c in order:
            name, typ, cost, dmg, sh, note, melee = c
            if cost > energy:
                continue
            # 防御卡只在敌人没被击晕时才值得出
            if typ == "def" and stunned:
                continue
            energy -= cost
            played.append(c)
            if typ == "atk":
                d = dmg + next_bonus
                if melee:
                    d *= 1 + melee_bonus
                if "stun" in note:
                    stunned = True
                if "bleed" in note:
                    bleed = 2
                ehp -= d
                next_bonus = 0
            elif typ == "def":
                shield += sh
                if "reduce" in note:
                    reduce = 0.2
            else:
                if "next" in note:
                    next_bonus = int(note.split("+")[1])
                if "heal" in note:
                    php = min(PLAYER_HP, php + 4)
                shield += sh
        for c in played:
            hand.remove(c)
            discard.append(c)
        if bleed > 0 and ehp > 0:
            ehp -= bleed
        if ehp <= 0:
            break
        if stunned:
            stunned = False
        else:
            php -= max(0, eatk - shield) * (1 - reduce)
        discard.extend(hand)
        hand.clear()
    return turns, php


def run(weapon_cards, enemy, melee_bonus, runs=RUNS, seed=7):
    rng = random.Random(seed)
    deck = BASE + ARMOR + weapon_cards
    ehp, eatk = enemy
    turns, hp, win = [], [], 0
    for _ in range(runs):
        t, p = play_battle(deck, rng, ehp, eatk, melee_bonus)
        turns.append(t)
        hp.append(max(p, 0))
        if p > 0:
            win += 1
    return statistics.mean(turns), win / runs, statistics.mean(hp)


def main():
    bonus = float(sys.argv[1]) if len(sys.argv) > 1 else 0.2
    print(f"手部近战加成 = {bonus:+.0%}，卡组 {len(BASE) + len(ARMOR) + 3} 张\n")
    for ename, enemy in ENEMIES.items():
        print(f"== {ename} ==")
        print(f"{'武器':<18}{'回合':>6}{'胜率':>8}{'剩余生命':>10}")
        for wname, cards in WEAPONS.items():
            t, w, hp = run(cards, enemy, bonus)
            print(f"{wname:<18}{t:>6.2f}{w:>8.1%}{hp:>10.1f}")
        print()


if __name__ == "__main__":
    main()
