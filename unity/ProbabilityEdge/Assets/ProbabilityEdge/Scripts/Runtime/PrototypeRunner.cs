using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using ProbabilityEdge.Core;
using UnityEngine;

namespace ProbabilityEdge.Runtime
{
    // 最小切片使用 IMGUI，正式美术阶段替换表现层，不改结算和存档内核。
    public sealed class PrototypeRunner : MonoBehaviour
    {
        private const string DefaultSlot = "PrototypeV1";
        private const string NewSlotPrefix = "PrototypeV1-New-";
        private static readonly UTF8Encoding IndexEncoding = new UTF8Encoding(false, true);
        private static PrototypeRunner owner;
        private GameSession session;
        private SaveStore store;
        private readonly UnitySessionSerializer serializer = new UnitySessionSerializer();
        private bool paused;
        private bool blockWrites;
        private bool confirmNew;
        private bool invalidIndex;
        private bool indexPending;
        private bool applicationPaused;
        private bool applicationFocused = true;
        private bool suspensionHandled;
        private bool pauseRequested;
        private string slotName;
        private string expectedActiveSlot;
        private string lastSavedPayload;
        private string notice = "";
        private string seedText = "20261015";
        private Vector2 scroll;
        private Font font;
        private bool ownsFont;
        private Texture2D panelTexture;
        private Texture2D buttonTexture;
        private GUIStyle titleStyle, headingStyle, bodyStyle, buttonStyle, panelStyle, fieldStyle, smallStyle;
        private RunnerAction pendingAction;
        private LayoutSnapshot layoutSnapshot;

        private enum ActionKind { State, TogglePause, Pause, Save, SaveAndQuit, ShowNew, CancelNew, NewGame }
        private sealed class RunnerAction
        {
            public ActionKind kind;
            public Action apply;
        }
        private sealed class LayoutSnapshot
        {
            public GameState state;
            public bool paused, blockWrites, confirmNew;
            public string notice, savePath;
        }

        public GameSession Session { get { return session; } }
        public bool IsPaused { get { return paused; } }
        public string LastNotice { get { return notice; } }
        private bool IsActiveOwner { get { return owner == this && isActiveAndEnabled; } }
        private string ActiveIndexPath { get { return Path.Combine(Application.persistentDataPath, "PrototypeV1.active"); } }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void Bootstrap()
        {
            // 尊重用户场景中停用的对象，不自动激活它，也不另建一个实例。
            if (FindFirstObjectByType<PrototypeRunner>(FindObjectsInactive.Include) == null)
                new GameObject("ProbabilityEdge Prototype").AddComponent<PrototypeRunner>();
        }

        private void Awake()
        {
            if (owner != null && owner != this) { Destroy(this); return; }
            owner = this;
            Application.runInBackground = false;
            try
            {
                expectedActiveSlot = ReadActiveSlot();
                slotName = expectedActiveSlot ?? DefaultSlot;
                indexPending = expectedActiveSlot == null;
                store = CreateStore(slotName);
            }
            catch (Exception e)
            {
                invalidIndex = true;
                blockWrites = true;
                notice = "活动槽索引或槽路径无效，未读取其他槽，也不会覆盖索引。请检查 PrototypeV1.active 后重启。\n" + e.Message;
                return;
            }
            if (store.Exists)
            {
                try
                {
                    session = store.Load();
                    blockWrites = store.LastLoadUsedBackup;
                    // 健康主档也是去重基线，避免恢复后的首次失焦挤掉不同状态的备份。
                    if (!blockWrites) lastSavedPayload = SavedPayload();
                    notice = blockWrites ? "主存档异常，已载入备份。自动写入已暂停，原文件保留；开始新流程时会使用新槽。" : "已恢复上次流程，骰点和未选择的目标均保留。";
                }
                catch (Exception e)
                {
                    blockWrites = true;
                    notice = "存档无法恢复，原文件保留。可开始独立新槽，不会覆盖旧档。\n" + e.Message;
                }
            }
            else notice = "第一章《出逃》共5关50节点。第二章尚未制作。";
        }

        private void Update()
        {
            if (!IsActiveOwner) return;
            if (pauseRequested && pendingAction == null)
            {
                QueueAction(ActionKind.Pause);
                pauseRequested = false;
            }
            if (Input.GetKeyDown(KeyCode.Escape) && session != null)
                QueueAction(ActionKind.TogglePause);
            RunnerAction action = pendingAction;
            pendingAction = null;
            if (action != null) ExecuteAction(action);
            if (pauseRequested)
            {
                QueueAction(ActionKind.Pause);
                pauseRequested = false;
            }
        }

