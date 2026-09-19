# -*- coding: utf-8 -*-
r"""方括号说明的缺口体检（只读）。

## 背景
功能性 mod 的购买提示是 `Hold ^3F^7 for <名字> [^3<效果说明>^7]` 这种形态，**说明装在方括号里**。
采集里它有两种出现方式：
  ① 独立成一个 run：`[^3Zombies Deal Double Damage (2-Hit Down with Juggernog) - Increases Reward Luck^7]`
  ② 跟在交互提示后面（同一条 run）：`Hold ^3F^7 for Cursed Relic [^3Zombies Speed 2x Faster - Increases Reward Luck^7]`

形态 ② 里，词库里那条"前缀+名字"的精确条目（`hold ^3f^7 for cursed relic=…`）**长度对不上** ⇒ 不会命中，
实际走的是片段组合（`~hold ^3f^7 for` + `~cursed relic`）⇒ **方括号块里若没有自己的条目就整块显示英文**
（用户 2026-09-18 截图 `按住 F 购买 诅咒遗物 [Zombies Speed 2x Faster - Increases Reward Luck]` 正是如此）。

本脚本把采集里**所有**方括号块抠出来，逐块查词库精确键，报出"没有条目"的块
⇒ 一次补全，不必等用户一张张截图。

只读：不改词库、不改采集。用法：python tools\bracket_gap.py
"""

import os
import re
from collections import Counter

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\bracket_gap.txt"

BLOCK = re.compile(rb"\[[^\[\]]*\]")
MIN_BLOCK = 12          # 太短的块多半是 [L] / [Cost: 250] 这类，跳过


def lower(b: bytes) -> bytes:
    """与引擎 LowerInPlace 同口径：只小写 A-Z。"""
    return bytes((c + 32) if 65 <= c <= 90 else c for c in b)


def trim(b: bytes) -> bytes:
    """两端剥掉 <= 0x20 的字节（与运行时 NextRun 的口径对齐）。"""
    a, z = 0, len(b)
    while a < z and b[a] <= 0x20:
        a += 1
    while z > a and b[z - 1] <= 0x20:
        z -= 1
    return b[a:z]


def main():
    keys = set()
    with open(DICT, "rb") as f:
        for line in f.read().split(b"\n"):
            if not line or line.startswith(b"#") or b"=" not in line:
                continue
            key = line.split(b"=", 1)[0].rstrip(b"\r")
            if key and not key.startswith(b"~"):
                keys.add(lower(key))

    blocks = Counter()
    samples = {}
    with open(DUMP, "rb") as f:
        for raw in f.read().split(b"\n"):
            run = trim(raw)
            if not run:
                continue
            for m in BLOCK.finditer(run):
                blk = m.group(0)
                if len(blk) < MIN_BLOCK:
                    continue
                if not re.search(rb"[A-Za-z]", blk):
                    continue
                blocks[blk] += 1
                samples.setdefault(blk, run.decode("utf-8", "replace"))

    missing = [(b, n) for b, n in blocks.items() if lower(b) not in keys]
    missing.sort(key=lambda x: (-x[1], x[0]))

    lines = ["# 方括号说明的缺口（只读报告）", "#",
             "# 词库精确键 %d 个；采集里 >=%d 字节的方括号块 %d 种，其中 %d 种没有条目"
             % (len(keys), MIN_BLOCK, len(blocks), len(missing)), ""]
    for blk, n in missing:
        lines.append("  出现 %2d 次  %s" % (n, blk.decode("utf-8", "replace")))
        lines.append("              例：%s" % samples[blk])
    lines.append("")
    lines.append("# 已有条目的块（供对照，共 %d 种）" % (len(blocks) - len(missing)))
    for blk, n in sorted(blocks.items()):
        if lower(blk) in keys:
            lines.append("  OK  %s" % blk.decode("utf-8", "replace"))
    lines.append("")

    with open(OUT, "wb") as f:
        f.write("\n".join(lines).encode("utf-8"))

    print("blocks=%d with_entry=%d missing=%d"
          % (len(blocks), len(blocks) - len(missing), len(missing)))
    print("report: %s" % OUT)


if __name__ == "__main__":
    main()
