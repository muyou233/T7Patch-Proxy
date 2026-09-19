r"""看一眼 xpak 资产表的**真实字节格式**（第一版正则没匹配上，先别猜）。

流式扫整个 xpak，抓前 5 处 "minecraft" 的原始上下文：十六进制 + 可打印映射
（控制字符写成 <XX>）。只读。
"""
import os

D = r"F:\SteamLibrary\steamapps\workshop\content\311210\3141747077"
XP = os.path.join(D, "zm_shinonuma_minecraft.xpak")
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\xpak_sample.txt"


def show(b):
    out = []
    for c in b:
        if 32 <= c < 127:
            out.append(chr(c))
        elif c == 0:
            out.append("\\0")
        else:
            out.append("<%02X>" % c)
    return "".join(out)


def main():
    lines = []
    found = 0
    pos = 0
    tail = b""
    with open(XP, "rb") as f:
        while found < 5:
            chunk = f.read(32 * 1024 * 1024)
            if not chunk:
                break
            buf = tail + chunk
            base = pos - len(tail)
            i = 0
            while found < 5:
                j = buf.find(b"minecraft", i)
                if j < 0:
                    break
                seg = buf[max(0, j - 60):j + 60]
                lines.append("--- 绝对偏移 %d ---" % (base + j))
                lines.append("hex : " + seg.hex())
                lines.append("text: " + show(seg))
                lines.append("")
                i = j + 9
                found += 1
            pos += len(chunk)
            tail = buf[-64:]
    lines.append("命中数（前 5 处已列）=%d" % found)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("done")


main()
