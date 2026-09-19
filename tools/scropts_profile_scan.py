# -*- coding: utf-8 -*-
# 目的：看清 v3.2.4 DLL 里"偏移档案(profile)"到底怎么存的
#  1) 三个 build 名串的位置
#  2) crc 表区(0xF7FF8~0xFAAC8)前后是不是一个描述符结构(指针表 + 名字指针 + 指纹常量)
#  3) 我们 exe 的 SizeOfImage / CheckSum 在不在 DLL 里
import struct, re

DLL = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\Scropts.QOL.v3.2.4.dll"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\scropts_profile_scan.txt"

dll = open(DLL, "rb").read()
L = []

def w(s=""):
    L.append(s)

w("DLL 大小 = 0x%X (%d)" % (len(dll), len(dll)))
w("")

# --- 1) 三个 build 名串 ---
w("=== 1) build 名串在 DLL 内的文件偏移 ===")
for s in (b"March 2023", b"February 2026", b"September 2026",
          b"offset profile", b"Image size:", b"Build marker:"):
    offs = []
    i = dll.find(s)
    while i != -1:
        offs.append(i)
        i = dll.find(s, i + 1)
    w("  %-16s -> %s" % (s.decode(), ["0x%X" % o for o in offs[:8]]))
w("")

# --- 2) crc 表区上下文 ---
# 已知尾地址位置
TAILS = {"crc3": 0xF7FF8, "crc2": 0xFA2A8, "crc1": 0xFAAC8}
w("=== 2) crc 表区上下文（按 8 字节指针 dump，每行 4 个）===")
start = 0xF7E00
end = 0xFAC00
for base in range(start, end, 32):
    chunk = dll[base:base + 32]
    if len(chunk) < 32:
        break
    qs = struct.unpack("<4Q", chunk)
    # 只打印"像指针/像 RVA"的行，减少噪音
    lines = []
    for q in qs:
        if 0x140000000 <= q <= 0x140000000 + 0x40000000:
            lines.append(" .rdata+0x%X" % (q - 0x140000000))
        elif 0x1000000 <= q <= 0x1D800000:
            lines.append(" RVA?0x%X" % q)
        elif q == 0:
            lines.append(" 0")
        else:
            lines.append(" %d" % q if q < 1000 else " 0x%X" % q)
    w("  0x%06X : %s" % (base, " | ".join(lines)))
w("")

# --- 3) 我们 exe 的指纹常量 ---
w("=== 3) 我们 exe 的 PE 指纹是否出现在 DLL 里 ===")
for name, val in (("SizeOfImage", 0x1D75BC00), ("CheckSum", 0x06531394), ("TimeStamp", 0x0)):
    n32 = dll.count(struct.pack("<I", val))
    n64 = dll.count(struct.pack("<Q", val))
    w("  %-12s 0x%08X  uint32命中=%d  uint64命中=%d" % (name, val, n32, n64))
w("")

# --- 4) 在所有"像 uint64 RVA 数组"的区域里，统计每个区域有多少个 0x1Dxxxxxx ---
w("=== 4) DLL 里成片出现 0x1Dxxxxxx(uint64) 的区域（候选表）===")
pat = re.compile(b"(?:\x00\x00\x00\x00[\x00-\x1D]...)", re.S)
# 简化：逐个扫描 4 字节，找值落在 [0x1D000000,0x1D800000) 的 uint64 序列
seq_start = None
count = 0
regions = []
i = 0
n = len(dll)
while i + 8 <= n:
    v = struct.unpack_from("<Q", dll, i)[0]
    if 0x1D000000 <= v < 0x1D800000:
        if seq_start is None:
            seq_start = i
        count += 1
    else:
        if count >= 8:
            regions.append((seq_start, count))
        seq_start = None
        count = 0
    i += 8
if count >= 8:
    regions.append((seq_start, count))
w("  找到 %d 个'连续 >=8 个 0x1Dxxxxxx(uint64)'的区域：" % len(regions))
for off, c in regions[:40]:
    w("    0x%06X  元素=%d  (约 %d 字节)" % (off, c, c * 8))

open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("done")
