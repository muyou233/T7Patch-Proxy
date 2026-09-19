# -*- coding: utf-8 -*-
r"""修补体检查出的标记 / 覆盖缺口（写盘前断言，先备份）。

体检结论（2026-09-18）：
  A. fragment_candidates  A 段（该升格未升格）= 0  -> 分段翻译机制没有漏标
  B. fragment_audit       ERROR = 0               -> 片段格式全部合规
  C. color_check / value_marker_scan 查出两处真缺陷（本脚本修的就是这两处）：

1) 值缺一组颜色码（value_marker_scan 报"值缺标记 1"）：
   键 hold ^3f^7 to ^3refill weapons, grenades, and field upgrade^7  有 4 个标记
   值 按住 ^3F^7 补满武器、手雷与战地升级                            只有 2 个
   -> 补成 按住 ^3F^7 补满 ^3武器、手雷与战地升级^7（与键一一对应）
   依据：同族模板 `hold ^3f^7 to ^3*^7` 的值写法就是第二段也高亮。

2) 键的标记写死，覆盖不到"无颜色形态"（color_check 报 3 条"标记不一致"）：
   采集里同一组击杀提示**两种形态都有**（带 ^3 与不带 ^3，共 6 行实测），
   词库只收了带 ^3 的 4 条 -> 不带色的 3 条会整条漏翻，补上（值不带颜色，与原文一致）：
     zombie headshot kill / zombie melee kill / zombie explosive kill
   （`zombie critical kill` 的带色版在采集里存在、无颜色形态**不存在**，故意不补 ——
     补了会变成 dict_qa 报的"采集里没出现的键"。）

跑完请接：dict_verify -> value_marker_scan -> color_check -> match_sim -> translate_sync deploy
"""

import os
import shutil

DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
BACKUP = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\translate_zh.before-markerfix.txt"

OLD_LINE = ("hold ^3f^7 to ^3refill weapons, grenades, and field upgrade^7="
            "按住 ^3F^7 补满武器、手雷与战地升级")
NEW_LINE = ("hold ^3f^7 to ^3refill weapons, grenades, and field upgrade^7="
            "按住 ^3F^7 补满 ^3武器、手雷与战地升级^7")

# 原本还想补"无颜色形态"的 3 条击杀提示，**被脚本断言拦下了**：词库 847-849 行早就有
#   zombie headshot kill / zombie melee kill / zombie explosive kill（无颜色版），
# 带 `^3` 的三条在 860-862 ⇒ 两种形态都已覆盖。
# 所以 color_check 报的 3 条"标记不一致"是**误报**（它拿带标记的键去采集里找同名的无标记串，
# 而覆盖那个形态的是另一条键）。故此处保持为空 —— 不要"顺手补"，那会造出重复键。
INSERTS = []


def main():
    with open(DICT, "rb") as f:
        raw = f.read()

    text = raw.decode("utf-8")
    lines = text.split("\n")

    # ---- 断言 1：目标值行存在且唯一 ----
    if text.count(OLD_LINE) != 1:
        raise SystemExit("FATAL: 目标值行出现 %d 次（应为 1 次）" % text.count(OLD_LINE))

    # ---- 断言 2：三条新键都还不存在 ----
    for _, new_line in INSERTS:
        if new_line in text:
            raise SystemExit("FATAL: 新键已存在，别重复插入 -> %s" % new_line)

    # ---- 断言 3：每条锚点都能找到唯一行 ----
    for anchor, _ in INSERTS:
        hits = [i for i, ln in enumerate(lines) if ln.startswith(anchor + "=")]
        if len(hits) != 1:
            raise SystemExit("FATAL: 锚点 %s 命中 %d 行（应为 1 行）" % (anchor, len(hits)))

    entries_before = sum(1 for ln in lines if ln and not ln.startswith("#") and "=" in ln)

    # ---- 改 1：替换值行 ----
    lines = [NEW_LINE if ln == OLD_LINE else ln for ln in lines]

    # ---- 改 2：在各自锚点后插入新键（从后往前插，避免索引漂移）----
    for anchor, new_line in reversed(INSERTS):
        idx = next(i for i, ln in enumerate(lines) if ln.startswith(anchor + "="))
        lines.insert(idx + 1, new_line)

    out = "\n".join(lines).encode("utf-8")

    # ---- 断言 4：写盘前校验条目数 ----
    entries_after = sum(1 for ln in lines if ln and not ln.startswith("#") and "=" in ln)
    if entries_after != entries_before + len(INSERTS):
        raise SystemExit("FATAL: 条目数 %d -> %d，期望 +%d"
                         % (entries_before, entries_after, len(INSERTS)))
    if NEW_LINE not in out.decode("utf-8"):
        raise SystemExit("FATAL: 替换未生效")
    if b"\r" in out:
        raise SystemExit("FATAL: 结果含 CR（必须 LF）")
    if out[:3] == b"\xef\xbb\xbf":
        raise SystemExit("FATAL: 结果带 BOM")

    shutil.copyfile(DICT, BACKUP)
    with open(DICT, "wb") as f:
        f.write(out)

    print("entries: %d -> %d (+%d)" % (entries_before, entries_after, len(INSERTS)))
    print("backup : %s" % BACKUP)


if __name__ == "__main__":
    main()
