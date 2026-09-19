# -*- coding: utf-8 -*-
r"""把「AAT 弹药类型」从"一种一条"改成"通用后缀片段"（写盘前断言）。

## 问题（用户 2026-09-18 截图：`按住 F 购买 Thunder Wall Ammo Mod`）
词库里 AAT 是**整块写死**的：
    ~blast furnace ammo mod=Blast Furnace 弹药模组
    ~dead wire ammo mod=Dead Wire 弹药模组
⇒ 每出一个新 AAT（采集里已经有 Thunder Wall，还可能有 Turned / Fireworks / …）就得再加一条，
正是用户说的"每一个长句都单独翻译"。而且 AAT 专名按现行规则**保留原文**（值里就是英文原名 + 中文后缀），
所以真正需要翻译的只有 `Ammo Mod` 这个后缀 —— 它才是该被片段化的部分。

## 解法：一条通用后缀片段
    ~ammo mod=弹药模组
X 的位置由原文原样保留 ⇒ `Thunder Wall Ammo Mod` → `Thunder Wall 弹药模组`，
以后**任何**新 AAT 自动成立，不必再动词库。

## 等价性
旧的两条给出 `Blast Furnace 弹药模组` / `Dead Wire 弹药模组`；
新片段是子串替换，只动 `Ammo Mod` 那一段 ⇒ 输出**逐字相同**（由 match_sim 前后 diff 证明）。
"""

import os
import shutil

DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
BACKUP = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\translate_zh.before-ammomod.txt"

OLD_KEYS = ["~blast furnace ammo mod", "~dead wire ammo mod"]
NEW_LINE = "~ammo mod=弹药模组"


def main():
    with open(DICT, "rb") as f:
        text = f.read().decode("utf-8")
    lines = text.split("\n")

    # ---- 断言 1：两条旧片段各存在且唯一 ----
    for key in OLD_KEYS:
        hit = [i for i, ln in enumerate(lines) if ln.startswith(key + "=")]
        if len(hit) != 1:
            raise SystemExit("FATAL: %s 命中 %d 行（应为 1）" % (key, len(hit)))

    # ---- 断言 2：新片段键不存在 ----
    newkey = NEW_LINE.split("=", 1)[0]
    if any(ln.startswith(newkey + "=") for ln in lines):
        raise SystemExit("FATAL: 新片段键已存在 -> %s" % newkey)

    entries_before = sum(1 for ln in lines if ln and not ln.startswith("#") and "=" in ln)

    # ---- 改：第一条位置换成新片段，第二条删除 ----
    out_lines = []
    for ln in lines:
        if ln.startswith(OLD_KEYS[0] + "="):
            out_lines.append(NEW_LINE)
        elif ln.startswith(OLD_KEYS[1] + "="):
            continue
        else:
            out_lines.append(ln)

    out = "\n".join(out_lines)

    # ---- 断言 3：写盘前 ----
    entries_after = sum(1 for ln in out_lines if ln and not ln.startswith("#") and "=" in ln)
    if entries_after != entries_before - 1:
        raise SystemExit("FATAL: 条目数 %d -> %d（期望 -1：两条并一条）"
                         % (entries_before, entries_after))
    if out.count("\n" + NEW_LINE + "\n") != 1:
        raise SystemExit("FATAL: 新片段不是恰好一条")
    for key in OLD_KEYS:
        if out.count("\n" + key + "=") != 0:
            raise SystemExit("FATAL: 旧片段仍在 -> %s" % key)
    if b"\r" in out.encode("utf-8"):
        raise SystemExit("FATAL: 结果含 CR（必须 LF）")

    shutil.copyfile(DICT, BACKUP)
    with open(DICT, "wb") as f:
        f.write(out.encode("utf-8"))

    print("entries: %d -> %d" % (entries_before, entries_after))
    print("added: %s ; removed: %s" % (NEW_LINE, ", ".join(OLD_KEYS)))
    print("backup: %s" % BACKUP)


if __name__ == "__main__":
    main()
