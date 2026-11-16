using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using ProbabilityEdge.Core;

internal static class Program
{
    private static readonly JsonSerializerOptions JsonOptions = new JsonSerializerOptions { IncludeFields = true };
    private static int assertions;
    private static int failures;
    private static int groups;

    private static readonly int[] BattleNodes = { 2, 5, 8, 11, 17, 22, 25, 28, 31, 37, 42, 46 };
    private static readonly string[] BattleEnemies =
    {
        "patrol", "binder", "patrol,security", "patrol,binder", "mage,patrol", "security,binder",
        "elite", "mage,security", "patrol,patrol", "operator", "mage,binder", "captain"
    };
    private static readonly int[] SupplyNodes = { 3, 6, 9, 12, 18, 23, 26, 29, 32, 38, 43, 47 };
    private static readonly int[] SupplyHeals = { 10, 8, 10, 10, 10, 12, 10, 10, 8, 16, 10, 12 };
    private static readonly int[] RewardNodes = { 6, 12, 18, 23, 29, 38, 43 };
    private static readonly int[] EventNodes = { 4, 13, 24, 33, 41 };
    private static readonly int[] ChoiceNodes = { 1, 14, 15, 20, 27, 34, 36, 44, 45, 48 };
    private static readonly int[] EvidenceNodes = { 7, 20, 35 };
    private static readonly string[] EvidenceNames = { "关押记录", "转运记录", "局部识别链" };
    private static readonly string[] Skills = { "sword", "shield", "heal", "shot" };

    // 每个事件：安全、20、12～19、2～11、1 的生命变化（与剧情文本中的规则一致）。
    private static readonly int[][] EventDeltas =
    {
        new[] { 0, 12, 0, -4, -8 },
        new[] { 8, 16, 12, 4, -4 },
        new[] { 0, 16, 8, -4, -8 },
        new[] { 0, 12, 8, -4, -8 },
        new[] { 8, 16, 12, 4, -4 }
    };

    private static readonly string[][] Templates =
    {
        new[] { "patrol", "巡检机", "24", "attack:13" },
        new[] { "binder", "束缚器", "30", "wait,attack:26" },
        new[] { "security", "安保员", "38", "attack:16,charge,attack:26" },
        new[] { "mage", "术式安保", "36", "shield:8,attack:15,attack:15" },
        new[] { "elite", "精英锁卫", "72", "shield:10,charge,attack:36,attack:18" },
        new[] { "operator", "束缚器操作者", "40", "wait,attack:24,attack:16" },
        new[] { "captain", "回收队长", "110", "shield:12,charge,attack:42,attack:20" }
    };

    private static Dictionary<int, SessionData> snapshots;

    private static int Main()
    {
        Run("第一章50节点数据完整性", DataIntegrity);
        Run("初始状态、版本2与基础技能", InitialState);
        Run("十面骰布局与无偏拒绝采样", DiceLayout);
        Run("剑与枪击伤害、待选目标与敌人护盾吸收", TargetDamage);
        Run("玩家护盾吸收、回合清零与治疗上限", ShieldAndHeal);
        Run("三投限制、提前结束与无效动作原子拒绝", TurnRules);
        Run("多目标胜利、失败与敌方行动顺序", VictoryAndDefeat);
        Run("七类敌人行动循环与意图", EnemySchedules);
        Run("选择节点存储与证据收集", ChoicesAndEvidence);
        Run("补给领取、技能强化与推进幂等", SuppliesAndUpgrades);
        Run("五个D20事件所有分支与最低生命", EventBranches);
        Run("事件结果恢复后推进且不重掷", EventPersistence);
        Run("存档序列化、待选技能与随机状态", Serialization);
        Run("固定种子完整重放", FixedSeedReplay);
        Run("十二场战斗失败重试与重新洗牌", CheckpointRetry);
        Run("存档结构、阶段与进度非法变异拒绝", InvalidSaves);
        Run("战斗、失败与检查点非法变异拒绝", InvalidBattleSaves);
        Run("手工深拷贝与日志12条上限", CloneAndLogs);
        Run("多种子全章自然通关与每步精确恢复", NaturalPlay);
        SaveStoreTests.Run(Run, Check);
        Console.WriteLine("测试组：" + groups + "；断言：" + assertions + "；失败：" + failures + "。");
        return failures == 0 ? 0 : 1;
    }

    private static void Run(string name, Action test)
    {
        groups++;
        try { test(); Console.WriteLine("通过：" + name); }
        catch (Exception exception) { failures++; Console.WriteLine("失败：" + name + "\n" + exception); }
    }

    private static void Check(bool condition, string message)
    {
        assertions++;
        if (!condition) throw new Exception(message);
    }

    private static void Equal<T>(T expected, T actual, string message)
    {
        Check(EqualityComparer<T>.Default.Equals(expected, actual), message + "，预期=" + expected + "，实际=" + actual);
    }

    private static string Save(SessionData data) { return JsonSerializer.Serialize(data, JsonOptions); }
    private static string Json(GameState state) { return JsonSerializer.Serialize(state, JsonOptions); }
    private static SessionData Read(string json) { return JsonSerializer.Deserialize<SessionData>(json, JsonOptions); }
    private static GameSession RoundTrip(GameSession session) { return GameSession.Restore(Read(Save(session.Data))); }
    private static string Join(IEnumerable<int> values) { return string.Join(",", values); }

    private static void Invalid(GameSession session, Action action)
    {
        string before = Save(session.Data);
        bool rejected = false;
        try { action(); } catch (InvalidOperationException) { rejected = true; }
        Check(rejected, "无效动作必须拒绝");
        Equal(before, Save(session.Data), "无效动作不能改变任何状态或随机数");
    }

    private static void RejectSave(SessionData data)
    {
        string before = Save(data);
        bool rejected = false;
        try { GameSession.Restore(data); } catch (InvalidOperationException) { rejected = true; }
        Check(rejected, "无效存档必须拒绝");
        Equal(before, Save(data), "拒绝恢复不能修改输入存档");
    }

    private static void RejectAll(SessionData source, string label, params Action<SessionData>[] mutations)
    {
        string json = Save(source);
        Equal(json, Save(GameSession.Restore(source).Data), label + "：变异基准本身合法");
        Equal(json, Save(source), label + "：合法恢复不修改输入");
        for (int i = 0; i < mutations.Length; i++)
        {
            SessionData data = GameSession.Clone(source);
            mutations[i](data);
            try { RejectSave(data); }
            catch (Exception error) { throw new Exception(label + " 第" + i + "个变异：" + error.Message); }
        }
    }

    // —— 随机数逆推 ——
    private static uint Next(uint value)
    {
        value ^= value << 13;
        value ^= value >> 17;
        value ^= value << 5;
        return value;
    }

    private static uint Bounded(ref uint seed, uint bound)
    {
        uint threshold = unchecked(0u - bound) % bound;
        do { seed = Next(seed); } while (seed < threshold);
        return seed % bound;
    }

    private static uint SeedFor(uint bound, int result)
    {
        for (uint seed = 1; seed < 100000; seed++)
        {
            uint state = seed;
            if (Bounded(ref state, bound) == result) return seed;
        }
        throw new Exception("没有找到测试种子");
    }

    private static uint UndoLeft(uint value, int shift)
    {
        uint result = value;
        for (int bits = shift; bits < 32; bits += shift) result ^= value << bits;
        return result;
    }

    private static uint UndoRight(uint value, int shift)
    {
        uint result = value;
        for (int bits = shift; bits < 32; bits += shift) result ^= value >> bits;
        return result;
    }

    private static uint SeedProducing(uint value) { return UndoLeft(UndoRight(UndoLeft(value, 5), 17), 13); }

    private static uint MixSeed(uint seed, uint salt)
    {
        uint x = seed ^ (salt * 0x9E3779B9u);
        x ^= x >> 16; x *= 0x7FEB352Du; x ^= x >> 15; x *= 0x846CA68Bu; x ^= x >> 16;
        return x == 0 ? 0x6D2B79F5u : x;
    }

    // 下一次输出恰为 10+face（≥6 不被拒绝，模10得face）。
    private static int ForceFace(GameSession session, int face)
    {
        uint output = (uint)(10 + face);
        session.Data.state.rngState = SeedProducing(output);
        int result = session.Roll();
        Equal(face, result, "构造随机状态应投出指定骰面");
        Equal(output, session.Data.state.rngState, "单次采样只推进一次随机状态");
        return result;
    }

    // 下一次输出恰为 roll+19（≥16 不被拒绝，模20得roll-1）。
    private static void SetD20(GameSession session, int roll)
    {
        session.Data.state.rngState = SeedProducing((uint)(roll + 19));
    }

    private static int FirstAlive(GameState s)
    {
        foreach (EnemyState enemy in s.enemies) if (enemy.hp > 0) return enemy.id;
        throw new Exception("没有存活敌人");
    }

    private static void BattleAction(GameSession session)
    {
        GameState s = session.Data.state;
        if (s.pendingFace != -1) session.ChooseTarget(FirstAlive(s));
        else if (s.rollsLeft == 0) session.EndTurn();
        else ForceFace(session, GameSession.ShotFace);
    }

    private static void ClearBattle(GameSession session)
    {
        for (int steps = 0; session.Data.state.phase == "battle" && steps < 300; steps++) BattleAction(session);
        Equal("supply", session.Data.state.phase, "战斗胜利后必须进入补给节点");
    }

    private static void DefeatNow(GameSession session)
    {
        session.Data.state.hp = 1;
        for (int i = 0; session.Data.state.phase == "battle" && i < 10; i++)
        {
            if (session.Data.state.pendingFace != -1) session.ChooseTarget(FirstAlive(session.Data.state));
            session.EndTurn();
        }
        Equal("defeat", session.Data.state.phase, "构造战斗失败");
    }

