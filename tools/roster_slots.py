#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
roster_slots.py -- dump the 12-slot player table at a fixed RVA inside blackops3.exe,
and follow the pointer field to see what it references (looking for an address).

Table: RVA 0x4C9EC90 (this build), stride 0xB0, 12 slots.
  +0x00 u64 XUID   +0x0C u32 level   +0x18 u32 slot   +0x20 u64 ptr
  +0x28 char name[32]                +0x48 char clantag[8]
Read-only.
"""
import ctypes, ctypes.wintypes as w, struct, re, subprocess, time, argparse, io, sys

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.ReadProcessMemory.restype = ctypes.c_int
k32.ReadProcessMemory.argtypes = [w.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.OpenProcess.restype = ctypes.c_void_p
k32.OpenProcess.argtypes = [w.DWORD, ctypes.c_int, w.DWORD]
k32.VirtualQueryEx.restype = ctypes.c_size_t
k32.VirtualQueryEx.argtypes = [w.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]

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


def module_bases():
    TH32CS = 0x08 | 0x10
    class ME32(ctypes.Structure):
        _fields_ = [("dwSize", w.DWORD), ("th32ModuleID", w.DWORD),
                    ("th32ProcessID", w.DWORD), ("GlblcntUsage", w.DWORD),
                    ("ProccntUsage", w.DWORD), ("modBaseAddr", ctypes.c_void_p),
                    ("modBaseSize", w.DWORD), ("hModule", w.HMODULE),
                    ("szModule", ctypes.c_char * 256), ("szExePath", ctypes.c_char * 260)]
    pid = find_pid()
    snap = k32.CreateToolhelp32Snapshot(TH32CS, pid)
    me = ME32(); me.dwSize = ctypes.sizeof(ME32)
    res = {}
    ok = k32.Module32First(snap, ctypes.byref(me))
    while ok:
        res[me.szModule.decode("latin-1").lower()] = me.modBaseAddr
        ok = k32.Module32Next(snap, ctypes.byref(me))
    k32.CloseHandle(snap)
    return res


def read_at(h, addr, n):
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t(0)
    if not k32.ReadProcessMemory(h, ctypes.c_void_p(addr), ctypes.cast(buf, ctypes.c_void_p),
                                 n, ctypes.byref(got)):
        return b""
    return buf.raw[:got.value]


def hexdump(data, base):
    L = []
    for i in range(0, len(data) - (len(data) % 16), 16):
        ch = data[i:i + 16]
        L.append("      %012X  %-47s  %s" % (base + i, " ".join("%02X" % b for b in ch),
                                             "".join(chr(b) if 32 <= b < 127 else "." for b in ch)))
    return L


def owner(addr, bases):
    best = None
    for n, b in bases.items():
        if b and addr >= b and (best is None or b > best[1]):
            best = (n, b)
    if best:
        return "%s+0x%X" % (best[0], addr - best[1])
    return "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rva", type=lambda s: int(s, 0), default=0x4C9EC90)
    ap.add_argument("--stride", type=lambda s: int(s, 0), default=0xB0)
    ap.add_argument("--slots", type=int, default=12)
    ap.add_argument("--follow", type=lambda s: int(s, 0), default=0x60)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    out = []

    def w(s=""):
        out.append(s)

    pid = find_pid()
    bases = module_bases()
    gb = bases.get("blackops3.exe")
    w("=== roster_slots @ %s ===" % time.strftime("%H:%M:%S"))
    w("pid=%s  blackops3.exe base=%s" % (pid, hex(gb) if gb else "?"))
    if not pid or not gb:
        w("no game"); finish(out, a.out); return
    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, 0, pid)

    table = gb + a.rva
    w("table @ %s (RVA 0x%X) stride 0x%X slots %d" % (hex(table), a.rva, a.stride, a.slots))
    w("")

    ptrs = []
    for s in range(a.slots):
        rec = table + s * a.stride
        blob = read_at(h, rec, a.stride)
        if len(blob) < 0x60:
            w("slot %-2d 0x%012X  <unreadable>" % (s, rec)); continue
        xuid = struct.unpack_from("<Q", blob, 0)[0]
        lvl = struct.unpack_from("<I", blob, 0x0C)[0]
        slotf = struct.unpack_from("<I", blob, 0x18)[0]
        ptr = struct.unpack_from("<Q", blob, 0x20)[0]
        nm = blob[0x28:0x48].split(b"\x00")[0]
        cl = blob[0x48:0x50].split(b"\x00")[0]
        empty = (xuid == 0 and not nm)
        w("slot %-2d 0x%012X  xuid=%-20s lvl=%-5d slotf=%-3d ptr=0x%012X  name=%-20s clan=%-6s %s"
          % (s, rec, str(xuid) if xuid else "-", lvl, slotf, ptr,
             nm.decode("latin-1"), cl.decode("latin-1"), "<empty>" if empty else ""))
        if not empty and ptr:
            ptrs.append((s, ptr))

    w("")
    w("--- following +0x20 pointers (0x%X bytes each) ---" % a.follow)
    for s, ptr in ptrs:
        data = read_at(h, ptr, a.follow)
        w("")
        w("slot %d -> ptr 0x%012X  (%s)" % (s, ptr, owner(ptr, bases)))
        if not data:
            w("      <unreadable>"); continue
        for line in hexdump(data, ptr):
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
