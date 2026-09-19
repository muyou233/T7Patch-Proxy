# -*- coding: utf-8 -*-
r"""第三轮增补：dict_triage 的初筛结果，经人工二次确认后写进词库（仓库源）。

规矩沿用 dict_add.py / dict_add2.py：**键一律从 dump 原文取**（needle 只用
"折叠空白 + 小写"定位），要求恰好命中一条；字节级锚点插入，沿用文件原换行。

本轮**人工二次确认**的取舍（工具只当初筛）：
  收：HUD 标签 2 + MOD 击杀播报标签 7 + MOD 选项值 3 + 模板 1 + 地图简介 2
      + 带颜色码 2（工具因含 '^' 被 pool 过滤掉，属漏网，手工加入）
  不收：STOOPID（作者自造的玩笑选项名，属专名）、玩家名/氏族标签、
        usermaps（地图目录名）、Twitter（overlay 链接标签）、
        VS / CDP / ID / black（短 token 堆 / 字体名）、2 条截断句
  暂不收：7 条"武器名: 短语"聊天播报 —— 它们与带颜色码版成对出现，
        而聊天里实际显示的是带颜色码那版（见 dump 2518/2519），
        只加纯文本版等于零可见效果；整对一起加会引入 '^' 键并失去
        "恰好命中一条"的校验，留待下一轮单独处理。
"""
import os
import re

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
REPORT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\dict_add3_report.txt"

raw = open(DUMP, "rb").read()
if raw[:3] == b"\xef\xbb\xbf":
    raw = raw[3:]


def strip_wrap(b):
    i, j = 0, len(b)
    while i < j and b[i] <= 0x20:
        i += 1
    while j > i and b[j - 1] <= 0x20:
        j -= 1
    return b[i:j]


pool = {}
for line in raw.split(b"\n"):
    s = strip_wrap(line.rstrip(b"\r"))
    if not s or any(c >= 0x80 or c < 0x20 for c in s) or any(c in b"^$&" for c in s):
        continue
    txt = s.decode("ascii")
    k = re.sub(r"\s+", " ", txt).strip().lower()
    if txt not in pool.setdefault(k, []):
        pool[k].append(txt)

dict_raw = open(DICT, "rb").read()
EOL = b"\r\n" if b"\r\n" in dict_raw else b"\n"
EOLS = EOL.decode()
have = set()
for line in dict_raw.split(EOL):
    ls = line.lstrip(b" \t")
    if not ls or ls[:1] in (b"#", b";") or b"=" not in ls:
        continue
    have.add(ls.split(b"=", 1)[0].rstrip(b" \t").lower().decode("utf-8", "replace"))

# ---------------------------------------------------------------- 翻译表
HUD = [
    ("ELIMINATIONS", "消灭次数"),
    ("CRITICAL KILLS", "致命击杀次数"),
]

KILLFEED = [
    ("Zombie Elimination", "消灭僵尸"),
    ("Zombie Headshot Kill", "爆头击杀僵尸"),
    ("Zombie Melee Kill", "近战击杀僵尸"),
    ("Zombie Explosive Kill", "爆炸击杀僵尸"),
    ("Weapon Obtained", "获得武器"),
    ("Weapon Shared", "分享武器"),
    ("Perk Acquired", "获得技能"),
]

OPTIONS = [
    ("Less", "更少"),
    ("More", "更多"),
    ("Insane", "疯狂"),
]

MAPS3 = [
    ("Shi No Numa in minecraft style. Have fun!",
     "Minecraft 风格的 Shi No Numa。祝你玩得开心！"),
    ("A minecraft theme map made by Scriptwo !",
     "由 Scriptwo 制作的 Minecraft 主题地图！"),
]

TEMPLATES = [
    ("PING: 10", [("10", "*")], "延迟：*"),
]

# 带颜色码的条目：pool 会把含 '^' 的行整行丢掉，所以手工给，
# 但仍要断言它真的在 dump 里（大小写原样），否则宁可不加。
MANUAL = [
    ("^3Zombie Critical Kill", "^3zombie critical kill", "^3致命击杀僵尸"),
    ("^3Sharpshooter Kill", "^3sharpshooter kill", "^3神射手击杀"),
]

# ---------------------------------------------------------------- 解析
report = []
rendered = {}


def resolve(needle):
    return pool.get(re.sub(r"\s+", " ", needle).strip().lower(), [])