    // 以固定枪击走完整章，记录每个节点首次进入时的会话快照（奖励统一强化“心”，不影响伤害数值）。
    private static GameSession AtNode(int index)
    {
        if (snapshots == null)
        {
            Dictionary<int, SessionData> map = new Dictionary<int, SessionData>();
            GameSession session = GameSession.New(12345);
            map[0] = GameSession.Clone(session.Data);
            for (int steps = 0; session.Data.state.phase != "completed" && steps < 5000; steps++)
            {
                GameState s = session.Data.state;
                int before = s.nodeIndex;
                if (s.phase == "battle") BattleAction(session);
                else if (s.phase == "supply")
                {
                    if (!s.supplyClaimed) session.ClaimSupply();
                    else if (session.CurrentNode.reward && !session.CurrentUpgradeChosen) session.Upgrade("heal");
                    else session.Advance();
                }
                else if (s.phase == "event") session.ResolveEvent(false);
                else session.Advance();
                if (session.Data.state.nodeIndex != before) map[session.Data.state.nodeIndex] = GameSession.Clone(session.Data);
            }
            Equal("completed", session.Data.state.phase, "快照路线应通关");
            Equal(ChapterOne.NodeCount, map.Count, "快照覆盖全部节点");
            snapshots = map;
        }
        GameSession result = GameSession.Restore(snapshots[index]);
        Equal(index, result.Data.state.nodeIndex, "应到达目标节点");
        return result;
    }

    private static string[] SpecActions(string kind)
    {
        foreach (string[] t in Templates) if (t[0] == kind) return t[3].Split(',');
        throw new Exception("未知敌人：" + kind);
    }

    private static bool ValidAction(string action)
    {
        if (action == "wait" || action == "charge") return true;
        int value;
        return (action.StartsWith("attack:") || action.StartsWith("shield:")) && int.TryParse(action.Substring(7), out value) && value > 0;
    }

    private static int ActionValue(string action, string prefix)
    {
        return action.StartsWith(prefix) ? int.Parse(action.Substring(prefix.Length)) : 0;
    }

    // —— 1. 数据完整性 ——
    private static void DataIntegrity()
    {
        Equal(50, ChapterOne.NodeCount, "节点总数");
        foreach (int bad in new[] { -1, 50 })
        {
            bool thrown = false;
            try { ChapterOne.Node(bad); } catch (ArgumentOutOfRangeException) { thrown = true; }
            Check(thrown, "节点越界抛出ArgumentOutOfRangeException");
        }
        List<int> battles = new List<int>(), supplies = new List<int>(), rewards = new List<int>(), events = new List<int>(),
            choices = new List<int>(), evidence = new List<int>(), endings = new List<int>(), eventIndexes = new List<int>(), heals = new List<int>();
        HashSet<string> ids = new HashSet<string>();
        for (int i = 0; i < ChapterOne.NodeCount; i++)
        {
            NodeDef n = ChapterOne.Node(i);
            string id = "C1-0" + (i / 10 + 1) + "-" + (i % 10 + 1).ToString("00");
            Equal(id, n.id, "节点编号格式C1-0S-0N");
            Check(n.id.Length == 8 && n.id.StartsWith("C1-0") && n.id[5] == '-', "编号固定8字符");
            Check(ids.Add(n.id), "编号唯一");
            Equal(i / 10 + 1, ChapterOne.StageOf(i), "关卡序号");
            Equal(i % 10 + 1, ChapterOne.StepOf(i), "关内步骤");
            Check(!string.IsNullOrEmpty(n.title) && !string.IsNullOrEmpty(n.text), "每节点有标题与剧情");
            Check(n.choices != null && n.responses != null && n.enemies != null && n.evidence != null, "数组与证据非null");
            Equal(n.choices.Length, n.responses.Length, "选项与回应等长");
            Check(new[] { "story", "choice", "battle", "supply", "event", "ending" }.Contains(n.kind), "节点类型合法");
            if (n.kind == "choice")
            {
                choices.Add(i);
                Check(n.choices.Length >= 2, "选择节点至少两个选项");
                for (int c = 0; c < n.choices.Length; c++) Check(n.choices[c] != "" && n.responses[c] != "", "选项与回应非空");
            }
            else Equal(0, n.choices.Length, "非选择节点没有选项");
            if (n.kind == "battle")
            {
                battles.Add(i);
                Check(n.enemies.Length >= 1 && n.enemies.Length <= 3, "战斗敌人数量");
                foreach (string kind in n.enemies)
                {
                    EnemyTemplate t = ChapterOne.Template(kind);
                    Equal(kind, t.kind, "敌人模板存在且kind一致");
                    Check(t.hp > 0 && t.actions.Length > 0 && t.actions.All(ValidAction), "模板生命与行动格式");
                }
                Check(i + 1 < ChapterOne.NodeCount, "战斗不能是最后节点");
                Equal("supply", ChapterOne.Node(i + 1).kind, "每场战斗后紧跟补给");
            }
            else Equal(0, n.enemies.Length, "非战斗节点没有敌人");
            if (n.kind == "supply")
            {
                supplies.Add(i);
                heals.Add(n.heal);
                Check(n.heal > 0, "补给恢复量为正");
                Equal("battle", ChapterOne.Node(i - 1).kind, "补给前一节点为战斗");
                if (n.reward) rewards.Add(i);
            }
            else Check(n.heal == 0 && !n.reward, "非补给节点没有恢复与奖励");
            if (n.kind == "event") { events.Add(i); eventIndexes.Add(n.eventIndex); }
            else Equal(-1, n.eventIndex, "非事件节点eventIndex为-1");
            if (n.kind == "ending") endings.Add(i);
            if (n.evidence != "") evidence.Add(i);
        }
        Equal(Join(BattleNodes), Join(battles), "12场战斗位置");
        Equal(12, battles.Count, "12场战斗");
        Equal(Join(SupplyNodes), Join(supplies), "12处补给位置");
        Equal(Join(SupplyHeals), Join(heals), "补给恢复量");
        Equal(Join(RewardNodes), Join(rewards), "7处奖励补给");
        Equal(Join(EventNodes), Join(events), "5个事件位置");
        Equal("0,1,2,3,4", Join(eventIndexes), "事件索引各用一次且按序");
        Equal(Join(ChoiceNodes), Join(choices), "选择节点位置");
        Equal("49", Join(endings), "ending只在最后");
        Equal(Join(EvidenceNodes), Join(evidence), "证据节点");
        for (int i = 0; i < EvidenceNodes.Length; i++) Equal(EvidenceNames[i], ChapterOne.Node(EvidenceNodes[i]).evidence, "证据名称");
        for (int b = 0; b < BattleNodes.Length; b++) Equal(BattleEnemies[b], string.Join(",", ChapterOne.Node(BattleNodes[b]).enemies), "战斗敌人配置");
        foreach (string[] spec in Templates)
        {
            EnemyTemplate t = ChapterOne.Template(spec[0]);
            Equal(spec[1], t.name, "敌人名称");
            Equal(int.Parse(spec[2]), t.hp, spec[0] + "生命");
            Equal(spec[3], string.Join(",", t.actions), spec[0] + "行动循环");
        }
        bool missing = false;
        try { ChapterOne.Template("unknown"); } catch (KeyNotFoundException) { missing = true; }
        Check(missing, "未知敌人模板不存在");
        for (int e = 0; e < 5; e++)
        {
            EventDef d = ChapterOne.Event(e);
            Equal(Join(EventDeltas[e]), Join(new[] { d.safeDelta, d.critDelta, d.successDelta, d.failDelta, d.fumbleDelta }), "事件" + e + "数值");
            Check(new[] { d.safeLabel, d.riskLabel, d.safeText, d.critText, d.successText, d.failText, d.fumbleText }.All(x => !string.IsNullOrEmpty(x)), "事件文本完整");
        }
    }

    private static void InitialState()
    {
        Equal(2, GameSession.SaveVersion, "存档版本常量");
        GameSession session = GameSession.New(0);
        GameState s = session.Data.state;
        Equal(2, session.Data.version, "新会话存档版本");
        Equal(0x6D2B79F5u, s.rngState, "零种子规范化");
        Equal(5u, GameSession.New(5).Data.state.rngState, "非零种子原样");
        Equal(0, s.nodeIndex, "初始节点");
        Equal("story", s.phase, "初始阶段");
        Equal(100, s.hp, "初始生命"); Equal(100, s.maxHp, "生命上限");
        Check(s.shield == 0 && s.turn == 0 && s.rollsLeft == 0 && s.pendingFace == -1 && s.pendingSkill == "" &&
            s.enemies.Length == 0 && !s.supplyClaimed && s.battleRetries == 0 && session.Data.battleCheckpoint == null, "初始无战斗数据");
        Check(s.claimedSupplies.Count == 0 && s.upgradedNodes.Count == 0, "初始无补给与强化记录");
        Check(s.choices.Length == 50 && s.choices.All(x => x == -1) && s.eventRolls.Length == 50 && s.eventRolls.All(x => x == -1), "选择与事件记录50格全为-1");
        Equal(8, s.sword, "剑8"); Equal(6, s.shieldPower, "盾6"); Equal(8, s.heal, "心8"); Equal(11, s.shot, "枪击11");
        Equal("C1-01-01", session.CurrentNode.id, "当前节点");
        Equal(0, session.CollectedEvidence().Count, "初始无证据");
        Equal(Save(session.Data), Save(RoundTrip(session).Data), "初始存档精确往返");
        Invalid(session, delegate { session.Roll(); });
        Invalid(session, delegate { session.EndTurn(); });
        Invalid(session, delegate { session.ChooseTarget(1); });
        Invalid(session, delegate { session.ClaimSupply(); });
        Invalid(session, delegate { session.Upgrade("sword"); });
        Invalid(session, delegate { session.ResolveEvent(true); });
        Invalid(session, delegate { session.ResetBattle(); });
        Invalid(session, delegate { session.Advance(1); });
        Invalid(session, delegate { session.Advance(-1); });
        Invalid(session, delegate { session.CurrentEventDelta(); });
        Invalid(session, delegate { session.CurrentEventText(); });
        Equal("准备", GameSession.DescribeIntent("wait"), "意图描述wait");
        Equal("蓄力（下次重击）", GameSession.DescribeIntent("charge"), "意图描述charge");
        Equal("攻击 13", GameSession.DescribeIntent("attack:13"), "意图描述attack");
        Equal("护盾 +8", GameSession.DescribeIntent("shield:8"), "意图描述shield");
        Equal("剑", GameSession.SkillName("sword")); Equal("盾", GameSession.SkillName("shield"));
        Equal("心", GameSession.SkillName("heal")); Equal("枪击", GameSession.SkillName("shot"));
        session.Advance();
        Equal("choice", s.phase, "第二节点为选择");
    }

