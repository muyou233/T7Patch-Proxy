"""预写入官方道具 / 称号类专名（2026-09-18，用户要求"官方全部的道具以及其他称号，反正专用的，全部先预写入词库"）。

数据来源（技能规则三层里的第一层，权威）：
  · 灰机 wiki《GobbleGum(ZM)》   https://cod.huijiwiki.com/wiki/GobbleGum(ZM)      —— BO3 泡泡糖 62 条
  · 灰机 wiki《Perk-a-Cola(ZM)》 https://cod.huijiwiki.com/wiki/Perk-a-Cola(ZM)    —— 特长汽水
标注为"页面未给出英文名/仅图标文件名"的条目按页面实际给出的写法收录，不猜测。

两条命名决定（用户拍板优先于 wiki）：
  · `Perkaholic` 用**「技能狂」**（用户 2026-09-18："技能狂是我常看的称呼"），不用灰机的"特长狂"；
  · `Cache Back` **跳过**——灰机给的是网络梗译名，不适合入游戏词库，保留原文。

分段策略（配合用户的"分段翻译"要求）：
  · **多词**名字标成可组合片段（`~`）⇒ 将来 `X: <名> 2.0` / `Hold F for <名> [Cost: N]` 这类
    **新组合自动生效**，不必再逐条补词库；
  · **单词**名字只能用精确条目（单 token 标片段会误伤玩家名，见 skill 硬约定）。
"""
import io
import os

REPO = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private"
PATH = os.path.join(REPO, r"translate\translate_zh.txt")

SECTION_ANCHOR = "coagulant=凝血剂\n"

# ---- 灰机《GobbleGum(ZM)》BO3 全表（英文 = 中文）--------------------------
GOBBLEGUMS = [
    ("Always Done Swiftly", "快如既往"),
    ("Arms Grace", "优雅武装"),
    ("Coagulant", "凝血剂"),
    ("In Plain Sight", "熟视无睹"),
    ("Stock Option", "自动补给"),
    ("Impatient", "急不可耐"),
    ("Sword Flay", "刀剑凌虐"),
    ("Anywhere But Here", "慌不择路"),
    ("Anywhere But Here!", "慌不择路！"),
    ("Danger Closest", "炸弹专家"),
    ("Armamental Accomplishment", "武器成就"),
    ("Firing On All Cylinders", "千足马力"),
    ("Arsenal Accelerator", "火力加速"),
    ("Lucky Crit", "幸运暴击"),
    ("Now You See Me", "众矢之的"),
    ("Alchemical Antithesis", "炼铅术士"),
    ("Projectile Vomiting", "狂吐不止"),
    ("Newtonian Negation", "牛顿错了"),
    ("Eye Candy", "视觉享受"),
    ("Tone Death", "五音不全"),
    ("Aftertaste", "回味"),
    ("Burned Out", "烈火罩"),
    ("Dead of Nuclear Winter", "核冬天的死寂"),
    ("Ephemeral Enhancement", "短暂加强"),
    ("I'm Feeling Lucky", "运气不错"),
    ("Immolation Liquidation", "清仓减价"),
    ("Licensed Contractor", "执照施工"),
    ("Phoenix Up", "凤凰涅槃"),
    ("Pop Shocks", "爆裂冲击"),
    ("Respin Cycle", "再转一次"),
    ("Unquenchable", "所向披靡"),
    ("Who's Keeping Score?", "名列前茅"),
    ("Crawl Space", "膝盖已碎"),
    ("Fatal Contraption", "致命装置"),
    ("Unbearable", "闲熊勿扰"),
    ("Disorderly Combat", "乱枪混战"),
    ("Slaughter Slide", "杀戮滑行"),
    ("Mind Blown", "精神惩戒"),
    ("Board Games", "板上钉钉"),
    ("Board To Death", "危险施工"),
    ("Flavor Hexed", "独特口味"),
    ("Idle Eyes", "斜眼废物"),
    ("Kill Joy", "杀戮快感"),
    ("On the House", "免费招待"),
    ("Wall Power", "壁力惊人"),
    ("Undead Man Walking", "行尸走肉"),
    ("Fear in Headlights", "目光如炬"),
    ("Temporal Gift", "时间的馈赠"),
    ("Crate Power", "魔盒之力"),
    ("Bullet Boost", "子弹加速"),
    ("Extra Credit", "额外收入"),
    ("Soda Fountain", "苏打畅饮"),
    ("Killing Time", "杀戮时刻"),
    ("Perkaholic", "技能狂"),          # 用户指定：技能狂
    ("Head Drama", "大难临头"),
    ("Secret Shopper", "神秘顾客"),
    ("Shopping Free", "免费购物"),
    ("Near Death Experience", "濒死体验"),
    ("Profit Sharing", "好处均摊"),
    ("Round Robbin'", "循环轮转"),
    ("Self Medication", "自行治疗"),
    ("Power Vacuum", "频繁强化"),
    ("Reign Drops", "全面强化"),
]

