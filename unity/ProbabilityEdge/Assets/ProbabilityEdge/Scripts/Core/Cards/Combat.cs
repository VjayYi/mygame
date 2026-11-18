using System;
using System.Collections.Generic;
using System.Linq;

namespace ProbabilityEdge.Core.Cards
{
    // 战斗引擎：与 outputs/balance/gsim_core.py 逐行对应（Python 侧用于贪心模拟，这里用于可玩版本与对拍）。
    public sealed class Card
    {
        public string name, text, kind = "x";
        public int cost, hpCost, costAdj;
        public bool exhaust, upgraded;
        public Fx v;
        public Func<Fight, Fx> est;
        public Action<Fight, Card> special;
        public Func<Fight, double> uext;

        public static Card From(CardDef d, bool upgraded)
        {
            return new Card { name = d.name, text = d.text, cost = d.cost, exhaust = d.exhaust, v = d.fx.Clone(), upgraded = upgraded };
        }

        public Card Clone()
        {
            var c = (Card)MemberwiseClone();
            c.v = v.Clone();
            return c;
        }

        public bool IsAttack { get { return v.dmg > 0 || v.aoe > 0; } }
        public string Label { get { return name + (upgraded ? "+" : ""); } }
    }

    public sealed class Enemy
    {
        public string name;
        public double maxhp, hp, dot, edown, enrageRate = 0.1;
        public double[] pattern;
        public bool boss, stunned;
        public int immune, idx, enrageTurn = 99, nphase = 1;
        public List<KeyValuePair<double, double[]>> phases = new List<KeyValuePair<double, double[]>>();
        public List<double[]> flatDot = new List<double[]>();

        public bool Alive { get { return hp > 0; } }

        public double Intent(int turn)
        {
            double b = pattern[idx % pattern.Length];
            if (turn >= enrageTurn) b *= 1.0 + enrageRate * (turn - enrageTurn + 1);
            return b;
        }

        public double FutureIntent(int turn, int k)
        {
            double b = pattern[(idx + k) % pattern.Length];
            int t = turn + k;
            if (t >= enrageTurn) b *= 1.0 + enrageRate * (t - enrageTurn + 1);
            return b;
        }
    }

    public static class Encounters
    {
        public static readonly Dictionary<string, double[]> Pattern = new Dictionary<string, double[]>
        {
            { "elite", new[] { 0.75, 0.75, 1.5 } },
            { "mini", new[] { 0.8, 0.8, 1.5, 0.8, 1.6 } },
        };
        public static readonly Dictionary<string, int> Enrage = new Dictionary<string, int>
        {
            { "mob", 14 }, { "elite", 20 }, { "mini", 26 }, { "final", 40 }
        };
        public static readonly Dictionary<string, string> Names = new Dictionary<string, string>
        {
            { "mob", "小怪（2 体）" }, { "elite", "精英" }, { "mini", "小 Boss" }, { "final", "终极 Boss（3 阶段）" }
        };
        public static readonly Dictionary<string, double> Avg = new Dictionary<string, double>
        {
            { "mob", 8 }, { "elite", 21 }, { "mini", 20 }, { "final", 18 }
        };
        // 推荐生命：层 1/2/3（终极 Boss 三层相同）
        public static double RecHp(string kind, int layer)
        {
            switch (kind)
            {
                // v0.30：按“塞满模块的随机 build、起始 80 生命”校准（层 3 为校准层，层 1/2 按旧比例缩放）
                case "mob": return new[] { 82.0, 92.0, 104.0 }[layer - 1];
                case "elite": return new[] { 95.0, 107.0, 121.0 }[layer - 1];
                case "mini": return new[] { 150.0, 170.0, 195.0 }[layer - 1];
                default: return 286.0;
            }
        }
        public static readonly Dictionary<string, int[]> Window = new Dictionary<string, int[]>
        {
            { "mob", new[] { 5, 10 } }, { "elite", new[] { 8, 15 } }, { "mini", new[] { 13, 20 } }, { "final", new[] { 20, 30 } }
        };

        private static double[] Norm(double[] pat, double avg)
        {
            double m = pat.Average();
            return pat.Select(x => x / m * avg).ToArray();
        }

