"""带标记（^X）条目的自动核对。

先分清 BO3 UI 文本里的三种标记 —— 它们的语义完全不同，混为一谈会出事：
    ^数字    颜色码（^1 红 / ^3 黄 / ^7 默认色 …）          可以自动识别
    ^B名字^  按键 / 图标绑定（BUTTON_MOUSE_LEFT、mouseWheelUp）  **不是颜色**，必须原样保留
    $(...)   运行时属性绑定（$(lobbyRoot.lobbyList.playerCount)）必须原样保留

本脚本做三件事：
  1) 列出采集文件里所有带标记的串（含标记序列），给人工对照
  2) 核对词库里带标记的条目：**键里的标记序列**是否与采集到的原文逐一致
     —— 键必须逐字节匹配游戏送来的片段，标记位置抄错就永远匹配不上
  3) 反向找：采集里有、词库里没有的带标记串（= 漏翻）
"""
import io
import os
import re

GAME_DUMP = (r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
             r"\T7Patch\ui_dump.txt")
DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"

MARK = re.compile(r"\^[0-9A-Za-z]")


def strip_marks(s):
    return MARK.sub("", s)


def marks(s):
    return [m.group(0).lower() for m in MARK.finditer(s)]


def read(path):
    if not os.path.exists(path):
        return []
    with io.open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        return [l.rstrip("\r\n") for l in fh]


def trim(s):
    """两端剥掉 <= 0x20 —— 必须与运行时一致。

    采集文件里有不少行还带着 \\x15/\\x14 包装字节（SPEND ^B...^ FOR ... 那一批就是），
    Python 的 str.strip() 只认空白，剥不掉它们。第一版忘了这一步，就把 4 条错报成
    "采集里找不到原文"。
    """
    i, j = 0, len(s)
    while i < j and ord(s[i]) <= 0x20:
        i += 1
    while j > i and ord(s[j - 1]) <= 0x20:
        j -= 1
    return s[i:j]


dump_raw = [l for l in read(GAME_DUMP) if trim(l) and not l.lstrip().startswith("#")]
dump_all = sorted(set(trim(l) for l in dump_raw))

# dump 是跨进程追加的，里面混着 2026-09-15 首版采集器写的**整串**（整串含 \x15 包装
# ⇒ 字符串中间会出现控制字节）。现在按片段记录，段内不该再有控制字节，所以这类行是旧数据，
# 必须剔除：它们的 base 带着 \x15，永远对不上任何键，会被误报成"漏翻"
# （'^3[P^7] \x15PERSONALIZE' 就是这么骗过我一次 —— 我还照它加了个永远匹配不上的键）。
stale = [d for d in dump_all if any(ord(c) < 0x20 for c in d)]
dump = [d for d in dump_all if not any(ord(c) < 0x20 for c in d)]

entries = []
for ln in read(DICT):
    if not ln.strip() or ln.lstrip().startswith("#") or "=" not in ln:
        continue
    k, v = ln.split("=", 1)
    entries.append((trim(k), trim(v)))

# 采集原文的归一化索引（去标记 + 小写）
by_base = {}
for d in dump:
    by_base.setdefault(strip_marks(d).lower(), []).append(d)

out = []
out.append("采集：%d 行原始 / %d 条去重（另有 %d 条旧格式整串行已剔除）；其中带标记 %d 条"
           % (len(dump_raw), len(dump), len(stale),
              sum(1 for d in dump if MARK.search(d))))
out.append("词库：%d 条；其中带标记 %d 条" % (len(entries), sum(1 for k, _ in entries if MARK.search(k))))
out.append("")
out.append("=== 采集里全部带标记的串 ===")
for d in dump:
    if MARK.search(d):
        out.append("  %-22s %s" % ("[" + " ".join(marks(d)) + "]", d[:96]))

out.append("")
out.append("=== 词库带标记条目：键的标记序列 与 采集原文 的核对 ===")
dict_base = set()
ok = bad = orphan = 0
for k, v in entries:
    dict_base.add(strip_marks(k).lower())
    if not MARK.search(k):
        continue
    cand = by_base.get(strip_marks(k).lower(), [])
    if not cand:
        orphan += 1
        out.append("  ? 采集里找不到对应原文：%s" % k[:84])
        continue
    want = marks(cand[0])
    got = marks(k)
    if want == got:
        ok += 1
    else:
        bad += 1
        out.append("  ✗ 标记不一致")
        out.append("      键    ：%s" % k[:88])
        out.append("      采集  ：%s" % cand[0][:88])
        out.append("      键=%s  采集=%s" % (" ".join(got), " ".join(want)))
out.append("  一致 %d 条 / 不一致 %d 条 / 采集里无原文 %d 条" % (ok, bad, orphan))

out.append("")
out.append("=== 漏翻：采集里有标记、词库里没有的串 ===")
miss = [d for d in dump if MARK.search(d) and strip_marks(d).lower() not in dict_base]
for d in miss:
    out.append("  %-22s %s" % ("[" + " ".join(marks(d)) + "]", d[:96]))
if not miss:
    out.append("  （无）")

txt = "\n".join(out)
print(txt)
