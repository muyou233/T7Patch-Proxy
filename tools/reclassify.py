"""按功能重排词库分节（去掉「第 N 批 / 补充」这类记账式命名）。

背景：分节标题原本混了两种东西 ——
  · 按界面/功能分的（标题屏 / 多人 / 军营 / 设置 / 挑战名称 …）—— 有意义，保留
  · 按我补译先后记的账（补充（第 2 批）/ MOD 汉化第二批…第六批）—— 对使用者没意义
本脚本把后者按**内容**重新归类，并顺手把两处名不副实的条目挪回该去的节。

归类规则（只对 MOD 各批的条目、以及"补充（第 2 批）"适用）：
  · 含 '*'        -> 模板节（动态数值）
  · 长度 > 24 或 以 . ! ? : 结尾 -> 「功能说明」
  · 其余短条目    -> 「菜单项与选项值」
第四批（信息页 / 链接 / FAQ）与第六批（带颜色码的技能说明）整批各成一节，不做拆分。

安全：全程只重排行，**不改任何一条词条**；结束时断言「条目数」与「键集合」完全不变。
"""
import io
import os

SRC = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
HEAD_MARK = "# ═══ "

TITLE_MAIN = "# ═══ 标题屏 / 主菜单 ═══"
TITLE_BARRACKS = "# ═══ 军营 / 黑市 ═══"
TITLE_MP = "# ═══ 多人 / 大厅 ═══"
TITLE_MARKS = "# ═══ 格式标记片段（^B 按键绑定 / $() 属性绑定 / [{...}] 令牌）═══"
TITLE_TEMPLATES = "# ═══ 模板条目（动态数值：等级 / 转生 / 时长 / 命中次数）═══"
TITLE_MOD_MENU = "# ═══ MOD：菜单项与选项值 ═══"
TITLE_MOD_DESC = "# ═══ MOD：功能说明（僵尸 / 技能 / 游戏选项的长句）═══"
TITLE_MOD_INFO = "# ═══ MOD：信息页、链接与 FAQ ═══"
TITLE_MOD_PERK = "# ═══ MOD：技能说明（含颜色码）═══"

# 内容归类用的分节名（与文件里的原文一致）
SEC_SUPPLEMENT = "补充（第 2 批）"
SEC_MARKS = "带颜色码 / 图标占位符的片段"
SEC_TEMPLATES = "模板条目"
SEC_MOD4 = "MOD 汉化第四批"
SEC_MOD6 = "MOD 汉化第六批"
SEC_MOD_BATCHES = ("MOD 汉化：Girls' Frontline", "MOD 汉化第二批",
                   "MOD 汉化第三批", "MOD 汉化第五批")

# 这两条其实不属于「格式标记」节（它们没有标记），挪回军营
MOVE_TO_BARRACKS = {"party privacy:", "assault rifle"}


def read_lines(path):
    with io.open(path, "r", encoding="utf-8", newline="") as fh:
        return [l.rstrip("\r\n") for l in fh]


def is_item(ln):
    s = ln.strip()
    return bool(s) and not s.startswith("#")


def is_sentence(key):
    return len(key) > 24 or key[-1:] in ".!?:"


lines = read_lines(SRC)

head, i = [], 0
while i < len(lines) and not lines[i].startswith(HEAD_MARK):
    head.append(lines[i])
    i += 1

sections = []
cur_title, cur_body = None, []
for ln in lines[i:]:
    if ln.startswith(HEAD_MARK):
        if cur_title is not None:
            sections.append([cur_title, cur_body])
        cur_title, cur_body = ln, []
    else:
        cur_body.append(ln)
if cur_title is not None:
    sections.append([cur_title, cur_body])


def items_of(body):
    return [l for l in body if is_item(l)]


def notes_of(body):
    return [l for l in body if l.strip().startswith("#")]


# ---- 抽池子 -----------------------------------------------------------------
pool = {"interface": [], "supplement": [], "marks": [], "templates": [],
        "mod_info": [], "mod_perk": [], "mod_other": []}
policy_notes = []

