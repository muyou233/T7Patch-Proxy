# -*- coding: utf-8 -*-
r"""读出 PE 的 Machine 字段：x64 应该是 0x8664，x86 是 0x14C。

`ERROR_BAD_EXE_FORMAT (193)` + "不是有效的 Win32 应用程序" 最常见的原因
就是把 32 位的 DLL 放进 64 位进程的目录里。
"""
import io
import os
import struct

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\probe_machine.txt"

TARGETS = [
    ("d3d11.dll（我们的代理）", os.path.join(GAME, "d3d11.dll")),
    ("d3d11_backend.dll（DXVK）", os.path.join(GAME, "d3d11_backend.dll")),
    ("dxgi.dll（DXVK）", os.path.join(GAME, "dxgi.dll")),
    ("BlackOps3.exe（游戏本体）", os.path.join(GAME, "BlackOps3.exe")),
    ("steam_api64.dll（对照）", os.path.join(GAME, "steam_api64.dll")),
]

MACHINE = {
    0x014C: "x86  (32 位)  <<< 放进 64 位游戏 = 必然失败",
    0x8664: "x64  (64 位)  OK",
    0x0200: "IA64",
    0xAA64: "ARM64",
}


def describe(path):
    data = io.open(path, "rb").read(0x400)
    if data[:2] != b"MZ":
        return "不是 PE 文件"
    e = struct.unpack_from("<I", data, 0x3C)[0]
    if data[e:e + 4] != b"PE\0\0":
        return "DOS 头有、PE 头坏（可能被截断/加密）"
    machine = struct.unpack_from("<H", data, e + 4)[0]
    magic = struct.unpack_from("<H", data, e + 24)[0]
    return "Machine=0x%04X  %s | OptionalMagic=0x%03X" % (
        machine, MACHINE.get(machine, "未知"), magic)


lines = []
for label, path in TARGETS:
    if not os.path.exists(path):
        lines.append("%-30s (不存在)" % label)
        continue
    lines.append("%-30s %s  [%d bytes]" % (label, describe(path), os.path.getsize(path)))

lines.append("")
lines.append("判读：如果 DXVK 两个文件是 x86 而游戏/我们的是 x64，")
lines.append("      那 DXVK 从来就没被加载过 —— 也解释了为什么帧数毫无变化。")
io.open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
