# -*- coding: utf-8 -*-
r"""第四轮增补：MOD 聊天播报（纯文本版 + 颜色码版成对）与带格式标记的交互提示。

这一轮正是 dict_add3.py 里"留待下一轮单独处理"的那件事：dump 里 2518/2519 这种
成对出现的聊天播报 —— 玩家名（G11 / P90）与武器名（KAP-40 / SVU-AS / M1216）
每次都不一样，所以只能写成模板（键里的 '*'），并把玩家名/武器名按"原样填回"处理。

规矩沿用前几轮：
  * 纯文本条目：键从 dump 原文取（needle 用"折叠空白 + 小写"定位），要求恰好命中一条；
  * 含 '^' 的条目：pool 会把整行丢掉（见 dict_triage 的 dropped 计数），所以手工给 probe，
    但**断言它真的在 dump 里逐字节存在**，否则宁可不写；
  * 颜色码条目的模板：probe 取 dump 原文，把玩家名/武器名换成 '*'，并断言被换的片段
    确实出现在该行里（错位就是静默错译）。
  收：3 条击杀勋章颜色码版 + 5 条聊天播报模板（颜色码版）+ 5 条（纯文本版）
      + 17 条交互提示 + 1 条地图简介
  不收：地图名（用户 2026-09-16 明确"这些是地图名字"）、mod 名（All-around Enhancement）、
        玩家名（XDCROAZZY / STOOPID / Ulises Damian Qu / I'm the king of）、
        ^BBUTTON_PURCHASABLE_ICON^ 系列（= 地图名）、$() 属性绑定串（引擎自己替换，不会显示）
"""
import os
import re

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
REPORT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\dict_add4_report.txt"
OLDV = "# version: 2026-09-16d"
NEWV = "# version: 2026-09-16e"

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

report = []
rows = {}


def resolve(needle):
    return pool.get(re.sub(r"\s+", " ", needle).strip().lower(), [])


def add_plain(tag, header, table):
    out = []
    for needle, value in table:
        hits = resolve(needle)
        if len(hits) != 1:
            report.append("!! [%s] %s -> 命中 %d 条 %s" % (tag, needle[:60], len(hits), hits[:3]))
            continue
        key = hits[0].lower()
        if key in have:
            report.append("-- [%s] %s 已在词库（跳过）" % (tag, key))
            continue
        out.append("%s=%s" % (key, value))
    rows[tag] = out
    return ["", header] + out if header else out


def add_manual(tag, probe, key, value):
    """probe = dump 逐字节原文（ASCII）；key 用小写形态写盘。"""
    if raw.count(probe.encode("ascii")) < 1:
        report.append("!! [%s] dump 里找不到 %r" % (tag, probe))
        return None
    if key in have:
        report.append("-- [%s] %s 已在词库（跳过）" % (tag, key))
        return None
    return "%s=%s" % (key, value)


# ------------------------------------------------------------------ 1. 击杀勋章（颜色码版）
MEDALS = [
    ("^3Zombie Headshot Kill", "^3zombie headshot kill", "^3爆头击杀僵尸"),
    ("^3Zombie Melee Kill", "^3zombie melee kill", "^3近战击杀僵尸"),
    ("^3Zombie Explosive Kill", "^3zombie explosive kill", "^3爆炸击杀僵尸"),
]

# ------------------------------------------- 2. 聊天播报：颜色码版（玩家名 / 武器名 → '*'）
# (dump 原文, [(该行里被替换成 '*' 的小写片段, ...)], 译文)
CHAT_COLOUR = [
    ("^7^2G11^7: ^7I'm downed!^7", ["g11"], "^7^2*^7: ^7我倒了！^7"),
    ("^7^2P90^7: ^7I'm downed!^7", ["p90"], "^7^2*^7: ^7我倒了！^7"),
    ("^7^2G11^7: ^7KABOOM!^7", ["g11"], "^7^2*^7: ^7轰！！！^7"),
    ("^7^2G11^7: ^7I got a new perk.^7", ["g11"], "^7^2*^7: ^7我买到一个新技能。^7"),
    ("^7^2P90^7: ^7I got the^7 ^7KAP-40^7.^7", ["p90", "kap-40"],
     "^7^2*^7: ^7我捡到了^7 ^7*^7。^7"),
    ("^7^2G11^7: ^7I got the^7 ^7SVU-AS^7.^7", ["g11", "svu-as"],
     "^7^2*^7: ^7我捡到了^7 ^7*^7。^7"),
    ("^7^2P90^7: ^7I shared a^7 ^7M1216^7 ^7here^7.^7", ["p90", "m1216"],
     "^7^2*^7: ^7我在这里分享了^7 ^7*^7。^7"),
    ("^7^2G11^7: ^7I shared a^7 ^7KAP-40^7 ^7here^7.^7", ["g11", "kap-40"],
     "^7^2*^7: ^7我在这里分享了^7 ^7*^7。^7"),
]

