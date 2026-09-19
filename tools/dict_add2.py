r"""第二轮增补：把 dict_triage 分出来的「界面文本候选」翻好写进词库（仓库源）。

沿用 dict_add.py 的规矩：**键一律从 dump 原文取**（needle 只用"折叠空白 + 小写"做定位），
要求恰好命中一条；字节级锚点插入，沿用文件原换行；每条锚点必须唯一。

本轮范围（工作清单截图里除玩家名/截断句以外的全部）：
  状态提示 / 暂停菜单       12
  僵尸：局内提示与道具说明    4
  MOD：工坊模组栈界面（续）    7  (+1 模板)
  MOD：地图列表与兼容性说明（续） 5

明确**不收**：玩家名（Ulises Damian Qu / I'm the king of / muyou…）、
武器名、按键名、纯数值、字形测试串，以及那条被截断的 mod 简介
（"This map was entirely made by me…scripting and" —— 结尾是 and，不是完整句，
加进去要么永不命中、要么把半句话翻出来）。
"""
import os
import re

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
REPORT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\dict_add2_report.txt"

# ---------------------------------------------------------------- 候选池
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
    # dump 会跨进程重复追加同一行（旧采集器不去重）——逐字节相同的重复不是歧义，
    # 只有**不同**变体（空白差异）才该拦下来问人。
    if txt not in pool.setdefault(k, []):
        pool[k].append(txt)

# ---------------------------------------------------------------- 已有键
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
STATUS = [
    ("Loading:", "加载中："),
    ("PAUSED", "已暂停"),
    ("CLOSE", "关闭"),
    ("RESTART LEVEL", "重新开始关卡"),
    ("START MENU", "开始菜单"),
    ("GAME OVER", "游戏结束"),
    ("END GAME", "结束游戏"),
    ("MATCH BEGINS IN", "比赛即将开始"),
    ("Low Ammo", "弹药不足"),
    ("No Ammo", "无弹药"),
    ("Double XP", "双倍经验"),
    ("Double Weapon XP", "双倍武器经验"),
]

ZOMBIE = [
    ("Elevator is Active", "电梯已启动"),
    ("Lasts 3 minutes", "持续 3 分钟"),
    ("Ammo taken from stockpile instead of magazine", "弹药从储备中取用，而非弹匣"),
    ("You must turn on the Power first!", "你必须先打开电源！"),
]

WORKSHOP2 = [
    ("Access Denied: Requires operational component", "拒绝访问：需要可用的组件"),
    ("No gameplay mods are loaded.", "未载入任何玩法模组。"),
    ("Active load order. Mod 1 has the highest priority when assets overlap.",
     "当前生效的载入顺序。资源冲突时，模组 1 的优先级最高。"),
    ("BO3 Workshop Stack (Experimental)", "BO3 工坊模组栈（实验性）"),
    ("Modern weapons | Enabled Gums and AAT | Additional perks",
     "现代武器 | 启用泡泡糖与 AAT | 额外技能"),
    ("Classic weapons | Disabled Gums and AAT | No added perks",
     "经典武器 | 禁用泡泡糖与 AAT | 无额外技能"),
    ("Esc / B: close    Scroll / Up / Down: browse",
     "Esc / B：关闭    滚轮 / 上 / 下：浏览"),
]

MAPS2 = [
    ("Maggot ridden corpses. Bug infested swamp. Hundreds of undead Imperial Army."
     " Choose your tactic and defend for your lives!",
     "蛆虫遍地的尸骸。虫害肆虐的沼泽。成百上千的不死帝国军。"
     "选择你的战术，为性命而战！"),
    ("Witness the origins of Group 935, as an ancient evil is unleashed upon the"
     " battlefields of World War I.",
     "见证 935 小组的起源 —— 一场古老的邪恶被释放在第一次世界大战的战场上。"),
    ("Electroshock therapy. Chemically engineered beverages. Hordes of undead Nazis."
     " Find the power to unite and send them back to their graves!",
     "电击疗法。化学合成的饮料。成群的不死纳粹。"
     "找到团结起来的力量，把他们送回坟墓！"),
    ("The risen dead have overtaken a Soviet cosmodrome and all Hell has broken loose."
     " The countdown to the zombie apocalypse has begun.",
     "复活的死者占领了苏联航天发射场，一切彻底失控。僵尸末日的倒计时已经开始。"),
    ("A legendary shrine lost in an exotic jungle, where the undead lurk within a"
     " treacherous labyrinth of underground caverns, deadly traps and dark secrets.",
     "一座失落在异域丛林中的传奇神殿，不死者潜伏在险恶的地下洞窟迷宫、"
     "致命陷阱与黑暗秘密之中。"),
]

# 模板: (needle, [(old, new), ...], 译文)
TEMPLATES = [
    ("loaded mods  /  0", [("/  0", "/  *")], "已载入模组 / *"),
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
        if key.count("*") != value.count("*"):
            report.append("!! %s 的 '*' 数不匹配（键 %d / 译 %d）"
                          % (key, key.count("*"), value.count("*")))
            continue
        rows.append("%s=%s" % (key, value))
    rendered[tag] = rows
    return ["", header] + rows


tpl_rows = []
for needle, reps, value in TEMPLATES:
    hits = resolve(needle)
    if len(hits) != 1:
        report.append("!! [模板] %s -> 命中 %d 条 %s" % (needle, len(hits), hits[:3]))
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

# ---------------------------------------------------------------- 锚点（都必须唯一）
JOBS = [
    (build("status", "# ═══ 状态提示 / 暂停菜单 ═══", STATUS),
     "# ═══ 等级 / 转生 / 战斗记录数值 ═══"),
    (build("zombie", "# ═══ 僵尸：局内提示与道具说明 ═══", ZOMBIE),
     "# ═══ 排位 / 赛事 ═══"),
    (build("workshop2", "# ═══ MOD：工坊模组栈界面（续）═══", WORKSHOP2),
     "# ═══ MOD：聊天指令帮助 ═══"),
    (build("maps2", "# ═══ MOD：地图列表与兼容性说明（续）═══", MAPS2),
     "# ═══ 模板条目（动态数值：等级 / 转生 / 时长 / 命中次数）═══"),
    (["", "# ═══ 模板条目（动态数值：等级 / 转生 / 时长 / 命中次数）（续）═══"] + tpl_rows,
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
        oldv = "# version: 2026-09-16b"
        if buf.count(oldv.encode()) != 1:
            print("版本行不唯一")
            ok = False
        else:
            buf = buf.replace(oldv.encode(), "# version: 2026-09-16c".encode(), 1)
    if ok:
        open(DICT, "wb").write(buf)
        total = sum(len(v) for v in rendered.values()) + len(tpl_rows)
        print("已写入 %s（%d 字节，EOL=%s，新增 %d 条）" % (DICT, len(buf), EOL, total))

with open(REPORT, "w", encoding="utf-8") as fh:
    fh.write("新增条目：\n")
    for tag in ("status", "zombie", "workshop2", "maps2"):
        fh.write("\n### %s (%d)\n%s\n" % (tag, len(rendered.get(tag, [])),
                                          "\n".join(rendered.get(tag, []))))
    fh.write("\n### templates (%d)\n%s\n" % (len(tpl_rows), "\n".join(tpl_rows)))
    if report:
        fh.write("\n=== 未解析 ===\n" + "\n".join(report))
print("report:", REPORT)
