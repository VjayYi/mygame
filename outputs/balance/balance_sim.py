# -*- coding: utf-8 -*-
"""首版数值粗模拟。目的：校准量级与比较方案，不代表真实游戏平衡。
简化：敌人护盾/有限回复/分裂/召唤/镜层折算为有效耐久；腐蚀折算为额外DPS；
减益/强化类特效不模拟。自动目标：优先可击杀目标，其次威胁(DPS/耐久)最高。
"""
import random, statistics, sys
sys.path.insert(0, ".")
import balance_data as D

random.seed(20261014)

PARTY = {"E05": ["M02", "M01"], "E13": ["M01", "M04"]}

def byid():
    return {x["id"]: x for x in D.M + D.E + D.B + D.FINAL}

class En:
    def __init__(self, d, hp_mult=1.0, dmg_mult=1.0, idx=0):
        self.id = d["id"]
        self.ehp = (d["hp"] + d["shield"] + d["extra_ehp"]) * hp_mult
        self.dmg = d["dmg"] * dmg_mult
        self.hits = d["hits"]
        self.interval = d["interval"]
        self.bonus = d["bonus_dps"] * dmg_mult
        self.next = self.interval * (0.55 + 0.12 * idx)
        self.one_shot = (d["id"] == "M21")
        self.alive = True
        self.counter = 0.0
    @property
    def dps(self):
        return (self.dmg * self.hits / self.interval) + self.bonus

def face_list(loadout):
    f = []
    for k, n in loadout.items():
        f += [k] * n
    assert len(f) == 10, loadout
    return f

def pick_target(enemies, dmg):
    alive = [e for e in enemies if e.alive]
    if not alive:
        return None
    kill = [e for e in alive if e.ehp <= dmg]
    if kill:
        return max(kill, key=lambda e: e.dps)
    return max(alive, key=lambda e: e.dps / max(e.ehp, 1))

def apply_skill(p, face, enemies, mult):
    s = D.SKILLS[face]
    if face in ("sword", "gun"):
        dmg = s["dmg"] * mult["dmg"]
        t = pick_target(enemies, dmg)
        if t:
            t.ehp -= dmg
            if t.ehp <= 0:
                t.alive = False
    elif face == "shield":
        p["shield"] += s["shield"] * mult["shield"]
    elif face == "heart":
        p["hp"] = min(p["max"], p["hp"] + s["heal"] * mult["heal"])

def hurt(p, amount):
    absorbed = min(p["shield"], amount)
    p["shield"] -= absorbed
    p["hp"] -= amount - absorbed

# ---------- 实时 ----------
def fight_rt(p, enemies, faces, mult, interval):
    t = 0.0
    next_roll = interval * 0.5
    p["shield"] = 0.0
    while True:
        t += 0.1
        if t >= next_roll:
            apply_skill(p, random.choice(faces), enemies, mult)
            next_roll += interval
        for e in enemies:
            if e.alive and t >= e.next:
                hurt(p, e.dmg * e.hits)
                e.next += e.interval
                if e.one_shot:
                    e.alive = False
        bonus = sum(e.bonus for e in enemies if e.alive) * 0.1
        if bonus:
            hurt(p, bonus)
        if not any(e.alive for e in enemies):
            return True, t
        if p["hp"] <= 0:
            return False, t
        if t > 240:
            return False, t

def make_normals(n, hp_mult, dmg_mult):
    B = byid()
    ids = random.sample([m["id"] for m in D.M], n)
    return [En(B[i], hp_mult, dmg_mult, k) for k, i in enumerate(ids)]

def make_elite(eid, hp_mult, dmg_mult):
    B = byid()
    out = [En(B[eid], hp_mult, dmg_mult, 0)]
    for k, i in enumerate(PARTY.get(eid, [])):
        out.append(En(B[i], hp_mult, dmg_mult, k + 1))
    return out

def run_street(loadout, street_n=1, tail="normal", growth=False, runs=2000):
    faces = face_list(loadout)
    hpm = 1 + 0.20 * (street_n - 1)
    dmm = 1 + 0.12 * (street_n - 1)
    sizes = [2, 3, 3] if tail == "elite" else [2, 3, 3, 3]
    cleared, fights = 0, []
    for _ in range(runs):
        p = {"hp": 100, "max": 100, "shield": 0}
        mult = {"dmg": 1.0, "shield": 1.0, "heal": 1.0}
        if growth:
            for k in mult: mult[k] *= 1.20
        ok = True
        specs = [("n", s) for s in sizes] + ([("e", None)] if tail == "elite" else [])
        for kind, s in specs:
            hp0 = p["hp"]
            en = make_normals(s, hpm, dmm) if kind == "n" else make_elite(random.choice(D.E)["id"], hpm, dmm)
            win, dur = fight_rt(p, en, faces, mult, D.PLAYER["roll_interval_s"])
            fights.append((kind, win, dur, max(0, hp0 - max(p["hp"], 0))))
            if not win:
                ok = False
                break
            if growth:
                g = 1.25 if kind == "e" else 1.04
                for k in mult: mult[k] *= g
        cleared += ok
    return cleared / runs, fights

