#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
region_probe.py -- inspect ONE memory region and look for given tags inside it.

Usage:
  region_probe.py --addr 0x7FF61EFCE000 --names a,b,c [--ctx 0x60] [--max-mb 512]

Prints the region's base/size/protect/type, then every occurrence of each tag
(ASCII and UTF-16LE) with a short hex/ascii context. Read-only.
"""
import ctypes, ctypes.wintypes as w, struct, re, subprocess, time, argparse, io, sys

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.VirtualQueryEx.argtypes = [w.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
k32.ReadProcessMemory.restype = ctypes.c_int
k32.ReadProcessMemory.argtypes = [w.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.OpenProcess.restype = ctypes.c_void_p
k32.OpenProcess.argtypes = [w.DWORD, ctypes.c_int, w.DWORD]

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
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
    return int(m.group(1)) if m else None


def read_at(h, addr, n):
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), ctypes.cast(buf, ctypes.c_void_p),
                                 n, ctypes.byref(got)):
        return b""
    return buf.raw[:got.value]


def hexdump(data, base, ctx):
    lines = []
    for i in range(0, len(data) - (len(data) % 16), 16):
        ch = data[i:i + 16]
        lines.append("      %012X  %-47s  %s" % (base + i,
                                                 " ".join("%02X" % b for b in ch),
                                                 "".join(chr(b) if 32 <= b < 127 else "." for b in ch)))
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--addr", type=lambda s: int(s, 0), required=True)
    ap.add_argument("--names", default="")
    ap.add_argument("--ctx", type=lambda s: int(s, 0), default=0x60)
    ap.add_argument("--max-mb", type=int, default=512)
    ap.add_argument("--dumps", type=int, default=8)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    names = [x.strip() for x in a.names.split(",") if x.strip()]
    out = []

    def w(s=""):
        out.append(s)

    pid = find_pid()
    if not pid:
        w("blackops3.exe not running"); finish(out, a.out); return
    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, 0, pid)

    mbi = MBI64()
    k32.VirtualQueryEx(h, ctypes.c_void_p(a.addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
    w("=== region_probe @ %s ===" % time.strftime("%H:%M:%S"))
    w("addr   0x%X" % a.addr)
    w("region base=0x%X size=0x%X (%d MB) protect=0x%X type=%s state=0x%X"
      % (mbi.BaseAddress, mbi.RegionSize, mbi.RegionSize // 1048576, mbi.Protect,
         TYPE_NAME.get(mbi.Type, str(mbi.Type)), mbi.State))
    if not names:
        finish(out, a.out); return

    needles = []
    for t in names:
        needles.append((t, "ascii", t.encode("ascii")))
        needles.append((t, "utf16", t.encode("utf-16-le")))

    hits = []
    total = 0
    cap = a.max_mb * 1048576
    CH = 8 * 1048576
    off = 0
    while off < mbi.RegionSize and total < cap:
        n = min(CH, mbi.RegionSize - off)
        data = read_at(h, mbi.BaseAddress + off, n)
        total += len(data)
        if data:
            for t, enc, nd in needles:
                s = 0
                while True:
                    i = data.find(nd, s)
                    if i < 0:
                        break
                    hits.append((t, mbi.BaseAddress + off + i, enc))
                    s = i + 1
        if off + n >= mbi.RegionSize:
            break
        off += n - 64
    w("scanned %.1f MB   hits = %d" % (total / 1048576.0, len(hits)))
    seen = set()
    for t, addr, enc in hits:
        k = (t, addr, enc)
        if k in seen:
            continue
        seen.add(k)
        w("  %-22s 0x%012X  %s" % (t, addr, enc))
    w("")
    w("--- context ---")
    shown = 0
    for t, addr, enc in sorted(set(hits), key=lambda x: x[1]):
        if shown >= a.dumps:
            break
        shown += 1
        start = max(mbi.BaseAddress, addr - a.ctx)
        blob = read_at(h, start, a.ctx * 2)
        w("")
        w("  %s @ 0x%012X (%s)" % (t, addr, enc))
        for line in hexdump(blob, start, a.ctx):
            w(line)
    w("")
    w("=== DONE ===")
    finish(out, a.out)


def finish(out, path):
    txt = "\n".join(out) + "\n"
    if path:
        io.open(path, "w", encoding="utf-8").write(txt)
    sys.stdout.write(txt)
    sys.stdout.flush()


if __name__ == "__main__":
    main()
