# -*- coding: utf-8 -*-
# Read-only PE inspection of BlackOps3.exe: image size, sections, and where the
# RVAs used by the reference project fall.  Nothing is written outside .codebuddy.
import struct, os, re, sys

EXE = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\BlackOps3.exe"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\pe_probe.txt"
CRC_H = r"E:\MyProject\T7Patch\Scropts-QOL-main\ImGui DirectX 11 Kiero Hook\crc.h"

lines = []
def w(s=""):
    lines.append(s)

data = open(EXE, "rb").read()
w("file size = %d (%.1f MB)" % (len(data), len(data) / 1048576.0))

e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
assert data[e_lfanew:e_lfanew + 4] == b"PE\0\0", "not a PE"
coff = e_lfanew + 4
nsec, = struct.unpack_from("<H", data, coff + 2)
optsize, = struct.unpack_from("<H", data, coff + 16)
opt = coff + 20
magic, = struct.unpack_from("<H", data, opt)
w("PE32+ = %s  (magic 0x%X)" % (magic == 0x20b, magic))
size_of_image, = struct.unpack_from("<I", data, opt + 56)
w("SizeOfImage = 0x%X  (%.1f MB)" % (size_of_image, size_of_image / 1048576.0))
w("NumberOfSections = %d" % nsec)

secs = []
so = opt + optsize
for i in range(nsec):
    off = so + i * 40
    name = data[off:off + 8].rstrip(b"\0").decode("latin1")
    vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, off + 8)
    chars, = struct.unpack_from("<I", data, off + 36)
    secs.append((name, vaddr, vsize, rawptr, rawsize, chars))
    w("  %-8s VA=0x%08X VSize=0x%08X (%.1f MB) Raw=0x%08X RawSize=0x%08X (%.1f MB) Flags=0x%08X"
      % (name, vaddr, vsize, vsize / 1048576.0, rawptr, rawsize, rawsize / 1048576.0, chars))

def section_of(rva):
    for name, vaddr, vsize, rawptr, rawsize, ch in secs:
        if vaddr <= rva < vaddr + max(vsize, rawsize):
            return name, vaddr, rawptr, rawsize
    return None, 0, 0, 0

def file_off(rva):
    name, vaddr, rawptr, rawsize = section_of(rva)
    if name is None:
        return None
    d = rva - vaddr
    if d >= rawsize:
        return None
    return rawptr + d

# --- how much of the image is actually mapped beyond the file (packed/encrypted?) ---
w("")
w("--- 各 section 的 VSize/RawSize 比（>1 说明运行时比磁盘大 = 解包/解密后展开）---")
for name, vaddr, vsize, rawptr, rawsize, ch in secs:
    if rawsize:
        w("  %-8s VSize/RawSize = %.2f" % (name, vsize / float(rawsize)))

# --- sample the .text bytes on disk: does it look like x86 code (readable) ---
w("")
w("--- .text 磁盘样本（判断是否加密/加壳）---")
text = [s for s in secs if s[0] == ".text"]
if text:
    name, vaddr, vsize, rawptr, rawsize, ch = text[0]
    for rva in (0x1000, 0x100000, 0x1000000, 0x2000000, 0x4000000, 0x8000000, 0x10000000, 0x1A000000, 0x1D000000):
        fo = file_off(rva)
        if fo and fo + 16 <= len(data):
            b = data[fo:fo + 16]
            w("  rva 0x%09X -> raw 0x%X : %s" % (rva, fo, " ".join("%02X" % x for x in b)))
        else:
            w("  rva 0x%09X -> 不在磁盘数据内（只存在于运行时映射）" % rva)

# --- crc lists ---
w("")
w("--- crc1/crc2/crc3 中 RVA 的分布 ---")
txt = open(CRC_H, encoding="utf-8", errors="replace").read()
blocks = re.split(r"static\s+uintptr_t\s+(\w+)\[\]\s*=\s*\{", txt)
pairs = list(zip(blocks[1::2], blocks[2::2]))
for name, body in pairs:
    vals = [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]+)", body)]
    w("  %s: %d 个, min=0x%X max=0x%X, >0x268CC60 的有 %d 个"
      % (name, len(vals), min(vals), max(vals), sum(1 for v in vals if v > 0x268CC60)))
    cnt = {}
    for v in vals:
        nm, _, _, _ = section_of(v)
        cnt[nm] = cnt.get(nm, 0) + 1
    w("     落在 section: %s" % cnt)
    outside = [v for v in vals if file_off(v) is None]
    w("     磁盘上取不到字节的: %d 个" % len(outside))
    for v in vals[:6]:
        fo = file_off(v)
        if fo:
            b = data[fo:fo + 8]
            w("     0x%08X -> raw 0x%X : %s" % (v, fo, " ".join("%02X" % x for x in b)))
        else:
            w("     0x%08X -> 无磁盘字节" % v)

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("done ->", OUT)
