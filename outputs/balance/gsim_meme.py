"""骰面异能武器（玩梗）的模拟实现 v0.29：6 把 × 5 张，期望值近似。

近似说明：十连按期望值结算；卸载重下简化为抽 2；Ctrl+C/V 复制手牌里价值最高的牌；爆裂魔法后下回合能源为 0；
外卖"配送中"2 回合后送达（费用 -1，伤害/护盾 +3）。梗武器不带模块，所以没有终极卡。
"""
# ruff: noqa: E501
from collections import defaultdict

from gsim_core import KEYS, Card, comp_e

TEXT = {
    "和我签订契约吧": "选择手牌 1 张牌：本场战斗内伤害/护盾 +4，之后每次打出它失去 2 生命",
    "变身！": "【消耗】接下来 2 回合攻击牌伤害 +4；第 3 回合起进入【黑化】直到战斗结束：攻击牌 +2，无法获得护盾，回合开始失去 2 生命",
    "已经没什么好怕的了": "本回合攻击牌伤害 +3；回合结束时若生命 ≤50% 受到 8 伤害，否则回复 3 生命",
    "魔杖其实是平底锅": "伤害 3，并投 d6：1~2 煎蛋再 4 伤害；3~4 锅盖护盾 4；5 抽 1 张；6 全体 3 伤害",
    "魔法少女·俺": "造成当前护盾 ×1.5 的伤害，随后护盾减半（向上取整）",
    "单抽": "伤害 5，保底 +1；30% 歪了：保底改为 +3",
    "十连！": "10 次抽取：55% 凡品 1 伤害 / 35% 稀有护盾 1 / SSR（10%+3%×保底）全体 5 伤害；结算后保底清空",
    "保底！": "消耗全部保底层，每层 3 伤害（至多 6 层）；保底 ≥4 层时抽 2 张",
    "非酋的怒火": "护盾 4；本回合每受到一次伤害，保底 +1（至多 3 层）",
    "卸载重下": "【消耗】抽 2 张，保底 +2（原案：弃全部手牌后抽等量+1，此处简化）",
    "Ctrl+C": "复制手牌中 1 张牌（不含本卡）放入剪贴板，覆盖旧内容",
    "Ctrl+V": "把剪贴板的牌加入手牌，拷贝带【消耗】且本回合费用为 0",
    "Ctrl+Z": "回复本回合已受伤害的 70%（最多 10，此处折为护盾）并抽 1 张",
    "Alt+F4": "【消耗】目标跳过下次行动；对精英/Boss 无效，改为 10 伤害",
    "rm -rf /": "【消耗】弃置全部手牌，每张对敌 4 伤害；弃置 ≥5 张时本回合免疫伤害",
    "画大饼": "本回合 +2 能源，下回合少抽 2 张",
    "加班": "本回合所有牌费用 -1；下回合前 2 张牌费用 +1",
    "背锅": "本回合受到的下一次伤害 50%（最多 8）改由敌人承受（此处折为护盾+反伤）",
    "保温杯里泡枸杞": "回复 3 生命，之后 3 回合每回合开始回复 1；本回合没打攻击牌（摸鱼）额外回复 3",
    "KPI 考核": "回合结束时，本回合每打出 1 种不同费用的牌，全体 2 伤害（至多 4 种）；≥3 种抽 2 张",
    "吃我这招·暗黑火焰": "伤害 5，获得 1 层封印",
    "我的右手……在疼……": "护盾 3；本回合每受到一次伤害获得 1 层封印（至多 3 层）",
    "解除封印！": "消耗 2 层封印：本回合攻击牌 +4 并抽 1 张；不足 2 层反噬：受 3 伤害，+1 层封印",
    "邪王真眼": "选 1 名敌人：其下次攻击 -50%（至多 -6）",
    "爆裂魔法": "【消耗】消耗全部封印，每层对全体 6 伤害；之后倒地：下回合能源为 0；封印为 0 哑火，受 3 伤害",
    "您有一份外卖": "选手牌 1 张放入【配送中】，2 回合后送达：费用 -1，伤害/护盾 +3",
    "加急配送": "所有配送中的牌立即送达（无加成），抽 1 张",
    "差评！": "伤害 3，目标获得差评：每回合开始受 2 伤害，持续 2 回合",
    "五星好评": "护盾 4；本回合有牌送达时额外护盾 +4、回复 1 能源",
    "闯红灯！": "伤害 9，自己受 3 伤害；本回合有牌送达时免除罚单，伤害 +3",
}


