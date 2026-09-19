# -*- coding: utf-8 -*-
"""查 ui_dump.txt：截图里那些中文串到底有没有经过我们的 hook。

判定逻辑：ui_dump.txt 由 translate::Collect() 写出，只有经过 Lookup 的片段才会出现。
某串在 dump 里 => 它一定经过我们的翻译层；不在 => 我们够不着它。
"""
import io, os, re, sys

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\dump_query.txt"

lines = io.open(DUMP, encoding="utf-8", errors="replace").read().split("\n")
cjk = re.compile(r"[\u4e00-\u9fff]")

o = []
o.append("dump lines: %d" % len(lines))
o.append("含汉字的行: %d" % sum(1 for l in lines if cjk.search(l)))
o.append("含 '^' 的行 : %d" % sum(1 for l in lines if "^" in l))
o.append("")

needles = [
    "最近接触", "公开比赛", "团队死斗", "上进行", "人小队", "小时前", "转生大师",
    "公开对局", "最近玩家", "管理队伍", "在线排序",
    "Infection", "infection", "Team Deathmatch", "TEAM DEATHMATCH", "Public Match",
    "PLAYING", "RECENT", "FRIENDS", "GROUPS", "SOCIAL", "ONLINE", "Prestige Master",
    "Prestige", "hours ago", "Party", "PARTY", "Manage", "MANAGE",
]
o.append("=== 逐个 needle 在 dump 中的出现 ===")
for n in needles:
    low = n.lower()
    hits = [i for i, l in enumerate(lines) if low in l.lower()]
    o.append("  %-18s %3d 处%s" % (n, len(hits),
              ("" if not hits else "  |  " + " ; ".join(repr(lines[i])[:60] for i in hits[:4]))))
o.append("")

o.append("=== dump 里所有含汉字的行（前 40 条，看是谁写的）===")
shown = 0
for i, l in enumerate(lines):
    if cjk.search(l):
        o.append("  %5d  %s" % (i + 1, l[:90]))
        shown += 1
        if shown >= 40:
            break
if shown == 0:
    o.append("  （一条都没有 —— dump 里全是英文片段）")
o.append("")

o.append("=== dump 尾部 25 行 ===")
for i, l in enumerate(lines[-25:]):
    o.append("  %5d  %s" % (len(lines) - 25 + i + 1, l[:90]))
o.append("")

d = io.open(DICT, encoding="utf-8", errors="replace").read().split("\n")
keys = {}
for ln in d:
    if not ln or ln.startswith("#") or "=" not in ln:
        continue
    k, v = ln.split("=", 1)
    keys[k.strip().lower()] = v.strip()

o.append("=== 词库规模 ===")
o.append("  非注释行 %d, 键 %d" % (sum(1 for l in d if l and not l.startswith("#") and "=" in l), len(keys)))
o.append("")
o.append("=== 截图里那几个中文串，词库里有对应值吗（值侧反查）===")
for zh in ["最近接触过的玩家", "最近玩家", "公开比赛", "公开对局", "团队死斗", "转生大师",
           "上进行", "人在小队中", "小时前", "在线排序", "字母顺序", "管理队伍", "群组"]:
    owner = [k for k, v in keys.items() if v == zh]
    part = [k for k, v in keys.items() if zh in v]
    o.append("  %-16s 值完全等于: %-28s 作为子串出现在: %s"
             % (zh, (", ".join(owner) if owner else "—"),
                (", ".join(part[:4]) if part else "—")))

io.open(OUT, "w", encoding="utf-8").write("\n".join(o))
print("written", OUT)
