#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
roster_live.py -- read-only locator for the in-game lobby roster.

Given the gamertags visible on the BO3 lobby screen, scan the game's committed
readable memory (ASCII + UTF-16LE) and report where each tag lives, what
surrounds it, and which regions hold several tags at once (= the roster table).

Pure ReadProcessMemory. Nothing is written into the target process.
"""
import ctypes, ctypes.wintypes as w, struct, re, subprocess, time, argparse, io, sys
from collections import defaultdict

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.VirtualQueryEx.argtypes = [w.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
k32.ReadProcessMemory.restype = ctypes.c_int
k32.ReadProcessMemory.argtypes = [w.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.OpenProcess.restype = ctypes.c_void_p
k32.OpenProcess.argtypes = [w.DWORD, ctypes.c_int, w.DWORD]

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ           = 0x0010
MEM_COMMIT    = 0x1000
PAGE_NOACCESS = 0x01
PAGE_GUARD    = 0x100

STEAM_HI = 0x01100001          # SteamID64 individual accounts: 0x01100001xxxxxxxx

TYPE_NAME = {0x20000: "PRIVATE", 0x40000: "MAPPED", 0x1000000: "IMAGE", 0: "-"}


class MBI64(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_ulonglong),
                ("AllocationBase", ctypes.c_ulonglong),
                ("AllocationProtect", w.DWORD),
                ("_p1", w.DWORD),
                ("RegionSize", ctypes.c_ulonglong),
                ("State", w.DWORD),
                ("Protect", w.DWORD),
                ("Type", w.DWORD),
                ("_p2", w.DWORD)]


def find_pid():
    o = subprocess.run(["tasklist", "/FI", "IMAGENAME eq blackops3.exe", "/FO", "CSV", "/NH"],
                       capture_output=True, text=True).stdout
    m = re.search(r'"blackops3\.exe","(\d+)"', o, re.I)
    if m:
        return int(m.group(1))
    o2 = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True).stdout
    m = re.search(r'"[^"]*blackops3[^"]*","(\d+)"', o2, re.I)
    return int(m.group(1)) if m else None


def iter_regions(h):
    addr = 0
    mbi = MBI64()
    while True:
        got = k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
        if not got:
            break
        base, size = mbi.BaseAddress, mbi.RegionSize
        if size == 0:
            break
        good = (mbi.State == MEM_COMMIT) and not (mbi.Protect & PAGE_NOACCESS) \
               and not (mbi.Protect & PAGE_GUARD)
        yield base, size, mbi.Protect, mbi.Type, good
        addr = base + size
        if addr > 0x7FFFFFFFFFFF:
            break


def read_at(h, addr, n):
    if n <= 0:
        return b""
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t(0)
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr),
                               ctypes.cast(buf, ctypes.c_void_p), n, ctypes.byref(got))
    if not ok:
        return b""
    return buf.raw[:got.value]


def hexdump(data, base):
    lines = []
    for i in range(0, len(data) - (len(data) % 16), 16):
        chunk = data[i:i + 16]
        hx = " ".join("%02X" % b for b in chunk)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append("%012X  %-47s  %s" % (base + i, hx, asc))
    return lines


def xuids_in(data, base):
    found = []
    for i in range(0, max(0, len(data) - 7)):
        v = struct.unpack_from("<Q", data, i)[0]
        if (v >> 32) == STEAM_HI:
            found.append((base + i, v))
    return found


def emit(out, path):
    txt = "\n".join(out) + "\n"
    if path:
        io.open(path, "w", encoding="utf-8").write(txt)
    sys.stdout.write(txt)
    sys.stdout.flush()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", default="MartinBryant96,PARASITE,PandaTurtleFish,YoshiWiseguy,"
                                       "AutisticNek9,TheTumbleweedKid,izanagi,THWolfy33,kingofcheese555")
    ap.add_argument("--max-mb", type=int, default=9000)
    ap.add_argument("--ctx", type=lambda s: int(s, 0), default=0x100)
    ap.add_argument("--dumps", type=int, default=50)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    targets = [t.strip() for t in a.names.split(",") if t.strip()]
    out = []

    def w(s=""):
        out.append(s)

    pid = find_pid()
    w("=== roster_live @ %s ===" % time.strftime("%H:%M:%S"))
    w("pid = %s" % pid)
    if not pid:
        w("blackops3.exe not running")
        emit(out, a.out)
        return

    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, 0, pid)
    if not h:
        w("OpenProcess failed err=%d" % ctypes.get_last_error())
        emit(out, a.out)
        return

    needles = []
    for t in targets:
        needles.append((t, "ascii", t.encode("ascii")))
        needles.append((t, "utf16", t.encode("utf-16-le")))

    hits = []
    maxbytes = a.max_mb * 1024 * 1024
    total = 0
    t0 = time.time()
    CHUNK = 8 * 1024 * 1024
    for base, size, prot, typ, good in iter_regions(h):
        if not good:
            continue
        if total >= maxbytes:
            break
        off = 0
        while off < size:
            n = min(CHUNK, size - off)
            data = read_at(h, base + off, n)
            total += len(data)
            if data:
                for t, enc, nd in needles:
                    s = 0
                    while True:
                        i = data.find(nd, s)
                        if i < 0:
                            break
                        hits.append((t, base + off + i, enc, base, typ, prot))
                        s = i + 1
            if off + n >= size:
                break
            off += n - 64
            if total >= maxbytes:
                break
    w("scanned %.1f MB in %.1fs   raw hits = %d" % (total / 1048576.0, time.time() - t0, len(hits)))

    seen = set()
    uniq = []
    for t, addr, enc, rbase, typ, prot in hits:
        k = (t, addr, enc)
        if k in seen:
            continue
        seen.add(k)
        uniq.append((t, addr, enc, rbase, typ, prot))
    w("unique hits = %d" % len(uniq))

    clus = defaultdict(set)
    for t, addr, enc, rbase, typ, prot in uniq:
        clus[rbase].add(t)
    w("")
    w("=== regions holding >=2 distinct tags ===")
    found_any = False
    for rbase, names in sorted(clus.items(), key=lambda kv: -len(kv[1])):
        if len(names) >= 2:
            found_any = True
            w("  region 0x%012X : %d tags -> %s" % (rbase, len(names), ", ".join(sorted(names))))
    if not found_any:
        w("  (none)")

    w("")
    w("=== per-tag hit summary ===")
    per = defaultdict(list)
    for t, addr, enc, rbase, typ, prot in uniq:
        per[t].append((addr, enc))
    for t in targets:
        lst = per.get(t, [])
        sample = ", ".join("0x%X/%s" % (x[0], x[1]) for x in lst[:4]) if lst else "-"
        w("  %-22s %3d hits   %s" % (t, len(lst), sample))

    w("")
    w("=== context around interesting hits (xuid nearby or 05 00 0A prefix) ===")
    shown = 0
    for t, addr, enc, rbase, typ, prot in sorted(uniq, key=lambda x: x[1]):
        if shown >= a.dumps:
            break
        start = max(0, addr - a.ctx)
        blob = read_at(h, start, a.ctx * 2)
        if not blob:
            continue
        near = [x for x in xuids_in(blob, start) if abs(x[0] - addr) <= a.ctx]
        pre = read_at(h, addr - 4, 4)
        interesting = bool(near) or (enc == "ascii" and pre[:3] == b"\x05\x00\x0a")
        if not interesting:
            continue
        shown += 1
        w("")
        w("--- %-20s @ 0x%012X  enc=%s  region=0x%012X  type=%s  protect=0x%X  pre=%s"
          % (t, addr, enc, rbase, TYPE_NAME.get(typ, str(typ)), prot, pre.hex()))
        for line in hexdump(blob, start):
            w("    " + line)
        if near:
            w("    XUID nearby: " + ", ".join("0x%X=0x%016X" % (x[0], x[1]) for x in near))
    w("")
    w("=== DONE ===")
    emit(out, a.out)


if __name__ == "__main__":
    main()
