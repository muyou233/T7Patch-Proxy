# -*- coding: utf-8 -*-
"""追加 §68 到今日日志（append-only，先查重）。"""
import io
import os

REF = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(os.path.dirname(REF), "memory", "2026-09-16.md")
SRC = os.path.join(REF, "sec68_append.txt")

body = io.open(SRC, encoding="utf-8").read().rstrip("\n")
assert "§68" in body and len(body) > 1000, "待追加内容不对"

log = io.open(LOG, encoding="utf-8").read()
assert "## §68 线索二（调用点指纹）采集完成" not in log, "§68 已经追加过了，别重复"

io.open(LOG, "w", encoding="utf-8").write(log.rstrip("\n") + "\n" + body + "\n")

new = io.open(LOG, encoding="utf-8").read()
lines = new.split("\n")
print("今日日志: %d 字节 / %d 行" % (len(new.encode("utf-8")), len(lines)))
print("--- 尾部 6 行 ---")
for l in lines[-6:]:
    print(l)
