using System;
using System.Collections.Generic;
using System.Linq;

namespace ProbabilityEdge.Core.Cards
{
    // 构筑：武器（普通武器 + 模块拼图 / 梗武器）+ 义体 + 防具。测试版所有内容全部开放，不做解锁限制。
    public sealed class BuildSpec
    {
        public string meme;                 // 非空：梗武器
        public string cat = "剑", form = "均衡";
        public ModuleGrid grid;             // 普通武器的模块拼图
        public ItemDef[] hands = new ItemDef[2], feet = new ItemDef[2];
        public ItemDef brain, torso;
        public ItemDef[] armor = new ItemDef[3];
        public int upgrades = 4;

        public List<ItemDef> forcedMods;    // 仅测试/对拍用：绕过拼图直接指定模块
        public bool IsMeme { get { return !string.IsNullOrEmpty(meme); } }
        public List<ItemDef> Modules
        {
            get
            {
                if (forcedMods != null) return forcedMods;
                return grid == null ? new List<ItemDef>() : grid.placed.Select(p => p.module).ToList();
            }
        }

        public static BuildSpec Create(CardPool pool, string cat, string form, int seed)
        {
            var b = new BuildSpec { cat = cat, form = form };
            b.grid = new ModuleGrid(pool.weapons[cat + "|" + form], pool.shapes);
            b.Randomize(pool, seed, false);
            return b;
        }

        public static BuildSpec CreateMeme(CardPool pool, string meme, int seed)
        {
            var b = new BuildSpec { meme = meme };
            b.Randomize(pool, seed, false);
            return b;
        }

        public void SetWeapon(CardPool pool, string newCat, string newForm)
        {
            meme = null;
            cat = newCat; form = newForm;
            var old = grid == null ? new List<ItemDef>() : Modules;
            grid = new ModuleGrid(pool.weapons[cat + "|" + form], pool.shapes);
            // 尽量保留已选模块（限定品类不符的丢弃，装不下的丢弃）
            var legal = pool.ModulesFor(cat);
            var keep = old.Where(m => legal.Contains(m)).ToList();
            if (!grid.Repack(keep))
                foreach (var m in keep) { string w; grid.AutoPlace(m, out w); }
        }

        // 随机补全：没选的位置随机；mods=true 时同时重抽模块
        public void Randomize(CardPool pool, int seed, bool mods)
        {
            var rng = new Random(seed);
            if (hands[0] == null || mods) { hands[0] = Pick(pool.hands, rng); hands[1] = PickOther(pool.hands, rng, hands[0]); }
            if (feet[0] == null || mods) { feet[0] = Pick(pool.feet, rng); feet[1] = PickOther(pool.feet, rng, feet[0]); }
            if (brain == null || mods) brain = Pick(pool.brains, rng);
            if (torso == null || mods) torso = Pick(pool.torsos, rng);
            for (int i = 0; i < 3; i++)
                if (armor[i] == null || mods) armor[i] = Pick(pool.armor[CardPool.ArmorParts[i]], rng);
            if (!IsMeme && grid != null && mods)
            {
                // 随机 build：按真实形状尽量填满。重复 12 次，保留填得最满的一次
                var best = new List<Placement>();
                int bestUsed = -1;
                string w;
                for (int t = 0; t < 12; t++)
                {
                    grid.Clear();
                    foreach (var m in pool.ModulesFor(cat).OrderBy(x => rng.Next()))
                    {
                        if (grid.Free < 3) break;
                        if (m.size > grid.Free) continue;
                        grid.AutoPlace(m, out w);
                    }
                    if (grid.Used > bestUsed) { bestUsed = grid.Used; best = new List<Placement>(grid.placed); }
                }
                grid.placed.Clear();
                grid.placed.AddRange(best);
            }
        }

        private static ItemDef Pick(List<ItemDef> l, Random r) { return l[r.Next(l.Count)]; }
        private static ItemDef PickOther(List<ItemDef> l, Random r, ItemDef not)
        {
            for (int i = 0; i < 50; i++) { var x = l[r.Next(l.Count)]; if (x != not) return x; }
            return l[0];
        }
    }

    public static class GridExt
    {
        public static int Modules(this ModuleGrid g) { return g.placed.Count; }
    }

    public sealed class BuiltDeck
    {
        public List<Card> cards = new List<Card>();
        public Passive passive = new Passive();
        public string ultText = "";
    }

    public static class DeckBuilder
    {
        public static Fx UltFx(IEnumerable<ItemDef> mods)
        {
            var v = new Fx { dmg = 6 };
            foreach (var m in mods) if (m.ultFx != null) v.AddUlt(m.ultFx);
            return v;
        }

        public static string UltText(IEnumerable<ItemDef> mods)
        {
            return "伤害 +6" + string.Concat(mods.Select(m => "；" + m.name + "：" + m.ult));
        }

        public static BuiltDeck Build(CardPool pool, BuildSpec b, int upgrades, int seed)
        {
            var rng = new Random(seed);
            var res = new BuiltDeck();
            var items = new List<ItemDef>();
            var pairs = new List<KeyValuePair<CardPair, bool>>(); // (pair, 梗武器卡不可强化)
            var memeCards = new List<Card>();
            if (b.IsMeme)
            {
                var texts = pool.memes.First(m => m.name == b.meme).cards.ToDictionary(c => c.name, c => c.text);
                memeCards = MemeCards.Make(b.meme, texts);
            }
            else
            {
                items.AddRange(pool.weapons[b.cat + "|" + b.form].items);
                items.AddRange(b.Modules);
                res.passive.Add(pool.weapons[b.cat + "|" + b.form].passive);
            }
            items.AddRange(b.hands);
            items.AddRange(b.feet);
            items.Add(b.brain);
            items.Add(b.torso);
            items.AddRange(b.armor);
            items.AddRange(pool.generic);
            res.passive.Add(b.brain.passive);
            res.passive.Add(b.torso.passive);
            foreach (var it in items) foreach (var p in it.cards) pairs.Add(new KeyValuePair<CardPair, bool>(p, true));
            // 随机强化 N 张（梗武器自带牌不参与）
            var idx = Enumerable.Range(0, pairs.Count).OrderBy(i => rng.Next()).Take(Math.Min(upgrades, pairs.Count)).ToList();
            var up = new HashSet<int>(idx);
            foreach (var c in memeCards) res.cards.Add(c);
            for (int i = 0; i < pairs.Count; i++)
                res.cards.Add(up.Contains(i) ? ToCard(pairs[i].Key.upCard, true) : ToCard(pairs[i].Key.baseCard, false));
            if (!b.IsMeme)
            {
                var mods = b.Modules;
                res.ultText = UltText(mods);
                res.cards.Add(new Card { name = "终极", cost = 3, v = UltFx(mods), text = res.ultText, kind = "ult" });
            }
            return res;
        }

        private static Card ToCard(CardDef d, bool upgraded) { return Card.From(d, upgraded); }

        public static List<Card> BuildPlain(CardPool pool, BuildSpec b, out Passive passive)
        {
            var d = Build(pool, b, 0, 1);
            passive = d.passive;
            return d.cards;
        }
    }
}
