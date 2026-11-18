"""概率边缘 · 文字测试版（单场战斗）v0.1

运行：python3 outputs/text_game/play.py [--seed 7]
规则口径与 outputs/balance/gsim_*.py 的贪心模拟完全一致：玩家 100 生命、每回合 3 能源、抽 5 张、
回合末手牌全弃、护盾每回合清零；敌人意图公开。每场对话会存到 outputs/text_game/logs/。

结算数值说明：卡面文字是设计稿；"▶"后面是模拟实际结算的数值（解析不了的机制，会把预算价值差额折成伤害/护盾）。
"""
# ruff: noqa: E501
import argparse
import os
import random
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BAL = os.path.join(HERE, "..", "balance")
sys.path.insert(0, BAL)
import gsim_data as D  # noqa: E402
import gsim_meme as M  # noqa: E402
import gsim_run_v029 as R  # noqa: E402
import weapon_audit_v026 as WA  # noqa: E402
from gsim_core import PLAYER_HP, Fight  # noqa: E402

REC_HP = {"mob": {1: 87, 2: 96, 3: 108}, "elite": {1: 135, 2: 150, 3: 173},
          "mini": {1: 196, 2: 222, 3: 250}, "final": {1: 332, 2: 332, 3: 332}}
REC_AVG = {"mob": 6, "elite": 11, "mini": 10, "final": 12}
WINDOW = {"mob": (5, 10), "elite": (8, 15), "mini": (13, 20), "final": (20, 30)}
KINDS = [("mob", "小怪（2 体）"), ("elite", "精英"), ("mini", "小 Boss"), ("final", "终极 Boss（3 阶段）")]
SLOT_NAMES = {"模": "模块", "手": "手", "脚": "脚", "脑": "大脑", "躯": "躯干", "头": "防具·头", "身": "防具·躯干", "腿": "防具·四肢"}
FLAG_NAMES = {"pity": "保底层", "seal": "封印层", "transform": "变身剩余回合", "dark": "【黑化】"}

LOG = []


def say(text=""):
    print(text, flush=True)
    LOG.append(text)


def ask(prompt):
    try:
        s = input(prompt)
    except EOFError:
        say("\n（输入结束，退出）")
        raise SystemExit(0) from None
    LOG.append(f"{prompt}{s}")
    return s.strip()


# ---------------------------------------------------------------- 展示
def fmt_eff(g, card):
    v = g.vals(card)
    hits = max(1.0, v.get("hits", 1.0))
    flat = g.turn_atk + g.atk_flat
    out = []
    if v["dmg"] > 0:
        d = v["dmg"] + g.next_atk + flat * hits
        out.append(f"伤害 {d:.0f}" + (f"（{int(hits)} 段）" if hits > 1 else ""))
    if v["aoe"] > 0:
        out.append(f"全体 {v['aoe'] + flat:.0f}")
    if v["dot"] > 0:
        out.append(f"持续伤害 {v['dot']:.0f} 层")
    if v["shield"] > 0:
        out.append(f"护盾 {v['shield']:.0f}")
    if v["shield_next"] > 0:
        out.append(f"下回合护盾 {v['shield_next']:.0f}")
    if v["heal"] > 0:
        out.append(f"回复 {v['heal']:.0f}")
    if v["draw"] > 0:
        out.append(f"抽 {v['draw']:.0f}")
    if v["energy"] > 0:
        out.append(f"能源 +{v['energy']:.0f}")
    if v["stun"] > 0:
        out.append(f"击晕 {v['stun'] * 100:.0f}%")
    if v["nextatk"] > 0:
        out.append(f"下一张攻击 +{v['nextatk']:.0f}")
    if v["turnatk"] > 0:
        out.append(f"本回合攻击 +{v['turnatk']:.0f}")
    if v["edown"] > 0:
        out.append(f"敌攻击 -{v['edown']:.0f}")
    if v["costdown"] > 0:
        out.append("下一张费用 -1")
    if v["selfdmg"] > 0:
        out.append(f"自伤 {v['selfdmg']:.0f}")
    if card.hpcost:
        out.append(f"每次打出失去 {card.hpcost} 生命")
    return "，".join(out) if out else "（见卡面）"


def card_name(c):
    return c.name + ("+" if c.upgraded else "")


