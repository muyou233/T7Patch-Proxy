"""按「游戏偏向官方的权威中文」补道具类专用名词（2026-09-18）。

权威来源（技能规则：灰机 > Fandom 中文维基 > B站）：
  · 灰机 wiki《GobbleGum(ZM)》  https://cod.huijiwiki.com/wiki/GobbleGum(ZM)
  · 灰机 wiki《Winter's Howl(奇迹武器)》 https://cod.huijiwiki.com/wiki/Winter's_Howl(奇迹武器)

本次落地：
  1. 新增 7 条道具名 —— 6 条多词名标成**可组合片段**（`~`，这样 "Hold F for <名> [Cost: N]" 这类
     变体不必再逐条补），1 条单词名用精确条目（规则：单 token 不许标片段）；
  2. 同步修掉 3 条与权威名冲突的旧译文（同名道具在别处仍写拉丁原文 / 旧译名）。

断言（写盘前）：新增键恰好这 7 个、3 条改动命中且只有 1 处、无 CR、无 BOM、无重复键。
"""
import io
import os

REPO = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private"
PATH = os.path.join(REPO, r"translate\translate_zh.txt")

SECTION_HEADER = "# ═══ 可组合片段（键以 ~ 开头；2026-09-18 新增机制）═══"

# (键, 值, 是否可组合片段)
#   灰机原文：Stock Option = 自动补给 / In Plain Sight = 熟视无睹 / Always Done Swiftly = 快如既往
#             Arms Grace = 优雅武装 / Coagulant = 凝血剂 / Winter's Howl = 冬日嚎叫（强化版 冬日之怒）
#             Double Points = 双倍分数（强化道具，非泡泡糖）
NEW_ITEMS = [
    ("stock option", "自动补给", True),
    ("in plain sight", "熟视无睹", True),
    ("always done swiftly", "快如既往", True),
    ("arms grace", "优雅武装", True),
    ("winter's howl", "冬日嚎叫", True),
    ("double points", "双倍分数", True),
    ("coagulant", "凝血剂", False),          # 单词名：规则禁止标成片段（易误伤）
]

# (旧整行, 新整行) —— 与权威名对齐
FIXUPS = [
    ("hold ^3f^7 for stock option=按住 ^3F^7 购买 Stock Option",
     "hold ^3f^7 for stock option=按住 ^3F^7 购买自动补给"),
    ("spawn with perkaholic=出生携带「技能全满」",
     "spawn with perkaholic=出生携带「特长狂」"),
    ("choose whether to start with perkaholic.=选择是否开局携带「技能全满」。",
     "choose whether to start with perkaholic.=选择是否开局携带「特长狂」。"),
]

SECTION = """# ═══ 道具 / 泡泡糖名（2026-09-18：改按游戏权威中文名翻译）═══
# 依据（技能规则优先级：灰机 > Fandom 中文维基 > B站）：
#   灰机《GobbleGum(ZM)》与《Winter's Howl(奇迹武器)》页面。
# 规则：多词道具名标成可组合片段（`~`），这样 "Hold F for <名> [Cost: N]" 这类变体自动覆盖；
#       单词名只能用精确条目（单 token 标片段会误伤玩家名）。
# ⚠️ 灰机未收录的名字（Peek Me Pookie / Gum Gobbler）**不硬译**，保留原文（歧义规则）。
# ⚠️ 上下文是玩家名的 token（Little Boy / Flash）**不是道具**，不在此翻译。
~winter's howl=冬日嚎叫
~always done swiftly=快如既往
~in plain sight=熟视无睹
~arms grace=优雅武装
~stock option=自动补给
~double points=双倍分数
coagulant=凝血剂
"""


def parse(text):
    """返回 (精确/片段键 -> 行, 模板键集合)；键已小写。"""
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


raw = io.open(PATH, "rb").read()
assert b"\r" not in raw, "词库必须是 LF：发现 CR"
assert not raw.startswith(b"\xef\xbb\xbf"), "词库必须无 BOM：发现 UTF-8 BOM"

text = raw.decode("utf-8")
before_plain, before_tmpl = parse(text)

# ---- 1) 三处对齐（先做替换，断言命中次数）--------------------------------
for old, new in FIXUPS:
    assert text.count(old + "\n") == 1, "旧行未唯一命中:\n%s" % old
    text = text.replace(old + "\n", new + "\n")

# ---- 2) 新分节插到「可组合片段」机制节之前 -------------------------------
assert text.count(SECTION_HEADER) == 1, "找不到可组合片段节头"
text = text.replace(SECTION_HEADER, SECTION + "\n" + SECTION_HEADER)

# ---- 3) 写盘前断言 -------------------------------------------------------
after_plain, after_tmpl = parse(text)
want = {(("~" + k) if frag else k) for k, _, frag in NEW_ITEMS}
added = set(after_plain) - set(before_plain)
assert added == want, "新增键不是预期集合：多=%r 少=%r" % (sorted(added - want), sorted(want - added))
assert after_tmpl == before_tmpl, "模板集合被动到了"
assert len(after_plain) == len(before_plain) + len(NEW_ITEMS), "净增条目数不对"
keys = [l.split("=", 1)[0].strip().lower() for l in text.split("\n")
        if l.strip() and l.strip()[:1] not in ("#", ";") and "=" in l]
assert len(keys) == len(set(keys)), "出现重复键"
assert b"\r" not in text.encode("utf-8")

io.open(PATH, "wb").write(text.encode("utf-8"))

print("ok")
print("  新增 %d 条：%s" % (len(NEW_ITEMS), ", ".join(sorted(want))))
print("  对齐 %d 条旧译文" % len(FIXUPS))
print("  条目 %d -> %d" % (len(before_plain), len(after_plain)))
