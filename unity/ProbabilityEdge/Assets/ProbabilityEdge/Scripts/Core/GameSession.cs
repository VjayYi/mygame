using System;
using System.Collections.Generic;

namespace ProbabilityEdge.Core
{
    [Serializable]
    public sealed class SessionData
    {
        public int version = GameSession.SaveVersion;
        public GameState state;
        public GameState battleCheckpoint;
    }

    [Serializable]
    public sealed class GameState
    {
        public int nodeIndex;
        public string phase = "story";
        public int hp = 100;
        public int maxHp = 100;
        public int shield;
        public int turn;
        public int rollsLeft;
        public int pendingFace = -1;
        public string pendingSkill = "";
        public uint rngState;
        public EnemyState[] enemies = new EnemyState[0];
        public List<string> logs = new List<string>();
        public int sword = GameSession.BaseSword;
        public int shieldPower = GameSession.BaseShield;
        public int heal = GameSession.BaseHeal;
        public int shot = GameSession.BaseShot;
        public bool supplyClaimed;
        public int battleRetries;
        public List<int> claimedSupplies = new List<int>();
        public List<int> upgradedNodes = new List<int>();
        public int[] choices = GameSession.Filled(-1);
        public int[] eventRolls = GameSession.Filled(-1);
    }

    [Serializable]
    public sealed class EnemyState
    {
        public int id;
        public string name;
        public string kind;
        public int hp;
        public int maxHp;
        public int shield;
        public int actionIndex;
        public string intent;
    }

    public sealed class GameSession
    {
        public const int SaveVersion = 2;
        public const int FaceCount = 10;
        public const int SwordFace = 0;
        public const int ShieldFace = 4;
        public const int HealFace = 7;
        public const int ShotFace = 9;
        public const int BaseSword = 8, BaseShield = 6, BaseHeal = 8, BaseShot = 11;
        public const int RollsPerTurn = 3;
        public const int SuccessThreshold = 12;

        public SessionData Data { get; private set; }

        private GameSession(SessionData data) { Data = data; }

        public static int[] Filled(int value)
        {
            int[] array = new int[ChapterOne.NodeCount];
            for (int i = 0; i < array.Length; i++) array[i] = value;
            return array;
        }

        public static GameSession New(uint seed)
        {
            GameState state = new GameState { rngState = seed == 0 ? 0x6D2B79F5u : seed };
            GameSession session = new GameSession(new SessionData { state = state });
            session.AddLog("C1-01-01：离开关押室，寻找出口。");
            return session;
        }

        public static GameSession Restore(SessionData data)
        {
            Require(data != null && data.version == SaveVersion && data.state != null, "存档版本或结构无效。");
            ValidateState(data.state);
            bool inBattle = data.state.phase == "battle" || data.state.phase == "defeat";
            Require(inBattle == (data.battleCheckpoint != null), "战斗检查点缺失或位置无效。");
            if (inBattle) ValidateCheckpoint(data.battleCheckpoint, data.state);
            return new GameSession(Clone(data));
        }

        // —— 便于界面读取的派生信息 ——
        public NodeDef CurrentNode { get { return ChapterOne.Node(Data.state.nodeIndex); } }
        public bool CurrentUpgradeChosen { get { return Data.state.upgradedNodes.Contains(Data.state.nodeIndex); } }
        public List<string> CollectedEvidence()
        {
            List<string> result = new List<string>();
            for (int i = 0; i < Data.state.nodeIndex; i++)
            {
                string evidence = ChapterOne.Node(i).evidence;
                if (evidence != "") result.Add(evidence);
            }
            return result;
        }
        public int CurrentEventDelta()
        {
            GameState s = Data.state;
            NodeDef node = CurrentNode;
            Require(node.kind == "event" && s.eventRolls[s.nodeIndex] >= 0, "当前没有已结算的事件。");
            return EventDelta(ChapterOne.Event(node.eventIndex), s.eventRolls[s.nodeIndex]);
        }
        public string CurrentEventText()
        {
            GameState s = Data.state;
            NodeDef node = CurrentNode;
            Require(node.kind == "event" && s.eventRolls[s.nodeIndex] >= 0, "当前没有已结算的事件。");
            EventDef e = ChapterOne.Event(node.eventIndex);
            int roll = s.eventRolls[s.nodeIndex];
            if (roll == 0) return e.safeText;
            if (roll == 20) return e.critText;
            if (roll == 1) return e.fumbleText;
            return roll >= SuccessThreshold ? e.successText : e.failText;
        }

