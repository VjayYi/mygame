using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace ProbabilityEdge.Core
{
    public interface ISessionSerializer
    {
        string Serialize(SessionData data);
        SessionData Deserialize(string json);
    }

    public sealed class SaveStore
    {
        private const string Header = "PROBABILITY-EDGE-SAVE-1";
        private const int MaxFileBytes = 1024 * 1024;
        private static readonly UTF8Encoding Utf8 = new UTF8Encoding(false, true);
        private readonly ISessionSerializer serializer;

        public string SavePath { get; }
        public bool Exists => File.Exists(SavePath) || File.Exists(BackupPath);
        public bool LastLoadUsedBackup { get; private set; }
        public string LastLoadWarning { get; private set; } = "";

        private string BackupPath => SavePath + ".bak";
        private string TemporaryPath => SavePath + ".tmp";

        public SaveStore(string directory, ISessionSerializer serializer)
        {
            if (string.IsNullOrWhiteSpace(directory)) throw new ArgumentException("存档目录不能为空。", "directory");
            if (serializer == null) throw new ArgumentNullException("serializer");
            SavePath = Path.Combine(Path.GetFullPath(directory), "session.sav");
            this.serializer = serializer;
        }

        public void Save(GameSession session)
        {
            if (session == null) throw new ArgumentNullException("session");
            SessionData validated = GameSession.Restore(session.Data).Data;
            string payload = serializer.Serialize(validated);
            ValidatePayload(payload);
            // 第三行明确记录 null；JsonUtility 可能把嵌套 null 还原成默认对象。
            string checkpoint = validated.battleCheckpoint == null ? "0" : "1";
            byte[] bytes = Utf8.GetBytes(Header + "\n" + Checksum(payload) + "\n" + checkpoint + "\n" + payload);
            if (bytes.Length > MaxFileBytes) throw new InvalidDataException("存档不能超过1MB。");

            Directory.CreateDirectory(Path.GetDirectoryName(SavePath));
            bool ownsTemporary = false;
            try
            {
                using (FileStream stream = new FileStream(TemporaryPath, FileMode.CreateNew, FileAccess.Write, FileShare.None))
                {
                    ownsTemporary = true;
                    stream.Write(bytes, 0, bytes.Length);
                    stream.Flush(true);
                }
                // 不支持 File.Replace 的平台直接报错，不退化为删除旧档后覆盖。
                if (File.Exists(SavePath)) File.Replace(TemporaryPath, SavePath, BackupPath);
                else File.Move(TemporaryPath, SavePath);
            }
            catch (Exception writeError)
            {
                if (ownsTemporary)
                {
                    try { File.Delete(TemporaryPath); }
                    catch (Exception cleanupError)
                    {
                        throw new IOException("存档写入失败，且临时文件清理失败；请保留原存档。",
                            new AggregateException(writeError, cleanupError));
                    }
                }
                throw;
            }
        }

        public GameSession Load()
        {
            LastLoadUsedBackup = false;
            LastLoadWarning = "";
            Exception primaryError;
            try { return ReadSession(SavePath); }
            catch (Exception error) { primaryError = error; }

            try
            {
                GameSession recovered = ReadSession(BackupPath);
                LastLoadUsedBackup = true;
                LastLoadWarning = "主存档读取失败，已从备份只读恢复；主存档未被覆盖。原因：" + primaryError.Message;
                return recovered;
            }
            catch (Exception backupError)
            {
                AggregateException errors = new AggregateException(primaryError, backupError);
                if (Missing(primaryError) && Missing(backupError))
                    throw new FileNotFoundException("主存档与备份均不存在；没有创建新会话或写入文件。", SavePath, errors);
                throw new InvalidDataException("主存档与备份均无法恢复；原文件已保留。", errors);
            }
        }

        private GameSession ReadSession(string path)
        {
            byte[] bytes;
            using (FileStream stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read))
            {
                if (stream.Length == 0 || stream.Length > MaxFileBytes)
                    throw new InvalidDataException("存档为空或超过1MB。");
                bytes = new byte[(int)stream.Length];
                int offset = 0;
                while (offset < bytes.Length)
                {
                    int read = stream.Read(bytes, offset, bytes.Length - offset);
                    if (read == 0) throw new InvalidDataException("存档读取不完整。");
                    offset += read;
                }
                if (stream.ReadByte() != -1) throw new InvalidDataException("存档在读取期间发生变化。");
            }

            string envelope = Utf8.GetString(bytes);
            int first = envelope.IndexOf('\n');
            int second = first < 0 ? -1 : envelope.IndexOf('\n', first + 1);
            int third = second < 0 ? -1 : envelope.IndexOf('\n', second + 1);
            if (first < 0 || envelope.Substring(0, first) != Header)
                throw new InvalidDataException("存档格式版本未知或文件头无效。");
            if (second < 0 || third < 0) throw new InvalidDataException("存档封装不完整。");
            string checksum = envelope.Substring(first + 1, second - first - 1);
            string checkpoint = envelope.Substring(second + 1, third - second - 1);
            if (checkpoint != "0" && checkpoint != "1") throw new InvalidDataException("检查点存在标记无效。");
            string payload = envelope.Substring(third + 1);
            ValidatePayload(payload);
            if (!string.Equals(checksum, Checksum(payload), StringComparison.Ordinal))
                throw new InvalidDataException("存档校验和不匹配。");

            SessionData data = serializer.Deserialize(payload);
            if (data != null && data.state != null)
            {
                bool inBattle = data.state.phase == "battle" || data.state.phase == "defeat";
                if (inBattle != (checkpoint == "1")) throw new InvalidDataException("检查点标记与会话阶段不一致。");
                if (checkpoint == "0") data.battleCheckpoint = null;
            }
            return GameSession.Restore(data);
        }

        private static void ValidatePayload(string payload)
        {
            if (string.IsNullOrWhiteSpace(payload)) throw new InvalidDataException("序列化内容不能为空。");
            if (Utf8.GetByteCount(payload) > MaxFileBytes) throw new InvalidDataException("存档不能超过1MB。");
        }

        private static string Checksum(string payload)
        {
            using (SHA256 sha = SHA256.Create())
            {
                byte[] hash = sha.ComputeHash(Utf8.GetBytes(payload));
                StringBuilder result = new StringBuilder(hash.Length * 2);
                foreach (byte value in hash) result.Append(value.ToString("x2"));
                return result.ToString();
            }
        }

        private static bool Missing(Exception error)
        {
            return error is FileNotFoundException || error is DirectoryNotFoundException;
        }
    }
}
