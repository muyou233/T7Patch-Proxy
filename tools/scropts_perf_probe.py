# -*- coding: utf-8 -*-
# 目的：v3.2.4 发布 DLL 里除了 README 之外，还有没有"性能/FPS"相关的实现或文案
import re

DLL = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\Scropts.QOL.v3.2.4.dll"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\scropts_perf_probe.txt"
dll = open(DLL, "rb").read()
L = []

def w(s=""):
    L.append(s)

w("=== 1) ASCII 关键词直查（大小写不敏感）===")
KEYS = [b"stutter", b"fps", b"lag", b"hitch", b"frame", b"freeze", b"performance",
        b"IsRenderingImmediately", b"dlc", b"BIsSubscribed", b"BIsDlcInstalled",
        b"appCache", b"dlcCache", b"Menu Stutter", b"scan"]
low = dll.lower()
for k in KEYS:
    n = low.count(k.lower())
    offs = []
    i = low.find(k.lower())
    while i != -1 and len(offs) < 5:
        offs.append(i)
        i = low.find(k.lower(), i + 1)
    w("  %-22s 命中 %-4d %s" % (k.decode("latin-1"), n, ["0x%X" % o for o in offs]))
w("")

w("=== 2) 含关键词的人读串（从 DLL 里抽出完整可打印串）===")
def strings(data, minlen=8):
    out = []
    cur = bytearray()
    start = 0
    for i, b in enumerate(data):
        if 32 <= b < 127:
            if not cur:
                start = i
            cur.append(b)
        else:
            if len(cur) >= minlen:
                out.append((start, cur.decode("latin-1")))
            cur = bytearray()
    if len(cur) >= minlen:
        out.append((start, cur.decode("latin-1")))
    return out

WANT = ("stutter", "fps", "lag", "hitch", "frame", "freeze", "performance", "dlc", "install", "subscribe")
hits = 0
for off, s in strings(dll, 8):
    ls = s.lower()
    if any(k in ls for k in WANT):
        hits += 1
        if hits <= 60:
            w("  0x%06X  %s" % (off, s[:150]))
w("  （相关串共 %d 条，上面最多列 60 条）" % hits)
w("")

w("=== 3) 我们关注的那两个槽位在 DLL 里有没有痕迹（+48/+56 立即数不易识别，退一步看 Steam 接口字符串）===")
for k in (b"SteamApps", b"STEAMAPPS_INTERFACE_VERSION", b"ISteamApps", b"steam_api"):
    i = dll.find(k)
    w("  %-30s %s" % (k.decode(), ("0x%X" % i) if i != -1 else "未找到"))

open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("done")
