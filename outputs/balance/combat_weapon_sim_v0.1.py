"""首版武器粗模拟（v0.1）。

目的：比较单把武器在固定基础卡组下的节奏，检查费用与伤害是否大致持平。
口径（粗略，仅作起点）：
- 每回合 3 点能源，抽 5 张，打完或能源耗尽结束回合。
- 手部芯片近战卡 +20% 伤害；远程无加成。
- 基础卡：手 2 + 脚 2（固定），通用 4（固定），防具 3 件 × 2 张（固定）。
- 敌人 HP 40，每回合攻击 6；击晕类技能让敌人跳过一次攻击。
- 攻击/防御供能阈值类卡暂按"已满足"处理（未模拟供能分配）。
- 玩家生命 60。
"""
import random
import statistics

PLAYER_HP = 60
ENEMY_HP = 40
ENEMY_ATK = 6
ENERGY = 3
DRAW = 5
RUNS = 3000
MELEE_BONUS = 1.2

# 卡: (名称, 类型 atk/def/aux, 费用, 伤害, 护盾, 备注)
# 备注: stun=击晕，reduce=减伤比例，heal=治疗
BASE = [
    ("徒手攻击", "atk", 1, 2, 0, "", False),
    ("格挡", "def", 1, 0, 3, "", False),
    ("踢击", "atk", 1, 2, 0, "", False),
    ("闪避", "def", 1, 0, 2, "", False),
    ("瞄准", "aux", 1, 0, 0, "next+2", False),
    ("急救", "aux", 2, 0, 0, "heal4", False),
    ("强化格挡", "def", 2, 0, 6, "", False),
    ("突袭", "atk", 2, 5, 0, "", False),
]
ARMOR = [
    ("轻甲格挡", "def", 1, 0, 4, "", False),
    ("轻甲减伤", "def", 2, 0, 0, "reduce20", False),
] * 3

WEAPONS = {
    "短刃(单手,近)": (True, [
        ("劈刺", "atk", 1, 4, 0, "", True),
        ("连刺", "atk", 2, 4, 0, "", True),   # 两段各2
        ("割裂", "atk", 2, 3, 0, "bleed2", True),
    ]),
    "长刀(双手,近)": (True, [
        ("斩击", "atk", 1, 7, 0, "", True),
        ("旋斩", "atk", 2, 4, 0, "", True),
        ("斩破", "atk", 3, 10, 0, "", True),
    ]),
    "重斧(单手,近)": (True, [
        ("劈砍", "atk", 2, 8, 0, "", True),
        ("震地", "atk", 2, 5, 0, "stun", True),
        ("碎甲", "atk", 3, 6, 0, "", True),
    ]),
    "手枪(单手,远)": (False, [
        ("点射", "atk", 1, 4, 0, "", False),
        ("双发", "atk", 1, 4, 0, "", False),  # 两段各2
        ("校准射击", "atk", 2, 6, 0, "", False),
    ]),
    "突击步枪(单手,远)": (False, [
        ("连射", "atk", 2, 6, 0, "", False),  # 3×2
        ("压制", "atk", 2, 3, 0, "", False),
        ("精确打击", "atk", 3, 9, 0, "", False),
    ]),
    "霰弹枪(双手,远)": (False, [
        ("散射", "atk", 2, 6, 0, "", False),
        ("近距离", "atk", 2, 10, 0, "", False),
        ("贯穿", "atk", 3, 8, 0, "", False),
    ]),
}


def build_deck(weapon_cards, melee):
    deck = []
    for c in BASE + ARMOR + weapon_cards:
        deck.append(c)
    return deck


def play_battle(deck, rng):
    draw_pile = deck[:]
    rng.shuffle(draw_pile)
    discard = []
    hand = []
    php, ehp = PLAYER_HP, ENEMY_HP
    turns = 0
    dealt = 0
    stunned = False
    next_bonus = 0
    while ehp > 0 and php > 0 and turns < 40:
        turns += 1
        shield = 0
        reduce = 0.0
        # 抽牌
        for _ in range(DRAW):
            if not draw_pile:
                rng.shuffle(discard)
                draw_pile.extend(discard)
                discard.clear()
                if not draw_pile:
                    break
            hand.append(draw_pile.pop())
        energy = ENERGY
        # 简单贪心：先攻击(按伤害/费用)，再防御，再辅助
        order = sorted(hand, key=lambda c: (c[1] != "atk", -(c[3] / max(c[2], 1))))
        played = []
        for c in order:
            name, typ, cost, dmg, sh, note, melee = c
            if cost > energy:
                continue
            energy -= cost
            played.append(c)
            if typ == "atk":
                d = dmg + next_bonus
                if melee:
                    d *= MELEE_BONUS
                if "stun" in note:
                    stunned = True
                dealt += d
                ehp -= d
                next_bonus = 0
            elif typ == "def":
                shield += sh
                if "reduce" in note:
                    reduce = 0.2
            else:
                if "next" in note:
                    next_bonus = 2
                if "heal" in note:
                    php = min(PLAYER_HP, php + 4)
        for c in played:
            hand.remove(c)
            discard.append(c)
        # 敌方回合
        if stunned:
            stunned = False
        else:
            incoming = max(0, ENEMY_ATK - shield) * (1 - reduce)
            php -= incoming
        # 手牌未出的保留到下回合（简化：全部回收进弃牌）
        discard.extend(hand)
        hand.clear()
    return turns, dealt, php


def run(name, melee, weapon_cards, runs=RUNS, seed=1):
    rng = random.Random(seed)
    deck = build_deck(weapon_cards, melee)
    turns_list, dmg_list, hp_list, win = [], [], [], 0
    for _ in range(runs):
        t, d, hp = play_battle(deck, rng)
        turns_list.append(t)
        dmg_list.append(d)
        hp_list.append(hp)
        if hp > 0:
            win += 1
    return {
        "name": name,
        "turns": statistics.mean(turns_list),
        "dmg_per_turn": statistics.mean(dmg_list) / statistics.mean(turns_list),
        "winrate": win / runs,
        "hp_left": statistics.mean(hp_list),
    }


def main():
    print(f"{'武器':<18}{'平均回合':>8}{'每回合伤害':>10}{'胜率':>8}{'剩余生命':>10}")
    for name, (melee, cards) in WEAPONS.items():
        r = run(name, melee, cards)
        print(f"{r['name']:<18}{r['turns']:>8.2f}{r['dmg_per_turn']:>10.2f}{r['winrate']:>8.1%}{r['hp_left']:>10.1f}")


if __name__ == "__main__":
    main()
