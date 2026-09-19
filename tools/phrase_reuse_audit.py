# -*- coding: utf-8 -*-
r"""可复用性审计：长句里"还没做成片段"的重复短语（只读）。

## 用户策略（2026-09-18）
"为了避免每一个长句都单独翻译，尽量优先采用片段翻译，并且可复用性。"

⇒ 判断标准落在这里：**一条长句里，凡是"在别处也重复出现"的固定文字，都应该先有片段**，
这样新句子（mod 出新图、出新道具）只需要"拼"出来，不必整句重翻。

本脚本的算法与运行时一致：
  对每条**精确条目**的键，从位置 0 开始**贪心**吃掉已知片段（键长从长到短，与 translate.cpp 的
  ComposeFragments 同口径）；吃不掉的部分就是"裸文本"。把所有条目的裸文本收集起来统计重复次数 ——
  **出现 >= 2 次的裸文本 = 高价值片段候选**（它每出现一次，就意味着有一条长句在重复劳动）。

另外标注：该裸文本**在词库里是否已有一条同名精确条目** ⇒ 是的话，把它升格成片段即可
（注意 `~x` 与 `x` 不能并存，`dict_verify` 会报重复键 ⇒ 升格 = 删精确、加片段）。

只读，不改词库。
"""

import os
import re
from collections import Counter, defaultdict

DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\phrase_reuse_audit.txt"

MIN_BARE = 6      # 裸文本短于此没有复用价值
MIN_COUNT = 2     # 至少出现两次才算"重复"


def lower(b: bytes) -> bytes:
    return bytes((c + 32) if 65 <= c <= 90 else c for c in b)


def split_bare(key: bytes, frags) -> list:
    """把 key 里被已知片段覆盖的部分剔掉，返回剩下的裸文本段。"""
    out, i, n = [], 0, len(key)
    while i < n:
        hit = None
        for f in frags:                       # frags 已按长度降序
            if key.startswith(f, i):
                hit = f
                break
        if hit:
            i += len(hit)
            continue
        j = i
        while j < n:
            if any(key.startswith(f, j) for f in frags):
                break
            j += 1
        if j == i:
            j += 1                            # 保险：绝不粘住
        out.append(key[i:j])
        i = j
    return out


def main():
    exact, fragments = [], []
    with open(DICT, "rb") as f:
        for line in f.read().split(b"\n"):
            if not line or line.startswith(b"#") or b"=" not in line:
                continue
            key = line.split(b"=", 1)[0].rstrip(b"\r")
            if not key:
                continue
            if key.startswith(b"~"):
                fragments.append(key[1:])
            elif b"*" not in key:
                exact.append(key)

    frags = sorted(fragments, key=len, reverse=True)
    exact_keys = set(lower(k) for k in exact)

    bare = Counter()
    owners = defaultdict(list)
    for key in exact:
        low = lower(key)
        for seg in split_bare(low, frags):
            seg = seg.strip()
            if len(seg) < MIN_BARE or not re.search(rb"[A-Za-z]", seg):
                continue
            bare[seg] += 1
            if len(owners[seg]) < 4:
                owners[seg].append(key.decode("utf-8", "replace"))

    cands = [(s, n) for s, n in bare.items() if n >= MIN_COUNT]
    cands.sort(key=lambda x: (-x[1], x[0]))

    lines = ["# 可复用性审计：长句里还没做成片段的重复短语（只读）", "#",
             "# 词库：%d 精确条目（不含模板） / %d 片段" % (len(exact), len(fragments)), "#",
             "# 判断：把每条精确键用现有片段贪心剥离，剩下的裸文本若在 >=%d 条长句里重复出现，"
             "就是高价值的片段候选" % MIN_COUNT, ""]
    for seg, n in cands:
        tag = "【词库里已有同名精确条目 ⇒ 可直接升格】" if lower(seg) in exact_keys else ""
        lines.append("  出现 %2d 次 %s  %s" % (n, seg.decode("utf-8", "replace"), tag))
        for ex in owners[seg]:
            lines.append("       例：%s" % ex)
    lines.append("")
    lines.append("（候选共 %d 个；出现 1 次的裸文本 %d 种未列出 —— 单次出现没有复用价值）"
                 % (len(cands), sum(1 for _, n in bare.items() if n == 1)))

    with open(OUT, "wb") as f:
        f.write("\n".join(lines).encode("utf-8"))

    print("exact=%d fragments=%d bare_distinct=%d candidates(>=%d)=%d"
          % (len(exact), len(fragments), len(bare), MIN_COUNT, len(cands)))
    print("report: %s" % OUT)


if __name__ == "__main__":
    main()
