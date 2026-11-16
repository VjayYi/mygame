using ProbabilityEdge.Core;
using UnityEngine;

namespace ProbabilityEdge.Runtime
{
    public sealed class UnitySessionSerializer : ISessionSerializer
    {
        public string Serialize(SessionData data) { return JsonUtility.ToJson(data, true); }
        public SessionData Deserialize(string json) { return JsonUtility.FromJson<SessionData>(json); }
    }
}
