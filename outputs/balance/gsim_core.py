"""贪心战斗模拟内核 v0.29：卡牌文本解析 + 单场战斗（玩家贪心出牌）。

口径（刻意简化，只用来估怪物水平）：
- 玩家 100 生命，每回合 3 能源，抽 5 张，回合结束手牌全弃，护盾每回合清零。
- 敌人意图公开：玩家贪心出牌时知道本回合要吃多少伤害。
- 条件触发的效果按 0.65 折算（与预算模型一致）；解析不了的机制，用预算价值差额折成伤害/护盾。
- 供能修正、朝向、套装加成、分段单独触发的命中效果均未模拟。
"""
# ruff: noqa: E501
import random
import re
from collections import defaultdict

DMG_PER_E = 6.0
COND = re.compile(r"击杀|若|低于|带|已破盾|异常状态|距离\s*3|每打出|当|上一张|之前|目标有|每受到|首次受")
KEYS = ("dmg", "aoe", "shield", "shield_next", "heal", "draw", "energy", "stun",
        "nextatk", "turnatk", "dot", "edown", "costdown", "selfdmg")

PLAYER_HP = 100
ENERGY = 3
DRAW = 5
HAND_MAX = 10
MAX_PLAYS = 14


# ---------------------------------------------------------------- 文本解析
def _parse_seg(seg):
    s = seg
    part = defaultdict(float)
    hits = 1

    def take(pat, key, scale=1.0):
        nonlocal s
        for m in re.finditer(pat, s):
            part[key] += float(m.group(1)) * scale
        s = re.sub(pat, " ", s)

    take(r"(?:全体|所有敌人)受到\s*(\d+)\s*(?:点)?伤害", "aoe")
    take(r"自己受到\s*(\d+)\s*(?:点)?伤害", "selfdmg")
    take(r"(?<![到体人])受\s*(\d+)\s*(?:点)?伤害", "selfdmg")
    take(r"(?:所有|全体)敌人各\s*-?(\d+)", "aoe")
    take(r"随机(?:两|2)名敌人各\s*-?(\d+)", "dmg", 1.7)
    m = re.search(r"(?:伤害\s*\+?(\d+)|(\d+)\s*伤害)\s*[×x]\s*(\d+)\s*段", s)
    if m:
        n = float(m.group(1) or m.group(2))
        hits = int(m.group(3))
        part["dmg"] += n * hits
        s = s.replace(m.group(0), " ", 1)
    take(r"伤害\s*\+(\d+)(?!%)", "dmg")
    take(r"造成\s*(\d+)\s*伤害", "dmg")
    take(r"(\d+)\s*伤害", "dmg")
    if part["dmg"] and part["aoe"] == 0 and re.search(r"全体|所有敌人", seg):
        part["aoe"] = part["dmg"]
        part["dmg"] = 0.0
    take(r"下回合(?:开始时)?护盾\s*\+(\d+)", "shield_next")
    take(r"护盾\s*\+?(\d+)", "shield")
    take(r"(\d+)\s*护盾", "shield")
    take(r"回复\s*(\d+)\s*(?:点)?生命", "heal")
    take(r"回复\s*(\d+)\s*(?:点)?能源", "energy")
    take(r"能源\s*\+(\d+)", "energy")
    take(r"抽\s*(\d+)\s*张", "draw")
    take(r"弃\s*(\d+)\s*张", "draw", -0.35)
    take(r"(?:流血|中毒|灼烧)\s*\+?(\d+)", "dot")
    take(r"接下来\s*2\s*张攻击(?:牌)?各\s*\+(\d+)", "nextatk", 2.0)
    take(r"下一张(?:\S{0,3})?攻击(?:牌)?(?:伤害)?\s*\+(\d+)", "nextatk")
    take(r"本回合(?:所有)?(?:攻击牌?|每次攻击)(?:伤害)?\s*\+(\d+)", "turnatk")
    if re.search(r"费用\s*-1", s):
        part["costdown"] += 1.0
    take(r"(\d+)%\s*击晕", "stun", 0.01)
    if "必定击晕" in s:
        part["stun"] += 1.0
    take(r"(?:目标|敌人)(?:下回合|下一次|下次)?(?:的)?攻击(?:伤害)?\s*-(\d+)", "edown")
    take(r"本回合敌人(?:首次)?攻击伤害\s*-(\d+)", "edown")
    return part, hits


def parse(text):
    total = defaultdict(float)
    hits = 1
    for seg in re.split(r"[；;]", text):
        part, h = _parse_seg(seg)
        factor = 0.65 if COND.search(seg) else 1.0
        for key, val in part.items():
            total[key] += val * factor
        hits = max(hits, h)
    total["hits"] = float(hits)
    return total


