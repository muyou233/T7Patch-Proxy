r"""枚举 MC 地图 xpak 末端的资产表，找「字体类资产」。

上一版正则写错了：真实分隔符是 **换行 0x0A**，不是点。真实格式（已用 hex 验证）：
    format: BC7_SRGB\nsemantic: diffuseMap\ninitial: none\nname: i_minecraft_xxx_c\ntype: image\n...
而且这张表在**文件末尾**（1.19 GB 处），不在开头，所以小窗口扫不到。

要回答的问题：这张图有没有打包装 **字体（type: font / ttf）** 资产，
以及有没有命中官方那几个字体槽名（default / escom / FoundryGridnik / RefrigeratorDeluxe /
wearetrippinshort）。只读。
"""
import os
import re

D = r"F:\SteamLibrary\steamapps\workshop\content\311210\3141747077"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\mapasset_scan.txt"

PAIR = re.compile(rb"name: ([ -~]{1,90}?)\ntype: ([a-z0-9_]{1,24})")
SLOTS = ("default", "escom", "foundrygridnik", "refrigeratordeluxe", "wearetrippinshort")


def main():
    type_count = {}
    fontish = set()
    slotish = set()
    for name in sorted(os.listdir(D)):
        if not (name.endswith(".xpak") or name.endswith(".ff")):
            continue
        path = os.path.join(D, name)
        if os.path.getsize(path) < 1024 * 1024:
            continue
        tail = b""
        with open(path, "rb") as f:
            while True:
                chunk = f.read(32 * 1024 * 1024)
                if not chunk:
                    break
                buf = tail + chunk
                for m in PAIR.finditer(buf):
                    aname = m.group(1).decode("ascii", "replace").strip()
                    atype = m.group(2).decode("ascii", "replace")
                    type_count[atype] = type_count.get(atype, 0) + 1
                    low = aname.lower()
                    if "font" in atype or "font" in low or "ttf" in atype or "ttf" in low:
                        fontish.add("%s  [type=%s]" % (aname, atype))
                    if any(s in low for s in SLOTS):
                        slotish.add("%s  [type=%s]" % (aname, atype))
                tail = buf[-200:]

    lines = ["MC 地图资产表侦察 v2（只读；已修正分隔符为换行，且只扫 >1MB 的 .ff/.xpak）", ""]
    lines.append("== 资产类型统计（全部，共 %d 种） ==" % len(type_count))
    for t, c in sorted(type_count.items(), key=lambda x: -x[1]):
        lines.append("   %-30s %d" % (t, c))
    lines.append("")
    lines.append("== 名字或类型带 font/ttf 的资产（%d） ==" % len(fontish))
    for s in sorted(fontish)[:100]:
        lines.append("   " + s)
    lines.append("")
    lines.append("== 命中官方字体槽名的资产（%d） ==" % len(slotish))
    for s in sorted(slotish)[:100]:
        lines.append("   " + s)
    lines.append("")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("done types=%d fontish=%d slotish=%d" % (len(type_count), len(fontish), len(slotish)))


main()