        public static List<Enemy> Make(string kind, double hp, double avg)
        {
            const double rate = 0.10;
            int en = Enrage[kind];
            var list = new List<Enemy>();
            if (kind == "mob")
            {
                list.Add(new Enemy { name = "怪甲", maxhp = hp / 2, hp = hp / 2, pattern = new[] { avg }, enrageTurn = en, enrageRate = rate });
                list.Add(new Enemy { name = "怪乙", maxhp = hp / 2, hp = hp / 2, pattern = new[] { avg }, enrageTurn = en, enrageRate = rate });
                return list;
            }
            if (kind == "elite" || kind == "mini")
            {
                list.Add(new Enemy { name = Names[kind], maxhp = hp, hp = hp, pattern = Norm(Pattern[kind], avg), boss = true, enrageTurn = en, enrageRate = rate });
                return list;
            }
            var mini = Pattern["mini"];
            var e = new Enemy
            {
                name = "终极 Boss", boss = true, enrageTurn = en, enrageRate = rate,
                maxhp = hp * 0.30, hp = hp * 0.30, pattern = Norm(mini, avg * 0.9)
            };
            e.phases.Add(new KeyValuePair<double, double[]>(hp * 0.35, Norm(mini, avg * 1.0)));
            e.phases.Add(new KeyValuePair<double, double[]>(hp * 0.35, Norm(mini, avg * 1.15)));
            e.nphase = 3;
            list.Add(e);
            return list;
        }
    }

    public sealed class Fight
    {
        public const double PlayerHp = 100;
        public const double StartHp = 80;
        public const int Energy0 = 3, Draw0 = 5, HandMax = 10, MaxPlays = 14;

        public readonly Random rng;
        public List<Enemy> enemies;
        public double hp = StartHp, maxhp = PlayerHp, shield, shieldCarry, nextAtk, turnAtk, atkFlat, hpLost, dmgTakenTurn;
        public int energy, energyNext, drawNext, costNext, costTurn, costPlusNextTurn, costPlusCards, turn;
        public bool noShield;
        public List<Card> hand = new List<Card>(), drawPile = new List<Card>(), discard = new List<Card>(), exhausted = new List<Card>(), played = new List<Card>();
        public Passive passive;
        public readonly Dictionary<string, double> flags = new Dictionary<string, double>();
        public Card clip;
        public List<KeyValuePair<Card, int>> queue = new List<KeyValuePair<Card, int>>();
        public List<Action<Fight>> endHooks = new List<Action<Fight>>(), startHooks = new List<Action<Fight>>();
        public List<Action<Fight, double>> hurtHooks = new List<Action<Fight, double>>();
        public Enemy pick;

        public Fight(IEnumerable<Card> deck, List<Enemy> enemies, int seed, Passive passive)
        {
            rng = new Random(seed);
            this.enemies = enemies;
            this.passive = passive ?? new Passive();
            foreach (var c in deck) drawPile.Add(c.Clone());
            Shuffle(drawPile);
        }

        public double Flag(string k) { double v; return flags.TryGetValue(k, out v) ? v : 0.0; }
        public void SetFlag(string k, double v) { flags[k] = v; }
        public double Rand() { return rng.NextDouble(); }

        public void Shuffle(List<Card> l)
        {
            for (int i = l.Count - 1; i > 0; i--)
            {
                int j = rng.Next(i + 1);
                var t = l[i]; l[i] = l[j]; l[j] = t;
            }
        }

        public void DrawCards(int n)
        {
            for (int k = 0; k < n; k++)
            {
                if (hand.Count >= HandMax) return;
                if (drawPile.Count == 0)
                {
                    if (discard.Count == 0) return;
                    drawPile = discard;
                    discard = new List<Card>();
                    Shuffle(drawPile);
                }
                var c = drawPile[drawPile.Count - 1];
                drawPile.RemoveAt(drawPile.Count - 1);
                hand.Add(c);
            }
        }

        public List<Enemy> AliveEnemies() { return enemies.Where(e => e.Alive).ToList(); }

        public Enemy Target()
        {
            if (pick != null && pick.Alive) return pick;
            Enemy best = null;
            foreach (var e in enemies) if (e.Alive && (best == null || e.hp < best.hp)) best = e;
            return best;
        }

        public Enemy MaxIntentEnemy()
        {
            if (pick != null && pick.Alive) return pick;
            Enemy best = null;
            foreach (var e in enemies) if (e.Alive && (best == null || e.Intent(turn) > best.Intent(turn))) best = e;
            return best;
        }

        public double IntentOf(Enemy e)
        {
            if (e.stunned && e.immune <= 0) return 0.0;
            return Math.Max(0.0, e.Intent(turn) - e.edown);
        }

        public double Incoming() { double s = 0; foreach (var e in enemies) if (e.Alive) s += IntentOf(e); return s; }

        public int CostOf(Card c)
        {
            int k = c.cost - costTurn - costNext;
            if (costPlusCards > 0) k += 1;
            return Math.Max(0, k + c.costAdj);
        }

