# -*- coding: utf-8 -*-
# Append the §65c block to today's daily log, refusing to double-append.
import io

SRC = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\sec65c_append.txt"
DST = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\.codebuddy\memory\2026-09-16.md"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\append_sec65c.txt"

add = io.open(SRC, encoding="utf-8").read()
old = io.open(DST, encoding="utf-8").read()
marker = "## 65c. 方案选型：玩家名防撞"
assert marker not in old, "已经有 §65c 了，别重复追加"
if not old.endswith("\n"):
    old += "\n"
new = old + add
io.open(DST, "w", encoding="utf-8", newline="").write(new)

msg = ["ok: +%d chars" % len(add), "old=%d new=%d chars" % (len(old), len(new))]
io.open(OUT, "w", encoding="utf-8").write("\n".join(msg))
print("\n".join(msg))
