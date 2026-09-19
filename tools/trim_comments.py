"""精简词库注释：头部换成用户指定的版本，正文只留分节标题 + 两条必要提示。

规则：
  - 头部（文件开头的连续注释/空行）整段替换为 NEW_HEADER
  - 正文里的注释行：分节标题（`# ═══`）保留当目录；两条必要提示换成单行压缩版；
    其余解释性注释全部丢弃（含历史成因、批次日期、"仍未覆盖"清单）
  - 条目行原样保留 —— 本脚本只动注释，一个词条都不改
  - 连续空行压成一个
"""
import io
import os

SRC = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"

NEW_HEADER = [
    "# T7Patch UI 翻译词库",
    "# version: 2026-09-16",
    "# 匹配规则（实现见 src\\translate.cpp）：",
    "#   - 引擎会把一条 UI 文本拆成若干「片段」分别送出（片段之间是控制字节），本文件按片段匹配",
    "#   - 键里的 '*' 匹配任意文本（模板条目，见文件末尾）；值里的 '*' 按顺序填回捕获到的原文",
    "#   - 精确条目永远先于模板；模板之间「'*' 更少」的先试",
    "#   ⇒ 改完保存即生效（约 2 秒内热加载），不用重启游戏",
]

REPL_POLICY = "# ⚠️ 产品策略：mod 名 / 武器名 / 按键名 / 其他专有名词一律不翻（不要为它们加条目）。"
REPL_COLOR = "# 以下是「彩色技能名 + 说明」拼成的整行；^1/^3/^7 是颜色码，必须原样保留。"

with io.open(SRC, "r", encoding="utf-8", newline="") as fh:
    lines = fh.read().split("\n")

# ---- 头部：跳过开头的空行/注释 -------------------------------------------------
i = 0
while i < len(lines) and (lines[i].strip() == "" or lines[i].lstrip().startswith("#")):
    i += 1
body = lines[i:]

# ---- 正文：只放行条目、分节标题、两条压缩提示 -----------------------------------
out = []
dropped = []
for raw in body:
    s = raw.rstrip("\r")
    if s.strip() == "":
        out.append("")
        continue
    if s.lstrip().startswith("#"):
        t = s.strip()
        if t.startswith("# ═══"):
            out.append(s)                       # 分节标题 = 目录，保留
        elif "产品策略" in t:
            out.append(REPL_POLICY)
        elif "彩色技能名" in t:
            out.append(REPL_COLOR)
        else:
            dropped.append(t)
        continue
    out.append(s)

# ---- 连续空行压成一个 ---------------------------------------------------------
squashed = []
for s in out:
    if s == "" and squashed and squashed[-1] == "":
        continue
    squashed.append(s)

result = NEW_HEADER + [""] + squashed
text = "\n".join(result)
if not text.endswith("\n"):
    text += "\n"

entries_before = sum(1 for l in lines if "=" in l and not l.lstrip().startswith("#") and l.strip())
entries_after = sum(1 for l in result if "=" in l and not l.lstrip().startswith("#") and l.strip())
assert entries_before == entries_after, "条目数变了：%d -> %d" % (entries_before, entries_after)

with io.open(SRC, "w", encoding="utf-8", newline="\n") as fh:
    fh.write(text)

report = []
report.append("条目数：%d -> %d（不变，断言通过）" % (entries_before, entries_after))
report.append("总行数：%d -> %d" % (len(lines), len(result)))
report.append("丢弃的解释性注释 %d 行：" % len(dropped))
for d in dropped:
    report.append("  - %s" % (d[:78] + ("…" if len(d) > 78 else "")))
report.append("")
report.append("=== 新文件前 22 行 ===")
report.extend(result[:22])
print("\n".join(report))
