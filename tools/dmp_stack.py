# -*- coding: utf-8 -*-
# Corrected forensics: thread stack parse (TEB is 8 bytes!), module names, stack chain.
import struct, datetime

DMP = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\blackops3.exe.BEYQBBUILD132.CL#13892626.1789445311.dmp"
blob = open(DMP, "rb").read()
size = len(blob)

def u32(o): return struct.unpack_from("<I", blob, o)[0]
def u64(o): return struct.unpack_from("<Q", blob, o)[0]

def mdstr(rva):
    if not (0 < rva < size - 4):
        return "<bad rva %08X>" % rva
    n = u32(rva)
    raw = blob[rva + 4: rva + 4 + n]
    if n and n % 2 == 0:
        s = raw.decode("utf-16-le", "replace").rstrip("\x00")
        if all(32 <= ord(c) < 127 for c in s if c):
            return s
    return raw.decode("latin-1", "replace").rstrip("\x00")

ML = 0x10f0
nmod = u32(ML)
mods = []
for k in range(nmod):
    so = ML + 4 + k * 108
    mods.append((u64(so), u32(so + 8), u32(so + 16), mdstr(u32(so + 20))))
mods.sort(key=lambda m: m[0])
print("=== MODULES (%d) ===" % nmod)
for base, sz, tds, nm in mods:
    print("  %016X - %016X  %10d  %s" % (base, base + sz, sz, nm))

def owner(a):
    for base, sz, tds, nm in mods:
        if base <= a < base + sz:
            return "%s+0x%X" % (nm, a - base)
    return "<UNMAPPED>"

# exception
EX = 0x648
tid = u32(EX)
code = u32(EX + 8)
addr = u64(EX + 24)
npar = u32(EX + 32)
info = [u64(EX + 40 + j * 8) for j in range(npar)]
print("\n=== EXCEPTION ===")
print("  tid=%d code=%08X addr=%016X (%s) params=%s" % (tid, code, addr, owner(addr), [hex(v) for v in info]))

# thread
thr = None
for k in range(u32(0x6f0)):
    to = 0x6f0 + 4 + k * 48
    if u32(to) == tid:
        thr = (u64(to + 16), u64(to + 24), u32(to + 32), u32(to + 36), u32(to + 40), u32(to + 44))
print("\n=== FAULT THREAD 19412 ===")
print("  Teb=%016X  StackStart=%016X StackDataSize=%d StackRva=0x%X  CtxSize=%d CtxRva=0x%X" % thr)
S, DSZ, SRVA = thr[1], thr[2], thr[3]
E = S + DSZ
print("  stack captured: %016X - %016X (%d bytes)" % (S, E, DSZ))

# memory list chunks (for fallback)
chunks = []
for k in range(u32(0x22320)):
    o = 0x22320 + 4 + k * 16
    st, ds, rv = u64(o), u32(o + 8), u32(o + 12)
    chunks.append((st, st + ds, rv))
def memfind(a):
    for st, en, rv in chunks:
        if st <= a < en: return (st, en, rv)
    return None
def rd(a, n=8):
    # prefer thread stack blob, else memory list
    if S <= a and a + n <= E and SRVA:
        return blob[SRVA + (a - S): SRVA + (a - S) + n]
    m = memfind(a)
    if m and m[0] <= a and a + n <= m[1]:
        return blob[m[2] + (a - m[0]): m[2] + (a - m[0]) + n]
    return None

RSP = 0x754E56FA90
print("  Rsp=%016X inside stack capture: %s   inside memlist: %s" % (RSP, S <= RSP < E, memfind(RSP) is not None))

print("\n=== STACK WORDS around Rsp (callers are at HIGHER addresses) ===")
for a in range(RSP - 0x80, RSP + 0x500, 8):
    v = rd(a)
    if v is None:
        print("  %016X  <not captured>" % a); continue
    q = struct.unpack("<Q", v)[0]
    tag = " <== RSP" if a == RSP else ""
    if q == addr: tag += "   <<< THE BAD TARGET"
    print("  %016X  %016X  %s%s" % (a, q, owner(q), tag))

print("\n=== STACK WINDOW around crashes.log Rsp=000000754E56C840 ===")
for a in range(0x754E56C810, 0x754E56C880, 8):
    v = rd(a)
    if v is None:
        print("  %016X  <not captured>" % a); continue
    q = struct.unpack("<Q", v)[0]
    print("  %016X %s %016X  %s" % (a, "*" if a == 0x754E56C840 else " ", q, owner(q)))

print("\n=== QWORD scan: where does the bad target %016X appear at all? ===" % addr)
pat = struct.pack("<Q", addr)
pos, hits = 0, []
while True:
    i = blob.find(pat, pos)
    if i < 0: break
    hits.append(i); pos = i + 1
for h in hits:
    where = ""
    for st, en, rv in chunks:
        if rv <= h < rv + (en - st):
            where = "in memory chunk %016X-%016X at %016X" % (st, en, st + (h - rv))
    if not where and S <= 0 and False: pass
    print("  file 0x%X  %s" % (h, where))
print("  total:", len(hits))
print("\n=== DONE ===")
