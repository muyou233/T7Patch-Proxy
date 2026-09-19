# -*- coding: utf-8 -*-
r"""把 `hold ^3f^7 to …` 族从模板合并为片段，并加入 `~aether shroud`（写盘前断言）。

## 为什么必须一起做（用户诉求："Aether Shroud 翻成中文"）
`Hold ^3F^7 to pick up ^3Aether Shroud^7` 命中的是**模板** `hold ^3f^7 to pick up ^3*^7`，
而匹配顺序是「精确 → 模板 → 片段」⇒ **模板命中后就不再走片段通道**（见 translate.cpp 说明与
文件里 1160-1163 行的注释）⇒ 只加一条 `~aether shroud` 是**永远不会生效**的。

## 做法（与 1177 行 `~hold ^3f^7 for ` 同款，用户 2026-09-18 要求"拆分合并、不要一句一句的"）
把三条 `to` 模板换成等价的**前缀片段**：固定部分吃掉前缀，名字交给各自的片段/精确条目
⇒ 以后任何新名字（`Cursed Relic` / `Random LMG` / …）都不必再加条目。

等价性：模板值里的 `*` 会把捕获原文原样填回，而片段方案里"名字若无条目"也会原样留在输出中
⇒ 对**没有条目**的名字两者输出逐字节相同；对**有条目**的名字，片段方案会顺手翻掉它（= 改进）。
改前/改后必须用 `match_sim.py` 对比，**不允许出现"改前能翻、改后丢失"**。

跑完接：dict_verify -> match_sim(与基线 diff) -> translate_sync deploy
"""

import os
import shutil

DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
BACKUP = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\translate_zh.before-tofamily.txt"

REPLACE = [
    # (旧模板行, 新片段行)
    ("hold ^3f^7 to pick up ^3*^7=按住 ^3F^7 拾取 ^3*^7",
     "~hold ^3f^7 to pick up ^3=按住 ^3F^7 拾取 ^3"),
    ("hold ^3f^7 to ^3*^7=按住 ^3F^7 使用 ^3*^7",
     "~hold ^3f^7 to ^3=按住 ^3F^7 使用 ^3"),
    ("hold ^3f^7 to *=按住 ^3F^7 使用 *",
     "~hold ^3f^7 to =按住 ^3F^7 使用 "),
]

INSERT_AFTER = "~phd flopper=飞扑专家"
INSERT_LINES = [
    "# 2026-09-18（用户要求翻）：Aether Shroud = 《黑色行动冷战》的战场升级，本 mod 借用了这个名字",
    "# （BO3 本体没有它）⇒ 取社区最通行的「以太披风」（贴吧/抖音一致；另有「以太隐匿」「以太护罩」，",
    "#  各作品官方口径并未统一）。放在这里是因为它由 `~hold ^3f^7 to pick up ^3` 片段在句内组合出来。",
    "~aether shroud=以太披风",
]


def main():
    with open(DICT, "rb") as f:
        raw = f.read()
    text = raw.decode("utf-8")
    lines = text.split("\n")

    # ---- 断言 1：三条旧模板各出现且仅出现一次 ----
    for old, _ in REPLACE:
        if text.count(old) != 1:
            raise SystemExit("FATAL: 旧行出现 %d 次（应为 1）-> %s" % (text.count(old), old))

    # ---- 断言 2：新片段键都还不存在（避免撞已有的） ----
    for _, new in REPLACE:
        key = new.split("=", 1)[0]
        if any(ln.startswith(key + "=") for ln in lines):
            raise SystemExit("FATAL: 新片段键已存在 -> %s" % key)
    newkeys = []
    for new in [r[1] for r in REPLACE] + [INSERT_LINES[-1]]:
        newkeys.append(new.split("=", 1)[0])

    # ---- 断言 3：插入锚点唯一 ----
    if sum(1 for ln in lines if ln == INSERT_AFTER) != 1:
        raise SystemExit("FATAL: 插入锚点不唯一 -> %s" % INSERT_AFTER)

    entries_before = sum(1 for ln in lines if ln and not ln.startswith("#") and "=" in ln)

    # ---- 改 1：模板 -> 片段 ----
    lines = [dict(REPLACE).get(ln, ln) for ln in lines]

    # ---- 改 2：插入 Aether Shroud 片段（含说明注释） ----
    at = lines.index(INSERT_AFTER)
    lines[at + 1:at + 1] = INSERT_LINES

    out = "\n".join(lines)

    # ---- 断言 4：写盘前 ----
    entries_after = sum(1 for ln in lines if ln and not ln.startswith("#") and "=" in ln)
    if entries_after != entries_before + 1:
        raise SystemExit("FATAL: 条目数 %d -> %d（期望 +1：三条替换不增减，只多 Aether Shroud）"
                         % (entries_before, entries_after))
    for _, new in REPLACE:
        if new not in out:
            raise SystemExit("FATAL: 替换未生效 -> %s" % new)
    for k in newkeys:
        if out.count("\n" + k + "=") != 1:
            raise SystemExit("FATAL: 新键出现次数不为 1 -> %s" % k)
    if b"\r" in out.encode("utf-8"):
        raise SystemExit("FATAL: 结果含 CR（必须 LF）")

    shutil.copyfile(DICT, BACKUP)
    with open(DICT, "wb") as f:
        f.write(out.encode("utf-8"))

    print("entries: %d -> %d" % (entries_before, entries_after))
    print("new fragments: %s" % ", ".join(newkeys))
    print("backup: %s" % BACKUP)


if __name__ == "__main__":
    main()
