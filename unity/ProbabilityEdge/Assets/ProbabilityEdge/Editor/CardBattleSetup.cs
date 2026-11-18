using System;
using System.IO;
using System.Linq;
using ProbabilityEdge.Core.Cards;
using ProbabilityEdge.Runtime;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace ProbabilityEdge.Editor
{
    // 卡牌战斗文字测试版：场景准备、编辑器内烟测、打包。旧的骰子原型 PrototypeSetup 保持不动。
    public static class CardBattleSetup
    {
        public const string ScenePath = "Assets/ProbabilityEdge/Scenes/CardBattle.unity";
        public const string Version = "0.3.0-card";

        [MenuItem("Probability Edge/Prepare Card Battle")]
        public static void Prepare()
        {
            if (!File.Exists(ScenePath))
            {
                Directory.CreateDirectory("Assets/ProbabilityEdge/Scenes");
                var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                var go = new GameObject("CardBattle Runner");
                go.AddComponent<CardBattleRunner>();
                EditorSceneManager.SaveScene(scene, ScenePath);
                AssetDatabase.Refresh();
            }
            var scenes = EditorBuildSettings.scenes.Where(s => s.path != ScenePath).ToList();
            scenes.Insert(0, new EditorBuildSettingsScene(ScenePath, true)); // 卡牌版放第一个，打包后默认进入
            EditorBuildSettings.scenes = scenes.ToArray();
            PlayerSettings.companyName = "Independent Prototype";
            PlayerSettings.productName = "Probability Edge Card Battle";
            PlayerSettings.defaultScreenWidth = 1280;
            PlayerSettings.defaultScreenHeight = 800;
            PlayerSettings.resizableWindow = true;
            PlayerSettings.fullScreenMode = FullScreenMode.Windowed;
        }

        [MenuItem("Probability Edge/Run Card Battle Smoke Test")]
        public static void SmokeTest()
        {
            var ta = AssetDatabase.LoadAssetAtPath<TextAsset>("Assets/ProbabilityEdge/Resources/CardData/cardpool.json");
            if (ta == null) throw new Exception("找不到 cardpool.json");
            var pool = CardPool.Parse(ta.text);
            if (pool.modules.Count != 240 || pool.weapons.Count != 27) throw new Exception("卡池数量不对");
            int fights = 0, wins = 0;
            foreach (var cat in CardPool.Cats)
                foreach (var form in CardPool.Forms)
                {
                    var spec = BuildSpec.Create(pool, cat, form, 7);
                    spec.Randomize(pool, 11, true);
                    var d = DeckBuilder.Build(pool, spec, 4, 3);
                    var f = new Fight(d.cards, Encounters.Make("elite", 173, 11), 5, d.passive);
                    var r = f.Run();
                    fights++;
                    if (r.Value) wins++;
                }
            foreach (var m in MemeCards.Names)
            {
                var d = DeckBuilder.Build(pool, BuildSpec.CreateMeme(pool, m, 1), 4, 3);
                var f = new Fight(d.cards, Encounters.Make("mini", 250, 10), 5, d.passive);
                f.Run();
                fights++;
            }
            Debug.Log("PROBABILITY_EDGE_CARD_SMOKE_PASS: 卡池 " + pool.modules.Count + " 个模块，" + fights + " 场战斗跑完，普通武器精英战胜 " + wins + "/27。");
        }

        public static void BuildMac() { Build(BuildTarget.StandaloneOSX, "Builds/CardBattle-macOS/ProbabilityEdge-CardBattle.app"); }
        public static void BuildWindows() { Build(BuildTarget.StandaloneWindows64, "Builds/CardBattle-Windows/ProbabilityEdge-CardBattle/ProbabilityEdge.exe"); }

        private static void Build(BuildTarget target, string path)
        {
            Prepare();
            SmokeTest();
            PlayerSettings.bundleVersion = Version;
            Directory.CreateDirectory(Path.GetDirectoryName(path));
            var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
            {
                scenes = new[] { ScenePath },
                locationPathName = path,
                target = target,
                options = BuildOptions.None
            });
            if (report.summary.result != UnityEditor.Build.Reporting.BuildResult.Succeeded)
                throw new Exception(target + " build failed: " + report.summary.result);
        }
    }
}
