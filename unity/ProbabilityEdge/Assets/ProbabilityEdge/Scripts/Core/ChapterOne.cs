using System;
using System.Collections.Generic;

namespace ProbabilityEdge.Core
{
    // 第一章《出逃》数据：5关×10节点。文本与数值来自 outputs/story-chapter-1-v0.1.md，均为测试候选值。
    public sealed class NodeDef
    {
        public string id;
        public string title;
        public string text;
        public string kind;          // story / choice / battle / supply / event / ending
        public string[] choices = new string[0];
        public string[] responses = new string[0];
        public string[] enemies = new string[0];
        public int heal;
        public bool reward;
        public int eventIndex = -1;
        public string evidence = "";
    }

    public sealed class EventDef
    {
        public string safeLabel, riskLabel;
        public int safeDelta, critDelta, successDelta, failDelta, fumbleDelta;
        public string safeText, critText, successText, failText, fumbleText;
    }

    public sealed class EnemyTemplate
    {
        public string kind, name;
        public int hp;
        public string[] actions;     // attack:N / shield:N / charge / wait
    }

    public static class ChapterOne
    {
        public const int NodeCount = 50;
        private static readonly NodeDef[] nodes = BuildNodes();
        private static readonly EventDef[] events = BuildEvents();
        private static readonly Dictionary<string, EnemyTemplate> templates = BuildTemplates();

        public static NodeDef Node(int index)
        {
            if (index < 0 || index >= NodeCount) throw new ArgumentOutOfRangeException("index");
            return nodes[index];
        }
        public static EventDef Event(int eventIndex) { return events[eventIndex]; }
        public static EnemyTemplate Template(string kind) { return templates[kind]; }
        public static int StageOf(int index) { return index / 10 + 1; }
        public static int StepOf(int index) { return index % 10 + 1; }

        private static NodeDef Story(string title, string text, string evidence = "")
        { return new NodeDef { title = title, text = text, kind = "story", evidence = evidence }; }
        private static NodeDef Choice(string title, string text, string[] choices, string[] responses, string evidence = "")
        { return new NodeDef { title = title, text = text, kind = "choice", choices = choices, responses = responses, evidence = evidence }; }
        private static NodeDef Battle(string title, string text, params string[] enemies)
        { return new NodeDef { title = title, text = text, kind = "battle", enemies = enemies }; }
        private static NodeDef Supply(string title, string text, int heal, bool reward)
        { return new NodeDef { title = title, text = text, kind = "supply", heal = heal, reward = reward }; }
        private static NodeDef EventNode(string title, string text, int eventIndex)
        { return new NodeDef { title = title, text = text, kind = "event", eventIndex = eventIndex }; }