    private static void Equal(string expected, string actual) { Equal(expected, actual, "技能名称"); }

    private static void DiceLayout()
    {
        int[] counts = new int[10];
        bool sameAsReference = true;
        for (uint seed = 1; seed <= 10000; seed++)
        {
            GameSession session = GameSession.New(seed);
            session.Advance(); session.Advance();
            GameState s = session.Data.state;
            uint reference = seed;
            int expected = (int)Bounded(ref reference, 10);
            int face = session.Roll();
            sameAsReference &= face == expected && s.rngState == reference && s.rollsLeft == 2;
            counts[face]++;
            if (face < 4) sameAsReference &= s.pendingSkill == "sword" && s.pendingFace == face;
            else if (face < 7) sameAsReference &= s.shield == 6 && s.pendingFace == -1;
            else if (face < 9) sameAsReference &= s.hp == 100 && s.pendingFace == -1 && s.shield == 0;
            else sameAsReference &= s.pendingSkill == "shot" && s.pendingFace == 9;
        }
        Check(sameAsReference, "一万种子：骰面、随机状态与布局（0-3剑、4-6盾、7-8心、9枪击）与参考采样一致");
        foreach (int count in counts) Check(count > 850 && count < 1150, "各骰面均匀覆盖：" + count);
        for (int face = 0; face < 10; face++)
        {
            GameSession battle = AtNode(2);
            ForceFace(battle, face);
            string skill = battle.Data.state.pendingSkill;
            Equal(face < 4 ? "sword" : face == 9 ? "shot" : "", skill, "骰面" + face + "技能");
            uint state = SeedFor(10, face);
            Equal((uint)face, Bounded(ref state, 10), "搜索种子与逆推一致");
        }
        uint rejecting = SeedProducing(1);
        Equal(1u, Next(rejecting), "构造会被拒绝的随机输出");
        GameSession dice = AtNode(2);
        dice.Data.state.rngState = rejecting;
        Equal((int)(Next(1) % 10), dice.Roll(), "十面骰拒绝低于6的随机输出");
        Equal(Next(1), dice.Data.state.rngState, "拒绝采样推进两次随机状态");
        GameSession boundary = AtNode(2);
        boundary.Data.state.rngState = SeedProducing(6);
        Equal(6, boundary.Roll(), "输出6恰在阈值上被接受");
        boundary.Data.state.rngState = SeedProducing(5);
        boundary.Roll();
        Equal(Next(5), boundary.Data.state.rngState, "输出5被拒绝");
        GameSession eventSession = AtNode(4);
        eventSession.Data.state.rngState = rejecting;
        eventSession.ResolveEvent(true);
        Equal((int)(Next(1) % 20) + 1, eventSession.Data.state.eventRolls[4], "D20拒绝低于16的随机输出");
        Equal(Next(1), eventSession.Data.state.rngState, "D20拒绝采样随机状态");
        GameSession d20 = AtNode(4);
        d20.Data.state.rngState = SeedProducing(16);
        d20.ResolveEvent(true);
        Equal(17, d20.Data.state.eventRolls[4], "D20输出16恰在阈值上被接受");
        d20 = AtNode(4);
        d20.Data.state.rngState = SeedProducing(15);
        d20.ResolveEvent(true);
        Equal(Next(15), d20.Data.state.rngState, "D20输出15被拒绝");
    }

    // —— 3. 伤害与护盾 ——
    private static void TargetDamage()
    {
        GameSession session = AtNode(2);
        ForceFace(session, 3);
        Equal(3, session.Data.state.pendingFace, "保留真实剑面索引");
        Equal("sword", session.Data.state.pendingSkill, "待选剑");
        Equal(2, session.Data.state.rollsLeft, "待选技能已扣一次投掷");
        Invalid(session, delegate { session.Roll(); });
        Invalid(session, delegate { session.EndTurn(); });
        Invalid(session, delegate { session.ChooseTarget(99); });
        Invalid(session, delegate { session.ChooseTarget(0); });
        Invalid(session, delegate { session.ChooseTarget(2); });
        Invalid(session, delegate { session.Advance(); });
        Invalid(session, delegate { session.ClaimSupply(); });
        Invalid(session, delegate { session.ResolveEvent(false); });
        Invalid(session, delegate { session.Upgrade("sword"); });
        Invalid(session, delegate { session.ResetBattle(); });
        session.ChooseTarget(1);
        Equal(16, session.Data.state.enemies[0].hp, "剑伤害8");
        Check(session.Data.state.pendingFace == -1 && session.Data.state.pendingSkill == "", "选目标后清理待选");
        Invalid(session, delegate { session.ChooseTarget(1); });
        ForceFace(session, 9); session.ChooseTarget(1);
        Equal(5, session.Data.state.enemies[0].hp, "枪击伤害11");
        Equal(Save(session.Data), Save(RoundTrip(session).Data), "受伤敌人存档往返");
        session.Data.state.shield = 1000;
        ForceFace(session, 0);
        session.ChooseTarget(1);
        GameState s = session.Data.state;
        Equal(3, s.nodeIndex, "胜利进入下一节点");
        Equal("supply", s.phase, "战后为补给");
        Check(s.shield == 0 && s.enemies.Length == 0 && s.pendingFace == -1 && s.turn == 0 && s.rollsLeft == 0 &&
            s.battleRetries == 0 && session.Data.battleCheckpoint == null, "胜利清理战斗状态与护盾");
        Check(s.logs.Any(l => l.Contains("剩余0生命")), "过量伤害后敌人生命为0而非负数");
        Invalid(session, delegate { session.ChooseTarget(1); });
        Invalid(session, delegate { session.Roll(); });

        // 敌人护盾：术式安保首个行动为护盾8。
        GameSession mage = AtNode(17);
        mage.Data.state.hp = 100;
        Equal("shield:8", mage.Data.state.enemies[0].intent, "术式安保首个意图");
        mage.EndTurn();
        EnemyState m = mage.Data.state.enemies[0];
        Equal(8, m.shield, "术式安保获得护盾8");
        ForceFace(mage, 0); mage.ChooseTarget(1);
        m = mage.Data.state.enemies[0];
        Equal(0, m.shield, "剑8被护盾完全吸收");
        Equal(36, m.hp, "护盾完全吸收时生命不变");
        mage.Data.state.enemies[0].shield = 5;
        ForceFace(mage, 9); mage.ChooseTarget(1);
        m = mage.Data.state.enemies[0];
        Equal(0, m.shield, "护盾部分吸收后清空");
        Equal(30, m.hp, "枪击11被吸收5后造成6");
        mage.Data.state.enemies[0].shield = 20;
        ForceFace(mage, 1); mage.ChooseTarget(1);
        m = mage.Data.state.enemies[0];
        Equal(12, m.shield, "护盾大于伤害时剩余12");
        Equal(30, m.hp, "大护盾不掉血");
        Equal(Save(mage.Data), Save(RoundTrip(mage).Data), "敌人护盾存档往返");
        mage.EndTurn();
        Equal(12, mage.Data.state.enemies[0].shield, "敌人护盾跨回合保留");
        ForceFace(mage, 9); mage.ChooseTarget(2);
        Equal(13, mage.Data.state.enemies[1].hp, "无护盾巡检直接受伤");
    }

    private static void ShieldAndHeal()
    {
        GameSession session = AtNode(2);
        GameState s = session.Data.state;
        s.hp = 90;
        ForceFace(session, 4);
        Equal(6, s.shield, "盾立即+6");
        Equal(-1, s.pendingFace, "盾无需选目标");
        session.EndTurn();
        Equal(83, s.hp, "护盾6吸收后承受7");
        Equal(0, s.shield, "新回合护盾清零");
        ForceFace(session, 5); ForceFace(session, 6); ForceFace(session, 4);
        Equal(18, s.shield, "三个盾面叠加");
        session.EndTurn();
        Equal(83, s.hp, "护盾完全吸收攻击13");
        Equal(0, s.shield, "剩余护盾5在新回合清零而不保留");
        ForceFace(session, 4); ForceFace(session, 4);
        session.EndTurn();
        Equal(82, s.hp, "护盾12吸收后承受1");
        Equal(0, s.shield, "护盾不会负数并清零");
        ForceFace(session, 7);
        Equal(90, s.hp, "心恢复8");
        ForceFace(session, 8);
        Equal(98, s.hp, "第二个心面恢复8");
        ForceFace(session, 7);
        Equal(100, s.hp, "治疗不超过最大生命");
        session.EndTurn();
        ForceFace(session, 8);
        Equal(95, s.hp, "满血以下正常治疗");
        s.shield = int.MaxValue - 2;
        ForceFace(session, 4);
        Equal(int.MaxValue, s.shield, "护盾表示边界不会溢出");
        Equal(Save(session.Data), Save(RoundTrip(session).Data), "大护盾允许存档恢复");
        session.EndTurn();
        Equal(95, s.hp, "大护盾吸收攻击");
        Equal(0, s.shield, "大护盾也在新回合清零");

        // 多名敌人依次攻击，玩家护盾先吸收。
        GameSession multi = AtNode(8);
        GameState m = multi.Data.state;
        m.hp = 100;
        ForceFace(multi, 4); ForceFace(multi, 4); ForceFace(multi, 4);
        multi.EndTurn();
        Equal(89, m.hp, "护盾18：巡检13全吸收，安保16吸收5承受11");
        Equal(0, m.shield, "多敌回合后护盾清零");
    }