def card_line(g, i, c):
    cost = g.cost_of(c)
    mark = "" if cost <= g.energy else "×"
    cstr = f"{cost}费" + (f"(原{c.cost})" if cost != c.cost else "")
    tag = "【消耗】" if c.exhaust else ""
    return f" {mark}{i:>2}. [{cstr}] {card_name(c)}{tag}  ▶ {fmt_eff(g, c)}"


def future_intent(e, g, k):
    base = e.pattern[(e.idx + k) % len(e.pattern)]
    t = g.turn + k
    if t >= e.enrage_turn:
        base *= 1.0 + e.enrage_rate * (t - e.enrage_turn + 1)
    return base


def enemy_lines(g):
    lines = []
    for i, e in enumerate(g.enemies, 1):
        if not e.alive:
            lines.append(f" [{i}] {e.name}  已击败")
            continue
        ph = f"阶段 {e.nphase - len(e.phases)}/{e.nphase} " if e.nphase > 1 else ""
        st = []
        if e.dot > 0:
            st.append(f"持续伤害 {e.dot:.0f} 层")
        if e.flat_dot:
            st.append(f"差评 {e.flat_dot[0][0]}×{e.flat_dot[0][1]} 回合")
        if e.edown > 0:
            st.append(f"本次攻击 -{e.edown:.0f}")
        if e.immune > 0:
            st.append(f"击晕免疫 {e.immune}")
        if e.stunned:
            it = "已被击晕：本回合不行动"
        else:
            now = max(0.0, e.intent(g.turn) - e.edown)
            nxt = [future_intent(e, g, k) for k in (1, 2)]
            it = f"将造成 {now:.0f}（之后 {nxt[0]:.0f}、{nxt[1]:.0f}）"
        lines.append(f" [{i}] {e.name} {ph}生命 {e.hp:.0f}/{e.maxhp:.0f}  意图：{it}" + (f"  〔{'，'.join(st)}〕" if st else ""))
    return lines


def status_extra(g):
    out = []
    for k, name in FLAG_NAMES.items():
        if g.flags[k]:
            out.append(f"{name}{'' if k == 'dark' else ' ' + str(int(g.flags[k]))}")
    if g.flags["clip_card"]:
        out.append(f"剪贴板：{g.flags['clip_card'].name}")
    q = g.flags["queue"]
    if q:
        out.append("配送中：" + "、".join(f"{it[0].name}（{it[1]} 回合）" for it in q))
    if g.energy_next:
        out.append(f"下回合能源 {g.energy_next:+d}")
    if g.draw_next:
        out.append(f"下回合抽牌 {g.draw_next:+d}")
    if g.cost_plus_next_turn:
        out.append(f"下回合前 {g.cost_plus_next_turn} 张牌费用 +1")
    if g.shield_carry:
        out.append(f"下回合护盾 +{g.shield_carry:.0f}")
    if g.no_shield:
        out.append("无法获得护盾")
    if g.turn_atk + g.atk_flat >= 0.5:
        out.append(f"本回合攻击 +{g.turn_atk + g.atk_flat:.0f}")
    if g.next_atk:
        out.append(f"下一张攻击 +{g.next_atk:.0f}")
    return out


def show_turn(g):
    say(f"\n━━━━━━━━ 第 {g.turn} 回合 ━━━━━━━━")
    say(f"生命 {g.hp:.0f}/{g.maxhp}   护盾 {g.shield:.0f}   能源 {g.energy}   牌库 {len(g.draw_pile)}  弃牌 {len(g.discard)}  消耗 {len(g.exhausted)}")
    ex = status_extra(g)
    if ex:
        say("状态：" + "；".join(ex))
    say("敌人：")
    for ln in enemy_lines(g):
        say(ln)
    say("手牌：")
    for i, c in enumerate(g.hand, 1):
        say(card_line(g, i, c))
    if not g.hand:
        say("  （无手牌）")
    say("指令：编号[ 目标]出牌 ｜ e 结束回合 ｜ a 本回合自动 ｜ aa 自动打完 ｜ i 编号看详情 ｜ d 牌堆 ｜ h 帮助 ｜ q 放弃")


def snap(g):
    return dict(hp=g.hp, sh=g.shield, en=g.energy, hand=len(g.hand),
                es=[(e.hp, e.dot, e.stunned, e.edown, len(e.phases), e.alive) for e in g.enemies])


