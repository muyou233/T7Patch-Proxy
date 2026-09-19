# -*- coding: utf-8 -*-
"""exact_gap.py - 找出"被模板吃掉、但捕获部分仍是英文"的 run（= 翻了一半）。

为什么需要它（2026-09-18 踩到的工具盲区）：
    dict_triage.py 把**被模板命中的 run** 归进「已有-模板」桶 ⇒ 它们**从不进入工作清单**。
    于是 `Hold ^3F^7 for ^3<PHD Flopper>^7` 这类"框架已翻、名字仍英文"的串，
    在两轮"补完"之后仍然照旧在游戏里露英文（用户连续截图追问才暴露）。

它做什么：
    读 ui_dump.txt + translate_zh.txt。对每条**没有精确键**的采集 run，
    用词库的模板键（`*` 通配）整条试匹配；命中即"模板吃掉了它"，
    再检查**捕获到的文本是否仍含拉丁字母且不含中文** —— 是则报出来（这才是真缺陷）。
    只读，不写游戏目录；报告落 ref/exact_gap.txt。

    近似引擎的模板顺序（`*` 少者优先，其次文件书写顺序）。
    权威模拟仍是 match_sim.py；本脚本的目标是"发现"，宁可多报不可漏报。
"""

import os
import re
import sys

# 控制台是 GBK 时，报告里的 ⇒ / → 这类字符会让 print() 抛 UnicodeEncodeError
# （报告文件本身已按 UTF-8 写好，所以只影响回显）。降级而不是崩。
try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
HERE = os.path.dirname(os.path.abspath(__file__))
DICT = os.path.join(HERE, "..", "..", "translate", "translate_zh.txt")
OUT = os.path.join(HERE, "exact_gap.txt")

MIN_CAPTURE = 2   # 捕获片段太短（单字符）不值得报，噪声大


def read_lines(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return [ln.rstrip("\r\n") for ln in fh]


def load_dict(path):
    exact = set()
    templates = []
    for ln in read_lines(path):
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        key = ln.split("=", 1)[0].strip()
        if not key or key.startswith("~"):
            continue
        low = key.lower()
        if "*" in low:
            templates.append(low)
        else:
            exact.add(low)
    return exact, templates


def has_cjk(s):
    return any("\u4e00" <= ch <= "\u9fff" for ch in s)


def looks_english(s):
    """捕获文本里还有拉丁字母、且一个中文字都没有 ⇒ 判定为"还没翻"。"""
    return (not has_cjk(s)) and any(("a" <= ch.lower() <= "z") for ch in s)


def main():
    exact, templates = load_dict(DICT)
    patterns = []
    for key in sorted(set(templates), key=lambda k: (k.count("*"),)):
        body = "".join("(.*)" if ch == "*" else re.escape(ch) for ch in key)
        patterns.append((key, re.compile("^" + body + "$")))

    runs = []
    seen = set()
    for ln in read_lines(DUMP):
        s = ln.strip()
        low = s.lower()
        if s and low not in seen:
            seen.add(low)
            runs.append(s)

    hits = []
    for run in runs:
        low = run.lower()
        if low in exact:
            continue
        for key, rx in patterns:
            m = rx.match(low)
            if not m:
                continue
            leftover = [g for g in m.groups() if g and len(g) >= MIN_CAPTURE and looks_english(g)]
            if leftover:
                hits.append((run, key, leftover))
            break

    lines = []
    lines.append("exact_gap：被模板吃掉、捕获部分仍是英文的 run（= 只翻了一半）")
    lines.append("采集 %s" % DUMP)
    lines.append("  去重 run %d 条；词库精确键 %d 条 / 模板 %d 条" % (len(runs), len(exact), len(patterns)))
    lines.append("")
    if not hits:
        lines.append("（无：当前没有被模板吃掉且残留英文的 run）")
    for run, key, leftover in hits:
        lines.append("  run      %s" % run)
        lines.append("    模板   %s" % key)
        lines.append("    仍英文 %s" % " | ".join(leftover))
    lines.append("")
    lines.append("合计 %d 条。这些串**不会**出现在 dict_triage 的工作清单里 ⇒ 必须来这里看。" % len(hits))
    lines.append("读法：多为「框架已翻 + 专名未翻」⇒ 要么补精确条目（首选，精确优先于模板），")
    lines.append("      要么把专名做成 `~` 片段**并**确认它不会被模板抢先吃掉（模板命中后不再走片段）。")
    lines.append("注意：少数条目**故意**保留英文（玩家名 / 地图名 / 武器名模板），需人工判读。")

    text = "\n".join(lines) + "\n"
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
