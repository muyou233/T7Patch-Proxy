# -*- coding: utf-8 -*-
# Consolidated minidump forensics: header times, process uptime, exception, module containment,
# memory ranges, faulting-thread context + walkable frames.
import struct, sys, datetime, os

DMP = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\blackops3.exe.BEYQBBUILD132.CL#13892626.1789445311.dmp"

def u(f, fmt, off):
    f.seek(off)
    n = struct.calcsize(fmt)
    b = f.read(n)
    v = struct.unpack(fmt, b)
    return v[0] if len(v) == 1 else v

def ts(v):
    try:
        return datetime.datetime.fromtimestamp(v).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "invalid"

def rstr(f, rva):
    try:
        if rva <= 0 or rva >= size - 4:
            return "<bad name rva 0x%X>" % rva
        f.seek(rva)
        n = struct.unpack("<I", f.read(4))[0]
        if n <= 0 or n > 1024 or rva + 4 + n > size:
            return "<suspect size %d @0x%X>" % (n, rva)
        f.seek(rva + 4)
        raw = f.read(n)
        if n % 2 == 0:
            try:
                return raw.decode("utf-16-le").rstrip("\x00")
            except Exception:
                pass
        return raw.decode("latin-1").rstrip("\x00")
    except Exception as ex:
        return "<err %s>" % ex

f = open(DMP, "rb")
size = os.path.getsize(DMP)
print("=== FILE ===")
print("path :", DMP)
print("bytes:", size)

sig = u(f, "<I", 0)
print("signature:", hex(sig), "OK" if sig == 0x504D444D else "BAD")
ver, nstreams, dirrva, checksum, hts, flags = (
    u(f, "<I", 4), u(f, "<I", 8), u(f, "<I", 12), u(f, "<I", 16), u(f, "<I", 20), u(f, "<Q", 24))
print("NumberOfStreams:", nstreams, " StreamDirRva:", hex(dirrva))
print("Header TimeDateStamp:", hts, ts(hts))
print("Flags:", hex(flags))

STREAMS = {3: "ThreadList", 4: "ModuleList", 5: "MemoryList", 6: "Exception", 7: "SystemInfo",
           8: "ThreadExList", 9: "Memory64List", 12: "HandleData", 14: "UnloadedModuleList",
           15: "MiscInfo", 16: "MemoryInfoList", 17: "ThreadInfoList", 22: "ProcessVmCounters",
           24: "ThreadNames", 25: "ceStreamNull"}
dirs = []
print("\n=== STREAM DIRECTORY ===")
for i in range(nstreams):
    off = dirrva + i * 12
    st, dsz, rva = u(f, "<III", off)
    dirs.append((st, dsz, rva))
    print("  %2d type=%3d %-20s size=%8d rva=%s" % (i, st, STREAMS.get(st, "?"), dsz, hex(rva)))

# --- MiscInfo: process id + create time -> uptime
# --- ModuleList
mods = []
for st, dsz, rva in dirs:
    if st == 4:
        n = u(f, "<I", rva)
        for k in range(n):
            mo = rva + 4 + k * 108
            base = u(f, "<Q", mo)
            isize = u(f, "<I", mo + 8)
            tds = u(f, "<I", mo + 12)
            namerva = u(f, "<I", mo + 16)
            mods.append((base, isize, tds, rstr(f, namerva)))
print("\n=== MODULES (%d) ===" % len(mods))
for base, isize, tds, name in sorted(mods):
    print("  %016X - %016X  %10d  %s" % (base, base + isize, isize, name))

def owner(addr):
    for base, isize, tds, name in mods:
        if base <= addr < base + isize:
            return "%s+0x%X" % (os.path.basename(name), addr - base)
    return "<not in any module>"