def diff(g, b, played_card=None):
    a = snap(g)
    out = []
    for i, (eb, ea) in enumerate(zip(b["es"], a["es"]), 1):
        name = f"[{i}]{g.enemies[i - 1].name}"
        if ea[4] < eb[4]:
            out.append(f"{name} 被击破，进入下一阶段（生命 {g.enemies[i - 1].hp:.0f}）")
        elif eb[5] and not ea[5]:
            out.append(f"{name} 被击败")
        elif ea[0] < eb[0]:
            out.append(f"{name} 生命 -{eb[0] - ea[0]:.0f}")
        if ea[1] > eb[1]:
            out.append(f"{name} 持续伤害 +{ea[1] - eb[1]:.0f} 层")
        if ea[2] and not eb[2]:
            out.append(f"{name} 被击晕")
        if ea[3] > eb[3]:
            out.append(f"{name} 下次攻击 -{ea[3] - eb[3]:.0f}")
    if a["sh"] != b["sh"]:
        out.append(f"护盾 {a['sh'] - b['sh']:+.0f}（现 {a['sh']:.0f}）")
    if a["hp"] != b["hp"]:
        out.append(f"生命 {a['hp'] - b['hp']:+.0f}（现 {a['hp']:.0f}）")
    gain = a["en"] - b["en"] + (played_card[1] if played_card else 0)
    if gain:
        out.append(f"能源 {gain:+d}")
    if played_card:
        drawn = a["hand"] - (b["hand"] - 1)
        if drawn:
            out.append(f"手牌 {drawn:+d}")
    return out


# ---------------------------------------------------------------- build
def ult_text(spec):
    return "伤害 +6" + "".join(f"；{m['name']}：{m['ult']}" for m in spec["mods"])


def cap_of(spec):
    return D.weapon_vol(spec["cat"], spec["form"]) * D.FILL


def used_of(spec):
    return sum(m["size"] for m in spec["mods"])


def make_spec(cp, rng, layer, mode, cat=None, form=None, meme=None):
    if meme:
        sk = 1
        spec = dict(kind="meme", name=meme, cat=None, form=None, mods=[], hands=R.pick_many(rng, cp.hands, 2, sk),
                    feet=R.pick_many(rng, cp.feet, 2, sk), brain=R.pick(rng, cp.brains, sk), torso=R.pick(rng, cp.torsos, sk),
                    armor=[R.pick(rng, cp.armor[k], sk) for k in ("头", "躯干", "四肢")], pools=cp)
        return spec
    spec = R.sample_spec(cp, rng, layer, 1, cat, form)
    spec["kind"] = "std"
    return spec


def build_cards(spec, layer, seed):
    rng = random.Random(seed)
    cp = spec["pools"]
    ups = R.LAYER_UPG[layer]
    if spec["kind"] == "std":
        return D.assemble(spec, ups, rng)
    items = M.meme_items(spec["name"]) + list(cp.generic) + list(spec["hands"]) + list(spec["feet"]) + [spec["brain"], spec["torso"]] + list(spec["armor"])
    flat = []
    for it in items:
        flat.extend((c, u, it["part"]) for c, u in it["cards"])
    idx = [i for i, (_c, _u, part) in enumerate(flat) if part != "梗"]
    chosen = set(rng.sample(idx, min(ups, len(idx))))
    cards = [u if i in chosen else c for i, (c, u, _p) in enumerate(flat)]
    passive = {"shield": 0.0, "draw": 0.0, "energy": 0.0, "turnatk": 0.0}
    for it in (spec["brain"], spec["torso"]):
        for k, v in it["passive"].items():
            passive[k] += v
    return cards, passive


def item_text(it):
    parts = []
    for c, _u in it["cards"]:
        parts.append(f"{c.name}[{c.cost}费] {c.text}")
    ps = it.get("passive")
    ptxt = ""
    if ps:
        ptxt = f"  （被动折算：护盾 {ps.get('shield', 0):.1f}/攻击 {ps.get('turnatk', 0):.1f} 每回合）"
    return "；".join(parts) + ptxt


