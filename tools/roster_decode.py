#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
roster_decode.py -- walk the fixed-stride (0x338) player-record array that holds
the lobby roster, and print tag + XUID for each slot.

Record layout observed in BO3 (PID live, 2026-09-15 16:2x):
    +0x00 : gamertag, NUL-terminated ASCII
    +0x5C : XUID, u64 LE (SteamID64, high dword == 0x01100001)
    stride: 0x338 (824 bytes); the rest of the record is zero for remote peers.

Read-only. Nothing is written into the target.
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
STEAM_HI = 0x01100001


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=lambda s: int(s, 0), required=True, help="address of a known record")
    ap.add_argument("--stride", type=lambda s: int(s, 0), default=0x338)
    ap.add_argument("--count", type=int, default=16)
    ap.add_argument("--back", type=int, default=2, help="records to walk backwards")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    out = []

    def w(s=""):
        out.append(s)

    pid = find_pid()
    w("=== roster_decode @ %s ===" % time.strftime("%H:%M:%S"))
    w("pid = %s" % pid)
    if not pid:
        w("blackops3.exe not running")
        finish(out, a.out)
        return
    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, 0, pid)
    if not h:
        w("OpenProcess failed")
        finish(out, a.out)
        return

    mbi = MBI64()
    k32.VirtualQueryEx(h, ctypes.c_void_p(a.base), ctypes.byref(mbi), ctypes.sizeof(mbi))
    w("region containing 0x%X : base=0x%X size=0x%X protect=0x%X type=0x%X"
      % (a.base, mbi.BaseAddress, mbi.RegionSize, mbi.Protect, mbi.Type))
    w("stride = 0x%X   walking %d records, %d back from base" % (a.stride, a.count, a.back))
    w("")

    start = a.base - a.stride * a.back
    w("%-4s %-16s %-24s %-20s %s" % ("idx", "address", "gamertag", "xuid", "notes"))
    for i in range(a.count):
        rec = start + i * a.stride
        blob = read_at(h, rec, 0x80)
        if len(blob) < 0x64:
            w("%-4d 0x%012X  <unreadable>" % (i, rec))
            continue
        raw = blob[:0x30].split(b"\x00")[0]
        ok = bool(raw) and all(32 <= b < 127 for b in raw)
        tag = raw.decode("latin-1") if ok else ""
        x = struct.unpack_from("<Q", blob, 0x5C)[0]
        note = []
        if not ok:
            note.append("no-tag")
        if (x >> 32) == STEAM_HI:
            note.append("steamid")
        else:
            note.append("xuid?=0x%016X" % x)
        w("%-4d 0x%012X  %-24s 0x%016X     %s" % (i, rec, (tag or "<none>"), x, ", ".join(note)))

    w("")
    w("--- raw 0x90 bytes of the record at --base ---")
    blob = read_at(h, a.base, 0x90)
    for o in range(0, len(blob) - (len(blob) % 16), 16):
        ch = blob[o:o + 16]
        w("    %012X  %-47s  %s" % (a.base + o,
                                    " ".join("%02X" % b for b in ch),
                                    "".join(chr(b) if 32 <= b < 127 else "." for b in ch)))
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
