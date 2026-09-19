"""Dump the import DLL list of a PE file (read-only).

Usage:  python pe_imports.py <path-to-exe-or-dll> [filter-substring]

Works on mapped-image RVAs directly from the file (import directory is not
encrypted even when .text is, because the loader needs it).
"""
import struct
import sys


def rva_to_off(sections, rva):
    for va, vsize, raw, rsize in sections:
        if va <= rva < va + max(vsize, rsize):
            return raw + (rva - va)
    return None


def main():
    path = sys.argv[1]
    needle = sys.argv[2].lower() if len(sys.argv) > 2 else None

    data = open(path, "rb").read()
    if data[:2] != b"MZ":
        print("not a PE file")
        return 1
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        print("no PE signature")
        return 1

    coff = e_lfanew + 4
    num_sections = struct.unpack_from("<H", data, coff + 2)[0]
    opt_size = struct.unpack_from("<H", data, coff + 16)[0]
    opt = coff + 20
    magic = struct.unpack_from("<H", data, opt)[0]
    is_pe32p = magic == 0x20B
    dd_off = opt + (112 if is_pe32p else 96)

    import_rva, import_size = struct.unpack_from("<II", data, dd_off + 8)
    sec_off = opt + opt_size
    sections = []
    for i in range(num_sections):
        b = sec_off + i * 40
        vsize, va, rsize, raw = struct.unpack_from("<IIII", data, b + 8)
        name = data[b:b + 8].rstrip(b"\0").decode("latin-1")
        sections.append((va, vsize, raw, rsize))

    print("file      : %s" % path)
    print("sections  : %s" % ", ".join(s[0] and n for n, s in zip(
        [data[sec_off + i * 40:sec_off + i * 40 + 8].rstrip(b"\0").decode("latin-1")
         for i in range(num_sections)], sections)))
    print("imp dir   : rva=0x%X size=0x%X" % (import_rva, import_size))

    if not import_rva:
        print("no import directory")
        return 0

    off = rva_to_off(sections, import_rva)
    if off is None:
        print("import directory RVA not mapped")
        return 1

    print("--- imported DLLs ---")
    i = 0
    while True:
        ent = off + i * 20
        if ent + 20 > len(data):
            break
        oft, tstamp, fwd, name_rva, first_thunk = struct.unpack_from("<IIIII", data, ent)
        if not (oft or tstamp or fwd or name_rva or first_thunk):
            break
        if name_rva:
            noff = rva_to_off(sections, name_rva)
            if noff is not None:
                end = data.index(b"\0", noff)
                dll = data[noff:end].decode("latin-1")
                mark = ""
                if needle and needle in dll.lower():
                    mark = "   <== MATCH"
                print("  %-38s%s" % (dll, mark))
        i += 1
        if i > 4096:
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
