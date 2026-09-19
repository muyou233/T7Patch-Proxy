# -*- coding: utf-8 -*-
# 目标：把 DLL 里所有"像 exe 镜像大小"的 32 位常量挖出来 -> 反推它认哪几个 build
# 依据：BlackOps3.exe 的 SizeOfImage 落在 0x1Dxxxxxx 量级（本地实测 0x1D75BC00）
import struct, collections

DLL = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\Scropts.QOL.v3.2.4.dll"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\scropts_fingerprint_hunt.txt"
dll = open(DLL, "rb").read()
L = []

def w(s=""):
    L.append(s)

# ---------- A) uint32 扫描：值落在 0x1D000000~0x1E000000 ----------
w("=== A) DLL 内 uint32 常量中落在 [0x1D000000, 0x1E000000) 的不同值 ===")
w("   （这类值高度可疑 = 某个 exe 的 SizeOfImage）")
cnt = collections.Counter()
for i in range(0, len(dll) - 4, 4):
    v = struct.unpack_from("<I", dll, i)[0]
    if 0x1D000000 <= v < 0x1E000000:
        cnt[v] += 1
for v, c in sorted(cnt.items()):
    w("    0x%08X  出现 %d 次" % (v, c))
w("")

# 对每个候选，把文件偏移列出来（前 12 个）
w("=== B) 各候选值的出现位置（前 12 个，看是否成组出现=指纹表）===")
for v in sorted(cnt):
    needle = struct.pack("<I", v)
    offs = []
    i = dll.find(needle)
    while i != -1 and len(offs) < 12:
        offs.append(i)
        i = dll.find(needle, i + 1)
    # 判断落在 .text(code) 还是 .rdata(data)：粗略用是否落在已知数据区
    w("  0x%08X -> %s" % (v, ["0x%X" % o for o in offs]))
w("")

# ---------- C) 找"三个 0x1Dxxxxxx 挨在一起"的指纹三元组 ----------
w("=== C) 相邻出现、疑似 {ts, size, marker} 三元组的 32 位序列 ===")
hits = []
for i in range(0, len(dll) - 12, 4):
    a, b, c = struct.unpack_from("<3I", dll, i)
    img = [x for x in (a, b, c) if 0x1C000000 <= x < 0x1E000000]
    if len(img) >= 1:
        # 三元组里至少一个像镜像大小，且另外两个是"像时间戳或小标记"的值
        others = [x for x in (a, b, c) if x not in img]
        if all(x == 0 or x < 0x10000000 or 0x50000000 < x < 0x80000000 for x in others):
            hits.append((i, a, b, c))
w("  命中 %d 处：" % len(hits))
for i, a, b, c in hits[:60]:
    w("    0x%06X : 0x%08X 0x%08X 0x%08X" % (i, a, b, c))

open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("done")
