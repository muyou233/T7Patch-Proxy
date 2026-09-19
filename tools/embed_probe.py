# -*- coding: utf-8 -*-
# Probe: does the built / deployed d3d11.dll already carry the current dictionary,
# and does MSBuild's resource step track translate_zh.txt as a dependency?
import io, os, re, sys

ROOT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private"
DICT = os.path.join(ROOT, "translate", "translate_zh.txt")
DLLS = [
    ("built",    os.path.join(ROOT, "x64", "Release", "d3d11.dll")),
    ("deployed", r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\d3d11.dll"),
]
TLOG = os.path.join(ROOT, "T7Patch", "x64", "Release", "T7Patch.tlog", "rc.read.1.tlog")
OUT = os.path.join(ROOT, ".codebuddy", "ref", "embed_probe.txt")

o = []
def p(s=""):
    o.append(s)

dict_bytes = open(DICT, "rb").read()
lines = dict_bytes.split(b"\n")
ver = [l for l in lines if l.startswith(b"# version:")]
entry_lines = [l for l in lines if l and not l.startswith(b"#") and b"=" in l]
p("== current repo dictionary ==")
p("  file      : %s" % DICT)
p("  bytes     : %d" % len(dict_bytes))
p("  lines     : %d" % len(lines))
p("  entries   : %d" % len(entry_lines))
p("  version   : %s" % (ver[0].decode("utf-8", "replace") if ver else "(none)"))
p("  head      : %r" % lines[0][:60])
p("  tail      : %r" % (lines[-2][:60] if len(lines) > 1 else b""))
p()

for tag, dll in DLLS:
    p("== %s dll ==" % tag)
    if not os.path.exists(dll):
        p("  MISSING %s" % dll)
        p()
        continue
    b = open(dll, "rb").read()
    st = os.stat(dll)
    p("  path      : %s" % dll)
    p("  size      : %d   mtime=%s" % (st.st_size, __import__("time").strftime("%Y-%m-%d %H:%M:%S", __import__("time").localtime(st.st_mtime))))
    p("  sha256[:16] = %s" % __import__("hashlib").sha256(b).hexdigest()[:16])
    # whole-file match = inner copy is identical to the repo dictionary
    p("  WHOLE-FILE dictionary embedded : %s" % (dict(dict_bytes=dict_bytes, dll=b) and (dict_bytes in b)))
    # version strings found anywhere in the image
    vs = re.findall(rb"# version: [0-9A-Za-z\-]+", b)
    p("  '# version:' hits in image       : %d  %s" % (len(vs), [v.decode() for v in vs]))
    # spot-check a few entries that only exist in the newest file
    for probe in [b"aquarium=", b"nuk3town=", b"fringe nightfall=", b"hold \x5e3f\x5e7 "]:
        p("  probe %-22r : %s" % (probe, (probe + b"\x00")[:0].__class__ and (probe in b)))
    p()

p("== MSBuild resource dependency log (rc.read.1.tlog) ==")
if os.path.exists(TLOG):
    raw = open(TLOG, "rb").read()
    try:
        txt = raw.decode("utf-16")
    except Exception:
        txt = raw.decode("utf-8", "replace")
    hits = [ln for ln in txt.splitlines() if "translate" in ln.lower()]
    p("  lines mentioning translate: %d" % len(hits))
    for h in hits[:20]:
        p("    %s" % h.strip())
else:
    p("  MISSING %s" % TLOG)
p()

open(OUT, "w", encoding="utf-8").write("\n".join(o))
print("\n".join(o).encode("utf-8", "replace").decode("utf-8", "replace"))
