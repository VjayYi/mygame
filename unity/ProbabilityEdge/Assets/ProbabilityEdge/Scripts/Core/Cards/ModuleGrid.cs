using System;
using System.Collections.Generic;
using System.Text;

namespace ProbabilityEdge.Core.Cards
{
    // 武器容积拼图：模块可旋转（4 向）与镜像，放进武器轮廓里，不能重叠、不能越界、不能压在缺口上。
    public sealed class Placement
    {
        public ItemDef module;
        public int rot;        // 0..3，顺时针 90 度
        public bool mirror;    // 先镜像（左右翻转），再旋转
        public int row, col;   // 变换后形状左上角在棋盘上的位置
        public List<int[]> cells = new List<int[]>();
    }

    public sealed class ModuleGrid
    {
        public readonly WeaponDef weapon;
        public readonly bool[,] open;
        public readonly int rows, cols;
        private readonly Dictionary<string, int[][]> shapes;
        public readonly List<Placement> placed = new List<Placement>();

        public ModuleGrid(WeaponDef w, Dictionary<string, int[][]> shapes)
        {
            weapon = w;
            this.shapes = shapes;
            rows = w.mask.Length;
            cols = w.mask[0].Length;
            open = new bool[rows, cols];
            for (int r = 0; r < rows; r++)
                for (int c = 0; c < cols; c++) open[r, c] = w.mask[r][c] == '#';
        }

        public int Used { get { int n = 0; foreach (var p in placed) n += p.module.size; return n; } }
        public int Free { get { return weapon.volume - Used; } }

        public int[,] Occupancy()
        {
            var g = new int[rows, cols];
            for (int r = 0; r < rows; r++) for (int c = 0; c < cols; c++) g[r, c] = -1;
            for (int i = 0; i < placed.Count; i++)
                foreach (var rc in placed[i].cells) g[rc[0], rc[1]] = i;
            return g;
        }

        public static List<int[]> Transform(int[][] cells, int rot, bool mirror)
        {
            var cur = new List<int[]>();
            foreach (var c in cells) cur.Add(new[] { c[0], mirror ? -c[1] : c[1] });
            for (int k = 0; k < rot; k++)
            {
                var next = new List<int[]>();
                foreach (var c in cur) next.Add(new[] { c[1], -c[0] });
                cur = next;
            }
            int mr = int.MaxValue, mc = int.MaxValue;
            foreach (var c in cur) { mr = Math.Min(mr, c[0]); mc = Math.Min(mc, c[1]); }
            var res = new List<int[]>();
            foreach (var c in cur) res.Add(new[] { c[0] - mr, c[1] - mc });
            return res;
        }

        // 同一形状的不同朝向（去重）
        public static List<KeyValuePair<int, bool>> Orientations(int[][] cells)
        {
            var seen = new HashSet<string>();
            var res = new List<KeyValuePair<int, bool>>();
            foreach (bool m in new[] { false, true })
                for (int r = 0; r < 4; r++)
                {
                    var t = Transform(cells, r, m);
                    t.Sort((a, b) => a[0] != b[0] ? a[0].CompareTo(b[0]) : a[1].CompareTo(b[1]));
                    var sb = new StringBuilder();
                    foreach (var c in t) sb.Append(c[0]).Append(',').Append(c[1]).Append(';');
                    if (seen.Add(sb.ToString())) res.Add(new KeyValuePair<int, bool>(r, m));
                }
            return res;
        }

        public bool CanPlace(ItemDef m, int rot, bool mirror, int row, int col, out List<int[]> cells, out string why)
        {
            cells = new List<int[]>();
            why = "";
            foreach (var p in placed)
                if (p.module == m) { why = "该模块已装配"; return false; }
            var occ = Occupancy();
            foreach (var c in Transform(shapes[m.shape], rot, mirror))
            {
                int r = row + c[0], cc = col + c[1];
                if (r < 0 || cc < 0 || r >= rows || cc >= cols) { why = "超出武器范围"; return false; }
                if (!open[r, cc]) { why = "压在武器缺口上"; return false; }
                if (occ[r, cc] >= 0) { why = "与「" + placed[occ[r, cc]].module.name + "」重叠"; return false; }
                cells.Add(new[] { r, cc });
            }
            return true;
        }

