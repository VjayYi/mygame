using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using ProbabilityEdge.Core.Cards;
using UnityEngine;

namespace ProbabilityEdge.Runtime
{
    // 卡牌战斗文字测试版（IMGUI）。所有模块/义体/防具全部开放；武器模块用拼图格子展示，支持旋转、镜像、自动放入与重排。
    public sealed class CardBattleRunner : MonoBehaviour
    {
        private enum Page { Build, Battle, Result }
        private enum Tab { Weapon, Implant, Armor, Start }

        private CardPool pool;
        private BuildSpec spec;
        private string loadError = "";
        private Page screen = Page.Build;
        private Tab tab = Tab.Weapon;
        private bool memeMode;

        // 样式
        private Font font;
        private bool ownsFont;
        private Texture2D white, bgTex;
        private GUIStyle title, heading, body, small, button, buttonSel, input, cellLabel, box;
        private float scale = 1f;

        // 拼图
        private ItemDef armed;
        private int rot;
        private bool mirror;
        private string gridMsg = "先在右侧点选一个模块，再点左侧格子放置；点已放置的格子可移除。快捷键：R 旋转，M 镜像。";
        private string modFilter = "";
        private int modSize;
        private Vector2 modScroll, placedScroll;
        private static readonly Color[] Palette =
        {
            new Color(0.95f,0.60f,0.55f), new Color(0.55f,0.78f,0.95f), new Color(0.65f,0.88f,0.60f), new Color(0.98f,0.82f,0.45f),
            new Color(0.80f,0.65f,0.92f), new Color(0.55f,0.88f,0.82f), new Color(0.96f,0.70f,0.82f), new Color(0.78f,0.80f,0.55f),
            new Color(0.70f,0.72f,0.95f), new Color(0.95f,0.75f,0.55f), new Color(0.60f,0.85f,0.70f), new Color(0.90f,0.60f,0.75f),
            new Color(0.62f,0.80f,0.90f), new Color(0.88f,0.88f,0.55f), new Color(0.75f,0.68f,0.88f), new Color(0.85f,0.70f,0.62f)
        };

        // 义体/防具选择
        private int slotIndex;
        private string pickFilter = "";
        private Vector2 pickScroll;

        // 开战设置
        private int layer = 3;
        private int upgrades = 7;
        private string seedText = "2026";
        private string hpText = "";
        private string enemyKind = "elite";
        private Vector2 deckScroll;

        // 战斗
        private Fight fight;
        private int battleSeed;
        private double battleHp;
        private readonly List<string> log = new List<string>();
        private Vector2 logScroll, handScroll;
        private int targetIdx = -1;
        private bool autoAll;
        private bool? result;
        private int turnCount;
        private string resultText = "";
        private string logPath = "";

        private void Awake()
        {
            var ta = Resources.Load<TextAsset>("CardData/cardpool");
            if (ta == null) { loadError = "找不到 Resources/CardData/cardpool.json"; return; }
            try
            {
                pool = CardPool.Parse(ta.text);
                spec = BuildSpec.Create(pool, "剑", "均衡", 20261118);
                string w;
                foreach (var m in pool.ModulesFor("剑").Where(x => x.size >= 3).Take(3)) spec.grid.AutoPlace(m, out w);
            }
            catch (Exception e) { loadError = "卡池读取失败：" + e.Message; }
        }

        private void OnDestroy() { if (ownsFont && font != null) Destroy(font); }

        // ------------------------------------------------------------------ 样式
        private Texture2D Solid(Color c)
        {
            var t = new Texture2D(1, 1, TextureFormat.RGBA32, false) { hideFlags = HideFlags.HideAndDontSave };
            t.SetPixel(0, 0, c);
            t.Apply();
            return t;
        }