        public static string DescribeIntent(string intent)
        {
            if (intent == "wait") return "准备";
            if (intent == "charge") return "蓄力（下次重击）";
            if (intent.StartsWith("attack:")) return "攻击 " + intent.Substring(7);
            if (intent.StartsWith("shield:")) return "护盾 +" + intent.Substring(7);
            return intent;
        }

        public static string SkillName(string skill)
        {
            if (skill == "sword") return "剑";
            if (skill == "shield") return "盾";
            if (skill == "heal") return "心";
            if (skill == "shot") return "枪击";
            return skill;
        }

        // —— 剧情推进 ——
        public void Advance(int choice = 0)
        {
            GameState s = Data.state;
            NodeDef node = CurrentNode;
            if (s.phase == "story") Require(choice == 0, "剧情节点没有可选项。");
            else if (s.phase == "choice") Require(choice >= 0 && choice < node.choices.Length, "选项无效。");
            else if (s.phase == "supply") Require(choice == 0 && s.supplyClaimed && (!node.reward || CurrentUpgradeChosen), "请先领取补给并完成技能强化。");
            else if (s.phase == "eventResult") Require(choice == 0, "事件结果没有可选项。");
            else throw new InvalidOperationException("当前不能推进。");

            if (s.phase == "choice")
            {
                s.choices[s.nodeIndex] = choice;
                AddLog(node.responses[choice]);
            }
            if (node.evidence != "") AddLog("取得证据：" + node.evidence + "。");
            EnterNode(s.nodeIndex + 1);
        }

        public bool ClaimSupply()
        {
            GameState s = Data.state;
            Require(s.phase == "supply", "当前没有可领取的补给。");
            if (s.supplyClaimed) return false;
            int before = s.hp;
            s.hp = HealTo(s.hp, s.maxHp, CurrentNode.heal);
            s.supplyClaimed = true;
            s.claimedSupplies.Add(s.nodeIndex);
            AddLog("使用补给，实际恢复" + (s.hp - before) + "点生命。");
            return true;
        }

        public void Upgrade(string skill)
        {
            GameState s = Data.state;
            Require(s.phase == "supply" && CurrentNode.reward && s.supplyClaimed && !CurrentUpgradeChosen &&
                (skill == "sword" || skill == "shield" || skill == "heal" || skill == "shot"), "当前不能选择该技能强化。");
            if (skill == "sword") s.sword += 2;
            else if (skill == "shield") s.shieldPower += 2;
            else if (skill == "heal") s.heal += 2;
            else s.shot += 2;
            s.upgradedNodes.Add(s.nodeIndex);
            AddLog("技能强化：" + SkillName(skill) + "效果+2。");
        }

        public void ResolveEvent(bool risk)
        {
            GameState s = Data.state;
            Require(s.phase == "event", "事件不能重复结算。");
            EventDef e = ChapterOne.Event(CurrentNode.eventIndex);
            int roll = risk ? (int)NextBounded(20) + 1 : 0;
            int delta = EventDelta(e, roll);
            if (delta >= 0) s.hp = HealTo(s.hp, s.maxHp, delta);
            else s.hp = Math.Max(1, s.hp + delta);
            s.eventRolls[s.nodeIndex] = roll;
            s.phase = "eventResult";
            AddLog((risk ? "D20结果：" + roll + "，" : "安全选择，") + "生命" + s.hp + "。");
        }

