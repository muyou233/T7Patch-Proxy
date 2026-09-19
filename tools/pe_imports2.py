# -*- coding: utf-8 -*-
r"""列出某个 DLL 的静态导入（LoadLibrary 失败最常见的原因 = 某个被导入的模块找不到）。

只读 PE 头，不加载目标文件。
"""
import io
import os
import struct

TARGETS = [
    (r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\d3d11_backend.dll", "DXVK 的 d3d11（收编后）"),
    (r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\d3d11.dll", "我们的代理"),
    (r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\dxgi.dll", "DXVK 的 dxgi"),
]
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\pe_imports2.txt"


def rva_to_off(sections, rva):
    for va, vsize, raw, rawsize in sections:
        if va <= rva < va + max(vsize, rawsize):
            return raw + (rva - va)
    return None


def imports(path):
    data = io.open(path, "rb").read()
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[e_lfanew:e_lfanew + 4] == b"PE\0\0", "not a PE"
    coff = e_lfanew + 4
    nsec = struct.unpack_from("<H", data, coff + 2)[0]
    opt_size = struct.unpack_from("<H", data, coff + 16)[0]
    magic = struct.unpack_from("<H", data, coff + 20)[0]
    expected = 0x20B if magic == 0x20B else 0x10B
    assert magic == expected, "unexpected optional header magic"
    dd_off = coff + 20 + (0x70 if magic == 0x20B else 0x60)
    imp_rva, imp_size = struct.unpack_from("<II", data, dd_off + 8)

    sec_off = coff + 20 + opt_size
    sections = []
    for i in range(nsec):
        base = sec_off + i * 40
        vsize, va = struct.unpack_from("<II", data, base + 8)
        rawsize, raw = struct.unpack_from("<II", data, base + 16)
        sections.append((va, vsize, raw, rawsize))

    names = []
    if imp_rva:
        off = rva_to_off(sections, imp_rva)
        while off:
            entry = data[off:off + 20]
            if len(entry) < 20 or entry == b"\0" * 20:
                break
            name_rva = struct.unpack_from("<I", entry, 12)[0]
            if name_rva:
                noff = rva_to_off(sections, name_rva)
                if noff:
                    end = data.index(b"\0", noff)
                    names.append(data[noff:end].decode("ascii", "replace"))
            off += 20
    return names, sections


lines = []
for path, label in TARGETS:
    lines.append("=== %s  (%s)" % (label, os.path.basename(path)))
    if not os.path.exists(path):
        lines.append("    (不存在)")
        lines.append("")
        continue
    lines.append("    大小 %d bytes" % os.path.getsize(path))
    try:
        names, _ = imports(path)
    except Exception as exc:                       # noqa: BLE001 - report, never crash
        lines.append("    解析失败: %r" % exc)
        lines.append("")
        continue
    for n in names:
        present = ""
        if not n.lower().startswith(("api-ms-", "ext-ms-")):
            present = "  [系统可见]" if True else ""
        lines.append("      %s" % n)
    lines.append("    共 %d 个导入模块" % len(names))
    lines.append("")

io.open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("written", OUT)