        private void InitStyles()
        {
            if (title != null) return;
            string[] installed = Font.GetOSInstalledFontNames();
            string selected = null;
            foreach (string n in new[] { "PingFang SC", "Microsoft YaHei", "Microsoft YaHei UI", "Noto Sans CJK SC", "Arial Unicode MS", "Heiti SC", "SimSun" })
                if (Array.IndexOf(installed, n) >= 0) { selected = n; break; }
            ownsFont = selected != null;
            font = ownsFont ? Font.CreateDynamicFontFromOSFont(selected, 24) : Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            white = Solid(Color.white);
            bgTex = Solid(new Color(0.97f, 0.98f, 0.99f));
            Func<int, Color, bool, GUIStyle> label = (size, col, wrap) =>
            {
                var s = new GUIStyle(GUI.skin.label) { font = font, fontSize = size, wordWrap = wrap, richText = false };
                s.normal.textColor = col;
                return s;
            };
            title = label(26, new Color(0.08f, 0.17f, 0.28f), false);
            heading = label(19, new Color(0.10f, 0.22f, 0.34f), true);
            body = label(16, new Color(0.16f, 0.22f, 0.29f), true);
            small = label(13, new Color(0.35f, 0.42f, 0.49f), true);
            button = new GUIStyle(GUI.skin.button) { font = font, fontSize = 15, wordWrap = true, alignment = TextAnchor.MiddleLeft };
            button.normal.background = Solid(new Color(0.87f, 0.92f, 0.97f));
            button.hover.background = Solid(new Color(0.80f, 0.88f, 0.96f));
            button.active.background = Solid(new Color(0.70f, 0.82f, 0.94f));
            button.normal.textColor = button.hover.textColor = button.active.textColor = new Color(0.08f, 0.19f, 0.31f);
            button.padding = new RectOffset(10, 10, 5, 5);
            buttonSel = new GUIStyle(button);
            buttonSel.normal.background = Solid(new Color(0.99f, 0.86f, 0.45f));
            buttonSel.hover.background = Solid(new Color(1f, 0.90f, 0.55f));
            input = new GUIStyle(GUI.skin.textField) { font = font, fontSize = 15 };
            cellLabel = new GUIStyle(GUI.skin.label) { font = font, fontSize = 18, alignment = TextAnchor.MiddleCenter, fontStyle = FontStyle.Bold };
            cellLabel.normal.textColor = new Color(0.12f, 0.16f, 0.22f);
            box = new GUIStyle(GUI.skin.box);
            box.normal.background = Solid(new Color(0.94f, 0.96f, 0.98f));
        }

        private bool Btn(string text, params GUILayoutOption[] opt) { return GUILayout.Button(text, button, opt); }
        private bool BtnSel(string text, bool selected, params GUILayoutOption[] opt) { return GUILayout.Button(text, selected ? buttonSel : button, opt); }

        // ------------------------------------------------------------------ OnGUI
        private void OnGUI()
        {
            InitStyles();
            scale = Mathf.Clamp(Mathf.Min(Screen.width / 1280f, Screen.height / 800f), 0.6f, 2.5f);
            GUI.matrix = Matrix4x4.Scale(new Vector3(scale, scale, 1f));
            float W = Screen.width / scale, H = Screen.height / scale;
            GUI.DrawTexture(new Rect(0, 0, W, H), bgTex);
            GUILayout.BeginArea(new Rect(14, 10, W - 28, H - 20));
            if (!string.IsNullOrEmpty(loadError)) GUILayout.Label(loadError, title);
            else if (screen == Page.Build) BuildScreen(W - 28, H - 20);
            else if (screen == Page.Battle) BattleScreen(W - 28, H - 20);
            else ResultScreen(W - 28, H - 20);
            GUILayout.EndArea();
        }

        // ------------------------------------------------------------------ 构筑页
        private void BuildScreen(float w, float h)
        {
            GUILayout.BeginHorizontal();
            GUILayout.Label("概率边缘 · 卡牌战斗测试版（全部内容开放）", title);
            GUILayout.FlexibleSpace();
            foreach (var t in new[] { Tab.Weapon, Tab.Implant, Tab.Armor, Tab.Start })
            {
                string n = t == Tab.Weapon ? "① 武器与模块拼装" : t == Tab.Implant ? "② 义体" : t == Tab.Armor ? "③ 防具" : "④ 开战";
                if (BtnSel(n, tab == t, GUILayout.Width(190), GUILayout.Height(40))) tab = t;
            }
            GUILayout.EndHorizontal();
            GUILayout.Space(6);
            switch (tab)
            {
                case Tab.Weapon: WeaponTab(w, h - 70); break;
                case Tab.Implant: ImplantTab(w, h - 70); break;
                case Tab.Armor: ArmorTab(w, h - 70); break;
                default: StartTab(w, h - 70); break;
            }
        }