        private static NodeDef[] BuildNodes()
        {
            NodeDef[] list =
            {
                // 第一关：隔离走廊
                Story("门外", "白灯闪烁，门内仍有固定手腕的装置。\n广播：“样本17偏离观察区。请保持原位。”\n你看一眼门内：“我不回去了。”\n\n你刚离开关押室，但尚未离开集团设施。"),
                Choice("观察窗", "观察窗后还有被关押的人。你试着开门，隔离门却无法从这里打开。\n窗内的人指向墙角的维护口。\n\n这个回应只记录态度，不改变属性，也不封死后续救援。",
                    new[] { "“我会找人。”", "“先找到出口。”" },
                    new[] { "你对窗内的人点头：我会找人回来。", "你低声说：先找到出口，才有办法回来。" }),
                Battle("第一道拦截", "巡检机挡住走廊，红灯扫过你的编号。\n每回合最多投三次：剑和枪击需要选择目标，盾与心立即生效。敌人的下一步行动会提前显示。", "patrol"),
                Supply("洗消间", "你躲进洗消间，在柜内找到急救材料。\n包装上写着“耗材”，柜里却没有一件是为逃出去的人准备的。\n\n补给恢复最多10点生命，不超过上限。", 10, false),
                EventNode("断开的维护门", "门后传来岑芜的声音：“别硬扳，门轴断了会把整条通道封住。”\n可以慢慢拆开，也可以迅速打开寻找备用急救包。\n\n冒险D20：20恢复12；12～19无损；2～11失去4；1失去8。探索伤害至少保留1生命，任何结果都能继续。", 0),
                Battle("束缚装置", "束缚器从天花板降下。它会先进入准备，再释放强力束缚攻击。\n看清它的预告，提前用盾抵挡。", "binder"),
                Supply("维修凳", "岑芜递出工具：“手抖就坐一会儿。它们坏得起，你不行。”\n你问：“你知道里面是什么？”\n她说：“知道一点。够我不把你送回去。”\n\n恢复最多8生命，并强化一个已携带技能+2；只作用于本次流程，不换面。", 8, true),
                Story("交接记录", "记录上有你的编号、受限行动范围和“回收”一栏。\n岑芜：“我能留下记录，但开不了这里所有的门。”\n\n你带走初步的关押记录。它不是集团全部罪证。", "关押记录"),
                Battle("走廊封锁", "巡检机和安保员同时出现。一个持续低伤害，一个会蓄力后重击。\n先处理谁，由你决定。", "patrol", "security"),
                Supply("临时安全门", "岑芜关上维护门，递给你一件外套：“先别让他们隔着玻璃就认出你。”\n你回看观察区：“那边还关着人。”\n她说：“我留了记录。你活着出去，才有人知道。”\n\n恢复最多10生命。", 10, false),

                // 第二关：维护夹层
                Story("照明之外", "维护夹层狭窄闷热，管线之间夹着发热的术式纹路。\n岑芜：“机器坏了可以换。术式坏了，先得找会读它的人。”\n你记下方位，沿夹层继续前进。"),
                Battle("夹层巡检", "夹层尽头，巡检机和束缚器同时启动。\n岑芜退到门后：“我帮不上手，别逞强。”", "patrol", "binder"),
                Supply("检修平台", "岑芜把备用药布放在平台上：“这包不是免费的——不是要你还钱，别把命扔在我看不见的地方。”\n\n恢复最多10生命，并强化一个已携带技能+2。", 10, true),
                EventNode("救护箱", "一只完整的救护箱挂在松动的支架上。\n可以直接取出基础材料，也可以先加固支架再取，争取更多补给。\n\n安全：恢复8。冒险D20：20恢复16；12～19恢复12；2～11只恢复4；1支架倾倒，失去4。", 1),
                Choice("帮忙的理由", "你说：“帮我，他们会找你。”\n岑芜：“我的工友上个月被换了工牌。人没回来，工单倒是结了。”",
                    new[] { "“我会记住。”", "“我现在保证不了什么。”" },
                    new[] { "你说：我会记住。岑芜没有回答，只把工具递给你。", "你说：我现在保证不了什么。岑芜点头：先出去再说。" }),
                Choice("留下一扇门", "岑芜要给仍被扣留的同事留下撤离方向。\n无论你怎么选，她都会完成自己的工作；区别只在之后的回信。",
                    new[] { "帮她设置醒目标记", "先确认自己的出口" },
                    new[] { "你帮她在门框上留下只有维修工认得的标记。", "你先确认出口方向，岑芜独自留下了标记。" }),
                Story("通道尽头", "监测灯由远及近。透过百叶，你看到一辆转运车停在后场。\n出口通向集团后场，而不是普通街道。堵住出口的安保必须先清掉。"),
                Battle("术式巡守", "术式安保先展开护盾，再用短促的术式攻击。\n敌人的护盾会先吸收你的伤害，但它不是无敌的。", "mage", "patrol"),
                Supply("工具车", "岑芜在工具车边替你处理擦伤：“下一扇门外，就不是你熟悉的地方了。”\n你说：“那总比里面好。”\n\n恢复最多10生命，并强化一个已携带技能+2。", 10, true),
                Story("转运班次", "广播响起：回收小队接管后场。\n岑芜塞给你一个联络方式：“余砚。他修坏东西，也接走错门的人。”\n你得到了下一个目的地。"),

                // 第三关：转运库
                Choice("箱号和人名", "转运库里，箱体只有编号，夹在纸质记录里的却是人的名字。\n你拿自己的编号一一对照。这份名单不是全部，但足够证明有人被当作货物运走。",
                    new[] { "抄录名单", "带走一页" },
                    new[] { "你把名单抄在袖口内侧。", "你撕下一页，折好放进外套。" }, "转运记录"),
                Story("撤离目标", "岑芜确认工友能走员工通道，她将和你分头撤离。\n值守室里，一名运输工被当作普通货物锁着。他还能走，但门外有人看守。"),
                Battle("装卸岗", "安保员和束缚器守着值守室。\n清掉它们，运输工就能自己离开。", "security", "binder"),
                Supply("值守室", "运输工把藏起的药包交给你：“我不知道你是谁。但他们喊你编号的时候，我知道不能开门让他们进来。”\n他沿另一条路离开。\n\n恢复最多12生命，并强化一个已携带技能+2。", 12, true),
                EventNode("报废补给盒", "一只贴着污染标识的报废盒卡在货架底下。\n可以放弃，也可以冒险检查里面有没有完好的备用包。\n\n安全：无收益无损失。冒险D20：20恢复16；12～19恢复8；2～11失去4；1失去8。", 2),
                Battle("精英锁卫", "一名重装安保挡在库门前。它会先架起护盾，再蓄力重击。\n只有一个目标，但压力最大。", "elite"),
                Supply("挡风棚", "分开前，岑芜分出最后一份急救材料：“工单写我进来修门。出去的时候，我就当自己确实修好了一扇。”\n她走员工通道离开，接下来你要独自行动。\n\n恢复最多10生命。", 10, false),
                Choice("带出记录", "广播里的回收命令写着：样本17与转运资料。\n记录已经在你身上。你带着它的理由是什么？",
                    new[] { "把记录交给可信的人", "先保住自己" },
                    new[] { "你决定把记录交给可信的人。", "你决定先保住自己，记录也一起带走。" }),
                Battle("后场出口", "术式安保和安保员封住后场出口。\n冲过去，外面就是旧城。", "mage", "security"),
                Supply("真正的夜风", "你在废弃候车棚里打开运输工留下的小包。集团的白灯退到身后，远处仍能看见它的标识。\n你说：“原来外面也有他们的灯。”\n\n恢复最多10生命，并强化一个已携带技能+2。", 10, true),

                // 第四关：旧城接应
                Story("没有登记的人", "你试着进入正规临时安置点，但超凡登记核验无法完成。工作人员建议等人工处理。\n墙上贴着集团的回收公告。你带着初步记录，却没有能通过核验的身份证明，现在还不敢停下。"),
                Battle("街口追猎", "两台旧城巡检机从街口包抄过来。\n通讯里传出队长的声音：“目标仍在旧城，留活口。”", "patrol", "patrol"),
                Supply("废弃报亭", "你躲进报亭止血，终端震动。岑芜发来短讯：“我出来了。工友也在。找余砚，不要走主街。”\n\n恢复最多8生命。", 8, false),
                EventNode("无人售药柜", "一台无人售药柜的门板松了，里面留着维护后遗留的急救包。\n这里不涉及金币；风险是门板故障造成擦伤。余砚的地址你已经知道，失败也能找到他。\n\n安全：放弃。冒险D20：20恢复12；12～19恢复8；2～11失去4；1失去8。", 3),
                Choice("余砚的门", "余砚只开了半扇门：“岑芜说有人过来，没说后面跟着几辆车。”\n你说：“我不想把他们带进来。”\n他说：“那就别站在门口。”",
                    new[] { "说明自己是试验对象", "先出示岑芜的联络" },
                    new[] { "你说出自己从哪里逃出来。余砚沉默片刻，让你进门。", "你先出示岑芜的联络。余砚看了一眼，让你进门。" }),
                Story("追踪来源", "余砚检查你身上的试验装具，发现它会被附近的集团设备识别。\n他说：“不是整座城在看你，是有人知道该看哪里。”\n你得到线索：局部识别链。", "局部识别链"),
                Choice("不能留在这里", "回收小队正在接近修理间。\n余砚：“不管怎么走，都得先打掉门外的拦截点。”",
                    new[] { "先替街区挡住这一队", "找一条不牵连居民的路" },
                    new[] { "你决定先挡住这一队，不让他们闯进街区。", "你决定找一条不牵连居民的路，但先得清掉门外的人。" }),
                Battle("拦截修理间", "一名束缚器操作者守在防火隔间外。\n居民都在门后，这一战只有你和它。", "operator"),
                Supply("修理台", "余砚替你处理伤口，递来一份短时可用的防护材料：“我只能让你撑过眼前这段，别拿它当第二条命。”\n\n恢复最多16生命，并强化一个已携带技能+2。", 16, true),
                Story("决定下一步", "你决定截断这一轮回收。余砚给了你一个无人作业区的位置。\n你说：“我不是回去。我是让他们暂时过不来。”"),

                // 第五关：截断追猎
                Story("准备", "出发前，你检查自己的骰面与强化。没有新的骰面，也不会重新贴面——你只能带着现在的自己去。\n余砚：“要是觉得现在不行，就先坐下。不用向我证明你能打。”"),
                EventNode("最后一包材料", "余砚手里有一包完好的防护材料。可以直接用，也可以试着和受损护具配合，争取更多防护。\n\n安全：恢复8。冒险D20：20恢复16；12～19恢复12；2～11只恢复4；1装具故障，失去4。", 4),
                Battle("外围追猎", "无人作业区外，术式安保和束缚器拦住了去路。", "mage", "binder"),
                Supply("作业间", "你把带出的记录装进干燥封套。余砚在通讯里提醒：别丢掉原件。\n你说：“这回不只有我一个人记得。”\n\n恢复最多10生命，并强化一个已携带技能+2。", 10, true),
                Choice("确认退路", "退路通往余砚安排的空置工作间。出发前，你想再确认一件事。",
                    new[] { "检查通道", "确认通讯" },
                    new[] { "你沿通道走了一遍，记住每个转角。", "你和余砚核对了接应时间。" }),
                Choice("回收命令", "回收队长站在探照灯下：“你不在登记册上。回去，事情还能按原流程处理。”\n他肩侧的移动识别装置一直亮着。余砚在通讯里说：这支小队靠它维持近距离追踪。",
                    new[] { "“我不是你们的材料。”", "“那套流程里没有我的选择。”" },
                    new[] { "你说：我不是你们的材料。队长：控制目标，带回设施。", "你说：那套流程里没有我的选择。队长：控制目标，带回设施。" }),
                Battle("回收队长", "回收队长：先架护盾，再明显蓄力，随后重击。\n击坏他的识别装置，这一轮追猎才会中断。", "captain"),
                Supply("离开探照灯", "队长的识别装置损坏，他退守求援。你沿确认过的通道离开，余砚在接应处帮你包扎。\n“你能走，就走。伤口不用给谁交报告。”\n\n恢复最多12生命。", 12, false),
                Choice("谁保管记录", "关押记录、转运记录和识别链线索都在你手里。下一步交给谁，还没有答案。",
                    new[] { "先交余砚保存副本", "自己保管，先确认可信的接收者" },
                    new[] { "你把副本交给余砚，原件留在身上。", "你决定自己保管，先确认谁值得信任。" }),
                new NodeDef { title = "没有编号的床", kind = "ending", text = "空置工作间只有一张折叠床。岑芜发来平安的消息；余砚把钥匙放下：“今晚先休息。要往哪里去，明天自己说。”\n你看着没有固定带的床沿，坐下，没有立刻躺下。\n\n第一章《出逃》结束。集团还在，你也还不知道全部真相。第二章尚未制作。" }
            };
            if (list.Length != NodeCount) throw new InvalidOperationException("第一章节点数量必须为50。");
            for (int i = 0; i < list.Length; i++)
                list[i].id = "C1-" + StageOf(i).ToString("00") + "-" + StepOf(i).ToString("00");
            return list;
        }

