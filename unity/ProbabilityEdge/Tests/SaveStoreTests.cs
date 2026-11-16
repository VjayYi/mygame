using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using ProbabilityEdge.Core;

internal static class SaveStoreTests
{
    private static readonly UTF8Encoding Utf8 = new UTF8Encoding(false, true);
    private static Action<bool, string> check;

    internal static void Run(Action<string, Action> run, Action<bool, string> assertion)
    {
        check = assertion;
        run("存档：参数与缺失文件不创建新会话", MissingFiles);
        run("存档：UTF8无BOM、安全退出与完整重开", SafeExit);
        run("存档：原子替换与备份轮换", BackupRotation);
        run("存档：损坏主档只读备份恢复及UI提示", CorruptPrimary);
        run("存档：主档缺失仍可只读恢复备份", MissingPrimary);
        run("存档：双档损坏保留文件并报告两个错误", BothInvalid);
        run("存档：版本、大小与校验先于反序列化", EnvelopeValidation);
        run("存档：Restore拒绝非法结构与进度", SchemaValidation);
        run("存档：临时写入失败不损坏旧档", TemporaryFailure);
        run("存档：原子替换失败不退化为覆盖", ReplaceFailure);
        run("存档：非法会话及序列化失败不触碰旧档", SaveValidation);
        run("存档：重复补给与奖励跨重开幂等", SupplyRoundTrip);
        run("存档：待选剑枪、随机状态与检查点往返", PendingRoundTrip);
        run("存档：失败检查点可在重开后精确重试", DefeatRoundTrip);
        run("存档：JsonUtility嵌套null兼容与战斗检查点保护", NestedNullRoundTrip);
    }

    private sealed class JsonSessionSerializer : ISessionSerializer
    {
        private static readonly JsonSerializerOptions Options = new JsonSerializerOptions { IncludeFields = true, WriteIndented = true };
        internal int SerializeCalls;
        internal int DeserializeCalls;
        internal bool MaterializeNullCheckpoint;
        internal bool OverridePayload;
        internal string Payload;
        internal Exception SerializeError;

        public string Serialize(SessionData data)
        {
            SerializeCalls++;
            if (SerializeError != null) throw SerializeError;
            return OverridePayload ? Payload : JsonSerializer.Serialize(data, Options);
        }

        public SessionData Deserialize(string json)
        {
            DeserializeCalls++;
            SessionData data = JsonSerializer.Deserialize<SessionData>(json, Options);
            if (MaterializeNullCheckpoint && data != null && data.battleCheckpoint == null)
                data.battleCheckpoint = new GameState();
            return data;
        }
    }