        private void WeaponTab(float w, float h)
        {
            GUILayout.BeginHorizontal();
            if (BtnSel("普通武器 + 模块拼图", !memeMode, GUILayout.Width(220), GUILayout.Height(36))) { memeMode = false; spec.meme = null; if (spec.grid == null) spec.SetWeapon(pool, spec.cat, spec.form); }
            if (BtnSel("梗武器（6 把，无模块）", memeMode, GUILayout.Width(240), GUILayout.Height(36))) { memeMode = true; spec.meme = spec.meme ?? MemeCards.Names[0]; spec.meme = MemeCards.Names.Contains(spec.meme) ? spec.meme : MemeCards.Names[0]; }
            GUILayout.EndHorizontal();
            if (memeMode) { MemePanel(); return; }
            GUILayout.BeginHorizontal();
            foreach (var c in CardPool.Cats)
                if (BtnSel(c, spec.cat == c, GUILayout.Width(70), GUILayout.Height(32))) { spec.SetWeapon(pool, c, spec.form); armed = null; gridMsg = "已切换武器，原模块能拼回的已保留。"; }
            GUILayout.Space(20);
            foreach (var f in CardPool.Forms)
                if (BtnSel(f + "（" + pool.weapons[spec.cat + "|" + f].volume + "格）", spec.form == f, GUILayout.Width(120), GUILayout.Height(32))) { spec.SetWeapon(pool, spec.cat, f); armed = null; gridMsg = "已切换形态，原模块能拼回的已保留。"; }
            GUILayout.EndHorizontal();
            GUILayout.Space(4);
            GUILayout.BeginHorizontal();
            GUILayout.BeginVertical(GUILayout.Width(500));
            GridPanel();
            GUILayout.EndVertical();
            GUILayout.Space(10);
            GUILayout.BeginVertical();
            ModulePicker(h - 90);
            GUILayout.EndVertical();
            GUILayout.EndHorizontal();
        }

        private void MemePanel()
        {
            GUILayout.Space(6);
            GUILayout.BeginHorizontal();
            foreach (var n in MemeCards.Names)
                if (BtnSel(n, spec.meme == n, GUILayout.Width(170), GUILayout.Height(36))) spec.meme = n;
            GUILayout.EndHorizontal();
            var m = pool.memes.First(x => x.name == spec.meme);
            GUILayout.Space(6);
            GUILayout.Label(m.name + "：5 张专属牌（每把武器自带一个新机制）", heading);
            foreach (var c in m.cards) GUILayout.Label("· [" + c.cost + "费] " + c.name + "：" + c.text, body);
            GUILayout.Label("梗武器没有模块槽，也没有终极卡；义体与防具在其它标签页里选。", small);
        }

