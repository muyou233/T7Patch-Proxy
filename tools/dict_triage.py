"""把 ui_dump.txt 里"词库还没有"的串**分桶**，让工作清单只剩真正要翻的那一撮。

背景：dict_diff.py 只回答"有没有"，把 200+ 条平铺出来 —— 里面有玩家名、武器名、
按键名、分辨率、字形测试串，混在一起没法干活。这个脚本按产品策略自动分流：

  已有-精确       键逐字命中词库
  已有-模板       命中词库里的 '*' 模板条目（dict_diff 看不见这层，会误报"缺"）
  按键名/输入提示  ENTER / WHEEL UP / [[{+actionslot 1}]] / 单字母
  数值规格        1920x1080 / 240.000hz / 4132 Kbps / 100% - 1920x1080
  武器名          BO3 武器表（按策略保留原文）
  专有名词        地图 / 歌曲 / 泡泡糖 / 角色名（按策略保留原文）
  疑似玩家名/ID   含数字或 _ [ ] # . 的无空格串、纯数字混合 ID
  界面文本候选 <- **这是要翻的清单**
  待人工过目      单 token、既不在上面任何表里也不是按键 —— 需过一眼

只读；结果落 ref/dict_triage.txt。

维护：新出现的武器 / 泡泡糖 / 歌曲名直接加进下面的表里，别让它们掉进"界面文本候选"。
"""
import os
import re

from dict_lower import dict_lower

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\dict_triage.txt"

# ---------------------------------------------------------------- 人工表
# BO3 武器名（含僵尸彩蛋武器）。产品策略：保留原文，不进词库。
WEAPONS = {
    "olympia", "svg-100", "krm-262", "drakon", "hvk-30", "ripper", "weevil",
    "vesper", "razorback", "ak-74u", "kn-44", "icr-1", "locus", "pharo",
    "m16a1", "ak-12", "hk416", "suomi", "negev", "ump45", "9a-91", "argus",
    "xm-53", "kuda", "m4a1", "mr6", "rk5", "brm", "vmp", "g11", "p90", "mp7",
    "m4", "haymaker 12", "super sass", "205 brecci", "l-car 9", "dmr 14",
    "hg 40", "ots 9", "howa type 89", "m4 sopmod ii", "m16a1 (sf)",
    ".420 ironhide", "48 dredge", "megaton", "bowie knife",
}

# 地图 / 歌曲 / 角色 等专有名词（保留原文）。
# 2026-09-18 移除：泡泡糖 / 强化道具名已按灰机权威中文翻译，不再"保留原文"
#   （stock option / in plain sight / always done swiftly / arms grace / winter's howl /
#     double points / coagulant → 词库「道具 / 泡泡糖名」节，见 ref/dict_add_items.py）。
# 2026-09-18 移除 peek me pookie：它不是泡泡糖，是**玩家昵称**（采集上下文四周全是玩家名）
#   ⇒ 让规则把它归进「疑似玩家名」桶，别再当专有名词挂在这里。
PROPER = {
    # 地图 / 歌曲 / 模式名
    "chinese home", "hardcore group", "end game?",
    # 歌曲 / 地图 / 模式名
    "cybernetic combat", "chasing secrets", "unknown soldier",
    "town reimagined", "in darkness", "damned 3", "i live (electronic)",
    "safehouse", "vengeance", "coagulant", "ignition", "reverose", "psyche",
    "ramses", "brave", "crowea", "jaeger", "gimp", "five", "legacy",
    "modernized", "blackcell", "hypocenter", "bloodhound", "provocation",
    "black ops", "resume carnage",
    # 角色（少女前线战术人形）
    "vepley", "oncent", "ouicho", "liqlxu", "nanako", "shuma_6orath",
}

KEYS = {
    "enter", "space", "shift", "ctrl", "esc", "tab", "f10",
    "right mouse", "left mouse", "wheel up", "wheel down", "move up",
    "move down", "g or middle mouse", "v or mouse 4",
}

# 必须以数字开头 —— 否则 "HK416" / "P90" 这种武器名会被当成数值规格。
NUMERIC = re.compile(r"^[0-9][0-9\sxX%\.\-\:hHzZkKbBpP]*$")
# 带这些标点的串一定是界面文本（Loading: / Esc / B: close / 说明句）
PUNCT = re.compile(r"[:!?|/]")


