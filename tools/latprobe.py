"""Probe: which file-access operations actually refresh NTFS LastAccessTime?

Answers the user's objection: "maybe reading it doesn't update the date at all".

Design note: the *reading* of the timestamp (os.stat -> GetFileAttributesExW)
could itself refresh LAT, which would poison the experiment. So the first case
is a pure baseline ("no action at all"); if that case already shows CHANGED,
the measurement method itself is broken and every other row is void.
"""
import os
import sys
import time
import glob
import ctypes
from ctypes import wintypes

BASE = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools"
SENT = 978307200.0  # 2001-01-01 00:00:00 UTC


def fmt(t):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))


def atime(path):
    return os.stat(path).st_atime


k32 = ctypes.windll.kernel32
k32.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
k32.GetFileAttributesW.restype = wintypes.DWORD

k32.CreateFileW.restype = wintypes.HANDLE
k32.CreateFileW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
    wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
]
k32.ReadFile.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
]
k32.CloseHandle.argtypes = [wintypes.HANDLE]

GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x00000001
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80

rows = []


def probe(label, action):
    path = os.path.join(BASE, "_latprobe_%d.bin" % len(rows))
    with open(path, "wb") as f:
        f.write(b"lat probe\n")
    os.utime(path, (SENT, SENT))
    action(path)
    time.sleep(1.0)
    rows.append((label, atime(path)))


def act_nothing(path):
    pass


def act_stat_only(path):
    os.stat(path)


def act_getattrs(path):
    k32.GetFileAttributesW(path)


def act_findfirst(path):
    glob.glob(path)


def act_createfile_close(path):
    h = k32.CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, None,
                        OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
    if h != wintypes.HANDLE(-1).value and h != -1:
        k32.CloseHandle(h)


def act_createfile_read(path):
    h = k32.CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, None,
                        OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None)
    if h != wintypes.HANDLE(-1).value and h != -1:
        buf = ctypes.create_string_buffer(64)
        got = wintypes.DWORD(0)
        k32.ReadFile(h, buf, 64, ctypes.byref(got), None)
        k32.CloseHandle(h)


probe("A. baseline (no action at all)", act_nothing)
probe("B. os.stat (metadata only)", act_stat_only)
probe("C. GetFileAttributesW", act_getattrs)
probe("D. FindFirstFile (glob)", act_findfirst)
probe("E. CreateFile(OPEN_EXISTING) + Close", act_createfile_close)
probe("F. CreateFile + ReadFile", act_createfile_read)

out = os.path.join(BASE, "_latprobe_result.txt")
with open(out, "w", encoding="utf-8") as f:
    f.write("sentinel = %s  (all targets reset to this right before the action)\n" % fmt(SENT))
    f.write("%-42s %-20s %s\n" % ("ACTION", "LAT AFTER", "VERDICT"))
    for label, a in rows:
        verdict = "CHANGED" if abs(a - SENT) > 2 else "unchanged"
        f.write("%-42s %-20s %s\n" % (label, fmt(a), verdict))

for p in glob.glob(os.path.join(BASE, "_latprobe_*.bin")):
    try:
        os.remove(p)
    except OSError:
        pass

print("done")