    private static void TurnRules()
    {
        GameSession session = AtNode(2);
        GameState s = session.Data.state;
        Equal(100, s.hp, "首战前满血");
        Equal(1, s.turn, "首回合");
        Equal(3, s.rollsLeft, "首轮3投");
        ForceFace(session, 7); ForceFace(session, 7); ForceFace(session, 7);
        Equal(0, s.rollsLeft, "恰好三投");
        Invalid(session, delegate { session.Roll(); });
        Invalid(session, delegate { session.Advance(); });
        Invalid(session, delegate { session.ResolveEvent(false); });
        Invalid(session, delegate { session.Upgrade("sword"); });
        Invalid(session, delegate { session.ResetBattle(); });
        Invalid(session, delegate { session.ClaimSupply(); });
        Invalid(session, delegate { session.ChooseTarget(1); });
        session.EndTurn();
        Equal(2, s.turn, "敌方行动后新回合");
        Equal(3, s.rollsLeft, "新回合恢复三投");
        Equal(87, s.hp, "巡检伤害13");
        session.EndTurn();
        Equal(3, s.turn, "允许零投提前结束");
        Equal(74, s.hp, "提前结束仍结算攻击");
        ForceFace(session, 7);
        Equal(2, s.rollsLeft, "一投后剩2");
        session.EndTurn();
        Equal(4, s.turn, "一投后提前结束");
        Equal(69, s.hp, "治疗8后承受13");
        ForceFace(session, 0);
        Invalid(session, delegate { session.EndTurn(); });
        Invalid(session, delegate { session.Roll(); });
        session.ChooseTarget(1);
        session.EndTurn();
        Equal(5, s.turn, "清理待选后可结束");
        Equal(Save(session.Data), Save(RoundTrip(session).Data), "多回合后存档往返");
    }

    private static void VictoryAndDefeat()
    {
        GameSession session = AtNode(8);
        GameState s = session.Data.state;
        s.hp = 100;
        Equal(2, s.enemies.Length, "双目标");
        Check(s.enemies[0].id == 1 && s.enemies[1].id == 2, "目标ID按顺序");
        Check(s.enemies[0].name == "巡检机" && s.enemies[1].name == "安保员", "不同种类不加后缀");
        ForceFace(session, 9); session.ChooseTarget(1);
        ForceFace(session, 9); session.ChooseTarget(1);
        Equal(2, s.enemies[0].hp, "巡检剩2");
        ForceFace(session, 0);
        session.ChooseTarget(1);
        Equal(0, s.enemies[0].hp, "首目标死亡生命归零");
        Equal("battle", s.phase, "仍有敌人存活");
        Equal(0, s.rollsLeft, "三投用完");
        session.EndTurn();
        Equal(84, s.hp, "死亡巡检不再攻击，仅安保16");
        Equal(0, s.enemies[0].actionIndex, "死亡敌人不推进行动");
        Equal(1, s.enemies[1].actionIndex, "存活敌人推进行动");
        Equal("charge", s.enemies[1].intent, "安保下回合蓄力");
        ForceFace(session, 0);
        Invalid(session, delegate { session.ChooseTarget(1); });
        session.ChooseTarget(2);
        Equal(30, s.enemies[1].hp, "剑击安保");
        Equal(Save(session.Data), Save(RoundTrip(session).Data), "含死亡敌人可以恢复");
        ClearBattle(session);
        Equal(9, session.Data.state.nodeIndex, "全部击败进入节点9");

        // 第一名敌人即击倒玩家：后续敌人不行动。
        GameSession defeat = AtNode(8);
        GameState d = defeat.Data.state;
        d.hp = 10;
        ForceFace(defeat, 7);
        Equal(10 + d.heal, d.hp, "快照路线强化后的治疗");
        d.hp = 10;
        defeat.EndTurn();
        Equal("defeat", d.phase, "失败阶段");
        Equal(0, d.hp, "生命下限0");
        Check(d.shield == 0 && d.rollsLeft == 0 && d.pendingFace == -1, "失败清理护盾与投掷");
        Equal(1, d.turn, "失败不进入新回合");
        Equal(1, d.enemies[0].actionIndex, "击倒玩家的巡检已行动");
        Equal(0, d.enemies[1].actionIndex, "后续安保未行动");
        Equal("attack:16", d.enemies[1].intent, "安保意图保持");
        Equal(Save(defeat.Data), Save(RoundTrip(defeat).Data), "失败状态精确往返");
        Invalid(defeat, delegate { defeat.Roll(); });
        Invalid(defeat, delegate { defeat.EndTurn(); });
        Invalid(defeat, delegate { defeat.ChooseTarget(1); });
        Invalid(defeat, delegate { defeat.Advance(); });
        Invalid(defeat, delegate { defeat.ClaimSupply(); });
        Invalid(defeat, delegate { defeat.ResolveEvent(true); });

        // 护盾先吸收第一击，第二名敌人击倒玩家。
        GameSession second = AtNode(8);
        GameState t = second.Data.state;
        t.hp = 20;
        ForceFace(second, 4);
        second.EndTurn();
        Equal("defeat", t.phase, "第二名敌人击倒");
        Check(t.enemies[0].actionIndex == 1 && t.enemies[1].actionIndex == 1, "两名敌人均已行动");
        Equal(0, t.shield, "失败时护盾清零");
        Equal(Save(second.Data), Save(RoundTrip(second).Data), "两敌均行动的失败状态往返");

        // 同类双敌命名。
        GameSession twins = AtNode(31);
        Check(twins.Data.state.enemies[0].name == "巡检机A" && twins.Data.state.enemies[1].name == "巡检机B", "同类敌人加A/B后缀");
    }

    // —— 4. 敌人行动循环 ——
    private static void EnemySchedules()
    {
        for (int b = 0; b < BattleNodes.Length; b++)
        {
            GameSession session = AtNode(BattleNodes[b]);
            string[] kinds = BattleEnemies[b].Split(',');
            GameState s = session.Data.state;
            Equal(kinds.Length, s.enemies.Length, "敌人数量");
            for (int i = 0; i < kinds.Length; i++)
            {
                EnemyState e = s.enemies[i];
                string[] spec = Templates.First(t => t[0] == kinds[i]);
                int same = kinds.Count(k => k == kinds[i]);
                int order = kinds.Take(i).Count(k => k == kinds[i]);
                Equal(same > 1 ? spec[1] + (char)('A' + order) : spec[1], e.name, "敌人名称");
                Check(e.id == i + 1 && e.kind == kinds[i] && e.hp == int.Parse(spec[2]) && e.maxHp == e.hp && e.shield == 0 && e.actionIndex == 0, "敌人初始状态");
            }
            int[] shields = new int[kinds.Length];
            for (int turn = 1; turn <= 9; turn++)
            {
                s = session.Data.state;
                s.hp = 100;
                int damage = 0;
                for (int i = 0; i < kinds.Length; i++)
                {
                    string[] actions = SpecActions(kinds[i]);
                    string expected = actions[(turn - 1) % actions.Length];
                    Equal(expected, s.enemies[i].intent, kinds[i] + "第" + turn + "回合意图");
                    damage += ActionValue(expected, "attack:");
                    shields[i] += ActionValue(expected, "shield:");
                }
                session.EndTurn();
                s = session.Data.state;
                Equal("battle", s.phase, "满血时不会失败");
                Equal(100 - damage, s.hp, "节点" + BattleNodes[b] + "第" + turn + "回合伤害");
                Equal(turn + 1, s.turn, "回合推进");
                Check(s.rollsLeft == 3 && s.shield == 0, "新回合三投与护盾清零");
                for (int i = 0; i < kinds.Length; i++)
                {
                    string[] actions = SpecActions(kinds[i]);
                    Equal(shields[i], s.enemies[i].shield, kinds[i] + "护盾累计");
                    Equal(turn, s.enemies[i].actionIndex, "行动索引");
                    Equal(actions[turn % actions.Length], s.enemies[i].intent, "下一意图");
                }
                session = RoundTrip(session);
            }
        }
        // 抽查关键节奏。
        GameSession binder = AtNode(5);
        binder.Data.state.hp = 100;
        binder.EndTurn(); Equal(100, binder.Data.state.hp, "束缚器先准备");
        binder.EndTurn(); Equal(74, binder.Data.state.hp, "束缚器随后攻击26");
        Check(binder.Data.state.logs.Any(l => l.Contains("准备")), "等待行动写入日志");
        GameSession captain = AtNode(46);
        captain.Data.state.hp = 100;
        captain.EndTurn(); Equal(12, captain.Data.state.enemies[0].shield, "队长先护盾12");
        captain.EndTurn(); Equal(100, captain.Data.state.hp, "队长蓄力无伤害");
        Check(captain.Data.state.logs.Any(l => l.Contains("蓄力")), "蓄力写入日志");
        captain.EndTurn(); Equal(58, captain.Data.state.hp, "蓄力后重击42");
        captain.EndTurn(); Equal(38, captain.Data.state.hp, "随后攻击20");
        captain.EndTurn(); Equal(24, captain.Data.state.enemies[0].shield, "循环回到护盾并累计");
    }

