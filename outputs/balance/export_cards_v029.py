"""把卡池、武器轮廓格子、模块形状导出成 Unity 可读的 JSON，并生成 Python 对拍用的校验套牌。

输出：
- unity/ProbabilityEdge/Assets/ProbabilityEdge/Resources/CardData/cardpool.json
- unity/ProbabilityEdge/Tests/CardData/validation.json（C# 战斗引擎与 Python 引擎对拍用）
"""
# ruff: noqa: E501
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gsim_data as D  # noqa: E402
import gsim_meme as M  # noqa: E402
import gsim_run_v029 as R  # noqa: E402
import module_shapes as MS  # noqa: E402
import weapon_audit_v026 as WA  # noqa: E402
import weapon_shapes as SH  # noqa: E402
from gsim_core import KEYS, Fight  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_POOL = os.path.join(ROOT, "unity", "ProbabilityEdge", "Assets", "ProbabilityEdge", "Resources", "CardData", "cardpool.json")
OUT_VAL = os.path.join(ROOT, "unity", "ProbabilityEdge", "Tests", "CardData", "validation.json")

FX_KEYS = list(KEYS) + ["hits"]

# ---------------------------------------------------------------- 形状（格坐标 [行, 列]）
SHAPE_CELLS = MS.SHAPES


def connected(cells):
    if not cells:
        return True
    start = next(iter(cells))
    seen, stack = {start}, [start]
    while stack:
        r, c = stack.pop()
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (r + d[0], c + d[1])
            if n in cells and n not in seen:
                seen.add(n)
                stack.append(n)
    return len(seen) == len(cells)


def cells_of(mask):
    return {(r, c) for r, row in enumerate(mask) for c, ch in enumerate(row) if ch == "#"}


# ---------------------------------------------------------------- 序列化
def fx_json(v):
    return {k: round(float(v.get(k, 0.0) if k != "hits" else v.get("hits", 1.0)), 4) for k in FX_KEYS}


def card_json(c):
    return dict(name=c.name, cost=c.cost, text=c.text, exhaust=bool(c.exhaust), fx=fx_json(c.v))


def item_json(it, kind, extra=None):
    d = dict(kind=kind, name=it["name"], part=it.get("part", ""),
             cards=[dict(base=card_json(b), up=card_json(u)) for b, u in it["cards"]],
             passive={k: round(float(v), 4) for k, v in (it.get("passive") or {}).items()})
    if extra:
        d.update(extra)
    return d