        private void GridPanel()
        {
            var w = pool.weapons[spec.cat + "|" + spec.form];
            var g = spec.grid;
            GUILayout.Label(w.Label + "   容积 " + w.volume + " 格   已用 " + g.Used + "   剩余 " + g.Free, heading);
            if (!string.IsNullOrEmpty(w.passiveName)) GUILayout.Label("均衡被动「" + w.passiveName + "」：" + w.passiveText, small);
            const float cell = 46f;
            Rect area = GUILayoutUtility.GetRect(g.cols * cell + 4, g.rows * cell + 4);
            var occ = g.Occupancy();
            var ev = Event.current;
            // 悬停格 → 预览放置
            int hr = -1, hc = -1;
            for (int r = 0; r < g.rows; r++)
                for (int c = 0; c < g.cols; c++)
                    if (new Rect(area.x + c * cell, area.y + r * cell, cell, cell).Contains(ev.mousePosition)) { hr = r; hc = c; }
            List<int[]> ghost = null; bool ghostOk = false; string ghostWhy = "";
            if (armed != null && hr >= 0 && g.open[hr, hc])
            {
                var shape = ModuleGrid.Transform(pool.shapes[armed.shape], rot, mirror);
                shape.Sort((a, b) => a[0] != b[0] ? a[0].CompareTo(b[0]) : a[1].CompareTo(b[1]));
                int ar = hr - shape[0][0], ac = hc - shape[0][1];
                ghostOk = g.CanPlace(armed, rot, mirror, ar, ac, out ghost, out ghostWhy);
                if (!ghostOk)
                {
                    ghost = new List<int[]>();
                    foreach (var s in shape) ghost.Add(new[] { ar + s[0], ac + s[1] });
                }
                if (ev.type == EventType.MouseDown && ev.button == 0 && area.Contains(ev.mousePosition))
                {
                    if (ghostOk) { string wy; g.Place(armed, rot, mirror, ar, ac, out wy); gridMsg = "已放入「" + armed.name + "」。"; armed = null; }
                    else gridMsg = "不能放：" + ghostWhy;
                    ev.Use();
                }
            }
            else if (ev.type == EventType.MouseDown && ev.button == 0 && hr >= 0 && occ[hr, hc] >= 0)
            {
                string n = g.placed[occ[hr, hc]].module.name;
                g.Remove(g.placed[occ[hr, hc]].module);
                gridMsg = "已移除「" + n + "」。";
                ev.Use();
            }
            for (int r = 0; r < g.rows; r++)
                for (int c = 0; c < g.cols; c++)
                {
                    var rc = new Rect(area.x + c * cell + 1, area.y + r * cell + 1, cell - 2, cell - 2);
                    if (!g.open[r, c]) continue;
                    Color col = new Color(0.86f, 0.89f, 0.93f);
                    string letter = "";
                    if (occ[r, c] >= 0) { col = Palette[occ[r, c] % Palette.Length]; letter = ((char)('A' + occ[r, c])).ToString(); }
                    if (ghost != null && ghost.Any(p => p[0] == r && p[1] == c)) col = ghostOk ? new Color(0.55f, 0.92f, 0.55f) : new Color(0.95f, 0.45f, 0.45f);
                    if (ev.type == EventType.Repaint)
                    {
                        var old = GUI.color; GUI.color = col; GUI.DrawTexture(rc, white); GUI.color = old;
                    }
                    if (letter != "") GUI.Label(rc, letter, cellLabel);
                }
            if (ev.type == EventType.KeyDown && ev.keyCode == KeyCode.R) { rot = (rot + 1) % 4; ev.Use(); }
            if (ev.type == EventType.KeyDown && ev.keyCode == KeyCode.M) { mirror = !mirror; ev.Use(); }
            GUILayout.BeginHorizontal();
            if (Btn("旋转 ↻（R）", GUILayout.Height(34))) rot = (rot + 1) % 4;
            if (Btn("镜像 ⇋（M）", GUILayout.Height(34))) mirror = !mirror;
            if (Btn("自动放入选中", GUILayout.Height(34)) && armed != null) { string wy; gridMsg = g.AutoPlace(armed, out wy) ? "已自动放入「" + armed.name + "」。" : wy; if (wy == "") armed = null; }
            GUILayout.EndHorizontal();
            GUILayout.BeginHorizontal();
            if (Btn("重新排布已装模块", GUILayout.Height(34))) gridMsg = g.Repack(spec.Modules) ? "重排成功（大块优先回溯）。" : "无法重排，保持原状。";
            if (Btn("清空", GUILayout.Height(34))) { g.Clear(); gridMsg = "已清空。"; }
            if (Btn("随机装满", GUILayout.Height(34))) { spec.Randomize(pool, (int)(Time.realtimeSinceStartup * 1000), true); gridMsg = "已随机装满（义体/防具也一并重抽）。"; }
            GUILayout.EndHorizontal();
            GUILayout.Label(gridMsg, small);
            GUILayout.Label("当前朝向：旋转 " + (rot * 90) + "°" + (mirror ? " + 镜像" : ""), small);
            GUILayout.Label("已装模块（" + g.placed.Count + "）：", heading);
            placedScroll = GUILayout.BeginScrollView(placedScroll, GUILayout.Height(150));
            for (int i = 0; i < g.placed.Count; i++)
            {
                var m = g.placed[i].module;
                GUILayout.BeginHorizontal();
                var old = GUI.color; GUI.color = Palette[i % Palette.Length];
                GUILayout.Label(((char)('A' + i)).ToString(), cellLabel, GUILayout.Width(26)); GUI.color = old;
                GUILayout.Label(m.name + "（" + m.size + "格" + m.shape + "，" + m.cards[0].baseCard.cost + "费）", body);
                if (Btn("移除", GUILayout.Width(60))) { g.Remove(m); gridMsg = "已移除「" + m.name + "」。"; break; }
                GUILayout.EndHorizontal();
            }
            GUILayout.EndScrollView();
        }

        private void ModulePicker(float h)
        {
            GUILayout.BeginHorizontal();
            GUILayout.Label("模块（全部开放）", heading, GUILayout.Width(150));
            modFilter = GUILayout.TextField(modFilter, input, GUILayout.Width(180));
            foreach (int s in new[] { 0, 2, 3, 4, 5, 6 })
                if (BtnSel(s == 0 ? "全部" : s + "格", modSize == s, GUILayout.Width(54))) modSize = s;
            GUILayout.EndHorizontal();
            var all = pool.ModulesFor(spec.cat).Where(m => (modSize == 0 || m.size == modSize) && (modFilter == "" || m.name.Contains(modFilter) || m.type.Contains(modFilter))).ToList();
            GUILayout.Label("共 " + all.Count + " 个候选（点选后在左侧放置）", small);
            modScroll = GUILayout.BeginScrollView(modScroll, GUILayout.Height(h - 250));
            foreach (var m in all)
            {
                bool placed = spec.grid.placed.Any(p => p.module == m);
                string txt = (placed ? "✔ " : "") + m.name + "  " + m.size + "格·" + m.shape + "  [" + m.cards[0].baseCard.cost + "费] " + m.type;
                if (BtnSel(txt, armed == m, GUILayout.Height(30))) { armed = armed == m ? null : m; rot = 0; mirror = false; gridMsg = armed == null ? "已取消选中。" : "已选中「" + m.name + "」，在左侧点格子放置。"; }
            }
            GUILayout.EndScrollView();
            if (armed != null) ItemDetail(armed, true);
            else GUILayout.Label("（选中一个模块可查看详情与形状）", small);
        }

