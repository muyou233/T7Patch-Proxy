"""Dump the first bytes of one or more RVAs inside a PE file.

Why this exists: every offset we take from an offsets list is a *claim* that
"a function starts here".  Before hooking it (a wrong address = the game
crashes) we can check it cheaply, offline: a real x64 function starts with a
prologue (push/mov/sub), while a stale or bogus RVA usually lands on padding
(0xCC / 0x00) or in the middle of unrelated instructions.

Usage:
    python pe_rva_probe.py <pe-file> <rva> [<rva> ...]

RVAs are the *final* ones (build translation already applied) - this script
does no relocation math on purpose, so it can also check a known-good address
as a reference.
"""

import struct
import sys


def parse_sections(data):
    if data[:2] != b"MZ":
        raise SystemExit("not a PE file (no MZ)")
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    if data[e_lfanew:e_lfanew + 4] != b"PE\0\0":
        raise SystemExit("not a PE file (no PE signature)")
    coff = e_lfanew + 4
    nsec = struct.unpack_from("<H", data, coff + 2)[0]
    opt_size = struct.unpack_from("<H", data, coff + 16)[0]
    opt = coff + 20
    size_of_image = struct.unpack_from("<I", data, opt + 56)[0]
    sec_off = opt + opt_size
    sections = []
    for i in range(nsec):
        s = sec_off + i * 40
        name = data[s:s + 8].rstrip(b"\0").decode("latin1")
        vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, s + 8)
        sections.append((name, vaddr, vsize, rawptr, rawsize))
    return sections, size_of_image


def rva_to_off(sections, rva):
    for name, vaddr, vsize, rawptr, rawsize in sections:
        if vaddr <= rva < vaddr + max(vsize, rawsize):
            return rawptr + (rva - vaddr), name
    return None, None


def describe(b):
    """A short guess at what the bytes look like."""
    if all(x == 0xCC for x in b):
        return "int3 padding - NOT code"
    if all(x == 0x00 for x in b):
        return "zero padding - NOT code"
    first = b[:3]
    if first in (b"\x48\x89\x5c", b"\x48\x8b\xc4", b"\x48\x83\xec",
                 b"\x48\x81\xec", b"\x40\x53", b"\x48\x89\x4c",
                 b"\x4c\x89\x44", b"\x48\x89\x74", b"\x57", b"\x55",
                 b"\x56", b"\x53", b"\x48\x8b\xc1", b"\x4c\x8b\xdc"):
        return "looks like a function prologue"
    return "unknown (not an obvious prologue)"


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    path = sys.argv[1]
    with open(path, "rb") as f:
        data = f.read()
    sections, size_of_image = parse_sections(data)
    print("file        : %s" % path)
    print("size        : %d bytes (SizeOfImage 0x%X)" % (len(data), size_of_image))
    print("sections    : %s" % ", ".join(s[0] for s in sections))
    print("")
    for arg in sys.argv[2:]:
        rva = int(arg, 16)
        off, sec = rva_to_off(sections, rva)
        if off is None:
            print("RVA 0x%08X : outside every section -> %s"
                  % (rva, "beyond SizeOfImage" if rva >= size_of_image else "gap"))
            continue
        chunk = data[off:off + 32]
        hexs = " ".join("%02X" % c for c in chunk)
        print("RVA 0x%08X : section %-8s offset 0x%08X" % (rva, sec, off))
        print("              %s" % hexs)
        print("              -> %s" % describe(chunk))
    print("")


if __name__ == "__main__":
    main()
