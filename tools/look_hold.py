# -*- coding: utf-8 -*-
import io

DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
raw = io.open(DICT, "rb").read()
EOL = b"\r\n" if b"\r\n" in raw else b"\n"
lines = raw.split(EOL)
out = ["EOL=%r  lines=%d" % (EOL, len(lines))]
for i, ln in enumerate(lines):
    if b"^3f^7" in ln.lower() or b"hold ^3" in ln.lower():
        out.append("%4d  [%s]  %r" % (i + 1, "LINE-START" if ln.startswith(b"^3f^7 ") else "other",
                                      ln[:80]))
out.append("")
out.append("start-with-^3f^7 count: %d" % sum(1 for ln in lines if ln.startswith(b"^3f^7 ")))
out.append("start-with-hold count:  %d" % sum(1 for ln in lines if ln.startswith(b"hold ^3f^7 ")))
io.open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\look_hold.txt", "w",
        encoding="utf-8").write("\n".join(out) + "\n")
print("ok")
