# -*- coding: utf-8 -*-
r"""列出任意 PE 文件的静态导入模块名。用法: pe_imports3.py <文件> [<文件> ...]"""
import io
import struct
import sys


def imports(path):
    data = io.open(path, "rb").read()
    e = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[e:e + 4] == b"PE\0\0", "not a PE: " + path
    coff = e + 4
    nsec = struct.unpack_from("<H", data, coff + 2)[0]
    opt_size = struct.unpack_from("<H", data, coff + 16)[0]
    magic = struct.unpack_from("<H", data, coff + 20)[0]
    dd_off = coff + 20 + (0x70 if magic == 0x20B else 0x60)
    imp_rva = struct.unpack_from("<I", data, dd_off + 8)[0]

    sec_off = coff + 20 + opt_size
    sections = []
    for i in range(nsec):
        base = sec_off + i * 40
        vsize, va = struct.unpack_from("<II", data, base + 8)
        rawsize, raw = struct.unpack_from("<II", data, base + 16)
        sections.append((va, vsize, raw, rawsize))

    def to_off(rva):
        for va, vsize, raw, rawsize in sections:
            if va <= rva < va + max(vsize, rawsize):
                return raw + (rva - va)
        return None

    names = []
    if imp_rva:
        off = to_off(imp_rva)
        while off:
            entry = data[off:off + 20]
            if len(entry) < 20 or entry == b"\0" * 20:
                break
            name_rva = struct.unpack_from("<I", entry, 12)[0]
            if name_rva:
                noff = to_off(name_rva)
                if noff:
                    end = data.index(b"\0", noff)
                    names.append(data[noff:end].decode("ascii", "replace"))
            off += 20
    return names


for path in sys.argv[1:]:
    print("=== %s" % path)
    try:
        names = imports(path)
    except Exception as exc:                            # noqa: BLE001
        print("    解析失败: %r" % exc)
        continue
    interesting = [n for n in names
                   if not n.lower().startswith(("api-ms-", "ext-ms-"))]
    for n in interesting:
        print("    %s" % n)
    print("    （共 %d 个，其中非 api-ms 的 %d 个）" % (len(names), len(interesting)))
    for probe in ("dxgi.dll", "d3d11.dll", "d3d12.dll"):
        print("    %-12s 静态导入? %s" % (probe, probe.lower() in [x.lower() for x in names]))
