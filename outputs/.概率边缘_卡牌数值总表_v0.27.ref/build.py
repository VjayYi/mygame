# -*- coding: utf-8 -*-
try:
    import openpyxl
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "openpyxl>=3.1.0"])
    import openpyxl
import json, re, os, sys, math
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.formatting.rule import FormulaRule
from openpyxl.utils import get_column_letter

BASE = "/Users/vjayyi/WeChatProjects/mygame/outputs"
BAL = BASE + "/balance"
sys.path.insert(0, BAL)
OUT = BASE + "/概率边缘_卡牌数值总表_v0.27.xlsx"


def xl_color(css_hex):
    v = css_hex.removeprefix("#").upper()
    if len(v) != 6:
        raise ValueError(css_hex)
    return "FF" + v


XL_PRIMARY = xl_color("#4472C4")
XL_LIGHT = xl_color("#D9E2F3")
XL_DARK = xl_color("#2F5597")
XL_WHITE = xl_color("#FFFFFF")
XL_BORDER = xl_color("#BFBFBF")
XL_GREY = xl_color("#F2F2F2")
thin = Side(style="thin", color=XL_BORDER)
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
HFONT = Font(name="微软雅黑", bold=True, color=XL_WHITE, size=10)
BFONT = Font(name="微软雅黑", size=10)
HFILL = PatternFill("solid", fgColor=XL_PRIMARY)

# ---------------- 数据装载 ----------------
rows = json.load(open(BAL + "/module_audit_v0.26.json", encoding="utf-8"))
pool = json.load(open(BAL + "/module_pool_v0.27.json", encoding="utf-8"))
unlock = json.load(open(BAL + "/module_unlock_v0.27.json", encoding="utf-8"))
import weapon_audit_v026 as W

ATK = re.compile(r"\d+\s*伤害|伤害\s*[+＋]\s*\d|各\s*-\d|×\s*\d?\s*段|造成\s*\d+")
SHD = re.compile(r"获得\s*\d+\s*护盾|护盾\s*[+＋]?\s*\d|\d+\s*护盾")


def cls(t):
    first = re.split(r"[；;<]", t)[0]
    if ATK.search(first):
        return "攻击"
    if SHD.search(first):
        return "防御"
    return "功能"


TAG = {"保持": "不变", "亏模，数值上调": "数值上调", "亏模，补助效果": "补小效果", "亏模，费用-1": "降费", "亏模，费用-1并补助": "降费并补助",
       "亏模，费用-2并补助": "降费并补助", "手工重设（大块强化）": "大块重做", "补助效果": "补小效果", "升至1费": "升至1费", "超模削减": "数值下调"}
POOL = {"基地·通用": "基地·通用", "基地·限定": "基地·品类限定", "怪物": "怪物产出"}


def style_header(ws, row, ncol):
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = HFONT
        cell.fill = HFILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[row].height = 30


from openpyxl.worksheet.datavalidation import DataValidation


