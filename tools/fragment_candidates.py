r"""片段候选自动发现 —— 扫采集文件，找出"该把哪个精确键升格成片段（~）"。

## 它解决什么
用户诉求：`Girls' Frontline: Black Ops III 2.0` 这类**组合**不要再逐条补词库。
片段机制（键以 `~` 开头）已经能做到"一次标记、覆盖所有未来组合"，但**该标记哪个**以前只能人肉翻工作清单。
本脚本把这件事自动化：凡是"当前没命中、但内部**包含**某个已知精确键"的采集串，就是活生生的证据，
说明那个键值得标成片段。

## 与 dict_triage.py 的分工（方向相反，谁也替代不了谁）
    dict_triage.py :  词库 → 采集串    "这条采集串里有没有片段/精确键？"   （正向，分桶）
    本脚本         :  采集串 → 词库    "这条**没命中**的串里，藏着该升格的精确键吗？"（反向，发现）

## 前提：采集文件（**本脚本替代不了它**）
`ui_dump.txt` 由游戏侧写：`<游戏>\T7Patch\t7patch.conf` 里 `dump_ui_strings=1`
（实现在 `src/translate.cpp` 的 `g_collect` / `RecordCollected`，只记 distinct 串）。
**本脚本是那份文件的离线消费者**：没有采集就没有输入，它不能替代采集接口 —— 采集是眼睛，这个脚本是脑子。
只吃旧快照也能跑，但发现不了新内容。

## 输出
`ref/fragment_candidates.txt`
  A. 升格建议：`~键` + 命中条数 + 证据原串（排除玩家聊天 / 引擎模板变量 / 以标点结尾的键）
  B. 全新专名候选：反复出现、词库完全没有的多词 Title Case 短语 —— **只报候选，禁止直接翻译**，
     拿英文原名去灰机 / Fandom 中文站查权威中文（技能里"歧义译名规则"）。
  C. 被过滤掉的命中（玩家聊天 / 模板变量）——留作人工过目，避免"静默漏掉真的该升格的键"。

只读：绝不改词库、绝不改采集文件。用法：python fragment_candidates.py
"""
import os
import re

from dict_lower import dict_lower

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\fragment_candidates.txt"

# 升格门槛 —— 与 skill 的片段硬约定一致（单词键绝不升格：会误伤玩家名）
MIN_LEN = 8          # 与 dict_verify.py 的片段审计同门槛
MIN_WORDS = 2
MAX_WORDS = 4        # 超过 4 词的基本是整句，不该当专名
BAD_CHARS = "^$%&"   # 格式码 / 模板变量符号
BAD_TAIL = ":,.;?!"  # 以标点结尾的键是被更长的 UI 标签截出来的前缀，升格会出双标点


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


def is_engine_template(txt):
    """引擎变量占位串（`Party Privacy: $(PartyPrivacy.privacyStatus)`）—— 升格只会得到半截中文。"""
    return "$(" in txt or "%)" in txt or "$" in txt


def is_chat_like(txt):
    """疑似玩家聊天：整串无格式码、以小写开头、词数多。UI 标签不会长这样。"""
    if "^" in txt or is_engine_template(txt):
        return False
    words = txt.split()
    return len(words) >= 5 and txt[:1].islower()


# ------------------------------------------------------------------ 词库
raw = open(DICT, "rb").read()
exact, patterns, fragments = set(), [], set()
for line in raw.split(b"\n"):
    s = line.lstrip(b" \t").rstrip(b"\r")
    if not s or s[:1] in (b"#", b";") or b"=" not in s:
        continue
    # 引擎口径的小写（只动 A-Z）—— 见 dict_lower.py
    k = dict_lower(s.split(b"=", 1)[0].rstrip(b" \t").decode("utf-8", "replace"))
    if not k:
        continue
    if k.startswith("~"):
        fragments.add(k[1:].lstrip(" \t"))
    elif "*" in k:
        patterns.append(re.compile("^" + re.escape(k).replace(r"\*", ".*") + "$"))
    else:
        exact.add(k)


def matched(key):
    """当前词库能不能吃到这条串（精确 / 模板 / 片段三通道，与引擎同序）。"""
    if key in exact or any(p.match(key) for p in patterns):
        return True
    return any(f in key for f in fragments)


# ---------------------------------------------------------- 可升格的精确键
def promotable(k):
    if len(k) < MIN_LEN or k[-1] in BAD_TAIL:
        return False
    if any(c in k for c in BAD_CHARS):
        return False
    words = k.split()
    return MIN_WORDS <= len(words) <= MAX_WORDS


