r"""验证「启动语言门」：dll 里的字符串 + ReadGameLanguage 判定逻辑的复刻。

判定逻辑是按 src\translate.cpp 的 ReadGameLanguage / IsChineseGameLanguage
逐行复刻的（取首行、去 BOM、去首尾空格/制表符、转小写），用典型输入跑一遍，确认：
  * 中文（简体 simplifiedchinese / schinese、繁体 traditionalchinese / tchinese）
    -> 不动开关（2026-09-16 用户实切繁体，确认我们的简体译文在繁体包下正常渲染）
  * 其它语言（english / japanese / ...）-> 关闭
  * 读不到 / 首行空 -> 也算「非中文」-> 关闭（fail closed，同日拍板）
另外用本机真实的 localization.txt 首行验证「当前会被怎么判」。

2026-09-16 追加（用户拍板「直接关闭，要开启自己开启就是了」）：**明确读到**的非中文
语言除了本次会话抑制，还会被写回 conf（`translate=0`），所以 dll 里应能搜到
`start-up language gate: mod translation switched off in the config`；
「读不到」只抑制本次会话、不改玩家文件，其日志因此保留 `session only` 字样。
"""
import os

DLL = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\x64\Release\d3d11.dll"
GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
REPORT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\lang_probe2.txt"

data = open(DLL, "rb").read()
out = []
out.append("dll = %s" % DLL)
out.append("dll size = %d bytes" % len(data))
out.append("")
out.append("--- strings in the dll (utf-8) ---")

CHECKS = [
    ("new zh tooltip       ", "开启自动模组汉化（游戏必须为中文）", True),
    ("new en tooltip       ", "Enables automatic mod translation (the game must be set to Chinese).", True),
    ("gate log line (known)", "the game's own language is", True),
    ("gate log (known off) ", "not Chinese - mod translation switched off", True),
    ("gate log (unknown)   ", "cannot read the game's own language", True),
    ("gate log (session)   ", "session only", True),
    ("gate persist line    ", "start-up language gate: mod translation switched off in the config", True),
    ("localization.txt     ", "localization.txt", True),
    ("old gate wording gone", "stays off for this session", False),
    ("old log wording gone ", "not Simplified Chinese", False),
    ("old zh tooltip gone  ", "（游戏必须为简体中文）", False),
    ("old en tooltip gone  ", "the game must be set to Simplified Chinese)", False),
    ("old zh tooltip2 gone ", "本体与模组界面里的英文文本会被替换成中文", False),
    ("old en tooltip2 gone ", "Replaces English text in the base game and mods with Chinese.", False),
    ("old helper name gone ", "IsSimplifiedGameLanguage", False),
]
str_bad = 0
for name, s, want in CHECKS:
    got = data.find(s.encode("utf-8")) != -1
    ok = got == want
    str_bad += 0 if ok else 1
    out.append("  %s expect=%-5s got=%-5s %s" % (name, want, got, "OK" if ok else "!! FAIL"))


def first_line(raw):
    """Mirror of ReadGameLanguage: first line, BOM/space/tab trimmed, lower-cased."""
    end = 0
    while end < len(raw) and raw[end] not in (0x0D, 0x0A):
        end += 1
    begin = 0
    if end >= 3 and raw[0:3] == b"\xef\xbb\xbf":
        begin = 3
    while begin < end and raw[begin] in (0x20, 0x09):
        begin += 1
    while end > begin and raw[end - 1] in (0x20, 0x09):
        end -= 1
    if end <= begin:
        return None
    return raw[begin:end].decode("ascii", "replace").lower()


def gate(raw):
    """Mirror of the Init() gate: ANY Chinese pack leaves the switch alone."""
    lang = first_line(raw)
    if lang is None:
        return "no answer   -> switch OFF (fail closed)"
    if "chinese" in lang:
        return "CHINESE     -> leave the switch alone"
    return "NOT chinese -> switch OFF"


out.append("")
out.append("--- gate decisions (mirror of ReadGameLanguage / IsChineseGameLanguage) ---")
CASES = [
    (b"simplifiedchinese\r\n\r\nWIN_X\r\n", "simplifiedchinese", "leave"),
    (b"\xef\xbb\xbfsimplifiedchinese\n", "bom+simplifiedchinese", "leave"),
    (b"schinese\n", "schinese (steam short)", "leave"),
    (b"TraditionalChinese\r\n", "TraditionalChinese", "leave"),
    (b"traditionalchinese\n", "traditionalchinese", "leave"),
    (b"tchinese\n", "tchinese (steam short)", "leave"),
    (b"english\r\n\r\nWIN_X\r\n", "english", "OFF"),
    (b"english\n", "english (lf only)", "OFF"),
    (b"  english  \r\n", "padded english", "OFF"),
    (b"japanese\n", "japanese", "OFF"),
    (b"koreana\n", "koreana", "OFF"),
    (b"russian\n", "russian", "OFF"),
    (b"", "empty file", "OFF"),
    (b"\r\nWIN_X\r\n", "blank first line", "OFF"),
    (b"   \r\n", "spaces only", "OFF"),
]
dec_bad = 0
for raw, label, want in CASES:
    got = gate(raw)
    ok = (want == "leave") == got.startswith("CHINESE")
    dec_bad += 0 if ok else 1
    out.append("  %-24s -> %-34s %s"
               % (label, got, "OK" if ok else "!! FAIL (want %s)" % want))

out.append("")
out.append("--- live game file on this machine ---")
p = os.path.join(GAME, "localization.txt")
if os.path.exists(p):
    raw = open(p, "rb").read(128)
    out.append("  %s" % p)
    out.append("  first line = %r" % first_line(raw))
    out.append("  decision   = %s" % gate(raw))
else:
    out.append("  MISSING: %s" % p)

out.append("")
if str_bad == 0 and dec_bad == 0:
    out.append("RESULT: OK")
else:
    out.append("RESULT: %d STRING + %d DECISION CHECK(S) FAILED" % (str_bad, dec_bad))

with open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
print("report -> %s" % REPORT)
