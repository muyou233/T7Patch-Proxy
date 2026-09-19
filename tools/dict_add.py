r"""把 ui_dump.txt 里这一轮新采集到的界面串，翻好后写进词库（仓库源）。

为什么不留给人手打键：**键必须与引擎送出的片段逐字节一致**，
而像 "INSTALLED MODS  /  3" 这种双向双空格的串，手打必错。
所以：键一律从这个 dump 里**原文取**，只在比对时把连续空白折叠成单空格
（needle 用折叠后的形式写，方便阅读），并且要求"恰好命中一条"，
命中 0 条或 >1 条都报出来，不许猜。

模板条目（动态数值）用 replacements 把变体部分换成 '*'。

写盘：字节级替换锚点，沿用文件原有的换行风格（LF/CRLF 自动判断）。
"""
import os
import re

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
REPORT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\dict_add_report.txt"

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


pool = {}   # norm -> [原文, ...]
for line in raw.split(b"\n"):
    s = strip_wrap(line.rstrip(b"\r"))
    if not s or any(c >= 0x80 or c < 0x20 for c in s):
        continue
    if any(c in b"^$&" for c in s):
        continue
    txt = s.decode("ascii")
    pool.setdefault(re.sub(r"\s+", " ", txt).strip().lower(), []).append(txt)

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
HUD = [
    ("points", "点数"),
    ("rounds", "回合数"),
    ("round", "回合"),
    ("downs", "倒地次数"),
    ("revives", "复活次数"),
    ("ping", "延迟"),
    ("you survived", "你活了下来"),
    ("instant kill", "秒杀"),
]

WORKSHOP = [
    ("workshop stack / ready", "工坊模组栈 / 就绪"),
    ("build your mod stack", "构建你的模组栈"),
    ("reset changes", "重置更改"),
    ("your selection matches the loaded stack.", "你的选择与已载入的模组栈一致。"),
    ("no mods selected. add mods from the left.", "未选择任何模组。请从左侧添加。"),
    ("select multiple mods, arrange their priority, then apply your changes together.",
     "可多选模组、调整优先级，然后一并应用更改。"),
    ("cancel / back", "取消 / 返回"),
    ("up to date", "已是最新"),
]

CHAT = [
    ("/s: suicide.", "/s：自杀。"),
    ("/tps: toggle thirdperson.", "/tps：切换第三人称视角。"),
    ("/char: change your character.", "/char：更换你的角色。"),
    ("/tpscam: load a thirdperson preset.", "/tpscam：载入第三人称预设。"),
    ("/cheats: toggle cheats. host only.", "/cheats：切换作弊开关。仅主机可用。"),
    ("/help or /?: print help message for chat command system.",
     "/help 或 /?：打印聊天指令系统的帮助信息。"),
    ("/mw3intro: preview a mw3-ish intro cutscene.",
     "/mw3intro：预览一段近似 MW3 风格的开场动画。"),
    ('you can use the chat command system by typing "/[insert command here]" in the'
     " in-game chat. below is an incomplete list of usable commands. some commands are"
     " exclusive to zombies.",
     "你可以在游戏内聊天里输入「/[在此填写指令]」来使用聊天指令系统。"
     "以下是可用指令的不完整列表；部分指令仅限僵尸模式。"),
    ("enter / a: toggle q / lb: up e / rb: down f / y: apply r / x: reset u / ls: clear"
     " esc / b: cancel",
     "Enter / A：切换    Q / LB：上移    E / RB：下移    F / Y：应用"
     "    R / X：重置    U / LS：清空    Esc / B：取消"),
]

MAPS = [
    ("click here for more information about the compatibility of custom maps.",
     "点击此处了解自定义地图兼容性的更多信息。"),
    ("relive the unsettling experience of town set years after the events of tranzit.",
     "重温「小镇」那令人不安的体验 —— 故事发生在「TranZit」事件数年之后。"),
    ('the pentagon is under attack! washington is going to defcon 1 in this installment'
     ' of "zombies"',
     "五角大楼遭到袭击！在「僵尸模式」的这一篇章里，华盛顿即将进入 DEFCON 1。"),
    ("here it is everyone! hope you all enjoy playing it as much as i did making it! :]",
     "各位，它来了！希望你们玩得和我做的时候一样开心！:]"),
    ("most official and custom maps should work. however keep in mind that bo3 is tight on"
     " asset limits. gfl mod has already included a large amount of high quality assets so"
     " do some custom maps. certain maps are equipped with anti-cheating and don't allow"
     " the usage of mods.",
     "大多数官方与自定义地图都能正常运行。但请记住 BO3 的资源上限很紧，GFL 模组本身"
     "已包含大量高质量资源，因此部分自定义地图可能出问题。某些地图带有反作弊机制，"
     "不允许使用模组。"),
]

