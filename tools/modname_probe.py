# -*- coding: utf-8 -*-
# 1) 从游戏目录 ui_dump.txt 里取出所有含 All-around 的 run 原始字节（repr）
# 2) 比对 仓库词库 / translate_zh0000.txt / translate_zh.txt.old 三份
import os, hashlib

GD = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
T7 = os.path.join(GD, "T7Patch")
REPO = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"

out = []

out.append("=== ui_dump.txt 里含 All-around 的 run（原始字节 repr）===")
dump = os.path.join(T7, "ui_dump.txt")
raw = open(dump, "rb").read()
seen = {}
for ln in raw.split(b"\n"):
    if b"all-around" in ln.lower():
        seen.setdefault(ln, 0)
        seen[ln] += 1
for ln, cnt in sorted(seen.items(), key=lambda kv: -kv[1]):
    out.append("  x%-3d %s" % (cnt, repr(ln)))
out.append("  不同形态数 = %d" % len(seen))

def stats(p):
    if not os.path.exists(p):
        return "  %-34s (不存在)" % os.path.basename(p)
    b = open(p, "rb").read()
    exact = tpl = 0
    for r in b.split(b"\n"):
        if len(r) > 1024: continue
        s = r.lstrip(b" \t")
        if not s or s[:1] in (b"#", b";") or b"=" not in s: continue
        k, v = s.split(b"=", 1)
        if not k.rstrip(b" \t") or not v.rstrip(b" \t"): continue
        if b"*" in k: tpl += 1
        else: exact += 1
    return "  %-34s %7d B  sha=%s  精确=%d 模板=%d 合计=%d" % (
        os.path.basename(p), len(b), hashlib.sha256(b).hexdigest()[:16].upper(), exact, tpl, exact + tpl)

out.append("")
out.append("=== 三份词库比对 ===")
for p in [REPO,
          os.path.join(T7, "translate_zh0000.txt"),
          os.path.join(T7, "translate_zh.txt.old"),
          os.path.join(T7, "translate_zh.txt")]:
    out.append(stats(p))

out.append("")
out.append("=== 仓库词库里是否已有这两条（精确/模板）===")
repo_has = []
for r in open(REPO, "rb").read().split(b"\n"):
    if b"all-around" in r.lower():
        repo_has.append(repr(r))
out += ["  " + x for x in repo_has] or ["  (无)"]

open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\modname_probe.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
print("ok")