for title, body in sections:
    name = title.replace(HEAD_MARK, "").rstrip(" ═").strip()
    it, nt = items_of(body), notes_of(body)
    if SEC_SUPPLEMENT in name:
        pool["supplement"] += it
    elif SEC_MARKS in name:
        pool["marks"] += it
    elif SEC_TEMPLATES in name:
        pool["templates"] += it
    elif SEC_MOD4 in name:
        pool["mod_info"] += it
    elif SEC_MOD6 in name:
        pool["mod_perk"] += it
    elif any(b in name for b in SEC_MOD_BATCHES):
        pool["mod_other"] += it
    else:
        pool["interface"].append([title, it])
    # 「产品策略」那条注释要活下来，挂到 MOD 节开头
    for n in nt:
        if "产品策略" in n:
            policy_notes.append(n)

# ---- MOD 各批按内容分流（模板 / 长句 / 短条目）--------------------------------
mod_templates, mod_desc, mod_menu = [], [], []
for ln in pool["mod_other"]:
    key = ln.split("=", 1)[0].strip()
    if "*" in key:
        mod_templates.append(ln)
    elif is_sentence(key):
        mod_desc.append(ln)
    else:
        mod_menu.append(ln)
pool["templates"] += mod_templates

# ---- 「补充（第 2 批）」+ 两条无标记条目 -> 军营 -------------------------------
extra_barracks = pool["supplement"] + [l for l in pool["marks"]
                                       if l.split("=", 1)[0].strip() in MOVE_TO_BARRACKS]
pool["marks"] = [l for l in pool["marks"]
                 if l.split("=", 1)[0].strip() not in MOVE_TO_BARRACKS]

# ---- 重组输出 -----------------------------------------------------------------
out = [h for h in head]
while out and out[-1].strip() == "":
    out.pop()

new_sections = []
for title, it in pool["interface"]:
    if title == TITLE_BARRACKS:
        it = it + extra_barracks
    new_sections.append((title, it))
new_sections.append((TITLE_MOD_MENU, mod_menu))
new_sections.append((TITLE_MOD_DESC, mod_desc))
new_sections.append((TITLE_MOD_INFO, pool["mod_info"]))
new_sections.append((TITLE_MOD_PERK, pool["mod_perk"]))
new_sections.append((TITLE_TEMPLATES, pool["templates"]))
new_sections.append((TITLE_MARKS, pool["marks"]))

for title, it in new_sections:
    out.append("")
    out.append(title)
    if title.startswith("# ═══ MOD") and policy_notes:
        out.append(policy_notes[0])
    out += it

text = "\n".join(out) + "\n"

# ---- 断言：一个词条都不能丢、不能改 -------------------------------------------
def entry_map(ls):
    m = {}
    for l in ls:
        if is_item(l):
            k = l.split("=", 1)[0]
            m.setdefault(k, []).append(l)
    return m


before, after = entry_map(lines), entry_map(text.split("\n"))
missing = sorted(set(before) - set(after))
added = sorted(set(after) - set(before))
assert not missing and not added, "键集合变了！missing=%s added=%s" % (missing[:5], added[:5])
assert len(before) == len(after) and all(len(before[k]) == len(after[k]) for k in before)

report = []
report.append("条目数：%d -> %d（不变）" % (sum(len(v) for v in before.values()),
                                            sum(len(v) for v in after.values())))
report.append("分节：%d -> %d 节" % (len(sections), len(new_sections)))
report.append("")
report.append("=== 新分节结构 ===")
for title, it in new_sections:
    report.append("  %-58s %3d 条" % (title.replace(HEAD_MARK, "").rstrip(" ═"), len(it)))
report.append("")
report.append("MOD 池分流：菜单/选项值 %d 条、说明长句 %d 条、模板 %d 条"
              % (len(mod_menu), len(mod_desc), len(mod_templates)))
report.append("军营新增 %d 条（原「补充（第 2 批）」%d + 无标记条目 %d）"
              % (len(extra_barracks), len(pool["supplement"]), len(extra_barracks) - len(pool["supplement"])))
report.append("产品策略注释保留：%s" % bool(policy_notes))

with io.open(SRC, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(text)
print("\n".join(report))
