r"""侦察：BO3 主程序里跟「字体光栅化」有关的外部 API / 库名（只读，不修改任何文件）。

为什么查这个：官方文档说 BO3 的字体是 **真 .ttf**（zone 里写 `ttf,fonts/xxx.ttf`）。
如果程序是通过某个可 hook 的 API 把 ttf 交给光栅化器（GDI 的 AddFontMemResourceEx /
FreeType 的 FT_New_Memory_Face），那补丁侧「把缺中文的字体换成带中文的」就只需要一个挂钩点；
如果是自研光栅化器，成本要高一个量级。

注意：游戏 exe 的 .text 是磁盘加密的（Arxan），所以「找不到」**不能**证明没有，
只能证明这些串没出现在明文段里。报告里会写清楚这一点。
"""
import os
import re

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\fontapi_scan.txt"

NEEDLES = [
    b"AddFontMemResourceEx",  # GDI: 从内存装字体
    b"AddFontResourceEx",     # GDI: 从文件装字体
    b"CreateFontIndirect",    # GDI: 建字体对象
    b"GetGlyphOutline",       # GDI: 取字形轮廓（光栅化核心）
    b"gdi32", b"user32", b"dwrite", b"DWriteCreateFactory",
    b"freetype", b"FreeType", b"FT_New_Memory_Face", b"FT_New_Face",
    b"FT_Load_Glyph", b"FT_Init_FreeType", b"FT_Get_Char_Index",
    b"stb_truetype", b"stbtt_", b"harfbuzz", b"hb_font",
    b".ttf", b".otf",
]


def scan(path, label):
    lines = []
    size = os.path.getsize(path)
    lines.append("== %s  %d B (%.1f MB) ==" % (label, size, size / 1048576.0))
    counts = {n: 0 for n in NEEDLES}
    overlap = 64
    with open(path, "rb") as f:
        tail = b""
        while True:
            chunk = f.read(4 * 1024 * 1024)
            if not chunk:
                break
            buf = tail + chunk
            for n in NEEDLES:
                counts[n] += buf.count(n)
            tail = buf[-overlap:]
    for n in NEEDLES:
        if counts[n]:
            lines.append("   [hits %d] %s" % (counts[n], n.decode("ascii", "replace")))
    missing = [n.decode("ascii", "replace") for n in NEEDLES if not counts[n]]
    lines.append("   未命中: %s" % (", ".join(missing) if missing else "(无)"))
    return lines


def main():
    out = []
    out.append("BO3 字体光栅化 API 侦察（只读）")
    out.append("说明：.text 磁盘加密 ⇒ 未命中不代表不存在，只代表没出现在明文段。")
    out.append("")
    found = []
    for name in sorted(os.listdir(GAME)):
        if name.lower().endswith(".exe"):
            found.append(name)
    out.append("游戏目录下的 exe：%s" % ", ".join(found) if found else "（没找到 exe）")
    out.append("")
    for name in found:
        # 只扫主程序，mod tools 的 exe 不在这个目录
        out += scan(os.path.join(GAME, name), name)
        out.append("")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("\n".join(out))


main()
