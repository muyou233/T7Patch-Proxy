r"""补入 workshop 地图 / mod 的 UI 文案与简介（2026-09-18 第三批采集）。

来源：`<游戏>\T7Patch\ui_dump.txt`（用户单人游玩多张新地图后采集）。
用户 2026-09-18 澄清："没聊天，我全程单人玩的，有些是 mod 或者地图的简介"
⇒ 采集里的**句子**不能一概当聊天跳过，要按下面三类分开处理：

  ① 玩家名 / `host xxx` / 大厅与好友面板文本  ⇒ **不翻**（产品策略：玩家名一律保留原文）
  ② mod / 地图的 **UI 与任务提示**            ⇒ 翻（本脚本 A、B 段）
  ③ mod / 地图的 **简介与宣传段**              ⇒ 翻（本脚本 C 段；含 `[h3]`/`[img]` 标记的要连标记一起译）
  · 专名（地图名 / mod 名 / 道具名）无权威中文译名的**保留原文**（技能里的歧义译名规则）；
    本批按此保留：Kronorium、Aether Shroud、Dead Wire、Maxis Drone、EZ Target、`host xxx`、各 workshop 地图名。

安全措施（都是踩过坑加上的）：
  · **写盘前断言无重复键** —— 2026-09-18 我连续两次手写出重复键（引擎里后者静默覆盖前者，不报错）；
  · 已存在的键自动跳过并报告（不覆盖既有译文）；
  · 断言全是 LF、无 BOM、条目数与预期一致。
"""
import io
import os

REPO = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private"
PATH = os.path.join(REPO, r"translate\translate_zh.txt")

# ---- A. mod 的功能宣传段（一个 mod 的简介块，逐句）--------------------------
BLURB = [
    ("Getting overwhelmed?", "招架不住了？"),
    ("Out of ammo?", "子弹打光了？"),
    ("Running low on ammo?", "弹药快见底了？"),
    ("Lost or almost down?", "迷路了，还是快倒地了？"),
    ("Feeling a bit slow?", "觉得有点吃力？"),
    ("We got you covered!", "有我们帮你兜底！"),
    ("Need a new weapon?", "想要把新武器？"),
    ("We have all you need", "你需要的这里都有"),
    ("This will never let you down", "它绝不会让你失望"),
    ("This will give you a temporary boost", "这会给你一次临时增益"),
]

# ---- B. 任务提示 / 界面标签 -------------------------------------------------
OBJECTIVES = [
    ("ENTER CODE", "输入代码"),
    ("Call the elevator", "呼叫电梯"),
    ("Find the keycard", "找到门禁卡"),
    ("Access the lab", "进入实验室"),
    ("Access the director office", "进入主管办公室"),
    ("Disable the alarm system", "关闭警报系统"),
    ("Find the key for the chapel", "找到教堂的钥匙"),
    ("Find the RC-XD Remote", "找到 RC-XD 遥控器"),
    ("Take the elevator to the sub ground floor", "乘电梯到地下层"),
    ("Take out the doctor with the RC-XD", "用 RC-XD 干掉医生"),
    ("Gain Access to Security Room in West Offices", "进入西办公区的安保室"),
    ("Throw one of these to burn them to the ground", "扔一个过去，把它们烧成灰"),
    ("Use Nightmare vision for invincibility and hints", "用「梦魇视野」获得无敌与提示"),
    ("Would you like to apply recommended settings?", "是否应用推荐设置？"),
    ("Find the kronorium", "找到 Kronorium"),
    ("Gamma: REC 709", "伽马：REC 709"),
    ("The Dutchman's Zombies UI Overhaul +", "荷兰人的僵尸 UI 重制 +"),
]

