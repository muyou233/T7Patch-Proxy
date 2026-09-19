# -*- coding: utf-8 -*-
"""把 MEMORY.md 的当前全文存进 REF_notes.md（快照），之后 MEMORY.md 才能放心精简。"""
import io
import os

REF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "memory")
MEM = os.path.join(REF_DIR, "MEMORY.md")
REF = os.path.join(REF_DIR, "REF_notes.md")

mem = io.open(MEM, encoding="utf-8").read()
ref = io.open(REF, encoding="utf-8").read()
assert "MEMORY.md 全文快照" not in ref, "已经存过快照了，别重复追加"
assert len(mem) > 5000, "MEMORY.md 读进来不对"

hdr = ("\n\n---\n\n# 【MEMORY.md 全文快照】2026-09-16 20:50（瘦身前的完整版，逐字保留）\n\n"
       "系统在注入时把 MEMORY.md 截断了（超上限），所以它被重写成一份**索引**；\n"
       "下面是重写前那一版的**完整逐字快照**，任何在索引里看不到的细节都来这儿翻。\n\n"
       "```\n")
io.open(REF, "w", encoding="utf-8").write(ref.rstrip("\n") + hdr + mem.rstrip("\n") + "\n```\n")

print("快照已追加：MEMORY.md %d 字节 -> REF_notes.md 现 %d 字节" %
      (len(mem.encode("utf-8")), len(io.open(REF, encoding="utf-8").read().encode("utf-8"))))
