"""修正「道具 / 泡泡糖名」分节的依据注释（2026-09-18 第二稿）。

上一稿写的“灰机未收录（Peek Me Pookie / Gum Gobbler）⇒ 保留原文”是**结论对、理由错**：
经三层溯源与采集上下文复核，这两个名字根本不是道具：
  · Peek Me Pookie —— 采集里四周全是玩家名（Ouicho / #Mr.Nilsson# / "Last met …" 社交面板串）⇒ 玩家昵称；
  · Gum Gobbler    —— 词库「挑战/勋章」节里已译作“泡泡糖狂人”，是挑战名，不是泡泡糖。
注释要写对，否则下一个人会照错的理由继续判。

同时记录三层溯源的实际执行情况（供以后复用）：
  ① 灰机 wiki（cod.huijiwiki.com）—— 给出本节权威中文名；
  ② Fandom 中文维基 —— **本机代理下持续超时**，改用中文资料站 + 英文完整清单替代；
  ③ B站 —— 按英文原名搜，拿不到样本（老实说拿不到，不硬凑）。
"""
import io
import os

REPO = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private"
PATH = os.path.join(REPO, r"translate\translate_zh.txt")

OLD = """# ⚠️ 灰机未收录的名字（Peek Me Pookie / Gum Gobbler）**不硬译**，保留原文（歧义规则）。
# ⚠️ 上下文是玩家名的 token（Little Boy / Flash）**不是道具**，不在此翻译。
"""

NEW = """# ⚠️ 三个「看着像道具、其实不是」的 token —— 别再误判（判据都是采集里的上下文）：
#    · Peek Me Pookie —— 四周全是玩家名（Ouicho / #Mr.Nilsson# / "Last met …" 社交面板）⇒ **玩家昵称**，不翻；
#    · Little Boy / Flash —— 同上，玩家名，不翻；
#    · Gum Gobbler —— 是**挑战/勋章名**（词库「挑战」节已译作“泡泡糖狂人”），**不是泡泡糖**，不属本节。
# 译名依据（技能规则：灰机 > Fandom 中文维基 > B站，逐层下探；本次实际执行情况）：
#    · 灰机《GobbleGum(ZM)》《Winter's Howl(奇迹武器)》—— 给出本节全部权威中文名；
#    · Fandom 中文维基 —— **本机代理下持续超时**，故用英文完整清单（zombiescodex BO3 全表）交叉确认
#      “Gum Gobbler / Peek Me Pookie 都不在泡泡糖名单里”；
#    · 中文资料站（任地鱼 2015 泡泡糖一览）的译名是社区幽默译法（In Plain Sight=一马平川、
#      Stock Option=枪托藏子弹、Always Done Swiftly=随时走位都风骚）⇒ **不作依据**，只当反向佐证；
#    · B站 —— 按英文原名搜拿不到样本（不硬凑）。
"""

raw = io.open(PATH, "rb").read()
assert b"\r" not in raw, "词库必须是 LF：发现 CR"
text = raw.decode("utf-8")

assert text.count(OLD) == 1, "目标注释块未唯一命中"
new_text = text.replace(OLD, NEW)

# 只改注释：条目集合必须完全不变
def keys_of(t):
    out = []
    for line in t.split("\n"):
        s = line.strip()
        if not s or s[:1] in ("#", ";") or "=" not in line:
            continue
        out.append(line.split("=", 1)[0].strip().lower())
    return out

assert keys_of(new_text) == keys_of(text), "注释修正不该动到任何条目"
assert b"\r" not in new_text.encode("utf-8")

io.open(PATH, "wb").write(new_text.encode("utf-8"))
print("ok  注释已修正；条目 %d 条不变；文件 %d -> %d 字节"
      % (len(keys_of(text)), len(raw), len(new_text.encode("utf-8"))))
