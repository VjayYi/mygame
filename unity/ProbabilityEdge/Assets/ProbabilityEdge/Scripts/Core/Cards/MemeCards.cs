using System;
using System.Collections.Generic;
using System.Linq;

namespace ProbabilityEdge.Core.Cards
{
    // 6 把梗武器（每把 5 张）的结算实现，与 outputs/balance/gsim_meme.py 对应。
    public static class MemeCards
    {
        public static readonly string[] Names = { "魔法少女的法杖", "氪金手机", "程序员键盘", "社畜工牌保温杯", "绷带右手", "外卖保温箱" };

        private static Fx V(double dmg = 0, double aoe = 0, double shield = 0, double heal = 0, double draw = 0, double energy = 0,
            double stun = 0, double nextatk = 0, double turnatk = 0, double edown = 0, double selfdmg = 0)
        {
            return new Fx { dmg = dmg, aoe = aoe, shield = shield, heal = heal, draw = draw, energy = energy, stun = stun,
                nextatk = nextatk, turnatk = turnatk, edown = edown, selfdmg = selfdmg, hits = 1.0 };
        }

        private static Card Mk(string name, int cost, Fx v, Func<Fight, Fx> est = null, Action<Fight, Card> special = null,
            Func<Fight, double> uext = null, bool exhaust = false)
        {
            return new Card { name = name, cost = cost, v = v ?? V(), est = est, special = special, uext = uext, exhaust = exhaust, kind = "meme" };
        }

        private static Card BestOther(Fight g)
        {
            Card best = null;
            foreach (var c in g.hand) if (best == null || c.v.CompE() > best.v.CompE()) best = c;
            return best;
        }

        private static void Pity(Fight g, double n) { g.SetFlag("pity", Math.Min(8, g.Flag("pity") + n)); }
        private static void Seal(Fight g, double n) { g.SetFlag("seal", Math.Min(6, g.Flag("seal") + n)); }

        public static List<Card> Make(string name, Dictionary<string, string> texts)
        {
            var list = Build(name);
            foreach (var c in list) { string t; if (texts != null && texts.TryGetValue(c.name, out t)) c.text = t; }
            return list;
        }

        private static List<Card> Build(string name)
        {
            switch (name)
            {
                case "魔法少女的法杖": return W1();
                case "氪金手机": return W2();
                case "程序员键盘": return W3();
                case "社畜工牌保温杯": return W4();
                case "绷带右手": return W5();
                case "外卖保温箱": return W6();
            }
            throw new ArgumentException("未知梗武器：" + name);
        }

        // ---- 1 魔法少女的法杖
        private static List<Card> W1()
        {
            return new List<Card>
            {
                Mk("和我签订契约吧", 1, V(), special: (g, c) =>
                {
                    var cand = g.hand.Where(x => x.IsAttack).ToList();
                    if (cand.Count == 0) cand = g.hand.Where(x => x.v.shield > 0).ToList();
                    if (cand.Count == 0) return;
                    Card t = null;
                    foreach (var x in cand) if (t == null || x.v.dmg + x.v.aoe + x.v.shield > t.v.dmg + t.v.aoe + t.v.shield) t = x;
                    if (t.v.dmg > 0) t.v.dmg += 4; else if (t.v.aoe > 0) t.v.aoe += 4; else t.v.shield += 4;
                    t.hpCost += 2;
                }, uext: g => g.hand.Any(x => x.IsAttack) ? 3.5 : 0.0),
                Mk("变身！", 3, V(), special: (g, c) =>
                {
                    g.SetFlag("transform", 2);
                    g.atkFlat += 4;
                    g.startHooks.Add(gg =>
                    {
                        if (gg.Flag("dark") != 0) { gg.HurtSelf(2); return; }
                        if (gg.Flag("transform") > 0)
                        {
                            gg.SetFlag("transform", gg.Flag("transform") - 1);
                            if (gg.Flag("transform") == 0) { gg.atkFlat += -4 + 2; gg.noShield = true; gg.SetFlag("dark", 1); }
                        }
                    });
                }, exhaust: true, uext: g => g.turn <= 2 && g.Flag("transform") == 0 ? 7.0 : 0.0),
                Mk("已经没什么好怕的了", 1, V(turnatk: 3), special: (g, c) =>
                {
                    Action<Fight> hook = null;
                    hook = gg =>
                    {
                        if (gg.hp <= gg.maxhp * 0.5) gg.HurtSelf(8); else gg.hp = Math.Min(gg.maxhp, gg.hp + 3);
                        gg.endHooks.Remove(hook);
                    };
                    g.endHooks.Add(hook);
                }, uext: g => g.hp <= g.maxhp * 0.5 ? -2.0 : 0.0),
                Mk("魔杖其实是平底锅", 1, V(dmg: 3), special: (g, c) =>
                {
                    int r = g.rng.Next(1, 7);
                    var tgt = g.Target();
                    if (r <= 2 && tgt != null) g.Damage(tgt, 4);
                    else if (r <= 4) g.shield += 4;
                    else if (r == 5) g.DrawCards(1);
                    else foreach (var e in g.AliveEnemies()) g.Damage(e, 3);
                }),
                Mk("魔法少女·俺", 1, V(), est: g => V(dmg: 1.5 * g.shield), special: (g, c) => g.shield = Math.Ceiling(g.shield / 2.0)),
            };
        }

