# -*- coding: utf-8 -*-
r"""列出一个目录里所有 DLL/EXE 的 PE 位数（拿 DXVK 包时先过这一关）。

用法: probe_dir.py <目录> [<目录> ...]
"""
import io
import os
import struct
import sys

MACHINE = {0x8664: "x64", 0x014C: "x86", 0xAA64: "ARM64"}


def machine(path):
    try:
        with io.open(path, "rb") as fh:
            head = fh.read(0x400)
        if head[:2] != b"MZ":
            return "not-PE"
        e = struct.unpack_from("<I", head, 0x3C)[0]
        if head[e:e + 4] != b"PE\0\0":
            return "bad-PE"
        return MACHINE.get(struct.unpack_from("<H", head, e + 4)[0],
                           "0x%04X" % struct.unpack_from("<H", head, e + 4)[0])
    except Exception:                                   # noqa: BLE001
        return "?"


dirs = sys.argv[1:] or ["."]
for d in dirs:
    print("=== %s" % d)
    if not os.path.isdir(d):
        print("    (不是目录)")
        continue
    for name in sorted(os.listdir(d)):
        p = os.path.join(d, name)
        if not os.path.isfile(p):
            continue
        if os.path.splitext(name)[1].lower() not in (".dll", ".exe"):
            print("    %-34s %10d bytes  (非 PE，未判位数)" % (name, os.path.getsize(p)))
            continue
        print("    %-34s %10d bytes  %s" % (name, os.path.getsize(p), machine(p)))