# --- MiscInfo: process id, create time, cpu times
for st, dsz, rva in dirs:
    if st == 15:
        soinfo, mflags, pid, pcreate, puser, pkern = u(f, "<IIIIII", rva)
        print("\n=== MISC INFO ===")
        print("SizeOfInfo        :", soinfo, "(stream size %d)" % dsz)
        print("Flags1            : %08X" % mflags)
        print("ProcessId         :", pid)
        print("ProcessCreateTime : %d  %s" % (pcreate, ts(pcreate)))
        print("ProcessUserTime   :", puser, " ProcessKernelTime:", pkern)
        print(">>> uptime at dump (dump_ts - create_ts):", hts - pcreate, "seconds")
        if dsz >= 24 + 20:
            extra = u(f, "<IIIII", rva + 24)
            print("MISC_INFO_2 proc mhz (max/cur/limit):", extra[0], extra[1], extra[2])

# --- Exception stream
exc = None
for st, dsz, rva in dirs:
    if st == 6:
        tid = u(f, "<I", rva)
        code, eflags = u(f, "<II", rva + 8)
        rec, addr = u(f, "<QQ", rva + 16)
        nparams = u(f, "<I", rva + 32)
        info = [u(f, "<Q", rva + 40 + j * 8) for j in range(15)]
        ctxds, ctxrva = u(f, "<II", rva + 160)
        exc = dict(tid=tid, code=code, eflags=eflags, rec=rec, addr=addr,
                   nparams=nparams, info=info, ctxds=ctxds, ctxrva=ctxrva)
print("\n=== EXCEPTION STREAM ===")
print("ThreadId        :", exc["tid"])
print("ExceptionCode   : %08X  %s" % (exc["code"], {0xC0000005: "ACCESS_VIOLATION",
                                                   0xC000001D: "ILLEGAL_INSTRUCTION",
                                                   0xC0000006: "IN_PAGE_ERROR",
                                                   0xC0000096: "PRIV_INSTRUCTION",
                                                   0xC0000409: "STACK_BUFFER_OVERRUN"}.get(exc["code"], "?")))
print("ExceptionFlags  :", hex(exc["eflags"]))
print("ExceptionRecord : %016X" % exc["rec"])
print("ExceptionAddress: %016X  -> %s" % (exc["addr"], owner(exc["addr"])))
print("NumberParameters:", exc["nparams"])
KIND = {0: "READ", 1: "WRITE", 8: "EXECUTE", 9: "DEP"}
for j in range(exc["nparams"]):
    v = exc["info"][j]
    extra = ""
    if j == 0:
        extra = KIND.get(v, "")
    if j == 1:
        extra = owner(v)
    print("  info[%d] = %016X  %s" % (j, v, extra))

# --- Thread context of faulting thread
def ctx(off, name, mask):
    return u(f, "<Q", off)

print("\n=== FAULTING THREAD CONTEXT ===")
cr = exc["ctxrva"]
CF = u(f, "<I", cr + 0x30)
print("ContextFlags: %08X  (ctxsize=%d)" % (CF, exc["ctxds"]))
regs = {"Rax": 0x78, "Rcx": 0x80, "Rdx": 0x88, "Rbx": 0x90, "Rsp": 0x98, "Rbp": 0xA0,
        "Rsi": 0xA8, "Rdi": 0xB0, "R8": 0xB8, "R9": 0xC0, "R10": 0xC8, "R11": 0xD0,
        "R12": 0xD8, "R13": 0xE0, "R14": 0xE8, "R15": 0xF0, "Rip": 0xF8}
rv = {}
for k, o in regs.items():
    rv[k] = u(f, "<Q", cr + o)
    print("  %-4s = %016X  %s" % (k, rv[k], owner(rv[k])))

# --- memory ranges
ranges = []
for st, dsz, rva in dirs:
    if st == 9:
        n = u(f, "<Q", rva)
        brva = u(f, "<Q", rva + 8)
        cur = brva
        for k in range(n):
            start, dsz2 = u(f, "<QQ", rva + 16 + k * 16)
            ranges.append((start, start + dsz2, cur))
            cur += dsz2
        print("\n=== Memory64List: %d ranges ===" % n)
    elif st == 5:
        n = u(f, "<I", rva)
        for k in range(n):
            start, dsize, r = u(f, "<QII", rva + 4 + k * 16)
            ranges.append((start, start + dsize, r))
        print("\n=== MemoryList: %d ranges ===" % n)