def V(**kw):
    v = defaultdict(float)
    for key in KEYS:
        v[key] = 0.0
    v["hits"] = 1.0
    for key, val in kw.items():
        v[key] = float(val)
    return v


def _others(g, card=None):
    return [c for c in g.hand if c is not card]


def _best_other(g, key=None):
    return max(g.hand, key=key or (lambda c: comp_e(c.v)), default=None)


def _flag_hook(g):
    def hook(gg):
        if gg.hp <= gg.maxhp * 0.5:
            gg.hurt_self(8)
        else:
            gg.hp = min(gg.maxhp, gg.hp + 3)
        gg.end_hooks.remove(hook)

    g.end_hooks.append(hook)


def _mk(name, cost, v=None, est=None, special=None, uext=None, exhaust=False):
    return Card(name, cost, v if v is not None else V(), exhaust=exhaust, special=special, est=est, kind="meme", uext=uext,
                text=TEXT.get(name, ""))


# ---------------------------------------------------------------- 1 魔法少女的法杖
def _contract(g, card):
    cand = [c for c in g.hand if c.is_attack] or [c for c in g.hand if c.v["shield"] > 0]
    if not cand:
        return
    t = max(cand, key=lambda c: c.v["dmg"] + c.v["aoe"] + c.v["shield"])
    key = "dmg" if t.v["dmg"] > 0 else ("aoe" if t.v["aoe"] > 0 else "shield")
    t.v[key] += 4
    t.hpcost += 2


def _transform(g, card):
    g.flags["transform"] = 2
    g.atk_flat += 4

    def hook(gg):
        if gg.flags["dark"]:
            gg.hurt_self(2)
            return
        if gg.flags["transform"] > 0:
            gg.flags["transform"] -= 1
            if gg.flags["transform"] == 0:
                gg.atk_flat += -4 + 2
                gg.no_shield = True
                gg.flags["dark"] = 1

    g.start_hooks.append(hook)


def _pan(g, card):
    r = g.rng.randint(1, 6)
    tgt = g.target()
    if r <= 2 and tgt is not None:
        g.damage(tgt, 4)
    elif r <= 4:
        g.shield += 4
    elif r == 5:
        g.draw_cards(1)
    else:
        for e in g.alive_enemies():
            g.damage(e, 3)