    // —— 选择与证据 ——
    private static void ChoicesAndEvidence()
    {
        GameSession session = AtNode(1);
        Equal("choice", session.Data.state.phase, "节点1为选择");
        Invalid(session, delegate { session.Advance(-1); });
        Invalid(session, delegate { session.Advance(2); });
        Invalid(session, delegate { session.Roll(); });
        Invalid(session, delegate { session.ClaimSupply(); });
        int hp = session.Data.state.hp;
        uint rng = session.Data.state.rngState;
        session.Advance(1);
        GameState s = session.Data.state;
        Equal(1, s.choices[1], "选择存入choices[1]");
        Check(s.logs.Contains(ChapterOne.Node(1).responses[1]), "选择回应写入日志");
        Check(s.hp == hp && s.rngState == rng, "选择不改生命、不消耗随机数");
        Equal("battle", s.phase, "选择后进入战斗");
        Equal(Save(session.Data), Save(RoundTrip(session).Data), "选择记录往返");
        foreach (int node in ChoiceNodes)
        {
            GameSession c = AtNode(node);
            int last = ChapterOne.Node(node).choices.Length - 1;
            Equal(-1, c.Data.state.choices[node], "当前选择尚未记录");
            Invalid(c, delegate { c.Advance(last + 1); });
            c.Advance(last);
            Equal(last, c.Data.state.choices[node], "节点" + node + "选择记录");
            Equal(node + 1, c.Data.state.nodeIndex, "选择后推进");
            c = RoundTrip(c);
            Equal(last, c.Data.state.choices[node], "选择记录跨存档保留");
        }
        GameSession story = AtNode(7);
        Equal(0, story.CollectedEvidence().Count, "停留证据节点时尚未计入");
        Invalid(story, delegate { story.Advance(1); });
        story.Advance();
        Equal("关押记录", string.Join(",", story.CollectedEvidence()), "离开节点7计入关押记录");
        Check(story.Data.state.logs.Contains("取得证据：关押记录。"), "证据日志");
        GameSession transfer = AtNode(20);
        Equal("关押记录", string.Join(",", transfer.CollectedEvidence()), "节点20前一项证据");
        transfer.Advance(1);
        Equal("关押记录,转运记录", string.Join(",", transfer.CollectedEvidence()), "选择节点离开时计入证据");
        Equal(1, transfer.Data.state.choices[20], "证据选择节点记录选项");
        GameSession chain = AtNode(35);
        chain.Advance();
        Equal(string.Join(",", EvidenceNames), string.Join(",", chain.CollectedEvidence()), "三项证据");
        GameSession end = AtNode(49);
        Equal("completed", end.Data.state.phase, "进入ending即完成");
        Equal(string.Join(",", EvidenceNames), string.Join(",", end.CollectedEvidence()), "完成时证据齐全");
        Check(end.Data.state.choices.Where((v, i) => ChapterOne.Node(i).kind == "choice").All(v => v == 0), "路线选择全部记录");
        Invalid(end, delegate { end.Advance(); });
        Invalid(end, delegate { end.ClaimSupply(); });
        Invalid(end, delegate { end.Roll(); });
        Invalid(end, delegate { end.ResolveEvent(false); });
        Equal(Save(end.Data), Save(RoundTrip(end).Data), "完成状态往返");
        GameSession lastChoice = AtNode(48);
        lastChoice.Advance(1);
        Check(lastChoice.Data.state.phase == "completed" && lastChoice.Data.state.nodeIndex == 49, "最后选择进入完成");
    }

    // —— 补给与强化 ——
    private static void SuppliesAndUpgrades()
    {
        GameSession session = AtNode(3);
        GameState s = session.Data.state;
        s.hp = 70;
        Invalid(session, delegate { session.Advance(); });
        Invalid(session, delegate { session.Upgrade("sword"); });
        Check(session.ClaimSupply(), "首次补给成功");
        Equal(80, s.hp, "节点3恢复10");
        Equal("3", Join(s.claimedSupplies), "领取记录");
        Check(s.supplyClaimed, "领取标记");
        string claimed = Save(session.Data);
        Check(!session.ClaimSupply(), "重复补给返回false");
        Equal(claimed, Save(session.Data), "重复领取完全不变");
        session = RoundTrip(session);
        Check(!session.ClaimSupply(), "恢复后仍不可重复领取");
        Invalid(session, delegate { session.Upgrade("sword"); });
        Invalid(session, delegate { session.Advance(1); });
        session.Advance();
        Equal(4, session.Data.state.nodeIndex, "补给后推进");
        Check(!session.Data.state.supplyClaimed, "新节点重置领取标记");
        Equal("3", Join(session.Data.state.claimedSupplies), "领取列表保留");

        GameSession cap = AtNode(3);
        cap.Data.state.hp = 95;
        cap.ClaimSupply();
        Equal(100, cap.Data.state.hp, "补给不超过上限");

        for (int k = 0; k < SupplyNodes.Length; k++)
        {
            GameSession supply = AtNode(SupplyNodes[k]);
            supply.Data.state.hp = 50;
            Equal(Join(SupplyNodes.Where(n => n < SupplyNodes[k])), Join(supply.Data.state.claimedSupplies), "此前补给均已领取");
            supply.ClaimSupply();
            Equal(50 + SupplyHeals[k], supply.Data.state.hp, "节点" + SupplyNodes[k] + "恢复量");
            if (!supply.CurrentNode.reward) Invalid(supply, delegate { supply.Upgrade("shot"); });
            else Invalid(supply, delegate { supply.Advance(); });
        }

        foreach (string skill in Skills)
        {
            GameSession reward = AtNode(6);
            GameState r = reward.Data.state;
            r.hp = 60;
            Invalid(reward, delegate { reward.Upgrade(skill); });
            reward.ClaimSupply();
            Equal(68, r.hp, "节点6恢复8");
            Invalid(reward, delegate { reward.Advance(); });
            Invalid(reward, delegate { reward.Upgrade("unknown"); });
            Invalid(reward, delegate { reward.Upgrade(null); });
            Invalid(reward, delegate { reward.Upgrade(""); });
            Check(!reward.CurrentUpgradeChosen, "尚未强化");
            reward.Upgrade(skill);
            Check(reward.CurrentUpgradeChosen, "已强化");
            Equal(skill == "sword" ? 10 : 8, r.sword, "剑奖励");
            Equal(skill == "shield" ? 8 : 6, r.shieldPower, "盾奖励");
            Equal(skill == "heal" ? 10 : 8, r.heal, "心奖励");
            Equal(skill == "shot" ? 13 : 11, r.shot, "枪击奖励");
            Equal("6", Join(r.upgradedNodes), "强化记录");
            reward = RoundTrip(reward);
            foreach (string other in Skills) Invalid(reward, delegate { reward.Upgrade(other); });
            Check(!reward.ClaimSupply(), "强化不重置领取");
            Invalid(reward, delegate { reward.Advance(1); });
            reward.Advance();
            Equal("story", reward.Data.state.phase, "领取并强化后推进");
            reward.Advance();
            Equal("battle", reward.Data.state.phase, "进入节点8战斗");
            GameState b = reward.Data.state;
            if (skill == "sword") { ForceFace(reward, 0); reward.ChooseTarget(1); Equal(14, b.enemies[0].hp, "强化剑造成10"); }
            else if (skill == "shot") { ForceFace(reward, 9); reward.ChooseTarget(1); Equal(11, b.enemies[0].hp, "强化枪击造成13"); }
            else if (skill == "shield") { ForceFace(reward, 4); Equal(8, b.shield, "强化盾+8"); }
            else { b.hp = 50; ForceFace(reward, 7); Equal(60, b.hp, "强化心恢复10"); }
            Equal(b.sword, reward.Data.battleCheckpoint.sword, "检查点保存强化后数值");
            Equal(Save(reward.Data), Save(RoundTrip(reward).Data), "强化跨节点持久化");
        }
        Equal(8, GameSession.New(777).Data.state.sword, "强化不永久成长");

        GameSession end = AtNode(49);
        Equal(Join(SupplyNodes), Join(end.Data.state.claimedSupplies), "全章12处补给各领取一次");
        Equal(Join(RewardNodes), Join(end.Data.state.upgradedNodes), "全章7次强化");
        Equal(8 + 14, end.Data.state.heal, "7次强化心+14");
        Check(end.Data.state.sword == 8 && end.Data.state.shieldPower == 6 && end.Data.state.shot == 11, "其他技能未变");
    }

    // —— 6. 事件 ——
    private static int ExpectedDelta(int eventIndex, int roll)
    {
        int[] d = EventDeltas[eventIndex];
        if (roll == 0) return d[0];
        if (roll == 20) return d[1];
        if (roll == 1) return d[4];
        return roll >= 12 ? d[2] : d[3];
    }

    private static string ExpectedText(EventDef e, int roll)
    {
        if (roll == 0) return e.safeText;
        if (roll == 20) return e.critText;
        if (roll == 1) return e.fumbleText;
        return roll >= 12 ? e.successText : e.failText;
    }

    private static GameSession ResolveAt(int node, int hp, int roll)
    {
        GameSession session = AtNode(node);
        session.Data.state.hp = hp;
        uint before = session.Data.state.rngState;
        if (roll > 0) SetD20(session, roll);
        session.ResolveEvent(roll > 0);
        Equal(roll, session.Data.state.eventRolls[node], "事件记录指定点数");
        Equal(roll > 0 ? (uint)(roll + 19) : before, session.Data.state.rngState, roll > 0 ? "D20消耗一次随机数" : "安全路线不使用随机数");
        return session;
    }

