# -*- coding: utf-8 -*-
r"""方括号"奖励说明"升格为片段 + 补上缺的一条（写盘前断言）。

## 为什么必须用片段
`bracket_gap.py` 查出：采集里有 18 种方括号块，其中真缺条目的只有 1 种 ——
`[^3Zombies Speed 2x Faster - Increases Reward Luck^7]`（用户 2026-09-18 截图那条）。

它的出现方式是**句内**：`Hold ^3F^7 for Cursed Relic [^3Zombies Speed 2x Faster - Increases Reward Luck^7]`
⇒ **精确条目在这里无效**（精确查找是"整条 run 相等"，而这条 run 带着前面的交互提示），
拼写完全正确的键也命中不了。**片段**是子串匹配，且同样能匹配"整条 run" ⇒ 一条片段覆盖两种场景。

原有的 4 条是精确条目（它们只在"块独立成一个 run"时出现，所以一直能用）。本次一并把
**这 5 条全部改成片段**：行为是既有能力的超集（独立出现照样命中，句内出现新增命中），
且与 `~hold ^3f^7 for` / `~cursed relic` 那套"拆分合并"的做法一致（用户 2026-09-18 的要求）。

⚠️ 不能"精确 + 片段共存"：`dict_verify` 把 `~x` 与 `x` 视作同一命名空间，会当场报重复键。

改前/改后必须用 `match_sim.py` 逐条比对，**不允许出现"改前能翻、改后丢失"**。
"""

import os
import shutil

DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
BACKUP = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\translate_zh.before-bracket.txt"

# 已有 4 条：键前加 `~` 即升格为片段（值一字不改）
PROMOTE = [
    "[^3zombies deal double damage (2-hit down with juggernog) - increases reward luck^7]",
    "[^34 perk limit (perks are replaced when picked up) - increases reward luck^7]",
    "[^3zombies have chance to explode on death - increases reward luck^7]",
    "[^3only 1 weapon allowed. keeps holding weapon - increases reward luck^7]",
]

# 新增的一条（与上面同款；措辞对齐库里既有的 `~power up spawning 2x faster=强力奖励生成快 2 倍`）
NEW_FRAGMENT = ("~[^3zombies speed 2x faster - increases reward luck^7]="
                "[^3僵尸速度变快 2 倍——提升奖励运气^7]")
NEW_ANCHOR = "~[^3zombies have chance to explode on death - increases reward luck^7]"


def main():
    with open(DICT, "rb") as f:
        text = f.read().decode("utf-8")
    lines = text.split("\n")

    # ---- 断言 1：4 条待升格的精确键各存在且唯一 ----
    for key in PROMOTE:
        hit = [i for i, ln in enumerate(lines) if ln.startswith(key + "=")]
        if len(hit) != 1:
            raise SystemExit("FATAL: %s 命中 %d 行（应为 1）" % (key, len(hit)))

    # ---- 断言 2：新片段键不存在（锚点是**升格后**的形态，要等下面升格完才检查）----
    newkey = NEW_FRAGMENT.split("=", 1)[0]
    if any(ln.startswith(newkey + "=") for ln in lines):
        raise SystemExit("FATAL: 新片段键已存在 -> %s" % newkey)

    entries_before = sum(1 for ln in lines if ln and not ln.startswith("#") and "=" in ln)

    # ---- 改 1：升格（键前加 `~`）----
    for i, ln in enumerate(lines):
        for key in PROMOTE:
            if ln.startswith(key + "="):
                lines[i] = "~" + ln

    # ---- 断言 3：锚点此刻才存在，且必须唯一（行是 `键=值`，必须按 `键=` 前缀比）----
    if sum(1 for ln in lines if ln.startswith(NEW_ANCHOR + "=")) != 1:
        raise SystemExit("FATAL: 锚点不唯一 -> %s" % NEW_ANCHOR)

    # ---- 改 2：插入新片段（紧跟同类之后）----
    at = next(i for i, ln in enumerate(lines) if ln.startswith(NEW_ANCHOR + "="))
    lines.insert(at + 1, NEW_FRAGMENT)

    out = "\n".join(lines)

    # ---- 断言 3：写盘前 ----
    entries_after = sum(1 for ln in lines if ln and not ln.startswith("#") and "=" in ln)
    if entries_after != entries_before + 1:
        raise SystemExit("FATAL: 条目数 %d -> %d（期望 +1）" % (entries_before, entries_after))
    for key in PROMOTE:
        if out.count("\n~" + key + "=") != 1:
            raise SystemExit("FATAL: 升格未生效 -> %s" % key)
        if out.count("\n" + key + "=") != 0:
            raise SystemExit("FATAL: 旧的裸键仍在 -> %s" % key)
    if NEW_FRAGMENT not in out:
        raise SystemExit("FATAL: 新片段未写入")
    if b"\r" in out.encode("utf-8"):
        raise SystemExit("FATAL: 结果含 CR（必须 LF）")

    shutil.copyfile(DICT, BACKUP)
    with open(DICT, "wb") as f:
        f.write(out.encode("utf-8"))

    print("entries: %d -> %d" % (entries_before, entries_after))
    print("promoted: %d ; added: 1" % len(PROMOTE))
    print("backup: %s" % BACKUP)


if __name__ == "__main__":
    main()
