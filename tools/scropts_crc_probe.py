# -*- coding: utf-8 -*-
# 关键一问：发布 DLL 里到底存了几套"crc 站点表"？
# crc1 的末尾 4 个地址在本机 crc.h 里是唯一序列，拿它当探针在 DLL 里数出现次数。
import struct, re

DLL = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\Scropts.QOL.v3.2.4.dll"
CRC = r"E:\MyProject\T7Patch\Scropts-QOL-main\ImGui DirectX 11 Kiero Hook\crc.h"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\scropts_crc_probe.txt"

dll = open(DLL, "rb").read()
txt = open(CRC, encoding="utf-8", errors="replace").read()
blocks = re.split(r"static\s+uintptr_t\s+(\w+)\[\]\s*=\s*\{", txt)
arrays = {}
for name, body in zip(blocks[1::2], blocks[2::2]):
    arrays[name] = [int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]+)", body)]

lines = []
def w(s=""):
    lines.append(s)

for name in ("crc1", "crc2", "crc3"):
    vals = arrays[name]
    w("=== %s （源码里 %d 个）===" % (name, len(vals)))
    # 用"末尾 8 个连续地址"当作指纹
    tail = vals[-8:]
    pat = b"".join(struct.pack("<Q", v) for v in tail)
    hits = []
    i = dll.find(pat)
    while i != -1:
        hits.append(i)
        i = dll.find(pat, i + 1)
    w("  末尾 8 个地址的连续序列在 DLL 里出现 %d 次：%s" % (len(hits), ["0x%X" % h for h in hits]))
    # 4 字节版本（若按 uint32 存）
    pat32 = b"".join(struct.pack("<I", v) for v in tail)
    hits32 = []
    i = dll.find(pat32)
    while i != -1:
        hits32.append(i)
        i = dll.find(pat32, i + 1)
    w("  同上按 uint32 打包出现 %d 次：%s" % (len(hits32), ["0x%X" % h for h in hits32[:6]]))
    # 头 8 个
    head = vals[:8]
    pat32h = b"".join(struct.pack("<I", v) for v in head)
    h32 = []
    i = dll.find(pat32h)
    while i != -1:
        h32.append(i)
        i = dll.find(pat32h, i + 1)
    w("  头部 8 个（uint32 打包）出现 %d 次：%s" % (len(h32), ["0x%X" % h for h in h32[:6]]))
    w("")

# 顺便：DLL 里有没有三套不同长度的同类表？（按"同尾不同头"很难判，先看总数量级）
allv = sorted(set(arrays["crc1"] + arrays["crc2"] + arrays["crc3"]))
found = 0
for v in allv:
    if dll.find(struct.pack("<I", v)) != -1:
        found += 1
w("源码三张表合计不同地址 %d 个，其中在 DLL 里能按 uint32 找到的 %d 个" % (len(allv), found))

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("done")