def show_build(spec, layer):
    cp = spec["pools"]
    say("\n══════════ 当前构筑 ══════════")
    if spec["kind"] == "std":
        say(f"武器：{spec['cat']}·{spec['form']}    模块容积 {used_of(spec)}/{cap_of(spec):.0f} 格（已按 80% 填充率）    强化 {R.LAYER_UPG[layer]} 张（开战随机）")
        say("  武器基础卡：")
        for it in cp.weapons[(spec["cat"], spec["form"])]:
            c = it["cards"][0][0]
            say(f"    · {c.name}[{c.cost}费] {c.text}")
        if spec["form"] == "均衡":
            n, t, _e = WA.PASSIVE[spec["cat"]]
            say(f"    · 被动「{n}」：{t}")
        say("  模块：")
        for i, m in enumerate(spec["mods"], 1):
            c = m["cards"][0][0]
            say(f"    模{i}. {m['name']}（{m['size']}格）[{c.cost}费] {c.text}")
            say(f"        终极叠加：{m['ult']}")
    else:
        say(f"梗武器：{spec['name']}    强化 {R.LAYER_UPG[layer]} 张（开战随机，不含梗武器卡）")
        for it in M.meme_items(spec["name"]):
            c = it["cards"][0][0]
            say(f"    · {c.name}[{c.cost}费] {c.text}")
    say("  义体：")
    for i, it in enumerate(spec["hands"], 1):
        say(f"    手{i}. {item_text(it)}")
    for i, it in enumerate(spec["feet"], 1):
        say(f"    脚{i}. {item_text(it)}")
    say(f"    脑. {item_text(spec['brain'])}")
    say(f"    躯. {item_text(spec['torso'])}")
    say("  防具：")
    for tag, it in zip(("头", "身", "腿"), spec["armor"]):
        say(f"    {tag}. {it['name']} → {item_text(it)}")
    if spec["kind"] == "std":
        say(f"  终极卡（3 费）：{ult_text(spec)}")
    say("  通用牌：攻击、格挡、重击、加固")


def pool_for(spec, slot):
    cp = spec["pools"]
    if slot == "模":
        return D.modules_for(cp.mods, spec["cat"])
    return {"手": cp.hands, "脚": cp.feet, "脑": cp.brains, "躯": cp.torsos,
            "头": cp.armor["头"], "身": cp.armor["躯干"], "腿": cp.armor["四肢"]}[slot]


def find_item(pool, kw):
    exact = [x for x in pool if x["name"] == kw]
    if exact:
        return exact, None
    hits = [x for x in pool if kw in x["name"]]
    return hits, None


def cmd_edit(spec, parts):
    """换 槽 [序号] 关键词 / 加 模 关键词 / 删 模 序号 / 查 槽 [关键词]"""
    cmd = parts[0]
    if len(parts) < 2 or parts[1] not in SLOT_NAMES:
        say("槽位：模 手 脚 脑 躯 头 身 腿。例：换 模 2 刃口 ｜ 换 手 1 重锤 ｜ 换 脑 感知 ｜ 加 模 毒 ｜ 删 模 3 ｜ 查 模 弹")
        return
    slot = parts[1]
    if spec["kind"] == "meme" and slot == "模":
        say("梗武器没有模块槽。")
        return
    pool = pool_for(spec, slot)
    if cmd == "查":
        kw = parts[2] if len(parts) > 2 else ""
        hits = [x for x in pool if kw in x["name"]]
        say(f"{SLOT_NAMES[slot]}候选（{len(hits)}）：" + "、".join(
            f"{x['name']}" + (f"({x['size']}格)" if slot == "模" else "") for x in hits[:40]))
        return
    if cmd == "删":
        if slot != "模" or len(parts) < 3 or not parts[2].isdigit() or not (1 <= int(parts[2]) <= len(spec["mods"])):
            say("用法：删 模 序号")
            return
        m = spec["mods"].pop(int(parts[2]) - 1)
        say(f"已删除模块 {m['name']}")
        return
    if cmd == "加":
        if slot != "模" or len(parts) < 3:
            say("用法：加 模 关键词")
            return
        hits, _ = find_item(pool, parts[2])
        if len(hits) != 1:
            say("匹配到：" + ("、".join(x["name"] for x in hits[:15]) if hits else "无") + "（请写得更具体）")
            return
        m = hits[0]
        if m in spec["mods"]:
            say("已装配该模块。")
        elif used_of(spec) + m["size"] > cap_of(spec):
            say(f"容积不足：{used_of(spec)}+{m['size']} > {cap_of(spec):.0f}")
        else:
            spec["mods"].append(m)
            say(f"已加入 {m['name']}（{m['size']}格）")
        return
    # 换
    idx = None
    rest = parts[2:]
    if slot in ("模", "手", "脚"):
        if not rest or not rest[0].isdigit():
            say(f"用法：换 {slot} 序号 关键词")
            return
        idx = int(rest[0]) - 1
        rest = rest[1:]
    if not rest:
        say("缺少关键词。")
        return
    hits, _ = find_item(pool, rest[0])
    if len(hits) != 1:
        say("匹配到：" + ("、".join(x["name"] for x in hits[:15]) if hits else "无") + "（请写得更具体）")
        return
    new = hits[0]
    if slot == "模":
        if idx is None or not (0 <= idx < len(spec["mods"])):
            say("模块序号超出范围，可先用“加 模”。")
            return
        if new in spec["mods"]:
            say("已装配该模块。")
            return
        cur = spec["mods"][idx]
        if used_of(spec) - cur["size"] + new["size"] > cap_of(spec):
            say(f"容积不足：{used_of(spec) - cur['size'] + new['size']} > {cap_of(spec):.0f}")
            return
        spec["mods"][idx] = new
    elif slot in ("手", "脚"):
        key = "hands" if slot == "手" else "feet"
        if not (0 <= idx < 2):
            say("序号为 1 或 2。")
            return
        spec[key][idx] = new
    elif slot == "脑":
        spec["brain"] = new
    elif slot == "躯":
        spec["torso"] = new
    else:
        spec["armor"][{"头": 0, "身": 1, "腿": 2}[slot]] = new
    say(f"已替换为 {new['name']}")