        private void OnApplicationPause(bool value)
        {
            if (!IsActiveOwner) return;
            applicationPaused = value;
            HandleSuspension();
        }
        private void OnApplicationFocus(bool value)
        {
            if (!IsActiveOwner) return;
            applicationFocused = value;
            HandleSuspension();
        }
        private void HandleSuspension()
        {
            if (!applicationPaused && applicationFocused) { suspensionHandled = false; return; }
            if (suspensionHandled || session == null) return;
            suspensionHandled = true;
            pauseRequested = true;
            // 系统挂起后 Update 可能不再执行，保存不能只依赖下一帧；暂停界面仍走队列。
            SaveNow();
        }
        private void OnApplicationQuit() { if (IsActiveOwner) SaveNow(); }
        private void OnDisable()
        {
            pendingAction = null;
            pauseRequested = false;
            suspensionHandled = false;
            layoutSnapshot = null;
        }
        private void OnDestroy()
        {
            if (owner == this) owner = null;
            if (ownsFont && font != null) Destroy(font);
            if (panelTexture != null) Destroy(panelTexture);
            if (buttonTexture != null) Destroy(buttonTexture);
        }

        public bool SaveNow()
        {
            if (!IsActiveOwner) return false;
            if (blockWrites)
            {
                notice = invalidIndex ? "活动槽索引或路径无效，禁止写入及保存并退出；请检查 PrototypeV1.active 后重启。" : "当前禁止写入；损坏旧档与备份保留。请开始独立新槽，不能保存并退出。";
                return false;
            }
            if (session == null) { notice = "尚未开始流程，没有可保存的进度。"; return false; }
            try
            {
                string payload = SavedPayload();
                if (!string.Equals(payload, lastSavedPayload, StringComparison.Ordinal))
                {
                    ValidateSlotDirectory(slotName);
                    store.Save(session);
                    lastSavedPayload = payload;
                }
                // 只有槽保存成功（或已有健康主档）后才发布索引；发布失败仍返回失败。
                if (indexPending) WriteActiveSlot();
                return true;
            }
            catch (Exception e)
            {
                notice = "保存失败，请不要退出；当前内存进度还在。活动槽索引可能尚未更新。\n" + e.Message;
                return false;
            }
        }

        private string SavedPayload()
        {
            return (session.Data.battleCheckpoint == null ? "0\n" : "1\n") + serializer.Serialize(session.Data);
        }

        private static bool IsAllowedSlot(string value)
        {
            if (value == DefaultSlot) return true;
            if (value == null || value.Length != NewSlotPrefix.Length + 32 || !value.StartsWith(NewSlotPrefix, StringComparison.Ordinal)) return false;
            for (int i = NewSlotPrefix.Length; i < value.Length; i++)
            {
                char c = value[i];
                if (!(c >= '0' && c <= '9') && !(c >= 'a' && c <= 'f') && !(c >= 'A' && c <= 'F')) return false;
            }
            return true;
        }

        private string ReadActiveSlot()
        {
            try
            {
                FileAttributes attributes = File.GetAttributes(ActiveIndexPath);
                if ((attributes & (FileAttributes.ReparsePoint | FileAttributes.Directory)) != 0)
                    throw new InvalidDataException("活动槽索引必须是普通文件。");
                using (FileStream stream = new FileStream(ActiveIndexPath, FileMode.Open, FileAccess.Read, FileShare.Read))
                {
                    if (stream.Length == 0 || stream.Length > NewSlotPrefix.Length + 32)
                        throw new InvalidDataException("活动槽索引为空或超长。");
                    byte[] bytes = new byte[(int)stream.Length];
                    int offset = 0;
                    while (offset < bytes.Length)
                    {
                        int read = stream.Read(bytes, offset, bytes.Length - offset);
                        if (read == 0) throw new InvalidDataException("活动槽索引读取不完整。");
                        offset += read;
                    }
                    if (stream.ReadByte() != -1) throw new InvalidDataException("活动槽索引在读取期间变化。");
                    string value = IndexEncoding.GetString(bytes);
                    if (!IsAllowedSlot(value)) throw new InvalidDataException("活动槽名仅允许 PrototypeV1 或 PrototypeV1-New-32位十六进制标识。");
                    return value;
                }
            }
            catch (FileNotFoundException) { return null; }
            catch (DirectoryNotFoundException) { return null; }
        }