        private void ItemDetail(ItemDef it, bool showShape)
        {
            GUILayout.BeginVertical(box);
            GUILayout.Label(it.name + (it.kind == "module" ? "  " + it.size + "格·" + it.shape + "·" + it.type : "") + (string.IsNullOrEmpty(it.part) ? "" : "  [" + it.part + "]"), heading);
            foreach (var c in it.cards)
            {
                GUILayout.Label("[" + c.baseCard.cost + "费] " + c.baseCard.name + "：" + c.baseCard.text, body);
                if (c.upCard.text != c.baseCard.text || c.upCard.cost != c.baseCard.cost)
                    GUILayout.Label("  强化后：[" + c.upCard.cost + "费] " + c.upCard.text, small);
            }
            if (it.kind == "module") GUILayout.Label("终极叠加：" + it.ult + "    供能 攻" + it.supplyA + "/防" + it.supplyD + "·" + it.tier + (it.pool == "怪物产出" || it.pool == "怪物" ? "    （正式版：怪物产出）" : ""), small);
            if (it.passive != null && (it.passive.shield + it.passive.turnatk + it.passive.draw > 0)) GUILayout.Label("被动折算：每回合 护盾 " + it.passive.shield.ToString("F1") + "，攻击 +" + it.passive.turnatk.ToString("F1"), small);
            if (showShape && it.kind == "module")
            {
                var cells = ModuleGrid.Transform(pool.shapes[it.shape], rot, mirror);
                int hh = cells.Max(c => c[0]) + 1, ww = cells.Max(c => c[1]) + 1;
                var sb = new StringBuilder();
                for (int r = 0; r < hh; r++) { for (int c = 0; c < ww; c++) sb.Append(cells.Any(p => p[0] == r && p[1] == c) ? "■" : "　"); sb.Append('\n'); }
                GUILayout.Label("当前朝向形状：\n" + sb.ToString().TrimEnd('\n'), body);
            }
            GUILayout.EndVertical();
        }

        // ------------------------------------------------------------------ 义体 / 防具
        private void SlotPicker(string[] names, Func<int, ItemDef> get, Action<int, ItemDef> set, Func<int, List<ItemDef>> options, float h)
        {
            GUILayout.BeginHorizontal();
            GUILayout.BeginVertical(GUILayout.Width(430));
            for (int i = 0; i < names.Length; i++)
            {
                var it = get(i);
                if (BtnSel(names[i] + "：" + (it != null ? it.name : "（空）") + (it != null && it.cards.Count > 0 ? "\n" + it.Summary() : ""), slotIndex == i, GUILayout.MinHeight(54))) slotIndex = i;
            }
            GUILayout.EndVertical();
            GUILayout.Space(10);
            GUILayout.BeginVertical();
            slotIndex = Mathf.Clamp(slotIndex, 0, names.Length - 1);
            GUILayout.BeginHorizontal();
            GUILayout.Label("为「" + names[slotIndex] + "」选择（全部开放）", heading, GUILayout.Width(300));
            pickFilter = GUILayout.TextField(pickFilter, input, GUILayout.Width(200));
            if (Btn("随机", GUILayout.Width(70))) { var l = options(slotIndex); set(slotIndex, l[UnityEngine.Random.Range(0, l.Count)]); }
            GUILayout.EndHorizontal();
            var opts = options(slotIndex).Where(x => pickFilter == "" || x.name.Contains(pickFilter) || x.Summary().Contains(pickFilter)).ToList();
            GUILayout.Label("候选 " + opts.Count + " 个", small);
            pickScroll = GUILayout.BeginScrollView(pickScroll, GUILayout.Height(h - 120));
            foreach (var x in opts)
            {
                var cur = get(slotIndex);
                string txt = x.name + "  " + (x.cards.Count > 0 ? "[" + x.cards[0].baseCard.cost + "费] " : "") + x.Summary();
                if (BtnSel(txt, cur == x, GUILayout.MinHeight(34))) set(slotIndex, x);
            }
            GUILayout.EndScrollView();
            GUILayout.EndVertical();
            GUILayout.EndHorizontal();
        }

