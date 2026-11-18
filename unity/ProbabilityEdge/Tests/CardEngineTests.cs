using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using ProbabilityEdge.Core.Cards;

// 卡牌战斗内核测试：JSON、拼图、构筑，以及与 Python 贪心模拟的统计对拍（RNG 不同，不能逐点相等）。
internal static class CardEngineTests
{
    private static Action<bool, string> check;
    private static CardPool pool;

    private static string Find(string rel)
    {
        string dir = AppContext.BaseDirectory;
        for (int i = 0; i < 10 && dir != null; i++)
        {
            string p = Path.Combine(dir, rel);
            if (File.Exists(p)) return p;
            dir = Path.GetDirectoryName(dir);
        }
        throw new FileNotFoundException(rel);
    }

    internal static void Run(Action<string, Action> run, Action<bool, string> assertion)
    {
        check = assertion;
        pool = CardPool.LoadFile(Find("Assets/ProbabilityEdge/Resources/CardData/cardpool.json"));
        run("卡牌：卡池数量与武器轮廓格数", PoolCounts);
        run("卡牌：模块形状变换、旋转镜像与去重", ShapeTransforms);
        run("卡牌：拼图放置规则（越界、缺口、重叠、重复）", GridRules);
        run("卡牌：自动放置与回溯重排", GridPacking);
        run("卡牌：随机模块组合的拼装成功率", PackRate);
        run("卡牌：梗武器 30 张牌可完整结算（只验证不出错）", MemeSmoke);
        run("卡牌：战斗文字层（出牌、结束回合、自动）可完整跑完一场", TextLayer);
        run("卡牌：战斗引擎与 Python 贪心模拟统计对拍", Validation);
    }

    private static void PoolCounts()
    {
        check(pool.modules.Count == 240, "模块 240，实际 " + pool.modules.Count);
        check(pool.hands.Count == 30 && pool.feet.Count == 30, "手脚各 30");
        check(pool.brains.Count == 20 && pool.torsos.Count == 20, "脑躯各 20");
        check(pool.armor["头"].Count == 30 && pool.armor["躯干"].Count == 30 && pool.armor["四肢"].Count == 30, "防具每部位 30");
        check(pool.weapons.Count == 27, "武器 27");
        check(pool.memes.Count == 6 && pool.memes.All(m => m.cards.Count == 5), "梗武器 6×5");
        foreach (var w in pool.weapons.Values)
        {
            int n = w.mask.Sum(r => r.Count(c => c == '#'));
            check(n == w.volume, w.Key + " 轮廓格数 " + n + " 应为 " + w.volume);
            check(w.items.Count == 4, w.Key + " 基础卡 4 张");
        }
        foreach (var m in pool.modules)
        {
            check(pool.shapes.ContainsKey(m.shape), m.name + " 形状存在");
            check(pool.shapes[m.shape].Length == m.size, m.name + " 形状格数=尺寸");
            check(m.cards.Count == 1 && m.ultFx != null, m.name + " 有 1 张牌和终极效果");
        }
    }

    private static void ShapeTransforms()
    {
        foreach (var kv in pool.shapes)
        {
            for (int rot = 0; rot < 4; rot++)
                foreach (bool mir in new[] { false, true })
                {
                    var t = ModuleGrid.Transform(kv.Value, rot, mir);
                    check(t.Count == kv.Value.Length, kv.Key + " 变换后格数不变");
                    check(t.Min(c => c[0]) == 0 && t.Min(c => c[1]) == 0, kv.Key + " 变换后归一到原点");
                    check(t.Select(c => c[0] + "," + c[1]).Distinct().Count() == t.Count, kv.Key + " 无重复格");
                }
        }
        check(ModuleGrid.Orientations(pool.shapes["块4"]).Count == 1, "块4（2×2）只有 1 种朝向");
        check(ModuleGrid.Orientations(pool.shapes["直4"]).Count == 2, "直4 有 2 种朝向");
        check(ModuleGrid.Orientations(pool.shapes["钩4"]).Count == 8, "钩4（L）有 8 种朝向（含镜像）");
        check(ModuleGrid.Orientations(pool.shapes["十5"]).Count == 1, "十5 只有 1 种朝向");
    }

    private static ItemDef ByShape(string shape) { return pool.modules.First(m => m.shape == shape); }