        private static EventDef[] BuildEvents()
        {
            return new[]
            {
                new EventDef { safeLabel = "慢慢拆开（安全）", riskLabel = "迅速打开（D20）", safeDelta = 0, critDelta = 12, successDelta = 0, failDelta = -4, fumbleDelta = -8,
                    safeText = "你慢慢拆开门板，岑芜在另一侧帮忙。无收益也无损失。", critText = "维护板脱开，露出一只完好的急救包。",
                    successText = "门被迅速打开，没有受伤。岑芜：手法不错。", failText = "碎片擦伤了你的手臂。岑芜接住了门板。", fumbleText = "门板失手砸下，岑芜把你拉向旁侧窄口。" },
                new EventDef { safeLabel = "直接取出（恢复8）", riskLabel = "先加固再取（D20）", safeDelta = 8, critDelta = 16, successDelta = 12, failDelta = 4, fumbleDelta = -4,
                    safeText = "你直接取出了基础材料。", critText = "支架加固成功，你取出了完整的材料。",
                    successText = "加固大体成功，取出了大部分材料。", failText = "材料损坏了一部分。", fumbleText = "支架倾倒砸到了你，岑芜把箱体扶住。" },
                new EventDef { safeLabel = "放弃（安全）", riskLabel = "检查（D20）", safeDelta = 0, critDelta = 16, successDelta = 8, failDelta = -4, fumbleDelta = -8,
                    safeText = "你没有碰它。", critText = "盒底藏着一只密封完好的备用包。",
                    successText = "你找到了可用的部分。", failText = "破损的封口割伤了你，什么都没找到。", fumbleText = "收拾时失手，伤得不轻。" },
                new EventDef { safeLabel = "放弃（安全）", riskLabel = "尝试取出（D20）", safeDelta = 0, critDelta = 12, successDelta = 8, failDelta = -4, fumbleDelta = -8,
                    safeText = "你放弃了药柜，继续去找余砚。", critText = "柜里有一只完整的备用包。",
                    successText = "你取出了基础急救包。", failText = "门板夹伤了你的手。", fumbleText = "玻璃碎裂，你转移位置后继续寻找余砚。" },
                new EventDef { safeLabel = "直接使用（恢复8）", riskLabel = "与护具配合（D20）", safeDelta = 8, critDelta = 16, successDelta = 12, failDelta = 4, fumbleDelta = -4,
                    safeText = "你直接用上了防护材料。", critText = "材料和护具配合得很好。",
                    successText = "大部分材料起了作用。", failText = "只有一小部分材料能用。", fumbleText = "受损的装具发生故障，反而伤到了你。余砚仍然在帮你。" }
            };
        }

