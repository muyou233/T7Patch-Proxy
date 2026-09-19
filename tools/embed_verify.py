# -*- coding: utf-8 -*-
# Verify that the dll's built-in RCDATA dictionary is byte-identical to the
# repo source.  Anchors on the first / last bytes of the source file, carves the
# region out of the image and compares it, so it also reports WHERE they differ
# if rc.exe altered anything.
import os, hashlib, time

ROOT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private"
# [LOCAL] 2026-09-17: 内置资源改为**冻结副本**（`src/translate_default.rc` 指向它）。
#   ⇒ 本工具比对的真不变量 = 「dll ↔ 冻结副本」；线上词库只作为"漂移量"参考打印出来。
#   刷新冻结副本的流程见 translate_default.rc 的注释：线上词库定稿 → push → 字节复制 → 重编。
PINNED = os.path.join(ROOT, "translate", "translate_zh.builtin.txt")
LIVE = os.path.join(ROOT, "translate", "translate_zh.txt")
DICT = PINNED  # 下面的比对逻辑一律对着冻结副本，不要改回 LIVE
DLLS = [
    ("built",    os.path.join(ROOT, "x64", "Release", "d3d11.dll")),
    ("deployed", r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\d3d11.dll"),
]
OUT = os.path.join(ROOT, ".codebuddy", "ref", "embed_verify.txt")


def stats(path):
    b = open(path, "rb").read()
    lines = b.split(b"\n")
    ent = [l for l in lines if l and not l.startswith(b"#") and b"=" in l]
    ver = next((l for l in lines if l.startswith(b"# version:")), b"(none)")
    return b, lines, ent, ver


src, src_lines, src_entries, src_ver = stats(PINNED)
live, live_lines, live_entries, live_ver = stats(LIVE)
HEAD = src[:64]
TAIL = src[-64:]
# 探针改为"冻结副本自己的版本行"：以前硬编码版本串（如 2026-09-16g）会长期假报 False，误导判断。
PROBES = [src_ver]

o = []
def p(s=""):
    o.append(s)

p("== PINNED built-in snapshot (this is what translate_default.rc embeds) ==")
p("  path=%s" % PINNED)
p("  bytes=%d  lines=%d  entries=%d  %s" % (len(src), len(src_lines),
                                            len(src_entries), src_ver.decode("utf-8", "replace")))
p("  sha256=%s" % hashlib.sha256(src).hexdigest()[:16])
p()
p("== LIVE dictionary in the repo (feeds deploy / the update button; NOT the built-in) ==")
p("  path=%s" % LIVE)
p("  bytes=%d  lines=%d  entries=%d  %s  sha256=%s"
  % (len(live), len(live_lines), len(live_entries), live_ver.decode("utf-8", "replace"),
     hashlib.sha256(live).hexdigest()[:16]))
p("  drift vs pinned: entries %+d ; byte-identical to pinned: %s"
  % (len(live_entries) - len(src_entries), live == src))
p()

for tag, dll in DLLS:
    p("== %s dll ==" % tag)
    if not os.path.exists(dll):
        p("  MISSING %s" % dll)
        p()
        continue
    b = open(dll, "rb").read()
    st = os.stat(dll)
    p("  path=%s" % dll)
    p("  size=%d  mtime=%s  sha256=%s" % (
        st.st_size, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
        hashlib.sha256(b).hexdigest()[:16]))

    i = b.find(HEAD)
    j = b.find(TAIL, i) if i >= 0 else -1
    if i < 0 or j < 0:
        p("  !! dictionary NOT found in image (head=%s / tail=%s)" % (i >= 0, j >= 0))
        p()
        continue
    region = b[i:j + len(TAIL)]
    identical = (region == src)
    p("  embedded dictionary at offset %d..%d (%d bytes)" % (i, j + len(TAIL), len(region)))
    p("  BYTE-IDENTICAL to source : %s" % identical)
    if not identical:
        p("  size delta = %+d" % (len(region) - len(src)))
        n = min(len(region), len(src))
        diffs = [k for k in range(n) if region[k] != src[k]]
        p("  differing byte count     = %d" % len(diffs))
        if diffs:
            k = diffs[0]
            p("  first diff at %d: embedded=%r source=%r" % (k, region[k:k+40], src[k:k+40]))
        if len(region) != len(src):
            p("  tail embedded=%r" % region[len(src) - 20:len(src) + 40])
    rl = region.split(b"\n")
    ent = [l for l in rl if l and not l.startswith(b"#") and b"=" in l]
    ver = next((l for l in rl if l.startswith(b"# version:")), b"(none)")
    p("  embedded: lines=%d  entries=%d  %s" % (len(rl), len(ent), ver.decode("utf-8", "replace")))
    for pr in PROBES:
        p("    probe %-30r : %s" % (pr, pr in b))
    p()

open(OUT, "w", encoding="utf-8").write("\n".join(o))
print("\n".join(o))
