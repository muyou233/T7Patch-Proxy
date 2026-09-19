# -*- coding: utf-8 -*-
# 只读：找一个可靠的"DXVK 标记串"，供代理识别游戏目录里的 dxgi.dll 是不是 DXVK 的。
# 关键问题：这个标记在文件里的位置有多靠前？（决定代理只读前 N KB 够不够）
import io

PATHS = [
    r"E:\Download\dxvk-3.1.1\x64\dxgi.dll",
    r"E:\Download\dxvk-3.1.1\x64\d3d11.dll",
]
NEEDLES = [b"DXVK", b"dxvk"]

out = []
for p in PATHS:
    d = io.open(p, "rb").read()
    out.append("=== %s  (%s bytes)" % (p, format(len(d), ",")))
    for n in NEEDLES:
        hits = []
        s = 0
        while len(hits) < 4:
            j = d.find(n, s)
            if j < 0:
                break
            hits.append(j)
            s = j + 1
        out.append("  needle %-6s  found=%d  first offsets: %s"
                   % (n.decode(), len(hits), [hex(x) for x in hits]))
        if hits:
            j = hits[0]
            chunk = d[max(0, j - 48): j + 96]
            printable = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
            out.append("      context: %s" % printable)
    out.append("")

io.open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\dxvk_marker_probe.txt",
        "w", encoding="utf-8").write("\n".join(out))
print("written")
