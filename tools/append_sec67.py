# -*- coding: utf-8 -*-
"""追加 §67 到今日日志（append-only，先查重）。"""
import io
import os

REF = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(os.path.dirname(REF), "memory", "2026-09-16.md")
SRC = os.path.join(REF, "sec67_append.txt")

body = io.open(SRC, encoding="utf-8").read().rstrip("\n")
assert "§67" in body and len(body) > 1000, "待追加内容不对"

log = io.open(LOG, encoding="utf-8").read()
assert "## §67 社交界面的 Steam 好友名" not in log, "§67 已经追加过了，别重复"

io.open(LOG, "w", encoding="utf-8").write(log.rstrip("\n") + "\n" + body + "\n")

new = io.open(LOG, encoding="utf-8").read()
lines = new.split("\n")
print("今日日志: %d 字节 / %d 行" % (len(new.encode("utf-8")), len(lines)))
print("--- 尾部 8 行 ---")
for l in lines[-8:]:
    print(l)
