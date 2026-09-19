"""列出 ui_dump.txt 里「还没进词库」的干净候选串（只读）。

筛选规则（都是为了让候选项能原样写进 translate_zh.txt）：
  - 去掉首尾 < 0x20 的包装字节（游戏 UI 串的前后控制符）
  - 中间含控制字节 / 含非 ASCII 的整条丢弃（键没法原样表示）
  - 含 ^ (颜色码) 或 $ (绑定) 或 & (格式位) 的丢弃
  - 词库键按小写比较（translate.cpp 把 key LowerInPlace 后存表）
"""
import os

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
DICT = os.path.join(GAME, r"T7Patch\translate_zh.txt")
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\dict_missing.txt"


def read_lines(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    return raw.split(b"\n")


def strip_wrap(b):
    """裁掉首尾的控制字节**和空格** —— 运行时的 NextRun 就是这么做的（两侧都裁），
    旧版采集器只裁控制字节，会把带行尾空格的串误报成"词库没有"。"""
    i, j = 0, len(b)
    while i < j and b[i] <= 0x20:
        i += 1
    while j > i and b[j - 1] <= 0x20:
        j -= 1
    return b[i:j]


# --- 词库已有的键 ---
keys = set()
for line in read_lines(DICT):
    s = line.lstrip(b" \t")
    if not s or s[:1] in (b"#", b";"):
        continue
    if b"=" not in s:
        continue
    k = s.split(b"=", 1)[0].rstrip(b" \t\r")
    if k:
        keys.add(k.lower().decode("ascii", "replace"))

# --- 采集到的候选 ---
seen = set()
order = []
skipped = {}
for line in read_lines(DUMP):
    s = strip_wrap(line.rstrip(b"\r"))
    if not s:
        continue
    low = s.lower()
    if low in seen:
        continue
    # 中间控制字节 / 非 ASCII / 特殊标记 => 记下原因后丢弃
    reason = None
    if any(c < 0x20 for c in s):
        reason = "ctrl-in-middle"
    elif any(c >= 0x80 for c in s):
        reason = "non-ascii"
    elif any(c in b"^$&" for c in s):
        reason = "colorcode/binding"
    if reason:
        skipped[reason] = skipped.get(reason, 0) + 1
        continue
    seen.add(low)
    order.append(s.decode("ascii"))

missing = [t for t in order if t.lower() not in keys]
present = [t for t in order if t.lower() in keys]

out = []
out.append("采集唯一串 %d 条；词库已有 %d 条；缺 %d 条；丢弃 %s"
           % (len(order), len(present), len(missing), skipped))
out.append("")
out.append("=== 缺失（按原样列出；空行分隔，供逐条翻译）===")
for t in sorted(missing, key=lambda x: (len(x.split()), -len(x))):
    out.append(t)

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("written", OUT, "missing:", len(missing))