        // —— 战斗 ——
        public int Roll()
        {
            GameState s = Data.state;
            Require(s.phase == "battle" && s.rollsLeft > 0 && s.pendingFace == -1, "当前不能投掷。");
            int face = (int)NextBounded(FaceCount);
            s.rollsLeft--;
            if (IsSword(face) || face == ShotFace)
            {
                s.pendingFace = face;
                s.pendingSkill = IsSword(face) ? "sword" : "shot";
                AddLog("投出" + SkillName(s.pendingSkill) + "，请选择存活目标。");
            }
            else if (face >= ShieldFace && face < HealFace)
            {
                s.shield = (int)Math.Min(int.MaxValue, (long)s.shield + s.shieldPower);
                AddLog("投出盾，护盾+" + s.shieldPower + "。");
            }
            else
            {
                int before = s.hp;
                s.hp = HealTo(s.hp, s.maxHp, s.heal);
                AddLog("投出心，实际恢复" + (s.hp - before) + "点生命。");
            }
            return face;
        }

        public void ChooseTarget(int id)
        {
            GameState s = Data.state;
            Require(s.phase == "battle" && (IsSword(s.pendingFace) || s.pendingFace == ShotFace), "没有待选择目标的技能。");
            EnemyState target = null;
            foreach (EnemyState enemy in s.enemies) if (enemy.id == id && enemy.hp > 0) target = enemy;
            Require(target != null, "目标不存在或已被击败。");
            int damage = IsSword(s.pendingFace) ? s.sword : s.shot;
            int absorbed = Math.Min(target.shield, damage);
            target.shield -= absorbed;
            target.hp = Math.Max(0, target.hp - (damage - absorbed));
            ClearPending(s);
            AddLog(target.name + "受到" + damage + "点攻击" + (absorbed > 0 ? "（护盾吸收" + absorbed + "）" : "") + "，剩余" + target.hp + "生命。");
            foreach (EnemyState enemy in s.enemies) if (enemy.hp > 0) return;
            AddLog("战斗胜利，护盾清零。");
            EnterNode(s.nodeIndex + 1);
        }

        public void EndTurn()
        {
            GameState s = Data.state;
            Require(s.phase == "battle" && s.pendingFace == -1 && s.turn < int.MaxValue, "当前不能结束回合。");
            s.rollsLeft = 0;
            foreach (EnemyState enemy in s.enemies)
            {
                if (enemy.hp == 0) continue;
                string action = enemy.intent;
                if (action.StartsWith("attack:"))
                {
                    int damage = int.Parse(action.Substring(7));
                    int absorbed = Math.Min(s.shield, damage);
                    s.shield -= absorbed;
                    s.hp = Math.Max(0, s.hp - (damage - absorbed));
                    AddLog(enemy.name + "攻击" + damage + "，护盾吸收" + absorbed + "。");
                }
                else if (action.StartsWith("shield:"))
                {
                    enemy.shield += int.Parse(action.Substring(7));
                    AddLog(enemy.name + "获得护盾，当前" + enemy.shield + "。");
                }
                else AddLog(enemy.name + "：" + DescribeIntent(action) + "。");
                enemy.actionIndex++;
                enemy.intent = IntentFor(enemy);
                if (s.hp == 0)
                {
                    s.phase = "defeat";
                    s.shield = 0;
                    AddLog("战斗失败，可从战前检查点重试。");
                    return;
                }
            }
            // 护盾只抵挡紧接着的敌方回合，新回合开始时清零。
            s.shield = 0;
            s.turn++;
            s.rollsLeft = RollsPerTurn;
            AddLog("第" + s.turn + "回合，护盾清零，剩余" + RollsPerTurn + "次投掷。");
        }

        public void ResetBattle()
        {
            Require(Data.state.phase == "defeat" && Data.battleCheckpoint != null && Data.state.battleRetries < int.MaxValue, "仅战斗失败后可以重试。");
            int retries = Data.state.battleRetries + 1;
            Data.state = Clone(Data.battleCheckpoint);
            // 生命、奖励、敌人回到战前；骰子序列随重试次数轮换，避免同样操作反复复现同一次失败。
            Data.state.battleRetries = retries;
            Data.state.rngState = MixSeed(Data.battleCheckpoint.rngState, (uint)retries);
            AddLog("从战前检查点重试（第" + retries + "次），骰子序列已重新洗牌。");
        }

        private static uint MixSeed(uint seed, uint salt)
        {
            uint x = seed ^ (salt * 0x9E3779B9u);
            x ^= x >> 16; x *= 0x7FEB352Du; x ^= x >> 15; x *= 0x846CA68Bu; x ^= x >> 16;
            return x == 0 ? 0x6D2B79F5u : x;
        }

