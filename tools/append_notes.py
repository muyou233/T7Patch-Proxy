# -*- coding: utf-8 -*-
"""把本轮细节追加进 REF_notes.md 与当日日志（字节级追加，避免 PS 编码坑）。"""
import io, os
BASE = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\.codebuddy"
MEM = os.path.join(BASE, "memory")

JOBS = [
    (os.path.join(BASE, "ref", "_append_ref.md"),
     os.path.join(MEM, "REF_notes.md")),
    (os.path.join(BASE, "ref", "_append_log.md"),
     os.path.join(MEM, "2026-09-16.md")),
]

for src, dst in JOBS:
    chunk = open(src, "rb").read()
    cur = open(dst, "rb").read() if os.path.exists(dst) else b""
    before = len(cur)
    if cur and not cur.endswith(b"\n"):
        cur += b"\n"
    open(dst, "wb").write(cur + chunk)
    print("%-28s %7d -> %7d B" % (os.path.basename(dst), before, os.path.getsize(dst)))
