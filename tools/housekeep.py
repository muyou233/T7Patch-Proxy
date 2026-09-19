# -*- coding: utf-8 -*-
# Housekeeping: drop this round's scratch outputs, keep the evidence + the tools.
import os

REF = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools"
MEM = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\.codebuddy\memory"

DROP = ["dlog.txt", "logdict_run.txt", "expect_run.txt", "expect_all.txt",
        "probe_run2.txt", "deploy_out.txt", "wait_out.txt", "verify.txt",
        "bchk.txt", "proc.txt", "pre_deploy.txt", "res_dump.py", "wrap.txt"]

out = []
for name in DROP:
    p = os.path.join(REF, name)
    if os.path.exists(p):
        try:
            os.remove(p)
            out.append("removed  %s" % name)
        except OSError as exc:
            out.append("FAILED   %s : %r" % (name, exc))
    else:
        out.append("absent   %s" % name)

out.append("")
out.append("=== memory sizes ===")
for name in ["MEMORY.md", "REF_notes.md", "2026-09-16.md"]:
    p = os.path.join(MEM, name)
    with open(p, "rb") as f:
        n = len(f.read())
    out.append("  %-18s %8d B" % (name, n))

out.append("=== ref kept ===")
for name in sorted(os.listdir(REF)):
    p = os.path.join(REF, name)
    if os.path.isfile(p):
        out.append("  %-32s %8d B" % (name, os.path.getsize(p)))

text = "\n".join(out) + "\n"
with open(os.path.join(REF, "wrap.txt"), "w", encoding="utf-8") as f:
    f.write(text)
print(text)
