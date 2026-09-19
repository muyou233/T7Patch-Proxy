r"""侦察第二轮：区分「真的没有」和「串是 UTF-16 所以没扫到」。

第一轮扫 ASCII 时连 `user32` / `gdi32` 都没命中，这很可疑 —— 正常 PE 一定导入 user32。
所以这轮加上 **UTF-16LE** 变体（PE 里 DLL 名/API 名常以宽字符存放）。
判读：
  * UTF-16 能扫到 user32/gdi32 ⇒ PE 明文可读，那「字体 API 没命中」才是有意义的结论；
  * 连 UTF-16 也扫不到 ⇒ 该 exe 的导入表被保护/加密（已知 Arxan），
    **磁盘字符串侦察在这条路上到此为止，别再花时间**。
只读，不改任何文件。
"""
import os

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\fontapi_scan2.txt"

WORDS = [
    "user32", "gdi32", "kernel32", "d3d11", "AddFontMemResourceEx",
    "AddFontResourceEx", "CreateFontIndirect", "GetGlyphOutline",
    "freetype", "FT_New_Memory_Face", "FT_Load_Glyph", "stb_truetype", "hb_font",
    ".ttf", ".otf", "fonts/", "localizedstrings",
]


def variants(w):
    a = w.encode("ascii", "ignore")
    u = w.encode("utf-16-le")
    return (("ascii", a), ("utf16", u))


def main():
    exe = os.path.join(GAME, "BlackOps3.exe")
    size = os.path.getsize(exe)
    counts = {}
    for w in WORDS:
        counts[w] = {"ascii": 0, "utf16": 0}
    tail = b""
    with open(exe, "rb") as f:
        while True:
            chunk = f.read(8 * 1024 * 1024)
            if not chunk:
                break
            buf = tail + chunk
            for w in WORDS:
                for enc, pat in variants(w):
                    counts[w][enc] += buf.count(pat)
            tail = buf[-128:]

    lines = ["BO3 主程序字符串侦察（ASCII + UTF-16LE，只读）",
             "exe = %s  %d B (%.1f MB)" % (exe, size, size / 1048576.0), ""]
    for w in WORDS:
        c = counts[w]
        lines.append("   %-24s ascii=%-6d utf16=%-6d" % (w, c["ascii"], c["utf16"]))
    sane = counts["user32"]["ascii"] + counts["user32"]["utf16"]
    lines.append("")
    if sane:
        lines.append("判读：user32 命中 ⇒ PE 明文可读 ⇒ 字体 API 的全线未命中是有意义的（不是编码问题）。")
    else:
        lines.append("判读：连 user32 都没命中 ⇒ 导入表被保护/加密（已知 Arxan）⇒ "
                     "磁盘字符串侦察在字体这条路上不可用，到此为止。")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


main()
