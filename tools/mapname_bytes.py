# -*- coding: utf-8 -*-
"""确认 ^BBUTTON_PURCHASABLE_ICON^ 到底是 0x02 控制字节还是字面 '^B'。
这决定「图名要不要写带前缀的键」——引擎是按控制字节切片段的。
"""
import io

DUMP = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\T7Patch\ui_dump.txt"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\mapname_bytes.txt"

raw = open(DUMP, "rb").read().split(b"\n")
o = []
for i, ln in enumerate(raw, 1):
    if b"BBUTTON" in ln:
        o.append("L%d  len=%d" % (i, len(ln)))
        o.append("   bytes: %s" % " ".join("%02X" % c for c in ln[:46]))
        o.append("   ctrl? : %s" % ("YES <0x20" if any(c < 0x20 for c in ln) else "no"))
        # 用 NextRun 规则切出来的片段
        out, i2, n = [], 0, len(ln)
        while i2 < n:
            while i2 < n and ln[i2] < 0x20:
                i2 += 1
            if i2 >= n:
                break
            j = i2
            while j < n and ln[j] >= 0x20:
                j += 1
            a, b = i2, j
            while a < b and ln[a] == 0x20:
                a += 1
            while b > a and ln[b - 1] == 0x20:
                b -= 1
            if b > a:
                out.append(ln[a:b].decode("ascii", "replace"))
            i2 = j
        o.append("   runs  : %s" % out)
        if len(o) > 40:
            o.append("   ...(截断)")
            break
    if i > 2900:
        break

# 顺便把「大写形态」那几行的字节也看一下，确认它们同样是整串
o.append("")
o.append("=== 大写形态（HUNTED / NUK3TOWN 之类）===")
for i, ln in enumerate(raw, 1):
    t = ln.strip()
    if t in (b"HUNTED", b"NUK3TOWN", b"INFECTION", b"HAVOC"):
        o.append("L%-5d bytes: %s | len=%d" % (i, " ".join("%02X" % c for c in ln[:30]), len(ln)))

with io.open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(o))
print("written", OUT)
