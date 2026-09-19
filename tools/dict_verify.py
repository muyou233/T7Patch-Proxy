"""词库最终自检：条目数 / 最长行字节（<1024，避免 fgets 截断）/ 重复键 / 覆盖率 / 空值
/ 可组合片段审计。

⚠️ 词库已于 2026-09-16 入库：`translate/translate_zh.txt` 是**唯一源**，游戏目录那份是部署
产物。所以这里默认检查**源**（游戏目录那份只用于"部署后核对"，用 translate_sync.py status）。
报告第一行永远打印实际检查的路径 —— 之前默认查游戏目录，曾让"源 839 条 / 报告 838 条"
这种同名不同版本的读数把人绕进去过。

2026-09-18 新增：键以 `~` 开头 = **可组合片段**（允许在更长文本里被子串替换，见
src/translate.cpp 的 ComposeFragments）。本脚本剥掉标记后与普通条目一同入库，所以
覆盖率/重复键对两者一视同仁，但会**单独统计**并审出"过短 / 单词"这类高危片段。
"""
import os

from dict_lower import dict_lower

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
REPO = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private"
SRC_DICT = os.path.join(REPO, r"translate\translate_zh.txt")
GAME_DICT = os.path.join(GAME, r"T7Patch\translate_zh.txt")
DICT = SRC_DICT if os.path.exists(SRC_DICT) else GAME_DICT
OUT = os.path.join(REPO, r"tools\dict_verify.txt")

db = open(DICT, "rb").read()
linesb = db.split(b"\n")

entries, fragments, dups, badkey, emptyval = {}, [], [], [], []
longest = (0, "")
for ln in linesb:
    s = ln.rstrip(b"\r")
    if not s.strip() or s.lstrip()[:1] in (b"#", b";"):
        continue
    if b"=" not in s:
        badkey.append(s[:80])
        continue
    k, v = s.split(b"=", 1)
    k2, v2 = k.strip(), v.strip()
    if len(s) > longest[0]:
        longest = (len(s), s[:100])
    if not k2 or not v2:
        emptyval.append(s[:80])
    # 2026-09-18：改 UTF-8 解码 + 引擎口径小写（只动 A-Z）。原写法 decode("ascii","replace")
    # 会把非 ASCII 键字节变成 '?'、再用 Unicode 感知的 str.lower() 折叠大小写 ⇒
    # 把 `verrÜckt`(C3 9C) 与 `verrückt`(C3 BC) 误判成同一个键（假重复键）。详见 dict_lower.py。
    kk = dict_lower(k2.decode("utf-8", "replace"))
    # '~' 前缀 = 可组合片段：剥掉标记后照常入库，这样覆盖率和重复键检查对两者一致。
    if kk.startswith("~"):
        kk = kk[1:].lstrip(" \t")
        fragments.append(kk)
    if kk in entries:
        dups.append(kk)
    entries[kk] = v2

dump_keys = set()
for ln in open(DUMP, "rb").read().split(b"\n"):
    b = ln.rstrip(b"\r")
    i, j = 0, len(b)
    while i < j and b[i] <= 0x20:   # 控制字节与空格都裁（与运行时 NextRun 一致）
        i += 1
    while j > i and b[j - 1] <= 0x20:
        j -= 1
    b = b[i:j]
    if b and not any(c >= 0x80 for c in b) and not any(c < 0x20 for c in b) and not any(c in b"^$&" for c in b):
        dump_keys.add(b.decode("ascii", "replace").lower())

missing = sorted(dump_keys - set(entries))

out = []
out.append("检查：%s" % DICT)
out.append("词库条目 %d 条（其中可组合片段 %d 条）；最长行 %d 字节（fgets 缓冲 1024，必须 <1024）"
           % (len(entries), len(fragments), longest[0]))
out.append("最长行开头：%s" % longest[1])
out.append("重复键 %d 个：%s" % (len(dups), dups[:20]))
out.append("键不含 '=' 的行 %d 行；空键/空值 %d 条" % (len(badkey), len(emptyval)))
out.append("")

# 可组合片段审计（2026-09-18）：片段是唯一会在更长文本里替换的条目，所以"太短 / 单个词"
# 的片段风险最高（玩家名、地图名、工坊图名都会撞）。短于 3 的键运行时根本不加载。
out.append("=== 可组合片段（键以 ~ 标记，允许在更长文本内替换；共 %d 条）===" % len(fragments))
out.append("   " + ("  ".join(sorted(fragments)) if fragments else "(无)"))
risky = sorted(f for f in fragments if len(f) < 8 or len(f.split()) < 2)
if risky:
    out.append("   ⚠️ 可疑片段 %d 条（过短或单词，易误伤玩家名/地图名，须人工复核）：%s"
               % (len(risky), "  ".join(risky)))
out.append("")

# 极短键审计：整串匹配下，越短的键越容易在不同上下文里误伤（如 power/perk/bots）。
short = sorted(k for k in entries if len(k) <= 6)
out.append("=== 极短键（长度 <= 6，误伤风险最高的一批，共 %d 条）===" % len(short))
out.append("   " + "  ".join(short))
out.append("采集(干净)唯一串 %d 条 → 未覆盖 %d 条" % (len(dump_keys), len(missing)))
out.append("")
out.append("=== 仍未覆盖（应只剩专有名词/动态值）===")
out.extend(missing)
out.append("")
out.append("=== 逐条渲染抽查（取 8 条新加的）===")
for k in ["extra slots pack: increase the number of customizable create-a-class slots to 10 sets of slots, and significantly expands media storage and showcase storage by more than 3 times the number of slots for emblems, paintjobs, gunsmith variants, screenshots, films and custom games.",
          "heavily armored general infantry unit robot. can be set to guard mode to protect the owner or set to patrol mode to defend a designated location.",
          "enter", "level 46", "level 12", "prestige 6", "spm", "unbound"]:
    out.append("  %-40s -> %s" % (k[:40], entries.get(k, "<<缺失>>")))

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("written", OUT)
