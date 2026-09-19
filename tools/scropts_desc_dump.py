# -*- coding: utf-8 -*-
# 目标：看清档案描述符数组 —— build 名串(0x105FF8/0x106008/0x106018)周围的结构
# 以及消息串区(0x10B600~)是否指向同一批描述符
import struct

DLL = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\Scropts.QOL.v3.2.4.dll"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\scropts_desc_dump.txt"
dll = open(DLL, "rb").read()
L = []

def w(s=""):
    L.append(s)

def is_ptr(q):
    return 0x180000000 <= q < 0x180000000 + len(dll) + 0x100000

def ptr_rva(q):
    return q - 0x180000000

def cstr(off, maxlen=64):
    e = dll.find(b"\x00", off)
    if e == -1 or e - off > maxlen:
        e = min(off + maxlen, len(dll))
    return dll[off:e].decode("latin-1", "replace")

def dump(lo, hi, title):
    w("=== %s  0x%X..0x%X ===" % (title, lo, hi))
    for base in range(lo, hi, 8):
        q = struct.unpack_from("<Q", dll, base)[0]
        tag = ""
        if is_ptr(q):
            r = ptr_rva(q)
            if r < len(dll):
                s = cstr(r, 40)
                printable = all(32 <= ord(c) < 127 for c in s) and len(s) >= 3
                tag = " -> 0x%X  \"%s\"" % (r, s if printable else "?")
            else:
                tag = " -> 0x%X (超界)" % r
        elif q == 0:
            tag = " 0"
        else:
            tag = " 0x%X" % q
        w("  0x%06X : %s" % (base, tag))
    w("")

# 1) 三个 build 名串的原始区（含串前后各 0x80）
w("--- build 名串原始字节 ---")
for off in (0x105FF8, 0x106008, 0x106018):
    w("  0x%06X : \"%s\"" % (off, cstr(off, 48)))
w("")

dump(0x105F80, 0x1060A0, "1) build 名串区（前后结构）")
dump(0x10B5C0, 0x10B7C0, "2) 日志/消息串区")
dump(0x10B8C0, 0x10B980, "3) 'does not match a supported build' 区")

# 4) 在整份 DLL 里找"指向 0x105FF8 / 0x106008 / 0x106018"的 qword 引用
w("=== 4) 谁引用了这三个名串 ===")
for target in (0x105FF8, 0x106008, 0x106018):
    needle = struct.pack("<Q", 0x180000000 + target)
    refs = []
    i = dll.find(needle)
    while i != -1:
        refs.append(i)
        i = dll.find(needle, i + 1)
    w("  0x%X 被引用 %d 次：%s" % (target, len(refs), ["0x%X" % r for r in refs[:10]]))

open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("done")