        // ---- 2 氪金手机
        private static List<Card> W2()
        {
            return new List<Card>
            {
                Mk("单抽", 1, V(dmg: 5), special: (g, c) => Pity(g, g.Rand() < 0.3 ? 3 : 1)),
                Mk("十连！", 3, V(), est: g => V(dmg: 5.5, shield: 3.5, aoe: 50 * Math.Min(1.0, 0.10 + 0.03 * g.Flag("pity"))), special: (g, c) => g.SetFlag("pity", 0)),
                Mk("保底！", 1, V(), est: g => V(dmg: 3 * Math.Min(g.Flag("pity"), 6), draw: g.Flag("pity") >= 4 ? 2 : 0), special: (g, c) => g.SetFlag("pity", 0)),
                Mk("非酋的怒火", 1, V(shield: 4), special: (g, c) =>
                {
                    g.SetFlag("fei", g.turn);
                    if (g.Flag("fei_hook") == 0)
                    {
                        g.SetFlag("fei_hook", 1);
                        g.hurtHooks.Add((gg, dealt) => { if (gg.Flag("fei") == gg.turn) Pity(gg, 1); });
                    }
                }),
                Mk("卸载重下", 1, V(draw: 2), special: (g, c) => Pity(g, 2), exhaust: true),
            };
        }

        // ---- 3 程序员键盘
        private static List<Card> W3()
        {
            return new List<Card>
            {
                Mk("Ctrl+C", 1, V(), special: (g, c) =>
                {
                    var cand = BestOther(g);
                    if (cand != null) { g.clip = cand.Clone(); g.clip.exhaust = true; }
                }, uext: g => g.hand.Any(x => x.v.CompE() >= 1.3) ? 3.0 : -1.0),
                Mk("Ctrl+V", 1, V(), special: (g, c) =>
                {
                    if (g.clip != null) { var x = g.clip.Clone(); x.costAdj = -x.cost; g.hand.Add(x); }
                }, uext: g => g.clip != null ? g.clip.v.CompE() * 6.0 * 0.9 : -9.0),
                Mk("Ctrl+Z", 1, V(), est: g => V(shield: Math.Min(10.0, 0.7 * g.Incoming()), draw: 1)),
                Mk("Alt+F4", 2, V(), est: g => { var t = g.Target(); return t != null && t.boss ? V(dmg: 10) : V(stun: 1.0); }, exhaust: true),
                Mk("rm -rf /", 3, V(), est: g => V(dmg: 4.0 * Math.Max(0, g.hand.Count - 1)), special: (g, c) =>
                {
                    int n = g.hand.Count;
                    g.discard.AddRange(g.hand);
                    g.hand = new List<Card>();
                    if (n >= 5) g.shield += 999;
                }, exhaust: true, uext: g => g.hand.Count >= 6 ? 6.0 : 0.0),
            };
        }

        // ---- 4 社畜工牌保温杯
        private static List<Card> W4()
        {
            return new List<Card>
            {
                Mk("画大饼", 1, V(energy: 2), special: (g, c) => g.drawNext -= 2),
                Mk("加班", 1, V(), special: (g, c) => { g.costTurn += 1; g.costPlusNextTurn = 2; },
                    uext: g => 2.5 * Math.Min(3, g.hand.Count(x => x.cost >= 1)) - 2.5),
                Mk("背锅", 1, V(), est: g => V(shield: Math.Min(8.0, 0.5 * g.Incoming()), dmg: Math.Min(8.0, 0.5 * g.Incoming()))),
                Mk("保温杯里泡枸杞", 1, V(heal: 3), special: (g, c) =>
                {
                    int[] left = { 3 };
                    Action<Fight> start = null;
                    start = gg =>
                    {
                        if (left[0] > 0)
                        {
                            left[0] -= 1;
                            gg.hp = Math.Min(gg.maxhp, gg.hp + 1);
                            if (left[0] == 0) gg.startHooks.Remove(start);
                        }
                    };
                    g.startHooks.Add(start);
                    Action<Fight> end = null;
                    end = gg =>
                    {
                        if (!gg.played.Any(x => x.IsAttack)) gg.hp = Math.Min(gg.maxhp, gg.hp + 3);
                        gg.endHooks.Remove(end);
                    };
                    g.endHooks.Add(end);
                }, uext: g => 3.0),
                Mk("KPI 考核", 2, V(), special: (g, c) =>
                {
                    Action<Fight> end = null;
                    end = gg =>
                    {
                        int kinds = gg.played.Select(x => x.cost).Distinct().Count();
                        foreach (var e in gg.AliveEnemies()) gg.Damage(e, 2 * Math.Min(kinds, 4));
                        if (kinds >= 3) gg.drawNext += 2;
                        gg.endHooks.Remove(end);
                    };
                    g.endHooks.Add(end);
                }, uext: g => 7.0),
            };
        }

