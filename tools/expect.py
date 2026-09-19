# -*- coding: utf-8 -*-
import os
GD = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\T7Patch"
out = []
out.append("translate_zh.txt present in game dir: %s" % os.path.exists(os.path.join(GD, "translate_zh.txt")))
out.append("deployed dll:")
import hashlib
p = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\d3d11.dll"
h = hashlib.sha256(open(p, "rb").read()).hexdigest().upper()
out.append("  size=%d sha256=%s" % (os.path.getsize(p), h[:16]))
# expected numbers from the embedded dictionary (same content as the repo source)
SRC = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
exact = tpl = 0
for raw in open(SRC, "rb").read().split(b"\n"):
    if len(raw) > 1024: continue
    s = raw.lstrip(b" \t")
    if not s or s[:1] in (b"#", b";") or b"=" not in s: continue
    k, v = s.split(b"=", 1)
    if not k.rstrip(b" \t") or not v.rstrip(b" \t"): continue
    if b"*" in k: tpl += 1
    else: exact += 1
out.append("expected log line for the built-in path:")
out.append("  init: translate=1, dictionary loaded from the built-in default (%d entries, %d templates, collect=1)" % (exact, tpl))
open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\expect.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
print("ok")
