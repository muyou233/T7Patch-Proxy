#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dump_region.py -- READ-ONLY: dump an arbitrary address window of a running
BlackOps3.exe as hex + ASCII (optionally filtering to interesting rows).

  python dump_region.py --addr 0x1093788000 --len 0x8000
"""
import argparse
import ctypes
import ctypes.wintypes as wt
import os
import re
import subprocess
import sys

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.ReadProcessMemory.restype = wt.BOOL
k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.CloseHandle.argtypes = [wt.HANDLE]
PROCESS_QUERY_INFORMATION, PROCESS_VM_READ = 0x0400, 0x0010


def find_pid():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq blackops3.exe",
                              "/FO", "CSV", "/NH"], capture_output=True, text=True,
                             timeout=30).stdout
    except Exception:
        return None
    m = re.search(r'"blackops3\.exe","(\d+)"', out, re.I)
    return int(m.group(1)) if m else None


def ascii_of(b):
    return "".join(chr(c) if 0x20 <= c < 0x7F else "." for c in b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--addr", required=True, type=lambda x: int(x, 0))
    ap.add_argument("--len", type=lambda x: int(x, 0), default=0x8000)
    ap.add_argument("--pid", type=int)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "dump_region.txt"))
    a = ap.parse_args()

    pid = a.pid or find_pid()
    if not pid:
        print("BlackOps3.exe not running")
        return 2
    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        print("OpenProcess failed err=%d" % ctypes.get_last_error())
        return 3

    buf = ctypes.create_string_buffer(a.len)
    got = ctypes.c_size_t()
    lines = []
    try:
        ok = k32.ReadProcessMemory(h, ctypes.c_void_p(a.addr), buf, a.len, ctypes.byref(got))
        lines.append("pid=%d addr=0x%X len=0x%X read=%d ok=%s" % (pid, a.addr, a.len, got.value, bool(ok)))
        lines.append("")
        if got.value:
            blob = buf.raw[:got.value]
            for k in range(0, len(blob), 16):
                row = blob[k:k + 16]
                lines.append("  %08X  %-47s |%s|" % (a.addr + k, row.hex(" "), ascii_of(row)))
    finally:
        k32.CloseHandle(h)
    open(a.out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