        public void AddLog(string message)
        {
            Require(message != null, "日志不能为null。");
            List<string> logs = Data.state.logs;
            logs.Add(message);
            if (logs.Count > 12) logs.RemoveRange(0, logs.Count - 12);
        }

        // —— 深拷贝 ——
        public static T Clone<T>(T value) where T : class
        {
            if (value == null) return null;
            SessionData session = value as SessionData;
            if (session != null)
                return (T)(object)new SessionData { version = session.version, state = Clone(session.state), battleCheckpoint = Clone(session.battleCheckpoint) };
            GameState s = value as GameState;
            if (s != null)
            {
                GameState c = new GameState
                {
                    nodeIndex = s.nodeIndex, phase = s.phase, hp = s.hp, maxHp = s.maxHp, shield = s.shield,
                    turn = s.turn, rollsLeft = s.rollsLeft, pendingFace = s.pendingFace, pendingSkill = s.pendingSkill,
                    rngState = s.rngState, sword = s.sword, shieldPower = s.shieldPower, heal = s.heal, shot = s.shot,
                    supplyClaimed = s.supplyClaimed, battleRetries = s.battleRetries,
                    logs = s.logs == null ? null : new List<string>(s.logs),
                    claimedSupplies = s.claimedSupplies == null ? null : new List<int>(s.claimedSupplies),
                    upgradedNodes = s.upgradedNodes == null ? null : new List<int>(s.upgradedNodes),
                    choices = s.choices == null ? null : (int[])s.choices.Clone(),
                    eventRolls = s.eventRolls == null ? null : (int[])s.eventRolls.Clone(),
                    enemies = s.enemies == null ? null : new EnemyState[s.enemies.Length]
                };
                if (s.enemies != null) for (int i = 0; i < s.enemies.Length; i++) c.enemies[i] = Clone(s.enemies[i]);
                return (T)(object)c;
            }
            EnemyState e = value as EnemyState;
            if (e != null)
                return (T)(object)new EnemyState { id = e.id, name = e.name, kind = e.kind, hp = e.hp, maxHp = e.maxHp, shield = e.shield, actionIndex = e.actionIndex, intent = e.intent };
            throw new ArgumentException("Clone仅支持会话、游戏状态和敌人状态。", "value");
        }

        // —— 内部 ——
        private void EnterNode(int index)
        {
            GameState s = Data.state;
            NodeDef node = ChapterOne.Node(index);
            s.nodeIndex = index;
            s.shield = 0;
            s.turn = 0;
            s.rollsLeft = 0;
            s.supplyClaimed = false;
            s.battleRetries = 0;
            ClearPending(s);
            s.enemies = new EnemyState[0];
            Data.battleCheckpoint = null;
            s.phase = PhaseFor(node.kind);
            AddLog("进入" + node.id + "：" + node.title + "。");
            if (s.phase == "completed") { AddLog("第一章完成。"); return; }
            if (s.phase != "battle") return;
            s.turn = 1;
            s.rollsLeft = RollsPerTurn;
            s.enemies = CreateEnemies(node);
            AddLog("战斗开始，每回合" + RollsPerTurn + "次投掷。");
            Data.battleCheckpoint = Clone(s);
        }

        private uint NextBounded(uint bound)
        {
            uint threshold = unchecked(0u - bound) % bound;
            uint value;
            do
            {
                value = Data.state.rngState;
                value ^= value << 13;
                value ^= value >> 17;
                value ^= value << 5;
                Data.state.rngState = value;
            } while (value < threshold);
            return value % bound;
        }

        private static string PhaseFor(string kind) { return kind == "ending" ? "completed" : kind; }

        private static int EventDelta(EventDef e, int roll)
        {
            if (roll == 0) return e.safeDelta;
            if (roll == 20) return e.critDelta;
            if (roll == 1) return e.fumbleDelta;
            return roll >= SuccessThreshold ? e.successDelta : e.failDelta;
        }