rs = sorted(ranges)
print("captured total bytes:", sum(e - s for s, e, _ in rs))
def memfind(addr):
    for s, e, r in rs:
        if s <= addr < e:
            return (s, e, r)
    return None
def rdmem(addr, n):
    m = memfind(addr)
    if not m:
        return None
    s, e, r = m
    f.seek(r + (addr - s))
    return f.read(min(n, e - addr))

print("\n=== KEY ADDRESS MAPPING ===")
for nm, a in (("ExceptionAddress", exc["addr"]), ("RIP", rv["Rip"]), ("Rsp", rv["Rsp"])):
    m = memfind(a)
    print("  %-16s %016X  %s" % (nm, a, ("captured[%016X-%016X]" % m[:2]) if m else "<NOT CAPTURED / unmapped>"))

# --- unwind: walk stack pointer-wise looking for return addresses
print("\n=== STACK SCAN (fault thread, looking for code pointers) ===")
stack_top = rv["Rsp"]
base_stack = u(f, "<Q", 0)  # placeholder
# get stack range for this thread
thr_stack = None
for st, dsz, rva in dirs:
    if st == 3:
        n = u(f, "<I", rva)
        for k in range(n):
            to = rva + 4 + k * 48
            tid = u(f, "<I", to)
            stk_start, stk_dsz, stk_rva = u(f, "<QII", to + 16)
            if tid == exc["tid"]:
                thr_stack = (stk_start, stk_start + stk_dsz, stk_rva)
        print("ThreadList count:", n)
print("fault thread captured stack:", ("%016X - %016X (%d bytes)" % (thr_stack[0], thr_stack[1], thr_stack[2] - thr_stack[0])) if thr_stack else "n/a")

if thr_stack:
    s, e, r = thr_stack
    off = max(rv["Rsp"] - s, 0)
    hits = []
    for p in range(off, e - s, 8):
        f.seek(r + p)
        v = struct.unpack("<Q", f.read(8))[0]
        if 0x00007FF000000000 <= v < 0x7FFFFFFF00000000:
            o = owner(v)
            if o != "<not in any module>":
                hits.append((s + p, v, o))
    print("candidate code/data pointers in stack (module-owned), second pass seq:")
    seen = set()
    for a, v, o in hits:
        key = (v, o)
        print("   [%016X] %016X  %s" % (a, v, o))

print("\n=== NEAREST MODULE BELOW fault address ===")
fa = exc["info"][1] if exc["nparams"] > 1 else 0
below = [m for m in mods if m[0] <= fa]
below.sort(key=lambda m: m[0])
if below:
    b = below[-1]
    print("  %016X is %s + 0x%X  (module size 0x%X, threads_ts=%s)" %
          (fa, os.path.basename(b[3]), fa - b[0], b[1], ts(b[2])))
print("  inside a module? ->", owner(fa))
print("  inside a captured memory range? ->", memfind(fa) is not None)

print("\n=== BYTES AT RIP (%016X) ===" % rv["Rip"])
bb = rdmem(rv["Rip"] - 16, 48)
if bb:
    for i in range(0, len(bb), 16):
        chunk = bb[i:i + 16]
        print("  %016X  %s  |%s|" % (rv["Rip"] - 16 + i,
                                    " ".join("%02X" % c for c in chunk),
                                    "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)))
else:
    print("  <not captured>")

print("\n=== QWORD SEARCH for fault address in whole dump ===")
target = struct.pack("<Q", fa)
f.seek(0)
blob = f.read()
pos, n = 0, 0
while True:
    i = blob.find(target, pos)
    if i < 0:
        break
    n += 1
    if n <= 10:
        print("  hit at file offset 0x%X" % i)
    pos = i + 1
print("  total hits:", n)

f.close()
print("\n=== DONE ===")
