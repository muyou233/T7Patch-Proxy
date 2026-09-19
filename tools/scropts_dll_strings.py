# -*- coding: utf-8 -*-
# Read-only string survey of the Scropts QOL v3.2.4 release DLL.
# We are looking for evidence of how it supports more than one game build:
# build detection, an offset table, a signature scan, or a "not supported" path.
# The DLL is NOT executed; we only read bytes.
import re, struct, os

DLL = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\Scropts.QOL.v3.2.4.dll"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\scropts_dll_strings.txt"

data = open(DLL, "rb").read()
lines = []
def w(s=""):
    lines.append(s)

w("size = %d (%.1f MB)" % (len(data), len(data) / 1048576.0))

# PE basics
e = struct.unpack_from("<I", data, 0x3C)[0]
assert data[e:e + 4] == b"PE\0\0"
coff = e + 4
nsec, = struct.unpack_from("<H", data, coff + 2)
optsize, = struct.unpack_from("<H", data, coff + 16)
opt = coff + 20
size_of_image, = struct.unpack_from("<I", data, opt + 56)
w("SizeOfImage = 0x%X  sections = %d" % (size_of_image, nsec))
secs = []
so = opt + optsize
for i in range(nsec):
    off = so + i * 40
    name = data[off:off + 8].rstrip(b"\0").decode("latin1")
    vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, off + 8)
    secs.append((name, vaddr, vsize, rawptr, rawsize))
    w("  %-8s VA=0x%08X VSize=0x%08X Raw=0x%08X RawSize=0x%08X" % (name, vaddr, vsize, rawptr, rawsize))

# whole-file ASCII strings
ascii_re = re.compile(rb"[\x20-\x7E]{5,}")
strings = [m.group().decode("latin1") for m in ascii_re.finditer(data)]
w("")
w("ASCII strings >= 5 chars: %d" % len(strings))

KEY = re.compile(r"version|build|old|legacy|steam|exe|offset|scan|pattern|signature|sigscan"
                 r"|detect|unsupported|support|downgrade|update|mismatch|module|image"
                 r"|crc|patch|hook|adjust|reloc|variant|compat|new|sept",
                 re.I)

w("")
w("--- 命中关键词的字符串（去重，最多 200 条）---")
seen = set()
n = 0
for s in strings:
    if KEY.search(s) and s not in seen:
        seen.add(s)
        n += 1
        if n <= 200:
            w("  " + s)
w("  (共 %d 条不同命中)" % n)

# UTF-16 strings (UI 文案常见)
w("")
w("--- UTF-16LE 里命中关键词的字符串 ---")
u16 = re.compile(rb"(?:[\x20-\x7E]\x00){5,}")
n = 0
seen = set()
for m in u16.finditer(data):
    s = m.group().decode("utf-16-le")
    if KEY.search(s) and s not in seen:
        seen.add(s)
        n += 1
        if n <= 120:
            w("  " + s)
w("  (共 %d 条不同命中)" % n)

# 找出可能的 build/版本常量：形如 0.1.0.0 或 2026 的数字串
w("")
w("--- 类似版本号 / 日期 的字符串 ---")
for s in strings:
    if re.search(r"\b\d+\.\d+\.\d+(\.\d+)?\b", s) and len(s) < 80:
        w("  " + s)
    elif re.search(r"20\d\d[-/.]\d\d?[-/.]\d\d?", s) and len(s) < 80:
        w("  " + s)

# 是否引用其它模块
w("")
w("--- 导入的模块名 ---")
for name, vaddr, vsize, rawptr, rawsize in secs:
    if "idata" in name.lower():
        blob = data[rawptr:rawptr + rawsize]
        for m in re.finditer(rb"[A-Za-z0-9_\-\.]{4,}\.(?:dll|exe)", blob):
            w("  " + m.group().decode("latin1"))

open(OUT, "w", encoding="utf-8", errors="replace").write("\n".join(lines))
print("done")