def stats_fights(fights, kind):
    f = [x for x in fights if x[0] == kind and x[1]]
    if not f:
        return None
    return (round(statistics.mean(x[2] for x in f), 1), round(statistics.mean(x[3] for x in f), 1))

def elite_single(eid, runs=600, street_n=1):
    faces = face_list(D.LOADOUTS["均衡 4剑3盾2心1枪"])
    wins, lost, dur = 0, [], []
    hpm = 1 + 0.20 * (street_n - 1); dmm = 1 + 0.12 * (street_n - 1)
    for _ in range(runs):
        p = {"hp": 100, "max": 100, "shield": 0}
        win, d = fight_rt(p, make_elite(eid, hpm, dmm), faces, {"dmg": 1.0, "shield": 1.0, "heal": 1.0}, 2.0)
        wins += win; lost.append(100 - max(p["hp"], 0)); dur.append(d)
    return wins / runs, statistics.mean(lost), statistics.mean(dur)

# ---------- 回合制 ----------
def fight_turn(p, enemies, faces, R, mult):
    p["shield"] = 0.0
    turns = 0
    dead_turns = 0
    while True:
        turns += 1
        attack_rolls = 0
        for _ in range(R):
            f = random.choice(faces)
            if f in ("sword", "gun"):
                attack_rolls += 1
            apply_skill(p, f, enemies, mult)
            if not any(e.alive for e in enemies):
                return True, turns, dead_turns
        if attack_rolls == 0:
            dead_turns += 1
        for e in enemies:
            if not e.alive:
                continue
            e.counter += (2 * R) / e.interval
            while e.counter >= 1.0 and e.alive:
                hurt(p, e.dmg * e.hits)
                e.counter -= 1.0
                if e.one_shot:
                    e.alive = False
            if e.bonus:
                hurt(p, e.bonus * 2 * R)
        if p["hp"] <= 0:
            return False, turns, dead_turns
        if turns > 60:
            return False, turns, dead_turns

def turn_compare(R, runs=3000):
    faces = face_list(D.LOADOUTS["均衡 4剑3盾2心1枪"])
    res = {"turns": [], "lost": [], "dead": [], "win": 0, "n": 0}
    for _ in range(runs):
        s = random.choice([2, 3])
        p = {"hp": 100, "max": 100, "shield": 0}
        en = make_normals(s, 1.0, 1.0)
        hp0 = p["hp"]
        ok, t, dead = fight_turn(p, en, faces, R, {"dmg": 1.0, "shield": 1.0, "heal": 1.0})
        res["win"] += ok; res["n"] += 1
        res["turns"].append(t); res["lost"].append(hp0 - max(p["hp"], 0)); res["dead"].append(dead / t)
    return {
        "R": R, "win": round(res["win"] / res["n"], 3),
        "avg_turns": round(statistics.mean(res["turns"]), 2),
        "avg_hp_lost": round(statistics.mean(res["lost"]), 1),
        "hp_lost_std": round(statistics.pstdev(res["lost"]), 1),
        "dead_turn_rate": round(statistics.mean(res["dead"]), 3),
    }

# ---------- 长局：第1层10事件 + 小Boss ----------
def make_boss(bid, layer):
    B = byid()
    hp_m, dm_m = (1.0, 1.0) if layer == 1 else (1.75, 1.3)
    return [En(B[bid], hp_m, dm_m, 0)]

def boss_fight(bid, layer, prog, max_hp, start_frac, R=3, runs=1500):
    faces = face_list(D.LOADOUTS["均衡 4剑3盾2心1枪"])
    wins, turns, lost = 0, [], []
    for _ in range(runs):
        p = {"hp": max_hp * start_frac, "max": max_hp, "shield": 0}
        hp0 = p["hp"]
        ok, t, _ = fight_turn(p, make_boss(bid, layer), faces, R, {"dmg": prog, "shield": prog, "heal": prog})
        wins += ok; turns.append(t); lost.append(hp0 - max(p["hp"], 0))
    return wins / runs, statistics.mean(turns), statistics.mean(lost)