        private void ImplantTab(float w, float h)
        {
            var names = new[] { "手 1", "手 2", "脚 1", "脚 2", "大脑", "躯干" };
            SlotPicker(names,
                i => i == 0 ? spec.hands[0] : i == 1 ? spec.hands[1] : i == 2 ? spec.feet[0] : i == 3 ? spec.feet[1] : i == 4 ? spec.brain : spec.torso,
                (i, it) => { if (i < 2) spec.hands[i] = it; else if (i < 4) spec.feet[i - 2] = it; else if (i == 4) spec.brain = it; else spec.torso = it; },
                i => i < 2 ? pool.hands : i < 4 ? pool.feet : i == 4 ? pool.brains : pool.torsos, h);
        }

        private void ArmorTab(float w, float h)
        {
            SlotPicker(new[] { "头", "躯干", "四肢" }, i => spec.armor[i], (i, it) => spec.armor[i] = it, i => pool.armor[CardPool.ArmorParts[i]], h);
        }

        // ------------------------------------------------------------------ 开战设置
        private void StartTab(float w, float h)
        {
            int[] defUp = { 2, 4, 7 };
            GUILayout.BeginHorizontal();
            GUILayout.BeginVertical(GUILayout.Width(520));
            GUILayout.Label("开战设置", heading);
            GUILayout.BeginHorizontal();
            GUILayout.Label("构筑层数（决定推荐生命）", body, GUILayout.Width(200));
            for (int l = 1; l <= 3; l++) if (BtnSel("层 " + l, layer == l, GUILayout.Width(70))) { layer = l; upgrades = defUp[l - 1]; hpText = ""; }
            GUILayout.EndHorizontal();
            GUILayout.BeginHorizontal();
            GUILayout.Label("随机强化张数", body, GUILayout.Width(200));
            if (Btn("－", GUILayout.Width(40))) upgrades = Mathf.Max(0, upgrades - 1);
            GUILayout.Label(upgrades.ToString(), heading, GUILayout.Width(40));
            if (Btn("＋", GUILayout.Width(40))) upgrades++;
            GUILayout.EndHorizontal();
            GUILayout.BeginHorizontal();
            GUILayout.Label("随机种子", body, GUILayout.Width(200));
            seedText = GUILayout.TextField(seedText, input, GUILayout.Width(120));
            GUILayout.EndHorizontal();
            GUILayout.Label("选择敌人", body);
            foreach (var k in new[] { "mob", "elite", "mini", "final" })
            {
                var win = Encounters.Window[k];
                if (BtnSel(Encounters.Names[k] + "   推荐生命 " + Encounters.RecHp(k, layer) + "，每回合伤害均值 " + Encounters.Avg[k] + "，目标 " + win[0] + "~" + win[1] + " 回合", enemyKind == k, GUILayout.Height(38))) { enemyKind = k; hpText = ""; }
            }
            GUILayout.BeginHorizontal();
            GUILayout.Label("覆盖总生命（留空用推荐）", body, GUILayout.Width(250));
            hpText = GUILayout.TextField(hpText, input, GUILayout.Width(100));
            GUILayout.EndHorizontal();
            GUILayout.Space(8);
            string err = spec.IsMeme ? "" : (spec.grid.placed.Count == 0 ? "提示：还没有装任何模块，终极卡只有基础 6 伤害。" : "");
            if (err != "") GUILayout.Label(err, small);
            if (GUILayout.Button("开 战", button, GUILayout.Height(52))) StartBattle();
            GUILayout.EndVertical();
            GUILayout.Space(10);
            GUILayout.BeginVertical();
            GUILayout.Label("牌库预览", heading);
            var d = DeckBuilder.Build(pool, spec, 0, 1);
            GUILayout.Label("共 " + d.cards.Count + " 张" + (spec.IsMeme ? "" : "（含终极卡）") + "；被动折算：每回合护盾 " + d.passive.shield.ToString("F1") + "，攻击 +" + d.passive.turnatk.ToString("F1"), small);
            if (!spec.IsMeme) GUILayout.Label("终极卡（3 费）：" + d.ultText, small);
            deckScroll = GUILayout.BeginScrollView(deckScroll, GUILayout.Height(h - 90));
            foreach (var c in d.cards) GUILayout.Label("· [" + c.cost + "费] " + c.name + "：" + (c.text ?? ""), small);
            GUILayout.EndScrollView();
            GUILayout.EndVertical();
            GUILayout.EndHorizontal();
        }