def build(tag, header, table):
    rows = []
    for needle, value in table:
        hits = resolve(needle)
        if len(hits) != 1:
            report.append("!! %s -> 命中 %d 条 %s" % (needle[:60], len(hits), hits[:3]))
            continue
        key = hits[0].lower()
        if key in have:
            report.append("-- %s 已在词库（跳过）" % key)
            continue
        rows.append("%s=%s" % (key, value))
    rendered[tag] = rows
    return ["", header] + rows


tpl_rows = []
for needle, reps, value in TEMPLATES:
    hits = resolve(needle)
    if len(hits) != 1:
        report.append("!! [模板] %s -> 命中 %d 条 %s" % (needle[:60], len(hits), hits[:3]))
        continue
    key = hits[0].lower()
    for old, new in reps:
        if old not in key:
            report.append("!! [模板] %s 里找不到 %r" % (key, old))
        key = key.replace(old, new)
    if key.count("*") != value.count("*"):
        report.append("!! [模板] %s 的 '*' 数(%d) != 译文(%d)"
                      % (key, key.count("*"), value.count("*")))
        continue
    if key in have:
        report.append("-- [模板] %s 已在词库（跳过）" % key)
        continue
    tpl_rows.append("%s=%s" % (key, value))

manual_rows = []
for probe, key, value in MANUAL:
    n = raw.count(probe.encode("ascii"))
    if n < 1:
        report.append("!! [颜色码] dump 里找不到 %r" % probe)
        continue
    if key in have:
        report.append("-- [颜色码] %s 已在词库（跳过）" % key)
        continue
    manual_rows.append("%s=%s" % (key, value))

# ---------------------------------------------------------------- 锚点（都必须唯一）
JOBS = [
    (build("hud", "# ═══ HUD / 记分板标签（续）═══", HUD),
     "# ═══ 状态提示 / 暂停菜单 ═══"),
    (build("killfeed", "# ═══ MOD：击杀播报标签 ═══", KILLFEED)
     + ["", "# 颜色码版（玩家名/武器名在播报里是前缀，这里只收整句标签）"]
     + manual_rows,
     "# ═══ MOD：功能说明（僵尸 / 技能 / 游戏选项的长句）═══"),
    (build("options", "# ═══ MOD：菜单项与选项值（续）═══", OPTIONS),
     "# ═══ MOD：信息页、链接与 FAQ ═══"),
    (build("maps3", "# ═══ MOD：地图列表与兼容性说明（续 2）═══", MAPS3),
     "# ═══ 模板条目（动态数值：等级 / 转生 / 时长 / 命中次数）═══"),
    (["", "# ═══ 模板条目（动态数值）（续 2）═══"] + tpl_rows,
     "# ═══ 格式标记片段（^B 按键绑定 / $() 属性绑定 / [{...}] 令牌）═══"),
]

if report:
    print("有未解析项，**未写盘**：")
    for r in report:
        print("  " + r)
else:
    buf = dict_raw
    ok = True
    for block, anchor in JOBS:
        a = anchor.encode("utf-8")
        n = buf.count(a)
        if n != 1:
            print("锚点不唯一：%s (%d)" % (anchor, n))
            ok = False
            break
        buf = buf.replace(a, (EOLS.join(block) + EOLS).encode("utf-8") + a, 1)
    if ok:
        oldv = "# version: 2026-09-16c"
        if buf.count(oldv.encode()) != 1:
            print("版本行不唯一")
            ok = False
        else:
            buf = buf.replace(oldv.encode(), "# version: 2026-09-16d".encode(), 1)
    if ok:
        open(DICT, "wb").write(buf)
        total = sum(len(v) for v in rendered.values()) + len(tpl_rows) + len(manual_rows)
        print("已写入 %s（%d 字节，EOL=%s，新增 %d 条）" % (DICT, len(buf), EOL, total))

with open(REPORT, "w", encoding="utf-8") as fh:
    fh.write("新增条目：\n")
    for tag in ("hud", "killfeed", "options", "maps3"):
        fh.write("\n### %s (%d)\n%s\n" % (tag, len(rendered.get(tag, [])),
                                          "\n".join(rendered.get(tag, []))))
    fh.write("\n### 颜色码 (%d)\n%s\n" % (len(manual_rows), "\n".join(manual_rows)))
    fh.write("\n### templates (%d)\n%s\n" % (len(tpl_rows), "\n".join(tpl_rows)))
    if report:
        fh.write("\n=== 未解析 ===\n" + "\n".join(report))
print("report:", REPORT)
