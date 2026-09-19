#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
players_extract.py -- enumerate the BO3 "player info" pool in the game's data.

Record layout (offsets relative to the XUID field):
    +0x00  u64  XUID          (high dword == 0x01100001 = SteamID64 individual)
    +0x08  u32  0
    +0x0C  u32  level         (matches the number shown next to the name in-lobby)
    +0x18  u32  slot / index
    +0x20  u64  pointer       (into another game structure)
    +0x28  char gamertag[32]  NUL-terminated ASCII
    +0x48  char clantag[8]    NUL-terminated ASCII (may be empty)

Scans the given address range (default: the whole image region holding the pool),
validates every candidate, and prints addr + RVA + fields. Read-only.
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


def module_bases():
    """name(lower) -> base, via .NET Process.Modules through powershell is slow;
    use toolhelp32 through ctypes instead."""
    TH32CS_SNAPMODULE = 0x08
    TH32CS_SNAPMODULE32 = 0x10
    INVALID = ctypes.c_void_p(-1).value

    class MODULEENTRY32(ctypes.Structure):
        _fields_ = [("dwSize", w.DWORD), ("th32ModuleID", w.DWORD),
                    ("th32ProcessID", w.DWORD), ("GlblcntUsage", w.DWORD),
                    ("ProccntUsage", w.DWORD), ("modBaseAddr", ctypes.c_void_p),
                    ("modBaseSize", w.DWORD), ("hModule", w.HMODULE),
                    ("szModule", ctypes.c_char * 256), ("szExePath", ctypes.c_char * 260)]

    pid = find_pid()
    if not pid:
        return {}
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if snap == INVALID:
        return {}
    me = MODULEENTRY32()
    me.dwSize = ctypes.sizeof(MODULEENTRY32)
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


def parse_record(data, i, base):
    """i = offset of the XUID field inside data. Return dict or None."""
    if i + 0x28 + 4 > len(data):
        return None
    xuid = struct.unpack_from("<Q", data, i)[0]
    if (xuid >> 32) != STEAM_HI:
        return None
    if struct.unpack_from("<I", data, i + 0x08)[0] != 0:
        return None
    level = struct.unpack_from("<I", data, i + 0x0C)[0]
    if level > 100000:
        return None
    slot = struct.unpack_from("<I", data, i + 0x18)[0]
    if slot > 4096:
        return None
    raw = data[i + 0x28:i + 0x28 + 32].split(b"\x00")[0]
    if not raw or len(raw) > 31:
        return None
    if not all(32 <= b < 127 for b in raw):
        return None
    name = raw.decode("latin-1")
    craw = data[i + 0x48:i + 0x48 + 8].split(b"\x00")[0]
    clan = craw.decode("latin-1") if craw and all(32 <= b < 127 for b in craw) else ""
    return dict(addr=base + i, xuid=xuid, level=level, slot=slot, name=name, clan=clan)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--addr", type=lambda s: int(s, 0), default=0x7FF61EFCE000)
    ap.add_argument("--max-mb", type=int, default=512)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    out = []

    def w(s=""):
        out.append(s)

    pid = find_pid()
    w("=== players_extract @ %s ===" % time.strftime("%H:%M:%S"))
    w("pid = %s" % pid)
    if not pid:
        w("blackops3.exe not running"); finish(out, a.out); return
    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, 0, pid)

    bases = module_bases()
    game_base = bases.get("blackops3.exe")
    w("blackops3.exe base = %s" % (hex(game_base) if game_base else "?"))
    for k in sorted(bases):
        if "blackops3" in k or "d3d11" in k:
            w("   %-24s %s" % (k, hex(bases[k])))

    mbi = MBI64()
    k32.VirtualQueryEx(h, ctypes.c_void_p(a.addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
    w("region base=0x%X size=0x%X (%.0f MB)"
      % (mbi.BaseAddress, mbi.RegionSize, mbi.RegionSize / 1048576.0))
    if game_base:
        w("region base - module base = %s (RVA 0x%X)"
          % (hex(mbi.BaseAddress - game_base) if mbi.BaseAddress >= game_base else "-",
             mbi.BaseAddress - game_base if mbi.BaseAddress >= game_base else 0))

    # scan
    recs = []
    total = 0
    cap = a.max_mb * 1048576
    CH = 8 * 1048576
    OVER = 0x200
    off = 0
    while off < mbi.RegionSize and total < cap:
        n = min(CH, mbi.RegionSize - off)
        data = read_at(h, mbi.BaseAddress + off, n)
        total += len(data)
        if data:
            s = 0
            while True:
                j = data.find(b"\x01\x00\x10\x01", s)
                if j < 0:
                    break
                i = j - 4
                if i >= 0:
                    r = parse_record(data, i, mbi.BaseAddress + off)
                    if r:
                        recs.append(r)
                s = j + 1
        if off + n >= mbi.RegionSize:
            break
        off += n - OVER
        if total >= cap:
            break

    # dedupe by (xuid, addr)
    seen = set()
    uniq = []
    for r in recs:
        k = (r["xuid"], r["addr"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    uniq.sort(key=lambda r: r["addr"])

    w("")
    w("scanned %.0f MB  ->  %d records" % (total / 1048576.0, len(uniq)))
    w("")
    w("%-14s %-12s %-6s %-5s %-8s %-20s %s" % ("address", "RVA", "level", "slot", "steamid64", "gamertag", "clan"))
    for r in uniq:
        rva = ("0x%X" % (r["addr"] - game_base)) if game_base else "-"
        w("0x%012X %-12s %-6d %-5d %-8s %-20s %s"
          % (r["addr"], rva, r["level"], r["slot"], str(r["xuid"]), r["name"], r["clan"] or "-"))

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