    private static void EventBranches()
    {
        for (int e = 0; e < EventNodes.Length; e++)
        {
            int node = EventNodes[e];
            Equal(e, ChapterOne.Node(node).eventIndex, "事件节点索引");
            EventDef def = ChapterOne.Event(e);
            for (int roll = 0; roll <= 20; roll++)
            {
                GameSession session = ResolveAt(node, 50, roll);
                int delta = ExpectedDelta(e, roll);
                Equal(50 + delta, session.Data.state.hp, "事件" + e + "点数" + roll + "生命变化");
                Equal("eventResult", session.Data.state.phase, "结果单独保存");
                Equal(delta, session.CurrentEventDelta(), "当前事件变化");
                Equal(ExpectedText(def, roll), session.CurrentEventText(), "当前事件文本");
                Invalid(session, delegate { session.ResolveEvent(true); });
                Invalid(session, delegate { session.ResolveEvent(false); });
                Invalid(session, delegate { session.Advance(1); });
                Invalid(session, delegate { session.Roll(); });
                Equal(Save(session.Data), Save(RoundTrip(session).Data), "所有点数结果均可恢复");
            }
            foreach (int roll in new[] { 0, 1, 2, 11, 12, 20 })
            {
                int delta = ExpectedDelta(e, roll);
                if (delta < 0)
                {
                    Equal(1, ResolveAt(node, 1, roll).Data.state.hp, "事件" + e + "点数" + roll + "：1生命仍保留1");
                    Equal(1, ResolveAt(node, -delta, roll).Data.state.hp, "恰好致死的探索伤害保留1");
                    Equal(1, ResolveAt(node, -delta + 1, roll).Data.state.hp, "差1生命时恰好剩1");
                    Equal(2, ResolveAt(node, -delta + 2, roll).Data.state.hp, "非致死伤害正常扣减");
                }
                else
                {
                    Equal(Math.Min(100, 1 + delta), ResolveAt(node, 1, roll).Data.state.hp, "低生命时正常恢复");
                    Equal(Math.Min(100, 95 + delta), ResolveAt(node, 95, roll).Data.state.hp, "事件恢复截断到上限");
                }
            }
            GameSession advanced = ResolveAt(node, 50, 2);
            advanced.Advance();
            Equal(node + 1, advanced.Data.state.nodeIndex, "事件结果后推进");
            Equal(2, advanced.Data.state.eventRolls[node], "离开后保留点数");
        }
    }

    private static void EventPersistence()
    {
        foreach (int node in new[] { 4, 41 })
        {
            GameSession session = ResolveAt(node, 50, 1);
            string before = Save(session.Data);
            session = RoundTrip(session);
            Equal(before, Save(session.Data), "事件结果完全恢复");
            Invalid(session, delegate { session.ResolveEvent(false); });
            Invalid(session, delegate { session.ResolveEvent(true); });
            int hp = session.Data.state.hp;
            uint rng = session.Data.state.rngState;
            session.Advance();
            Equal(hp, session.Data.state.hp, "推进不再次施加事件效果");
            Equal(rng, session.Data.state.rngState, "推进不重掷事件");
            Equal(1, session.Data.state.eventRolls[node], "结果保留到后续节点");
            session = RoundTrip(session);
            Equal(1, session.Data.state.eventRolls[node], "后续节点存档保留点数");
            GameSession safe = ResolveAt(node, 50, 0);
            safe = RoundTrip(safe);
            Check(safe.Data.state.phase == "eventResult" && safe.Data.state.eventRolls[node] == 0, "安全结果0可恢复");
        }
    }

    private static void Serialization()
    {
        GameSession session = AtNode(2);
        ForceFace(session, 2);
        string json = Save(session.Data);
        Check(json.Contains("\"version\":2"), "JSON写入版本2");
        SessionData deserialized = Read(json);
        string input = Save(deserialized);
        GameSession restored = GameSession.Restore(deserialized);
        Equal(json, Save(restored.Data), "public字段序列化往返");
        Equal(input, Save(deserialized), "恢复不修改输入");
        Equal(2, restored.Data.state.pendingFace, "待选剑面持久化");
        Equal("sword", restored.Data.state.pendingSkill, "待选技能持久化");
        session.ChooseTarget(1); restored.ChooseTarget(1);
        Equal(session.Roll(), restored.Roll(), "恢复后的下一投一致");
        Equal(Save(session.Data), Save(restored.Data), "随机数及战斗结果一致");
        deserialized.state.enemies[0].hp = 1;
        deserialized.state.logs.Add("外部修改");
        deserialized.state.choices[1] = 1;
        deserialized.battleCheckpoint.hp = 1;
        Check(restored.Data.state.enemies[0].hp != 1 && restored.Data.battleCheckpoint.hp != 1 &&
            restored.Data.state.choices[1] == 0 && !restored.Data.state.logs.Contains("外部修改"), "恢复必须深拷贝输入");
        GameSession shot = AtNode(2);
        ForceFace(shot, 9);
        Equal("shot", RoundTrip(shot).Data.state.pendingSkill, "枪击待选往返");
        GameSession eventResult = ResolveAt(13, 50, 20);
        Equal(Save(eventResult.Data), Save(RoundTrip(eventResult).Data), "事件结果往返");
        foreach (int node in Enumerable.Range(0, 50))
        {
            GameSession at = AtNode(node);
            Equal(Save(at.Data), Save(RoundTrip(at).Data), "每个节点入口状态往返：" + node);
        }
    }

    // —— 5. 全章流程 ——
    private static void Step(GameSession session, uint seed)
    {
        GameState s = session.Data.state;
        NodeDef node = session.CurrentNode;
        if (s.phase == "story" || s.phase == "eventResult") session.Advance();
        else if (s.phase == "choice") session.Advance((int)((seed + (uint)s.nodeIndex) % (uint)node.choices.Length));
        else if (s.phase == "event") session.ResolveEvent((seed + (uint)s.nodeIndex) % 3 != 0);
        else if (s.phase == "supply")
        {
            if (!s.supplyClaimed) session.ClaimSupply();
            else if (node.reward && !session.CurrentUpgradeChosen) session.Upgrade(Skills[(seed + (uint)s.upgradedNodes.Count) % 4]);
            else session.Advance();
        }
        else if (s.phase == "defeat") session.ResetBattle();
        else if (s.pendingFace != -1) session.ChooseTarget(FirstAlive(s));
        else if (s.rollsLeft == 0) session.EndTurn();
        else session.Roll();
    }

    private static void FixedSeedReplay()
    {
        GameSession first = GameSession.New(20261015);
        GameSession second = GameSession.New(20261015);
        for (int i = 0; first.Data.state.phase != "completed" && i < 20000; i++)
        {
            Step(first, 20261015); Step(second, 20261015);
            Equal(Save(first.Data), Save(second.Data), "固定种子逐步重放一致");
            if (i % 7 == 0) second = RoundTrip(second);
        }
        Equal("completed", first.Data.state.phase, "固定种子完整通关");
        Equal(Save(first.Data), Save(second.Data), "存档恢复不破坏重放");
    }

    // 验证从失败重试：回到检查点（生命、奖励、敌人），重试次数+1，随机状态按检查点与次数确定地洗牌。
    private static GameSession VerifyReset(GameSession session)
    {
        GameState checkpoint = session.Data.battleCheckpoint;
        string checkpointJson = Json(checkpoint);
        int retries = session.Data.state.battleRetries;
        GameSession twin = GameSession.Restore(Read(Save(session.Data)));
        session.ResetBattle();
        twin.ResetBattle();
        Equal(Save(session.Data), Save(twin.Data), "同一检查点同一重试次数结果确定");
        GameState s = session.Data.state;
        Equal("battle", s.phase, "重试回到战斗");
        Equal(retries + 1, s.battleRetries, "重试次数递增");
        Equal(MixSeed(checkpoint.rngState, (uint)(retries + 1)), s.rngState, "随机状态按检查点与次数洗牌");
        Check(s.rngState != checkpoint.rngState, "重试后随机状态改变");
        Equal(checkpoint.hp, s.hp, "生命回到检查点");
        Check(s.sword == checkpoint.sword && s.shieldPower == checkpoint.shieldPower && s.heal == checkpoint.heal && s.shot == checkpoint.shot &&
            Join(s.claimedSupplies) == Join(checkpoint.claimedSupplies) && Join(s.upgradedNodes) == Join(checkpoint.upgradedNodes), "奖励回到检查点");
        Equal(checkpointJson, Json(session.Data.battleCheckpoint), "重试不修改检查点");
        GameState normalized = GameSession.Clone(s);
        normalized.battleRetries = 0;
        normalized.rngState = checkpoint.rngState;
        normalized.logs = new List<string>(checkpoint.logs);
        Equal(checkpointJson, Json(normalized), "除次数、随机状态与日志外精确等于检查点");
        Check(s.logs[s.logs.Count - 1].Contains("第" + (retries + 1) + "次"), "重试日志");
        Equal(Save(session.Data), Save(RoundTrip(session).Data), "重试后存档往返");
        return session;
    }

    private static void CheckpointRetry()
    {
        foreach (int index in BattleNodes)
        {
            GameSession session = AtNode(index);
            string checkpoint = Json(session.Data.battleCheckpoint);
            Equal(checkpoint, Json(session.Data.state), "检查点等于战斗起始状态");
            Invalid(session, delegate { session.ResetBattle(); });
            ForceFace(session, 9); session.ChooseTarget(1);
            ForceFace(session, 4);
            DefeatNow(session);
            Equal(0, session.Data.state.hp, "失败生命为0");
            session = RoundTrip(session);
            GameSession other = AtNode(index);
            DefeatNow(other);
            session = VerifyReset(session);
            uint firstRetryRng = session.Data.state.rngState;
            other = VerifyReset(other);
            Equal(Save(session.Data), Save(other.Data), "不同失败过程在同一重试次数下结果相同");
            Invalid(session, delegate { session.ResetBattle(); });
            ForceFace(session, 9); session.ChooseTarget(1);
            DefeatNow(session);
            session = VerifyReset(session);
            Equal(2, session.Data.state.battleRetries, "第二次重试");
            Check(session.Data.state.rngState != firstRetryRng, "每次重试使用不同洗牌");
            ClearBattle(session);
            Equal(index + 1, session.Data.state.nodeIndex, "重试后胜利进入补给");
            Check(session.Data.state.battleRetries == 0 && session.Data.battleCheckpoint == null, "胜利后清空重试次数与检查点");
        }
        GameSession limit = AtNode(2);
        DefeatNow(limit);
        limit.Data.state.battleRetries = int.MaxValue;
        limit = RoundTrip(limit);
        Invalid(limit, delegate { limit.ResetBattle(); });
        limit.Data.state.battleRetries = int.MaxValue - 1;
        limit.ResetBattle();
        Equal(int.MaxValue, limit.Data.state.battleRetries, "重试次数到上限仍合法");
        Equal(Save(limit.Data), Save(RoundTrip(limit).Data), "上限重试次数可存档");
    }