# ------------------------------------------------ 3. 聊天播报：纯文本版（同一批消息）
CHAT_PLAIN = [
    ("G11: I'm downed!", "*: i'm downed!", "*：我倒了！"),
    ("G11: KABOOM!", "*: kaboom!", "*：轰！！！"),
    ("G11: I got a new perk.", "*: i got a new perk.", "*：我买到一个新技能。"),
    ("P90: I got the KAP-40.", "*: i got the *.", "*：我捡到了 *。"),
    ("G11: I shared a KAP-40 here.", "*: i shared a * here.", "*：我在这里分享了 *。"),
]

# ------------------------------------------------ 4. 交互提示（带 ^3F^7 按键标记）
PROMPTS = [
    ("Hold ^3F^7 for Tombstone (^22000^7)", "hold ^3f^7 for tombstone (^22000^7)",
     "按住 ^3F^7 购买 Tombstone（^22000^7）"),
    ("Hold ^3F^7 for Tombstone [Cost: 2000]", "hold ^3f^7 for tombstone [cost: 2000]",
     "按住 ^3F^7 购买 Tombstone [价格: 2000]"),
    ("Hold ^3F^7 to rebuild Barrier", "hold ^3f^7 to rebuild barrier",
     "按住 ^3F^7 重建路障"),
    ("Hold ^3F^7 for Stock Option", "hold ^3f^7 for stock option",
     "按住 ^3F^7 购买 Stock Option"),
    ("Hold ^3F^7 for ammo [Cost: 250]", "hold ^3f^7 for ammo [cost: 250]",
     "按住 ^3F^7 购买弹药 [价格: 250]"),
    ("Press ^3F^7 to take the weapon", "press ^3f^7 to take the weapon",
     "按 ^3F^7 拾取武器"),
    ("Hold ^3F^7 to dispense GobbleGum [Cost: 1500]", "hold ^3f^7 to dispense gobblegum [cost: 1500]",
     "按住 ^3F^7 获取泡泡糖 [价格: 1500]"),
    ("Hold ^3F^7 to dispense GobbleGum [Cost: 0]", "hold ^3f^7 to dispense gobblegum [cost: 0]",
     "按住 ^3F^7 获取泡泡糖 [价格: 0]"),
    ("Hold ^3F^7 for .420 Ironhide [Cost: 500]", "hold ^3f^7 for .420 ironhide [cost: 500]",
     "按住 ^3F^7 购买 .420 Ironhide [价格: 500]"),
    ("Hold ^3F^7 to clear Debris [Cost: 1000]", "hold ^3f^7 to clear debris [cost: 1000]",
     "按住 ^3F^7 清理残骸 [价格: 1000]"),
    ("Hold ^3F^7 to clear Debris [Cost: 1500]", "hold ^3f^7 to clear debris [cost: 1500]",
     "按住 ^3F^7 清理残骸 [价格: 1500]"),
    ("Hold ^3F^7 to use elevator [Cost: 250]", "hold ^3f^7 to use elevator [cost: 250]",
     "按住 ^3F^7 使用电梯 [价格: 250]"),
    ("Hold ^3F^7 to open Door [Cost: 750]", "hold ^3f^7 to open door [cost: 750]",
     "按住 ^3F^7 开门 [价格: 750]"),
    ("Hold ^3F^7 for DMR 14 [Cost: 500]", "hold ^3f^7 for dmr 14 [cost: 500]",
     "按住 ^3F^7 购买 DMR 14 [价格: 500]"),
    ("Hold ^3F^7 for Revive [Cost: 500]", "hold ^3f^7 for revive [cost: 500]",
     "按住 ^3F^7 复活队友 [价格: 500]"),
    ("^3[{+reload}]^7 Reload", "^3[{+reload}]^7 reload",
     "^3[{+reload}]^7 装填"),
    ("^3R^7 Reload", "^3r^7 reload",
     "^3R^7 装填"),
]

# 备注：`Expires in: &&1` 已被现有模板 `expires in: *` 覆盖，不加。
#       `Party Privacy: $(PartyPrivacy.privacyStatus)` / `$(scoreboardInfo...)` 是属性绑定串，不加。

MAP = [
    ("This map was entirely made by me, in terms of mapping. Gameplay features, scripting and",
     "就制图而言，这张地图完全由我一人完成。玩法内容、脚本与"),
]

# ------------------------------------------------------------------ 生成
medal_rows = []
for probe, key, value in MEDALS:
    row = add_manual("勋章", probe, key, value)
    if row:
        medal_rows.append(row)
