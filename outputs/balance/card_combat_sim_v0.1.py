"""卡牌战斗粗算 v0.1
目的：不是精确模拟，是"大概跑一下"——基于已经定下数值的卡
（义体卡 v0.2、防具卡 v0.2、武器基础卡 v0.14、模块目录 v0.21 的抽样）
推算"成熟构筑"每回合的大致攻防产出，再反推普通/精英/Boss 需要什么量级的
生命和伤害，才能匹配这套输出。

口径（粗糙，刻意从简）：
1. 玩家每回合 3 能源、每回合抽 5 张（已在 v0.3/v0.17/implant v0.1 中定过）。
2. 用"每点能源的产出"代替逐卡模拟：
   - 攻击：约 4.5 伤害/能源（见下方抽样统计）
   - 防御：约 5 护盾/能源（见下方抽样统计）
   这两个数字不是拍板数值，是从已写死的卡表里抽样算出来的，用来做这一轮的粗算。
3. 护盾不跨回合保留（多数卡如此，少数"护盾保留"是例外，粗算先忽略）。
4. 玩家按"够防就防，不够就全攻"的简单策略分配能源：
   - 本回合预计受到的伤害 <=5：0 能源点防御，全攻击
   - <=10：1 能源点防御，2 能源点攻击
   - <=15：2 能源点防御，1 能源点攻击
   - 否则：3 能源点全防御
5. 每场战斗跑 2000 次，伤害有 ±15% 随机波动，直到一方倒下或 30 回合超时判负。

抽样统计（手算自现有文档，写在这里留痕）：
- 义体手部 15 种攻击类，cost>=1 的 14 张里，总伤害/总费用 ≈ 68/17 ≈ 4.0 伤害/能源
- 武器基础卡（v0.14 示例）：劈砍 1费6伤=6.0，突刺 1费4伤(+流血)≈5
- 模块目录 v0.21 纯伤害类（按尺寸粗配费用 2→1/3→1/4→2/5→2/6→3）：
  刃口强化4.0、巨刃崩击4.5、大构重装4.67、重炮管4.5，其余多在 2.5~3.5
- 综合取整：攻击 4.5 伤害/能源，防御（护盾甲 1费5护盾、义体脚多数 1费3~4护盾）取 5 护盾/能源
"""
import random

ENERGY_PER_TURN = 3
DMG_PER_ENERGY = 4.5
SHIELD_PER_ENERGY = 5.0
PLAYER_HP = 100
TRIALS = 3000
ROUNDS_CAP = 30


def allocate(incoming_est, hp, max_hp):
    """够防就防、不够也不躺：正常情况最多留 2 能源防御（保底 1 能源攻击），
    只有生命低于 25% 时才允许 3 能源全防，避免"防御锁死、永远 0 输出"的死局。"""
    hp_frac = hp / max_hp
    cap = ENERGY_PER_TURN if hp_frac <= 0.25 else (ENERGY_PER_TURN - 1)
    if incoming_est <= 5:
        d = 0
    elif incoming_est <= 10:
        d = 1
    elif incoming_est <= 15:
        d = 2
    else:
        d = 3
    return min(d, cap)


def simulate(enemy_hp, enemy_dmg, hits_per_turn=1, trials=TRIALS, dmg_var=0.15):
    wins = 0
    rounds_list = []
    for _ in range(trials):
        hp = PLAYER_HP
        ehp = enemy_hp
        rounds = 0
        while hp > 0 and ehp > 0 and rounds < ROUNDS_CAP:
            rounds += 1
            incoming = 0.0
            for _ in range(hits_per_turn):
                incoming += enemy_dmg * random.uniform(1 - dmg_var, 1 + dmg_var)
            def_e = allocate(incoming, hp, PLAYER_HP)
            off_e = ENERGY_PER_TURN - def_e
            shield = def_e * SHIELD_PER_ENERGY
            dmg_out = off_e * DMG_PER_ENERGY * random.uniform(1 - dmg_var, 1 + dmg_var)
            ehp -= dmg_out
            hp -= max(0.0, incoming - shield)
        if ehp <= 0 and hp > 0:
            wins += 1
        rounds_list.append(rounds)
    return wins / trials, sum(rounds_list) / len(rounds_list)


def scan(label, hp_list, dmg_list, hits_per_turn=1, target=None):
    print(f"\n=== {label}（每回合攻击 {hits_per_turn} 次）===")
    print(f"{'HP':<6}" + "".join(f"DMG{d:<6}" for d in dmg_list))
    for hp in hp_list:
        row = f"{hp:<6}"
        for dmg in dmg_list:
            wr, avg_r = simulate(hp, dmg, hits_per_turn)
            row += f"{wr:<9.0%}"
        print(row)
    if target is not None:
        print(f"(目标胜率区间参考：{target})")


def solve_dmg_per_hit(hp, hits_per_turn, target, lo=1.0, hi=40.0, iters=16, trials=1200):
    """二分：固定敌人 HP 与每回合攻击次数，求单次伤害命中目标胜率。"""
    for _ in range(iters):
        mid = (lo + hi) / 2
        wr, _ = simulate(hp, mid, hits_per_turn, trials=trials)
        if wr > target:
            lo = mid
        else:
            hi = mid
    mid = (lo + hi) / 2
    wr, avg_r = simulate(hp, mid, hits_per_turn, trials=2500)
    return mid, wr, avg_r


def solve_table(label, hp_list, target, hits_options=(1, 2, 3)):
    print(f"\n=== {label}：反解单次伤害（目标胜率≈{target:.0%}）===")
    print(f"{'HP':<6}" + "".join(f"{h}次/回合(单次伤害,实际胜率,均回合)".ljust(26) for h in hits_options))
    for hp in hp_list:
        row = f"{hp:<6}"
        for h in hits_options:
            dmg, wr, avg_r = solve_dmg_per_hit(hp, h, target)
            row += f"{dmg:5.1f}/{wr:4.0%}/{avg_r:4.1f}  "
        print(row)


if __name__ == "__main__":
    random.seed(42)
    scan("普通怪·单体", [25, 35, 45, 55], [7, 9, 11, 13], hits_per_turn=1, target="90~97%")
    scan("普通怪·双体围攻", [18, 24, 30, 36], [6, 7, 8, 9], hits_per_turn=2, target="80~90%")
    scan("精英", [70, 90, 110, 130], [11, 14, 17, 20], hits_per_turn=1, target="60~75%")
    scan("小Boss", [110, 140, 170, 200], [14, 17, 20, 23], hits_per_turn=1, target="45~60%")
    scan("大Boss（终章，粗算单阶段）", [170, 210, 250, 290], [16, 19, 22, 25], hits_per_turn=1, target="35~50%")

    print("\n\n################ 反解：单次伤害 vs 多段攻击，看悬崖是否能抹平 ################")
    solve_table("普通怪", [25, 35, 45], target=0.93)
    solve_table("精英", [70, 90, 110], target=0.68)
    solve_table("小Boss", [120, 150, 180], target=0.52)
    solve_table("大Boss（单阶段粗算）", [180, 220, 260], target=0.42)
