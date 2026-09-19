# -*- coding: utf-8 -*-
"""zone_compat_dryrun.py - 只读预测 zone_compat 模块会做什么。

背景：工坊图按语言打包，引擎用「游戏启动时的语言」拼 zone 名
（`<lang>_zm_<map>.ff`），而多数作者只导出英文那一套 ⇒ 非英文玩家
直接报 `ERROR: Could not find zone 'sc_zm_...'` 进不去。

`src/zone_compat.cpp` 会在启动时把缺的那套从英文复制出来。这个脚本**照抄那份
C++ 的判定逻辑**（语言探测两条路 + 复制前的存在性检查），但**绝不写任何文件**
—— 只打印「哪些会新增、哪些已存在」，所以不用开游戏就能验证逻辑对不对。

用法：python zone_compat_dryrun.py [游戏目录]
"""
import os
import sys

GAME = sys.argv[1] if len(sys.argv) > 1 else \
    r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"

# 与 C++ 的 kWorkshopRel 一致：<steam>\steamapps\workshop\content\<appid>
WORKSHOP_REL = os.path.join("..", "..", "workshop", "content", "311210")

PAIRS = {
    "english": "en", "french": "fr", "italian": "it", "german": "ge",
    "spanish": "es", "russian": "ru", "polish": "pl", "japanese": "jp",
    "koreana": "ko", "simplifiedchinese": "sc", "traditionalchinese": "tc",
    "portuguese": "bp",
}
KNOWN = ["en", "fr", "it", "ge", "es", "ru", "pl",
         "jp", "ko", "sc", "tc", "bp", "ea"]


def read_language_name(game):
    """localization.txt 首行（去掉 BOM/空白/换行），小写。"""
    path = os.path.join(game, "localization.txt")
    try:
        with open(path, "rb") as fh:
            raw = fh.read(128)
    except OSError:
        return None
    line = raw.split(b"\r")[0].split(b"\n")[0]
    if line.startswith(b"\xef\xbb\xbf"):
        line = line[3:]
    name = line.decode("ascii", "replace").strip().lower()
    return name or None


def detect_from_zone_dir(game):
    """兜底：zone 目录里出现最多的已知语言前缀 = 游戏语言。"""
    zone = os.path.join(game, "zone")
    counts = {}
    try:
        entries = os.listdir(zone)
    except OSError:
        return None
    for name in entries:
        if len(name) < 3 or name[2] != "_":
            continue
        two = name[:2].lower()
        if two in KNOWN:
            counts[two] = counts.get(two, 0) + 1
    if not counts:
        return None
    best = max(counts.items(), key=lambda kv: kv[1])
    return best[0], counts


def detect_language(game):
    name = read_language_name(game)
    prefix = PAIRS.get(name) if name else None
    source = "localization.txt (%s)" % name if prefix else None
    if prefix is None:
        fallback = detect_from_zone_dir(game)
        if fallback:
            prefix, counts = fallback
            source = "zone folder probe (%s)" % ", ".join(
                "%s x%d" % (k, v) for k, v in sorted(counts.items(),
                                                     key=lambda kv: -kv[1]))
    return prefix, source


def scan(game, lang):
    """列出会新增/已存在的文件。返回 (planned, existing)。"""
    planned, existing, items = [], [], 0
    root = os.path.normpath(os.path.join(game, WORKSHOP_REL))
    if not os.path.isdir(root):
        return planned, existing, items, root
    for item in sorted(os.listdir(root)):
        item_dir = os.path.join(root, item)
        if not os.path.isdir(item_dir) or item.startswith("."):
            continue
        items += 1
        # 语言前缀型：<item>\en_x.ff -> <item>\<lang>_x.ff
        for name in sorted(os.listdir(item_dir)):
            src = os.path.join(item_dir, name)
            if not os.path.isfile(src) or not name.lower().startswith("en_"):
                continue
            dest = os.path.join(item_dir, "%s_%s" % (lang, name[3:]))
            (existing if os.path.exists(dest) else planned).append(dest)
        # 音效：<item>\snd\en\zm_x.en.sabl -> <item>\snd\<lang>\zm_x.<lang>.sabl
        snd = os.path.join(item_dir, "snd", "en")
        if os.path.isdir(snd):
            for name in sorted(os.listdir(snd)):
                if ".en." not in name:
                    continue
                head, _, tail = name.partition(".en.")
                dest = os.path.join(item_dir, "snd", lang,
                                    "%s.%s.%s" % (head, lang, tail))
                (existing if os.path.exists(dest) else planned).append(dest)
    return planned, existing, items, root


def main():
    print("game folder : %s" % GAME)
    lang, source = detect_language(GAME)
    if not lang:
        print("language    : UNKNOWN -> the module would do nothing")
        return
    print("language    : %s  (from %s)" % (lang, source))
    if lang == "en":
        print("              -> English: authors ship en_, nothing to add")
        return

    planned, existing, items, root = scan(GAME, lang)
    print("workshop    : %s" % root)
    print("items       : %d" % items)
    print("already ok  : %d" % len(existing))
    print("would add   : %d" % len(planned))
    for path in planned[:40]:
        print("   + %s" % path.replace(GAME, "<game>"))
    if len(planned) > 40:
        print("   ... and %d more" % (len(planned) - 40))


main()
