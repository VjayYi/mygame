"""贪心模拟的数据层 v0.29：把卡池整理成可组装的 build。

约定（假设，需用户确认）：
- 单武器：基础卡 4 + 模块卡 d + 终极卡 1；模块卡直接加入牌库；终极卡 3 费，基调 1E（6 伤害）+ 各模块终极效果（按卡价值的 0.4 折算）。
- 手 2 + 脚 2 + 大脑辅助 1 + 躯干辅助 1 + 防具 3 件（主防御+副防御共 6 张）+ 通用 4。
- 武器容积按 VOL_FIX/FORMS，装配填充率 80%。
"""
# ruff: noqa: E501
import ast
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import armor_v027 as AR  # noqa: E402
import weapon_audit_v026 as WA  # noqa: E402
from card_value_engine import base_budget  # noqa: E402
from gsim_core import KEYS, Card, comp_e, make_card, parse  # noqa: E402

MELEE = ("刀", "剑", "爪", "斧", "拳套")
RANGED = ("步枪", "炮筒", "手枪", "弓")
CATS = MELEE + RANGED
FORM_B = {"改装": 0, "均衡": 1, "强攻": 3}
UP_FACTOR = 1.45
FILL = 0.80


def _load(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        return json.load(f)


def _first_literal(path, var):
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and node.targets[0].id == var:
            try:
                return ast.literal_eval(node.value)
            except ValueError:
                continue
    raise KeyError(var)


def scale_card(card, f):
    c = card.clone()
    for key in ("dmg", "aoe", "shield", "shield_next", "heal"):
        c.v[key] = c.v[key] * f
    return c


def _last_int(x):
    s = str(x).replace("→", "->").split("->")[-1]
    return int(s)


def _passive(text, e=0.25):
    """被动估值：解析成每回合固定加成，解析不了的按 e 折成 1.5 点护盾/攻击加成。"""
    v = parse(text) if text else parse("")
    out = {
        "shield": v["shield"] + v["shield_next"],
        "draw": v["draw"],
        "energy": 0.0,
        "turnatk": v["turnatk"] + 0.5 * v["nextatk"],
    }
    left = e - comp_e(v)
    if left > 0 and text:
        out["shield"] += left * 6.0 * 0.5
        out["turnatk"] += left * 6.0 * 0.5 / 2.0
    return out


def _cap_cost(card):
    """名义 >3 费的条件减费卡：沿用预算假设“常态减到 3 费”，按 3 费结算（条件减费暂未实现）。"""
    if card.cost > 3:
        card.text += f"〔名义 {card.cost} 费，测试版按 3 费结算〕"
        card.cost = 3
    return card


def _item(name, cost, text, value, up_text=None, up_cost=None, hint="atk", part=""):
    card = _cap_cost(make_card(name, cost, text, value, hint))
    if up_text:
        up = _cap_cost(make_card(name, up_cost if up_cost is not None else cost, up_text, value * UP_FACTOR, hint))
    else:
        up = scale_card(card, 1.4)
        up.text = text + "（强化：数值 ×1.4）"
    up.upgraded = True
    return {"name": name, "part": part, "cards": [(card, up)], "passive": {}}


def mod_hint(t):
    return "def" if t in ("防御", "回复") else "atk"


# ---------------------------------------------------------------- 模块
def nerf2(text):
    """v0.30：2 格模块数值下调（按格性价比实测偏高）。护盾 ×0.67，持续伤害 -1 层，伤害 ×0.8。"""
    if not text:
        return text
    text = re.sub(r"护盾 \+(\d+)", lambda m: "护盾 +%d" % max(1, int(int(m.group(1)) * 0.67 + 0.5)), text)
    text = re.sub(r"(附加)?(流血|中毒|灼烧) ?(\d+)", lambda m: "%s%s %d" % (m.group(1) or "", m.group(2), max(1, int(m.group(3)) - 1)), text)
    text = re.sub(r"伤害 \+(\d+)", lambda m: "伤害 +%d" % max(1, int(int(m.group(1)) * 0.8 + 0.5)), text)
    return text


NERF_2CELL = True
USE_V030_SHAPES = True


def _shape_map():
    with open(os.path.join(HERE, "module_shapes_v0.30.json"), encoding="utf-8") as f:
        return json.load(f)


def load_modules():
    smap = _shape_map() if USE_V030_SHAPES else {}
    audit = _load("module_audit_v0.26.json")
    pool = _load("module_pool_v0.27.json")
    locked = set(_load("module_unlock_v0.27.json"))
    new = _load("new_cards_v028.json")
    out = []
    for m in audit:
        txt, utxt, val = m["new_text"], m["up_text"], m["v1"]
        if NERF_2CELL and m["size"] == 2:
            txt, utxt, val = nerf2(txt), nerf2(utxt), 0.0
        it = _item(m["name"], m["new_cost"], txt, val, utxt, m["up_cost"], mod_hint(m["type"]))
        it.update(size=smap[m["name"]]["size"] if smap else m["size"], shape=smap[m["name"]]["shape"] if smap else m["shape"], major=m["major"], limit=m["limit"], pool=("基地" if pool.get(m["name"], "").startswith("基地") else "怪物"),
                  locked=m["name"] in locked, ult=m["new_ult"], value=m["v1"], kind="audit")
        out.append(it)
    for m in new["mods"]:
        txt, utxt, val = m["text"], m["up_text"], m["value"]
        if NERF_2CELL and m["size"] == 2:
            txt, utxt, val = nerf2(txt), nerf2(utxt), 0.0
        it = _item(m["name"], m["cost"], txt, val, utxt, m["up_cost"], mod_hint(m["type"]))
        it.update(size=smap[m["name"]]["size"] if smap else m["size"], shape=smap[m["name"]]["shape"] if smap else m["shape"], major=m["major"], limit=m["limit"], pool=("基地" if m["pool"] == "基地" else "怪物"),
                  locked=False, ult=m["ult"], value=m["value"], kind="new")
        out.append(it)
    for it in out:
        it["ult_v"] = make_card(it["name"] + "·终", 3, it["ult"], max(0.12, 0.4 * it["value"]), "atk").v
    return out


def modules_for(mods, cat):
    major = "近战" if cat in MELEE else "远程"
    return [m for m in mods if m["major"] == major and m["limit"] in ("—", cat)]


# ---------------------------------------------------------------- 武器
def weapon_cards(cat, form):
    b = FORM_B[form]
    items = []
    for c in WA.CARDS[cat]:
        name, cost, dmgs, shd, _extra, tmpl, up_tmpl = c
        bb = -(-b // 2) if len(dmgs) >= 2 else b
        vals = {"d0": (dmgs[0] + bb) if dmgs else 0, "d1": (dmgs[1] + bb) if len(dmgs) > 1 else 0, "s": (shd + b) if shd else 0}
        up_vals = {"u0": round(vals["d0"] * 1.4 + 0.01), "us": round(vals["s"] * 1.4 + 0.01)}
        text = tmpl.format(**vals)
        up_text = up_tmpl.format(**up_vals)
        e = WA.card_v(c, b)
        hint = "def" if shd and not dmgs else "atk"
        items.append(_item(name, cost, text, e, up_text, cost, hint))
    return items


def weapon_passive(cat, form):
    if form != "均衡":
        return {}
    _n, text, e = WA.PASSIVE[cat]
    return _passive(text, e + 0.15)


def weapon_vol(cat, form):
    return WA.FORMS[form]["vol"] + WA.VOL_FIX[cat]


# ---------------------------------------------------------------- 义体
def load_implants():
    hands, feet, brains, torsos = [], [], [], []
    for _i, name, cost, text, wo, _adj in _first_literal(os.path.join(HERE, "budget_doc_v0.26.py"), "HANDS"):
        w, o = (int(x) for x in wo.split("/"))
        hint = "def" if "护盾" in text and "伤害" not in text else "atk"
        hands.append(_item(name, cost, text, base_budget(cost) + 0.04 * (w + o) * 0.5, hint=hint, part="手"))
    for _i, name, cost, text, _adj in _first_literal(os.path.join(HERE, "budget_doc_v0.26.py"), "FEET"):
        hint = "def" if "护盾" in text and "伤害" not in text and "攻击" not in text else "atk"
        feet.append(_item(name, cost, text, base_budget(cost), hint=hint, part="脚"))
    for tbl, dst, part in (("BRAINS", brains, "脑"), ("TORSO", torsos, "躯")):
        for _i, name, passive, cstr, aux in _first_literal(os.path.join(HERE, "budget_doc_v0.26.py"), tbl):
            cost = _last_int(cstr)
            it = _item(name, cost, aux, base_budget(cost), hint="def", part=part)
            it["passive"] = _passive(passive)
            dst.append(it)
    new = _load("new_cards_v028.json")
    for imp in new["imps"]:
        part = imp["part"]
        if part in ("手", "脚"):
            hint = "def" if "护盾" in imp["text"] and "伤害" not in imp["text"] else "atk"
            it = _item(imp["name"], imp["cost"], imp["text"], imp["value"], imp["up_text"], imp["up_cost"], hint, part)
            (hands if part == "手" else feet).append(it)
        else:
            it = _item(imp["name"], imp["cost"], imp["text"], imp["value"], imp["up_text"], imp["up_cost"], "def", part)
            it["passive"] = _passive(imp.get("passive", ""))
            (brains if part == "脑" else torsos).append(it)
    return hands, feet, brains, torsos


# ---------------------------------------------------------------- 防具
MAIN = {0: ("护盾 +2；下回合护盾 +1", 0.4), 1: ("护盾 +6", 1.0), 2: ("护盾 +12", 2.0)}


def load_armor():
    parts = {"头": [], "躯干": [], "四肢": []}
    old = _first_literal(os.path.join(HERE, "budget_doc_v0.26.py"), "ARMOR")
    for name, part, df, sc, eff, _adj in old:
        parts[part].append((name, df, _last_int(sc), eff))
    for name, part, _set, df, sc, eff, _note in AR.NEW:
        parts[part].append((name, df, sc, eff))
    out = {}
    for part, lst in parts.items():
        items = []
        for name, df, sc, eff in lst:
            mt, mv = MAIN[df]
            main = make_card(name + "·主", df, mt, mv, "def")
            sub = make_card(name + "·副", sc, eff, base_budget(sc), "def")
            items.append({"name": name, "part": part,
                          "cards": [(main, scale_card(main, 1.4)), (sub, scale_card(sub, 1.4))], "passive": {}})
        out[part] = items
    return out


def generic_cards():
    specs = [("攻击", 1, "伤害 +6", 1.0, "atk"), ("格挡", 1, "护盾 +6", 1.0, "def"),
             ("重击", 2, "伤害 +12", 2.0, "atk"), ("加固", 2, "护盾 +12", 2.0, "def")]
    return [_item(n, c, t, e, hint=h) for n, c, t, e, h in specs]


class Pools:
    def __init__(self):
        self.mods = load_modules()
        self.hands, self.feet, self.brains, self.torsos = load_implants()
        self.armor = load_armor()
        self.generic = generic_cards()
        self.weapons = {(cat, form): weapon_cards(cat, form) for cat in CATS for form in FORM_B}


# ---------------------------------------------------------------- 组装
def ult_card(mods):
    v = make_card("终极", 3, "伤害 +6", 1.0, "atk").v
    for m in mods:
        for key in KEYS:
            v[key] += m["ult_v"].get(key, 0.0)
    txt = "伤害 +6" + "".join(f"；{m['name']}：{m['ult']}" for m in mods)
    return Card("终极", 3, v, kind="ult", text=txt)


def assemble(spec, upgrades, rng):
    """spec: dict(cat, form, mods, hands, feet, brain, torso, armor, pools)。upgrades: 升级张数。"""
    pools = spec["pools"]
    cards = []
    passive = {"shield": 0.0, "draw": 0.0, "energy": 0.0, "turnatk": 0.0}

    def add_passive(p):
        for key, val in p.items():
            passive[key] = passive.get(key, 0.0) + val

    items = list(pools.weapons[(spec["cat"], spec["form"])]) + list(spec["mods"]) + list(spec["hands"]) + list(spec["feet"])
    items += [spec["brain"], spec["torso"]] + list(spec["armor"]) + list(pools.generic)
    add_passive(weapon_passive(spec["cat"], spec["form"]))
    add_passive(spec["brain"]["passive"])
    add_passive(spec["torso"]["passive"])
    pairs = []
    for it in items:
        pairs.extend(it["cards"])
    ups = set(rng.sample(range(len(pairs)), min(upgrades, len(pairs)))) if upgrades else set()
    forced = spec.get("forced_up")
    for i, (c, u) in enumerate(pairs):
        cards.append(u if (i in ups or (forced and c.name in forced)) else c)
    cards.append(ult_card(spec["mods"]))
    return cards, passive