        public bool Place(ItemDef m, int rot, bool mirror, int row, int col, out string why)
        {
            List<int[]> cells;
            if (!CanPlace(m, rot, mirror, row, col, out cells, out why)) return false;
            placed.Add(new Placement { module = m, rot = rot, mirror = mirror, row = row, col = col, cells = cells });
            return true;
        }

        public bool Remove(ItemDef m)
        {
            for (int i = 0; i < placed.Count; i++)
                if (placed[i].module == m) { placed.RemoveAt(i); return true; }
            return false;
        }

        public void Clear() { placed.Clear(); }

        // 自动找一个位置放入（先试当前朝向，再试所有朝向；扫描顺序固定，结果可复现）。
        public bool AutoPlace(ItemDef m, out string why)
        {
            why = "";
            if (Free < m.size) { why = "容积不足（剩 " + Free + " 格，需要 " + m.size + " 格）"; return false; }
            foreach (var o in Orientations(shapes[m.shape]))
                for (int r = 0; r < rows; r++)
                    for (int c = 0; c < cols; c++)
                    {
                        List<int[]> cells; string w;
                        if (CanPlace(m, o.Key, o.Value, r, c, out cells, out w))
                        {
                            placed.Add(new Placement { module = m, rot = o.Key, mirror = o.Value, row = r, col = c, cells = cells });
                            return true;
                        }
                    }
            why = "拼不进去：形状放不下（容积够，但剩余格子不连成该形状）";
            return false;
        }

        // 回溯重排：把给定的整组模块一起尽量放进武器（大块优先）。成功则替换当前摆放。
        public bool Repack(List<ItemDef> mods, int budget = 200000)
        {
            var order = new List<ItemDef>(mods);
            order.Sort((a, b) => b.size != a.size ? b.size.CompareTo(a.size) : string.CompareOrdinal(a.name, b.name));
            int total = 0;
            foreach (var m in order) total += m.size;
            if (total > weapon.volume) return false;
            var saved = new List<Placement>(placed);
            placed.Clear();
            int steps = 0;
            if (Solve(order, 0, ref steps, budget)) return true;
            placed.Clear();
            placed.AddRange(saved);
            return false;
        }

        private bool Solve(List<ItemDef> order, int idx, ref int steps, int budget)
        {
            if (idx == order.Count) return true;
            var m = order[idx];
            foreach (var o in Orientations(shapes[m.shape]))
            {
                for (int r = 0; r < rows; r++)
                    for (int c = 0; c < cols; c++)
                    {
                        if (++steps > budget) return false;
                        List<int[]> cells; string w;
                        if (!CanPlace(m, o.Key, o.Value, r, c, out cells, out w)) continue;
                        placed.Add(new Placement { module = m, rot = o.Key, mirror = o.Value, row = r, col = c, cells = cells });
                        if (Solve(order, idx + 1, ref steps, budget)) return true;
                        placed.RemoveAt(placed.Count - 1);
                    }
            }
            return false;
        }

        // 渲染：返回每行的字符数组；模块用 A、B、C… 标记，空格用 · ，缺口用 空白。
        public string[] Render(int highlight = -1)
        {
            var occ = Occupancy();
            var lines = new string[rows];
            for (int r = 0; r < rows; r++)
            {
                var sb = new StringBuilder();
                for (int c = 0; c < cols; c++)
                {
                    if (!open[r, c]) sb.Append("　");
                    else if (occ[r, c] < 0) sb.Append("□");
                    else sb.Append(Letter(occ[r, c]));
                }
                lines[r] = sb.ToString();
            }
            return lines;
        }

        public static string Letter(int i)
        {
            const string full = "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰ";
            return i >= 0 && i < full.Length ? full[i].ToString() : "？";
        }
    }
}