rows["medals"] = medal_rows

colour_rows = []
colour_seen = set()
for probe, swaps, value in CHAT_COLOUR:
    if raw.count(probe.encode("ascii")) < 1:
        report.append("!! [聊天颜色码] dump 里找不到 %r" % probe)
        continue
    key = probe.lower()
    for old in swaps:
        if old not in key:
            report.append("!! [聊天颜色码] %s 里找不到 %r" % (key[:50], old))
            continue
        key = key.replace(old, "*")
    if key.count("*") != value.count("*"):
        report.append("!! [聊天颜色码] %s 的 '*' 数(%d) != 译文(%d)" % (key, key.count("*"), value.count("*")))
        continue
    if key in colour_seen:
        continue          # 两条原文塌成同一条模板（G11/P90 各一）
    colour_seen.add(key)
    if key in have:
        report.append("-- [聊天颜色码] %s 已在词库（跳过）" % key)
        continue
    colour_rows.append("%s=%s" % (key, value))
rows["chat_colour"] = colour_rows

plain_rows = []
plain_seen = set()
for needle, key_template, value in CHAT_PLAIN:
    hits = resolve(needle)
    if len(hits) != 1:
        report.append("!! [聊天纯文本] %s -> 命中 %d 条 %s" % (needle, len(hits), hits[:3]))
        continue
    if key_template in plain_seen:
        continue
    plain_seen.add(key_template)
    if key_template in have:
        report.append("-- [聊天纯文本] %s 已在词库（跳过）" % key_template)
        continue
    plain_rows.append("%s=%s" % (key_template, value))
rows["chat_plain"] = plain_rows

prompt_rows = []
for probe, key, value in PROMPTS:
    row = add_manual("交互提示", probe, key, value)
    if row:
        prompt_rows.append(row)
rows["prompts"] = prompt_rows

map_rows = []
for needle, value in MAP:
    hits = resolve(needle)
    if len(hits) != 1:
        report.append("!! [地图简介] %s -> 命中 %d 条 %s" % (needle[:50], len(hits), hits[:3]))
        continue
    key = hits[0].lower()
    if key in have:
        report.append("-- [地图简介] %s 已在词库（跳过）" % key)
        continue
    map_rows.append("%s=%s" % (key, value))
rows["maps"] = map_rows

JOBS = [
    (["", "# 颜色码版（续：漏掉的三个击杀勋章）"] + medal_rows,
     "# ═══ MOD：功能说明（僵尸 / 技能 / 游戏选项的长句）═══"),
    (["", "# ═══ MOD：聊天播报（玩家名与武器名一律原样保留）═══",
      "# 纯文本版（面板里可能读它）与颜色码版（聊天真正渲染的那份）成对加入。"]
     + plain_rows, "# ═══ 模板条目（动态数值：等级 / 转生 / 时长 / 命中次数）═══"),
    (["", "# ═══ 模板条目（MOD 聊天播报：玩家名 / 武器名通配）═══"] + colour_rows,
     "# ═══ 格式标记片段（^B 按键绑定 / $() 属性绑定 / [{...}] 令牌）═══"),
    (["", "# ═══ MOD：交互提示（按住按键 / 价格）═══"] + prompt_rows,
     "# ═══ 格式标记片段（^B 按键绑定 / $() 属性绑定 / [{...}] 令牌）═══"),
    (["", "# ═══ MOD：地图列表与兼容性说明（续 3）═══"] + map_rows,
     "# ═══ 模板条目（动态数值：等级 / 转生 / 时长 / 命中次数）═══"),
]

total = sum(len(v) for v in rows.values())
if report and any(r.startswith("!!") for r in report):
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
    if ok and not any(block[1:] for block, _ in JOBS):
        ok = False
        print("这一轮什么都没新增")
    if ok:
        if buf.count(OLDV.encode()) != 1:
            print("版本行不唯一")
            ok = False
        else:
            buf = buf.replace(OLDV.encode(), NEWV.encode(), 1)
    if ok:
        open(DICT, "wb").write(buf)
        print("已写入 %s（%d 字节，EOL=%s，新增 %d 条）" % (DICT, len(buf), EOL, total))

with open(REPORT, "w", encoding="utf-8") as fh:
    fh.write("新增条目 %d：\n" % total)
    for tag in ("medals", "chat_colour", "chat_plain", "prompts", "maps"):
        fh.write("\n### %s (%d)\n%s\n" % (tag, len(rows.get(tag, [])), "\n".join(rows.get(tag, []))))
    if report:
        fh.write("\n=== 备注 / 未解析 ===\n" + "\n".join(report) + "\n")
print("report:", REPORT)
