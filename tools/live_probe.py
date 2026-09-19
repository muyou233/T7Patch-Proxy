#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
live_probe.py -- READ-ONLY live reconnaissance of a running BlackOps3.exe.

Nothing is written to the game, no engine function is called. We only read
committed PRIVATE memory with ReadProcessMemory and interpret it with the
layouts taken from src/structs.h:

  FixedClientInfo { __int64 xuid; char gamertag[32]; }        (40 = 0x28 bytes)
  SessionInfo     { bool inSession; char pad[7]; netadr_t; time_t last; }  (0x20)
  ActiveClient    { char pad[0x410]; FixedClientInfo; SessionInfo[2]; }    (0x478)
  netadr_t        { u8 ipv4[4]; u16 port; u16 pad; i32 type; i32 localNetID; }

Every Steam XUID is 0x01100001_xxxxxxxx, i.e. little-endian bytes
  ?? ?? ?? ?? 01 00 10 01
so that 8-byte signature finds every player record in the process without
needing any anchor, including the other members of the lobby.

  python live_probe.py
  python live_probe.py --passes 12 --interval 20      # watch a whole session
  python live_probe.py --ip 185.34.107.52             # hunt one address
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
import winreg

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
RE_IPPORT = re.compile(rb"(?<![0-9.])((?:\d{1,3}\.){3}\d{1,3}):(\d{1,5})(?![0-9])")


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