        private static Dictionary<string, EnemyTemplate> BuildTemplates()
        {
            EnemyTemplate[] list =
            {
                // 数值经 Tests/Sim 2026-10-15 校准：朴素策略约91～95%不失败通关、章末约70生命（测试起点，待真人试玩修正）。
                new EnemyTemplate { kind = "patrol", name = "巡检机", hp = 24, actions = new[] { "attack:13" } },
                new EnemyTemplate { kind = "binder", name = "束缚器", hp = 30, actions = new[] { "wait", "attack:26" } },
                new EnemyTemplate { kind = "security", name = "安保员", hp = 38, actions = new[] { "attack:16", "charge", "attack:26" } },
                new EnemyTemplate { kind = "mage", name = "术式安保", hp = 36, actions = new[] { "shield:8", "attack:15", "attack:15" } },
                new EnemyTemplate { kind = "elite", name = "精英锁卫", hp = 72, actions = new[] { "shield:10", "charge", "attack:36", "attack:18" } },
                new EnemyTemplate { kind = "operator", name = "束缚器操作者", hp = 40, actions = new[] { "wait", "attack:24", "attack:16" } },
                new EnemyTemplate { kind = "captain", name = "回收队长", hp = 110, actions = new[] { "shield:12", "charge", "attack:42", "attack:20" } }
            };
            var map = new Dictionary<string, EnemyTemplate>();
            foreach (EnemyTemplate t in list) map.Add(t.kind, t);
            return map;
        }
    }
}
