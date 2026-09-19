# -*- coding: utf-8 -*-
"""Minimal, non-recursive: list RT_RCDATA ids inside each PE's resource dir.

Answers exactly one question per file: does it carry RT_RCDATA(10) / id 101 -
the resource translate.cpp looks for with FindResource(nullptr, ...), which
resolves against the GAME EXE, not our dll.

Resource directory level 1 = type, level 2 = name/id.  Both are addressed by
offsets relative to the start of the resource directory, with the high bit
marking a subdirectory.  Two levels are enough; no recursion, no leaf walking.
"""
import os
import struct
import traceback

RT_RCDATA = 10
GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\res_probe.txt"

log = []


def rva_to_off(sections, rva):
    for va, vsize, raw, name in sections:
        if va <= rva < va + max(vsize, 0x1000):
            return raw + (rva - va)
    return None


def probe(path):
    data = open(path, "rb").read()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[pe:pe + 4] == b"PE\0\0", "not PE"
    n_sections = struct.unpack_from("<H", data, pe + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    opt = pe + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    dir_off = opt + (112 if magic == 0x20B else 96)
    rsrc_rva = struct.unpack_from("<I", data, dir_off + 2 * 8)[0]
    log.append("  magic=0x%X opt_size=%d n_sections=%d rsrc_rva=0x%X"
               % (magic, opt_size, n_sections, rsrc_rva))
    if not rsrc_rva:
        log.append("  no resource directory")
        return
    sections = []
    sec_off = opt + opt_size
    for i in range(n_sections):
        s = sec_off + i * 40
        name = data[s:s + 8].rstrip(b"\0").decode("ascii", "replace")
        vsize, va, raw = struct.unpack_from("<III", data, s + 8)
        sections.append((va, vsize, raw, name))
    log.append("  sections: %s" % [(n, hex(va), hex(v)) for va, v, _, n in sections])
    zero = rva_to_off(sections, rsrc_rva)
    log.append("  resource dir file offset = %s" % hex(zero) if zero else "  NOT MAPPED")
    if zero is None:
        return

    def entries(dir_off):
        n_named, n_id = struct.unpack_from("<HH", data, dir_off + 12)
        out = []
        for i in range(n_named + n_id):
            eid, off = struct.unpack_from("<II", data, dir_off + 16 + i * 8)
            out.append((eid, off))
        return n_named, n_id, out

    n_named, n_id, level1 = entries(zero)
    log.append("  level1: %d named + %d id entries -> %s"
               % (n_named, n_id, [(hex(e), hex(o)) for e, o in level1]))
    for eid, off in level1:
        if eid != RT_RCDATA:
            continue
        if not (off & 0x80000000):
            log.append("  RT_RCDATA entry is not a directory?! off=0x%X" % off)
            continue
        sub = rva_to_off(sections, rsrc_rva + (off & 0x7FFFFFFF))
        if sub is None:
            log.append("  RT_RCDATA subdir not mapped")
            continue
        n2, n2id, level2 = entries(sub)
        ids = sorted(e for e, _ in level2)
        log.append("  RT_RCDATA ids (%d): %s" % (len(ids), [str(x) for x in ids]))
        log.append("  >>> RCDATA id=101: %s"
                   % ("PRESENT" if 101 in ids else "ABSENT"))


for path in [os.path.join(GAME, "BlackOps3.exe"),
             os.path.join(GAME, "T7Patch", "d3d11.dll")]:
    log.append("=" * 72)
    if not os.path.exists(path):
        log.append("%s : MISSING" % path)
        continue
    log.append("%s  (%d bytes)" % (os.path.basename(path), os.path.getsize(path)))
    try:
        probe(path)
    except Exception:
        log.append("  !! EXCEPTION\n" + traceback.format_exc())

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(log) + "\n")