def own_identity():
    steam_path = None
    for root, key in ((winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                      (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")):
        try:
            steam_path, _ = winreg.QueryValueEx(winreg.OpenKey(root, key), "SteamPath")
            break
        except Exception:
            continue
    sid = name = None
    if steam_path:
        try:
            txt = open(os.path.join(steam_path, "config", "loginusers.vdf"),
                       encoding="utf-8", errors="replace").read()
            best = None
            for sid_, body in re.findall(r'"(\d{17})"\s*\{(.*?)\n\t\}', txt, re.S):
                nm = re.search(r'"PersonaName"\s*"([^"]*)"', body)
                cand = (sid_, nm.group(1) if nm else "")
                if re.search(r'"MostRecent"\s*"1"', body):
                    best = cand
                    break
                best = best or cand
            if best:
                sid, name = best
        except Exception:
            pass
    return sid, name


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


def read_at(h, addr, n):
    buf, nread = ctypes.create_string_buffer(n), ctypes.c_size_t()
    ok = k32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(nread))
    return buf.raw[:nread.value] if ok and nread.value else b""


def name_at(blob, off):
    b = blob[off:off + 32].split(b"\x00")[0]
    if not (2 <= len(b) <= 31):
        return None
    try:
        s = b.decode("ascii")
    except UnicodeDecodeError:
        return None
    return s if all(0x20 <= ord(c) < 0x7F for c in s) else None


def netadr_at(blob, off):
    if off + 16 > len(blob):
        return None
    b = blob[off:off + 16]
    a, c, d, e = b[0], b[1], b[2], b[3]
    if not (1 <= a <= 223 and 1 <= e <= 254) or b[6] or b[7]:
        return None
    typ, lnid = struct.unpack("<i", b[8:12])[0], struct.unpack("<i", b[12:16])[0]
    if typ not in (-1, 0, 1, 2, 3, 4) or lnid not in (-1, 0, 1, 2, 3, 4, 5):
        return None
    port = struct.unpack(">H", b[4:6])[0]
    if not (1024 <= port <= 65535):
        port = struct.unpack("<H", b[4:6])[0]
    if not (1024 <= port <= 65535):
        return None
    return "%d.%d.%d.%d:%d" % (a, c, d, e, port)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int)
    ap.add_argument("--passes", type=int, default=1)
    ap.add_argument("--interval", type=float, default=20.0)
    ap.add_argument("--max-mb", type=int, default=1500)
    ap.add_argument("--ip", action="append", default=[])
    ap.add_argument("--no-ipscan", action="store_true",
                    help="skip the ip:port ASCII sweep (it is the memory hog on huge scans)")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "live_probe.txt"))
    a = ap.parse_args()

    pid = a.pid or find_pid()
    if not pid:
        print("BlackOps3.exe not running")
        return 2
    sid, persona = own_identity()

    lines = []
    def w(s=""):
        print(s)
        lines.append(s)

    w("=" * 74)
    w("live_probe  pid=%d  %s   me=%s (%s)" % (pid, time.strftime("%H:%M:%S"), persona, sid))
    if a.ip:
        w("hunting: %s" % ", ".join(a.ip))
    w("=" * 74)

    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        w("OpenProcess failed err=%d" % ctypes.get_last_error())
        return 3

    tries = [tuple(int(x) for x in s.split(".")) for s in a.ip]

    try:
        regions = collect_regions(h)
        w("private committed regions=%d  total=%.0f MB" % (len(regions), sum(s for _, s in regions) / 1048576.0))

        for p in range(1, a.passes + 1):
            t0 = time.time()
            players, ipports, scanned = {}, {}, 0
            addr_hits = {t: [] for t in tries}
            chunk = 8 << 20
            buf, nread = ctypes.create_string_buffer(chunk), ctypes.c_size_t()

            for base, size in regions:
                off = 0
                while off < size and scanned < (a.max_mb << 20):
                    n = min(chunk, size - off)
                    here = base + off
                    if k32.ReadProcessMemory(h, ctypes.c_void_p(here), buf, n, ctypes.byref(nread)) and nread.value:
                        raw = buf.raw[:nread.value]
                        scanned += len(raw)
                        if not a.no_ipscan and len(ipports) < 200000:
                            for m in RE_IPPORT.finditer(raw):
                                k = m.group(0).decode("ascii")
                                ipports[k] = ipports.get(k, 0) + 1
                        for t in tries:
                            pat = bytes(t)
                            s = 0
                            while True:
                                i = raw.find(pat, s)
                                if i < 0:
                                    break
                                addr_hits[t].append(here + i)
                                s = i + 1
                        s = 0
                        while True:
                            i = raw.find(NEEDLE, s)
                            if i < 0:
                                break
                            if (here + i - 4) % 8 == 0:
                                xa = here + i - 4
                                blob = raw[i - 4:i - 4 + 0x1A0] if i >= 4 else b""
                                if len(blob) >= 0x100:
                                    xuid = struct.unpack("<Q", blob[0:8])[0]
                                    nm = name_at(blob, 8)
                                    if nm:
                                        adrs = []
                                        for k2 in (0, 1):
                                            b2 = 0x28 + 0x20 * k2
                                            if blob[b2] in (0, 1, 2):
                                                na = netadr_at(blob, b2 + 8)
                                                if na:
                                                    adrs.append((k2, blob[b2], na))
                                        key = (xuid, nm)
                                        if key not in players or (adrs and not players[key][2]):
                                            players[key] = (xa, adrs, "%d" % blob[0x28])
                            s = i + 1
                    off += n
            w("")
            w("--- pass %d: scanned %.0f MB in %.1fs ---" % (p, scanned / 1048576.0, time.time() - t0))

            w("  players (xuid+gamertag signature): %d" % len(players))
            for (xuid, nm), (xa, adrs, ins) in sorted(players.items(), key=lambda kv: -kv[1][0]):
                me = " <== me" if sid and str(xuid) == sid else ""
                w("    %-24s xuid=%-20d @0x%X%s" % (nm, xuid, xa, me))
                for k2, ins2, na in adrs:
                    w("        sessionInfo[%d] inSession=%d  netadr=%s  (%s)"
                      % (k2, ins2, na, classify(na.split(":")[0])))

            for t, hits in addr_hits.items():
                ip = "%d.%d.%d.%d" % t
                w("  hunt %s : %d occurrence(s)" % (ip, len(hits)))
                for at in hits[:8]:
                    nb = read_at(h, at - 0x40, 0x80)
                    w("    @0x%X context: %s" % (at, nb.hex(" ") if nb else "<unreadable>"))

            if ipports:
                w("  ip:port ASCII strings: %d distinct" % len(ipports))
                for s, c in sorted(ipports.items(), key=lambda kv: -kv[1])[:20]:
                    w("    %-24s x%-5d %s" % (s, c, classify(s.split(":")[0])))

            if p < a.passes:
                time.sleep(a.interval)
    finally:
        k32.CloseHandle(h)

    open(a.out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
