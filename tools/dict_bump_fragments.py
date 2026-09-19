"""词库头部文档 + 版本标记更新（2026-09-18，配合「可组合片段」机制上线）。

做两件事：
  1. version 标记 `2026-09-17e` → `2026-09-18a`（本次内容：新增可组合片段通道）；
  2. 头部「匹配规则」补上第三通道与命中顺序 —— 这个头部是**唯一源**里唯一的规则说明，
     改动匹配语义就必须同步它，否则下一个人（或下一任 agent）会照着旧规则理解代码。

断言（写盘前）：条目数不变、无 CR、无 BOM、头部两条目标文本各命中一次。
"""
import io
import os

REPO = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private"
PATH = os.path.join(REPO, r"translate\translate_zh.txt")

OLD_VERSION = "# version: 2026-09-17e"
NEW_VERSION = "# version: 2026-09-18a"

OLD_RULE = "#   - 精确条目永远先于模板；模板之间「'*' 更少」的先试"
NEW_RULE = (
    "#   - 键以 '~' 开头 = 可组合片段：只有标记过的条目才允许在更长的片段*内部*被替换（第三通道）\n"
    "#   - 命中顺序：精确条目 → 模板（'*' 更少者先试）→ 片段（键更长者先试）\n"
    "#   - 未标记的条目**永远**只在整段相同时命中，所以短词（menu/play/rogue）不会误伤玩家名"
)


def count_entries(text):
    n = 0
    for line in text.split("\n"):
        s = line.strip()
        if not s or s[:1] in ("#", ";") or "=" not in line:
            continue
        n += 1
    return n


raw = io.open(PATH, "rb").read()
assert b"\r" not in raw, "词库必须是 LF：发现 CR"
assert not raw.startswith(b"\xef\xbb\xbf"), "词库必须无 BOM：发现 UTF-8 BOM"

text = raw.decode("utf-8")
assert text.count(OLD_VERSION) == 1, "版本行命中次数不是 1"
assert text.count(OLD_RULE) == 1, "旧规则行命中次数不是 1"

before = count_entries(text)

new_text = text.replace(OLD_VERSION, NEW_VERSION).replace(OLD_RULE, NEW_RULE)

assert count_entries(new_text) == before, "条目数发生了变化（本脚本只应改头部）"
assert new_text.count(NEW_VERSION) == 1
assert b"\r" not in new_text.encode("utf-8")

io.open(PATH, "wb").write(new_text.encode("utf-8"))

print("ok")
print("  version: %s -> %s" % (OLD_VERSION.split(": ")[1], NEW_VERSION.split(": ")[1]))
print("  条目数不变：%d" % before)
print("  文件 %d -> %d 字节" % (len(raw), len(new_text.encode("utf-8"))))
