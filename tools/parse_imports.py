# -*- coding: utf-8 -*-
# Minimal PE import-table parser: does BlackOps3.exe statically import d3dcompiler_46?
import struct, sys

path = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\BlackOps3.exe"
out = []

with open(path, "rb") as f:
    data = f.read()

out.append("file size: %d bytes" % len(data))
if data[:2] != b"MZ":
    out.append("not a PE")
else:
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    out.append("PE header at 0x%X" % e_lfanew)
    sig = data[e_lfanew:e_lfanew+4]
    out.append("signature: %s" % sig)
    coff = e_lfanew + 4
    machine, nsec, tstamp, symptr, nsym, optsize, chars = struct.unpack_from("<HHIIIHH", data, coff)
    out.append("machine=0x%X sections=%d optsize=%d" % (machine, nsec, optsize))
    opt = coff + 20
    magic = struct.unpack_from("<H", data, opt)[0]
    out.append("optional magic=0x%X (0x20B=PE32+)" % magic)
    # data directories: import table is index 1
    if magic == 0x20B:
        dd = opt + 112
    else:
        dd = opt + 96
    imp_rva, imp_size = struct.unpack_from("<II", data, dd + 8)
    out.append("import dir RVA=0x%X size=%d" % (imp_rva, imp_size))
    # section headers to map RVA->offset
    secs = []
    sh = opt + optsize
    for i in range(nsec):
        off = sh + i * 40
        name = data[off:off+8].rstrip(b"\x00").decode("latin1")
        vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, off + 8)
        secs.append((name, vaddr, vsize, rawptr, rawsize))
        out.append("  section %-8s rva=0x%08X vsize=0x%X raw=0x%X" % (name, vaddr, vsize, rawptr))

    def rva_to_off(rva):
        for name, vaddr, vsize, rawptr, rawsize in secs:
            if vaddr <= rva < vaddr + max(vsize, rawsize):
                return rawptr + (rva - vaddr)
        return None

    imp_off = rva_to_off(imp_rva)
    out.append("\n=== imported DLLs ===")
    dlls = []
    i = 0
    while True:
        off = imp_off + i * 20
        oft, tstamp_, fwd, name_rva, first_thunk = struct.unpack_from("<IIIII", data, off)
        if name_rva == 0:
            break
        no = rva_to_off(name_rva)
        dllname = data[no:data.index(b"\x00", no)].decode("latin1")
        dlls.append(dllname)
        out.append("  %s" % dllname)
        i += 1
        if i > 200:
            break

    out.append("")
    hits = [d for d in dlls if "d3dcompiler" in d.lower() or "d3d11" in d.lower()]
    out.append("=== d3d-related static imports: %s ===" % (hits if hits else "NONE"))

with open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\imports.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("import parse done")
