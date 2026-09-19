# -*- coding: utf-8 -*-
# Where exactly do two builds of d3d11.dll differ inside .rdata?
# Used to prove a comment-only source change produced no code change: .text must
# hash equal, and every differing .rdata byte should fall inside the debug
# directory (PDB identity) rather than in real read-only data.
#
#   python rdata_ranges.py <a.dll> <b.dll>
import sys, struct

def u16(b, o): return struct.unpack_from("<H", b, o)[0]
def u32(b, o): return struct.unpack_from("<I", b, o)[0]

def sect(path, want):
    b = open(path, "rb").read()
    lfanew = u32(b, 0x3C)
    nsec = u16(b, lfanew + 6)
    optsz = u16(b, lfanew + 20)
    for i in range(nsec):
        s = lfanew + 24 + optsz + i * 40
        name = b[s:s + 8].rstrip(b"\x00").decode("latin-1")
        if name != want:
            continue
        praw, rsize = u32(b, s + 20), u32(b, s + 16)
        return b, praw, rsize
    raise SystemExit("no section " + want)

def dbgdir(path):
    b = open(path, "rb").read()
    lfanew = u32(b, 0x3C)
    opt = lfanew + 24
    dd = opt + (112 if u16(b, opt) == 0x20B else 96)
    rva, size = u32(b, dd + 6 * 8), u32(b, dd + 6 * 8 + 4)
    # map rva -> raw
    nsec = u16(b, lfanew + 6)
    optsz = u16(b, lfanew + 20)
    for i in range(nsec):
        s = lfanew + 24 + optsz + i * 40
        srva, svsize, srsize, spraw = u32(b, s + 12), u32(b, s + 8), u32(b, s + 16), u32(b, s + 20)
        if srva <= rva < srva + max(svsize, srsize):
            return spraw + (rva - srva), size
    return 0, 0

a, prawA, rsizeA = sect(sys.argv[1], ".rdata")
c, prawB, rsizeB = sect(sys.argv[2], ".rdata")
print("rdata raw: A", prawA, "B", prawB, "size", rsizeA, rsizeB)
loA, szA = dbgdir(sys.argv[1])
loB, szB = dbgdir(sys.argv[2])
print("debug dir raw: A [%d, %d)  B [%d, %d)" % (loA, loA + szA, loB, loB + szB))

diff = [i for i in range(rsizeA) if a[prawA + i] != c[prawB + i]]
print("differing bytes in .rdata: %d" % len(diff))
if not diff:
    raise SystemExit(0)
print("first=%d last=%d" % (diff[0], diff[-1]))
runs, start, prev = [], diff[0], diff[0]
for i in diff[1:]:
    if i != prev + 1:
        runs.append((start, prev)); start = i
    prev = i
runs.append((start, prev))
print("runs (%d):" % len(runs))
inside = 0
for s, e in runs:
    # diff offsets are .rdata-relative, the debug directory bounds are raw-file
    # offsets - convert before comparing, or every run looks "outside".
    rs, re_ = s + prawA, e + prawA
    inA = loA <= rs and re_ < loA + szA
    inB = loB <= rs and re_ < loB + szB
    inside += 1 if (inA or inB) else 0
    print("  [%d..%d] len=%d  inA=%s inB=%s" % (s, e, e - s + 1, inA, inB))
print("runs inside a debug directory: %d / %d" % (inside, len(runs)))
# show the debug directory content for both, as strings
for tag, b, lo, sz in (("A", a, loA, szA), ("B", c, loB, szB)):
    blob = b[lo:lo + sz]
    print(tag, "debug dir bytes:", blob[:64].hex())