        // ------------------------------------------------------------------ 战斗
        private void StartBattle()
        {
            int seed;
            if (!int.TryParse(seedText, out seed)) seed = 2026;
            battleSeed = seed;
            double hp;
            battleHp = double.TryParse(hpText, out hp) && hp > 0 ? hp : Encounters.RecHp(enemyKind, layer);
            var deck = DeckBuilder.Build(pool, spec, upgrades, seed);
            fight = new Fight(deck.cards, Encounters.Make(enemyKind, battleHp, Encounters.Avg[enemyKind]), seed, deck.passive);
            log.Clear();
            Say("▶ 开战：" + Encounters.Names[enemyKind] + "，总生命 " + battleHp.ToString("F0") + "，牌库 " + deck.cards.Count + " 张，强化 " + upgrades + " 张，种子 " + seed + "。");
            var win = Encounters.Window[enemyKind];
            Say("目标回合区间 " + win[0] + "~" + win[1] + "（参考，不是限制）。");
            targetIdx = -1; autoAll = false; result = null; turnCount = 0;
            screen = Page.Battle;
            NextTurn();
        }

        private void Say(string s) { log.Add(s); logScroll.y = float.MaxValue; }

        private void NextTurn()
        {
            turnCount++;
            if (turnCount > 80) { Finish(false); return; }
            fight.BeginTurn(turnCount);
            Say("\n━━ 第 " + turnCount + " 回合 ━━");
            if (autoAll)
            {
                foreach (var l in BattleText.AutoTurn(fight)) Say("  " + l);
                EndTurn();
            }
        }

        private void EndTurn()
        {
            bool? res;
            foreach (var l in BattleText.EnemyPhase(fight, out res)) Say("  " + l);
            if (res.HasValue) { Finish(res.Value); return; }
            NextTurn();
        }

        private void PlayCard(Card c)
        {
            int cost = fight.CostOf(c);
            var before = Snap.Take(fight);
            fight.pick = targetIdx >= 0 && targetIdx < fight.enemies.Count && fight.enemies[targetIdx].Alive ? fight.enemies[targetIdx] : null;
            fight.Play(c);
            fight.pick = null;
            Say("  打出 " + c.Label + "（-" + cost + " 能源）");
            foreach (var d in BattleText.Diff(fight, before, c, cost)) Say("   · " + d);
            if (fight.AliveEnemies().Count == 0) Finish(true);
            else if (fight.hp <= 0) Finish(false);
        }

        private void Finish(bool win)
        {
            result = win;
            var wd = Encounters.Window[enemyKind];
            var sb = new StringBuilder();
            sb.AppendLine((win ? "胜利" : "失败") + "：用了 " + Math.Min(turnCount, 80) + " 回合，累计损失 " + fight.hpLost.ToString("F0") + " 生命，剩余 " + Math.Max(fight.hp, 0).ToString("F0") + "/100。");
            if (win) sb.AppendLine("对照目标区间 " + wd[0] + "~" + wd[1] + " 回合：" + (turnCount < wd[0] ? "偏快" : turnCount > wd[1] ? "偏慢" : "区间内") + "。");
            var ts = new List<int>();
            for (int k = 0; k < 20; k++)
            {
                var d = DeckBuilder.Build(pool, spec, upgrades, battleSeed);
                var f2 = new Fight(d.cards, Encounters.Make(enemyKind, battleHp, Encounters.Avg[enemyKind]), 1000 + k, d.passive);
                var r = f2.Run();
                if (r.Value) ts.Add(r.Key);
            }
            sb.AppendLine(ts.Count > 0 ? "贪心 AI 打同一套牌（20 次）：平均 " + ts.Average().ToString("F1") + " 回合（" + ts.Min() + "~" + ts.Max() + "），胜率 " + (ts.Count / 20.0).ToString("P0") + "。" : "贪心 AI 打同一套牌：20 次全部失败。");
            resultText = sb.ToString();
            foreach (var l in resultText.Split('\n')) Say(l);
            SaveLog();
            screen = Page.Result;
        }

        private void SaveLog()
        {
            try
            {
                string dir = Path.Combine(Application.persistentDataPath, "CardBattleLogs");
                Directory.CreateDirectory(dir);
                logPath = Path.Combine(dir, "battle_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") + ".txt");
                var hdr = new StringBuilder();
                hdr.AppendLine(spec.IsMeme ? "梗武器：" + spec.meme : spec.cat + "·" + spec.form + "  模块：" + string.Join("、", spec.Modules.Select(m => m.name)));
                hdr.AppendLine("手：" + string.Join("、", spec.hands.Select(i => i.name)) + "；脚：" + string.Join("、", spec.feet.Select(i => i.name)) + "；脑：" + spec.brain.name + "；躯：" + spec.torso.name + "；防具：" + string.Join("、", spec.armor.Select(i => i.name)));
                File.WriteAllText(logPath, hdr + string.Join("\n", log), new UTF8Encoding(false));
            }
            catch (Exception e) { logPath = "日志保存失败：" + e.Message; }
        }

