# -*- coding: utf-8 -*-
# Compare the PE sections of two DLLs byte-for-byte, and dump the CodeView (PDB)
# identity of each.  Used to prove that a pure file-move refactor changed nothing
# in the generated code: every ".text"-like section must hash equal, and only the
# PDB identity (GUID/age/path) may differ.
#
#   python pe_text_hash.py <a.dll> <b.dll>
import sys, hashlib, struct

def u16(b, o): return struct.unpack_from("<H", b, o)[0]
def u32(b, o): return struct.unpack_from("<I", b, o)[0]

def sections(path):
    b = open(path, "rb").read()
    lfanew = u32(b, 0x3C)
    assert b[lfanew:lfanew + 4] == b"PE\x00\x00", "not a PE file: " + path
    nsec = u16(b, lfanew + 6)
    optsz = u16(b, lfanew + 20)
    opt = lfanew + 24
    magic = u16(b, opt)
    dd = opt + (112 if magic == 0x20B else 96)
    dbg_rva, dbg_size = u32(b, dd + 6 * 8), u32(b, dd + 6 * 8 + 4)
    out = []
    for i in range(nsec):
        s = lfanew + 24 + optsz + i * 40
        name = b[s:s + 8].rstrip(b"\x00").decode("latin-1")
        vsize = u32(b, s + 8)
        rva = u32(b, s + 12)
        rsize = u32(b, s + 16)
        praw = u32(b, s + 20)
        n = min(vsize, rsize) if vsize else rsize
        out.append((name, rva, vsize, rsize, hashlib.sha256(b[praw:praw + n]).hexdigest()))
    return b, magic, out, dbg_rva

def codeview(b, sections_, dbg_rva):
    if dbg_rva == 0:
        return None
    praw = None
    for name, rva, vsize, rsize, _ in sections_:
        if rva <= dbg_rva < rva + (vsize or rsize):
            praw = dbg_rva - rva
            break
    if praw is None:
        return None
    # 28-byte IMAGE_DEBUG_DIRECTORY entries; find the CodeView one (type 2)
    for k in range(8):
        o = praw + k * 28
        dtype = u32(b, o + 12)
        prawptr = u32(b, o + 24)
        if dtype == 2 and prawptr:
            sig = b[prawptr:prawptr + 4]
            g = b[prawptr + 4:prawptr + 20]
            age = u32(b, prawptr + 20)
            path = b[prawptr + 24:prawptr + 260].split(b"\x00")[0].decode("latin-1", "replace")
            gs = "%08X-%04X-%04X-%s-%s" % (
                u32(g, 0), u16(g, 4), u16(g, 6),
                g[8:10].hex().upper(), g[10:16].hex().upper())
            return sig.decode("latin-1"), gs, age, path
    return None

def report(path):
    b, magic, secs, dbg = sections(path)
    print("=== %s ===" % path)
    print("  size on disk      : %d" % len(b))
    print("  pe magic          : 0x%X (%s)" % (magic, "PE32+" if magic == 0x20B else "PE32"))
    cv = codeview(b, secs, dbg)
    if cv:
        print("  CodeView (%s)  : GUID %s  age %d" % (cv[0], cv[1], cv[2]))
        print("  PDB path          : %s" % cv[3])
    for name, rva, vsize, rsize, h in secs:
        print("  %-8s rva=0x%08X vsize=%9d rawsize=%9d sha256=%s" % (name, rva, vsize, rsize, h))
    return b, secs

def main():
    a, b = sys.argv[1], sys.argv[2]
    ba, sa = report(a)
    print()
    bb, sb = report(b)
    print()
    da = {n: h for n, _, _, _, h in sa}
    db = {n: h for n, _, _, _, h in sb}
    same, diff = [], []
    for n in da:
        if n in db:
            (same if da[n] == db[n] else diff).append(n)
    print("=== section comparison ===")
    print("  identical : %s" % (", ".join(same) if same else "(none)"))
    print("  differing : %s" % (", ".join(diff) if diff else "(none)"))
    print("  only in %s : %s" % (a.split("\\")[-1], ", ".join(sorted(set(da) - set(db))) or "(none)"))
    print("  only in %s : %s" % (b.split("\\")[-1], ", ".join(sorted(set(db) - set(da))) or "(none)"))
    print()
    print("  whole-file sha256 A : %s" % hashlib.sha256(ba).hexdigest().upper())
    print("  whole-file sha256 B : %s" % hashlib.sha256(bb).hexdigest().upper())

main()
