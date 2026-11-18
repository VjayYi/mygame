# -*- coding: utf-8 -*-
import json, os, re
from collections import defaultdict
D = os.path.dirname(__file__)
rows = json.load(open(os.path.join(D, "module_audit_v0.26.json"), encoding="utf-8"))
pool = json.load(open(os.path.join(D, "module_pool_v0.27.json"), encoding="utf-8"))
CATS = ["刀", "剑", "爪", "斧", "拳套", "步枪", "炮筒", "手枪", "弓"]
TIER_CAT = ["用该品类通关爬塔 1 次", "用该品类累计击败 3 个不同小 Boss", "用该品类无伤击败 1 名精英"]
TIER_GEN = ["爬塔累计通关 3 次", "累计击败全部 6 个小 Boss", "剧情模式通关第 1 章"]
lock = {}
by_cat = defaultdict(list); gen = []
for r in rows:
    if r["size"] < 5: continue
    pl = pool.get(r["name"])
    if pl == "基地·限定": by_cat[r["limit"]].append(r)
    elif pl == "基地·通用": gen.append(r)
for cat in CATS:
    g = sorted(by_cat[cat], key=lambda r: r["b1"])
    top3 = g[-3:]
    for i, r in enumerate(top3): lock[r["name"]] = TIER_CAT[i]
g = sorted(gen, key=lambda r: r["b1"])[-3:]
for i, r in enumerate(g): lock[r["name"]] = TIER_GEN[i]
json.dump(lock, open(os.path.join(D, "module_unlock_v0.27.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
tot56 = sum(1 for r in rows if r["size"] >= 5 and pool.get(r["name"]) in ("基地·限定", "基地·通用"))
print(len(lock), "/", tot56)