        public Fx Vals(Card c) { return c.est != null ? c.est(this) : c.v; }

        public double Utility(Card card)
        {
            var v = Vals(card);
            double u = 0.0;
            double hits = Math.Max(1.0, v.hits);
            double flat = turnAtk + atkFlat;
            var tgt = Target();
            if (tgt == null) return 0.0;
            if (v.dmg > 0)
            {
                double d = v.dmg + nextAtk + flat * hits;
                u += Math.Min(d, tgt.hp);
                if (d >= tgt.hp) u += 0.6 * IntentOf(tgt);
            }
            if (v.aoe > 0)
                foreach (var e in AliveEnemies())
                {
                    double d = v.aoe + flat;
                    u += Math.Min(d, e.hp);
                    if (d >= e.hp) u += 0.6 * IntentOf(e);
                }
            if (v.dot > 0) u += v.dot * 1.5 * 0.9;
            double inc = Incoming();
            double need = Math.Max(0.0, inc - shield);
            double frac = hp / maxhp;
            double wdef = 0.85 + 1.4 * (1.0 - frac);
            if (inc - shield >= hp - 6) wdef += 3.0;
            if (!noShield)
            {
                u += wdef * Math.Min(v.shield, need);
                u += 0.5 * wdef * Math.Min(v.shieldNext, inc);
            }
            u += wdef * Math.Min(v.edown, IntentOf(tgt));
            u += 0.9 * Math.Min(v.heal, maxhp - hp);
            var others = hand.Where(c => !ReferenceEquals(c, card)).ToList();
            bool hasAtk = others.Any(c => c.IsAttack);
            int nAtk = others.Count(c => c.IsAttack);
            if (v.draw != 0) u += 2.4 * v.draw * (energy > CostOf(card) ? 1.0 : 0.35);
            if (v.energy != 0) u += 5.0 * v.energy * (others.Any(c => c.cost >= 1) ? 1.0 : 0.2);
            if (v.nextatk != 0) u += v.nextatk * 0.9 * (hasAtk ? 1.0 : 0.1);
            if (v.turnatk != 0) u += v.turnatk * 0.8 * Math.Min(nAtk, 3) * (hasAtk ? 1.0 : 0.1);
            if (v.costdown != 0) u += others.Any(c => CostOf(c) >= 1) ? 4.0 : 0.0;
            if (v.stun != 0 && !(tgt.boss && tgt.immune > 0) && !tgt.stunned) u += v.stun * IntentOf(tgt) * 1.0;
            u -= v.selfdmg * (0.9 + (1.0 - frac));
            u -= card.hpCost * (0.9 + (1.0 - frac));
            if (card.uext != null) u += card.uext(this);
            return u;
        }

        public void Apply(Card card)
        {
            var v = Vals(card);
            double hits = Math.Max(1.0, v.hits);
            double flat = turnAtk + atkFlat;
            var tgt = Target();
            if (v.dmg > 0 && tgt != null)
            {
                double d = v.dmg + nextAtk + flat * hits;
                nextAtk = 0.0;
                Damage(tgt, d);
            }
            if (v.aoe > 0)
            {
                foreach (var e in AliveEnemies()) Damage(e, v.aoe + flat);
                nextAtk = 0.0;
            }
            if (v.dot > 0)
            {
                var t2 = Target();
                if (t2 != null) t2.dot += v.dot;
            }
            if (v.shield != 0 && !noShield) shield += v.shield;
            shieldCarry += v.shieldNext;
            if (v.heal != 0) hp = Math.Min(maxhp, hp + v.heal);
            if (v.energy != 0) energy += (int)Math.Round(v.energy, MidpointRounding.ToEven);
            if (v.nextatk != 0) nextAtk += v.nextatk;
            if (v.turnatk != 0) turnAtk += v.turnatk;
            if (v.costdown != 0) costNext = 1;
            if (v.edown != 0)
            {
                var t3 = MaxIntentEnemy();
                if (t3 != null) t3.edown += v.edown;
            }
            if (v.stun != 0)
            {
                var t4 = MaxIntentEnemy();
                if (t4 != null && !(t4.boss && t4.immune > 0) && Rand() < v.stun) t4.stunned = true;
            }
            if (v.selfdmg != 0) HurtSelf(v.selfdmg);
            if (v.draw != 0)
            {
                double n = v.draw;
                if (n >= 1) DrawCards((int)Math.Round(n, MidpointRounding.ToEven));
            }
            if (card.hpCost != 0) HurtSelf(card.hpCost);
        }