        private void BattleScreen(float w, float h)
        {
            var g = fight;
            GUILayout.BeginHorizontal();
            GUILayout.BeginVertical(GUILayout.Width(w * 0.62f));
            GUILayout.Label("第 " + g.turn + " 回合   " + Encounters.Names[enemyKind], title);
            GUILayout.Label("生命 " + g.hp.ToString("F0") + "/100    护盾 " + g.shield.ToString("F0") + "    能源 " + g.energy + "    牌库 " + g.drawPile.Count + "  弃牌 " + g.discard.Count + "  消耗 " + g.exhausted.Count, heading);
            var st = BattleText.Status(g);
            if (st.Count > 0) GUILayout.Label("状态：" + string.Join("；", st), small);
            GUILayout.Label("敌人（点击选目标，再次点击取消 = 自动选生命最低）：", small);
            for (int i = 0; i < g.enemies.Count; i++)
            {
                if (!g.enemies[i].Alive) { GUILayout.Label(BattleText.EnemyLine(g, i), small); continue; }
                if (BtnSel((targetIdx == i ? "◎ " : "") + BattleText.EnemyLine(g, i), targetIdx == i, GUILayout.MinHeight(36))) targetIdx = targetIdx == i ? -1 : i;
            }
            GUILayout.Space(4);
            GUILayout.Label("手牌（点击出牌，× = 能源不足）：", small);
            handScroll = GUILayout.BeginScrollView(handScroll, GUILayout.Height(h - 360));
            Card toPlay = null;
            foreach (var c in g.hand.ToList())
            {
                bool can = g.CostOf(c) <= g.energy;
                GUI.enabled = can;
                string txt = (can ? "" : "× ") + BattleText.CardTitle(g, c) + "   ▶ " + BattleText.Eff(g, c) + (string.IsNullOrEmpty(c.text) ? "" : "\n" + c.text);
                if (GUILayout.Button(txt, button, GUILayout.MinHeight(48))) toPlay = c;
                GUI.enabled = true;
            }
            if (g.hand.Count == 0) GUILayout.Label("（无手牌）", small);
            GUILayout.EndScrollView();
            if (toPlay != null) PlayCard(toPlay);
            GUILayout.BeginHorizontal();
            if (result == null)
            {
                if (Btn("结束回合", GUILayout.Height(46))) EndTurn();
                if (Btn("自动打本回合", GUILayout.Height(46))) { foreach (var l in BattleText.AutoTurn(g)) Say("  " + l); EndTurn(); }
                if (Btn("自动打完整场", GUILayout.Height(46))) { autoAll = true; foreach (var l in BattleText.AutoTurn(g)) Say("  " + l); EndTurn(); }
                if (Btn("放弃", GUILayout.Height(46), GUILayout.Width(80))) { Say("放弃本场。"); screen = Page.Build; }
            }
            GUILayout.EndHorizontal();
            GUILayout.EndVertical();
            GUILayout.Space(10);
            GUILayout.BeginVertical();
            GUILayout.Label("战斗记录", heading);
            logScroll = GUILayout.BeginScrollView(logScroll, GUILayout.Height(h - 40));
            foreach (var l in log) GUILayout.Label(l, small);
            GUILayout.EndScrollView();
            GUILayout.EndVertical();
            GUILayout.EndHorizontal();
        }

        private void ResultScreen(float w, float h)
        {
            GUILayout.Label("战斗结束", title);
            GUILayout.Label(resultText, heading);
            GUILayout.Label("日志：" + logPath, small);
            GUILayout.BeginHorizontal();
            if (Btn("同构筑再战", GUILayout.Height(48), GUILayout.Width(200))) { seedText = (battleSeed + 1).ToString(); StartBattle(); }
            if (Btn("返回改构筑", GUILayout.Height(48), GUILayout.Width(200))) screen = Page.Build;
            GUILayout.EndHorizontal();
            logScroll = GUILayout.BeginScrollView(logScroll, GUILayout.Height(h - 200));
            foreach (var l in log) GUILayout.Label(l, small);
            GUILayout.EndScrollView();
        }
    }
}