def final_boss(prog, max_hp, start_frac, R=3, runs=1500):
    faces = face_list(D.LOADOUTS["均衡 4剑3盾2心1枪"])
    B = byid(); wins, turns = 0, []
    for _ in range(runs):
        p = {"hp": max_hp * start_frac, "max": max_hp, "shield": 0}
        t_all, ok = 0, True
        for fid in ("F01", "F02", "F03"):
            ok, t, _ = fight_turn(p, [En(B[fid])], faces, R, {"dmg": prog, "shield": prog, "heal": prog})
            t_all += t
            if not ok:
                break
        wins += ok; turns.append(t_all)
    return wins / runs, statistics.mean(turns)

def layer1_run(R=3, runs=1500, boss_id="B01"):
    faces = face_list(D.LOADOUTS["均衡 4剑3盾2心1枪"])
    reached, beat, boss_turns = 0, 0, []
    for _ in range(runs):
        p = {"hp": 100, "max": 100, "shield": 0}
        mult = {"dmg": 1.0, "shield": 1.0, "heal": 1.0}
        dead = False
        for e_idx in range(1, 11):
            if random.random() < 0.70:
                hpm = 1 + 0.05 * (e_idx - 1); dmm = 1 + 0.02 * (e_idx - 1)
                if e_idx >= 4 and random.random() < 0.12:
                    en = make_elite(random.choice(D.E)["id"], hpm, dmm); g = 1.25
                else:
                    en = make_normals(random.choice([2, 3]), hpm, dmm); g = 1.04
                ok, _, _ = fight_turn(p, en, faces, R, mult)
                if not ok:
                    dead = True; break
                for k in mult: mult[k] *= g
                if random.random() < 0.12 * len(en):
                    for k in mult: mult[k] *= 1.06
            else:
                r = random.random()
                if r < 0.60: p["hp"] = min(p["max"], p["hp"] + 20)
                elif r < 0.90:
                    for k in mult: mult[k] *= 1.08
        if dead:
            continue
        reached += 1
        ok, t, _ = fight_turn(p, make_boss(boss_id, 1), faces, R, mult)
        beat += ok; boss_turns.append(t)
    return reached / runs, beat / runs, statistics.mean(boss_turns) if boss_turns else 0

if __name__ == "__main__":
    print("== 实时·街区1（不成长）==")
    for name, lo in D.LOADOUTS.items():
        a, fa = run_street(lo, 1, "normal", False)
        b, fb = run_street(lo, 1, "elite", False)
        print(f"{name}: 4普通关清街区={a:.0%}  3普通+精英尾关={b:.0%}  普通战(秒,失血)={stats_fights(fa,'n')}  精英战={stats_fights(fb,'e')}")
    lo = D.LOADOUTS["均衡 4剑3盾2心1枪"]
    print("== 实时·均衡配置，带成长近似（每街区仅入口+20%，不继承前区成长）==")
    for n in (1, 2, 3, 4, 5):
        a, fa = run_street(lo, n, "normal", True)
        b, fb = run_street(lo, n, "elite", True)
        print(f"街区{n}: 普通尾关={a:.0%} 精英尾关={b:.0%} 普通战={stats_fights(fa,'n')} 精英战={stats_fights(fb,'e')}")
    print("== 精英单战（均衡配置、满血、街区1）==")
    for e in D.E:
        w, l, d = elite_single(e["id"])
        print(f'{e["id"]} {e["name"]}: 胜率={w:.0%} 失血={l:.0f} 时长={d:.0f}s')
    print("== 回合制：2投 vs 3投（普通2~3怪，敌人单回合伤害按2R秒折算）==")
    for R in (2, 3):
        print(turn_compare(R))
    print("== 回合制·长局第1层（10事件，战斗约70%，成长近似）→小Boss ==")
    for bid in ("B01", "B02", "B03", "B04", "B05", "B06"):
        reach, beat, bt = layer1_run(3, 1200, bid)
        print(f"{bid}: 到达Boss={reach:.0%} 击败Boss(占全部)={beat:.0%} Boss平均回合={bt:.1f}")
    print("== 回合制·小Boss单战（玩家带成长倍率）==")
    for bid in ("B01", "B02", "B03", "B04", "B05", "B06"):
        w1, t1, l1 = boss_fight(bid, 1, 1.5, 120, 0.75)
        w2, t2, l2 = boss_fight(bid, 2, 2.2, 150, 0.75)
        print(f"{bid}: L1胜率={w1:.0%} 回合={t1:.1f} 失血={l1:.0f} | L2胜率={w2:.0%} 回合={t2:.1f} 失血={l2:.0f}")
    w, t = final_boss(2.8, 170, 0.8)
    print(f"大Boss(三阶段): 胜率={w:.0%} 总回合={t:.1f}")
