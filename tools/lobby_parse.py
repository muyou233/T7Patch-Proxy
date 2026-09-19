#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lobby_parse.py -- READ-ONLY: locate the game's serialized lobby-state buffer in a
running BlackOps3.exe and print, in address order, the printable strings and the
Steam XUIDs it contains.

We anchor on the literal lobby-state names that the client itself writes into that
buffer ("StatePrivate", "StateGame", "StateGamePublic", ...) and then tokenize a
window around each hit:

  * XUID          : 8 bytes matching  ?? ?? ?? ?? 01 00 10 01   (0x01100001_xxxxxxxx)
  * string        : <len:1> <len printable bytes> <NUL>

Nothing is written to the game; no engine function is called.

  python lobby_parse.py
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
ANCHORS = [b"StatePrivate", b"StateGamePublic", b"StateGameCustom",
           b"StateGame\0", b"StateTheater"]


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


def tokenize(blob, base):
    """Yield (absaddr, kind, text) in address order."""
    out = []
    i, n = 0, len(blob)
    while i < n:
        # XUID (any alignment)
        if i + 8 <= n and blob[i + 4:i + 8] == NEEDLE:
            v = struct.unpack("<Q", blob[i:i + 8])[0]
            if XUID_MIN <= v < XUID_MAX:
                out.append((base + i, "xuid", str(v)))
                i += 8
                continue
        # length-prefixed string: <len><printable...><NUL>
        L = blob[i]
        if 2 <= L <= 40 and i + 1 + L < n and blob[i + 1 + L] == 0:
            seg = blob[i + 1:i + 1 + L]
            if all(0x20 <= c < 0x7F for c in seg):
                out.append((base + i, "str", seg.decode("ascii")))
                i += 1 + L + 1
                continue
        i += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int)
    ap.add_argument("--max-mb", type=int, default=9000)
    ap.add_argument("--pad-before", type=lambda x: int(x, 0), default=0x300)
    ap.add_argument("--pad-after", type=lambda x: int(x, 0), default=0x700)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "lobby_parse.txt"))
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

    anchors = []
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
                    for pat in ANCHORS:
                        s = 0
                        while True:
                            i = raw.find(pat, s)
                            if i < 0:
                                break
                            anchors.append((here + i, pat.decode("ascii", "replace")))
                            s = i + 1
                off += n
        w("scanned %.0f MB in %.1fs   anchor hits=%d" % (scanned / 1048576.0, time.time() - t0, len(anchors)))

        seen = set()
        for at, name in anchors[:60]:
            lo = max(0, at - a.pad_before)
            want = (at - lo) + a.pad_after
            nb = ctypes.create_string_buffer(want)
            got = ctypes.c_size_t()
            if not k32.ReadProcessMemory(h, ctypes.c_void_p(lo), nb, want, ctypes.byref(got)):
                continue
            blob = nb.raw[:got.value]
            toks = tokenize(blob, lo)
            key = name + ":" + ",".join(t[2] for t in toks[:6])
            if key in seen:
                continue
            seen.add(key)
            w("")
            w("=== anchor %r @0x%X ===" % (name, at))
            for addr, kind, text in toks:
                w("  0x%X  %-4s  %s" % (addr, kind, text))
    finally:
        k32.CloseHandle(h)

    open(a.out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