        public void Damage(Enemy e, double d)
        {
            if (d <= 0 || !e.Alive) return;
            e.hp -= d;
            if (e.hp <= 0 && e.phases.Count > 0)
            {
                var ph = e.phases[0];
                e.phases.RemoveAt(0);
                e.hp = ph.Key; e.maxhp = ph.Key; e.pattern = ph.Value; e.idx = 0; e.dot = 0; e.stunned = false; e.edown = 0;
            }
        }

        public void HurtSelf(double d) { hp -= d; hpLost += d; }

        public void Play(Card card)
        {
            int c = CostOf(card);
            energy -= c;
            hand.Remove(card);
            costNext = 0;
            if (costPlusCards > 0) costPlusCards -= 1;
            Apply(card);
            if (card.special != null) card.special(this, card);
            played.Add(card);
            if (card.exhaust) exhausted.Add(card); else discard.Add(card);
        }

        public void PlayPhase()
        {
            for (int n = 0; n < MaxPlays; n++)
            {
                if (AliveEnemies().Count == 0 || hp <= 0) break;
                Card best = null;
                double bestR = 0.0;
                foreach (var card in hand)
                {
                    int c = CostOf(card);
                    if (c > energy) continue;
                    double u = Utility(card);
                    if (u <= 0.3) continue;
                    double r = u / Math.Max(c, 0.5);
                    if (r > bestR) { best = card; bestR = r; }
                }
                if (best == null) break;
                Play(best);
            }
        }

        public void BeginTurn(int t)
        {
            turn = t;
            shield = shieldCarry + passive.shield;
            shieldCarry = 0.0;
            energy = Energy0 + energyNext + (int)passive.energy;
            energyNext = 0;
            turnAtk = passive.turnatk;
            nextAtk = 0.0;
            costTurn = 0;
            costNext = 0;
            costPlusCards = costPlusNextTurn;
            costPlusNextTurn = 0;
            played = new List<Card>();
            dmgTakenTurn = 0.0;
            foreach (var h in startHooks.ToList()) h(this);
            DrawCards(Draw0 + drawNext + (int)passive.draw);
            drawNext = 0;
        }

        // 返回 null 继续、true 胜、false 负
        public bool? EndTurn()
        {
            foreach (var h in endHooks.ToList()) h(this);
            discard.AddRange(hand);
            hand = new List<Card>();
            if (AliveEnemies().Count == 0) return true;
            if (hp <= 0) return false;
            EnemyPhase();
            if (hp <= 0) return false;
            if (AliveEnemies().Count == 0) return true;
            return null;
        }

        public KeyValuePair<int, bool> Run(int maxTurns = 60)
        {
            for (int t = 1; t <= maxTurns; t++)
            {
                BeginTurn(t);
                PlayPhase();
                var res = EndTurn();
                if (res.HasValue) return new KeyValuePair<int, bool>(t, res.Value);
            }
            return new KeyValuePair<int, bool>(maxTurns, false);
        }

        public void EnemyPhase()
        {
            foreach (var e in AliveEnemies())
            {
                if (e.immune > 0) e.immune -= 1;
                if (e.stunned)
                {
                    e.stunned = false;
                    if (e.boss || e.phases.Count > 0) e.immune = 2;
                    e.idx += 1;
                    e.edown = 0.0;
                    continue;
                }
                double d = Math.Max(0.0, e.Intent(turn) - e.edown);
                e.edown = 0.0;
                e.idx += 1;
                double blocked = Math.Min(shield, d);
                shield -= blocked;
                double dealt = d - blocked;
                if (dealt > 0)
                {
                    hp -= dealt;
                    hpLost += dealt;
                    dmgTakenTurn += dealt;
                    foreach (var h in hurtHooks.ToList()) h(this, dealt);
                }
            }
            foreach (var e in AliveEnemies())
            {
                if (e.dot > 0)
                {
                    e.hp -= e.dot;
                    e.dot = Math.Max(0.0, e.dot - 1.0);
                }
                if (e.flatDot.Count > 0)
                {
                    e.hp -= e.flatDot[0][0];
                    e.flatDot[0][1] -= 1;
                    if (e.flatDot[0][1] <= 0) e.flatDot.RemoveAt(0);
                }
            }
            foreach (var e in enemies)
                if (e.hp <= 0 && e.phases.Count > 0)
                {
                    var ph = e.phases[0];
                    e.phases.RemoveAt(0);
                    e.hp = ph.Key; e.maxhp = ph.Key; e.pattern = ph.Value; e.idx = 0;
                }
        }
    }
}
