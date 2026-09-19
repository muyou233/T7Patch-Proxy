# -*- coding: utf-8 -*-
# 1) 读出本机 BlackOps3.exe 的构建指纹（PE TimeDateStamp / SizeOfImage / 文件大小）
# 2) 把我们补丁每个 hook 目标的磁盘前 16 字节打出来，看是否明文
#    —— 明文则说明可以像 Scropts QOL 那样做"改前校验"
import re, struct, os, hashlib

EXE = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\BlackOps3.exe"
SRC = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\src"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\our_build_fingerprint.txt"

data = open(EXE, "rb").read()
lines = []
def w(s=""):
    lines.append(s)

e = struct.unpack_from("<I", data, 0x3C)[0]
coff = e + 4
nsec, = struct.unpack_from("<H", data, coff + 2)
optsize, = struct.unpack_from("<H", data, coff + 16)
timestamp, = struct.unpack_from("<I", data, coff + 8)
opt = coff + 20
size_of_image, = struct.unpack_from("<I", data, opt + 56)
checksum, = struct.unpack_from("<I", data, opt + 64)
secs = []
so = opt + optsize
for i in range(nsec):
    off = so + i * 40
    name = data[off:off + 8].rstrip(b"\0").decode("latin1")
    vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, off + 8)
    secs.append((name, vaddr, vsize, rawptr, rawsize))

w("=== 本机 BlackOps3.exe 构建指纹 ===")
w("file size      = %d (0x%X)" % (len(data), len(data)))
w("sha256         = %s" % hashlib.sha256(data).hexdigest())
w("SizeOfImage    = 0x%08X" % size_of_image)
w("TimeDateStamp  = 0x%08X   (%s UTC)" % (timestamp, __import__("datetime").datetime.utcfromtimestamp(timestamp).isoformat()))
w("CheckSum       = 0x%08X" % checksum)
w("")

def file_off(rva):
    for name, vaddr, vsize, rawptr, rawsize in secs:
        if vaddr <= rva < vaddr + max(vsize, rawsize):
            d = rva - vaddr
            return (rawptr + d) if d < rawsize else None
    return None

rv = re.compile(r"(?:REBASE|OFFSET)\(0x([0-9A-Fa-f]+)\)")
targets = {}
for fn in ("offsets.h", "Hooks.cpp", "offsets.cpp"):
    p = os.path.join(SRC, fn)
    if not os.path.exists(p):
        continue
    txt = open(p, encoding="utf-8", errors="replace").read()
    for m in rv.finditer(txt):
        targets[int(m.group(1), 16)] = fn

w("=== 补丁 hook 目标在磁盘上的前 16 字节（共 %d 个 RVA）===" % len(targets))
w("%-12s %-8s %s" % ("RVA", "明文?", "bytes"))
plain = 0
enc = 0
for rva in sorted(targets):
    fo = file_off(rva)
    if fo is None:
        w("0x%08X   ?        该 RVA 无磁盘数据（.data/.bss 里的变量）" % rva)
        continue
    b = data[fo:fo + 16]
    # 简单熵判据：可打印 + 常见指令字节
    printable = sum(1 for x in b if 0x20 <= x <= 0x7E)
    # 明文布尔：不全是高熵随机（用 0x00/0xFF/常见前缀做粗略判断）
    looks_code = (b[0] in (0x48, 0x4C, 0x40, 0x44, 0x55, 0x53, 0x56, 0x57, 0x41, 0xE9, 0xE8, 0x8B, 0x89, 0x33, 0x83, 0xF3, 0x0F, 0xC3, 0xCC)
                  or b[1] in (0x8B, 0x89, 0x83, 0x33, 0x05, 0x3B))
    flag = "明文" if looks_code else "加密/随机"
    if looks_code:
        plain += 1
    else:
        enc += 1
    w("0x%08X   %-9s %s" % (rva, flag, " ".join("%02X" % x for x in b)))

w("")
w("明文 %d 个 / 加密 %d 个" % (plain, enc))
open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("done")
