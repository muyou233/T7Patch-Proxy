"""扫描「彩色字符」：BO3 的 UI 文本里 `^X` 到底是什么、有多少、长什么样。

要回答的问题：
  1) `^` 后面到底跟哪些字符（是只有 ^0-^9 还是有字母，如 ^B）？
  2) 采集到的串里有多少条带码？词库里有多少条带码？（= 手工抄码的规模）
  3) 有没有别的格式标记混在里面（$(...) 绑定、[^3X^7] 图标占位符）。
"""
import collections
import io
import os

GAME_DUMP = (r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
             r"\T7Patch\ui_dump.txt")
DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"


def read_lines(path):
    if not os.path.exists(path):
        return []
    with io.open(path, "r", encoding="utf-8", errors="replace", newline="") as fh:
        return [l.rstrip("\r\n") for l in fh]


def caret_stats(lines, label):
    follow = collections.Counter()
    with_code = 0
    total = 0
    samples = []
    for ln in lines:
        body = ln.split("=", 1)[0] if ("=" in ln and not ln.lstrip().startswith("#")) else ln
        if not body.strip():
            continue
        total += 1
        hit = False
        for i, ch in enumerate(body):
            if ch == "^" and i + 1 < len(body):
                follow[body[i + 1]] += 1
                hit = True
        if hit:
            with_code += 1
            if len(samples) < 8:
                samples.append(body)
    out = []
    out.append("【%s】非空行 %d 条，其中含 '^' 的 %d 条" % (label, total, with_code))
    if follow:
        out.append("  '^' 后跟的字符分布：" + "  ".join(
            "%r=%d" % (c, n) for c, n in sorted(follow.items(), key=lambda kv: -kv[1])))
    else:
        out.append("  没有任何 '^'")
    for s in samples:
        out.append("    样本: %s" % s[:100])
    return out


dump = read_lines(GAME_DUMP)
dict_lines = read_lines(DICT)

lines = []
lines.extend(caret_stats(dump, "ui_dump.txt"))
lines.append("")
lines.extend(caret_stats(dict_lines, "translate_zh.txt"))

# 两种衍生格式
lines.append("")
attr = [l for l in dump if "$(" in l]
icon = [l for l in dump if "^3C^7" in l or "^3P^7" in l or "^3N^7" in l]
lines.append("含 '$(...)' 绑定语法的串：%d 条" % len(attr))
for s in attr[:4]:
    lines.append("    %s" % s[:100])
lines.append("含 '[^3X^7]' 图标占位符的串：%d 条" % len(icon))
for s in icon[:4]:
    lines.append("    %s" % s[:100])

# 去重后的干净串总数（用于估"还要抄多少条码"）
clean = set()
for l in dump:
    if l.lstrip().startswith("#") or not l.strip():
        continue
    clean.add(l)
lines.append("")
lines.append("ui_dump.txt：原始 %d 行 / 去重后 %d 条" % (len(dump), len(clean)))
with_code_clean = sum(1 for l in clean if "^" in l)
lines.append("  去重后含 '^' 的：%d 条（%.0f%%）" % (
    with_code_clean, 100.0 * with_code_clean / max(1, len(clean))))

txt = "\n".join(lines)
print(txt)
