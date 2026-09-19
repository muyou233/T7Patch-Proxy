# -*- coding: utf-8 -*-
# Negative control: is ANY T7Patch (d3d11.dll) code/data pointer present in the captured memory?
import struct

DMP = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\blackops3.exe.BEYQBBUILD132.CL#13892626.1789445311.dmp"
blob = open(DMP, "rb").read()

def u32(o): return struct.unpack_from("<I", blob, o)[0]
def u64(o): return struct.unpack_from("<Q", blob, o)[0]

# all captured chunks
chunks = []
for k in range(u32(0x22320)):
    o = 0x22320 + 4 + k * 16
    st, ds, rv = u64(o), u32(o + 8), u32(o + 12)
    chunks.append((st, st + ds, rv))
print("chunks:", len(chunks), "bytes:", sum(e - s for s, e, _ in chunks))

CUR = 0x00007FF920DF0000            # our proxy d3d11.dll base
CUR_END = CUR + 0xCF000
SYS = 0x00007FF987FE0000            # system d3d11.dll
SYS_END = SYS + 0x260000

def scan_ranges(lo, hi, label):
    hits = []
    for st, en, rv in chunks:
        buf = blob[rv:rv + (en - st)]
        for off in range(0, len(buf) - 8 + 1, 8):
            v = struct.unpack_from("<Q", buf, off)[0]
            if lo <= v < hi:
                hits.append((st + off, v))
                if len(hits) > 40:
                    return hits
    print("\n%s: %d hit(s)" % (label, len(hits)))
    for a, v in hits[:40]:
        print("   stack %016X -> %016X" % (a, v))
    return hits

scan_ranges(CUR, CUR_END, "T7Patch proxy d3d11.dll range [%016X-%016X)" % (CUR, CUR_END))
scan_ranges(SYS, SYS_END, "system d3d11.dll range")
scan_ranges(0x00007FF6FBC00000, 0x00007FF6FBE00000, "blackops3 .data arena region")

print("\n=== sentinel search ===")
for name, val in (("0xFFEEDDCC44332212", 0xFFEEDDCC44332212),
                  ("0xFFEEDDCC44332211", 0xFFEEDDCC44332211),
                  ("0xFFEEDDCC44332210", 0xFFEEDDCC44332210)):
    pat = struct.pack("<Q", val)
    n, pos = 0, 0
    while True:
        i = blob.find(pat, pos)
        if i < 0: break
        n += 1; pos = i + 1
    print("  %s : %d occurrence(s) in whole dump" % (name, n))

print("\n=== T7Patch-ish strings anywhere in the dump ===")
for s in (b"t7patch", b"T7Patch", b"ZBR_VERSION", b"3.08"):
    print("  %-12s %d" % (s.decode(), blob.count(s)))
print("\n=== DONE ===")
