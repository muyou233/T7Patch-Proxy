# -*- coding: utf-8 -*-
# 只读：扫 DXVK 的二进制里有没有内嵌许可证文本 / 作者署名。
# 意义：zlib 许可要求"不得移除许可声明"。如果 dll 自带，那"分发 dll"本身就合规；
#       如果没带，打包时就必须额外附一个 LICENSE 文件。
import io

PATHS = [
    r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\T7Patch\dxvk\d3d11_backend.dll",
    r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\T7Patch\dxvk\dxgi.dll",
]

NEEDLES = [
    b"Rebohle",
    b"as-is",
    b"'as-is'",
    b"Permission is granted",
    b"zlib",
    b"Copyright (c)",
    b"Copyright (C)",
    b"authors be held liable",
    b"must not be misrepresented",
    b"warranty",
]

out = []
for p in PATHS:
    data = io.open(p, "rb").read()
    out.append("=== %s  (%s bytes)" % (p.split("\\")[-1], format(len(data), ",")))
    for n in NEEDLES:
        j = data.find(n)
        flag = "FOUND at 0x%X" % j if j >= 0 else "-"
        line = "  %-28s %s" % (n.decode(), flag)
        if j >= 0:
            chunk = data[max(0, j - 40): j + 80]
            printable = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
            line += "\n      %s" % printable
        out.append(line)
    out.append("")

io.open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\dxvk_license_probe.txt",
        "w", encoding="utf-8").write("\n".join(out))
print("written")