def comp_e(v):
    e = (v["dmg"] + v["aoe"] * 1.6 + v["dot"] * 1.5 + v["nextatk"] * 0.8 + v["turnatk"] * 2.0) / DMG_PER_E
    e += (v["shield"] + v["shield_next"] * 0.8) / DMG_PER_E
    e += v["heal"] * 1.3 / DMG_PER_E + v["draw"] * 0.4 + v["energy"] * 0.9
    e += v["stun"] * 2.0 + v["edown"] / DMG_PER_E + v["costdown"] * 0.7
    return e


class Card:
    """一张可打出的牌。v 为效果分量字典；est 为动态估值（梗武器用）；special 为额外结算。"""

    def __init__(self, name, cost, v, exhaust=False, special=None, est=None, kind="x", uext=None):
        self.name = name
        self.cost = cost
        self.v = v
        self.exhaust = exhaust
        self.special = special
        self.est = est
        self.kind = kind
        self.uext = uext
        self.hpcost = 0
        self.cost_adj = 0

    def clone(self):
        c = Card(self.name, self.cost, defaultdict(float, self.v), self.exhaust, self.special, self.est, self.kind, self.uext)
        c.hpcost = self.hpcost
        return c

    @property
    def is_attack(self):
        return self.v["dmg"] > 0 or self.v["aoe"] > 0


def make_card(name, cost, text, target_e, hint="atk", extra=None):
    """文本解析 + 把预算价值与解析价值的差额折成伤害/护盾。hint: atk/def/mix"""
    v = parse(text)
    for key in KEYS:
        v.setdefault(key, 0.0)
    if extra:
        for key, val in extra.items():
            v[key] += val
    left = target_e - comp_e(v)
    if left > 0.05:
        pts = left * DMG_PER_E
        offense = v["dmg"] + v["aoe"] > 0
        defense = v["shield"] > 0
        if hint == "def" and not offense:
            v["shield"] += pts
        elif offense and not defense:
            v["dmg"] += pts if v["aoe"] == 0 else 0
            v["aoe"] += pts / 1.6 if v["aoe"] > 0 else 0
        elif defense and not offense:
            v["shield"] += pts
        elif offense and defense:
            v["dmg"] += pts * 0.5
            v["shield"] += pts * 0.5
        elif hint == "def":
            v["shield"] += pts
        else:
            v["dmg"] += pts * 0.6
            v["shield"] += pts * 0.4
    exhaust = "消耗" in text
    return Card(name, cost, v, exhaust=exhaust)


# ---------------------------------------------------------------- 敌人
class Enemy:
    def __init__(self, hp, pattern, boss=False, phases=None, enrage_turn=99, enrage_rate=0.1, name="敌"):
        self.name = name
        self.maxhp = hp
        self.hp = hp
        self.pattern = pattern
        self.boss = boss
        self.phases = list(phases or [])
        self.enrage_turn = enrage_turn
        self.enrage_rate = enrage_rate
        self.dot = 0.0
        self.flat_dot = []
        self.stunned = False
        self.immune = 0
        self.edown = 0.0
        self.idx = 0

    @property
    def alive(self):
        return self.hp > 0

    def intent(self, turn):
        base = self.pattern[self.idx % len(self.pattern)]
        if turn >= self.enrage_turn:
            base *= 1.0 + self.enrage_rate * (turn - self.enrage_turn + 1)
        return base


