#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
netadr_scan.py -- READ-ONLY hunt for netadr_t records in a running BlackOps3.exe.

Layout (src/structs.h):
    struct netadr_t { u8 ipv4[4]; u16 port; u16 pad(0); i32 type; netsrc_t localNetID; }  (16 B)

We scan every committed PRIVATE readable region at 4-byte alignment and keep only
records whose ipv4 is a *public* address (LAN / link-local / multicast / reserved are
bucketed separately), port in [1024,65535], pad == 0, type in {-1..4}, localNetID in
{-1..5}.  Nothing is written to the game and no engine function is called.

  python netadr_scan.py                  # whole process
  python netadr_scan.py --max-mb 2000
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

# ASCII fallback: only accept ip:port strings whose first octet looks public.
RE_ASCII = re.compile(rb"(?<![0-9.])((?:[1-9]|[1-9][0-9]|1[0-9][0-9]|2[0-1][0-9]|22[0-3])"
                      rb"(?:\.\d{1,3}){3}):(\d{2,5})(?![0-9])")


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


def classify(ip):
    o = [int(x) for x in ip.split(".")]
    if o[0] in (10, 127, 0) or (o[0] == 172 and 16 <= o[1] <= 31) or (o[0] == 192 and o[1] == 168):
        return "lan"
    if o[0] == 169 and o[1] == 254:
        return "linklocal"
    if o[0] >= 224:
        return "reserved"
    return "public"


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int)
    ap.add_argument("--max-mb", type=int, default=9000)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "netadr_scan.txt"))
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

    bin_hits, ascii_hits = {}, {}
    ptr_like = {}
    t0 = time.time()
    try:
        regions = collect_regions(h)
        total = sum(s for _, s in regions)
        w("pid=%d  regions=%d  %.0f MB" % (pid, len(regions), total / 1048576.0))
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
                    # --- binary netadr_t, 4-byte aligned ---
                    end = len(raw) - 16
                    i = 0
                    while i < end:
                        b = raw[i:i + 16]
                        if b[6] == 0 and b[7] == 0:
                            typ = struct.unpack("<i", b[8:12])[0]
                            if typ in (-1, 0, 1, 2, 3, 4):
                                lnid = struct.unpack("<i", b[12:16])[0]
                                if lnid in (-1, 0, 1, 2, 3, 4, 5):
                                    ip = "%d.%d.%d.%d" % (b[0], b[1], b[2], b[3])
                                    cls = classify(ip)
                                    if cls != "reserved" and b[3] != 0 and b[0] != 0:
                                        be = struct.unpack(">H", b[4:6])[0]
                                        le = struct.unpack("<H", b[4:6])[0]
                                        port = be if 1024 <= be <= 65535 else (le if 1024 <= le <= 65535 else 0)
                                        if port:
                                            k = ("%s:%d" % (ip, port), cls, typ)
                                            bin_hits[k] = bin_hits.get(k, 0) + 1
                        i += 4
                    # --- ASCII ip:port (public-looking only) ---
                    for m in RE_ASCII.finditer(raw):
                        ip, pt = m.group(1).decode(), int(m.group(2))
                        if 1024 <= pt <= 65535:
                            cls = classify(ip)
                            if cls != "reserved":
                                k = ("%s:%d" % (ip, pt), cls)
                                ascii_hits[k] = ascii_hits.get(k, 0) + 1
                off += n
        w("scanned %.0f MB in %.1fs" % (scanned / 1048576.0, time.time() - t0))

        for label, d, extra in (("binary netadr_t", bin_hits, True), ("ascii ip:port", ascii_hits, False)):
            pub = {k: v for k, v in d.items() if k[1] == "public"}
            lan = {k: v for k, v in d.items() if k[1] == "lan"}
            w("")
            w("=== %s ===  distinct=%d  public=%d  lan=%d" % (label, len(d), len(pub), len(lan)))
            for k, c in sorted(pub.items(), key=lambda kv: -kv[1])[:30]:
                w("  %-24s x%-6d %s" % (k[0], c, ("type=%d" % k[2]) if extra else ""))
            for k, c in sorted(lan.items(), key=lambda kv: -kv[1])[:10]:
                w("  %-24s x%-6d LAN" % (k[0], c))
    finally:
        k32.CloseHandle(h)

    open(a.out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
