# -*- coding: utf-8 -*-
# Map RVA->file offset in blackops3.exe and dump raw bytes at the interesting addresses.
import struct

EXE = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\blackops3.exe"
f = open(EXE, "rb")
data = None

def u16(o): return struct.unpack_from("<H", f.read(2) if False else b"\0\0", 0)

f.seek(0)
dos = f.read(0x40)
e_lfanew = struct.unpack_from("<I", dos, 0x3C)[0]
f.seek(e_lfanew)
nt = f.read(0x18)
sig, machine, nsec = struct.unpack_from("<IHH", nt, 0)
print("PE sig=%08X machine=%04X sections=%d" % (sig, machine, nsec))
f.seek(e_lfanew + 0x18)
opt = f.read(0x70)
magic = struct.unpack_from("<H", opt, 0)[0]
sizeOfImage = struct.unpack_from("<I", opt, 0x38)[0]
imageBase = struct.unpack_from("<Q", opt, 0x18)[0]
print("magic=%04X imageBase=%016X sizeOfImage=%X (%.1f MB)" % (magic, imageBase, sizeOfImage, sizeOfImage / 1048576.0))

secs = []
f.seek(e_lfanew + 0x18 + 0xF0)
for i in range(nsec):
    s = f.read(40)
    name = s[0:8].rstrip(b"\0").decode("latin-1")
    vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", s, 8)
    secs.append((name, vaddr, vsize, rawptr, rawsize))
    print("  %-8s vaddr=%08X vsize=%08X rawptr=%08X rawsize=%08X" % (name, vaddr, vsize, rawptr, rawsize))

def rva2off(rva):
    for name, vaddr, vsize, rawptr, rawsize in secs:
        if vaddr <= rva < vaddr + max(vsize, rawsize):
            return rawptr + (rva - vaddr)
    return None

def dump(rva, n=64, label=""):
    off = rva2off(rva)
    print("\n--- RVA 0x%X %s ---" % (rva, label))
    if off is None:
        print("   <no section covers this RVA>"); return
    f.seek(off)
    b = f.read(n)
    for i in range(0, len(b), 16):
        c = b[i:i + 16]
        print("  0x%08X  %s  |%s|" % (rva + i, " ".join("%02X" % x for x in c),
                                      "".join(chr(x) if 32 <= x < 127 else "." for x in c)))

dump(0x16880A50, 0x60, "record-B caller (return addr at 0x16880A79)")
dump(0x227CA90, 0x90, "record-A crash site (RIP 0x227CAC4)")
dump(0x227CB20, 0x20, "I_stricmp (PTR_I_stricmp)")
for a in (0x1687C258, 0x1689A078, 0x16885038, 0x16876C08, 0x1D65F35F):
    dump(a, 48, "argument pointer seen in registers/stack")
f.close()
print("\n=== DONE ===")