# ---- 灰机《Perk-a-Cola(ZM)》特长汽水 ---------------------------------------
PERKS = [
    ("Juggernog", "厚血蛋酒"),
    ("Quick Revive", "快速复苏"),
    ("Speed Cola", "快手可乐"),
    ("Double Tap", "分裂射击"),
    ("Double Tap II", "分裂射击 II"),
    ("Mule Kick", "三枪烈酒"),
    ("Stamin-Up", "耐力提升"),
    ("Deadshot Daiquiri", "死亡射手代基里"),
    ("Electric Cherry", "电击樱桃"),
    ("Widow's Wine", "寡妇美酒"),
    ("Tombstone Soda", "墓碑汽水"),
]

# ---- 用户点名的"分段翻译"组合件（已有译法，标成片段即可让新组合自动生效）----
FRAGMENT_ONLY = [
    ("girls' frontline", "少女前线"),
    ("all-around enhancement", "全方位增强"),
]

SKIP = {"cache back"}  # 梗译名，不适合入词库


def parse(text):
    plain, tmpl = {}, set()
    for line in text.split("\n"):
        s = line.strip()
        if not s or s[:1] in ("#", ";") or "=" not in line:
            continue
        k = line.split("=", 1)[0].strip().lower()
        if "*" in k:
            tmpl.add(k)
        else:
            plain[k] = line
    return plain, tmpl


def key_for(en):
    """多词 ⇒ 片段（~ 前缀）；单词 ⇒ 精确键。"""
    k = en.lower()
    return ("~" + k) if " " in k else k


raw = io.open(PATH, "rb").read()
assert b"\r" not in raw, "词库必须是 LF：发现 CR"
text = raw.decode("utf-8")
before, before_tmpl = parse(text)

added, skipped = [], []
lines = []
for en, zh in GOBBLEGUMS + PERKS + [(en, zh) for en, zh in FRAGMENT_ONLY]:
    k = key_for(en)
    if en.lower() in SKIP or k in before:
        skipped.append(k)
        continue
    lines.append("%s=%s" % (k, zh))
    added.append(k)

# 插在「道具 / 泡泡糖名」节末尾（锚点是该节最后一条 coagulant），保持既有排版
assert text.count(SECTION_ANCHOR) == 1, "锚点不唯一"
block = (SECTION_ANCHOR
         + "\n# 官方道具 / 称号类专名全量预写入（2026-09-18）：数据来自灰机 wiki《GobbleGum(ZM)》《Perk-a-Cola(ZM)》。\n"
         + "# 多词名用 `~` 片段（新组合自动生效，不必再逐条补）；单词名用精确键（单 token 不许标片段）。\n"
         + "# ⚠️ Perkaholic 用用户指定的「技能狂」；⚠️ Cache Back 灰机给的是梗译名，**有意跳过**（保留原文）。\n"
         + "\n".join(lines) + "\n")
new_text = text.replace(SECTION_ANCHOR, block)

after, after_tmpl = parse(new_text)
assert set(after) - set(before) == set(added), "新增键与预期不符"
assert not (set(before) - set(after)), "有键被删"
assert after_tmpl == before_tmpl, "模板集合被动到了"
keys = [l.split("=", 1)[0].strip().lower() for l in new_text.split("\n")
        if l.strip() and l.strip()[:1] not in ("#", ";") and "=" in l]
assert len(keys) == len(set(keys)), "出现重复键"
assert b"\r" not in new_text.encode("utf-8")

io.open(PATH, "wb").write(new_text.encode("utf-8"))

print("ok")
print("  新增 %d 条（片段 %d / 精确 %d）"
      % (len(added), sum(1 for k in added if k.startswith("~")),
         sum(1 for k in added if not k.startswith("~"))))
print("  跳过已存在/不收录 %d 条：%s" % (len(skipped), ", ".join(sorted(skipped))))
print("  条目 %d -> %d" % (len(before), len(after)))
