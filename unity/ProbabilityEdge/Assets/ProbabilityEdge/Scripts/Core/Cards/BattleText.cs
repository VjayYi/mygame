using System;
using System.Collections.Generic;
using System.Linq;

namespace ProbabilityEdge.Core.Cards
{
    // 战斗信息的文字化：卡面结算数值、敌人意图、状态与每步变化。Unity 界面与文字日志共用。
    public sealed class Snap
    {
        public double hp, shield;
        public int energy, hand;
        public List<double[]> es = new List<double[]>(); // hp, dot, stunned, edown, phases, alive

        public static Snap Take(Fight g)
        {
            var s = new Snap { hp = g.hp, shield = g.shield, energy = g.energy, hand = g.hand.Count };
            foreach (var e in g.enemies)
                s.es.Add(new[] { e.hp, e.dot, e.stunned ? 1 : 0, e.edown, e.phases.Count, e.Alive ? 1 : 0 });
            return s;
        }
    }

    public static class BattleText
    {
        public static string Eff(Fight g, Card card)
        {
            var v = g.Vals(card);
            double hits = Math.Max(1.0, v.hits);
            double flat = g.turnAtk + g.atkFlat;
            var o = new List<string>();
            if (v.dmg > 0) o.Add("伤害 " + (v.dmg + g.nextAtk + flat * hits).ToString("F0") + (hits > 1 ? "（" + (int)hits + " 段）" : ""));
            if (v.aoe > 0) o.Add("全体 " + (v.aoe + flat).ToString("F0"));
            if (v.dot > 0) o.Add("持续伤害 " + v.dot.ToString("F0") + " 层");
            if (v.shield > 0) o.Add("护盾 " + v.shield.ToString("F0"));
            if (v.shieldNext > 0) o.Add("下回合护盾 " + v.shieldNext.ToString("F0"));
            if (v.heal > 0) o.Add("回复 " + v.heal.ToString("F0"));
            if (v.draw > 0) o.Add("抽 " + v.draw.ToString("F0"));
            if (v.energy > 0) o.Add("能源 +" + v.energy.ToString("F0"));
            if (v.stun > 0) o.Add("击晕 " + (v.stun * 100).ToString("F0") + "%");
            if (v.nextatk > 0) o.Add("下一张攻击 +" + v.nextatk.ToString("F0"));
            if (v.turnatk > 0) o.Add("本回合攻击 +" + v.turnatk.ToString("F0"));
            if (v.edown > 0) o.Add("敌攻击 -" + v.edown.ToString("F0"));
            if (v.costdown > 0) o.Add("下一张费用 -1");
            if (v.selfdmg > 0) o.Add("自伤 " + v.selfdmg.ToString("F0"));
            if (card.hpCost != 0) o.Add("每次打出失去 " + card.hpCost + " 生命");
            return o.Count > 0 ? string.Join("，", o) : "（见卡面）";
        }

        public static string CardTitle(Fight g, Card c)
        {
            int cost = g.CostOf(c);
            string cs = cost + "费" + (cost != c.cost ? "(原" + c.cost + ")" : "");
            return "[" + cs + "] " + c.Label + (c.exhaust ? "【消耗】" : "");
        }

        public static List<string> Status(Fight g)
        {
            var o = new List<string>();
            if (g.Flag("pity") != 0) o.Add("保底层 " + (int)g.Flag("pity"));
            if (g.Flag("seal") != 0) o.Add("封印层 " + (int)g.Flag("seal"));
            if (g.Flag("transform") != 0) o.Add("变身剩余 " + (int)g.Flag("transform") + " 回合");
            if (g.Flag("dark") != 0) o.Add("【黑化】");
            if (g.clip != null) o.Add("剪贴板：" + g.clip.name);
            if (g.queue.Count > 0) o.Add("配送中：" + string.Join("、", g.queue.Select(q => q.Key.name + "（" + q.Value + " 回合）")));
            if (g.energyNext != 0) o.Add("下回合能源 " + g.energyNext.ToString("+0;-0"));
            if (g.drawNext != 0) o.Add("下回合抽牌 " + g.drawNext.ToString("+0;-0"));
            if (g.costPlusNextTurn != 0) o.Add("下回合前 " + g.costPlusNextTurn + " 张牌费用 +1");
            if (g.shieldCarry != 0) o.Add("下回合护盾 +" + g.shieldCarry.ToString("F0"));
            if (g.noShield) o.Add("无法获得护盾");
            if (g.turnAtk + g.atkFlat >= 0.5) o.Add("本回合攻击 +" + (g.turnAtk + g.atkFlat).ToString("F0"));
            if (g.nextAtk != 0) o.Add("下一张攻击 +" + g.nextAtk.ToString("F0"));
            return o;
        }

