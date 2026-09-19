# -*- coding: utf-8 -*-
r"""在一个目录的文件里按 UTF-8 字节搜多个字符串（只读）。

用途：查游戏自带语言包（`<游戏>\zone\sc_*.ff` / `*.xpak`，简中）里到底有没有某个词的**官方中文**，
以及英文原名是否以明文存在。比 findstr 可靠：findstr 走控制台代码页（GBK），而游戏文本是 UTF-8
⇒ 中文串在 PowerShell/cmd 下根本传不进去。

用法：python search_bytes.py <目录> <glob> "<串1|串2|...>"
例：  python search_bytes.py "F:\...\zone" "sc_*" "Blast Furnace|高能炉|Thunder Wall"
"""

import glob
import os
import sys


def main():
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    root, pattern, joined = sys.argv[1], sys.argv[2], sys.argv[3]
    needles = [(s, s.encode("utf-8")) for s in joined.split("|") if s]

    files = [f for f in sorted(glob.glob(os.path.join(root, pattern))) if os.path.isfile(f)]
    print("scanning %d file(s) in %s for %d needle(s)" % (len(files), root, len(needles)))
    hits = 0
    for path in files:
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            print("  skip %s (%s)" % (os.path.basename(path), e))
            continue
        for text, nb in needles:
            n = data.count(nb)
            if n:
                hits += 1
                at = data.find(nb)
                print("  HIT  %-28s %-18s x%-3d first@0x%X" %
                      (os.path.basename(path), text, n, at))
    if not hits:
        print("  (no plain-text hit - the file is likely compressed, or the term is absent)")


if __name__ == "__main__":
    main()
