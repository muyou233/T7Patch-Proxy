# -*- coding: utf-8 -*-
# Module-list layout check + stack forensics for the crashing thread.
import struct, os, datetime

DMP = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\blackops3.exe.BEYQBBUILD132.CL#13892626.1789445311.dmp"
f = open(DMP, "rb")
blob = f.read()
size = len(blob)
print("file size:", size, hex(size))

def u32(o): return struct.unpack_from("<I", blob, o)[0]
def u64(o): return struct.unpack_from("<Q", blob, o)[0]

ML = 0x10f0
print("\n=== ModuleList raw check @0x%X ===" % ML)
print("count field:", u32(ML))
for k in range(3):
    so = ML + 4 + k * 108
    print("entry %d @0x%X: base=%016X size=%d tds=%u(%s) nameRva@16=%08X nameRva@20=%08X" % (
        k, so, u64(so), u32(so + 8), u32(so + 16),
        datetime.datetime.fromtimestamp(u32(so + 16)).strftime("%Y-%m-%d %H:%M") if 1e9 < u32(so + 16) < 2e9 else "n/a",
        u32(so + 16), u32(so + 20)))
    print("   raw:", " ".join("%02X" % b for b in blob[so:so + 40]))

print("\n=== unicode strings in dump (length-prefixed MINIDUMP_STRING) ===")
for name in ("blackops3.exe", "d3d11.dll", "kernel32.dll", "ntdll.dll", "steam_api64.dll",
             "d3dcompiler_47.dll", "d3dcompiler_46.dll", "gameoverlayrenderer64.dll"):
    pat = struct.pack("<I", len(name) * 2) + name.encode("utf-16-le")
    pos, hits = 0, []
    while True:
        i = blob.find(pat, pos)
        if i < 0: break
        hits.append(i); pos = i + 1
    print("  %-26s len-prefixed at: %s" % (name, [hex(h) for h in hits] or "NONE"))

# do these offsets line up with module entries?
print("\n=== which entry owns a plausible name RVA? ===")
cand = {}
for k in range(u32(ML)):
    so = ML + 4 + k * 108
    cand.setdefault(u32(so + 20), []).append((k, u64(so)))
    cand.setdefault(u32(so + 24), []).append((k, u64(so), "off+24"))
inrange = {r: v for r, v in cand.items() if 0 < r < size}
print("  name-rva candidates that fall inside the file:", len(inrange), "of", len(cand))
for r, v in list(inrange.items())[:10]:
    print("   rva %08X -> %s" % (r, v))

# --- thread/exception info
thr = None
for k in range(u32(0x6f0)):
    to = 0x6f0 + 4 + k * 48
    if u32(to) == 19412:
        thr = (u64(to + 16), u32(to + 24), u32(to + 28))
print("\n=== fault thread 19412 stack ===")
print("  StartOfMemoryRange=%016X DataSize=%d Rva=0x%X" % thr)

RSP = 0x754E56FA90
CAP_S, CAP_DSZ, CAP_RVA = thr
CAP_E = CAP_S + CAP_DSZ
print("  captured range: %016X - %016X  (Rsp inside: %s)" % (CAP_S, CAP_E, CAP_S <= RSP < CAP_E))

def rd(a, n=8):
    if not (CAP_S <= a and a + n <= CAP_E):
        return None
    return blob[CAP_RVA + (a - CAP_S): CAP_RVA + (a - CAP_S) + n]

# module table (base/size are valid; names unknown)
mods = []
for k in range(u32(ML)):
    so = ML + 4 + k * 108
    mods.append((u64(so), u32(so + 8)))
mods.sort(key=lambda m: m[0])
def owner(a):
    for base, sz in mods:
        if base <= a < base + sz:
            return "mod@%016X +0x%X" % (base, a - base)
    return "<unmapped>"

print("\n=== [Rsp .. Rsp+0x580] stack words (caller chain lives ABOVE Rsp) ===")
for a in range(RSP - 0x40, RSP + 0x580, 8):
    v = rd(a)
    if v is None: continue
    q = struct.unpack("<Q", v)[0]
    mark = ""
    if q == 0x7FF727D04700: mark = "   <<< THE BAD TARGET"
    print("  %016X %s  %016X  %s%s" % (a, "*" if a == RSP else " ", q, owner(q), mark))

print("\n=== window around the crashes.log frame (Rsp=000000754E56C840) ===")
for a in range(0x754E56C840 - 0x20, 0x754E56C840 + 0x60, 8):
    v = rd(a)
    if v is None:
        print("  %016X  <not captured>" % a); continue
    q = struct.unpack("<Q", v)[0]
    print("  %016X %s %016X  %s" % (a, "*" if a == 0x754E56C840 else " ", q, owner(q)))

f.close()
print("\n=== DONE ===")
