using System;
using ProbabilityEdge.Core;

// 粗略平衡模拟：朴素策略（每回合投满、打有效血量最低目标、事件选安全或冒险、强化按策略）。
// 这不是人类最优策略，只用于比较不同数值方案的相对压力。
internal static class Sim
{
    private static void Set(string kind, int hp, params string[] actions)
    {
        EnemyTemplate t = ChapterOne.Template(kind);
        t.hp = hp; t.actions = actions;
    }

    private static int Main(string[] args)
    {
        if (args.Length == 3 && args[0] == "scale")
        {
            double dmg = double.Parse(args[1]), hp = double.Parse(args[2]);
            foreach (string kind in new[] { "patrol", "binder", "security", "mage", "elite", "operator", "captain" })
            {
                EnemyTemplate t = ChapterOne.Template(kind);
                t.hp = (int)Math.Round(t.hp * hp);
                for (int i = 0; i < t.actions.Length; i++)
                {
                    string a = t.actions[i];
                    int colon = a.IndexOf(':');
                    if (colon > 0 && a.StartsWith("attack")) t.actions[i] = "attack:" + (int)Math.Round(int.Parse(a.Substring(colon + 1)) * dmg);
                }
            }
            Console.WriteLine("伤害×" + dmg + " 生命×" + hp);
            Run("mix", false, 2000);
            return 0;
        }
        if (args.Length > 0 && args[0] == "v2")
        {
            int v = args.Length > 1 ? int.Parse(args[1]) : 0;
            Set("patrol", 24, "attack:" + (9 + v));
            Set("binder", 30, "wait", "attack:" + (22 + v));
            Set("security", 38, "attack:" + (12 + v), "charge", "attack:" + (22 + v));
            Set("mage", 36, "shield:8", "attack:" + (11 + v), "attack:" + (11 + v));
            Set("elite", 72, "shield:10", "charge", "attack:" + (32 + v), "attack:" + (14 + v));
            Set("operator", 40, "wait", "attack:" + (20 + v), "attack:" + (12 + v));
            Set("captain", 110, "shield:12", "charge", "attack:" + (38 + v), "attack:" + (16 + v));
            Console.WriteLine("v2 偏移=" + v);
            Run("mix", false, 3000);
            Run("sword", true, 3000);
            return 0;
        }
        // 默认：直接使用 ChapterOne 当前数值。
        Run("mix", false, 3000);
        Run("sword", true, 3000);
        Run("shield", false, 3000);
        return 0;
    }

    private static void Run(string strategy, bool risky, int runs)
    {
        int clean = 0, totalRetries = 0, maxRetries = 0;
        int[] defeats = new int[ChapterOne.NodeCount];
        int[] wins = new int[ChapterOne.NodeCount];
        long[] turns = new long[ChapterOne.NodeCount];
        long[] hpLoss = new long[ChapterOne.NodeCount];
        long endHp = 0;
        for (uint seed = 1; seed <= runs; seed++)
        {
            GameSession session = GameSession.New(seed * 2654435761u);
            int retries = 0, upgrades = 0, hpAtStart = 100;
            for (int step = 0; session.Data.state.phase != "completed" && step < 50000; step++)
            {
                GameState s = session.Data.state;
                if (s.phase == "story") session.Advance();
                else if (s.phase == "choice") session.Advance(0);
                else if (s.phase == "event") session.ResolveEvent(risky);
                else if (s.phase == "eventResult") session.Advance();
                else if (s.phase == "supply")
                {
                    if (!s.supplyClaimed) session.ClaimSupply();
                    else if (session.CurrentNode.reward && !session.CurrentUpgradeChosen)
                    {
                        string pick = strategy == "mix" ? (upgrades % 2 == 0 ? "sword" : "shield") : strategy;
                        session.Upgrade(pick); upgrades++;
                    }
                    else session.Advance();
                }
                else if (s.phase == "defeat") { defeats[s.nodeIndex]++; retries++; session.ResetBattle(); }
                else if (s.pendingFace >= 0)
                {
                    EnemyState best = null;
                    foreach (EnemyState e in s.enemies) if (e.hp > 0 && (best == null || e.hp + e.shield < best.hp + best.shield)) best = e;
                    int node = s.nodeIndex, turn = s.turn;
                    session.ChooseTarget(best.id);
                    if (session.Data.state.nodeIndex != node)
                    {
                        wins[node]++; turns[node] += turn;
                        hpLoss[node] += hpAtStart - session.Data.state.hp;
                    }
                }
                else if (s.rollsLeft > 0)
                {
                    if (s.rollsLeft == GameSession.RollsPerTurn && s.turn == 1) hpAtStart = s.hp;
                    session.Roll();
                }
                else session.EndTurn();
            }
            if (retries == 0) clean++;
            totalRetries += retries; maxRetries = Math.Max(maxRetries, retries);
            endHp += session.Data.state.hp;
        }
        Console.WriteLine("策略=" + strategy + (risky ? " 事件冒险" : " 事件安全") + " | 无失败通关 " + (100.0 * clean / runs).ToString("0.0") +
            "% | 平均重试 " + ((double)totalRetries / runs).ToString("0.00") + " | 最多重试 " + maxRetries + " | 章末平均生命 " + (endHp / runs));
        for (int i = 0; i < ChapterOne.NodeCount; i++)
        {
            if (ChapterOne.Node(i).kind != "battle") continue;
            int attempts = wins[i] + defeats[i];
            Console.WriteLine("  " + ChapterOne.Node(i).id + " " + ChapterOne.Node(i).title.PadRight(6) +
                " 单次失败率 " + (100.0 * defeats[i] / Math.Max(1, attempts)).ToString("0.0").PadLeft(5) + "%" +
                " | 平均回合 " + ((double)turns[i] / Math.Max(1, wins[i])).ToString("0.0").PadLeft(4) +
                " | 胜场平均掉血 " + ((double)hpLoss[i] / Math.Max(1, wins[i])).ToString("0.0").PadLeft(5));
        }
    }
}
