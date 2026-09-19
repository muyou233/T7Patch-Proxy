# -*- coding: utf-8 -*-
# Dump a raw-file byte window from two PE files side by side, to identify which
# read-only structures a rebuild perturbed.  Companion to rdata_ranges.py.
#
#   python dump_window.py <a.dll> <b.dll> <offset> <len>
import sys

def sect(path, want):
    import struct
    b = open(path, "rb").read()
    lfanew = struct.unpack_from("<I", b, 0x3C)[0]
    nsec = struct.unpack_from("<H", b, lfanew + 6)[0]
    optsz = struct.unpack_from("<H", b, lfanew + 20)[0]
    for i in range(nsec):
        s = lfanew + 24 + optsz + i * 40
        name = b[s:s + 8].rstrip(b"\x00").decode("latin-1")
        if name == want:
            import struct as st
            return b, st.unpack_from("<I", b, s + 20)[0], st.unpack_from("<I", b, s + 12)[0]
    raise SystemExit("no section")

off, ln = int(sys.argv[3]), int(sys.argv[4])
for path in sys.argv[1:3]:
    b, praw, rva = sect(path, ".rdata")
    base = praw + off
    print("=== %s   .rdata+%d  (RVA 0x%X)" % (path, off, rva + off))
    for row in range(0, ln, 16):
        chunk = b[base + row: base + row + 16]
        hexs = " ".join("%02X" % c for c in chunk)
        txt = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        print("  %6d  %-47s  %s" % (off + row, hexs, txt))