    private static void InDirectory(Action<string> test)
    {
        string directory = Path.Combine(Path.GetTempPath(), "ProbabilityEdge-SaveStore-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        try { test(directory); }
        finally { Directory.Delete(directory, true); }
    }

    private static T Throws<T>(Action action) where T : Exception
    {
        try { action(); }
        catch (T error) { check(true, "预期异常：" + typeof(T).Name); return error; }
        check(false, "必须抛出异常：" + typeof(T).Name);
        throw new Exception("未抛出预期异常。");
    }

    private static void SameBytes(byte[] expected, string path, string message)
    {
        check(Convert.ToBase64String(expected) == Convert.ToBase64String(File.ReadAllBytes(path)), message);
    }

    private static void SameSession(GameSession expected, GameSession actual, string message)
    {
        JsonSessionSerializer serializer = new JsonSessionSerializer();
        check(serializer.Serialize(expected.Data) == serializer.Serialize(actual.Data), message);
    }

    private static string Envelope(string payload, string checkpoint = "0", string header = "PROBABILITY-EDGE-SAVE-1")
    {
        string checksum;
        using (SHA256 sha = SHA256.Create())
            checksum = BitConverter.ToString(sha.ComputeHash(Utf8.GetBytes(payload))).Replace("-", "").ToLowerInvariant();
        return header + "\n" + checksum + "\n" + checkpoint + "\n" + payload;
    }

    private static void MissingFiles()
    {
        Throws<ArgumentException>(() => new SaveStore(" ", new JsonSessionSerializer()));
        Throws<ArgumentNullException>(() => new SaveStore(Path.GetTempPath(), null));
        InDirectory(directory =>
        {
            string missing = Path.Combine(directory, "missing");
            SaveStore store = new SaveStore(missing, new JsonSessionSerializer());
            check(store.SavePath == Path.Combine(missing, "session.sav"), "固定档名与绝对路径");
            check(!store.Exists, "双档缺失时Exists为false");
            Throws<FileNotFoundException>(() => store.Load());
            check(!Directory.Exists(missing), "Load不能创建目录或新档");
            check(!store.LastLoadUsedBackup && store.LastLoadWarning == "", "失败不能声称已经恢复备份");
        });
    }

    private static void SafeExit()
    {
        InDirectory(directory =>
        {
            SaveStore store = new SaveStore(directory, new JsonSessionSerializer());
            GameSession session = GameSession.New(12345);
            session.AddLog("安全退出：保存中文日志。");
            store.Save(session);
            check(store.Exists, "首存后存在主档");
            byte[] bytes = File.ReadAllBytes(store.SavePath);
            check(!(bytes[0] == 0xef && bytes[1] == 0xbb && bytes[2] == 0xbf), "UTF8不含BOM");
            check(Utf8.GetString(bytes).StartsWith("PROBABILITY-EDGE-SAVE-1\n", StringComparison.Ordinal), "格式版本头");
            check(!File.Exists(store.SavePath + ".tmp") && !File.Exists(store.SavePath + ".bak"), "首存原子移动后没有临时文件或虚假备份");
            SaveStore reopened = new SaveStore(directory, new JsonSessionSerializer());
            GameSession loaded = reopened.Load();
            SameSession(session, loaded, "安全退出后新实例完整恢复");
            check(loaded.Data.battleCheckpoint == null, "非战斗检查点保留null");
            check(!reopened.LastLoadUsedBackup && reopened.LastLoadWarning == "", "主档成功不显示恢复警告");
            // 模拟退出前留下的不完整临时文件；只读加载必须忽略它。
            File.WriteAllText(store.SavePath + ".tmp", "未完成写入", Utf8);
            SameSession(session, reopened.Load(), "孤立临时文件不能影响主档恢复");
            check(File.ReadAllText(store.SavePath + ".tmp", Utf8) == "未完成写入", "Load不删除遗留文件");
        });
    }

    private static void BackupRotation()
    {
        InDirectory(directory =>
        {
            SaveStore store = new SaveStore(directory, new JsonSessionSerializer());
            GameSession session = GameSession.New(77);
            store.Save(session);
            byte[] first = File.ReadAllBytes(store.SavePath);
            session.Advance(); store.Save(session);
            SameBytes(first, store.SavePath + ".bak", "第二次存档备份精确等于旧主档");
            byte[] second = File.ReadAllBytes(store.SavePath);
            session.Advance(); store.Save(session);
            SameBytes(second, store.SavePath + ".bak", "第三次存档原子更新已有备份");
            SameSession(session, store.Load(), "新主档完整恢复");
            check(!File.Exists(store.SavePath + ".tmp"), "替换后临时文件已消费");
        });
    }

    private static void CorruptPrimary()
    {
        InDirectory(directory =>
        {
            SaveStore store = new SaveStore(directory, new JsonSessionSerializer());
            GameSession original = GameSession.New(44);
            store.Save(original);
            GameSession current = GameSession.Restore(original.Data);
            current.Advance(); store.Save(current);
            byte[] validPrimary = File.ReadAllBytes(store.SavePath);
            byte[] backup = File.ReadAllBytes(store.SavePath + ".bak");
            File.WriteAllText(store.SavePath, "损坏主档", Utf8);
            byte[] broken = File.ReadAllBytes(store.SavePath);
            SameSession(original, store.Load(), "主档损坏时恢复上一版");
            check(store.LastLoadUsedBackup && store.LastLoadWarning.Contains("备份只读恢复") && store.LastLoadWarning.Contains("主存档未被覆盖"), "UI可明确提示备份恢复与坏主档保留");
            SameBytes(broken, store.SavePath, "Load不能覆盖坏主档");
            SameBytes(backup, store.SavePath + ".bak", "Load不能修改备份");
            File.WriteAllBytes(store.SavePath, validPrimary);
            SameSession(current, store.Load(), "外部修复后读取主档");
            check(!store.LastLoadUsedBackup && store.LastLoadWarning == "", "每次Load重置上一轮警告");
        });
    }

    private static void MissingPrimary()
    {
        InDirectory(directory =>
        {
            SaveStore store = new SaveStore(directory, new JsonSessionSerializer());
            GameSession session = GameSession.New(8);
            store.Save(session);
            File.Move(store.SavePath, store.SavePath + ".bak");
            check(store.Exists, "仅备份存在也可继续游戏");
            SameSession(session, store.Load(), "缺主档仍可恢复备份");
            check(store.LastLoadUsedBackup && !File.Exists(store.SavePath), "只读恢复不能重建主档");
        });
    }

    private static void BothInvalid()
    {
        InDirectory(directory =>
        {
            SaveStore store = new SaveStore(directory, new JsonSessionSerializer());
            File.WriteAllText(store.SavePath, "主档坏了", Utf8);
            SessionData invalid = GameSession.New(1).Data;
            invalid.state.hp = -1;
            File.WriteAllText(store.SavePath + ".bak", Envelope(new JsonSessionSerializer().Serialize(invalid)), Utf8);
            byte[] primary = File.ReadAllBytes(store.SavePath);
            byte[] backup = File.ReadAllBytes(store.SavePath + ".bak");
            InvalidDataException error = Throws<InvalidDataException>(() => store.Load());
            AggregateException causes = error.InnerException as AggregateException;
            check(causes != null && causes.InnerExceptions.Count == 2, "不能吞掉主档和备份两个错误");
            check(causes.InnerExceptions[0] is InvalidDataException && causes.InnerExceptions[1] is InvalidOperationException, "保留版本与schema错误来源");
            SameBytes(primary, store.SavePath, "双档失败保留主档");
            SameBytes(backup, store.SavePath + ".bak", "双档失败保留备份");
            check(store.Exists && !store.LastLoadUsedBackup, "Exists仅表明文件存在，不表明可以恢复");
        });
    }

    private static void EnvelopeValidation()
    {
        InDirectory(directory =>
        {
            JsonSessionSerializer serializer = new JsonSessionSerializer();
            SaveStore store = new SaveStore(directory, serializer);
            string payload = new JsonSessionSerializer().Serialize(GameSession.New(3).Data);
            string valid = Envelope(payload);
            string badChecksum = valid.Substring(0, valid.LastIndexOf('\n') + 1) + "被改写";
            byte[][] malformed =
            {
                new byte[0],
                Utf8.GetBytes(Envelope(payload, "0", "PROBABILITY-EDGE-SAVE-2")),
                Utf8.GetBytes(badChecksum),
                Utf8.GetBytes(Envelope(" \n\t")),
                new byte[1024 * 1024 + 1],
                new byte[] { 0xff, 0xfe, 0xfd },
                Utf8.GetBytes("PROBABILITY-EDGE-SAVE-1\n"),
                Utf8.GetBytes(Envelope(payload, "unknown"))
            };
            foreach (byte[] bytes in malformed)
            {
                File.WriteAllBytes(store.SavePath, bytes);
                Throws<InvalidDataException>(() => store.Load());
                check(serializer.DeserializeCalls == 0, "版本、大小、空内容及校验错误须在反序列化前拒绝");
                SameBytes(bytes, store.SavePath, "拒绝封装不能修改文件");
            }
            // 总文件恰好1MB可以通过尺寸门槛；它仍因校验不匹配而在反序列化前拒绝。
            byte[] boundary = Utf8.GetBytes(valid.PadRight(1024 * 1024, ' '));
            File.WriteAllBytes(store.SavePath, boundary);
            InvalidDataException error = Throws<InvalidDataException>(() => store.Load());
            check(error.InnerException.InnerException.Message.Contains("校验和"), "1MB边界不应被当作超限");
        });
    }

    private static void SchemaValidation()
    {
        InDirectory(directory =>
        {
            JsonSessionSerializer serializer = new JsonSessionSerializer();
            SaveStore store = new SaveStore(directory, serializer);
            SessionData[] invalid = new SessionData[5];
            invalid[0] = GameSession.New(1).Data; invalid[0].version = 1;
            invalid[1] = GameSession.New(1).Data; invalid[1].state.hp = -1;
            invalid[2] = AtNode(3).Data; invalid[2].state.claimedSupplies.Add(3);
            invalid[3] = AtNode(2).Data; invalid[3].battleCheckpoint = null;
            invalid[4] = AtNode(2).Data; invalid[4].state.pendingFace = 9;
            foreach (SessionData data in invalid)
            {
                bool battle = data.state.phase == "battle";
                File.WriteAllText(store.SavePath, Envelope(serializer.Serialize(data), battle ? "1" : "0"), Utf8);
                InvalidDataException error = Throws<InvalidDataException>(() => store.Load());
                AggregateException causes = error.InnerException as AggregateException;
                check(causes.InnerExceptions[0] is InvalidOperationException, "通过checksum后必须再由Restore验证schema");
            }
            File.WriteAllText(store.SavePath, Envelope("null"), Utf8);
            Throws<InvalidDataException>(() => store.Load());
            check(serializer.DeserializeCalls == invalid.Length + 1, "schema校验实际发生在反序列化之后");
        });
    }

    private static void TemporaryFailure()
    {
        InDirectory(directory =>
        {
            SaveStore store = new SaveStore(directory, new JsonSessionSerializer());
            GameSession session = GameSession.New(10);
            store.Save(session); session.Advance(); store.Save(session);
            byte[] primary = File.ReadAllBytes(store.SavePath);
            byte[] backup = File.ReadAllBytes(store.SavePath + ".bak");
            File.WriteAllText(store.SavePath + ".tmp", "已有临时文件不可覆盖", Utf8);
            byte[] temporary = File.ReadAllBytes(store.SavePath + ".tmp");
            session.Advance();
            Throws<IOException>(() => store.Save(session));
            SameBytes(primary, store.SavePath, "CreateNew失败后主档原样保留");
            SameBytes(backup, store.SavePath + ".bak", "临时写失败不能轮换备份");
            SameBytes(temporary, store.SavePath + ".tmp", "不能清理不属于本次写入的临时文件");
            File.Delete(store.SavePath + ".tmp");
            Directory.CreateDirectory(store.SavePath + ".tmp");
            Throws<Exception>(() => store.Save(session));
            SameBytes(primary, store.SavePath, "临时路径是目录时也不能覆盖旧主档");
            check(Directory.Exists(store.SavePath + ".tmp"), "不能删除已有临时目录");
        });
    }

    private static void ReplaceFailure()
    {
        InDirectory(directory =>
        {
            SaveStore store = new SaveStore(directory, new JsonSessionSerializer());
            GameSession session = GameSession.New(19);
            store.Save(session);
            byte[] primary = File.ReadAllBytes(store.SavePath);
            Directory.CreateDirectory(store.SavePath + ".bak");
            session.Advance();
            Exception error = Throws<Exception>(() => store.Save(session));
            check(error is IOException || error is UnauthorizedAccessException, "保留平台原始文件系统异常");
            SameBytes(primary, store.SavePath, "备份目标阻塞导致Replace失败，旧主档必须保留");
            check(Directory.Exists(store.SavePath + ".bak"), "不擅自删除备份路径障碍");
            check(!File.Exists(store.SavePath + ".tmp"), "清理本次已flush的临时文件");
        });
    }

    private static void SaveValidation()
    {
        InDirectory(directory =>
        {
            JsonSessionSerializer serializer = new JsonSessionSerializer();
            SaveStore store = new SaveStore(directory, serializer);
            GameSession session = GameSession.New(2);
            store.Save(session); session.Advance(); store.Save(session);
            byte[] primary = File.ReadAllBytes(store.SavePath);
            byte[] backup = File.ReadAllBytes(store.SavePath + ".bak");
            int before = serializer.SerializeCalls;
            session.Data.state.hp = -1;
            Throws<InvalidOperationException>(() => store.Save(session));
            check(serializer.SerializeCalls == before, "非法会话在序列化前由Restore拒绝");
            session.Data.state.hp = 100;
            Throws<ArgumentNullException>(() => store.Save(null));
            Exception failure = new IOException("模拟序列化故障");
            serializer.SerializeError = failure;
            check(ReferenceEquals(failure, Throws<IOException>(() => store.Save(session))), "原始异常不吞掉或替换");
            serializer.SerializeError = null;
            serializer.OverridePayload = true;
            foreach (string payload in new[] { null, "", " \n\t", new string('中', 400000), new string('x', 1024 * 1024) })
            {
                serializer.Payload = payload;
                Throws<InvalidDataException>(() => store.Save(session));
                SameBytes(primary, store.SavePath, "空内容或超限不触碰主档");
                SameBytes(backup, store.SavePath + ".bak", "校验失败不触碰备份");
                check(!File.Exists(store.SavePath + ".tmp"), "序列化校验失败不生成临时文件");
            }
            SameBytes(primary, store.SavePath, "非法会话与序列化故障均保留旧档");
        });
    }

    private static uint SeedFor(int face)
    {
        for (uint seed = 1; seed < 10000; seed++)
        {
            uint next = seed;
            next ^= next << 13; next ^= next >> 17; next ^= next << 5;
            if (next >= 6 && next % 10 == face) return seed;
        }
        throw new Exception("找不到骰面种子。");
    }

    private static void ForceFace(GameSession session, int face)
    {
        session.Data.state.rngState = SeedFor(face);
        check(session.Roll() == face, "指定种子骰面一致");
    }

    // 新内核50节点：首个战斗index2、首个奖励补给index6；战斗用固定枪击清场，奖励统一强化剑。
    private static GameSession AtNode(int index)
    {
        GameSession session = GameSession.New(12345);
        for (int step = 0; session.Data.state.nodeIndex != index && step < 5000; step++)
        {
            GameState state = session.Data.state;
            if (state.phase == "battle")
            {
                if (state.pendingFace != -1)
                {
                    foreach (EnemyState enemy in state.enemies)
                        if (enemy.hp > 0) { session.ChooseTarget(enemy.id); break; }
                }
                else if (state.rollsLeft == 0) session.EndTurn();
                else ForceFace(session, GameSession.ShotFace);
            }
            else if (state.phase == "supply")
            {
                if (!state.supplyClaimed) session.ClaimSupply();
                else if (session.CurrentNode.reward && !session.CurrentUpgradeChosen) session.Upgrade("sword");
                else session.Advance();
            }
            else if (state.phase == "event") session.ResolveEvent(false);
            else session.Advance();
        }
        check(session.Data.state.nodeIndex == index, "到达测试节点");
        return session;
    }

    private static void SupplyRoundTrip()
    {
        foreach (int node in new[] { 3, 6, 12, 47 })
        {
            InDirectory(directory =>
            {
                SaveStore store = new SaveStore(directory, new JsonSessionSerializer());
                GameSession session = AtNode(node);
                bool reward = session.CurrentNode.reward;
                session.Data.state.hp = 60;
                check(session.ClaimSupply(), "首次补给成功");
                if (reward)
                {
                    store.Save(session);
                    GameSession pending = new SaveStore(directory, new JsonSessionSerializer()).Load();
                    SameSession(session, pending, "已领取未强化的奖励补给完整往返");
                    Throws<InvalidOperationException>(() => pending.Advance());
                    session.Upgrade("shot");
                }
                store.Save(session);
                GameSession loaded = new SaveStore(directory, new JsonSessionSerializer()).Load();
                SameSession(session, loaded, "已领取补给与奖励完整往返");
                string before = new JsonSessionSerializer().Serialize(loaded.Data);
                check(!loaded.ClaimSupply(), "重开后重复补给被拒绝");
                check(before == new JsonSessionSerializer().Serialize(loaded.Data), "重复领取不改变生命、日志或进度");
                Throws<InvalidOperationException>(() => loaded.Upgrade("shot"));
                check(before == new JsonSessionSerializer().Serialize(loaded.Data), "重复或非法强化不改变状态");
                loaded.Advance(); store.Save(loaded);
                SameSession(loaded, store.Load(), "领取后推进仍可再次存读");
                check(store.Load().Data.state.claimedSupplies.Contains(node), "领取记录跨重开保留");
            });
        }
    }

    private static void PendingRoundTrip()
    {
        foreach (int face in new[] { 2, 9 })
        {
            InDirectory(directory =>
            {
                GameSession session = AtNode(2);
                ForceFace(session, face);
                SaveStore store = new SaveStore(directory, new JsonSessionSerializer());
                store.Save(session);
                GameSession loaded = new SaveStore(directory, new JsonSessionSerializer()).Load();
                SameSession(session, loaded, "pending、剩余次数、日志、随机状态和checkpoint全部往返");
                check(loaded.Data.state.pendingFace == face && loaded.Data.state.pendingSkill == (face == 9 ? "shot" : "sword"), "保留真实待选骰面与技能");
                Throws<InvalidOperationException>(() => loaded.Roll());
                Throws<InvalidOperationException>(() => loaded.EndTurn());
                session.ChooseTarget(1); loaded.ChooseTarget(1);
                check(session.Roll() == loaded.Roll(), "选目标后的下一投确定性一致");
                SameSession(session, loaded, "恢复不会消耗随机数或重算动作");
            });
        }
    }

    private static void DefeatRoundTrip()
    {
        InDirectory(directory =>
        {
            GameSession session = AtNode(2);
            GameState checkpoint = GameSession.Clone(session.Data.battleCheckpoint);
            ForceFace(session, GameSession.ShotFace);
            session.ChooseTarget(1);
            session.Data.state.hp = 1;
            session.EndTurn();
            check(session.Data.state.phase == "defeat", "构造合法失败状态");
            SaveStore store = new SaveStore(directory, new JsonSessionSerializer());
            store.Save(session);
            GameSession loaded = new SaveStore(directory, new JsonSessionSerializer()).Load();
            GameSession twin = new SaveStore(directory, new JsonSessionSerializer()).Load();
            SameSession(session, loaded, "失败状态和战前检查点完整重开");
            loaded.ResetBattle();
            twin.ResetBattle();
            SameSession(twin, loaded, "重开后的重试结果确定");
            GameState state = loaded.Data.state;
            check(state.phase == "battle" && state.battleRetries == 1, "重试次数递增并回到战斗");
            check(state.hp == checkpoint.hp && state.enemies[0].hp == checkpoint.enemies[0].hp && state.turn == 1 && state.rollsLeft == 3, "重试精确返回战前生命与敌人");
            check(state.rngState != checkpoint.rngState, "重试重新洗牌骰子序列");
            check(loaded.Data.battleCheckpoint.rngState == checkpoint.rngState, "检查点本身不变");
            store.Save(loaded);
            GameSession reopened = new SaveStore(directory, new JsonSessionSerializer()).Load();
            SameSession(loaded, reopened, "重试后状态可再次存读");
            check(loaded.Roll() == reopened.Roll(), "重试后的下一投跨重开一致");
        });
    }

    private static void NestedNullRoundTrip()
    {
        InDirectory(directory =>
        {
            JsonSessionSerializer serializer = new JsonSessionSerializer { MaterializeNullCheckpoint = true };
            SaveStore store = new SaveStore(directory, serializer);
            foreach (int node in new[] { 0, 1, 3, 4, 6, 7, 13, 49, 2, 5, 8, 46 })
            {
                GameSession session = AtNode(node);
                if (node == 4) session.ResolveEvent(true);
                if (node == 6) session.ClaimSupply();
                store.Save(session);
                SameSession(session, store.Load(), "模拟JsonUtility空对象还原时仍精确恢复节点" + node);
                check((store.Load().Data.battleCheckpoint == null) == (session.Data.battleCheckpoint == null), "检查点存在标记不丢失");
            }
            GameSession battle = AtNode(2);
            File.WriteAllText(store.SavePath, Envelope(serializer.Serialize(battle.Data), "0"), Utf8);
            File.WriteAllText(store.SavePath + ".bak", "无有效备份", Utf8);
            Throws<InvalidDataException>(() => store.Load());
            battle.Data.battleCheckpoint = null;
            Throws<InvalidOperationException>(() => store.Save(battle));
            GameSession story = GameSession.New(1);
            story.Data.battleCheckpoint = new GameState();
            Throws<InvalidOperationException>(() => store.Save(story));
        });
    }
}
