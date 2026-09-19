r"""取证：BO3 的字体/字形资产存在哪儿、语言包里是不是独立资产。

背景：英文安装下我们把 mod 英文串替换成中文会渲染成透明/口口 => 英文包没有 CJK 字形。
问题：字形是 TTF（可加载系统字体解决）还是烘进 fastfile 的位图资产（必须动资源层）。
做法：在 zone 文件里搜 ASCII 资产名字符串（font / glyph / atlas / .ttf / localiz），
      并统计文件里 CJK 码点（UTF-8 与 UTF-16LE）的出现量，判断语言包里装的是什么。
只读，不写游戏目录。
"""
import os
import re

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
ZONE = os.path.join(GAME, "zone")
REPORT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\zone_font_scan.txt"

TARGETS = [
    "sc_core_frontend.ff",   # 语言包：前端（菜单/设置界面）
    "sc_core_frontend.fd",
    "sc_core_ui.fd",
    "sc_core_common.fd",
    "core_frontend.fd",      # 本体：同 zone，无语言前缀
    "core_ui.fd",
    "core_common.fd",
    "base_core_frontend.ff",
]

NEEDLES = [b"font", b"Font", b".ttf", b".otf", b"glyph", b"Glyph", b"atlas", b"Atlas",
           b"localiz", b"Localiz", b"dds", b"Bitmap"]

out = []
out.append("game  = %s" % GAME)
out.append("")

# --- what the game root / zone layout looks like -----------------------------
out.append("--- game root folders ---")
for name in sorted(os.listdir(GAME)):
    p = os.path.join(GAME, name)
    if os.path.isdir(p):
        out.append("  [dir] %s" % name)
out.append("--- zone subfolders ---")
subs = [d for d in os.listdir(ZONE) if os.path.isdir(os.path.join(ZONE, d))]
out.append("  %s" % (", ".join(sorted(subs)) if subs else "(none - all files are flat here)"))


def cjk_hits(data):
    """Rough counts: CJK codepoints as UTF-8 3-byte seqs and as UTF-16LE pairs."""
    u8 = 0
    i = 0
    n = len(data)
    while i + 2 < n:
        b0, b1, b2 = data[i], data[i + 1], data[i + 2]
        if 0xE0 <= b0 <= 0xEF and 0x80 <= b1 <= 0xBF and 0x80 <= b2 <= 0xBF:
            cp = ((b0 & 0x0F) << 12) | ((b1 & 0x3F) << 6) | (b2 & 0x3F)
            if 0x4E00 <= cp <= 0x9FFF:
                u8 += 1
                i += 3
                continue
        i += 1
    u16 = 0
    i = 0
    while i + 1 < n:
        lo, hi = data[i], data[i + 1]
        cp = lo | (hi << 8)
        if 0x4E00 <= cp <= 0x9FFF:
            u16 += 1
            i += 2
            continue
        i += 1
    return u8, u16


def contexts(data, needle, limit=4, width=48):
    """Printable-ASCII context around up to `limit` hits of `needle`."""
    res = []
    start = 0
    while len(res) < limit:
        idx = data.find(needle, start)
        if idx < 0:
            break
        a = max(0, idx - width // 2)
        b = min(len(data), idx + len(needle) + width)
        chunk = data[a:b]
        txt = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        res.append("      @0x%08X  %s" % (idx, txt))
        start = idx + 1
    return res


out.append("")
for name in TARGETS:
    p = os.path.join(ZONE, name)
    if not os.path.exists(p):
        out.append("== %s : MISSING" % name)
        out.append("")
        continue
    data = open(p, "rb").read()
    u8, u16 = cjk_hits(data)
    out.append("== %s  (%d bytes)  CJK: utf8=%d  utf16le=%d" % (name, len(data), u8, u16))
    for nd in NEEDLES:
        cnt = data.count(nd)
        out.append("   %-10s hits=%-8d" % (nd.decode(), cnt))
        if cnt:
            out.extend(contexts(data, nd))
    out.append("")

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
print("report -> %s" % REPORT)
