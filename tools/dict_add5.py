# -*- coding: utf-8 -*-
"""第五轮（§64）：把多人/DLC 地图名入库，并移除 mod=模组。

要点：
 · 键逐字节取自 ui_dump.txt（含 `^BBUTTON_PURCHASABLE_ICON^ ` 前缀那种「整条一个片段」的形态）
 · 大写形态（NUK3TOWN/INFECTION/HAVOC…）不用另加 —— 匹配大小写不敏感，同一个键就吃到
 · `mod=模组` 按用户要求删除：MOD 是 mod 的名字（专属名词），不应被翻成「模组」
"""
import io

DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
DUMP = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\T7Patch\ui_dump.txt"
REPORT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\dict_add5_report.txt"

# 基础图（截图里那一列）—— hunted 词库已有，不重复加
BASE = [
    ("Aquarium", "水族馆"),
    ("Breach", "突破口"),
    ("Combine", "联合体"),
    ("Evac", "撤离点"),
    ("Exodus", "大迁徙"),
    ("Fringe", "边缘地带"),
    ("Havoc", "浩劫"),
    ("Infection", "感染区"),
    ("Metro", "地铁站"),
    ("Redwood", "红杉林"),
    ("Stronghold", "要塞"),
    ("Nuk3town", "核弹镇"),
]
# DLC 图
DLC = [
    ("Rise", "崛起"),
    ("Splash", "水上乐园"),
    ("Skyjacked", "空艇突袭"),
    ("Gauntlet", "试炼场"),
    ("Knockout", "击倒"),
    ("Rift", "裂谷"),
    ("Spire", "尖塔"),
    ("Verge", "临界点"),
    ("Rumble", "轰鸣"),
    ("Berserk", "狂战"),
    ("Cryogen", "低温实验室"),
    ("Empire", "帝国"),
    ("Citadel", "城堡"),
    ("Micro", "微观世界"),
    ("Outlaw", "亡命之徒"),
    ("Rupture", "崩裂"),
]
# 变体图（只有「裸名」形态）
VARIANT = [
    ("Redwood Snow", "红杉林·雪"),
    ("Fringe Nightfall", "边缘地带·夜幕"),
]
MARKER = b"^BBUTTON_PURCHASABLE_ICON^ "

# ── 取 dump 原文，保证键逐字节一致 ──────────────────────────────
dump_lines = open(DUMP, "rb").read().split(b"\n")
exact = {}
for ln in dump_lines:
    b = ln.rstrip(b"\r")
    exact.setdefault(b.lower(), b)


fallback = set()


def dump_bytes(name):
    """取 dump 里该名字的原始字节。裸名不在 dump 里（如 Micro/Outlaw 只出现在带图标前缀的
    商店列表）时，退而从 `^BBUTTON_PURCHASABLE_ICON^ <名>` 那一行剥出后缀 —— 同样是原文。"""
    b = exact.get(name.lower().encode("ascii"))
    if b is None:
        m = exact.get((MARKER.decode("ascii") + name).lower().encode("ascii"))
        assert m is not None, "dump 里找不到 %r" % name
        b = m[len(MARKER):]
        fallback.add(name)
    return b


dump_bytes("Aquarium")  # sanity


def already(key, buf):
    return b"\n" + key.encode("ascii") + b"=" in buf

raw = open(DICT, "rb").read()
rep = []

# ── 1) 删除 mod=模组 ─────────────────────────────────────────
bad = b"\nmod=\xe6\xa8\xa1\xe7\xbb\x84\n"
assert raw.count(bad) == 1, "mod=模组 出现 %d 次（期望 1）" % raw.count(bad)
raw = raw.replace(bad, b"\n")
rep.append("[移除] mod=模组   （MOD 保留原文）")
assert b"mod=\xe6\xa8\xa1\xe7\xbb\x84" not in raw

# ── 2) 版本号 f -> g ────────────────────────────────────────
old_v = b"# version: 2026-09-16f"
assert raw.count(old_v) == 1
raw = raw.replace(old_v, b"# version: 2026-09-16g")
rep.append("[版本] 2026-09-16f -> 2026-09-16g")

# ── 3) 裸名段落：插到「僵尸：局内提示与道具说明」之前 ────────────
anchor = b"\n# \xe2\x95\x90\xe2\x95\x90\xe2\x95\x90 \xe5\x83\xb5\xe5\xb0\xb8\xef\xbc\x9a\xe5\xb1\x80\xe5\x86\x85\xe6\x8f\x90\xe7\xa4\xba"
assert raw.count(anchor) == 1, "找不到插入锚点（僵尸：局内提示）"

rows = []
for name, zh in BASE + DLC + VARIANT:
    k = dump_bytes(name).decode("ascii").lower()
    if already(k, raw):
        rep.append("[跳过] %s（词库已有）" % k)
        continue
    rows.append((k, zh))
    rep.append("[裸名] %-22s = %s" % (k, zh))

block = ["", "# ═══ 多人 / DLC 地图名（加载屏同名大写形态由大小写不敏感匹配自动覆盖）═══"]
for k, zh in rows:
    block.append("%s=%s" % (k, zh))
raw = raw.replace(anchor, "\n".join(block).encode("utf-8") + anchor, 1)

# ── 4) 带按键图标前缀的形态：追加到「格式标记片段」段末 ──────────
mk_rows = []
for name, zh in DLC:
    full = MARKER + dump_bytes(name)
    k = full.decode("ascii").lower()
    if already(k, raw):
        rep.append("[跳过] %s（词库已有）" % k)
        continue
    mk_rows.append("%s=%s%s" % (k, MARKER.decode("ascii"), zh))
    rep.append("[前缀] %s = %s %s" % (full.decode("ascii"), MARKER.decode("ascii"), zh))

assert raw.endswith(b"\n")
if mk_rows:
    raw += ("\n# ═══ 地图名（mod 商店列表：名字前带 ^BBUTTON_PURCHASABLE_ICON^ 图标）═══\n"
            + "\n".join(mk_rows) + "\n").encode("utf-8")

io.open(DICT, "wb").write(raw)

rep.append("")
rep.append("总计新增 %d 条（裸名 %d + 前缀 %d），删除 1 条" % (len(rows) + len(mk_rows), len(rows), len(mk_rows)))
if fallback:
    rep.append("裸名取自带前缀行（dump 里没有独立裸名）: %s" % ", ".join(sorted(fallback)))
io.open(REPORT, "w", encoding="utf-8").write("\n".join(rep))
print("done:", len(rows), "plain +", len(mk_rows), "prefixed")
