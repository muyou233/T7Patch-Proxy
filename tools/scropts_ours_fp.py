# -*- coding: utf-8 -*-
# 最后一问：我们 exe 的指纹到底以什么形式(若有)出现在 DLL 里
import struct

DLL = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\Scropts.QOL.v3.2.4.dll"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\scropts_ours_fp.txt"
dll = open(DLL, "rb").read()
L = []
def w(s=""): L.append(s)

CAND = {
    "SizeOfImage 0x1D75BC00": 0x1D75BC00,
    "CheckSum 0x06531394": 0x06531394,
    "文件大小 0x6539400": 0x06539400,   # 101.1MB 附近
    "EntryPoint? 0x0": 0,
}
for name, v in CAND.items():
    if v == 0:
        continue
    w("%-26s uint32=%d uint64=%d  ascii=%d" % (
        name,
        dll.count(struct.pack("<I", v)),
        dll.count(struct.pack("<Q", v)),
        dll.count(("%08X" % v).encode("ascii")) + dll.count(("%x" % v).encode("ascii")),
    ))

w("")
w("=== 直接找 ascii 片段 ===")
for s in (b"1D75BC00", b"1d75bc00", b"1D75", b"BlacksOps", b"BO3", b"March 2023\x00", b"Selected"):
    w("  %-14s -> %s" % (s.decode("latin-1"), ["0x%X" % i for i in [dll.find(s)] if i != -1]))

w("")
w("=== 找'时间戳+镜像大小'可能打包成 8 字节的形态 ===")
for v in (0x1D75BC00, 0x06531394):
    for hi in (0, 1, 0x5E8E, 0x6000, 0x5F00):
        q = (hi << 32) | v
        n = dll.count(struct.pack("<Q", q))
        if n:
            w("  0x%016X 出现 %d 次" % (q, n))

open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("done")
