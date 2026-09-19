#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
find_str.py -- READ-ONLY: locate an ASCII or UTF-16 string inside a running
BlackOps3.exe and dump its neighbourhood, so we can see which table it belongs to.

  python find_str.py --s YoyoCurtis
  python find_str.py --s YoyoCurtis --utf16
  python find_str.py --s "nuketown" --max-mb 2000 --ctx 0x80
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import re
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
MEM_IMAGE = 0x1000000
READABLE = {0x02, 0x04, 0x08, 0x20, 0x40, 0x80}
MAX_USER_ADDR = 0x7FFFFFFEFFFF


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


def collect_regions(h, private_only):
    out, addr, mbi = [], 0, MBI()
    while addr < MAX_USER_ADDR:
        if not k32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base, size = mbi.BaseAddress, mbi.RegionSize
        if size == 0:
            break
        ok = (mbi.State == MEM_COMMIT and not (mbi.Protect & PAGE_GUARD)
              and mbi.Protect != PAGE_NOACCESS and (mbi.Protect & 0xFF) in READABLE)
        if ok and private_only:
            ok = (mbi.Type == MEM_PRIVATE)
        if ok:
            out.append((base, size))
        addr = base + size
    return out


def ascii_of(b):
    return "".join(chr(c) if 0x20 <= c < 0x7F else "." for c in b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--s", required=True)
    ap.add_argument("--utf16", action="store_true")
    ap.add_argument("--pid", type=int)
    ap.add_argument("--max-mb", type=int, default=9000)
    ap.add_argument("--ctx", type=lambda x: int(x, 0), default=0x100)
    ap.add_argument("--all-regions", action="store_true", help="include mapped MEM_IMAGE too")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "find_str.txt"))
    a = ap.parse_args()

    pid = a.pid or find_pid()
    if not pid:
        print("BlackOps3.exe not running")
        return 2

    pat = a.s.encode("utf-16-le") if a.utf16 else a.s.encode("ascii")
    lines = []
    def w(s=""):
        print(s)
        lines.append(s)

    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        w("OpenProcess failed err=%d" % ctypes.get_last_error())
        return 3

    hits = []
    t0 = time.time()
    try:
        regions = collect_regions(h, not a.all_regions)
        w("pid=%d  regions=%d  %.0f MB   pattern=%r%s"
          % (pid, len(regions), sum(s for _, s in regions) / 1048576.0, a.s,
             " (utf16)" if a.utf16 else ""))
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
                        i = raw.find(pat, s)
                        if i < 0:
                            break
                        hits.append(here + i)
                        s = i + 1
                off += n
        w("scanned %.0f MB in %.1fs   hits=%d" % (scanned / 1048576.0, time.time() - t0, len(hits)))
        for at in hits[:40]:
            lo = max(0, at - a.ctx)
            nb = ctypes.create_string_buffer(a.ctx + len(pat) + a.ctx)
            got = ctypes.c_size_t()
            if not k32.ReadProcessMemory(h, ctypes.c_void_p(lo), nb, len(nb), ctypes.byref(got)):
                nb, got = None, None
            w("")
            w("@0x%X  (string at +0x%X)" % (at, at - lo))
            if nb is None:
                w("  <unreadable>")
                continue
            blob = nb.raw[:got.value]
            for k in range(0, len(blob), 16):
                row = blob[k:k + 16]
                w("    +%03X  %-47s |%s|" % (k, row.hex(" "), ascii_of(row)))
    finally:
        k32.CloseHandle(h)

    open(a.out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
