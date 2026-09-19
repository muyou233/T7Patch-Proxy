# -*- coding: utf-8 -*-
# 在 v3.2.4 的 DLL 里找我们本机 exe 的指纹常量。
# 如果 SizeOfImage / 文件大小 / PE checksum 这些数原样出现在 DLL 数据区，
# 就证明这个 DLL 的表里确实有"September 2026"这一档、且用的就是这些字段。
import struct

DLL = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\Scropts.QOL.v3.2.4.dll"
EXE = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\BlackOps3.exe"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\scropts_profile_match.txt"

dll = open(DLL, "rb").read()
exe = open(EXE, "rb").read()

e = struct.unpack_from("<I", exe, 0x3C)[0]
coff = e + 4
optsize, = struct.unpack_from("<H", exe, coff + 16)
opt = coff + 20
size_of_image, = struct.unpack_from("<I", exe, opt + 56)
checksum, = struct.unpack_from("<I", exe, opt + 64)
file_size = len(exe)

facts = {
    "SizeOfImage(0x%08X)" % size_of_image: struct.pack("<I", size_of_image),
    "file_size(%d/0x%X)" % (file_size, file_size): struct.pack("<I", file_size),
    "PECheckSum(0x%08X)" % checksum: struct.pack("<I", checksum),
    "SizeOfImage as u64": struct.pack("<Q", size_of_image),
    "file_size as u64": struct.pack("<Q", file_size),
}

lines = []
def w(s=""):
    lines.append(s)

w("=== 在 DLL 里检索本机 exe 的指纹常量 ===")
for label, pat in facts.items():
    hits = []
    i = dll.find(pat)
    while i != -1:
        hits.append(i)
        i = dll.find(pat, i + 1)
    w("  %-28s -> %d 次命中  %s" % (label, len(hits), ["0x%X" % h for h in hits[:8]]))

# 再看看 DLL 里有没有"三个 profile"的痕迹：一串相近的 SizeOfImage 值
# （BO3 各构建 SizeOfImage 都在 0x1Dxxxxxx 附近）
w("")
w("=== DLL 数据区里形如 0x1D0xxxxx-0x1D7xxxxx 的 4 字节大端/小端值（疑似各构建 SizeOfImage）===")
seen = set()
for m in __import__("re").finditer(rb"[\x00-\xff]{4}", dll):
    pass
for off in range(0, len(dll) - 4):
    v, = struct.unpack_from("<I", dll, off)
    if 0x1D000000 <= v <= 0x1D7FFFFF:
        if v not in seen:
            seen.add(v)
            w("  0x%08X   偏移 0x%X" % (v, off))
w("  共 %d 个不同值" % len(seen))

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("done")