        private string ValidateSlotDirectory(string name)
        {
            if (!IsAllowedSlot(name)) throw new InvalidDataException("活动槽名无效。");
            string directory = Path.Combine(Application.persistentDataPath, name);
            if (Directory.Exists(directory) && (File.GetAttributes(directory) & FileAttributes.ReparsePoint) != 0)
                throw new InvalidDataException("存档槽不能是符号链接。");
            return directory;
        }
        private SaveStore CreateStore(string name)
        {
            return new SaveStore(ValidateSlotDirectory(name), serializer);
        }

        private void WriteActiveSlot()
        {
            string current = ReadActiveSlot();
            if (!string.Equals(current, expectedActiveSlot, StringComparison.Ordinal))
                throw new IOException("活动槽索引已被其他操作修改；保留原索引，请检查后重试。");
            if (current == slotName) { indexPending = false; return; }
            string temporary = ActiveIndexPath + ".tmp";
            bool ownsTemporary = false;
            try
            {
                byte[] bytes = IndexEncoding.GetBytes(slotName);
                using (FileStream stream = new FileStream(temporary, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                {
                    ownsTemporary = true;
                    stream.Write(bytes, 0, bytes.Length);
                    stream.Flush(true);
                }
                // 不支持原子替换就报失败，不删除旧索引、不降级覆盖。
                if (current != null) File.Replace(temporary, ActiveIndexPath, null);
                else File.Move(temporary, ActiveIndexPath);
                expectedActiveSlot = slotName;
                indexPending = false;
            }
            catch (Exception writeError)
            {
                if (ownsTemporary)
                {
                    try { File.Delete(temporary); }
                    catch (Exception cleanupError)
                    {
                        throw new IOException("活动槽索引写入失败，且临时文件清理失败；旧索引保留。", new AggregateException(writeError, cleanupError));
                    }
                }
                throw;
            }
        }

        private void NewGame()
        {
            if (invalidIndex) throw new InvalidOperationException("活动槽索引或路径无效；不会创建或覆盖其他槽。请检查 PrototypeV1.active 后重启。");
            uint seed;
            if (!uint.TryParse(seedText, out seed)) throw new ArgumentException("种子必须是0～4294967295范围的整数。");
            GameSession newSession = GameSession.New(seed);
            if (blockWrites)
            {
                // 不覆盖损坏主档或唯一健康备份；首次保存成功后索引才指向新槽。
                string newSlot = NewSlotPrefix + Guid.NewGuid().ToString("N");
                SaveStore newStore = CreateStore(newSlot);
                slotName = newSlot;
                store = newStore;
                indexPending = true;
                blockWrites = false;
                lastSavedPayload = null;
            }
            session = newSession;
            paused = false;
            confirmNew = false;
            notice = "新流程开始。测试默认：十面骰，3投/回合，战间清盾，跨回合保留盾。";
        }

        private void QueueAction(ActionKind kind, Action action = null)
        {
            // OnGUI 只登记一个动作，不改变本轮 Layout 的控件树。
            if (!IsActiveOwner || pendingAction != null) return;
            pendingAction = new RunnerAction { kind = kind, apply = action };
        }

        private void ExecuteAction(RunnerAction action)
        {
            try
            {
                switch (action.kind)
                {
                    case ActionKind.State:
                        action.apply();
                        notice = "";
                        SaveNow();
                        break;
                    case ActionKind.NewGame:
                        NewGame();
                        SaveNow();
                        break;
                    case ActionKind.TogglePause:
                        if (session == null) break;
                        paused = !paused;
                        if (paused) SaveNow();
                        break;
                    case ActionKind.Pause:
                        if (session != null) paused = true;
                        break;
                    case ActionKind.ShowNew:
                        confirmNew = true;
                        break;
                    case ActionKind.CancelNew:
                        confirmNew = false;
                        break;
                    case ActionKind.Save:
                        if (SaveNow()) notice = "已保存当前节点与战斗状态。";
                        break;
                    case ActionKind.SaveAndQuit:
                        if (SaveNow()) Application.Quit();
                        break;
                }
            }
            catch (Exception e) { notice = e.Message; }
        }

        private void InitStyles()
        {
            if (titleStyle != null) return;
            string[] installed = Font.GetOSInstalledFontNames();
            string selected = null;
            // 仅原型使用操作系统字体；Windows 候选与内置后备都不是成品嵌入字体。
            foreach (string name in new[] { "PingFang SC", "Microsoft YaHei", "Microsoft YaHei UI", "Noto Sans CJK SC", "Arial Unicode MS", "Heiti SC", "SimSun" })
                if (Array.IndexOf(installed, name) >= 0) { selected = name; break; }
            ownsFont = selected != null;
            font = ownsFont ? Font.CreateDynamicFontFromOSFont(selected, 24) : Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            panelTexture = Solid(new Color(0.94f, 0.96f, 0.98f));
            buttonTexture = Solid(new Color(0.87f, 0.92f, 0.97f));
            titleStyle = Label(28, new Color(0.08f, 0.17f, 0.28f), true);
            headingStyle = Label(20, new Color(0.10f, 0.22f, 0.34f), true);
            bodyStyle = Label(17, new Color(0.16f, 0.22f, 0.29f), true);
            smallStyle = Label(14, new Color(0.35f, 0.42f, 0.49f), true);
            buttonStyle = new GUIStyle(GUI.skin.button) { font = font, fontSize = 17, fixedHeight = 48, wordWrap = true };
            buttonStyle.normal.background = buttonTexture;
            buttonStyle.normal.textColor = new Color(0.08f, 0.19f, 0.31f);
            buttonStyle.hover.textColor = Color.black;
            buttonStyle.active.textColor = Color.black;
            buttonStyle.focused.textColor = Color.black;
            panelStyle = new GUIStyle(GUI.skin.box) { padding = new RectOffset(24, 24, 20, 20) };
            panelStyle.normal.background = panelTexture;
            fieldStyle = new GUIStyle(GUI.skin.textField) { font = font, fontSize = 17, fixedHeight = 36 };
        }

        private GUIStyle Label(int size, Color color, bool wrap)
        {
            GUIStyle style = new GUIStyle(GUI.skin.label) { font = font, fontSize = size, wordWrap = wrap };
            style.normal.textColor = color;
            return style;
        }
        private static Texture2D Solid(Color color)
        {
            Texture2D texture = new Texture2D(1, 1);
            texture.SetPixel(0, 0, color); texture.Apply(); return texture;
        }
        private bool Button(string text) { return GUILayout.Button(text, buttonStyle); }
        private void Text(string text) { GUILayout.Label(text, bodyStyle); }
        private void Gap(float pixels = 12) { GUILayout.Space(pixels); }

        private void OnGUI()
        {
            if (!IsActiveOwner) return;
            InitStyles();
            if (Event.current.type == EventType.Layout || layoutSnapshot == null)
            {
                layoutSnapshot = new LayoutSnapshot
                {
                    state = session == null ? null : JsonUtility.FromJson<GameState>(JsonUtility.ToJson(session.Data.state)),
                    paused = paused || pauseRequested,
                    blockWrites = blockWrites,
                    confirmNew = confirmNew,
                    notice = notice,
                    savePath = store == null ? "" : store.SavePath
                };
            }
            LayoutSnapshot view = layoutSnapshot;
            bool originalEnabled = GUI.enabled;
            GUI.enabled = originalEnabled && pendingAction == null && !pauseRequested;
            float scale = Mathf.Min(Screen.width / 1100f, Screen.height / 740f);
            scale = Mathf.Max(0.1f, scale);
            GUI.matrix = Matrix4x4.TRS(Vector3.zero, Quaternion.identity, new Vector3(scale, scale, 1));
            float w = Screen.width / scale, h = Screen.height / scale;
            GUI.color = new Color(0.985f, 0.989f, 0.994f);
            GUI.DrawTexture(new Rect(0, 0, w, h), Texture2D.whiteTexture);
            GUI.color = Color.white;
            GUILayout.BeginArea(new Rect((w - 1040) / 2, 18, 1040, h - 36));
            GUILayout.Label("概率边缘 · 出逃", titleStyle);
            GUILayout.Label("试玩版 v" + Application.version + " | 第一章 · 5关50节点 · 12战斗 | 纯文字原型，美术与音效尚未制作", smallStyle);
            Gap();
            GUILayout.BeginHorizontal();
            if (Button("暂停 / 恢复")) QueueAction(ActionKind.TogglePause);
            if (Button("保存")) QueueAction(ActionKind.Save);
            if (Button("新流程")) QueueAction(ActionKind.ShowNew);
            if (Button("保存并退出")) QueueAction(ActionKind.SaveAndQuit);
            GUILayout.EndHorizontal();
            Gap(8);
            if (!string.IsNullOrEmpty(view.notice)) GUILayout.Label(view.notice, smallStyle);
            if (view.blockWrites) GUILayout.Label("当前写入暂停；损坏旧档与备份都不会自动覆盖。", smallStyle);
            if (view.confirmNew)
            {
                GUILayout.BeginVertical(panelStyle);
                Text("重新开始会重置当前槽的流程和局内强化。先确认是否需要保留当前进度。");
                seedText = GUILayout.TextField(seedText, fieldStyle);
                GUILayout.BeginHorizontal();
                if (Button("确认开始")) QueueAction(ActionKind.NewGame);
                if (Button("取消")) QueueAction(ActionKind.CancelNew);
                GUILayout.EndHorizontal();
                GUILayout.EndVertical();
            }
            if (view.state == null)
            {
                GUILayout.BeginVertical(panelStyle);
                Text("你刚离开集团关押室，尚未离开设施。先验证一段完整的出逃流程。");
                Gap();
                Text("随机种子（同种子可复现；默认便于自测）");
                seedText = GUILayout.TextField(seedText, fieldStyle);
                if (Button("开始第一章")) QueueAction(ActionKind.NewGame);
                GUILayout.EndVertical();
            }
            else
            {
                GameState s = view.state;
                NodeDef node = ChapterOne.Node(s.nodeIndex);
                List<string> evidence = new List<string>();
                for (int i = 0; i < s.nodeIndex; i++) if (ChapterOne.Node(i).evidence != "") evidence.Add(ChapterOne.Node(i).evidence);
                GUILayout.Label("第" + ChapterOne.StageOf(s.nodeIndex) + "关 · 节点 " + ChapterOne.StepOf(s.nodeIndex) + "/10（全章 " + (s.nodeIndex + 1) + "/50）    生命 " + s.hp + "/" + s.maxHp + "    护盾 " + s.shield, headingStyle);
                GUILayout.Label("骰面：剑×4 / 盾×3 / 心×2 / 枪击×1    效果：剑" + s.sword + " / 盾" + s.shieldPower + " / 心" + s.heal + " / 枪击" + s.shot +
                    "    强化 " + s.upgradedNodes.Count + "/7    证据：" + (evidence.Count == 0 ? "无" : string.Join("、", evidence.ToArray())), smallStyle);
                Gap();
                scroll = GUILayout.BeginScrollView(scroll);
                GUILayout.BeginVertical(panelStyle);
                GUILayout.Label(node.id + "  " + node.title, headingStyle);
                Gap();
                Text(node.text);
                Gap();
                bool previous = GUI.enabled;
                GUI.enabled = previous && !view.paused && !view.confirmNew;
                DrawPhase(s, node, view.savePath);
                GUI.enabled = previous;
                if (view.paused) GUILayout.Label("已暂停。选择与结算不会继续推进；点击恢复继续。", headingStyle);
                GUILayout.EndVertical();
                Gap();
                GUILayout.Label("最近结算", headingStyle);
                foreach (string log in s.logs) GUILayout.Label(log, smallStyle);
                GUILayout.EndScrollView();
            }
            GUILayout.EndArea();
            GUI.enabled = originalEnabled;
        }

        private void DrawPhase(GameState s, NodeDef node, string savePath)
        {
            if (s.phase == "battle")
            {
                Text("第 " + s.turn + " 回合 | 剩余 " + s.rollsLeft + " 次投掷 | 你的护盾 " + s.shield + "（敌方回合后清零）");
                if (s.pendingFace >= 0) Text("投出第" + (s.pendingFace + 1) + "面：" + GameSession.SkillName(s.pendingSkill) + "（" + (s.pendingSkill == "sword" ? s.sword : s.shot) + "伤害），点击存活敌人作为目标。");
                foreach (EnemyState enemy in s.enemies)
                {
                    int id = enemy.id;
                    string text = enemy.name + "  生命 " + enemy.hp + "/" + enemy.maxHp + (enemy.shield > 0 ? "  护盾 " + enemy.shield : "") +
                        "  | 下步：" + GameSession.DescribeIntent(enemy.intent);
                    if (enemy.hp > 0 && s.pendingFace >= 0)
                    { if (Button(text + "  → 选择")) QueueAction(ActionKind.State, () => session.ChooseTarget(id)); }
                    else GUILayout.Label(text + (enemy.hp == 0 ? "（已击败）" : ""), bodyStyle);
                }
                Gap();
                GUILayout.BeginHorizontal();
                bool enabled = GUI.enabled;
                GUI.enabled = enabled && s.rollsLeft > 0 && s.pendingFace < 0;
                if (Button("投掷技能骰")) QueueAction(ActionKind.State, () => session.Roll());
                GUI.enabled = enabled && s.pendingFace < 0;
                if (Button(s.rollsLeft > 0 ? "提前结束回合（放弃剩余投数）" : "结束回合 → 敌人行动")) QueueAction(ActionKind.State, () => session.EndTurn());
                GUI.enabled = enabled;
                GUILayout.EndHorizontal();
                if (s.battleRetries > 0) GUILayout.Label("本战已重试 " + s.battleRetries + " 次。", smallStyle);
            }
            else if (s.phase == "story")
            {
                if (Button(node.evidence != "" ? "带上" + node.evidence + "，继续" : "继续")) QueueAction(ActionKind.State, () => session.Advance());
            }
            else if (s.phase == "choice")
            {
                for (int i = 0; i < node.choices.Length; i++)
                { int choice = i; if (Button(node.choices[i])) QueueAction(ActionKind.State, () => session.Advance(choice)); }
            }
            else if (s.phase == "supply")
            {
                bool upgraded = s.upgradedNodes.Contains(s.nodeIndex);
                if (!s.supplyClaimed)
                { if (Button("使用补给（恢复最多" + node.heal + "）")) QueueAction(ActionKind.State, () => session.ClaimSupply()); }
                else Text("补给已结算，退出恢复不会再次领取。");
                if (node.reward && s.supplyClaimed && !upgraded)
                {
                    Text("选择一个已携带技能强化+2；只在本次流程内生效，不新增或重贴骰面。");
                    GUILayout.BeginHorizontal();
                    string[] skills = { "sword", "shield", "heal", "shot" };
                    for (int i = 0; i < skills.Length; i++)
                    { string skill = skills[i]; if (Button(GameSession.SkillName(skill) + " +2")) QueueAction(ActionKind.State, () => session.Upgrade(skill)); }
                    GUILayout.EndHorizontal();
                }
                if (s.supplyClaimed && (!node.reward || upgraded))
                    if (Button("继续")) QueueAction(ActionKind.State, () => session.Advance());
            }
            else if (s.phase == "event")
            {
                EventDef e = ChapterOne.Event(node.eventIndex);
                if (Button(e.safeLabel)) QueueAction(ActionKind.State, () => session.ResolveEvent(false));
                if (Button(e.riskLabel)) QueueAction(ActionKind.State, () => session.ResolveEvent(true));
            }
            else if (s.phase == "eventResult")
            {
                EventDef e = ChapterOne.Event(node.eventIndex);
                int roll = s.eventRolls[s.nodeIndex];
                string grade = roll == 0 ? "安全选择" : "D20 = " + roll + (roll == 20 ? " · 大成功" : roll == 1 ? " · 大失败" : roll >= GameSession.SuccessThreshold ? " · 成功" : " · 失败");
                string result = roll == 0 ? e.safeText : roll == 20 ? e.critText : roll == 1 ? e.fumbleText : roll >= GameSession.SuccessThreshold ? e.successText : e.failText;
                GUILayout.Label(grade, headingStyle);
                Text(result + "\n当前生命 " + s.hp + "/" + s.maxHp + "。无论结果如何，这条路都能继续。");
                if (Button("确认结果，继续")) QueueAction(ActionKind.State, () => session.Advance());
            }
            else if (s.phase == "defeat")
            {
                Text("战斗失败。重试回到此战开场状态（生命与强化不变，补给不会重复发放），骰子序列会重新洗牌。");
                if (Button("从战前检查点重试")) QueueAction(ActionKind.State, () => session.ResetBattle());
            }
            else if (s.phase == "completed")
            {
                GUILayout.Label("第一章《出逃》完成", headingStyle);
                Text("你完成了全部50个节点：章末生命 " + s.hp + "/" + s.maxHp + "，强化 " + s.upgradedNodes.Count + " 次。\n第二至五章尚未制作。可以用新种子重新开局，测试不同的选择、D20与强化路线。");
                Text("存档位置：" + savePath);
            }
        }

    }
}