        private static int HealTo(int hp, int maxHp, int amount) { return (int)Math.Min(maxHp, (long)hp + amount); }
        private static bool IsSword(int face) { return face >= SwordFace && face < ShieldFace; }
        private static void ClearPending(GameState s) { s.pendingFace = -1; s.pendingSkill = ""; }
        private static void Require(bool condition, string message) { if (!condition) throw new InvalidOperationException(message); }

        private static EnemyState[] CreateEnemies(NodeDef node)
        {
            EnemyState[] result = new EnemyState[node.enemies.Length];
            for (int i = 0; i < node.enemies.Length; i++)
            {
                EnemyTemplate t = ChapterOne.Template(node.enemies[i]);
                int sameKind = 0, order = 0;
                for (int j = 0; j < node.enemies.Length; j++)
                {
                    if (node.enemies[j] != t.kind) continue;
                    sameKind++;
                    if (j < i) order++;
                }
                string name = sameKind > 1 ? t.name + (char)('A' + order) : t.name;
                EnemyState e = new EnemyState { id = i + 1, name = name, kind = t.kind, hp = t.hp, maxHp = t.hp };
                e.intent = IntentFor(e);
                result[i] = e;
            }
            return result;
        }

        private static string IntentFor(EnemyState e)
        {
            string[] actions = ChapterOne.Template(e.kind).actions;
            return actions[e.actionIndex % actions.Length];
        }

        private static bool SameList(List<int> a, List<int> b)
        {
            if (a.Count != b.Count) return false;
            for (int i = 0; i < a.Count; i++) if (a[i] != b[i]) return false;
            return true;
        }

        private static bool SameArray(int[] a, int[] b)
        {
            if (a.Length != b.Length) return false;
            for (int i = 0; i < a.Length; i++) if (a[i] != b[i]) return false;
            return true;
        }

        private static void ValidateCheckpoint(GameState c, GameState s)
        {
            ValidateState(c);
            Require(c.phase == "battle" && c.nodeIndex == s.nodeIndex && c.turn == 1 && c.rollsLeft == RollsPerTurn &&
                c.pendingFace == -1 && c.shield == 0 && c.battleRetries == 0, "检查点不是战斗起始状态。");
            foreach (EnemyState enemy in c.enemies)
                Require(enemy.hp == enemy.maxHp && enemy.actionIndex == 0 && enemy.shield == 0, "检查点敌人状态无效。");
            Require(c.maxHp == s.maxHp && c.sword == s.sword && c.shieldPower == s.shieldPower && c.heal == s.heal &&
                c.shot == s.shot && SameList(c.claimedSupplies, s.claimedSupplies) && SameList(c.upgradedNodes, s.upgradedNodes) &&
                SameArray(c.choices, s.choices) && SameArray(c.eventRolls, s.eventRolls), "检查点与会话进度不一致。");
        }

