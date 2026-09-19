"""把 `hold ^3f^7 for ...` 这一族从「一句一条」合并成「片段规则」。

为什么必须这么改（用户 2026-09-18 要求「拆分合并，不要一句一句的」）：
  词库里有两条模板 `hold ^3f^7 for ^3*^7` / `hold ^3f^7 for *`，它们的 `*` **原样填回**
  ⇒ 道具名永远保持英文；而 `~名字` 片段因为「模板优先于片段」永远轮不到 ⇒ 只能逐条写精确条目。
  改法 = 删掉那两条模板，改用**片段**表达同一件事：
      ~hold ^3f^7 for =按住 ^3F^7 购买      （固定部分，长键，安全）
      ~juggernog=厚血蛋酒                    （名字，可被任何句子复用）
  片段是单遍左到右、最长键先试 ⇒ 前缀先被吃掉，后面的名字片段在同一次扫描里继续命中
  ⇒ `Hold ^3F^7 for ^3Juggernog^7` 得到和原来**完全相同**的译文。

本脚本只做**等价替换**，不改任何译文用词；安全网三层：
  ① **同名条目**（同一名字两条、译文不同）⇒ 不给它建片段、也不删它（片段复现不了两者）；
  ② 每个被删条目的名字必须有片段（新建的或本来就有的），否则保留；
  ③ 写盘前断言「删除数 == 计划数」，写盘后由 match_sim.py 逐条比对（除改进外不得有变化）。
"""
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DICT = os.path.join(REPO, "translate", "translate_zh.txt")

EXACT = re.compile(r"^hold \^3f\^7 for \^3(.+?)\^7=(按住 \^3F\^7 购买 \^3(.+?)\^7)$")
SHADOW = (
    "hold ^3f^7 for ^3*^7=按住 ^3F^7 购买 ^3*^7",
    "hold ^3f^7 for *=按住 ^3F^7 购买 *",
)
PREFIX = "~hold ^3f^7 for =按住 ^3F^7 购买 "
FRAG = re.compile(r"^~(.+?)=(.*)$")


def main():
    with open(DICT, "r", encoding="utf-8", newline="\n") as fp:
        lines = fp.read().split("\n")

    existing = {}
    for ln in lines:
        m = FRAG.match(ln.lstrip())
        if m:
            existing[m.group(1).strip().lower()] = m.group(2)

    # 名字 -> [(行号, 译名)]；同名多条全部记下来
    by_name = {}
    for i, ln in enumerate(lines):
        m = EXACT.match(ln.strip())
        if not m:
            continue
        # ⚠️ 模板 `hold ^3f^7 for ^3*^7=...` 也会被上面那条正则匹配到（"名字"就是 `*`）——
        #    它必须是"要删掉的遮蔽模板"，绝不能变成 `~*=*` 这种垃圾片段。
        if "*" in m.group(1) or "*" in m.group(3):
            continue
        by_name.setdefault(m.group(1).lower(), []).append((i, m.group(3)))

    dup = {n: v for n, v in by_name.items() if len(v) > 1}
    for n, v in dup.items():
        print("  [同名] %s 共 %d 条: %s" % (n, len(v), sorted({t for _, t in v})))

    new_frags, canonical = [], {}
    for name, entries in sorted(by_name.items()):
        trans = sorted({t for _, t in entries})
        if name in existing:
            canonical[name] = existing[name]          # 已有片段为准
        elif len(trans) == 1:
            canonical[name] = trans[0]
            new_frags.append("~%s=%s" % (name, trans[0]))
        else:
            print("  [跳过] %s 的译文不唯一（%s）⇒ 不建片段、条目保留" % (name, trans))

    removable = set()
    for name, entries in by_name.items():
        if name not in canonical:
            continue
        want = "按住 ^3F^7 购买 ^3%s^7" % canonical[name]
        for i, _t in entries:
            if lines[i].strip().split("=", 1)[1] == want:
                removable.add(i)
            else:
                print("  [保留] 行 %d 的译法与片段不一致: %s" % (i + 1, lines[i].strip()))

    shadow_idx = {i for i, ln in enumerate(lines) if ln.strip() in SHADOW}
    assert len(shadow_idx) == 2, "遮蔽模板应 2 条，实际 %d" % len(shadow_idx)

    out = []
    for i, ln in enumerate(lines):
        if i in shadow_idx or i in removable:
            continue
        out.append(ln)

    # ⚠️ 断言必须在**插入新片段之前**：插入会让 len(out) 变大，之后再加断言就是自己骗自己。
    assert len(lines) - len(out) == len(shadow_idx | removable), "删除行数与计划不符"

    at = max(i for i, ln in enumerate(out) if ln.startswith("hold ^3f^7"))
    block = ["# 2026-09-18：这一族从「一句一条」合并为片段规则（用户要求「拆分合并，不要一句一句的」）。",
             "# 固定部分一条长片段吃掉前缀，名字各一条片段 ⇒ 名字在任何句子里都能翻，新组合不必再加条目。",
             "# 等价性由 match_sim.py 逐条比对（改动前后除改进外不得有差异）。",
             PREFIX] + new_frags
    out[at + 1:at + 1] = block

    with open(DICT, "w", encoding="utf-8", newline="\n") as fp:
        fp.write("\n".join(out))

    print("新增名字片段 %d；删除精确条目 %d；删除遮蔽模板 %d；总行数 %d -> %d"
          % (len(new_frags), len(removable), len(shadow_idx), len(lines), len(out)))
    for f in new_frags:
        print("  + " + f)


if __name__ == "__main__":
    main()