# ---------------------------------------------------------------- 战斗
def deck_view(g):
    from collections import Counter
    say("牌库（抽牌堆，顺序保密）：" + "、".join(f"{n}×{k}" if k > 1 else n for n, k in sorted(Counter(card_name(c) for c in g.draw_pile).items())))
    say("弃牌堆：" + ("、".join(card_name(c) for c in g.discard) or "无"))
    say("已消耗：" + ("、".join(card_name(c) for c in g.exhausted) or "无"))


def auto_turn(g):
    before = snap(g)
    plays = []
    orig = g.play

    def logged(c):
        plays.append(card_name(c))
        orig(c)

    g.play = logged
    g.play_phase()
    g.play = orig
    say("  自动出牌：" + ("、".join(plays) if plays else "（无）"))
    for ln in diff(g, before):
        say("   · " + ln)


def run_enemy_phase(g):
    pre_hp, pre_sh = g.hp, g.shield
    pre = [(e.hp, e.stunned, e.intent(g.turn) - e.edown, e.alive) for e in g.enemies]
    res = g.end_turn()
    for i, (e, p) in enumerate(zip(g.enemies, pre), 1):
        if p[3] and p[1]:
            say(f"  [{i}] {e.name} 被击晕，跳过行动")
    lost = pre_hp - g.hp
    sh_used = pre_sh - g.shield if g.shield < pre_sh else 0
    intent_sum = sum(max(0.0, p[2]) for p, e in zip(pre, g.enemies) if p[3] and not p[1])
    say(f"  敌人行动：总攻击 {intent_sum:.0f}，护盾抵挡 {min(sh_used, intent_sum):.0f}，你损失 {lost:.0f} 生命（现 {g.hp:.0f}）")
    for i, (e, p) in enumerate(zip(g.enemies, pre), 1):
        if p[3] and e.alive and e.hp < p[0] and not p[1]:
            say(f"  [{i}] {e.name} 受持续伤害 -{p[0] - e.hp:.0f}")
    return res


