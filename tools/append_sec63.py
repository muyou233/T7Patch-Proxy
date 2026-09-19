# -*- coding: utf-8 -*-
"""把 §63 追加到今天的工作日志（append-only，UTF-8 无 BOM）。"""
import io
import os

DAY = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\.codebuddy\memory\2026-09-16.md"
SEC = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\sec63_append.txt"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\append_sec63.txt"

section = io.open(SEC, encoding="utf-8").read()
body = io.open(DAY, encoding="utf-8", newline="").read()
if "## §63 " in body:
    raise SystemExit("already appended")
if not body.endswith("\n"):
    body += "\n"
io.open(DAY, "w", encoding="utf-8", newline="").write(body + section)
io.open(OUT, "w", encoding="utf-8").write(
    "day log now %d bytes\n%s" % (os.path.getsize(DAY), (body + section)[-300:]))
print("ok")