def read_lines(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    return raw.split(b"\n")


def strip_wrap(b):
    i, j = 0, len(b)
    while i < j and b[i] <= 0x20:
        i += 1
    while j > i and b[j - 1] <= 0x20:
        j -= 1
    return b[i:j]


# ---------------------------------------------------------------- 词库
dict_raw = open(DICT, "rb").read()
exact, patterns, fragments = set(), [], []
for line in dict_raw.split(b"\n"):
    s = line.lstrip(b" \t").rstrip(b"\r")
    if not s or s[:1] in (b"#", b";") or b"=" not in s:
        continue
    # 引擎口径的小写（只动 A-Z，UTF-8 字节原样保留）—— 见 dict_lower.py
    k = dict_lower(s.split(b"=", 1)[0].rstrip(b" \t").decode("utf-8", "replace"))
    if not k:
        continue
    # 2026-09-18：键以 '~' 开头 = 可组合片段（能在更长文本**内部**替换），单独一表 ——
    # 不拆出来的话，`~stock option` 会被当成一个普通精确键，导致 Stock Option 落进工作清单。
    if k.startswith("~"):
        fragments.append(k[1:].lstrip(" \t"))
        continue
    if "*" in k:
        patterns.append(re.compile("^" + re.escape(k).replace(r"\*", ".*") + "$"))
    else:
        exact.add(k)

# ---------------------------------------------------------------- 分桶
buckets = {
    "已有-精确": [],
    "已有-模板": [],
    "已有-片段": [],
    "按键名/输入提示": [],
    "数值规格": [],
    "武器名（保留）": [],
    "专有名词（保留）": [],
    "疑似玩家名/ID（保留）": [],
    "杂项（字形测试串 / URL）": [],
    "界面文本候选 <<< 工作清单": [],
    "待人工过目（单 token）": [],
}
dropped = {}
seen = set()

for line in read_lines(DUMP):
    s = strip_wrap(line.rstrip(b"\r"))
    if not s:
        continue
    low = s.lower()
    if low in seen:
        continue
    if any(c >= 0x80 or c < 0x20 for c in s):
        dropped["非 ASCII/含控制字节"] = dropped.get("非 ASCII/含控制字节", 0) + 1
        continue
    if any(c in b"^$&" for c in s):
        dropped["含格式标记 ^$&（另见 dict_diff2）"] = \
            dropped.get("含格式标记 ^$&（另见 dict_diff2）", 0) + 1
        continue
    seen.add(low)
    txt = s.decode("ascii")
    key = low.decode("ascii")

    if key in exact:
        buckets["已有-精确"].append(txt)
        continue
    if any(p.match(key) for p in patterns):
        buckets["已有-模板"].append(txt)
        continue
    # 片段只要出现在串里就会出中文（周围文字保持原文），所以"包含即算已有"。
    if any(f in key for f in fragments):
        buckets["已有-片段"].append(txt)
        continue

    words = key.split()
    if key.startswith("http") or (len(key) > 4 and len(set(key)) <= 2):
        buckets["杂项（字形测试串 / URL）"].append(txt)
    elif key in KEYS or "mouse" in key or key.startswith("[[{+") or (
            len(key) == 1 and key.isalpha()):
        buckets["按键名/输入提示"].append(txt)
    elif NUMERIC.match(key):
        buckets["数值规格"].append(txt)
    elif key in WEAPONS:
        buckets["武器名（保留）"].append(txt)
    elif key in PROPER or key[:5] in ("[ + ]", "[ - ]"):
        buckets["专有名词（保留）"].append(txt)  # 列表行 "[ + ] 模组名" 也归这里
    elif len(words) > 1 or PUNCT.search(key):
        buckets["界面文本候选 <<< 工作清单"].append(txt)
    elif len(key) >= 4 and txt.isupper() and txt.isalpha():
        buckets["界面文本候选 <<< 工作清单"].append(txt)  # PAUSED / CLOSE 这种纯大写字标签
    elif any(c.isdigit() or c in "_.-[]#" for c in key) or len(key) > 8:
        buckets["疑似玩家名/ID（保留）"].append(txt)
    else:
        buckets["待人工过目（单 token）"].append(txt)

# 多词但明显是人名/ID 的（含数字/下划线，或整串全小写）。
# 判据要躲开句子：首词大写 + 后面有全小写词 = 句子（"Lasts 3 minutes"），留工作清单。
MULTI_ID = re.compile(r"[0-9_\[\]\#\\\.]")
UI = "界面文本候选 <<< 工作清单"
for name in list(buckets[UI]):
    k = name.lower()
    if PUNCT.search(k):
        continue
    words = name.split()
    looks_sentence = name[:1].isupper() and any(w[:1].islower() for w in words if w)
    if looks_sentence or len(words) > 4:
        continue
    # 注意用 name（原大小写）判「整串全小写」—— key 已经被 lower 过了，恒等于自身小写。
    if MULTI_ID.search(k) or name == name.lower():
        buckets[UI].remove(name)
        buckets["疑似玩家名/ID（保留）"].append(name)

# ---------------------------------------------------------------- 报告
total = sum(len(v) for v in buckets.values())
out = []
out.append("词库：%d 条精确键 + %d 条模板" % (len(exact), len(patterns)))
out.append("采集：%d 条唯一串（另有丢弃：%s）" % (total, dropped))
out.append("")
out.append("分类计数（工作清单 = 界面文本候选）：")
for name, items in buckets.items():
    out.append("  %-28s %4d" % (name, len(items)))
out.append("")
for name, items in buckets.items():
    out.append("")
    out.append("=== %s（%d）===" % (name, len(items)))
    for t in sorted(items, key=lambda x: (len(x.split()), -len(x))):
        out.append(t)

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out) + "\n")
print("written %s" % OUT)
for name, items in buckets.items():
    print("  %-28s %4d" % (name, len(items)))
