r"""核对：Minecraft Shi No Numa 这张图是不是真的「覆盖了官方字体槽」。

背景：官方文档说字体是通过 zone 里的 `ttf,fonts/xxx.ttf` 覆盖的，槽位名固定
（default / escom / FoundryGridnik-Medium / FoundryGridnik-Bold /
RefrigeratorDeluxe-Regular / wearetrippinshort）。
如果这张图的 fastfile / xpak 里出现这些名字，就证明它走的是同一条官方机制
（而不是自创玩法），那么"往里塞一个带中文的 ttf"就是同一条路上的事。

⚠️ 已知：BO3 的 fastfile 是压缩/加密的，**扫不到不代表没有**。
只读，不写任何游戏文件。
"""
import os

D = r"F:\SteamLibrary\steamapps\workshop\content\311210\3141747077"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\mapfont_scan.txt"

NEEDLES = [b"fonts/", b".ttf", b"default.ttf", b"escom", b"FoundryGridnik",
           b"RefrigeratorDeluxe", b"wearetrippinshort", b"localizedstrings",
           b"font", b"minecraft"]

SAMPLE = 48


def scan(path):
    size = os.path.getsize(path)
    counts = {n: 0 for n in NEEDLES}
    samples = {n: [] for n in NEEDLES}
    tail = b""
    with open(path, "rb") as f:
        while True:
            chunk = f.read(8 * 1024 * 1024)
            if not chunk:
                break
            buf = tail + chunk
            for n in NEEDLES:
                if len(samples[n]) < 3:
                    idx = buf.find(n)
                    if idx >= 0:
                        seg = buf[max(0, idx - 8):idx + SAMPLE]
                        samples[n].append(seg)
                counts[n] += buf.count(n)
            tail = buf[-SAMPLE:]
    return size, counts, samples


def main():
    lines = ["地图字体槽核对（只读）：%s" % D, ""]
    for name in sorted(os.listdir(D)):
        if not (name.endswith(".ff") or name.endswith(".xpak")):
            continue
        full = os.path.join(D, name)
        size, counts, samples = scan(full)
        hit = {k.decode(): v for k, v in counts.items() if v}
        lines.append("== %s  %d B (%.1f MB)" % (name, size, size / 1048576.0))
        if not hit:
            lines.append("   （无命中 —— 压缩/加密，或确实没有）")
        else:
            for k, v in sorted(hit.items(), key=lambda x: -x[1]):
                lines.append("   [%d] %s" % (v, k))
                for s in samples[k.encode()]:
                    txt = "".join(chr(c) if 32 <= c < 127 else "." for c in s)
                    lines.append("        ...%s..." % txt)
        lines.append("")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("done")


main()