    // —— 7. 非法存档 ——
    private static void InvalidSaves()
    {
        RejectSave(null);
        SessionData fresh = AtNode(0).Data;
        GameState checkpoint = AtNode(2).Data.battleCheckpoint;
        RejectAll(fresh, "初始节点",
            d => d.version = 0,
            d => d.version = 1,
            d => d.version = 3,
            d => d.state = null,
            d => d.state.rngState = 0,
            d => d.state.nodeIndex = -1,
            d => d.state.nodeIndex = 50,
            d => d.state.phase = null,
            d => d.state.phase = "unknown",
            d => d.state.phase = "choice",
            d => d.state.phase = "battle",
            d => d.state.phase = "defeat",
            d => d.state.phase = "supply",
            d => d.state.phase = "event",
            d => d.state.phase = "eventResult",
            d => d.state.phase = "completed",
            d => d.state.hp = -1,
            d => d.state.hp = 0,
            d => d.state.hp = 101,
            d => d.state.maxHp = 101,
            d => d.state.maxHp = 99,
            d => d.state.shield = -1,
            d => d.state.shield = 1,
            d => d.state.turn = 1,
            d => d.state.turn = -1,
            d => d.state.rollsLeft = 1,
            d => d.state.pendingFace = 0,
            d => { d.state.pendingFace = 0; d.state.pendingSkill = "sword"; },
            d => d.state.pendingSkill = null,
            d => d.state.pendingSkill = "sword",
            d => d.state.enemies = null,
            d => d.state.enemies = GameSession.Clone(AtNode(2).Data).state.enemies,
            d => d.state.logs = null,
            d => d.state.logs.Add(null),
            d => d.state.logs = new List<string>(Enumerable.Repeat("日志", 13)),
            d => d.state.claimedSupplies = null,
            d => d.state.claimedSupplies.Add(3),
            d => d.state.upgradedNodes = null,
            d => d.state.upgradedNodes.Add(6),
            d => { d.state.upgradedNodes.Add(6); d.state.sword += 2; },
            d => d.state.supplyClaimed = true,
            d => d.state.choices = null,
            d => d.state.choices = Enumerable.Repeat(-1, 49).ToArray(),
            d => d.state.choices = Enumerable.Repeat(-1, 51).ToArray(),
            d => d.state.choices[1] = 0,
            d => d.state.choices[0] = 0,
            d => d.state.choices[1] = -2,
            d => d.state.eventRolls = null,
            d => d.state.eventRolls = Enumerable.Repeat(-1, 51).ToArray(),
            d => d.state.eventRolls[4] = 0,
            d => d.state.eventRolls[0] = 0,
            d => d.state.sword = 10,
            d => d.state.sword = 9,
            d => d.state.sword = 7,
            d => d.state.shot = 13,
            d => d.state.shieldPower = 8,
            d => d.state.heal = 24,
            d => d.state.battleRetries = 1,
            d => d.state.battleRetries = -1,
            d => d.battleCheckpoint = GameSession.Clone(checkpoint));

        RejectAll(AtNode(1).Data, "选择节点",
            d => d.state.phase = "story",
            d => d.state.choices[1] = 0,
            d => d.state.choices[1] = 1);
        RejectAll(AtNode(3).Data, "首个补给",
            d => d.state.phase = "story",
            d => d.state.phase = "battle",
            d => d.state.choices[1] = -1,
            d => d.state.choices[1] = 2,
            d => d.state.choices[2] = 0,
            d => d.state.enemies = GameSession.Clone(AtNode(2).Data).state.enemies,
            d => d.state.shield = 1,
            d => d.state.turn = 1,
            d => d.state.rollsLeft = 3,
            d => { d.state.pendingFace = 9; d.state.pendingSkill = "shot"; },
            d => d.state.battleRetries = 1,
            d => d.battleCheckpoint = GameSession.Clone(checkpoint),
            d => d.state.claimedSupplies.Add(3),
            d => d.state.supplyClaimed = true,
            d => { d.state.supplyClaimed = true; d.state.claimedSupplies.Add(6); },
            d => d.state.upgradedNodes.Add(3));
        RejectAll(AtNode(4).Data, "事件节点",
            d => d.state.phase = "story",
            d => d.state.phase = "supply",
            d => d.state.eventRolls[4] = 5,
            d => d.state.eventRolls[4] = 0,
            d => d.state.phase = "eventResult",
            d => d.state.eventRolls[13] = 3);
        RejectAll(ResolveAt(4, 50, 12).Data, "事件结果",
            d => d.state.eventRolls[4] = -1,
            d => d.state.eventRolls[4] = 21,
            d => d.state.eventRolls[4] = -2,
            d => d.state.phase = "event",
            d => d.state.supplyClaimed = true);
        RejectAll(AtNode(5).Data, "事件之后",
            d => d.state.eventRolls[4] = -1,
            d => d.state.eventRolls[4] = 21,
            d => d.state.eventRolls[3] = 0);

        GameSession midReward = AtNode(6);
        midReward.ClaimSupply();
        RejectAll(midReward.Data, "奖励补给已领取未强化",
            d => d.state.upgradedNodes.Add(6),
            d => { d.state.upgradedNodes.Add(6); d.state.sword += 2; d.state.upgradedNodes.Add(6); },
            d => d.state.supplyClaimed = false,
            d => d.state.claimedSupplies.Remove(6),
            d => d.state.claimedSupplies.Add(6),
            d => d.state.sword += 2);
        RejectAll(AtNode(6).Data, "奖励补给未领取",
            d => { d.state.upgradedNodes.Add(6); d.state.heal += 2; },
            d => d.state.claimedSupplies.Add(6));
        RejectAll(AtNode(7).Data, "奖励补给之后",
            d => d.state.claimedSupplies.Remove(6),
            d => d.state.claimedSupplies.Remove(3),
            d => d.state.claimedSupplies.Add(9),
            d => d.state.claimedSupplies.Reverse(),
            d => d.state.upgradedNodes.Clear(),
            d => { d.state.upgradedNodes.Clear(); d.state.heal -= 2; },
            d => d.state.upgradedNodes.Add(6),
            d => d.state.upgradedNodes[0] = 3,
            d => d.state.heal += 2,
            d => d.state.heal = 9,
            d => d.state.supplyClaimed = true,
            d => d.state.phase = "supply");
        RejectAll(AtNode(48).Data, "最后选择",
            d => d.state.phase = "completed",
            d => d.state.upgradedNodes.RemoveAt(6),
            d => { d.state.upgradedNodes.RemoveAt(6); d.state.heal -= 2; },
            d => d.state.heal = 24);
        RejectAll(AtNode(49).Data, "完成状态",
            d => d.state.phase = "story",
            d => d.state.phase = "choice",
            d => d.state.choices[48] = -1,
            d => d.state.choices[48] = 2,
            d => d.state.eventRolls[41] = -1,
            d => d.state.claimedSupplies.RemoveAt(11),
            d => d.state.supplyClaimed = true,
            d => d.state.enemies = GameSession.Clone(AtNode(46).Data).state.enemies);
        // 合法但不常见：强化分配到其他技能仍然被接受（只校验总数）。
        SessionData redistributed = GameSession.Clone(AtNode(7).Data);
        redistributed.state.heal -= 2; redistributed.state.shot += 2;
        Equal(Save(redistributed), Save(GameSession.Restore(redistributed).Data), "强化总额一致的其他分配合法");
    }