        // ---- 5 绷带右手
        private static List<Card> W5()
        {
            return new List<Card>
            {
                Mk("吃我这招·暗黑火焰", 1, V(dmg: 5), special: (g, c) => Seal(g, 1)),
                Mk("我的右手……在疼……", 1, V(shield: 3), special: (g, c) =>
                {
                    g.SetFlag("pain", g.turn);
                    g.SetFlag("pain_n", 0);
                    if (g.Flag("pain_hook") == 0)
                    {
                        g.SetFlag("pain_hook", 1);
                        g.hurtHooks.Add((gg, dealt) =>
                        {
                            if (gg.Flag("pain") == gg.turn && gg.Flag("pain_n") < 3) { gg.SetFlag("pain_n", gg.Flag("pain_n") + 1); Seal(gg, 1); }
                        });
                    }
                }),
                Mk("解除封印！", 1, V(), est: g => g.Flag("seal") >= 2 ? V(turnatk: 4, draw: 1) : V(selfdmg: 3),
                    special: (g, c) => { if (g.Flag("seal") >= 2) g.SetFlag("seal", g.Flag("seal") - 2); else Seal(g, 1); }),
                Mk("邪王真眼", 1, V(), est: g =>
                {
                    double mx = 0;
                    foreach (var e in g.AliveEnemies()) mx = Math.Max(mx, e.Intent(g.turn));
                    return V(edown: Math.Min(6.0, 0.5 * mx));
                }),
                Mk("爆裂魔法", 3, V(), est: g => g.Flag("seal") > 0 ? V(aoe: 6 * g.Flag("seal")) : V(selfdmg: 3),
                    special: (g, c) => { g.SetFlag("seal", 0); g.energyNext = -3; }, exhaust: true,
                    uext: g => g.Flag("seal") >= 3 ? 2.0 : -12.0),
            };
        }

        // ---- 6 外卖保温箱
        private static double Delivered(Fight g) { return g.Flag("delivered") == g.turn && g.turn > 0 ? 1 : 0; }

        private static List<Card> W6()
        {
            return new List<Card>
            {
                Mk("您有一份外卖", 1, V(), special: (g, c) =>
                {
                    var cand = BestOther(g);
                    if (cand == null) return;
                    g.hand.Remove(cand);
                    g.queue.Add(new KeyValuePair<Card, int>(cand, 2));
                    if (g.Flag("queue_hook") == 0)
                    {
                        g.SetFlag("queue_hook", 1);
                        g.startHooks.Add(gg =>
                        {
                            var keep = new List<KeyValuePair<Card, int>>();
                            foreach (var item in gg.queue)
                            {
                                int left = item.Value - 1;
                                if (left <= 0)
                                {
                                    var x = item.Key;
                                    x.costAdj -= 1;
                                    if (x.v.dmg > 0) x.v.dmg += 3; else if (x.v.aoe > 0) x.v.aoe += 3; else x.v.shield += 3;
                                    gg.hand.Add(x);
                                    gg.SetFlag("delivered", gg.turn);
                                }
                                else keep.Add(new KeyValuePair<Card, int>(item.Key, left));
                            }
                            gg.queue = keep;
                        });
                    }
                }, uext: g => g.hand.Any(x => x.v.CompE() >= 1.2) && g.turn <= 8 ? 4.0 : -6.0),
                Mk("加急配送", 1, V(draw: 1), special: (g, c) =>
                {
                    foreach (var item in g.queue) g.hand.Add(item.Key);
                    if (g.queue.Count > 0) g.SetFlag("delivered", g.turn);
                    g.queue = new List<KeyValuePair<Card, int>>();
                }, uext: g => g.queue.Count > 0 ? 3.0 : -3.0),
                Mk("差评！", 1, V(dmg: 3), special: (g, c) => { var t = g.Target(); if (t != null) t.flatDot.Add(new double[] { 2, 2 }); }),
                Mk("五星好评", 1, V(), est: g => { double d = Delivered(g); return V(shield: 4 + 4 * d, energy: 1 * d); }),
                Mk("闯红灯！", 1, V(), est: g => { double d = Delivered(g); return V(dmg: 9 + 3 * d, selfdmg: 3 * (1 - d)); }),
            };
        }
    }
}
