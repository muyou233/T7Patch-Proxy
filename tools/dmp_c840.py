# -*- coding: utf-8 -*-
# Decisive check: does ANY captured chunk hold crashes.log's stack snapshot at 0x754E56C840?
import struct

DMP = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\blackops3.exe.BEYQBBUILD132.CL#13892626.1789445311.dmp"
blob = open(DMP, "rb").read()

def u32(o): return struct.unpack_from("<I", blob, o)[0]
def u64(o): return struct.unpack_from("<Q", blob, o)[0]

chunks = []
for k in range(u32(0x22320)):
    o = 0x22320 + 4 + k * 16
    st, ds, rv = u64(o), u32(o + 8), u32(o + 12)
    chunks.append((st, st + ds, rv))
chunks.sort()

TARGET = 0x754E56C840
print("=== chunks covering %016X ===" % TARGET)
cov = [c for c in chunks if c[0] <= TARGET < c[1]]
print("count:", len(cov))
for st, en, rv in cov:
    off = rv + (TARGET - st)
    q = [struct.unpack_from("<Q", blob, off + 8 * i)[0] for i in range(16)]
    print("  chunk %016X-%016X rva=0x%X size=%d" % (st, en, rv, en - st))
    print("    @C840: " + " ".join("%016X" % v for v in q[:8]))
    print("    @C880: " + " ".join("%016X" % v for v in q[8:]))

print("\n=== full chunk list (top 12 by start) ===")
for st, en, rv in chunks[:12]:
    print("  %016X - %016X  rva=0x%X  %d bytes" % (st, en, rv, en - st))

print("\n=== raw 48 bytes of every ThreadList entry (id, teb, stackstart, datasize, stkrva, ctxsize, ctxrva) ===")
n = u32(0x6f0)
print("thread count:", n)
for k in range(n):
    to = 0x6f0 + 4 + k * 48
    raw = blob[to:to + 48]
    tid = u32(to)
    teb = u64(to + 16)
    sstart = u64(to + 24)
    dsz = u32(to + 32)
    srva = u32(to + 36)
    csz = u32(to + 40)
    crva = u32(to + 44)
    tag = "  <== FAULT THREAD" if tid == 19412 else ""
    print("  tid=%-6d teb=%016X stack=%016X sz=%-6d rva=0x%-6X ctx=%d@0x%X%s" % (tid, teb, sstart, dsz, srva, csz, crva, tag))
print("\n=== DONE ===")