    private static void GridRules()
    {
        // 刀·改装：第 0 行 "..#####."（前两列、末列是缺口）
        var w = pool.weapons["刀|改装"];
        check(w.mask[0] == "..#####." && w.mask[1] == "########", "刀改装轮廓：" + w.mask[0]);
        var g = new ModuleGrid(w, pool.shapes);
        string why;
        var m2 = ByShape("直3");
        check(g.Place(m2, 0, false, 1, 0, out why), "合法放置：" + why);
        check(!g.Place(m2, 0, false, 1, 3, out why) && why.Contains("已装配"), "同一模块不能重复放");
        var other = pool.modules.First(m => m.shape == "直3" && m != m2);
        check(!g.Place(other, 0, false, 1, 2, out why) && why.Contains("重叠"), "重叠被拒：" + why);
        check(!g.Place(other, 0, false, 1, 6, out why) && why.Contains("超出"), "越界被拒：" + why);
        check(!g.Place(other, 0, false, 0, 0, out why) && why.Contains("缺口"), "缺口被拒：" + why);
        check(g.Place(other, 1, false, 0, 5, out why), "旋转后放置：" + why);
        check(g.Used == 6 && g.Free == 20, "已用/剩余计数");
        check(g.Remove(m2) && g.Used == 3, "移除");
        var occ = g.Occupancy();
        int occupied = 0;
        for (int r = 0; r < g.rows; r++) for (int c = 0; c < g.cols; c++) if (occ[r, c] >= 0) occupied++;
        check(occupied == 3, "占用格数");
    }

    private static void GridPacking()
    {
        var g = new ModuleGrid(pool.weapons["剑|均衡"], pool.shapes);
        var mods = pool.ModulesFor("剑").Where(m => m.size >= 4).Take(3).ToList();
        string why;
        foreach (var m in mods) check(g.AutoPlace(m, out why), "自动放置 " + m.name + "：" + why);
        check(g.Repack(mods), "回溯重排");
        check(g.Used == mods.Sum(m => m.size), "重排后总格数不变");
        // 容积不够必然失败
        var big = pool.modules.Where(m => m.size == 7).Take(4).ToList();
        check(!new ModuleGrid(pool.weapons["斧|强攻"], pool.shapes).Repack(big), "超容积重排失败且不破坏");
        // 失败的 Repack 不改变原摆放
        var g2 = new ModuleGrid(pool.weapons["斧|强攻"], pool.shapes);
        var small = pool.modules.First(m => m.size == 3);
        g2.AutoPlace(small, out why);
        int before = g2.placed.Count;
        g2.Repack(big);
        check(g2.placed.Count == before && g2.placed[0].module == small, "Repack 失败保持原状");
    }

    private static void PackRate()
    {
        // 与 Python 采样一致：模块总格数 ≤ 容积×80%，随机 3~5 个，统计真实形状能否拼进去
        var rng = new Random(7);
        int ok = 0, total = 0;
        var byForm = new Dictionary<string, int[]>();
        foreach (var w in pool.weapons.Values)
        {
            var legal = pool.ModulesFor(w.cat);
            for (int k = 0; k < 40; k++)
            {
                int want = 3 + rng.Next(3);
                var picks = new List<ItemDef>();
                int used = 0;
                for (int tries = 0; tries < 80 && picks.Count < want; tries++)
                {
                    var m = legal[rng.Next(legal.Count)];
                    if (picks.Contains(m) || used + m.size > w.volume * 0.8) continue;
                    picks.Add(m); used += m.size;
                }
                var g = new ModuleGrid(w, pool.shapes);
                bool good = g.Repack(picks, 60000);
                total++;
                if (good) ok++;
                int[] a; if (!byForm.TryGetValue(w.form, out a)) byForm[w.form] = a = new int[2];
                a[1]++; if (good) a[0]++;
            }
        }
        Console.WriteLine("  随机模块组合（≤80% 容积）真实拼装成功率：" + ok + "/" + total + " = " + (100.0 * ok / total).ToString("F0") + "%；" +
            string.Join("，", byForm.Select(kv => kv.Key + " " + (100.0 * kv.Value[0] / kv.Value[1]).ToString("F0") + "%")));
        check(total > 0, "统计有效");
    }

    private static void MemeSmoke()
    {
        foreach (var meme in MemeCards.Names)
        {
            var spec = BuildSpec.CreateMeme(pool, meme, 5);
            foreach (string kind in new[] { "mob", "elite", "final" })
            {
                int wins = 0;
                for (int s = 0; s < 12; s++)
                {
                    var d = DeckBuilder.Build(pool, spec, 4, s);
                    var f = new Fight(d.cards, Encounters.Make(kind, Encounters.RecHp(kind, 3), Encounters.Avg[kind]), 100 + s, d.passive);
                    var r = f.Run();
                    check(r.Key >= 1 && r.Key <= 60, meme + " 回合数合法");
                    check(!double.IsNaN(f.hp) && !double.IsNaN(f.shield), meme + " 数值无 NaN");
                    if (r.Value) wins++;
                }
                check(wins >= 0, meme + " 打 " + kind + " 结算完成（胜率不作要求，梗武器暂无模块）");
            }
            check(MemeCards.Make(meme, null).Count == 5, meme + " 5 张牌");
        }
    }