def main():
    cp = D.Pools()
    # 形状校验
    for k, cells in SHAPE_CELLS.items():
        assert len(set(cells)) == len(cells), k
    sizes = {k: len(v) for k, v in SHAPE_CELLS.items()}
    # 模块形状/供能来自审计 JSON
    audit = {m["name"]: m for m in json.load(open(os.path.join(HERE, "module_audit_v0.26.json"), encoding="utf-8"))}
    new = {m["name"]: m for m in json.load(open(os.path.join(HERE, "new_cards_v028.json"), encoding="utf-8"))["mods"]}
    mods = []
    for it in cp.mods:
        src = audit.get(it["name"]) or new.get(it["name"])
        shape = it["shape"]
        assert sizes[shape] == it["size"], (it["name"], shape, it["size"])
        mods.append(item_json(it, "module", dict(
            size=it["size"], shape=shape, major=it["major"], limit=it["limit"], pool=it["pool"], locked=bool(it["locked"]),
            type=src.get("type", ""), ult=it["ult"], ultFx=fx_json(it["ult_v"]),
            supplyA=src.get("A", 0), supplyD=src.get("D", 0), tier=src.get("supply_tier") or src.get("tier", ""))))
    weapons = {}
    for cat in D.CATS:
        for form in D.FORM_B:
            vol = D.weapon_vol(cat, form)
            cells = cells_of(SH.all_masks_cached()[f"{cat}|{form}"])
            assert len(cells) == vol, (cat, form, len(cells), vol)
            assert connected(cells)
            ptxt = WA.PASSIVE[cat] if form == "均衡" else None
            weapons[f"{cat}|{form}"] = dict(
                cat=cat, form=form, major="近战" if cat in D.MELEE else "远程", volume=vol, mask=SH.all_masks_cached()[f"{cat}|{form}"],
                passiveName=ptxt[0] if ptxt else "", passiveText=ptxt[1] if ptxt else "",
                passive={k: round(float(v), 4) for k, v in D.weapon_passive(cat, form).items()},
                items=[item_json(it, "weapon") for it in cp.weapons[(cat, form)]])
    pool = dict(
        version=1,
        shapes={k: [list(c) for c in v] for k, v in SHAPE_CELLS.items()},
        weapons=weapons, modules=mods,
        hands=[item_json(i, "hand") for i in cp.hands], feet=[item_json(i, "foot") for i in cp.feet],
        brains=[item_json(i, "brain") for i in cp.brains], torsos=[item_json(i, "torso") for i in cp.torsos],
        armor={part: [item_json(i, "armor") for i in lst] for part, lst in cp.armor.items()},
        generic=[item_json(i, "generic") for i in cp.generic],
        memes=[dict(name=n, cards=[dict(name=c.name, cost=c.cost, text=c.text) for c in fn()]) for n, fn in M.MEME.items()])
    os.makedirs(os.path.dirname(OUT_POOL), exist_ok=True)
    with open(OUT_POOL, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, separators=(",", ":"))
    print("写出", OUT_POOL, round(os.path.getsize(OUT_POOL) / 1024), "KB；模块", len(mods), "武器轮廓", len(weapons))
    for key in ("刀|改装", "刀|均衡", "刀|强攻", "步枪|均衡", "爪|强攻", "弓|均衡"):
        print(key, weapons[key]["volume"])
        for row in weapons[key]["mask"]:
            print("   ", row)

    # ---------------------------------------------------------------- 对拍套牌
    rng = random.Random(2026)
    decks = []
    for i in range(24):
        cat = D.CATS[i % len(D.CATS)]
        form = list(D.FORM_B)[(i // 3) % 3]
        spec = R.sample_spec(cp, rng, 3, 1, cat, form)
        spec["forced_up"] = None
        decks.append(("std", spec))
    for name in M.MEME:
        rng2 = random.Random(77)
        items = M.meme_items(name)
        spec = dict(hands=rng2.sample(cp.hands, 2), feet=rng2.sample(cp.feet, 2), brain=rng2.choice(cp.brains), torso=rng2.choice(cp.torsos),
                    armor=[rng2.choice(cp.armor[k]) for k in ("头", "躯干", "四肢")], items=items)
        decks.append(("meme", dict(spec, name=name)))
    enc = [("mob", 104, 8), ("elite", 121, 21), ("mini", 195, 20), ("final", 286, 18)]
    out = []
    for kind, spec in decks:
        if kind == "std":
            cards, passive = D.assemble(spec, 0, random.Random(1))
            d = dict(type="std", cat=spec["cat"], form=spec["form"], mods=[m["name"] for m in spec["mods"]],
                     hands=[i["name"] for i in spec["hands"]], feet=[i["name"] for i in spec["feet"]],
                     brain=spec["brain"]["name"], torso=spec["torso"]["name"], armor=[i["name"] for i in spec["armor"]])
        else:
            items = list(spec["items"]) + list(cp.generic) + spec["hands"] + spec["feet"] + [spec["brain"], spec["torso"]] + spec["armor"]
            cards = []
            for it in items:
                cards.extend(c for c, _u in it["cards"])
            passive = {"shield": 0.0, "draw": 0.0, "energy": 0.0, "turnatk": 0.0}
            for it in (spec["brain"], spec["torso"]):
                for k, v in it["passive"].items():
                    passive[k] += v
            d = dict(type="meme", meme=spec["name"], hands=[i["name"] for i in spec["hands"]], feet=[i["name"] for i in spec["feet"]],
                     brain=spec["brain"]["name"], torso=spec["torso"]["name"], armor=[i["name"] for i in spec["armor"]])
        res = {}
        for ek, hp, avg in enc:
            ts, wins = [], 0
            for s in range(60):
                f = Fight(cards, R.encounter(ek, hp, avg), random.Random(5000 + s), passive)
                t, w = f.run()
                ts.append(t)
                wins += 1 if w else 0
            res[ek] = dict(hp=hp, avg=avg, meanTurns=sum(ts) / len(ts), winRate=wins / len(ts))
        d["expect"] = res
        out.append(d)
    os.makedirs(os.path.dirname(OUT_VAL), exist_ok=True)
    with open(OUT_VAL, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("写出", OUT_VAL, len(out), "套")


if __name__ == "__main__":
    main()
