# -*- coding: utf-8 -*-
r"""Why do two builds of identical sources in different directories differ?

Compares .rdata between a pre-reorganisation build (flat layout) and the
current one (src/ layout): section sizes, and every path-ish string, so the
"the 16-byte .rdata delta is just the PDB path" hypothesis can be tested
instead of assumed.  (A path that got LONGER with the "src\" prefix should
make .rdata BIGGER -- the recorded delta was -16 bytes, i.e. smaller, so the
hypothesis is suspect.)

Usage: rdata_diff.py <a.dll> <b.dll>
"""
import hashlib
import struct
import sys

A = sys.argv[1]
B = sys.argv[2]
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\rdata_diff.txt"


def parse(path):
    with open(path, "rb") as f:
        data = f.read()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    optsz = struct.unpack_from("<H", data, pe + 20)[0]
    secs = []
    for i in range(nsec):
        o = pe + 24 + optsz + i * 40
        name = data[o:o + 8].rstrip(b"\x00").decode("latin-1")
        vsize, va, rawsize, rawptr = struct.unpack_from("<IIII", data, o + 8)
        secs.append((name, vsize, rawsize, rawptr))
    return data, secs


def sec_bytes(data, sec):
    return data[sec[3]:sec[3] + sec[2]]


def strings(blob, min_len=6):
    """ASCII runs and UTF-16LE runs, as (kind, text)."""
    res = []
    cur = bytearray()
    for b in blob:
        if 32 <= b < 127:
            cur.append(b)
        else:
            if len(cur) >= min_len:
                res.append(("a", cur.decode("latin-1")))
            cur = bytearray()
    if len(cur) >= min_len:
        res.append(("a", cur.decode("latin-1")))
    i = 0
    n = len(blob)
    cur = []
    while i + 1 < n:
        lo, hi = blob[i], blob[i + 1]
        if hi == 0 and 32 <= lo < 127:
            cur.append(chr(lo)); i += 2; continue
        if len(cur) >= min_len:
            res.append(("w", "".join(cur)))
        cur = []
        i += 1
    if len(cur) >= min_len:
        res.append(("w", "".join(cur)))
    return res


def report(tag, path):
    data, secs = parse(path)
    out = ["=== %s ===" % tag, "file: %s" % path,
           "whole sha256: %s" % hashlib.sha256(data).hexdigest().upper()]
    for s in secs:
        blob = sec_bytes(data, s)
        out.append("  %-8s vsize=%-8d rawsize=%-8d sha256=%s"
                   % (s[0], s[1], s[2], hashlib.sha256(blob).hexdigest()[:16]))
    return out, data, secs


lines = []
for tag, p in (("A (pre-reorg, flat layout)", A), ("B (post-reorg, src/ layout)", B)):
    r, data, secs = report(tag, p)
    lines += r
    lines.append("")

# ---- path-ish strings inside .rdata ------------------------------------
def rdata_strings(path):
    data, secs = parse(path)
    s = next(x for x in secs if x[0] == ".rdata")
    blob = sec_bytes(data, s)
    keep = []
    for kind, text in strings(blob):
        low = text.lower()
        if ("t7patch" in low or ".pdb" in low or ".cpp" in low
                or ".h" == text[-2:].lower() or "imgui" in low
                or "minhook" in low or "detours" in low):
            keep.append((kind, text))
    return keep


sa = rdata_strings(A)
sb = rdata_strings(B)
set_a = {(k, t) for k, t in sa}
set_b = {(k, t) for k, t in sb}

lines.append("=== path-ish strings in .rdata ===")
lines.append("A count=%d  B count=%d" % (len(sa), len(sb)))
lines.append("-- only in A --")
for k, t in sorted(set_a - set_b):
    lines.append("   [%s] len=%-4d %s" % (k, len(t), t))
lines.append("-- only in B --")
for k, t in sorted(set_b - set_a):
    lines.append("   [%s] len=%-4d %s" % (k, len(t), t))

lines.append("")
lines.append("=== every .pdb / .cpp string, with length ===")
for tag, lst in (("A", sa), ("B", sb)):
    tot = 0
    for k, t in lst:
        if ".pdb" in t.lower() or ".cpp" in t.lower():
            step = (len(t) + 1) * (2 if k == "w" else 1)
            tot += step
            lines.append("  %s [%s] len=%-4d bytes=%-4d %s" % (tag, k, len(t), step, t))
    lines.append("  %s total path bytes in .rdata = %d" % (tag, tot))

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("\n".join(lines))