def put_table(ws, header, data, widths, wrap_cols=(), center_cols=(), start_row=1, review=True):
    header = list(header)
    if review:
        header = header + ["审核", "审核备注"]
        data = [list(r) + ["", ""] for r in data]
        widths = list(widths) + [8, 26]
        center_cols = tuple(center_cols) + (len(header) - 1,)
        wrap_cols = tuple(wrap_cols) + (len(header),)
    for j, h in enumerate(header, 1):
        ws.cell(row=start_row, column=j, value=h)
    style_header(ws, start_row, len(header))
    for i, r in enumerate(data, start_row + 1):
        for j, v in enumerate(r, 1):
            c = ws.cell(row=i, column=j, value=v)
            c.font = BFONT
            c.border = BORDER
            c.alignment = Alignment(vertical="top", wrap_text=(j in wrap_cols), horizontal="center" if j in center_cols else "left")
    for j, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = ws.cell(row=start_row + 1, column=2)
    ws.auto_filter.ref = f"A{start_row}:{get_column_letter(len(header))}{start_row + len(data)}"
    if review:
        col = get_column_letter(len(header) - 1)
        rng = f"{col}{start_row + 1}:{col}{start_row + len(data)}"
        dv = DataValidation(type="list", formula1='"保留,待定,删除"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(rng)
        for val, bg in (("保留", "#C6EFCE"), ("待定", "#FFEB9C"), ("删除", "#FFC7CE")):
            ws.conditional_formatting.add(rng, FormulaRule(formula=[f'${col}{start_row + 1}="{val}"'], fill=PatternFill("solid", bgColor=xl_color(bg), fgColor=xl_color(bg))))


wb = Workbook()
wb.properties.title = "概率边缘_卡牌数值总表_v0.27"

# =============== 模块 ===============
wsM = wb.active
wsM.title = "模块"
mh = ["名称", "来源池", "品类限定", "大类", "格数", "形状", "类型", "主效果类", "倾向", "费用(旧)", "费用(新)", "攻需", "防需", "供能档",
      "卡效果(新)", "升级类型", "升级后费用", "升级后效果", "终极效果(新)", "朝向", "预算占比", "解锁条件", "调整说明", "卡效果(旧)"]
md = []
order = {"基地·通用": 0, "基地·限定": 1, "怪物": 2}
rs = sorted(rows, key=lambda r: (order[pool[r["name"]]], r["limit"] if r["limit"] != "—" else "", r["major"], r["size"], r["name"]))
for r in rs:
    pl = pool[r["name"]]
    unl = unlock.get(r["name"], "免费" if pl != "怪物" else "局内掉落/商店")
    md.append([r["name"], POOL[pl], "通用" if r["limit"] == "—" else r["limit"], r["major"], r["size"], r["shape"], r["type"], cls(r["new_text"]),
               r["lean"], r["cost"], r["new_cost"], r["A"], r["D"], r["supply_tier"], r["new_text"], r["utype"], r["up_cost"], r["up_text"],
               r["new_ult"].replace("**", ""), r["facing"], round(r["r1"], 3), unl, TAG.get(r["status"], r["status"]), r["card"]])
N_M = len(md)
put_table(wsM, mh, md, [11, 13, 9, 7, 6, 7, 8, 9, 7, 8, 8, 6, 6, 9, 38, 10, 9, 38, 38, 6, 9, 24, 12, 30],
          wrap_cols=(15, 18, 19, 22, 24), center_cols=(4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 20, 21))
for i in range(2, N_M + 2):
    wsM.cell(row=i, column=21).number_format = "0%"
last = N_M + 1
tier_fill = {"极端攻": ("FFC7CE", "9C0006"), "偏攻": ("FCE4D6", "833C0B"), "偏防": ("DDEBF7", "1F4E78"), "极端防": ("BDD7EE", "1F4E78")}
for t, (bg, fg) in tier_fill.items():
    wsM.conditional_formatting.add(f"N2:N{last}", FormulaRule(formula=[f'$N2="{t}"'], fill=PatternFill("solid", bgColor=xl_color("#" + bg), fgColor=xl_color("#" + bg)), font=Font(color=xl_color("#" + fg))))
wsM.conditional_formatting.add(f"K2:K{last}", FormulaRule(formula=["$K2<>$J2"], font=Font(bold=True, color=xl_color("#C00000"))))
wsM.conditional_formatting.add(f"U2:U{last}", FormulaRule(formula=["OR($U2<0.85,$U2>1.2)"], fill=PatternFill("solid", bgColor=xl_color("#FFC7CE"), fgColor=xl_color("#FFC7CE"))))

# =============== 武器基础卡 ===============
NAMES = {"刀": ("制式刀", "高周波刀", "断岳刀"), "剑": ("电热剑", "震颤剑", "裂空剑"), "爪": ("裂爪", "撕爪", "龙爪"), "斧": ("短柄斧", "震地斧", "裂山斧"),
         "拳套": ("铁拳套", "电弧拳套", "镇岳拳套"), "步枪": ("突击步枪", "精确步枪", "狙击步枪"), "炮筒": ("轻型炮筒", "战术炮筒", "重型炮筒"),
         "手枪": ("制式手枪", "穿甲手枪", "重型左轮"), "弓": ("复合弓", "猎弓", "裂空弓")}
AUX_UP = {
    "刀": ("持续", "接下来 2 张攻击各 +5；抽 1 张"), "剑": ("持续", "本回合与下回合的首张防御牌费用 -1；护盾 +2"),
    "爪": ("持续", "首次攻击后回复 1 能源（本回合与下回合各 1 次）；抽 1 张"), "斧": ("持续", "接下来 2 张攻击各 +7"),
    "拳套": ("持续", "抽 1 张；本回合与下回合拳套攻击 +1；护盾 +2"), "步枪": ("持续", "接下来 2 张攻击各 +7"),
    "炮筒": ("洗牌", "抽 2 张；将弃牌堆洗回牌库；护盾 +1"), "手枪": ("追加", "抽 2 张"), "弓": ("持续", "抽 1 张；接下来 2 回合每回合首次攻击 +5"),
}
FORMS = [("改装", 0, "24～28", 26), ("均衡", 1, "16～20", 18), ("强攻", 3, "10～14", 12)]
SLOT = ["攻击A", "攻击B", "防御", "辅助"]
VOLFIX = W.VOL_FIX
wdata = []
for cat, cards in W.CARDS.items():
    pname, ptxt, _pe = W.PASSIVE[cat]
    for fi, (form, b, vr, vmid) in enumerate(FORMS):
        A, D = W.PS.FORM_BASE[form] if hasattr(W, "PS") else {"改装": (2, 1), "均衡": (3, 1), "强攻": (4, 2)}[form]
        if cat == "爪":
            A += 1
        for idx, (name, cost, dmgs, shd, extra, tpl, utpl) in enumerate(cards):
            bb = -(-b // 2) if len(dmgs) >= 2 else b
            d0 = (dmgs[0] + bb) if dmgs else 0
            sh = (shd + b) if shd else 0
            t = tpl.format(d0=d0, s=sh)
            if idx == 3:
                utag, u = AUX_UP[cat]
            elif idx == 0 and len(dmgs) == 1:
                utag, u = "两段", f"{math.ceil(d0 * 0.6)} 伤害 ×2 段（每段独立结算）"
            elif idx == 1 and cost >= 2:
                utag, u = f"降费{cost}→{cost - 1}", t + "（效果不变）"
            elif dmgs:
                ud = d0 + math.ceil(3 * max(cost, 1) / (1.6 if name == "旋斧" else len(dmgs)))
                utag, u = "数值", utpl.format(u0=ud, us=0)
            else:
                utag, u = "数值", utpl.format(u0=0, us=sh + 3 * max(cost, 1))
            passive = f"{pname}：{ptxt}" if (form == "均衡" and idx == 3) else ""
            wdata.append([cat, form, NAMES[cat][fi], SLOT[idx], name, cost, cls(t), t, utag, u, A, D, f"中值{vmid + VOLFIX[cat]}（区间{vr}，品类修正{VOLFIX[cat]:+d}）", passive])
N_W = len(wdata)
wsW = wb.create_sheet("武器基础卡")
put_table(wsW, ["品类", "形态", "武器名", "卡位", "卡名", "费用", "主效果类", "卡效果", "升级类型", "升级后效果", "基础攻需", "基础防需", "容积", "核心被动(均衡型，印在辅助卡上)"], wdata,
          [7, 7, 11, 8, 8, 6, 9, 38, 11, 38, 9, 9, 30, 44], wrap_cols=(8, 10, 13, 14), center_cols=(1, 2, 4, 6, 7, 9, 11, 12))
wsW.conditional_formatting.add(f"B2:B{N_W + 1}", FormulaRule(formula=['$B2="强攻"'], font=Font(bold=True, color=xl_color("#C00000"))))

# =============== 防具 ===============
md_text = open(BASE + "/combat-budget-v0.26-model.md", encoding="utf-8").read()


def section(a, b=None):
    i = md_text.index(a)
    j = md_text.index(b, i) if b else len(md_text)
    return md_text[i:j]


def table_rows(txt):
    out = []
    for ln in txt.split("\n"):
        if ln.startswith("|") and not ln.startswith("|---"):
            out.append([x.strip() for x in ln.strip().strip("|").split("|")])
    return out


def newval(s):
    s = s.strip()
    return int(re.findall(r"\d+", s)[-1]) if re.findall(r"\d+", s) else 0


SETS = {"铁壁": ["铁壁盔", "铁壁甲", "铁壁靴"], "反震": ["反震盔", "反震胸甲", "反震护腕"], "流光": ["流光目镜", "流光甲", "流光靴"],
        "灼炉": ["灼炉面罩", "灼炉胸甲", "灼炉护腿"], "猎手": ["猎手目镜", "猎手外套", "猎手护腿"]}
setof = {n: s for s, ns in SETS.items() for n in ns}
adata = []
for c in table_rows(section("## 4. 防具", "## 5. 义体")):
    if len(c) == 6 and c[1] in ("头", "躯干", "四肢"):
        df = newval(c[2].split("：")[0])
        mshield = {0: "护盾 2；下回合护盾 +1", 1: "护盾 6", 2: "护盾 12"}[df]
        sc = newval(c[3])
        adata.append([c[0], c[1], setof.get(c[0], "散件"), df, mshield, sc, c[4], cls(c[4]), c[5]])
import armor_v027 as AR
_MAIN = {0: "护盾 2；下回合护盾 +1", 1: "护盾 6", 2: "护盾 12"}
for (n, part, st, df, sc, eff, note) in AR.NEW:
    adata.append([n, part, st, df, _MAIN[df], sc, eff, cls(eff), note])
N_A = len(adata)
wsA = wb.create_sheet("防具")
put_table(wsA, ["件名", "部位", "套装", "主防御费用", "主防御效果", "副防御费用", "副防御效果", "副防御主效果类", "调整说明"], adata,
          [11, 7, 8, 9, 20, 9, 44, 11, 24], wrap_cols=(5, 7, 9), center_cols=(2, 3, 4, 6, 8))

# =============== 义体 ===============
imp = section("## 5. 义体", "## 6.")
hands = imp[imp.index("### 手"):imp.index("### 脚")]
feet = imp[imp.index("### 脚"):imp.index("### 大脑")]
brain = imp[imp.index("### 大脑"):imp.index("### 躯干")]
torso = imp[imp.index("### 躯干"):]
idata = []
for c in table_rows(hands):
    if c[0].isdigit():
        idata.append(["手", int(c[0]), c[1], "", newval(c[2]), c[3], cls(c[3]), c[4], c[5]])
for c in table_rows(feet):
    if c[0].isdigit():
        idata.append(["脚", int(c[0]), c[1], "", newval(c[2]), c[3], cls(c[3]), "", c[4]])
for part, tx in (("大脑", brain), ("躯干", torso)):
    for c in table_rows(tx):
        if c[0].isdigit():
            idata.append([part, int(c[0]), c[1], c[2], newval(c[3]), c[4], cls(c[4]), "", ""])
N_I = len(idata)
wsI = wb.create_sheet("义体")
put_table(wsI, ["部位", "编号", "型号", "被动效果(常驻，不占手牌)", "可打卡费用", "可打卡效果", "主效果类", "重量/操作", "调整说明"], idata,
          [7, 6, 13, 40, 9, 44, 9, 10, 26], wrap_cols=(4, 6, 9), center_cols=(1, 2, 5, 7, 8))

# =============== 新增候选卡（v0.28） ===============
NC = json.load(open(BAL + "/new_cards_v028.json", encoding="utf-8"))
nm_rows = []
for m in NC["mods"]:
    nm_rows.append([m["name"], m["pool"], m["major"], m["size"], m["shape"], m["type"], cls(m["text"]), m["mech"], m["cost"], m["A"], m["D"], m["tier"], m["text"],
                    m["utype"], m["up_cost"], m["up_text"], m["ult"], m["facing"], m["ratio"]])
N_NM = len(nm_rows)
wsNM = wb.create_sheet("新增模块(候选)")
put_table(wsNM, ["名称", "来源池", "大类", "格数", "形状", "类型", "主效果类", "机制", "名义费用", "攻需", "防需", "供能档", "卡效果", "升级类型", "升级后费用", "升级后效果", "终极效果", "朝向", "预算占比"],
          nm_rows, [12, 10, 6, 6, 7, 8, 9, 14, 9, 6, 6, 9, 46, 10, 9, 44, 30, 6, 9], wrap_cols=(13, 16, 17), center_cols=(2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 18, 19))
for i in range(2, N_NM + 2):
    wsNM.cell(row=i, column=19).number_format = "0%"
wsNM.conditional_formatting.add(f"I2:I{N_NM + 1}", FormulaRule(formula=["$I2>=4"], font=Font(bold=True, color=xl_color("#C00000"))))
for t, (bg, fg) in tier_fill.items():
    wsNM.conditional_formatting.add(f"L2:L{N_NM + 1}", FormulaRule(formula=[f'$L2="{t}"'], fill=PatternFill("solid", bgColor=xl_color("#" + bg), fgColor=xl_color("#" + bg)), font=Font(color=xl_color("#" + fg))))

ni_rows = []
for m in NC["imps"]:
    ni_rows.append([m["part"].replace("脑", "大脑").replace("躯", "躯干"), m["name"], m["cost"], cls(m["text"]), m["mech"], m["text"], m["passive"], m["wo"], m["utype"], m["up_cost"], m["up_text"], m["ratio"]])
N_NI = len(ni_rows)
wsNI = wb.create_sheet("新增义体(候选)")
put_table(wsNI, ["部位", "型号", "费用", "主效果类", "机制", "可打卡效果", "被动效果(常驻)", "重量/操作", "升级类型", "升级后费用", "升级后效果", "预算占比"], ni_rows,
          [7, 12, 6, 9, 14, 46, 40, 9, 9, 9, 44, 9], wrap_cols=(6, 7, 11), center_cols=(1, 3, 4, 8, 9, 10, 12))
for i in range(2, N_NI + 2):
    wsNI.cell(row=i, column=12).number_format = "0%"
wsNI.conditional_formatting.add(f"C2:C{N_NI + 1}", FormulaRule(formula=["$C2>=3"], font=Font(bold=True, color=xl_color("#C00000"))))

wsT = wb.create_sheet("副产品卡")
put_table(wsT, ["名称", "类型", "费用", "效果", "说明/来源"], [list(t) for t in NC["tokens"]], [12, 8, 6, 50, 56], wrap_cols=(4, 5), center_cols=(2, 3))

DIC = [
    ("消耗", "打出后本场战斗移出牌库，不进弃牌堆", "杀戮尖塔「消耗」", "绝对防御、紧急补给、一次性爆弹", "价值预算 +0.4 费"),
    ("保留", "回合结束不弃牌", "杀戮尖塔「保留」", "蓄能炮、蓄势待发、蓄力腿", "沿用"),
    ("固有", "每场战斗开始必在起手牌中", "杀戮尖塔「固有」", "检索芯片（被动）", "被动手估"),
    ("成长（永久 +N）", "本场战斗内累计，战斗结束重置；卡面写明上限", "杀戮尖塔「暴走」类、怪物火车", "狂暴连锁、磨砺之刃、积怨、越战越勇", "按平均打出 3 次估成长增量"),
    ("递减", "每次打出后效果降低，有最低值", "耐久递减类", "用尽即弃、一次性护符、衰变光环", "起手数值略高，平均扣 0.17～0.2 费"),
    ("次数（弹药）", "共 N 发，打出 N 次后消耗", "炉石「耐久度」", "残存弹药", "按消耗牌加成"),
    ("检索", "从牌库中选择 1 张指定类型的牌加入手牌", "MTG 检索、炉石「检索」", "精准检索、防御检索、名册索引", "≈0.7 费"),
    ("发现", "查看牌库顶 N 张，选 1 张加入手牌，其余放回牌库底", "炉石「发现」", "战术发现", "≈0.9 费"),
    ("预知", "查看牌库顶 N 张，可弃置其中任意张", "MTG「Scry」、杀戮尖塔「预见」", "预知扫描、预知芯片", "≈0.45 费"),
    ("衍生（副产品卡）", "生成临时牌，加入手牌/弃牌堆；临时牌 0 费、消耗，不计入卡组", "杀戮尖塔「小刀」、炉石衍生物", "火种引信、碎刃、弹壳回收", "按所生成牌价值计"),
    ("废牌", "负面衍生牌，占手牌位或有代价，换取更强效果", "杀戮尖塔「灼伤/晕眩」", "过热废料", "负面价值 -0.5 费"),
    ("条件减费", "卡面写明名义费用和减费条件，最低 1 费", "MTG「掘冢」、炉石「费用减少」", "烈焰风暴、墓土召回、收割者、孤注一掷", "按“常态 3 费 + 10%”估价（3.3 费当量）"),
    ("追加（Kicker）", "额外支付费用获得强化效果（可选）", "MTG「Kicker」", "毁灭之矛", "基础 + 一半强化价值"),
    ("过载", "获得强效，但下回合有限制", "炉石「过载」", "重炮齐射", "负面价值 -0.4 费"),
    ("奥秘", "打出后埋下，敌人下一次行动时触发，每场限 1 次，不占手牌", "炉石「奥秘」", "反击手、陷阱腿、奥秘芯片", "条件触发 ×0.65"),
    ("能力牌", "打出后消耗，本场战斗常驻效果", "杀戮尖塔「能力牌」", "魔剑觉醒、绝对防御、契约核心", "按剩余回合 ≈4 估"),
    ("闪回", "从弃牌堆再打出 1 张牌，然后消耗", "MTG「Flashback」", "反刍芯片", "≈1.1 费"),
    ("复制", "复制手牌中 1 张牌，本回合有效", "杀戮尖塔/炉石「复制」类", "暗影分身、复制手", "≈1.2 费"),
    ("连携", "本回合已打出的牌越多，效果越强", "炉石「连击」", "爆发手、连携芯片", "平均 3 张牌估"),
    ("洗牌", "弃牌堆洗回牌库", "杀戮尖塔「洗牌」", "墓土召回、回炉重铸", "0.6 费"),
]
wsD = wb.create_sheet("机制词典")
put_table(wsD, ["关键词", "规则", "参考来源", "示例卡", "预算处理"], [list(x) for x in DIC], [16, 56, 28, 36, 34], wrap_cols=(2, 3, 4, 5), center_cols=(), review=True)

# =============== 规则 ===============
wsR = wb.create_sheet("规则汇总")
rules = [
    ("基本盘", "每回合 3 能源，抽 5 张；站位 1～5 号位；敌人意图公开", "已定"),
    ("价值锚点", "6 伤害 = 1 费；6 护盾 = 1 费；1 层流血/灼烧/中毒 = 1.5 伤害 = 0.25 费；延迟增益 ×0.8；控制：20% 击晕 0.6 费、30% 0.9、50% 1.2、必定 2.0；群体：全体 ×1.6、随机两名 ×1.7、1 号位全体 ×1.3；抽牌 1 张 0.4 费；能源 +1 = 0.9 费；回复生命 1 点 ≈ 1.3/6 费；带条件的效果 ×0.65", "已定(13:10 前)"),
    ("超模容差", "价值在费用预算的 85%～120% 内合格；超 120% 超模，低于 85% 亏模；亏模补小效果或降费，超模降数值或加费", "已定"),
    ("0 费规则", "模块 0 费限 15 个（全部 2 格）；其余最低 1 费；被抬到 1 费的卡可在升级后变 0 费；带能源/抽牌的卡不允许升级成 0 费；0 费预算 0.4 费", "已定"),
    ("占模补偿", "预算 = 费用价值 + 占模补偿 + 0.02×(攻需+防需)。占模补偿 = 0.06×(格数-2) + 0.02×(重量+操作) + 0.04×形状难拼度×(格数-2)；越大、形状越难拼、供能需求越高，卡越强", "已定"),
    ("终极卡", "固定 3 费；数值项终极 < 单卡，机制项终极可以 > 单卡；机制很强的终极不补数值，机制一般的补一点（约 0.22×卡价值，至少 1）", "已定"),
    ("矛盾词条", "卡本身没有伤害来源的，效果不得依赖“本卡伤害/击杀/命中”，须写成“本回合”范围的持续触发；无自身伤害的增益卡不设朝向", "已定"),
    ("供能规则", "攻击/防御供能 10% 一格；某侧供能 ≥80% 该侧卡 +1、100% 则 +2；对侧卡相应 -1/-2；只削数值，卡不会打不出；修正对所有攻击卡和防御卡生效（武器/模块/义体/防具），终极卡不吃；多段攻击整张只算一次；修正是追加状态，不写在卡面", "已定"),
    ("供能切换", "回合内任意时间点可改；改后下一回合冷却不能改，再下一回合才能改；新回合沿用上回合姿态", "已定"),
    ("终极卡门槛", "门槛 = 需求较高一侧占总需求的比例，向上取整到 10%；攻防需求相等则两侧各 50%；达标即可打出，不吃加成惩罚", "已定"),
    ("供能参数分布", "约 50% 一半一半、≈20% 偏攻、≈20% 偏防、≈10% 极端（只给 4 格以上、效果突出的卡）；攻击卡不一定攻高，防御/功能卡不一定防高。五档：均衡/偏攻/偏防/极端攻/极端防", "已定(比例可浮动)"),
    ("升级类型", "数值 / 两段（单次攻击变 2 段）/ 持续（下一张→接下来 2 张，下回合→接下来 2 回合）/ 降费 / 追加 / 机制核心；机制核心占 10%，必须 4 格及以上模块；终极卡与被动不升级；局内升级、跨局重置", "已定"),
    ("洗牌与冷却", "洗回牌库 = 弃牌堆洗回牌库（价值 0.6 费）；冷却 N 回合 = 打出后移出战斗，N 回合后回手（预算 +0.25 费×N）；只放少量，必须 4 格以上，建议只从怪物产出获得", "已定"),
    ("模块来源", "基地直接改装（通用 38 + 品类限定 108）；怪物产出（44，精英/小Boss 掉落和商店）。基地 5～6 格共 59 个，其中 30 个需完成成就解锁，其余免费", "已定"),
    ("经济", "局内金币：战斗/事件掉落，商店消费，本局清零；无局外货币、无仓库、无撤离。商店只卖怪物产出池：价格≈40×预算×1.25（2 格 25～30，3 格 55，4 格 60，5 格 100，6 格 130）；升级 60，移除卡 50(+25/次)，回复 20 点生命 40，刷新 20", "金币已定；价格为起点"),
    ("防具规则", "共 90 件（10 套装×3 件 + 60 散件，每部位 30 件可选），每件 2 张卡（主防御+副防御），共 180 张；主防御 0 费护盾 2+下回合护盾 1、1 费护盾 6、2 费护盾 12；副防御承载特效", "数值待模拟"),
    ("套装加成", "铁壁：2 件每回合开始护盾 +3，3 件回合结束保留护盾上限 8；反震：2 件受击反伤 2（每回合最多 2 次），3 件每回合首次受伤后下一张攻击 +4；流光：2 件每回合首张牌费用 -1，3 件每打出 0 费牌抽 1（每回合 1 次）；灼炉：2 件攻击附加灼烧 1，3 件灼烧结算对全体额外 2；猎手：2 件对距离 3 以上攻击 +3，3 件击杀回复 1 能源（每回合 1 次）；毒蚀：2 件每回合首次攻击附加中毒 2，3 件敌人回合开始时对每个中毒目标额外 2 伤害；裂血：2 件每回合首次攻击附加流血 2，3 件目标流血 ≥5 层时本回合对其伤害 +3（每回合 1 次）；雷霆：2 件每回合首次攻击 20% 击晕，3 件被击晕的敌人本回合受到的伤害 +2；狂潮：2 件生命低于 50% 时每回合开始护盾 +3，3 件生命低于 30% 时本回合所有攻击牌伤害 +3；机巧：2 件回合结束可多保留 1 张手牌，3 件每回合弃牌后抽 1 张（每回合 1 次）", "数值待模拟"),
    ("义体套装", "攻势套（手）：2 件手部可打卡伤害 +3，4 件每回合开始能源 +1 且伤害 +3 附击退；机动套（脚）：2 件脚部可打卡护盾 +3，4 件每回合开始护盾 +2 且护盾 +3 附位移；能源点 +N 只出现在 4 件套", "数值待模拟"),
    ("费用分布", "模块：0 费限 15 个（约 6%）；3 费约 10%（23 个，含 19 个新增）；名义 4～6 费的模块必须在卡面第一行写明费用和减费条件，常态减到 2～3 费，预算按 3.3 费当量；其余多数 1～2 费", "已定(14:07)"),
    ("新机制", "战斗内成长、递减、次数、检索/发现/预知、消耗、衍生（副产品卡）、废牌、条件减费、追加、过载、奥秘、能力牌、闪回、复制、连携，详见「机制词典」；新增 50 个模块 + 50 个义体 + 7 张副产品卡，均为候选，待你审核", "候选(待审核)"),
    ("武器三形态", "强攻型：每个伤害/护盾 +3，容积 10～14；均衡型：+1，容积 16～20，辅助卡印核心被动；改装型：基准，容积 24～28；品类容积修正：刀0/剑+1/爪-1/斧-2/拳套-1/步枪0/炮筒-2/手枪+1/弓+1；基础供能：改装 2/1、均衡 3/1、强攻 4/2，爪攻需 +1", "已定(供能本体待你定)"),
]
wsR["A1"] = "规则汇总（v0.27，截至 2026-11-18）"
wsR["A1"].font = Font(name="微软雅黑", bold=True, size=13, color=XL_DARK)
for j, h in enumerate(["项目", "规则", "状态"], 1):
    wsR.cell(row=2, column=j, value=h)
style_header(wsR, 2, 3)
for i, (a, b, c) in enumerate(rules, 3):
    for j, v in enumerate((a, b, c), 1):
        cell = wsR.cell(row=i, column=j, value=v)
        cell.font = BFONT
        cell.border = BORDER
        cell.alignment = Alignment(vertical="top", wrap_text=True)
wsR.column_dimensions["A"].width = 14
wsR.column_dimensions["B"].width = 110
wsR.column_dimensions["C"].width = 22

# =============== 待确认 ===============
wsQ = wb.create_sheet("待确认")
qs = [
    ("供能", "极端名单（19 个）里有没有不该极端的？能源爆发/反应炉/爆破核心三个能源件都是极端防，是否换掉一两个", "高"),
    ("供能", "品类性格：剑/斧/炮筒的攻击件偏防，爪/拳套/手枪的功能件偏攻，刀/步枪/弓中性，是否符合想象", "中"),
    ("供能", "武器本体供能是否也要变化（现在改装 2/1、均衡 3/1、强攻 4/2，爪攻需+1），如剑防需+1、炮筒防需+1", "中"),
    ("防具", "旧 45 件防具里仍有 30 件 0 费副防御（新增 45 件只有 6 件 0 费），是否也改成“升级后才 0 费”", "高"),
    ("义体", "义体已是 50 个型号，你说“义体到 50 件”是够了，还是想扩更多（手/脚各 25、增加套装）", "高"),
    ("升级", "升级成 0 费的卡若带资源效果，只在“每回合第一次”生效，是否接受", "中"),
    ("升级", "19 个机制核心名单是否认可、是否换几个", "中"),
    ("洗牌", "6 个洗牌/冷却模块是否只放怪物产出", "低"),
    ("强攻型", "强攻型单卡 +3 在单卡口径超 20%：保持整体口径平衡，还是每卡卡死（强攻 +1，其余放升级）", "高"),
    ("占模", "占模补偿系数（0.06/0.02/0.04）与形状分配规则（紧凑=防御/回复，长条=伤害，不规则=机制）是否合适", "中"),
    ("经济", "免费线：5～6 格 30/59 需成就解锁，比例与条件（通关 1 次/击败 3 个小Boss/无伤精英）是否合适", "中"),
    ("经济", "武器/防具/义体是否也靠成就解锁；剧情模式是否用金币；事件是否扣金币；怪物产出池是否需解锁", "中"),
    ("审核", "新增候选卡 100 张是否保留：Excel 每张表有“审核”列（保留/待定/删除），标完发回即可收口", "高"),
    ("新机制", "名义高费（4～6 费）模块 8 个 + 义体 1 个是否合适；能力牌（魔剑觉醒、绝对防御、契约核心）是否保留；废牌（过热）是否保留", "中"),
    ("怪物", "怪物按 生命×1.33、伤害×1.2 为起点重校，是否直接进入逐卡模拟（含供能修正、防具义体吃修正）", "高"),
    ("装备数量", "装备是否继续扩充：防具每部位 15 件偏薄，义体套装只有 2 套，具体补多少", "中"),
]
wsQ["A1"] = "待确认清单"
wsQ["A1"].font = Font(name="微软雅黑", bold=True, size=13, color=XL_DARK)
for j, h in enumerate(["类别", "问题", "优先级"], 1):
    wsQ.cell(row=2, column=j, value=h)
style_header(wsQ, 2, 3)
for i, (a, b, c) in enumerate(qs, 3):
    for j, v in enumerate((a, b, c), 1):
        cell = wsQ.cell(row=i, column=j, value=v)
        cell.font = BFONT
        cell.border = BORDER
        cell.alignment = Alignment(vertical="top", wrap_text=True, horizontal="center" if j != 2 else "left")
wsQ.column_dimensions["A"].width = 10
wsQ.column_dimensions["B"].width = 100
wsQ.column_dimensions["C"].width = 9
wsQ.conditional_formatting.add(f"C3:C{2 + len(qs)}", FormulaRule(formula=['$C3="高"'], fill=PatternFill("solid", bgColor=xl_color("#FFC7CE"), fgColor=xl_color("#FFC7CE"))))

# =============== 总览（公式引用各表） ===============
ws = wb.create_sheet("总览", 0)
ws["A1"] = "概率边缘 · 卡牌数值总表 v0.27"
ws["A1"].font = Font(name="微软雅黑", bold=True, size=15, color=XL_DARK)
ws["A2"] = "数据截至 2026-11-18。数值均为起点（未逐卡模拟）；下列统计由各工作表公式自动计算。"
ws["A2"].font = Font(name="微软雅黑", size=10, color=xl_color("#595959"))
MR = f"2:{N_M + 1}"
rngM = lambda col: f"模块!${col}$2:${col}${N_M + 1}"
rngW = lambda col: f"武器基础卡!${col}$2:${col}${N_W + 1}"
rngA = lambda col: f"防具!${col}$2:${col}${N_A + 1}"
rngI = lambda col: f"义体!${col}$2:${col}${N_I + 1}"
r = 4


def block(title, header, items):
    """items: [(label, formula)]，返回下一个起始行"""
    global r
    ws.cell(row=r, column=1, value=title).font = Font(name="微软雅黑", bold=True, size=11, color=XL_DARK)
    r += 1
    for j, h in enumerate(header, 1):
        ws.cell(row=r, column=j, value=h)
    style_header(ws, r, len(header))
    r += 1
    for it in items:
        for j, v in enumerate(it, 1):
            c = ws.cell(row=r, column=j, value=v)
            c.font = BFONT
            c.border = BORDER
            c.alignment = Alignment(horizontal="left" if j == 1 else "center", vertical="center")
        r += 1
    r += 1


# A. 可打出卡牌统计（攻击/防御/功能）
cardsrc = [
    ("模块（190）", f'=COUNTIF({rngM("H")},"攻击")', f'=COUNTIF({rngM("H")},"防御")', f'=COUNTIF({rngM("H")},"功能")'),
    ("武器基础卡（36 设计卡，按改装型一套计）", f'=COUNTIFS({rngW("B")},"改装",{rngW("G")},"攻击")', f'=COUNTIFS({rngW("B")},"改装",{rngW("G")},"防御")', f'=COUNTIFS({rngW("B")},"改装",{rngW("G")},"功能")'),
    ("防具（90 件×2 张）", "=0", f"=COUNTA({rngA('A')})+COUNTIF({rngA('H')},\"防御\")", f"=COUNTIF({rngA('H')},\"功能\")+COUNTIF({rngA('H')},\"攻击\")"),
    ("义体可打卡（50）", f'=COUNTIF({rngI("G")},"攻击")', f'=COUNTIF({rngI("G")},"防御")', f'=COUNTIF({rngI("G")},"功能")'),
]
start_cards = r + 2
items = []
for k, (lab, a, d, f) in enumerate(cardsrc):
    rowno = start_cards + k
    items.append((lab, a, d, f, f"=SUM(B{rowno}:D{rowno})"))
items.append(("合计（不含终极卡）", f"=SUM(B{start_cards}:B{start_cards + 3})", f"=SUM(C{start_cards}:C{start_cards + 3})", f"=SUM(D{start_cards}:D{start_cards + 3})", f"=SUM(E{start_cards}:E{start_cards + 3})"))
block("一、可打出卡牌总量", ["来源", "攻击卡", "防御卡", "功能卡", "合计"], items)

# B. 模块来源/格数
src_items = []
for lab in ("基地·通用", "基地·品类限定", "怪物产出"):
    src_items.append((lab, f'=COUNTIF({rngM("B")},"{lab}")'))
src_items.append(("模块合计", f"=SUM(B{r + 2}:B{r + 4})"))
block("二、模块来源", ["来源池", "数量"], src_items)

size_items = [(f"{s} 格", f'=COUNTIF({rngM("E")},{s})') for s in range(2, 7)]
block("三、模块格数分布", ["格数", "数量"], size_items)

cost_items = [(f"{c} 费", f'=COUNTIF({rngM("K")},{c})', f'=COUNTIF({rngM("J")},{c})') for c in range(0, 4)]
block("四、模块费用分布（新 vs 旧）", ["费用", "新", "旧"], cost_items)

tier_items = [(t, f'=COUNTIF({rngM("N")},"{t}")') for t in ("均衡", "偏攻", "偏防", "极端攻", "极端防")]
tier_items.append(("合计", f"=SUM(B{r + 2}:B{r + 6})"))
block("五、供能档位分布（攻/防需求）", ["档位", "数量"], tier_items)

up_items = [(t, f'=COUNTIF({rngM("P")},"{t}")') for t in ("数值", "两段", "持续", "降费", "追加", "机制核心")]
up_items.append(("机制核心占比", f'=IF(COUNTA({rngM("A")})=0,"",COUNTIF({rngM("P")},"机制核心")/COUNTA({rngM("A")}))'))
block("六、升级类型分布（模块）", ["类型", "数量"], up_items)
ws.cell(row=r - 2, column=2).number_format = "0.0%"

chk_items = [
    ("预算占比在 85%～120% 内", f'=COUNTIFS({rngM("U")},">=0.85",{rngM("U")},"<=1.2")'),
    ("预算超出区间（应为 0）", f'=COUNTIF({rngM("U")},"<0.85")+COUNTIF({rngM("U")},">1.2")'),
    ("需成就解锁的 5～6 格基地模块", f'=COUNTIFS({rngM("V")},"<>免费",{rngM("V")},"<>局内掉落/商店")'),
    ("0 费模块（限 15）", f'=COUNTIF({rngM("K")},0)'),
]
block("七、检查项", ["项目", "数值"], chk_items)

rngNM = lambda col: f"'新增模块(候选)'!${col}$2:${col}${N_NM + 1}"
rngNI = lambda col: f"'新增义体(候选)'!${col}$2:${col}${N_NI + 1}"

# 八、含新增候选的模块费用分布
st = r + 2
items = []
for k, c in enumerate(range(0, 4)):
    rn = st + k
    items.append((f"{c} 费", f'=COUNTIF({rngM("K")},{c})', f'=COUNTIF({rngNM("I")},{c})', f"=B{rn}+C{rn}", f"=IF(D{st + 5}=0,\"\",D{rn}/D{st + 5})"))
rn = st + 4
items.append(("4～6 费（名义，需卡面写条件减费）", f'=COUNTIF({rngM("K")},">=4")', f'=COUNTIF({rngNM("I")},">=4")', f"=B{rn}+C{rn}", f"=IF(D{st + 5}=0,\"\",D{rn}/D{st + 5})"))
items.append(("合计", f"=SUM(B{st}:B{st + 4})", f"=SUM(C{st}:C{st + 4})", f"=SUM(D{st}:D{st + 4})", f"=SUM(E{st}:E{st + 4})"))
block("八、模块费用分布（含新增候选，3 费目标约 10%）", ["费用", "原模块", "新增候选", "合计", "占比"], items)
for rr in range(st, st + 6):
    ws.cell(row=rr, column=5).number_format = "0.0%"

# 九、含候选的可打出卡牌总量
st = r + 2
items = [("现有可打出卡（上表合计）", f"=B{start_cards + 4}", f"=C{start_cards + 4}", f"=D{start_cards + 4}", f"=B{st}+C{st}+D{st}")]
items.append(("新增模块候选", f'=COUNTIF({rngNM("G")},"攻击")', f'=COUNTIF({rngNM("G")},"防御")', f'=COUNTIF({rngNM("G")},"功能")', f"=B{st + 1}+C{st + 1}+D{st + 1}"))
items.append(("新增义体候选", f'=COUNTIF({rngNI("D")},"攻击")', f'=COUNTIF({rngNI("D")},"防御")', f'=COUNTIF({rngNI("D")},"功能")', f"=B{st + 2}+C{st + 2}+D{st + 2}"))
items.append(("合计（含候选，不含终极卡与副产品卡）", f"=SUM(B{st}:B{st + 2})", f"=SUM(C{st}:C{st + 2})", f"=SUM(D{st}:D{st + 2})", f"=SUM(E{st}:E{st + 2})"))
block("九、含新增候选的可打出卡牌总量", ["来源", "攻击卡", "防御卡", "功能卡", "合计"], items)

# 十、审核进度
REV = [("模块", N_M, 24, "模块"), ("武器基础卡", N_W, 14, "武器基础卡"), ("防具", N_A, 9, "防具"), ("义体", N_I, 9, "义体"),
       ("新增模块(候选)", N_NM, 19, "'新增模块(候选)'"), ("新增义体(候选)", N_NI, 12, "'新增义体(候选)'"), ("副产品卡", len(NC["tokens"]), 5, "副产品卡"), ("机制词典", len(DIC), 5, "机制词典")]
st = r + 2
items = []
for k, (lab, n, ncol, sh) in enumerate(REV):
    col = get_column_letter(ncol + 1)
    rg = f"{sh}!${col}$2:${col}${n + 1}"
    rn = st + k
    items.append((lab, n, f'=COUNTIF({rg},"保留")', f'=COUNTIF({rg},"待定")', f'=COUNTIF({rg},"删除")', f"=B{rn}-C{rn}-D{rn}-E{rn}"))
items.append(("合计", f"=SUM(B{st}:B{st + len(REV) - 1})", f"=SUM(C{st}:C{st + len(REV) - 1})", f"=SUM(D{st}:D{st + len(REV) - 1})", f"=SUM(E{st}:E{st + len(REV) - 1})", f"=SUM(F{st}:F{st + len(REV) - 1})"))
block("十、审核进度（在各表“审核”列选 保留/待定/删除，这里自动统计）", ["表", "总数", "保留", "待定", "删除", "未审核"], items)

ws.column_dimensions["A"].width = 42
for col in "BCDEF":
    ws.column_dimensions[col].width = 12
ws.sheet_view.showGridLines = False

wb.save(OUT)
print("saved", OUT, N_M, N_W, N_A, N_I)
