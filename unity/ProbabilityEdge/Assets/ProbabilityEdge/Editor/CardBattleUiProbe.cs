using System;
using System.Reflection;
using ProbabilityEdge.Runtime;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace ProbabilityEdge.Editor
{
    // 无人值守界面探测：进入播放模式，驱动界面状态机走完 构筑 → 各标签 → 开战 → 自动打完 → 结果，捕获所有运行时异常。
    [InitializeOnLoad]
    public static class CardBattleUiProbe
    {
        private const string Key = "CardBattleUiProbe.Active";
        private static int frames;
        private static CardBattleRunner runner;
        private static readonly System.Collections.Generic.List<string> Errors = new System.Collections.Generic.List<string>();

        static CardBattleUiProbe()
        {
            if (SessionState.GetBool(Key, false)) EditorApplication.playModeStateChanged += OnState;
        }

        public static void Run()
        {
            SessionState.SetBool(Key, true);
            EditorSceneManager.OpenScene(CardBattleSetup.ScenePath);
            Application.logMessageReceived += OnLog;
            EditorApplication.playModeStateChanged += OnState;
            EditorApplication.isPlaying = true;
        }

        private static void OnLog(string msg, string stack, LogType type)
        {
            if (type == LogType.Exception || type == LogType.Error) Errors.Add(type + ": " + msg + "\n" + stack);
        }

        private static void OnState(PlayModeStateChange s)
        {
            if (s == PlayModeStateChange.EnteredPlayMode)
            {
                Application.logMessageReceived += OnLog;
                runner = UnityEngine.Object.FindObjectOfType<CardBattleRunner>();
                frames = 0;
                EditorApplication.update += Tick;
            }
        }

        private static object Get(string f) { return typeof(CardBattleRunner).GetField(f, BindingFlags.NonPublic | BindingFlags.Instance).GetValue(runner); }
        private static void Set(string f, object v) { typeof(CardBattleRunner).GetField(f, BindingFlags.NonPublic | BindingFlags.Instance).SetValue(runner, v); }
        private static void Call(string m, params object[] a) { typeof(CardBattleRunner).GetMethod(m, BindingFlags.NonPublic | BindingFlags.Instance).Invoke(runner, a); }

        private static void Tick()
        {
            frames++;
            try
            {
                if (runner == null) throw new Exception("找不到 CardBattleRunner");
                if (frames == 20) Set("tab", Enum.ToObject(typeof(CardBattleRunner).GetNestedType("Tab", BindingFlags.NonPublic), 1));
                if (frames == 40) Set("tab", Enum.ToObject(typeof(CardBattleRunner).GetNestedType("Tab", BindingFlags.NonPublic), 2));
                if (frames == 60) Set("memeMode", true);
                if (frames == 80) Set("memeMode", false);
                if (frames == 100) Set("tab", Enum.ToObject(typeof(CardBattleRunner).GetNestedType("Tab", BindingFlags.NonPublic), 3));
                if (frames == 120) Call("StartBattle");
                if (frames == 150) Set("autoAll", true);
                if (frames > 150 && frames % 20 == 0)
                {
                    var screen = Get("screen").ToString();
                    if (screen == "Battle" && Get("fight") != null) { try { Call("EndTurn"); } catch (Exception) { throw; } }
                }
                if (frames == 400)
                {
                    Debug.Log("CARD_UI_PROBE: screen=" + Get("screen") + " errors=" + Errors.Count);
                    Finish();
                }
            }
            catch (Exception e) { Errors.Add("探测异常：" + e); Finish(); }
        }

        private static void Finish()
        {
            EditorApplication.update -= Tick;
            foreach (var e in Errors) Debug.Log("CARD_UI_PROBE_ERROR: " + e);
            Debug.Log(Errors.Count == 0 ? "CARD_UI_PROBE_PASS" : "CARD_UI_PROBE_FAIL");
            SessionState.SetBool(Key, false);
            EditorApplication.Exit(Errors.Count == 0 ? 0 : 1);
        }
    }
}