        public static string EnemyLine(Fight g, int i)
        {
            var e = g.enemies[i];
            if (!e.Alive) return "[" + (i + 1) + "] " + e.name + "  已击败";
            string ph = e.nphase > 1 ? "阶段 " + (e.nphase - e.phases.Count) + "/" + e.nphase + " " : "";
            var st = new List<string>();
            if (e.dot > 0) st.Add("持续伤害 " + e.dot.ToString("F0") + " 层");
            if (e.flatDot.Count > 0) st.Add("差评 " + e.flatDot[0][0].ToString("F0") + "×" + e.flatDot[0][1].ToString("F0") + " 回合");
            if (e.edown > 0) st.Add("本次攻击 -" + e.edown.ToString("F0"));
            if (e.immune > 0) st.Add("击晕免疫 " + e.immune);
            string it;
            if (e.stunned) it = "已被击晕：本回合不行动";
            else
            {
                double now = Math.Max(0.0, e.Intent(g.turn) - e.edown);
                it = "将造成 " + now.ToString("F0") + "（之后 " + e.FutureIntent(g.turn, 1).ToString("F0") + "、" + e.FutureIntent(g.turn, 2).ToString("F0") + "）";
            }
            return "[" + (i + 1) + "] " + e.name + " " + ph + "生命 " + e.hp.ToString("F0") + "/" + e.maxhp.ToString("F0") + "  意图：" + it +
                   (st.Count > 0 ? "  〔" + string.Join("，", st) + "〕" : "");
        }

        public static List<string> Diff(Fight g, Snap b, Card played, int cost)
        {
            var a = Snap.Take(g);
            var o = new List<string>();
            for (int i = 0; i < b.es.Count; i++)
            {
                var eb = b.es[i]; var ea = a.es[i];
                string name = "[" + (i + 1) + "]" + g.enemies[i].name;
                if (ea[4] < eb[4]) o.Add(name + " 被击破，进入下一阶段（生命 " + g.enemies[i].hp.ToString("F0") + "）");
                else if (eb[5] > 0 && ea[5] == 0) o.Add(name + " 被击败");
                else if (ea[0] < eb[0]) o.Add(name + " 生命 -" + (eb[0] - ea[0]).ToString("F0"));
                if (ea[1] > eb[1]) o.Add(name + " 持续伤害 +" + (ea[1] - eb[1]).ToString("F0") + " 层");
                if (ea[2] > 0 && eb[2] == 0) o.Add(name + " 被击晕");
                if (ea[3] > eb[3]) o.Add(name + " 下次攻击 -" + (ea[3] - eb[3]).ToString("F0"));
            }
            if (Math.Abs(a.shield - b.shield) > 1e-9) o.Add("护盾 " + (a.shield - b.shield).ToString("+0;-0") + "（现 " + a.shield.ToString("F0") + "）");
            if (Math.Abs(a.hp - b.hp) > 1e-9) o.Add("生命 " + (a.hp - b.hp).ToString("+0;-0") + "（现 " + a.hp.ToString("F0") + "）");
            int gain = a.energy - b.energy + (played != null ? cost : 0);
            if (gain != 0) o.Add("能源 " + gain.ToString("+0;-0"));
            if (played != null)
            {
                int drawn = a.hand - (b.hand - 1);
                if (drawn != 0) o.Add("手牌 " + drawn.ToString("+0;-0"));
            }
            return o;
        }

        // 玩家回合结束 + 敌人行动，返回描述行；result：null 继续，true 胜，false 负
        public static List<string> EnemyPhase(Fight g, out bool? result)
        {
            var lines = new List<string>();
            double preHp = g.hp, preSh = g.shield;
            var pre = g.enemies.Select(e => new[] { e.hp, e.stunned ? 1.0 : 0.0, e.Intent(g.turn) - e.edown, e.Alive ? 1.0 : 0.0 }).ToList();
            result = g.EndTurn();
            for (int i = 0; i < g.enemies.Count; i++)
                if (pre[i][3] > 0 && pre[i][1] > 0) lines.Add("[" + (i + 1) + "] " + g.enemies[i].name + " 被击晕，跳过行动");
            double lost = preHp - g.hp;
            double shUsed = g.shield < preSh ? preSh - g.shield : 0;
            double sum = 0;
            for (int i = 0; i < pre.Count; i++) if (pre[i][3] > 0 && pre[i][1] == 0) sum += Math.Max(0, pre[i][2]);
            lines.Add("敌人行动：总攻击 " + sum.ToString("F0") + "，护盾抵挡 " + Math.Min(shUsed, sum).ToString("F0") + "，你损失 " + lost.ToString("F0") + " 生命（现 " + g.hp.ToString("F0") + "）");
            for (int i = 0; i < pre.Count; i++)
                if (pre[i][3] > 0 && g.enemies[i].Alive && g.enemies[i].hp < pre[i][0] && pre[i][1] == 0)
                    lines.Add("[" + (i + 1) + "] " + g.enemies[i].name + " 受持续伤害 -" + (pre[i][0] - g.enemies[i].hp).ToString("F0"));
            return lines;
        }

        // 自动打本回合（贪心），返回出牌顺序与变化
        public static List<string> AutoTurn(Fight g)
        {
            var lines = new List<string>();
            var before = Snap.Take(g);
            var names = new List<string>();
            for (int n = 0; n < Fight.MaxPlays; n++)
            {
                if (g.AliveEnemies().Count == 0 || g.hp <= 0) break;
                Card best = null; double bestR = 0;
                foreach (var c in g.hand)
                {
                    int k = g.CostOf(c);
                    if (k > g.energy) continue;
                    double u = g.Utility(c);
                    if (u <= 0.3) continue;
                    double r = u / Math.Max(k, 0.5);
                    if (r > bestR) { best = c; bestR = r; }
                }
                if (best == null) break;
                names.Add(best.Label);
                g.Play(best);
            }
            lines.Add("自动出牌：" + (names.Count > 0 ? string.Join("、", names) : "（无）"));
            foreach (var d in Diff(g, before, null, 0)) lines.Add("  · " + d);
            return lines;
        }
    }
}
