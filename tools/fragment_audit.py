# -*- coding: utf-8 -*-
r"""片段格式体检（只读）—— 检查所有 `~` 键是否符合"分段翻译"的格式硬约定。

用户诉求 = "分段翻译"（可组合片段）：词库里凡是**游戏原生专名**都该标成 `~` 片段，
这样它出现在任何新组合里都能被自动翻掉，不必一条条补词条。

本脚本只回答**格式层面合不合规**。"该标的有没有标"由 fragment_candidates.py 用采集证据回答
（它扫"未命中、但内部含某精确键"的采集串 —— A 段为空就说明采集上不存在漏标）。

检查项：
  1. 片段键 < 3 字节        ERROR —— 解析器按 kMinFragmentKey 直接丢弃，等于死条目
  2. 片段值里含 '*'         ERROR —— '*' 是模板语法，写在片段值里会破坏语义
  3. 片段键含大写字母        WARN  —— 键应统一小写（唯一已知例外：verrÜckt/verrückt 那对非 ASCII 键）
  4. 单词型片段（无空格）    WARN  —— 无词边界，可能撞玩家名（juggernog 是有意保留的已知例外）
  5. 片段值剥掉格式标记后仍含 ASCII 字母  WARN —— 可能没翻干净（标记内自带字母属正常，故先剥离）
  6. 片段值含格式标记（^X / $(...) / [{...}]）  INFO —— 需与键的标记序列一致，
     交给 color_check.py（键 vs 采集）与 value_marker_scan.py（值 vs 键）复核

另出一份"多词精确键"清单（含空格、不含 '*'、>=8 字节）：它们是**潜在**片段候选，
但**只有采集证明它在别处被包含时才该升格**（见 fragment_candidates.py A 段 / skill 的片段硬约定）。

只读：绝不改词库。用法：python tools\fragment_audit.py
"""

import os
import re

DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\fragment_audit.txt"

MIN_FRAGMENT_BYTES = 3   # 与 translate.cpp 的 kMinFragmentKey 对齐
SUSPECT_BYTES = 8        # 与 dict_verify.py 的片段审计门槛对齐

MARK_RE = re.compile(rb"\^.| \$\([^)]*\)|\$\([^)]*\)|\[\{[^}]*\}\]|\^[A-Za-z]")


def strip_marks(value: bytes) -> bytes:
    """剥掉格式标记，只留下真正会显示出来的字符。"""
    return MARK_RE.sub(b"", value)


def lower_bytes(b: bytes) -> bytes:
    """与引擎 LowerInPlace 同口径：只小写 A-Z，非 ASCII 原样。"""
    return bytes((c + 32) if 65 <= c <= 90 else c for c in b)


def main():
    with open(DICT, "rb") as f:
        raw = f.read()

    exact, templates, fragments = [], [], []
    for line in raw.split(b"\n"):
        if not line or line.startswith(b"#"):
            continue
        if b"=" not in line:
            continue
        key, value = line.split(b"=", 1)
        key = key.rstrip(b"\r")
        value = value.rstrip(b"\r")
        if not key:
            continue
        if key.startswith(b"~"):
            fragments.append((key, value))
        elif b"*" in key:
            templates.append((key, value))
        else:
            exact.append((key, value))

    errors, warnings, infos = [], [], []

    for key, value in fragments:
        body = key[1:]  # 去掉 '~'

        if len(body) < MIN_FRAGMENT_BYTES:
            errors.append("键 < %d 字节（解析器会丢弃）: %s" % (MIN_FRAGMENT_BYTES, key))

        if b"*" in value:
            errors.append("值里含 '*'（片段语法禁忌）: %s=%s" % (key, value))

        if lower_bytes(body) != body:
            warnings.append("键含大写字母（应统一小写）: %s" % key)

        if b" " not in body:
            warnings.append("单词型片段（无词边界，可能撞玩家名）: %s" % key)

        cleaned = strip_marks(value)
        if re.search(rb"[A-Za-z]", cleaned):
            warnings.append("值剥掉标记后仍含 ASCII 字母（可能没翻干净）: %s=%s -> %s"
                            % (key, value, cleaned))

        if MARK_RE.search(value):
            infos.append("值含格式标记（需与键一致，见 color_check / value_marker_scan）: %s=%s"
                         % (key, value))

    # 潜在片段候选：多词、不含 '*'
    multiword_exact = []
    for key, value in exact:
        if b" " in key and len(key) >= SUSPECT_BYTES:
            multiword_exact.append((key, value))

    lines = []
    lines.append("# 片段格式体检（只读报告）")
    lines.append("#")
    lines.append("# 词库: %s" % DICT)
    lines.append("# 规模: %d 精确 + %d 模板 + %d 片段 = %d 条"
                 % (len(exact), len(templates), len(fragments),
                    len(exact) + len(templates) + len(fragments)))
    lines.append("")
    lines.append("## ERROR（必须修）: %d" % len(errors))
    for x in errors:
        lines.append("   %s" % x)
    lines.append("")
    lines.append("## WARN（需人工判断）: %d" % len(warnings))
    for x in warnings:
        lines.append("   %s" % x)
    lines.append("")
    lines.append("## INFO（交给标记类工具复核）: %d" % len(infos))
    for x in infos:
        lines.append("   %s" % x)
    lines.append("")
    lines.append("## 多词精确键（潜在片段候选，共 %d 条）—— 只有采集证明"
                 "它在别处被包含时才升格" % len(multiword_exact))
    for key, value in multiword_exact:
        lines.append("   %s=%s" % (key.decode("utf-8", "replace"),
                                   value.decode("utf-8", "replace")))
    lines.append("")

    with open(OUT, "wb") as f:
        f.write("\n".join(lines).encode("utf-8"))

    print("exact=%d templates=%d fragments=%d"
          % (len(exact), len(templates), len(fragments)))
    print("ERROR=%d WARN=%d INFO=%d multiword_exact=%d"
          % (len(errors), len(warnings), len(infos), len(multiword_exact)))
    print("report: %s" % OUT)


if __name__ == "__main__":
    main()
