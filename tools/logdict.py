# -*- coding: utf-8 -*-
import os, glob
GD = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\T7Patch"
out = []
out.append("=== folder ===")
for n in sorted(os.listdir(GD)):
    p = os.path.join(GD, n)
    if os.path.isfile(p):
        out.append("  %-28s %8d B  %s" % (n, os.path.getsize(p),
            __import__("time").strftime("%H:%M:%S", __import__("time").localtime(os.path.getmtime(p)))))
    else:
        out.append("  %-28s <dir>" % n)
# any renamed dictionary?
out.append("=== dictionary candidates ===")
for p in glob.glob(os.path.join(GD, "translate*")):
    out.append("  " + p)
out.append("=== init lines from t7patch.log (all) ===")
for log in [os.path.join(GD, "t7patch.log"), os.path.join(GD, "t7patch.log.old")]:
    if not os.path.exists(log):
        continue
    out.append("--- %s (mtime %s) ---" % (os.path.basename(log),
        __import__("time").strftime("%Y-%m-%d %H:%M:%S", __import__("time").localtime(os.path.getmtime(log)))))
    data = open(log, "rb").read().decode("utf-8", "replace")
    keep = [ln for ln in data.splitlines()
            if "translat=" in ln or "dictionary" in ln or "wordlist" in ln or "built-in" in ln]
    out += keep[-40:] if keep else ["(no dictionary/translate lines at all)"]
open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\logdict.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
print("ok")
