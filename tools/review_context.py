# -*- coding: utf-8 -*-
r"""Where do the "needs human review" strings actually appear?

dict_triage.py buckets them; this finds each one in ui_dump.txt and prints the
surrounding lines, because the neighbours are what identify the screen the
string came from (the dump itself is a flat list, one string per line).
"""
import io

DUMP = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\T7Patch\ui_dump.txt"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\review_context.txt"

ITEMS = ["usermaps", "Ironic*", "AyerRex", "Twitter", "alvaro", "Insane",
         "Mechty", "muyou", "Henry", "black", "NerSo", "Bruce", "yayu",
         "king", "nick", "Less", "More", "CDP", "Ju", "BB", "VS", "ID"]

lines = io.open(DUMP, "r", encoding="utf-8", errors="replace").read().split("\n")
stripped = [ln.strip() for ln in lines]

out = ["dump: %s" % DUMP, "lines: %d" % len(lines),
       "（查找方式：整行相等优先；没有再退回子串匹配）", ""]

for item in ITEMS:
    exact = [i for i, s in enumerate(stripped) if s == item]
    mode = "整行"
    hits = exact
    if not hits:
        hits = [i for i, s in enumerate(stripped) if item in s]
        mode = "子串"

    out.append("### %-12s 命中 %d 处（%s）" % (item, len(hits), mode))
    if not hits:
        out.append("    <dump 里找不到>")
        out.append("")
        continue

    lo_all = min(hits)
    lo = max(0, lo_all - 4)
    hi = min(len(lines), lo_all + 5)
    for i in range(lo, hi):
        mark = "  <<<" if i in hits else ""
        out.append("   %5d | %s%s" % (i + 1, lines[i], mark))
    if len(hits) > 1:
        out.append("   （其它出现行号：%s）" % ", ".join(str(h + 1) for h in hits[1:8]))
    out.append("")

io.open(OUT, "w", encoding="utf-8").write("\n".join(out))
print("written", OUT)
