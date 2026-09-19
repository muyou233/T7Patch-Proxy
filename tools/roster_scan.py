#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
roster_scan.py -- READ-ONLY: enumerate player-name records inside a running
BlackOps3.exe.

The game serialises lobby state as  05 00 0A <name> 00  ("0A" = string tag),
and a player XUID rides at xuid+4 == 01 00 10 01.  We scan for those name records
and, for each, look for a XUID within +-0x40 so we can pair name <-> xuid.

Nothing is written to the game.

  python roster_scan.py --max-mb 9000
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
NAME_TAG = b"\x05\x00\x0a"
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


def find_xuid_near(raw, off, window=0x40):
    """Look for a XUID inside raw[off-window : off+window]."""
    lo = max(0, off - window)
    hi = min(len(raw), off + window)
    s = lo
    best = None
    while True:
        i = raw.find(NEEDLE, s, hi)
        if i < 0:
            break
        s = i + 1
        j = i - 4
        if j < lo:
            continue
        v = struct.unpack("<Q", raw[j:j + 8])[0]
        if XUID_MIN <= v < XUID_MAX:
            best = v
            break
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int)
    ap.add_argument("--max-mb", type=int, default=9000)
    ap.add_argument("--window", type=lambda x: int(x, 0), default=0x40)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "roster_scan.txt"))
    a = ap.parse_args()

    pid = a.pid or find_pid()
    if not pid:
        print("BlackOps3.exe not running")
        return 2
    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        print("OpenProcess failed err=%d" % ctypes.get_last_error())
        return 3

    lines = []
    def w(s=""):
        print(s)
        lines.append(s)

    found = {}      # (name, xuid) -> [addr,...]
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
                        i = raw.find(NAME_TAG, s)
                        if i < 0:
                            break
                        s = i + 1
                        j = i + 3
                        k = raw.find(b"\x00", j, j + 40)
                        if k < 0:
                            continue
                        seg = raw[j:k]
                        if not (2 <= len(seg) <= 32):
                            continue
                        if not all(0x20 <= c < 0x7F for c in seg):
                            continue
                        name = seg.decode("ascii")
                        xuid = find_xuid_near(raw, i, a.window)
                        key = (name, xuid)
                        found.setdefault(key, []).append(here + i)
                off += n
        w("scanned %.0f MB in %.1fs   distinct name-records=%d" % (scanned / 1048576.0, time.time() - t0, len(found)))
        w("")
        for (name, xuid) in sorted(found, key=lambda k: (-len(found[k]), k[0])):
            addrs = found[(name, xuid)]
            w("  %-32s xuid=%-20s x%-4d  first@0x%X"
              % (name, str(xuid) if xuid else "<none>", len(addrs), addrs[0]))
    finally:
        k32.CloseHandle(h)

    open(a.out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
