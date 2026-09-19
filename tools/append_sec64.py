# -*- coding: utf-8 -*-
"""把 sec64_append.txt 追加进今日工作日志（幂等：已有 §64 就拒绝）。"""
import io

LOG = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\.codebuddy\memory\2026-09-16.md"
SEC = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\sec64_append.txt"

log = io.open(LOG, "r", encoding="utf-8", newline="").read()
assert "## §64" not in log, "日志里已经有 §64 了，别重复追加"
add = io.open(SEC, "r", encoding="utf-8", newline="").read().lstrip("\n")
io.open(LOG, "w", encoding="utf-8", newline="").write(log.rstrip("\n") + "\n" + add)
print("appended %d chars; log now %d chars" % (len(add), len(log) + len(add) + 1))