        private static void ValidateState(GameState s)
        {
            Require(s != null && s.nodeIndex >= 0 && s.nodeIndex < ChapterOne.NodeCount && s.rngState != 0 &&
                s.maxHp == 100 && s.hp >= 0 && s.hp <= s.maxHp && s.shield >= 0 && s.phase != null &&
                s.enemies != null && s.logs != null && s.logs.Count <= 12 && s.claimedSupplies != null &&
                s.upgradedNodes != null && s.pendingSkill != null && s.choices != null && s.eventRolls != null &&
                s.choices.Length == ChapterOne.NodeCount && s.eventRolls.Length == ChapterOne.NodeCount, "游戏状态结构或数值无效。");
            foreach (string log in s.logs) Require(log != null, "日志结构无效。");

            NodeDef current = ChapterOne.Node(s.nodeIndex);
            bool battle = s.phase == "battle" || s.phase == "defeat";
            bool validPhase = current.kind == "battle" ? battle :
                current.kind == "event" ? s.phase == "event" || s.phase == "eventResult" :
                s.phase == PhaseFor(current.kind);
            Require(validPhase && (s.phase == "defeat" ? s.hp == 0 : s.hp > 0), "节点、阶段或生命状态无效。");

            List<int> expectedSupplies = new List<int>();
            List<int> rewardNodes = new List<int>();
            for (int i = 0; i < ChapterOne.NodeCount; i++)
            {
                NodeDef node = ChapterOne.Node(i);
                bool passed = i < s.nodeIndex;
                bool choiceDone = node.kind == "choice" && passed;
                Require(choiceDone ? s.choices[i] >= 0 && s.choices[i] < node.choices.Length : s.choices[i] == -1, "选择记录无效。");
                bool eventDone = node.kind == "event" && (passed || (i == s.nodeIndex && s.phase == "eventResult"));
                Require(eventDone ? s.eventRolls[i] >= 0 && s.eventRolls[i] <= 20 : s.eventRolls[i] == -1, "事件记录无效。");
                bool claimed = node.kind == "supply" && (passed || (i == s.nodeIndex && s.supplyClaimed));
                if (claimed) expectedSupplies.Add(i);
                if (claimed && node.reward) rewardNodes.Add(i);
            }
            Require(SameList(expectedSupplies, s.claimedSupplies) && (!s.supplyClaimed || current.kind == "supply"), "补给领取记录无效。");

            // 已离开的奖励节点必须完成强化；当前奖励节点可以尚未选择。
            int at = 0;
            foreach (int node in rewardNodes)
            {
                bool present = at < s.upgradedNodes.Count && s.upgradedNodes[at] == node;
                Require(present || node == s.nodeIndex, "技能强化进度无效。");
                if (present) at++;
            }
            Require(at == s.upgradedNodes.Count, "技能强化记录无效。");
            int bonus = Bonus(s.sword, BaseSword) + Bonus(s.shieldPower, BaseShield) + Bonus(s.heal, BaseHeal) + Bonus(s.shot, BaseShot);
            Require(bonus == 2 * s.upgradedNodes.Count, "技能强化数值无效。");

            Require(s.battleRetries >= 0 && (battle || s.battleRetries == 0), "重试次数无效。");
            if (!battle)
            {
                Require(s.enemies.Length == 0 && s.shield == 0 && s.turn == 0 && s.rollsLeft == 0 &&
                    s.pendingFace == -1 && s.pendingSkill == "", "非战斗状态含有战斗数据。");
                return;
            }
            Require(s.turn >= 1 && s.rollsLeft >= 0 && s.rollsLeft <= RollsPerTurn &&
                (s.pendingFace == -1 ? s.pendingSkill == "" :
                s.rollsLeft < RollsPerTurn && ((IsSword(s.pendingFace) && s.pendingSkill == "sword") ||
                (s.pendingFace == ShotFace && s.pendingSkill == "shot"))) &&
                (s.phase != "defeat" || (s.rollsLeft == 0 && s.pendingFace == -1 && s.shield == 0)), "回合或待选技能无效。");

            EnemyState[] templates = CreateEnemies(current);
            Require(s.enemies.Length == templates.Length, "敌人数量无效。");
            bool alive = false, acted = false, stopped = false;
            for (int position = 0; position < s.enemies.Length; position++)
            {
                EnemyState enemy = s.enemies[position];
                EnemyState template = templates[position];
                Require(enemy != null && enemy.id == template.id && enemy.name == template.name && enemy.kind == template.kind &&
                    enemy.maxHp == template.maxHp && enemy.hp >= 0 && enemy.hp <= enemy.maxHp && enemy.shield >= 0 &&
                    enemy.actionIndex >= 0 && enemy.actionIndex <= s.turn && enemy.intent == IntentFor(enemy), "敌人数据无效。");
                if (enemy.hp == 0) continue;
                alive = true;
                if (s.phase == "battle") Require(enemy.actionIndex == s.turn - 1, "敌方行动进度无效。");
                else
                {
                    Require(enemy.actionIndex == s.turn || enemy.actionIndex == s.turn - 1, "失败回合行动进度无效。");
                    if (enemy.actionIndex == s.turn) { Require(!stopped, "失败行动顺序无效。"); acted = true; }
                    else stopped = true;
                }
            }
            Require(alive && (s.phase != "defeat" || acted), "战斗已结束或失败状态无效。");
        }

        private static int Bonus(int power, int original)
        {
            int bonus = power - original;
            Require(bonus >= 0 && bonus % 2 == 0 && bonus <= 14, "技能数值无效。");
            return bonus;
        }
    }
}
