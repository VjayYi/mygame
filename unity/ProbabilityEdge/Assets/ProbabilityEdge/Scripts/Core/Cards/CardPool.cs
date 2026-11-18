using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace ProbabilityEdge.Core.Cards
{
    // 卡牌效果分量（由 Python 侧按文本解析 + 预算差额折算后导出）。
    public sealed class Fx
    {
        public double dmg, aoe, shield, shieldNext, heal, draw, energy, stun, nextatk, turnatk, dot, edown, costdown, selfdmg;
        public double hits = 1.0;

        public Fx Clone() { return (Fx)MemberwiseClone(); }

        // 与 gsim_core.comp_e 一致的预算价值（E）
        public double CompE()
        {
            double e = (dmg + aoe * 1.6 + dot * 1.5 + nextatk * 0.8 + turnatk * 2.0) / 6.0;
            e += (shield + shieldNext * 0.8) / 6.0;
            e += heal * 1.3 / 6.0 + draw * 0.4 + energy * 0.9;
            e += stun * 2.0 + edown / 6.0 + costdown * 0.7;
            return e;
        }

        public static Fx From(Dictionary<string, object> d)
        {
            var f = new Fx();
            f.dmg = MiniJson.N(d, "dmg");
            f.aoe = MiniJson.N(d, "aoe");
            f.shield = MiniJson.N(d, "shield");
            f.shieldNext = MiniJson.N(d, "shield_next");
            f.heal = MiniJson.N(d, "heal");
            f.draw = MiniJson.N(d, "draw");
            f.energy = MiniJson.N(d, "energy");
            f.stun = MiniJson.N(d, "stun");
            f.nextatk = MiniJson.N(d, "nextatk");
            f.turnatk = MiniJson.N(d, "turnatk");
            f.dot = MiniJson.N(d, "dot");
            f.edown = MiniJson.N(d, "edown");
            f.costdown = MiniJson.N(d, "costdown");
            f.selfdmg = MiniJson.N(d, "selfdmg");
            f.hits = d.ContainsKey("hits") ? MiniJson.N(d, "hits") : 1.0;
            return f;
        }

        public void AddUlt(Fx o)
        {
            dmg += o.dmg; aoe += o.aoe; shield += o.shield; shieldNext += o.shieldNext; heal += o.heal; draw += o.draw;
            energy += o.energy; stun += o.stun; nextatk += o.nextatk; turnatk += o.turnatk; dot += o.dot; edown += o.edown;
            costdown += o.costdown; selfdmg += o.selfdmg;
        }
    }

    public sealed class CardDef
    {
        public string name, text;
        public int cost;
        public bool exhaust;
        public Fx fx;
    }

    public sealed class CardPair
    {
        public CardDef baseCard, upCard;
    }

    public sealed class Passive
    {
        public double shield, draw, energy, turnatk;
        public static Passive From(Dictionary<string, object> d)
        {
            var p = new Passive();
            if (d == null) return p;
            p.shield = MiniJson.N(d, "shield");
            p.draw = MiniJson.N(d, "draw");
            p.energy = MiniJson.N(d, "energy");
            p.turnatk = MiniJson.N(d, "turnatk");
            return p;
        }
        public void Add(Passive o) { shield += o.shield; draw += o.draw; energy += o.energy; turnatk += o.turnatk; }
    }

    public sealed class ItemDef
    {
        public string kind, name, part;
        public List<CardPair> cards = new List<CardPair>();
        public Passive passive = new Passive();
        // 模块专用
        public int size;
        public string shape, major, limit, pool, type, ult, tier;
        public bool locked;
        public Fx ultFx;
        public int supplyA, supplyD;
        public string Summary()
        {
            var sb = new StringBuilder();
            foreach (var c in cards)
            {
                if (sb.Length > 0) sb.Append("；");
                sb.Append(c.baseCard.name).Append('[').Append(c.baseCard.cost).Append("费] ").Append(c.baseCard.text);
            }
            return sb.ToString();
        }
    }

    public sealed class WeaponDef
    {
        public string cat, form, major, passiveName, passiveText;
        public int volume;
        public string[] mask;
        public Passive passive = new Passive();
        public List<ItemDef> items = new List<ItemDef>();
        public string Key { get { return cat + "|" + form; } }
        public string Label { get { return cat + "·" + form; } }
    }

    public sealed class MemeDef
    {
        public string name;
        public List<CardDef> cards = new List<CardDef>();
    }

    public sealed class CardPool
    {
        public Dictionary<string, int[][]> shapes = new Dictionary<string, int[][]>();
        public Dictionary<string, WeaponDef> weapons = new Dictionary<string, WeaponDef>();
        public List<ItemDef> modules = new List<ItemDef>();
        public List<ItemDef> hands = new List<ItemDef>(), feet = new List<ItemDef>(), brains = new List<ItemDef>(), torsos = new List<ItemDef>();
        public Dictionary<string, List<ItemDef>> armor = new Dictionary<string, List<ItemDef>>();
        public List<ItemDef> generic = new List<ItemDef>();
        public List<MemeDef> memes = new List<MemeDef>();
        public static readonly string[] Cats = { "刀", "剑", "爪", "斧", "拳套", "步枪", "炮筒", "手枪", "弓" };
        public static readonly string[] Forms = { "改装", "均衡", "强攻" };
        public static readonly string[] ArmorParts = { "头", "躯干", "四肢" };

        public static CardPool LoadFile(string path) { return Parse(File.ReadAllText(path, Encoding.UTF8)); }

        public static CardPool Parse(string json)
        {
            var root = MiniJson.Obj(MiniJson.Parse(json));
            var p = new CardPool();
            foreach (var kv in MiniJson.Obj(root["shapes"]))
            {
                var arr = MiniJson.Arr(kv.Value);
                var cells = new int[arr.Count][];
                for (int i = 0; i < arr.Count; i++)
                {
                    var rc = MiniJson.Arr(arr[i]);
                    cells[i] = new[] { (int)(double)rc[0], (int)(double)rc[1] };
                }
                p.shapes[kv.Key] = cells;
            }
            foreach (var kv in MiniJson.Obj(root["weapons"]))
            {
                var d = MiniJson.Obj(kv.Value);
                var w = new WeaponDef
                {
                    cat = MiniJson.S(d, "cat"), form = MiniJson.S(d, "form"), major = MiniJson.S(d, "major"),
                    volume = (int)MiniJson.N(d, "volume"), passiveName = MiniJson.S(d, "passiveName"), passiveText = MiniJson.S(d, "passiveText"),
                    passive = Passive.From(MiniJson.Obj(d["passive"]))
                };
                var mk = MiniJson.Arr(d["mask"]);
                w.mask = new string[mk.Count];
                for (int i = 0; i < mk.Count; i++) w.mask[i] = (string)mk[i];
                foreach (var o in MiniJson.Arr(d["items"])) w.items.Add(Item(MiniJson.Obj(o)));
                p.weapons[kv.Key] = w;
            }
            foreach (var o in MiniJson.Arr(root["modules"])) p.modules.Add(Item(MiniJson.Obj(o)));
            foreach (var o in MiniJson.Arr(root["hands"])) p.hands.Add(Item(MiniJson.Obj(o)));
            foreach (var o in MiniJson.Arr(root["feet"])) p.feet.Add(Item(MiniJson.Obj(o)));
            foreach (var o in MiniJson.Arr(root["brains"])) p.brains.Add(Item(MiniJson.Obj(o)));
            foreach (var o in MiniJson.Arr(root["torsos"])) p.torsos.Add(Item(MiniJson.Obj(o)));
            foreach (var o in MiniJson.Arr(root["generic"])) p.generic.Add(Item(MiniJson.Obj(o)));
            foreach (var kv in MiniJson.Obj(root["armor"]))
            {
                var l = new List<ItemDef>();
                foreach (var o in MiniJson.Arr(kv.Value)) l.Add(Item(MiniJson.Obj(o)));
                p.armor[kv.Key] = l;
            }
            foreach (var o in MiniJson.Arr(root["memes"]))
            {
                var d = MiniJson.Obj(o);
                var m = new MemeDef { name = MiniJson.S(d, "name") };
                foreach (var c in MiniJson.Arr(d["cards"]))
                {
                    var cd = MiniJson.Obj(c);
                    m.cards.Add(new CardDef { name = MiniJson.S(cd, "name"), cost = (int)MiniJson.N(cd, "cost"), text = MiniJson.S(cd, "text") });
                }
                p.memes.Add(m);
            }
            return p;
        }

        private static CardDef Card(Dictionary<string, object> d)
        {
            return new CardDef
            {
                name = MiniJson.S(d, "name"), text = MiniJson.S(d, "text"), cost = (int)MiniJson.N(d, "cost"),
                exhaust = MiniJson.B(d, "exhaust"), fx = Fx.From(MiniJson.Obj(d["fx"]))
            };
        }

        private static ItemDef Item(Dictionary<string, object> d)
        {
            var it = new ItemDef
            {
                kind = MiniJson.S(d, "kind"), name = MiniJson.S(d, "name"), part = MiniJson.S(d, "part"),
                size = (int)MiniJson.N(d, "size"), shape = MiniJson.S(d, "shape"), major = MiniJson.S(d, "major"),
                limit = MiniJson.S(d, "limit"), pool = MiniJson.S(d, "pool"), type = MiniJson.S(d, "type"),
                ult = MiniJson.S(d, "ult"), tier = MiniJson.S(d, "tier"), locked = MiniJson.B(d, "locked"),
                supplyA = (int)MiniJson.N(d, "supplyA"), supplyD = (int)MiniJson.N(d, "supplyD")
            };
            object p;
            if (d.TryGetValue("passive", out p) && p != null) it.passive = Passive.From(MiniJson.Obj(p));
            if (d.TryGetValue("ultFx", out p) && p != null) it.ultFx = Fx.From(MiniJson.Obj(p));
            foreach (var c in MiniJson.Arr(d["cards"]))
            {
                var cd = MiniJson.Obj(c);
                it.cards.Add(new CardPair { baseCard = Card(MiniJson.Obj(cd["base"])), upCard = Card(MiniJson.Obj(cd["up"])) });
            }
            return it;
        }

        public ItemDef FindModule(string name)
        {
            foreach (var m in modules) if (m.name == name) return m;
            return null;
        }

        public ItemDef Find(List<ItemDef> list, string name)
        {
            foreach (var m in list) if (m.name == name) return m;
            return null;
        }

        public List<ItemDef> ModulesFor(string cat)
        {
            string major = Array.IndexOf(Cats, cat) <= 4 ? "近战" : "远程";
            var r = new List<ItemDef>();
            foreach (var m in modules) if (m.major == major && (m.limit == "—" || m.limit == cat)) r.Add(m);
            return r;
        }
    }
}