    private static void TextLayer()
    {
        var spec = BuildSpec.Create(pool, "剑", "均衡", 3);
        var d = DeckBuilder.Build(pool, spec, 4, 3);
        var f = new Fight(d.cards, Encounters.Make("mob", 108, 6), 11, d.passive);
        int lines = 0;
        for (int t = 1; t <= 40; t++)
        {
            f.BeginTurn(t);
            for (int i = 0; i < f.enemies.Count; i++) lines += BattleText.EnemyLine(f, i).Length > 0 ? 1 : 0;
            if (t % 2 == 0)
            {
                var c = f.hand.FirstOrDefault(x => f.CostOf(x) <= f.energy);
                if (c != null)
                {
                    var snap = Snap.Take(f);
                    string eff = BattleText.Eff(f, c);
                    int cost = f.CostOf(c);
                    f.Play(c);
                    lines += BattleText.Diff(f, snap, c, cost).Count + eff.Length;
                }
            }
            else lines += BattleText.AutoTurn(f).Count;
            bool? res;
            lines += BattleText.EnemyPhase(f, out res).Count;
            if (res.HasValue) { check(res.Value, "人工混合出牌能赢小怪"); break; }
        }
        check(lines > 0 && BattleText.Status(f) != null, "文字层输出有效");
    }

    // 读取 Python 导出的对拍套牌
    private static void Validation()
    {
        string json = File.ReadAllText(Find("Tests/CardData/validation.json"), Encoding.UTF8);
        var decks = MiniJson.Arr(MiniJson.Parse(json));
        var enc = new[] { "mob", "elite", "mini", "final" };
        double sumPy = 0, sumCs = 0;
        int bad = 0, n = 0;
        var report = new StringBuilder();
        foreach (var o in decks)
        {
            var d = MiniJson.Obj(o);
            string type = MiniJson.S(d, "type");
            BuildSpec spec;
            if (type == "std")
            {
                spec = new BuildSpec { cat = MiniJson.S(d, "cat"), form = MiniJson.S(d, "form") };
                spec.forcedMods = MiniJson.Arr(d["mods"]).Select(x => pool.FindModule((string)x)).ToList();
                check(spec.forcedMods.All(m => m != null), "模块名都存在");
            }
            else spec = BuildSpec.CreateMeme(pool, MiniJson.S(d, "meme"), 1);
            var hands = MiniJson.Arr(d["hands"]).Select(x => pool.Find(pool.hands, (string)x)).ToArray();
            var feet = MiniJson.Arr(d["feet"]).Select(x => pool.Find(pool.feet, (string)x)).ToArray();
            check(hands.All(x => x != null) && feet.All(x => x != null), "义体名都存在");
            spec.hands = hands; spec.feet = feet;
            spec.brain = pool.Find(pool.brains, MiniJson.S(d, "brain"));
            spec.torso = pool.Find(pool.torsos, MiniJson.S(d, "torso"));
            var arm = MiniJson.Arr(d["armor"]).Select(x => (string)x).ToList();
            for (int i = 0; i < 3; i++) spec.armor[i] = pool.Find(pool.armor[CardPool.ArmorParts[i]], arm[i]);
            check(spec.brain != null && spec.torso != null && spec.armor.All(x => x != null), "脑/躯/防具存在");
            var expect = MiniJson.Obj(d["expect"]);
            var built = DeckBuilder.Build(pool, spec, 0, 1);
            string label = type == "std" ? spec.cat + "·" + spec.form : MiniJson.S(d, "meme");
            var line = new StringBuilder("    " + label.PadRight(14));
            foreach (var kind in enc)
            {
                var e = MiniJson.Obj(expect[kind]);
                double hp = MiniJson.N(e, "hp"), avg = MiniJson.N(e, "avg");
                double py = MiniJson.N(e, "meanTurns");
                int tot = 0, wins = 0;
                for (int s = 0; s < 200; s++)
                {
                    var f = new Fight(built.cards, Encounters.Make(kind, hp, avg), 9000 + s, built.passive);
                    var r = f.Run();
                    tot += r.Key;
                    if (r.Value) wins++;
                }
                double cs = tot / 200.0;
                sumPy += py; sumCs += cs; n++;
                double tol = Math.Max(1.5, 0.15 * py);
                if (Math.Abs(cs - py) > tol) bad++;
                line.Append(" " + kind + " " + py.ToString("F1") + "/" + cs.ToString("F1"));
            }
            report.AppendLine(line.ToString());
        }
        Console.WriteLine("  对拍（Python 均值/C# 均值，每格 60/200 局）：");
        Console.Write(report.ToString());
        double ratio = sumCs / sumPy;
        Console.WriteLine("  总体 C#/Python = " + ratio.ToString("F3") + "；单格偏差超限 " + bad + "/" + n);
        check(Math.Abs(ratio - 1.0) < 0.06, "总体回合数偏差应在 6% 内，实际比值 " + ratio.ToString("F3"));
        check(bad <= n * 0.10, "单格偏差超限比例应 ≤10%，实际 " + bad + "/" + n);
    }
}