    private static void InvalidBattleSaves()
    {
        RejectAll(AtNode(2).Data, "首战",
            d => d.state.turn = 0,
            d => d.state.rollsLeft = -1,
            d => d.state.rollsLeft = 4,
            d => d.state.shield = -1,
            d => d.state.hp = 0,
            d => d.state.hp = 101,
            d => d.state.phase = "story",
            d => d.state.phase = "defeat",
            d => d.state.enemies = new EnemyState[0],
            d => d.state.enemies = null,
            d => d.state.enemies[0] = null,
            d => d.state.enemies = new[] { d.state.enemies[0], GameSession.Clone(d.state.enemies[0]) },
            d => d.state.enemies[0].id = 2,
            d => d.state.enemies[0].kind = "security",
            d => d.state.enemies[0].kind = "unknown",
            d => d.state.enemies[0].name = "未知",
            d => d.state.enemies[0].maxHp = 25,
            d => d.state.enemies[0].hp = 25,
            d => d.state.enemies[0].hp = -1,
            d => d.state.enemies[0].hp = 0,
            d => d.state.enemies[0].shield = -1,
            d => d.state.enemies[0].actionIndex = -1,
            d => d.state.enemies[0].actionIndex = 1,
            d => d.state.enemies[0].intent = "wait",
            d => d.state.enemies[0].intent = null,
            d => { d.state.pendingFace = 4; d.state.pendingSkill = "shield"; d.state.rollsLeft = 2; },
            d => { d.state.pendingFace = 9; d.state.pendingSkill = "sword"; d.state.rollsLeft = 2; },
            d => { d.state.pendingFace = 0; d.state.pendingSkill = "shot"; d.state.rollsLeft = 2; },
            d => { d.state.pendingFace = 10; d.state.pendingSkill = "shot"; d.state.rollsLeft = 2; },
            d => { d.state.pendingFace = 0; d.state.pendingSkill = "sword"; },
            d => { d.state.pendingFace = 0; d.state.pendingSkill = ""; d.state.rollsLeft = 2; },
            d => d.state.pendingSkill = "sword",
            d => d.state.battleRetries = -1,
            d => d.state.supplyClaimed = true,
            d => { d.state.choices[1] = -1; d.battleCheckpoint.choices[1] = -1; },
            d => { d.state.claimedSupplies.Add(3); d.battleCheckpoint.claimedSupplies.Add(3); },
            d => d.battleCheckpoint = null,
            d => d.battleCheckpoint.nodeIndex = 5,
            d => d.battleCheckpoint.phase = "defeat",
            d => d.battleCheckpoint.phase = "supply",
            d => d.battleCheckpoint.rngState = 0,
            d => d.battleCheckpoint.hp = 0,
            d => d.battleCheckpoint.maxHp = 99,
            d => d.battleCheckpoint.shield = 1,
            d => d.battleCheckpoint.turn = 2,
            d => d.battleCheckpoint.rollsLeft = 2,
            d => d.battleCheckpoint.enemies[0].hp = 23,
            d => d.battleCheckpoint.enemies[0].shield = 1,
            d => { d.battleCheckpoint.enemies[0].actionIndex = 1; },
            d => d.battleCheckpoint.enemies = new EnemyState[0],
            d => { d.battleCheckpoint.rollsLeft = 2; d.battleCheckpoint.pendingFace = 0; d.battleCheckpoint.pendingSkill = "sword"; },
            d => d.battleCheckpoint.battleRetries = 1,
            d => d.battleCheckpoint.choices[1] = 1,
            d => d.battleCheckpoint.logs = null);

        RejectAll(AtNode(8).Data, "强化后的双敌战斗",
            d => d.state.enemies[1] = GameSession.Clone(d.state.enemies[0]),
            d => d.state.enemies = new[] { d.state.enemies[1], d.state.enemies[0] },
            d => { d.battleCheckpoint.heal = 8; d.battleCheckpoint.sword = 10; },
            d => { d.battleCheckpoint.upgradedNodes.Clear(); d.battleCheckpoint.heal = 8; },
            d => d.battleCheckpoint.eventRolls[4] = 5,
            d => d.battleCheckpoint.choices[1] = 1,
            d => d.battleCheckpoint.claimedSupplies.Reverse(),
            d => d.battleCheckpoint.nodeIndex = 2);
        RejectAll(AtNode(31).Data, "同类双敌",
            d => { string name = d.state.enemies[0].name; d.state.enemies[0].name = d.state.enemies[1].name; d.state.enemies[1].name = name; });

        GameSession defeat = AtNode(8);
        defeat.Data.state.hp = 10;
        defeat.EndTurn();
        Equal("defeat", defeat.Data.state.phase, "构造失败基准");
        RejectAll(defeat.Data, "失败状态",
            d => d.state.hp = 1,
            d => d.state.phase = "battle",
            d => d.state.rollsLeft = 1,
            d => d.state.shield = 1,
            d => { d.state.pendingFace = 0; d.state.pendingSkill = "sword"; },
            d => { d.state.enemies[0].actionIndex = 0; d.state.enemies[0].intent = "attack:13"; },
            d => { d.state.enemies[0].actionIndex = 0; d.state.enemies[0].intent = "attack:13"; d.state.enemies[1].actionIndex = 1; d.state.enemies[1].intent = "charge"; },
            d => d.state.turn = 2,
            d => d.state.battleRetries = -1,
            d => d.battleCheckpoint = null,
            d => d.battleCheckpoint.phase = "defeat",
            d => { d.state.enemies[0].hp = 0; d.state.enemies[1].hp = 0; });
        SessionData retried = GameSession.Clone(defeat.Data);
        retried.state.battleRetries = 5;
        Equal(Save(retried), Save(GameSession.Restore(retried).Data), "失败中的重试次数合法");
    }

    private static void CloneAndLogs()
    {
        GameSession session = AtNode(2);
        SessionData clone = GameSession.Clone(session.Data);
        clone.state.enemies[0].hp = 1; clone.state.logs.Add("副本");
        clone.state.claimedSupplies.Add(3); clone.state.upgradedNodes.Add(6);
        clone.state.choices[1] = 1; clone.state.eventRolls[4] = 3;
        clone.battleCheckpoint.hp = 1; clone.battleCheckpoint.enemies[0].hp = 1;
        GameState s = session.Data.state;
        Equal(24, s.enemies[0].hp, "敌人深拷贝");
        Check(!s.logs.Contains("副本"), "日志深拷贝");
        Equal(0, s.claimedSupplies.Count, "领取列表深拷贝");
        Equal(0, s.upgradedNodes.Count, "强化列表深拷贝");
        Equal(0, s.choices[1], "选择数组深拷贝");
        Equal(-1, s.eventRolls[4], "事件数组深拷贝");
        Equal(100, session.Data.battleCheckpoint.hp, "检查点深拷贝");
        Equal(24, session.Data.battleCheckpoint.enemies[0].hp, "检查点敌人深拷贝");
        Check(!ReferenceEquals(s.enemies[0], GameSession.Clone(s.enemies[0])), "敌人克隆为新对象");
        Check(GameSession.Clone<GameState>(null) == null, "null克隆");
        bool rejected = false;
        try { GameSession.Clone("文本"); } catch (ArgumentException) { rejected = true; }
        Check(rejected, "不支持的类型拒绝克隆");
        for (int i = 0; i < 30; i++) session.AddLog("日志" + i);
        Equal(12, s.logs.Count, "日志最多12条");
        Equal("日志18", s.logs[0], "日志保留最近12条");
        Equal("日志29", s.logs[11], "最新日志");
        Invalid(session, delegate { session.AddLog(null); });
        Equal(Save(session.Data), Save(RoundTrip(session).Data), "日志上限存档合法");
    }

    private static void NaturalPlay()
    {
        int defeats = 0, risks = 0, actions = 0;
        const uint Seeds = 40;
        for (uint seed = 1; seed <= Seeds; seed++)
        {
            GameSession session = GameSession.New(seed);
            int[] expectedChoices = GameSession.Filled(-1);
            int[] expectedRolls = GameSession.Filled(-1);
            int seedDefeats = 0;
            for (int i = 0; session.Data.state.phase != "completed"; i++)
            {
                Check(i < 20000, "种子" + seed + "应在步数上限内通关");
                GameState s = session.Data.state;
                int index = s.nodeIndex;
                NodeDef node = session.CurrentNode;
                string phase = s.phase;
                bool claimedBefore = s.supplyClaimed;
                bool upgradedBefore = session.CurrentUpgradeChosen;
                if (phase == "defeat")
                {
                    defeats++; seedDefeats++;
                    Check(seedDefeats < 200, "重试应最终获胜");
                    session = VerifyReset(session);
                }
                else
                {
                    if (phase == "supply" && (!claimedBefore || (node.reward && !upgradedBefore))) Invalid(session, delegate { session.Advance(); });
                    if (phase == "choice") Invalid(session, delegate { session.Advance(node.choices.Length); });
                    Step(session, seed);
                    s = session.Data.state;
                    if (phase == "choice")
                    {
                        expectedChoices[index] = s.choices[index];
                        Equal((int)((seed + (uint)index) % (uint)node.choices.Length), s.choices[index], "选择记录");
                    }
                    else if (phase == "event")
                    {
                        expectedRolls[index] = s.eventRolls[index];
                        bool risk = (seed + (uint)index) % 3 != 0;
                        Check(risk ? s.eventRolls[index] >= 1 && s.eventRolls[index] <= 20 : s.eventRolls[index] == 0, "事件点数范围");
                        if (risk) risks++;
                        Check(s.hp >= 1, "探索后至少1生命");
                        Invalid(session, delegate { session.ResolveEvent(true); });
                        Invalid(session, delegate { session.ResolveEvent(false); });
                    }
                    else if (phase == "supply" && !claimedBefore)
                    {
                        string after = Save(session.Data);
                        Check(!session.ClaimSupply(), "补给不能重复领取");
                        Equal(after, Save(session.Data), "重复领取无副作用");
                    }
                    else if (phase == "supply" && node.reward && !upgradedBefore)
                    {
                        foreach (string skill in Skills) Invalid(session, delegate { session.Upgrade(skill); });
                    }
                }
                s = session.Data.state;
                Check(s.choices.SequenceEqual(expectedChoices) && s.eventRolls.SequenceEqual(expectedRolls), "选择与事件结果不会被改写或重掷");
                string before = Save(session.Data);
                session = RoundTrip(session);
                Equal(before, Save(session.Data), "每次合法行动后都能精确恢复");
                actions++;
            }
            GameState end = session.Data.state;
            Equal(49, end.nodeIndex, "完成于最后节点");
            Equal(Join(SupplyNodes), Join(end.claimedSupplies), "12处补给各领取一次");
            Equal(Join(RewardNodes), Join(end.upgradedNodes), "7次强化各一次");
            Check(ChoiceNodes.All(n => end.choices[n] >= 0) && EventNodes.All(n => end.eventRolls[n] >= 0), "选择与事件全部记录");
            Equal(string.Join(",", EvidenceNames), string.Join(",", session.CollectedEvidence()), "证据齐全");
            Check(end.enemies.Length == 0 && end.battleRetries == 0 && session.Data.battleCheckpoint == null, "完成时无战斗数据");
        }
        Console.WriteLine("  自然流程：" + Seeds + "个种子，" + actions + "次行动，冒险事件" + risks + "次，战败重试" + defeats + "次。");
        Check(risks > 0, "自然流程覆盖冒险事件");
        Check(defeats > 0, "自然流程覆盖战败重试");
    }
}