# ---------------------------------------------------------------- 战斗
class Fight:
    def __init__(self, deck, enemies, rng, passive=None, ult=None):
        self.rng = rng
        self.enemies = enemies
        self.hp = PLAYER_HP
        self.maxhp = PLAYER_HP
        self.shield = 0.0
        self.shield_carry = 0.0
        self.energy = 0
        self.energy_next = 0
        self.draw_next = 0
        self.hand = []
        self.draw_pile = [c.clone() for c in deck]
        rng.shuffle(self.draw_pile)
        self.discard = []
        self.exhausted = []
        self.passive = passive or {}
        self.next_atk = 0.0
        self.turn_atk = 0.0
        self.atk_flat = 0.0
        self.cost_next = 0
        self.cost_turn = 0
        self.cost_plus_next_turn = 0
        self.cost_plus_cards = 0
        self.no_shield = False
        self.turn = 0
        self.hp_lost = 0.0
        self.played_this_turn = []
        self.flags = defaultdict(float)
        self.end_hooks = []
        self.start_hooks = []
        self.hurt_hooks = []
        self.dmg_taken_turn = 0.0

    # ---- 牌堆
    def draw_cards(self, n):
        for _ in range(int(n)):
            if len(self.hand) >= HAND_MAX:
                return
            if not self.draw_pile:
                if not self.discard:
                    return
                self.draw_pile = self.discard
                self.discard = []
                self.rng.shuffle(self.draw_pile)
            self.hand.append(self.draw_pile.pop())

    def reshuffle_all(self):
        self.draw_pile.extend(self.discard)
        self.discard = []
        self.rng.shuffle(self.draw_pile)

    # ---- 查询
    def alive_enemies(self):
        return [e for e in self.enemies if e.alive]

    def target(self):
        alive = self.alive_enemies()
        return min(alive, key=lambda e: e.hp) if alive else None

    def intent_of(self, e):
        if e.stunned and e.immune <= 0:
            return 0.0
        return max(0.0, e.intent(self.turn) - e.edown)

    def incoming(self):
        return sum(self.intent_of(e) for e in self.alive_enemies())

    def cost_of(self, card):
        c = card.cost - self.cost_turn - self.cost_next
        if self.cost_plus_cards > 0:
            c += 1
        return max(0, c + card.cost_adj)

    # ---- 估值
    def vals(self, card):
        return card.est(self) if card.est else card.v

    def utility(self, card):
        v = self.vals(card)
        u = 0.0
        hits = max(1.0, v.get("hits", 1.0))
        flat = self.turn_atk + self.atk_flat
        tgt = self.target()
        if tgt is None:
            return 0.0
        if v["dmg"] > 0:
            d = v["dmg"] + self.next_atk + flat * hits
            u += min(d, tgt.hp)
            if d >= tgt.hp:
                u += 0.6 * self.intent_of(tgt)
        if v["aoe"] > 0:
            for e in self.alive_enemies():
                d = v["aoe"] + flat
                u += min(d, e.hp)
                if d >= e.hp:
                    u += 0.6 * self.intent_of(e)
        if v["dot"] > 0:
            u += v["dot"] * 1.5 * 0.9
        inc = self.incoming()
        need = max(0.0, inc - self.shield)
        frac = self.hp / self.maxhp
        wdef = 0.85 + 1.4 * (1.0 - frac)
        if inc - self.shield >= self.hp - 6:
            wdef += 3.0
        if not self.no_shield:
            u += wdef * min(v["shield"], need)
            u += 0.5 * wdef * min(v["shield_next"], inc)
        u += wdef * min(v["edown"], self.intent_of(tgt))
        u += 0.9 * min(v["heal"], self.maxhp - self.hp)
        others = [c for c in self.hand if c is not card]
        has_atk = any(c.is_attack for c in others)
        n_atk = sum(1 for c in others if c.is_attack)
        if v["draw"]:
            u += 2.4 * v["draw"] * (1.0 if self.energy > self.cost_of(card) else 0.35)
        if v["energy"]:
            u += 5.0 * v["energy"] * (1.0 if any(c.cost >= 1 for c in others) else 0.2)
        if v["nextatk"]:
            u += v["nextatk"] * 0.9 * (1.0 if has_atk else 0.1)
        if v["turnatk"]:
            u += v["turnatk"] * 0.8 * min(n_atk, 3) * (1.0 if has_atk else 0.1)
        if v["costdown"]:
            u += 4.0 if any(self.cost_of(c) >= 1 for c in others) else 0.0
        if v["stun"] and not (tgt.boss and tgt.immune > 0) and not tgt.stunned:
            u += v["stun"] * self.intent_of(tgt) * 1.0
        u -= v["selfdmg"] * (0.9 + (1.0 - frac))
        u -= card.hpcost * (0.9 + (1.0 - frac))
        if card.uext:
            u += card.uext(self)
        return u

    # ---- 打牌
    def apply(self, card):
        v = self.vals(card)
        hits = max(1.0, v.get("hits", 1.0))
        flat = self.turn_atk + self.atk_flat
        tgt = self.target()
        if v["dmg"] > 0 and tgt is not None:
            d = v["dmg"] + self.next_atk + flat * hits
            self.next_atk = 0.0
            self.damage(tgt, d)
        if v["aoe"] > 0:
            for e in self.alive_enemies():
                self.damage(e, v["aoe"] + flat)
            self.next_atk = 0.0
        if v["dot"] > 0:
            t2 = self.target()
            if t2 is not None:
                t2.dot += v["dot"]
        if v["shield"] and not self.no_shield:
            self.shield += v["shield"]
        self.shield_carry += v["shield_next"]
        if v["heal"]:
            self.hp = min(self.maxhp, self.hp + v["heal"])
        if v["energy"]:
            self.energy += int(round(v["energy"]))
        if v["nextatk"]:
            self.next_atk += v["nextatk"]
        if v["turnatk"]:
            self.turn_atk += v["turnatk"]
        if v["costdown"]:
            self.cost_next = 1
        if v["edown"]:
            t3 = max(self.alive_enemies(), key=lambda e: e.intent(self.turn), default=None)
            if t3 is not None:
                t3.edown += v["edown"]
        if v["stun"]:
            t4 = max(self.alive_enemies(), key=lambda e: e.intent(self.turn), default=None)
            if t4 is not None and not (t4.boss and t4.immune > 0) and self.rng.random() < v["stun"]:
                t4.stunned = True
        if v["selfdmg"]:
            self.hurt_self(v["selfdmg"])
        if v["draw"]:
            n = v["draw"]
            if n >= 1:
                self.draw_cards(int(round(n)))
        if card.hpcost:
            self.hurt_self(card.hpcost)

    def damage(self, e, d):
        if d <= 0 or not e.alive:
            return
        e.hp -= d
        if e.hp <= 0 and e.phases:
            hp, pat = e.phases.pop(0)
            e.hp = hp
            e.maxhp = hp
            e.pattern = pat
            e.idx = 0
            e.dot = 0.0
            e.stunned = False
            e.edown = 0.0

    def hurt_self(self, d):
        self.hp -= d
        self.hp_lost += d

    def play(self, card):
        card_cost = self.cost_of(card)
        self.energy -= card_cost
        self.hand.remove(card)
        self.cost_next = 0
        if self.cost_plus_cards > 0:
            self.cost_plus_cards -= 1
        self.apply(card)
        if card.special:
            card.special(self, card)
        self.played_this_turn.append(card)
        if card.exhaust:
            self.exhausted.append(card)
        else:
            self.discard.append(card)

    def play_phase(self):
        for _ in range(MAX_PLAYS):
            if not self.alive_enemies() or self.hp <= 0:
                break
            best, best_r = None, 0.0
            for card in self.hand:
                c = self.cost_of(card)
                if c > self.energy:
                    continue
                u = self.utility(card)
                if u <= 0.3:
                    continue
                r = u / max(c, 0.5)
                if r > best_r:
                    best, best_r = card, r
            if best is None:
                break
            self.play(best)

    # ---- 回合
    def run(self, max_turns=60):
        passive = self.passive
        for turn in range(1, max_turns + 1):
            self.turn = turn
            self.shield = self.shield_carry + passive.get("shield", 0.0)
            self.shield_carry = 0.0
            self.energy = ENERGY + self.energy_next + int(passive.get("energy", 0.0))
            self.energy_next = 0
            self.turn_atk = passive.get("turnatk", 0.0)
            self.next_atk = 0.0
            self.cost_turn = 0
            self.cost_next = 0
            self.cost_plus_cards = self.cost_plus_next_turn
            self.cost_plus_next_turn = 0
            self.played_this_turn = []
            self.dmg_taken_turn = 0.0
            for hook in list(self.start_hooks):
                hook(self)
            self.draw_cards(DRAW + self.draw_next + int(passive.get("draw", 0.0)))
            self.draw_next = 0
            self.play_phase()
            for hook in list(self.end_hooks):
                hook(self)
            self.discard.extend(self.hand)
            self.hand = []
            if not self.alive_enemies():
                return turn, True
            if self.hp <= 0:
                return turn, False
            self.enemy_phase()
            if self.hp <= 0:
                return turn, False
            if not self.alive_enemies():
                return turn, True
        return max_turns, False

    def enemy_phase(self):
        for e in self.alive_enemies():
            if e.immune > 0:
                e.immune -= 1
            if e.stunned:
                e.stunned = False
                if e.boss or e.phases:
                    e.immune = 2
                e.idx += 1
                e.edown = 0.0
                continue
            d = max(0.0, e.intent(self.turn) - e.edown)
            e.edown = 0.0
            e.idx += 1
            blocked = min(self.shield, d)
            self.shield -= blocked
            dealt = d - blocked
            if dealt > 0:
                self.hp -= dealt
                self.hp_lost += dealt
                self.dmg_taken_turn += dealt
                for hook in list(self.hurt_hooks):
                    hook(self, dealt)
        for e in self.alive_enemies():
            if e.dot > 0:
                e.hp -= e.dot
                e.dot = max(0.0, e.dot - 1.0)
            if e.flat_dot:
                e.hp -= e.flat_dot[0][0]
                e.flat_dot[0][1] -= 1
                if e.flat_dot[0][1] <= 0:
                    e.flat_dot.pop(0)
        for e in self.enemies:
            if e.hp <= 0 and e.phases:
                hp, pat = e.phases.pop(0)
                e.hp = hp
                e.maxhp = hp
                e.pattern = pat
                e.idx = 0


def seeded(seed):
    return random.Random(seed)