FAQ = [
    ("using t7patch is still recommended for multiplayer and zombies gameplay out of"
     " security concerns. see useful links for more infomation.",
     "出于安全考虑，多人游戏与僵尸模式依然建议使用 T7Patch。更多信息见「实用链接」。"),
    ("are you using t7patch? for now it has some issues with campaign. revert the patch"
     " if you want to play campaign.",
     "你在使用 T7Patch 吗？目前它与战役模式存在一些问题；如果想玩战役，请先撤下补丁。"),
    (r"every mod has its standalone save data. you may copy them from somewhere else by"
     r" manual. for this mod the save data is located in players\311210\3019676071.",
     r"每个模组都有独立的存档数据，你可以手动从别处复制过来。本模组的存档位于"
     r" players\311210\3019676071。"),
    ("moon and origins are one of the known maps that might crash the game for some users."
     " if the crash persists, consider playing other compatible maps.",
     "「月球」和「起源」是已知可能让部分玩家崩溃的地图。如果崩溃持续出现，"
     "建议改玩其他兼容地图。"),
]

# 模板条目: (needle, [(替换 old, new), ...], 译文)
TEMPLATES = [
    ("installed mods / 3", [("/  3", "/  *")], "已安装模组 / *"),
    ("press [l] loaded mods (0)", [("(0)", "(*)")], "按 [L] 已载入模组（*）"),
    ("load order / 0 selected", [("/  0 selected", "/  * selected")], "载入顺序 / 已选 *"),
    ("1 has highest priority. settings profile: none",
     [("1 has", "* has"), ("profile: none", "profile: *")],
     "* 为最高优先级。设置方案：*"),
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

# ---------------------------------------------------------------- 组装
hud_block = build("hud", "# ═══ HUD / 记分板标签 ═══", HUD)
mod_block = (build("workshop", "# ═══ MOD：工坊模组栈界面 ═══", WORKSHOP)
             + build("chat", "# ═══ MOD：聊天指令帮助 ═══", CHAT)
             + tpl_rows
             + build("maps", "# ═══ MOD：地图列表与兼容性说明 ═══", MAPS)
             + build("faq", "# ═══ MOD：t7patch 相关 FAQ（续）═══", FAQ))

MOD_ANCHOR = "# ═══ 模板条目（动态数值：等级 / 转生 / 时长 / 命中次数）═══"
HUD_ANCHOR = "# ═══ 等级 / 转生 / 战斗记录数值 ═══"

AFTER = [
    ("mods=模组", ["mod=模组"]),
    ("t-doll zombies=战术人形僵尸",
     ["t-dolls=战术人形", "sf units=SF 单位", "t-dolls and sf=战术人形与 SF 单位"]),
]

# ---------------------------------------------------------------- 写盘
if report:
    print("有未解析项，**未写盘**：")
    for r in report:
        print("  " + r)
else:
    buf = dict_raw
    ok = True
    for anchor, block in ((HUD_ANCHOR, hud_block), (MOD_ANCHOR, mod_block)):
        a = anchor.encode("utf-8")
        if buf.count(a) != 1:
            print("锚点不唯一：%s (%d)" % (anchor, buf.count(a)))
            ok = False
            break
        buf = buf.replace(a, (EOLS.join(block) + EOLS).encode("utf-8") + a, 1)
    if ok:
        for anchor, entries in AFTER:
            a = anchor.encode("utf-8")
            if buf.count(a) != 1:
                print("锚点不唯一：%s (%d)" % (anchor, buf.count(a)))
                ok = False
                break
            buf = buf.replace(a, (anchor + EOLS + EOLS.join(entries)).encode("utf-8"), 1)
    if ok:
        oldv = "# version: 2026-09-16"
        if buf.count(oldv.encode()) != 1:
            print("版本行不唯一")
            ok = False
        else:
            buf = buf.replace(oldv.encode(), "# version: 2026-09-16b".encode(), 1)
    if ok:
        open(DICT, "wb").write(buf)
        total = sum(len(v) for v in rendered.values()) + len(tpl_rows) + 1
        print("已写入 %s（%d 字节，EOL=%s，新增 %d 条）" % (DICT, len(buf), EOL, total))

with open(REPORT, "w", encoding="utf-8") as fh:
    fh.write("新增条目：\n")
    for tag in ("hud", "workshop", "chat", "maps", "faq"):
        fh.write("\n### %s (%d)\n%s\n" % (tag, len(rendered.get(tag, [])),
                                          "\n".join(rendered.get(tag, []))))
    fh.write("\n### templates (%d)\n%s\n" % (len(tpl_rows), "\n".join(tpl_rows)))
    fh.write("\n### 另插：mod=模组 + t-dolls / sf units / t-dolls and sf\n")
    if report:
        fh.write("\n=== 未解析 ===\n" + "\n".join(report))
print("report:", REPORT)
