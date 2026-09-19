# -*- coding: utf-8 -*-
"""Does BlackOps3.exe carry an RCDATA resource with our dictionary's id?

translate.cpp calls FindResource(nullptr, MAKEINTRESOURCE(101), RT_RCDATA).
A NULL hModule means "the module used to create the process" - i.e. the game
exe, NOT our d3d11.dll.  So the built-in dictionary only ever loads if the EXE
happens to carry RT_RCDATA/101.  This walks the EXE's own resource directory and
answers that directly, instead of arguing from the documentation.

The deployed d3d11.dll is dumped through the same code path as a control: the
resource must be visible THERE, otherwise the whole idea is moot.

PE resource layout notes (the two things that are easy to get wrong):
  - PE header: COFF starts at pe+4, so NumberOfSections is at pe+6 and
    SizeOfOptionalHeader at pe+20.
  - Inside the resource directory every OffsetToData is relative to the START
    OF THE RESOURCE DIRECTORY, and the high bit marks a subdirectory.
"""
import os
import struct

RT_RCDATA = 10
GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\res_check.txt"


def parse_resource_tree(path):
    data = open(path, "rb").read()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        return None, "not a PE file"
    n_sections = struct.unpack_from("<H", data, pe + 6)[0]
    opt_size = struct.unpack_from("<H", data, pe + 20)[0]
    opt = pe + 24
    magic = struct.unpack_from("<H", data, opt)[0]
    dir_off = opt + (112 if magic == 0x20B else 96)
    rsrc_rva = struct.unpack_from("<I", data, dir_off + 2 * 8)[0]
    if not rsrc_rva:
        return None, "no resource directory"

    sec_off = opt + opt_size
    sections = []
    for i in range(n_sections):
        s = sec_off + i * 40
        vsize, va, raw = struct.unpack_from("<III", data, s + 8)
        sections.append((va, vsize, raw))

    def rva_to_off(rva):
        for va, vsize, raw in sections:
            if va <= rva < va + max(vsize, 0x1000):
                return raw + (rva - va)
        return None

    rsrc_off = rva_to_off(rsrc_rva)
    if rsrc_off is None:
        return None, "resource RVA not inside any section"

    leaves = []
    debug = []

    def entries_at(dir_off):
        n_named, n_id = struct.unpack_from("<HH", data, dir_off + 12)
        rows = []
        for i in range(n_named + n_id):
            name_or_id, offset = struct.unpack_from("<II", data, dir_off + 16 + i * 8)
            rows.append((name_or_id, offset))
        return rows

    def walk(dir_off, path, depth=0):
        if depth > 3:
            debug.append("depth cap at %s" % data[dir_off:dir_off + 8])
            return
        for eid, offset in entries_at(dir_off):
            if offset & 0x80000000:                      # subdirectory
                sub = rva_to_off(rsrc_rva + (offset & 0x7FFFFFFF))
                debug.append("  " * depth + "dir eid=0x%X off=0x%X sub=%s"
                             % (eid, offset & 0x7FFFFFFF, hex(sub) if sub else None))
                if sub is not None:
                    walk(sub, path + [eid], depth + 1)
            else:                                        # IMAGE_RESOURCE_DATA_ENTRY
                de = rva_to_off(rsrc_rva + offset)
                if de is None:
                    continue
                data_rva, size = struct.unpack_from("<II", data, de)
                leaves.append((tuple(path + [eid]), data_rva, size))

    debug.append("PE magic=0x%X opt_size=%d n_sections=%d rsrc_rva=0x%X rsrc_off=0x%X"
                 % (magic, opt_size, n_sections, rsrc_rva, rsrc_off))
    walk(rsrc_off, [])
    return (leaves, rva_to_off, data, debug), None


lines = []
targets = [os.path.join(GAME, "BlackOps3.exe"),
           os.path.join(GAME, "T7Patch", "d3d11.dll")]
for path in targets:
    lines.append("=" * 72)
    if not os.path.exists(path):
        lines.append("%s : MISSING" % path)
        continue
    lines.append("%s  (%d bytes)" % (path, os.path.getsize(path)))
    res, err = parse_resource_tree(path)
    if err:
        lines.append("   !! %s" % err)
        continue
    leaves, rva_to_off, data, debug = res
    lines.extend(debug)
    type_counts = {}
    rcd = []
    for p, rva, size in leaves:
        type_counts[p[0]] = type_counts.get(p[0], 0) + 1
        if p[0] == RT_RCDATA and len(p) >= 2:
            rcd.append((p[1], size, rva))
    lines.append("   resource types: %s" % sorted(type_counts.items()))
    lines.append("   RT_RCDATA(10) entries: %d" % len(rcd))
    for eid, size, rva in sorted(rcd):
        off = rva_to_off(rva)
        head = data[off:off + 20].split(b"\n")[0][:20] if off is not None else b"?"
        lines.append("      id=%-6s size=%-8d head=%r" % (eid, size, head))
    hit = [e for e in rcd if e[0] == 101]
    lines.append("   >>> RCDATA id=101: %s"
                 % ("PRESENT (size=%d)" % hit[0][1] if hit else "ABSENT"))

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
print("\n".join(lines))