cands = {k: [] for k in exact if promotable(k)}
filtered = {}             # 命中但被排除的：键 -> [(串, 原因)]
total, miss = 0, 0
new_strings = []
seen = set()

for line in read_lines(DUMP):
    s = strip_wrap(line.rstrip(b"\r"))
    if not s or any(c >= 0x80 or c < 0x20 for c in s):
        continue
    low = s.lower()
    if low in seen:
        continue
    seen.add(low)
    total += 1
    key = low.decode("ascii", "replace")
    if matched(key):
        continue
    miss += 1
    txt = s.decode("ascii", "replace")
    new_strings.append(txt)
    why = "引擎模板变量" if is_engine_template(txt) else ("疑似玩家聊天" if is_chat_like(txt) else None)
    for k in cands:
        if k in key:
            if why:
                filtered.setdefault(k, []).append((txt, why))
            else:
                cands[k].append(txt)

ranked = sorted(((k, v) for k, v in cands.items() if v), key=lambda kv: (-len(kv[1]), kv[0]))

# ------------------------------------------------ B 段：全新专名候选（n-gram）
TITLE = re.compile(r"[A-Z][a-z']+(?:\s+[A-Z][a-z']+){1,3}")


def gram_is_proper(txt, m):
    """过滤"句中大写词"与人名：[GRaf]Arcus Cosinus（公会标签）、muyou And My Access Level（句中 And）。"""
    i = m.start()
    if i > 0 and txt[i - 1] == "]":          # [TAG]Name ⇒ 玩家名
        return False
    if i > 0:
        prev = txt[:i].rstrip()
        if prev and prev[-1].isalpha():       # 紧贴字母（无空格）
            return False
        token = prev.split()[-1] if prev.split() else ""
        if len(token) > 2 and token.islower():  # 前一个词是小写单词 ⇒ 句中大写，不是专名开头
            return False
    return True


gram = {}
for txt in new_strings:
    if is_chat_like(txt):
        continue
    for m in TITLE.finditer(txt):
        if not gram_is_proper(txt, m):
            continue
        g = m.group(0).lower()
        if len(g) < MIN_LEN or matched(g):
            continue
        if any(g in f or f in g for f in fragments):
            continue
        gram.setdefault(g, []).append(txt)
gram = {g: v for g, v in gram.items() if len(v) >= 2}
ranked_gram = sorted(gram.items(), key=lambda kv: (-len(kv[1]), kv[0]))

# ------------------------------------------------------------------ 报告
out = []
out.append("# 片段候选自动发现（只读报告，不代表已改动）")
out.append("# 采集：%s" % DUMP)
out.append("# 词库：%d 精确 + %d 模板 + %d 片段；采集 %d 条唯一串，其中 %d 条当前未命中"
           % (len(exact), len(patterns), len(fragments), total, miss))
out.append("")
out.append("## A. 升格建议（把下列精确键标成 `~` 片段；多词键，符合片段硬约定）")
out.append("")
if not ranked:
    out.append("（无）")
for k, v in ranked:
    out.append("- `~%s`  命中 %d 条" % (k, len(v)))
    for t in v[:3]:
        out.append("    例：%s" % t)
    if len(v) > 3:
        out.append("    （另有 %d 条同类）" % (len(v) - 3))
out.append("")
out.append("## B. 全新专名候选（词库完全没有、且反复出现 —— **只报候选，禁止直接翻译**）")
out.append("##    下一步：拿英文原名去灰机 / Fandom 中文站查权威中文，查不到就保留原文。")
out.append("")
if not ranked_gram:
    out.append("（无）")
for g, v in ranked_gram[:40]:
    out.append("- `%s`  出现 %d 条   例：%s" % (g, len(v), v[0]))
if len(ranked_gram) > 40:
    out.append("（另有 %d 个）" % (len(ranked_gram) - 40))
out.append("")
out.append("## C. 被排除的命中（玩家聊天 / 引擎模板变量）—— 人工过目，防止真候选被静默漏掉")
out.append("")
if not filtered:
    out.append("（无）")
for k in sorted(filtered):
    for txt, why in filtered[k][:2]:
        out.append("- `%s`（%s）例：%s" % (k, why, txt))

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out) + "\n")

print("written %s" % OUT)
print("  采集 %d 条唯一串 / 未命中 %d 条" % (total, miss))
print("  A 升格建议 %d 个键" % len(ranked))
print("  B 全新专名候选 %d 个" % len(ranked_gram))
print("  C 被排除 %d 个键" % len(filtered))
for k, v in ranked[:12]:
    print("   ~%-38s 命中 %d" % (k, len(v)))