def _ore(g, card):
    g.shield = float(-(-g.shield // 2))


def w1():
    return [
        _mk("和我签订契约吧", 1, V(), special=_contract, uext=lambda g: 3.5 if any(c.is_attack for c in g.hand) else 0.0),
        _mk("变身！", 3, V(), special=_transform, exhaust=True, uext=lambda g: 7.0 if g.turn <= 2 and not g.flags["transform"] else 0.0),
        _mk("已经没什么好怕的了", 1, V(turnatk=3), special=lambda g, c: _flag_hook(g),
            uext=lambda g: -2.0 if g.hp <= g.maxhp * 0.5 else 0.0),
        _mk("魔杖其实是平底锅", 1, V(dmg=3), special=_pan),
        _mk("魔法少女·俺", 1, est=lambda g: V(dmg=1.5 * g.shield), special=_ore),
    ]


# ---------------------------------------------------------------- 2 氪金手机
def _pity(g, n):
    g.flags["pity"] = min(8, g.flags["pity"] + n)


def _single(g, card):
    _pity(g, 3 if g.rng.random() < 0.3 else 1)


def _ten(g, card):
    g.flags["pity"] = 0


def _guarantee(g, card):
    g.flags["pity"] = 0


def _fei(g, card):
    g.flags["fei"] = g.turn
    if not g.flags["fei_hook"]:
        g.flags["fei_hook"] = 1

        def hook(gg, dealt):
            if gg.flags["fei"] == gg.turn:
                _pity(gg, 1)

        g.hurt_hooks.append(hook)


def w2():
    return [
        _mk("单抽", 1, V(dmg=5), special=_single),
        _mk("十连！", 3, est=lambda g: V(dmg=5.5, shield=3.5, aoe=50 * min(1.0, 0.10 + 0.03 * g.flags["pity"])), special=_ten),
        _mk("保底！", 1, est=lambda g: V(dmg=3 * min(g.flags["pity"], 6), draw=2 if g.flags["pity"] >= 4 else 0), special=_guarantee),
        _mk("非酋的怒火", 1, V(shield=4), special=_fei),
        _mk("卸载重下", 1, V(draw=2), special=lambda g, c: _pity(g, 2), exhaust=True),
    ]


# ---------------------------------------------------------------- 3 程序员键盘
def _copy(g, card):
    cand = _best_other(g)
    if cand is not None:
        c = cand.clone()
        c.exhaust = True
        g.flags["clip_card"] = c


def _paste(g, card):
    src = g.flags["clip_card"]
    if src:
        c = src.clone()
        c.cost_adj = -c.cost
        g.hand.append(c)


def _alt(g, card):
    pass


def _rmrf(g, card):
    n = len(g.hand)
    g.discard.extend(g.hand)
    g.hand = []
    if n >= 5:
        g.shield += 999


def _alt_est(g):
    tgt = g.target()
    if tgt is not None and tgt.boss:
        return V(dmg=10)
    return V(stun=1.0)


def w3():
    return [
        _mk("Ctrl+C", 1, V(), special=_copy, uext=lambda g: 3.0 if any(comp_e(c.v) >= 1.3 for c in g.hand) else -1.0),
        _mk("Ctrl+V", 1, V(), special=_paste, uext=lambda g: (comp_e(g.flags["clip_card"].v) * 6.0 * 0.9) if g.flags["clip_card"] else -9.0),
        _mk("Ctrl+Z", 1, est=lambda g: V(shield=min(10.0, 0.7 * g.incoming()), draw=1)),
        _mk("Alt+F4", 2, est=_alt_est, special=_alt, exhaust=True),
        _mk("rm -rf /", 3, est=lambda g: V(dmg=4.0 * max(0, len(g.hand) - 1)), special=_rmrf, exhaust=True,
            uext=lambda g: 6.0 if len(g.hand) >= 6 else 0.0),
    ]


# ---------------------------------------------------------------- 4 社畜
def _pie(g, card):
    g.draw_next -= 2


def _overtime(g, card):
    g.cost_turn += 1
    g.cost_plus_next_turn = 2


def _cup(g, card):
    left = [3]

    def start(gg):
        if left[0] > 0:
            left[0] -= 1
            gg.hp = min(gg.maxhp, gg.hp + 1)
            if left[0] == 0:
                gg.start_hooks.remove(start)

    g.start_hooks.append(start)

    def end(gg):
        if not any(c.is_attack for c in gg.played_this_turn):
            gg.hp = min(gg.maxhp, gg.hp + 3)
        gg.end_hooks.remove(end)

    g.end_hooks.append(end)


def _kpi(g, card):
    def end(gg):
        kinds = len({c.cost for c in gg.played_this_turn})
        for e in gg.alive_enemies():
            gg.damage(e, 2 * min(kinds, 4))
        if kinds >= 3:
            gg.draw_next += 2
        gg.end_hooks.remove(end)

    g.end_hooks.append(end)


def w4():
    return [
        _mk("画大饼", 1, V(energy=2), special=_pie),
        _mk("加班", 1, V(), special=_overtime, uext=lambda g: 2.5 * min(3, sum(1 for c in g.hand if c.cost >= 1)) - 2.5),
        _mk("背锅", 1, est=lambda g: V(shield=min(8.0, 0.5 * g.incoming()), dmg=min(8.0, 0.5 * g.incoming()))),
        _mk("保温杯里泡枸杞", 1, V(heal=3), special=_cup, uext=lambda g: 3.0),
        _mk("KPI 考核", 2, V(), special=_kpi, uext=lambda g: 7.0),
    ]


# ---------------------------------------------------------------- 5 中二病
def _seal(g, n):
    g.flags["seal"] = min(6, g.flags["seal"] + n)


def _eat(g, card):
    _seal(g, 1)


def _pain(g, card):
    g.flags["pain"] = g.turn
    g.flags["pain_n"] = 0
    if not g.flags["pain_hook"]:
        g.flags["pain_hook"] = 1

        def hook(gg, dealt):
            if gg.flags["pain"] == gg.turn and gg.flags["pain_n"] < 3:
                gg.flags["pain_n"] += 1
                _seal(gg, 1)

        g.hurt_hooks.append(hook)


def _unseal_est(g):
    if g.flags["seal"] >= 2:
        return V(turnatk=4, draw=1)
    return V(selfdmg=3)


def _unseal(g, card):
    if g.flags["seal"] >= 2:
        g.flags["seal"] -= 2
    else:
        _seal(g, 1)


def _boom_est(g):
    if g.flags["seal"] > 0:
        return V(aoe=6 * g.flags["seal"])
    return V(selfdmg=3)


def _boom(g, card):
    g.flags["seal"] = 0
    g.energy_next = -3


def _eye_est(g):
    mx = max((e.intent(g.turn) for e in g.alive_enemies()), default=0)
    return V(edown=min(6.0, 0.5 * mx))


def w5():
    return [
        _mk("吃我这招·暗黑火焰", 1, V(dmg=5), special=_eat),
        _mk("我的右手……在疼……", 1, V(shield=3), special=_pain),
        _mk("解除封印！", 1, est=_unseal_est, special=_unseal),
        _mk("邪王真眼", 1, est=_eye_est),
        _mk("爆裂魔法", 3, est=_boom_est, special=_boom, exhaust=True, uext=lambda g: 2.0 if g.flags["seal"] >= 3 else -12.0),
    ]


# ---------------------------------------------------------------- 6 外卖保温箱
def _order(g, card):
    cand = _best_other(g)
    if cand is None:
        return
    g.hand.remove(cand)
    q = g.flags["queue"] or []
    q.append([cand, 2])
    g.flags["queue"] = q
    if not g.flags["queue_hook"]:
        g.flags["queue_hook"] = 1

        def hook(gg):
            qq = gg.flags["queue"] or []
            keep = []
            for item in qq:
                item[1] -= 1
                if item[1] <= 0:
                    c = item[0]
                    c.cost_adj -= 1
                    key = "dmg" if c.v["dmg"] > 0 else ("aoe" if c.v["aoe"] > 0 else "shield")
                    c.v[key] += 3
                    gg.hand.append(c)
                    gg.flags["delivered"] = gg.turn
                else:
                    keep.append(item)
            gg.flags["queue"] = keep

        g.start_hooks.append(hook)


def _rush(g, card):
    q = g.flags["queue"] or []
    for item in q:
        g.hand.append(item[0])
    if q:
        g.flags["delivered"] = g.turn
    g.flags["queue"] = []


def _bad(g, card):
    t = g.target()
    if t is not None:
        t.flat_dot.append([2, 2])


def _star_est(g):
    d = 1 if g.flags["delivered"] == g.turn and g.turn > 0 else 0
    return V(shield=4 + 4 * d, energy=1 * d)


def _red_est(g):
    d = 1 if g.flags["delivered"] == g.turn and g.turn > 0 else 0
    return V(dmg=9 + 3 * d, selfdmg=3 * (1 - d))


def w6():
    return [
        _mk("您有一份外卖", 1, V(), special=_order,
            uext=lambda g: 4.0 if any(comp_e(c.v) >= 1.2 for c in g.hand) and g.turn <= 8 else -6.0),
        _mk("加急配送", 1, V(draw=1), special=_rush, uext=lambda g: 3.0 if g.flags["queue"] else -3.0),
        _mk("差评！", 1, V(dmg=3), special=_bad),
        _mk("五星好评", 1, est=_star_est),
        _mk("闯红灯！", 1, est=_red_est),
    ]


MEME = {"魔法少女的法杖": w1, "氪金手机": w2, "程序员键盘": w3, "社畜工牌保温杯": w4, "绷带右手": w5, "外卖保温箱": w6}


def meme_items(name):
    cards = MEME[name]()
    return [{"name": c.name, "part": "梗", "cards": [(c, c)], "passive": {}} for c in cards]