def battle(spec, layer, kind, hp, seed):
    cards, passive = build_cards(spec, layer, seed)
    enemies = R.encounter(kind, hp, REC_AVG[kind])
    for e in enemies:
        e.nphase = 1 + len(e.phases)
    g = Fight(cards, enemies, random.Random(seed), passive)
    say(f"\n▶ 开战：{dict(KINDS)[kind]}，总生命 {sum(e.maxhp for e in enemies) + sum(p[0] for e in enemies for p in e.phases):.0f}，"
        f"牌库 {len(cards)} 张。目标回合区间 {WINDOW[kind][0]}~{WINDOW[kind][1]}（参考，不是限制）。")
    auto_all = False
    result = None
    for turn in range(1, 81):
        g.begin_turn(turn)
        if auto_all:
            say(f"\n━━ 第 {turn} 回合（自动）生命 {g.hp:.0f}")
            auto_turn(g)
        else:
            show_turn(g)
            while True:
                cmd = ask("> ")
                if not cmd:
                    continue
                low = cmd.lower()
                if low in ("e", "end", "结束"):
                    break
                if low == "a":
                    auto_turn(g)
                    break
                if low == "aa":
                    auto_all = True
                    auto_turn(g)
                    break
                if low in ("d", "deck"):
                    deck_view(g)
                    continue
                if low in ("h", "help", "?"):
                    say("编号出牌；若有多名敌人，可写“编号 目标”，如 “3 2” 对 2 号敌人。e 结束回合；a 自动打本回合；aa 自动打完整场；i 编号 看卡面原文；d 看牌堆；q 放弃。带 × 的牌能源不足。")
                    continue
                if low in ("q", "quit"):
                    say("放弃本场。")
                    return None
                toks = cmd.split()
                if toks[0] in ("i", "详情") and len(toks) > 1 and toks[1].isdigit() and 1 <= int(toks[1]) <= len(g.hand):
                    c = g.hand[int(toks[1]) - 1]
                    say(f"  {card_name(c)}：{c.text or '（无）'}")
                    say(f"  结算：{fmt_eff(g, c)}")
                    continue
                if toks[0].isdigit() and 1 <= int(toks[0]) <= len(g.hand):
                    c = g.hand[int(toks[0]) - 1]
                    cost = g.cost_of(c)
                    if cost > g.energy:
                        say(f"  能源不足（需要 {cost}，现有 {g.energy}）")
                        continue
                    alive = g.alive_enemies()
                    if len(toks) > 1 and toks[1].isdigit() and 1 <= int(toks[1]) <= len(g.enemies) and g.enemies[int(toks[1]) - 1].alive:
                        g.pick = g.enemies[int(toks[1]) - 1]
                    else:
                        g.pick = None
                        if len(toks) > 1:
                            say("  目标无效，使用默认目标（生命最低者）。")
                    b = snap(g)
                    g.play(c)
                    g.pick = None
                    say(f"  打出 {card_name(c)}（-{cost} 能源）")
                    for ln in diff(g, b, (c, cost)):
                        say("   · " + ln)
                    if not g.alive_enemies() or g.hp <= 0:
                        break
                    if len(alive) > 1 and len(g.alive_enemies()) == 1:
                        say("  （场上只剩 1 名敌人）")
                    show_hand_short(g)
                    continue
                say("  无效指令，h 查看帮助。")
        res = run_enemy_phase(g)
        if res is not None:
            result = (turn, res)
            break
    if result is None:
        result = (80, False)
    turns, win = result
    say("\n══════════ 战斗结束 ══════════")
    say(("胜利" if win else "失败") + f"：用了 {turns} 回合，累计损失 {g.hp_lost:.0f} 生命，剩余 {max(g.hp, 0):.0f}/{PLAYER_HP}。")
    lo, hi = WINDOW[kind]
    if win:
        say(f"对照目标区间 {lo}~{hi} 回合：" + ("偏快" if turns < lo else "偏慢" if turns > hi else "区间内") + "。")
    # 贪心对照
    ts = []
    for k in range(20):
        c2, p2 = build_cards(spec, layer, seed)
        e2 = R.encounter(kind, hp, REC_AVG[kind])
        f2 = Fight(c2, e2, random.Random(1000 + k), p2)
        t, w = f2.run()
        if w:
            ts.append(t)
    if ts:
        say(f"贪心 AI 打同一套牌（20 次）：平均 {statistics.mean(ts):.1f} 回合（{min(ts)}~{max(ts)}），胜率 {len(ts) / 20:.0%}。")
    else:
        say("贪心 AI 打同一套牌：20 次全部失败。")
    return turns, win, g.hp_lost


def show_hand_short(g):
    ex = status_extra(g)
    say(f"  —— 生命 {g.hp:.0f}  护盾 {g.shield:.0f}  能源 {g.energy}" + (f"  ｜ {'；'.join(ex)}" if ex else ""))
    for ln in enemy_lines(g):
        say("  " + ln)
    for i, c in enumerate(g.hand, 1):
        say(card_line(g, i, c))


