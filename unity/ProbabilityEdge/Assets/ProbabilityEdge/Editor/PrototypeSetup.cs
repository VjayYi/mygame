using System;
using System.IO;
using ProbabilityEdge.Core;
using ProbabilityEdge.Runtime;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace ProbabilityEdge.Editor
{
    public static class PrototypeSetup
    {
        public const string ScenePath = "Assets/ProbabilityEdge/Scenes/Prototype.unity";

        [MenuItem("Probability Edge/Prepare Prototype")]
        public static void Prepare()
        {
            if (!File.Exists(ScenePath))
            {
                if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
                Directory.CreateDirectory("Assets/ProbabilityEdge/Scenes");
                var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                var go = new GameObject("ProbabilityEdge Prototype");
                go.AddComponent<PrototypeRunner>();
                EditorSceneManager.SaveScene(scene, ScenePath);
                AssetDatabase.Refresh();
            }
            var scenes = new System.Collections.Generic.List<EditorBuildSettingsScene>(EditorBuildSettings.scenes);
            if (!scenes.Exists(s => s.path == ScenePath)) scenes.Add(new EditorBuildSettingsScene(ScenePath, true));
            EditorBuildSettings.scenes = scenes.ToArray();
            PlayerSettings.companyName = "Independent Prototype";
            PlayerSettings.productName = "Probability Edge Prototype";
            PlayerSettings.defaultScreenWidth = 1280;
            PlayerSettings.defaultScreenHeight = 800;
            PlayerSettings.resizableWindow = true;
            PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
        }

        [MenuItem("Probability Edge/Run Serialization Smoke Test")]
        public static void SmokeTest()
        {
            var serializer = new UnitySessionSerializer();
            string dir = Path.Combine(Path.GetTempPath(), "ProbabilityEdgeSmoke-" + Guid.NewGuid().ToString("N"));
            var store = new SaveStore(dir, serializer);
            var session = GameSession.New(20261015);
            store.Save(session);
            Assert(store.Load().Data.state.nodeIndex == 0, "首次存档恢复");
            session.Advance(); session.Advance();
            int steps = 0;
            while (session.Data.state.phase == "battle")
            {
                Assert(++steps < 1000, "首战没有无限循环");
                var s = session.Data.state;
                if (s.pendingFace >= 0) session.ChooseTarget(1);
                else if (s.rollsLeft > 0) session.Roll();
                else session.EndTurn();
                Assert(session.Data.state.phase != "defeat", "首战正常推进");
                store.Save(session);
                session = store.Load();
            }
            Assert(session.Data.state.phase == "supply", "战后补给");
            session.ClaimSupply(); store.Save(session);
            session = store.Load();
            Assert(!session.ClaimSupply(), "补给幂等");
            session.Advance(); session.ResolveEvent(true); store.Save(session);
            int roll = session.Data.state.eventRolls[4];
            session = store.Load();
            Assert(session.Data.state.eventRolls[4] == roll && session.Data.state.phase == "eventResult", "D20结果恢复");

            // 用 Unity JsonUtility 真实存读，逐动作打通整个第一章（含战败重试）。
            int actions = 0, retries = 0;
            while (session.Data.state.phase != "completed")
            {
                Assert(++actions < 20000, "全章没有无限循环");
                var s = session.Data.state;
                if (s.phase == "story" || s.phase == "eventResult") session.Advance();
                else if (s.phase == "choice") session.Advance(actions % session.CurrentNode.choices.Length);
                else if (s.phase == "event") session.ResolveEvent(actions % 2 == 0);
                else if (s.phase == "supply")
                {
                    if (!s.supplyClaimed) session.ClaimSupply();
                    else if (session.CurrentNode.reward && !session.CurrentUpgradeChosen) session.Upgrade(actions % 2 == 0 ? "sword" : "shield");
                    else session.Advance();
                }
                else if (s.phase == "defeat") { retries++; session.ResetBattle(); }
                else if (s.pendingFace >= 0)
                {
                    foreach (var enemy in s.enemies) if (enemy.hp > 0) { session.ChooseTarget(enemy.id); break; }
                }
                else if (s.rollsLeft > 0) session.Roll();
                else session.EndTurn();
                string before = serializer.Serialize(session.Data);
                store.Save(session);
                session = store.Load();
                Assert(serializer.Serialize(session.Data) == before, "JsonUtility逐动作存读一致");
            }
            Assert(session.Data.state.claimedSupplies.Count == 12 && session.Data.state.upgradedNodes.Count == 7, "全章补给与强化次数");
            Debug.Log("PROBABILITY_EDGE_UNITY_SMOKE_PASS: JsonUtility逐动作存读打通第一章50节点，动作" + actions + "次，战败重试" + retries + "次，章末生命" + session.Data.state.hp + "。");
        }

        public const string PlaytestVersion = "0.2.0";

        public static void BuildMac() { Build(BuildTarget.StandaloneOSX, "Builds/macOS/ProbabilityEdge.app", BuildOptions.Development); }

        // 给朋友测试的正式包：无 Development 水印与调试连接。
        public static void BuildMacPlaytest() { Build(BuildTarget.StandaloneOSX, "Builds/Playtest-macOS/ProbabilityEdge-Chapter1.app", BuildOptions.None); }
        public static void BuildWindowsPlaytest() { Build(BuildTarget.StandaloneWindows64, "Builds/Playtest-Windows/ProbabilityEdge-Chapter1/ProbabilityEdge.exe", BuildOptions.None); }

        private static void Build(BuildTarget target, string path, BuildOptions options)
        {
            Prepare();
            if (!File.Exists(ScenePath)) throw new Exception("原型场景尚未准备好，构建取消。");
            PlayerSettings.bundleVersion = PlaytestVersion;
            SmokeTest();
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = new[] { ScenePath },
                locationPathName = path,
                target = target,
                options = options
            });
            if (report.summary.result != UnityEditor.Build.Reporting.BuildResult.Succeeded)
                throw new Exception(target + " build failed: " + report.summary.result);
        }
        private static void Assert(bool condition, string name)
        { if (!condition) throw new Exception("Unity烟测失败：" + name); }
    }
}
