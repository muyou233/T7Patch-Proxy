#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
xuid_ctx.py -- READ-ONLY: dump the raw context around every Steam XUID found in a
running BlackOps3.exe, so we can learn the *real* player-record layout instead of
guessing it.

Every Steam XUID is 0x01100001_xxxxxxxx, whose little-endian byte form contains the
needle  01 00 10 01  at xuid+4.  We take every occurrence of that needle at ANY byte
alignment, treat the 8 bytes before it as the XUID, and dump 0x50 bytes of context
before / 0x90 after.  Nothing is written to the game.

  python xuid_ctx.py --max-mb 9000
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import re
import struct
import subprocess
import sys
import time

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.ReadProcessMemory.restype = wt.BOOL
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.VirtualQueryEx.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
k32.CloseHandle.argtypes = [wt.HANDLE]

PROCESS_QUERY_INFORMATION, PROCESS_VM_READ = 0x0400, 0x0010
MEM_COMMIT, MEM_PRIVATE, PAGE_GUARD, PAGE_NOACCESS = 0x1000, 0x20000, 0x100, 0x01
READABLE = {0x02, 0x04, 0x08, 0x20, 0x40, 0x80}
MAX_USER_ADDR = 0x7FFFFFFEFFFF
NEEDLE = b"\x01\x00\x10\x01"
XUID_MIN, XUID_MAX = 0x0110000100000000, 0x0110000200000000


class MBI(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_ulonglong),
                ("AllocationBase", ctypes.c_ulonglong),
                ("AllocationProtect", wt.DWORD), ("_p1", wt.DWORD),
                ("RegionSize", ctypes.c_ulonglong),
                ("State", wt.DWORD), ("Protect", wt.DWORD),
                ("Type", wt.DWORD), ("_p2", wt.DWORD)]


def find_pid():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq blackops3.exe",
                              "/FO", "CSV", "/NH"], capture_output=True, text=True,
                             timeout=30).stdout
    except Exception:
        return None
    m = re.search(r'"blackops3\.exe","(\d+)"', out, re.I)
    return int(m.group(1)) if m else None


def collect_regions(h):
    out, addr, mbi = [], 0, MBI()
    while addr < MAX_USER_ADDR:
        if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base, size = mbi.BaseAddress, mbi.RegionSize
        if size == 0:
            break
        if (mbi.State == MEM_COMMIT and mbi.Type == MEM_PRIVATE
                and not (mbi.Protect & PAGE_GUARD) and mbi.Protect != PAGE_NOACCESS
                and (mbi.Protect & 0xFF) in READABLE):
            out.append((base, size))
        addr = base + size
    return out


def ascii_of(b):
    return "".join(chr(c) if 0x20 <= c < 0x7F else "." for c in b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int)
    ap.add_argument("--max-mb", type=int, default=9000)
    ap.add_argument("--samples", type=int, default=2)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "xuid_ctx.txt"))
    a = ap.parse_args()

    pid = a.pid or find_pid()
    if not pid:
        print("BlackOps3.exe not running")
        return 2

    lines = []
    def w(s=""):
        print(s)
        lines.append(s)

    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        w("OpenProcess failed err=%d" % ctypes.get_last_error())
        return 3

    recs = {}          # xuid -> [(addr, ctx_hex)]
    total = 0
    t0 = time.time()
    try:
        regions = collect_regions(h)
        w("pid=%d  regions=%d  %.0f MB" % (pid, len(regions), sum(s for _, s in regions) / 1048576.0))
        chunk, scanned = (8 << 20), 0
        buf, nread = ctypes.create_string_buffer(chunk), ctypes.c_size_t()
        for base, size in regions:
            off = 0
            while off < size and scanned < (a.max_mb << 20):
                n = min(chunk, size - off)
                here = base + off
                if k32.ReadProcessMemory(h, ctypes.c_void_p(here), buf, n, ctypes.byref(nread)) and nread.value:
                    raw = buf.raw[:nread.value]
                    scanned += len(raw)
                    s = 0
                    while True:
                        i = raw.find(NEEDLE, s)
                        if i < 0:
                            break
                        s = i + 1
                        xa = i - 4
                        if xa < 0:
                            continue
                        xuid = struct.unpack("<Q", raw[xa:xa + 8])[0]
                        if not (XUID_MIN <= xuid < XUID_MAX):
                            continue
                        total += 1
                        lo = max(0, xa - 0x50)
                        hi = min(len(raw), xa + 8 + 0x90)
                        ctx = raw[lo:hi]
                        absaddr = here + xa
                        if xuid not in recs:
                            recs[xuid] = []
                        if len(recs[xuid]) < a.samples and len(recs) <= 400:
                            recs[xuid].append((absaddr, xa - lo, ctx))
                off += n
        w("scanned %.0f MB in %.1fs   needle hits=%d   distinct XUID=%d"
          % (scanned / 1048576.0, time.time() - t0, total, len(recs)))
        w("")
        for xuid in sorted(recs):
            w("XUID %d  (0x%016X)   occurrences shown: %d" % (xuid, xuid, len(recs[xuid])))
            for absaddr, rel, ctx in recs[xuid]:
                w("  @0x%X   (xuid at offset %d in the dump below)" % (absaddr, rel))
                for k in range(0, len(ctx), 16):
                    row = ctx[k:k + 16]
                    w("    +%03X  %-47s |%s|" % (k, row.hex(" "), ascii_of(row)))
            w("")
    finally:
        k32.CloseHandle(h)

    open(a.out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
