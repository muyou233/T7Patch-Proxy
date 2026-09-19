"""给词库加入第一批「可组合片段」（键以 ~ 开头）。

背景（2026-09-18，用户拍板新增机制）：
    匹配顺序 = 精确键 → 模板(*) → 片段(~)。片段是**唯一**允许出现在更长文本里的条目，
    用来让"已知专名 + 新组合"不必逐条重写（例：`Rogue Run: Black Ops 3` →
    `Rogue Run: 黑色行动 3`）。刻意逐条 opt-in：没标记的键永远不会在长文本里替换。

本脚本做的就是三件事：
    1. 把 `black ops 3=黑色行动 3` 从精确条目**删掉**（它将由片段通道覆盖，含整串场景）；
    2. 在文件末尾追加「可组合片段」分节（含 ~black ops iii / ~black ops 3）；
    3. 写盘前断言：精确键集合只少了 black ops 3、片段集合恰好是这两条、无 CR、无 BOM。

⚠️ 词库必须是 UTF-8 无 BOM + LF，本脚本用二进制读写并断言，避免 PowerShell/编辑器
   悄悄改成 CRLF（那会破坏 fgets 行长与运行时对比）。
"""
import io
import os

REPO = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private"
PATH = os.path.join(REPO, r"translate\translate_zh.txt")

# 被片段化的精确条目（键, 整行）
CONVERT_KEY = "black ops 3"
CONVERT_LINE = "black ops 3=黑色行动 3"

SECTION = """# ═══ 可组合片段（键以 ~ 开头；2026-09-18 新增机制）═══
# 匹配顺序：精确键 → 模板(*) → 片段(~)。片段是**唯一**允许出现在更长文本里的条目，
# 用来让"已知专名 + 新组合"不必逐条重写（例：Rogue Run: Black Ops 3 → Rogue Run: 黑色行动 3）。
# ⚠️ 只标记"这个游戏里已有权威译名"的专名（官方中文 > 中文维基/灰机 > B站/社区惯用）。
# ⚠️ 语义有歧义、查不到、或译出来牵强的，**一律不标、也不翻**（见 skill 的歧义译名规则）。
# ⚠️ 单 token / 过短的键不许标（会误伤玩家名与地图名）；解析器硬性丢弃键长 < 3 的片段。
# ⚠️ 片段的值里不要再出现 * —— 那是模板的语法，片段只要"英文=中文"。
~black ops iii=黑色行动 III
~black ops 3=黑色行动 3
"""


def key_of(line):
    """返回该行的键（小写、去首尾空白）；注释/空行/无 '=' 的行返回 None。"""
    if not line.strip() or line.lstrip()[:1] in ("#", ";"):
        return None
    if "=" not in line:
        return None
    return line.split("=", 1)[0].strip().lower()


raw = io.open(PATH, "rb").read()
assert b"\r" not in raw, "词库必须是 LF：发现 CR"
assert not raw.startswith(b"\xef\xbb\xbf"), "词库必须无 BOM：发现 UTF-8 BOM"

text = raw.decode("utf-8")
lines = text.split("\n")

before = {key_of(l): l for l in lines if key_of(l)}
assert CONVERT_KEY in before, "预期精确条目 %s 存在" % CONVERT_KEY

# ---- 1) 删掉将被片段化的精确条目 ------------------------------------------
kept, removed = [], []
for line in lines:
    if key_of(line) == CONVERT_KEY:
        removed.append(line)
        continue
    kept.append(line)
assert removed == [CONVERT_LINE], "预期只删掉一行且内容一致，实际: %r" % (removed,)

# ---- 2) 追加片段分节 ------------------------------------------------------
new_text = "\n".join(kept).rstrip("\n") + "\n\n" + SECTION

# ---- 3) 写盘前的断言 ------------------------------------------------------
after, frags = {}, {}
for line in new_text.split("\n"):
    k = key_of(line)
    if k is None:
        continue
    if k.startswith("~"):
        frags[k[1:].lstrip(" \t")] = line
    else:
        after[k] = line

assert set(after) == set(before) - {CONVERT_KEY}, (
    "精确键集合变化超出预期: 多=%r 少=%r"
    % (sorted(set(after) - set(before)), sorted(set(before) - {CONVERT_KEY} - set(after)))
)
assert set(frags) == {"black ops 3", "black ops iii"}, "片段集合不对: %r" % sorted(frags)
assert not any(len(f) < 3 for f in frags), "存在过短的片段键"

io.open(PATH, "wb").write(new_text.encode("utf-8"))

print("ok")
print("  精确条目 %d -> %d" % (len(before), len(after)))
print("  片段 %d 条: %s" % (len(frags), sorted(frags)))
print("  文件 %d -> %d 字节" % (len(raw), len(new_text.encode("utf-8"))))