# ---------------------------------------------------------------- 菜单
def pick_enemy(layer):
    say("\n选择敌人：")
    for i, (_k, n) in enumerate(KINDS, 1):
        say(f"  {i}. {n}（推荐生命 {REC_HP[_k][layer]}，每回合伤害均值 {REC_AVG[_k]}）")
    say("  可在序号后加生命值覆盖，例如“2 200”。")
    while True:
        s = ask("敌人> ").split()
        if s and s[0].isdigit() and 1 <= int(s[0]) <= 4:
            kind = KINDS[int(s[0]) - 1][0]
            hp = float(s[1]) if len(s) > 1 and s[1].replace(".", "").isdigit() else REC_HP[kind][layer]
            return kind, hp
        say("请输入 1~4。")


def choose_build(cp, rng):
    say("\n选择武器：  1 随机普通武器   2 指定品类/形态   3 梗武器   0 退出")
    while True:
        s = ask("武器> ")
        if s == "0":
            raise SystemExit(0)
        if s in ("1", "2", "3"):
            break
    layer = ask("构筑层数 1/2/3（模块 3/4/5 个，强化 2/4/7 张；默认 3）> ")
    layer = int(layer) if layer in ("1", "2", "3") else 3
    if s == "1":
        return make_spec(cp, rng, layer, "std"), layer
    if s == "2":
        say("品类：" + " ".join(f"{i}.{c}" for i, c in enumerate(D.CATS, 1)))
        c = ask("品类序号> ")
        cat = D.CATS[int(c) - 1] if c.isdigit() and 1 <= int(c) <= len(D.CATS) else D.CATS[0]
        say("形态：1 改装（容积大、数值低）  2 均衡（带被动）  3 强攻（容积小、数值高）")
        f = ask("形态序号> ")
        form = list(D.FORM_B)[int(f) - 1] if f in ("1", "2", "3") else "均衡"
        return make_spec(cp, rng, layer, "std", cat, form), layer
    names = list(M.MEME)
    say("梗武器：" + "  ".join(f"{i}.{n}" for i, n in enumerate(names, 1)))
    n = ask("序号> ")
    name = names[int(n) - 1] if n.isdigit() and 1 <= int(n) <= len(names) else names[0]
    return make_spec(cp, rng, layer, "meme", meme=name), layer


def build_loop(spec, layer, cp, rng):
    while True:
        show_build(spec, layer)
        say("\n指令：y 开始 ｜ r 重新随机 ｜ 换/加/删/查 槽 … （h 看写法）｜ 0 退出")
        cmd = ask("构筑> ")
        if cmd in ("y", "Y", ""):
            return spec
        if cmd == "0":
            raise SystemExit(0)
        if cmd == "h":
            say("例：换 模 2 刃口 ｜ 加 模 毒 ｜ 删 模 3 ｜ 换 手 1 重锤 ｜ 换 脚 2 滑行 ｜ 换 脑 感知 ｜ 换 躯 防护 ｜ 换 头 铁壁 ｜ 查 模 弹。槽位：模 手 脚 脑 躯 头 身 腿")
            continue
        if cmd == "r":
            if spec["kind"] == "std":
                spec = make_spec(cp, rng, layer, "std", spec["cat"], spec["form"])
            else:
                spec = make_spec(cp, rng, layer, "meme", meme=spec["name"])
            continue
        parts = cmd.split()
        if parts and parts[0] in ("换", "加", "删", "查"):
            cmd_edit(spec, parts)
        else:
            say("无法识别。")


def save_log(log_dir):
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, time.strftime("session_%Y%m%d_%H%M%S.txt"))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(LOG) + "\n")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--log-dir", default=os.path.join(HERE, "logs"))
    args = ap.parse_args()
    seed = args.seed if args.seed is not None else int(time.time()) % 100000
    rng = random.Random(seed)
    cp = D.Pools()
    say(f"概率边缘 · 文字测试版 v0.1（种子 {seed}）。随时输入 h 查看帮助。")
    try:
        spec, layer = choose_build(cp, rng)
        spec = build_loop(spec, layer, cp, rng)
        while True:
            kind, hp = pick_enemy(layer)
            battle(spec, layer, kind, hp, rng.randint(1, 10**6))
            say("\n下一步：1 同构筑再战   2 改构筑   0 退出")
            s = ask("> ")
            if s == "2":
                spec, layer = choose_build(cp, rng)
                spec = build_loop(spec, layer, cp, rng)
            elif s != "1":
                break
    except SystemExit:
        pass
    finally:
        say("已保存对话记录：" + save_log(args.log_dir))


if __name__ == "__main__":
    main()
