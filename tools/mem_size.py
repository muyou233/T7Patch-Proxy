# -*- coding: utf-8 -*-
import os

D = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\.codebuddy\memory"
out = []
for name in sorted(os.listdir(D)):
    p = os.path.join(D, name)
    if os.path.isfile(p):
        n = os.path.getsize(p)
        with open(p, "rb") as f:
            data = f.read()
        try:
            chars = len(data.decode("utf-8"))
        except UnicodeDecodeError:
            chars = -1
        out.append("%-16s %7d bytes  %6d chars" % (name, n, chars))
open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\mem_size.txt", "w", encoding="utf-8").write("\n".join(out))