# ---- C. 地图简介（长段；标记与句子一起译）----------------------------------
DESCRIPTIONS = [
    ("In another world, the Pentagon is left in ruin...",
     "在另一个世界里，五角大楼只剩废墟……"),
    ("December, 1984. In a chilly Berlin town, things are not calm but they are bright....",
     "1984 年 12 月。寒冷的柏林小镇并不平静，却格外明亮……"),
    ("Mass-energy equivalence, secret tests, crash-landing perks. Survive in the iconic "
     "Nuketown, where the past and the future come together.",
     "质能等价、秘密试验、坠机获得的技能。在这张标志性的「核弹镇」求生——过去与未来在此交汇。"),
    ("[h3]Deep inside a child's mind, our four hero's attempt to escape the dark and secret "
     "past within her dreams.[/h3]",
     "[h3]在孩童意识的深处，四位英雄试图逃离她梦境里那段黑暗而隐秘的过往。[/h3]"),
    ("This map is still a Work in Progress and has some bugs I need to fix, but I'd like "
     "feedback a",
     "这张地图仍在制作中，还有些我得修的 bug，不过我很希望能收到反馈……"),
    ("Watch your step! Fight for survival atop the towers of doom, where dizzying heights "
     "and the relentless undead make a deadly combination.",
     "小心脚下！在末日高塔之巅为生存而战——令人眩晕的高度加上无穷无尽的尸潮，是致命的组合。"),
    ("This is a small remaster of Verruckt trying to emulate the feeling of classic zombies "
     "like WaW and Bo1. The courtyard and some outside parts are now playable.",
     "这是「疯狂」的小型重制版，力求还原《战火世界》与《黑色行动 1》那种经典僵尸手感。"
     "现在庭院与部分室外区域也能游玩了。"),
]

SECTION = ("\n# ═══ workshop 地图 / mod 的 UI 与简介（2026-09-18 采集补入）═══\n"
           "# 用户澄清过「没聊天，全程单人玩，有些是 mod/地图简介」⇒ 这些句子要翻，别当聊天跳过。\n"
           "# 继续保留原文的：玩家名 / `host xxx` / 无权威中文译名的专名（Kronorium、Aether Shroud、\n"
           "# Dead Wire、Maxis Drone、EZ Target）与各 workshop 地图名本身。\n")


def parse(text):
    plain = set()
    for line in text.split("\n"):
        s = line.strip()
        if not s or s[:1] in ("#", ";") or "=" not in line:
            continue
        k = line.split("=", 1)[0].strip().lower()
        plain.add(k)
    return plain


raw = io.open(PATH, "rb").read()
assert b"\r" not in raw, "词库必须是 LF：发现 CR"
assert not raw.startswith(b"\xef\xbb\xbf"), "词库不能带 BOM"
text = raw.decode("utf-8")
before = parse(text)

added, skipped = [], []
lines = []
for en, zh in BLURB + OBJECTIVES + DESCRIPTIONS:
    k = en.lower()
    if k in before or k in added:
        skipped.append(k)
        continue
    assert "\n" not in k and "=" not in k, "键里有非法字符：%r" % k
    lines.append("%s=%s" % (k, zh))
    added.append(k)

assert added, "没有任何新条目"
new_text = text.rstrip("\n") + "\n" + SECTION + "\n".join(lines) + "\n"

after = parse(new_text)
assert after - before == set(added), "新增键与预期不符"
assert len(after) == len(before) + len(added), "出现重复键（脚本自身防呆）"
assert b"\r" not in new_text.encode("utf-8"), "写出内容含 CR"
for k in added:
    assert k in after, "新键丢失：%s" % k

io.open(PATH, "wb").write(new_text.encode("utf-8"))

print("ok")
print("  新增 %d 条（宣传段 %d / 任务提示 %d / 地图简介 %d）"
      % (len(added), min(len(BLURB), len(added)),
         len([k for k in added if k in [e.lower() for e, _ in OBJECTIVES]]),
         len([k for k in added if k in [e.lower() for e, _ in DESCRIPTIONS]])))
print("  跳过（词库已有）%d 条：%s" % (len(skipped), ", ".join(sorted(skipped)) or "无"))
print("  条目 %d -> %d" % (len(before), len(after)))
