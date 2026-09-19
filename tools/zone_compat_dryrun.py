# -*- coding: utf-8 -*-
"""zone_compat_dryrun.py - 只读预测 zone_compat 模块会做什么。

背景：工坊图按语言打包，引擎用「游戏启动时的语言」拼 zone 名
（`<lang>_zm_<map>.ff`），而作者可能只导出某一种语言 ⇒ 其他语言的玩家
直接报 `ERROR: Could not find zone 'sc_zm_...'` 进不去。

`src/zone_compat.cpp` 会在启动时把缺的那套从**任意已存在的语言**复制出来
（英文优先）。这个脚本**照抄那份 C++ 的判定逻辑**（语言探测两条路 + 复制前的
存在性检查），但**绝不写任何文件** —— 只打印「哪些会新增、哪些已存在」，
所以不用开游戏就能验证逻辑对不对。

用法：
    python zone_compat_dryrun.py [游戏目录]
    python zone_compat_dryrun.py --lang en          # 假装游戏跑的是英文
    python zone_compat_dryrun.py --workshop <目录>  # 换一个工坊根目录（自测用）
"""
import os
import sys

DEFAULT_GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"

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
# 与 C++ 的 kSourceOrder 一致：可作为「源」的语言顺序（en 优先）。
# 注意 sc/tc 也在内 —— 只打包了中文的图，同样要为英文客户端补出 en。
SOURCE_ORDER = KNOWN


def parse_args(argv):
    game, lang, workshop = DEFAULT_GAME, None, None
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--lang" and i + 1 < len(argv):
            lang = argv[i + 1]
            i += 2
            continue
        if a == "--workshop" and i + 1 < len(argv):
            workshop = argv[i + 1]
            i += 2
            continue
        game = a
        i += 1
    return game, lang, workshop


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


def scan(root, lang):
    """列出会新增/已存在的文件。返回 (planned, existing, items)。"""
    planned, existing, items = [], [], 0
    if not os.path.isdir(root):
        return planned, existing, items
    for item in sorted(os.listdir(root)):
        item_dir = os.path.join(root, item)
        if not os.path.isdir(item_dir) or item.startswith("."):
            continue
        items += 1
        names = set(os.listdir(item_dir))
        for src in SOURCE_ORDER:
            if src == lang:
                continue
            # 语言前缀型：<item>\<src>_x.ff -> <item>\<lang>_x.ff
            for name in sorted(names):
                if not name.lower().startswith(src + "_"):
                    continue
                if not os.path.isfile(os.path.join(item_dir, name)):
                    continue
                dest = os.path.join(item_dir, "%s_%s" % (lang, name[3:]))
                if not os.path.exists(dest) and dest not in planned:
                    planned.append(dest)
                elif os.path.exists(dest) and dest not in existing:
                    existing.append(dest)
            # 音效：<item>\snd\<src>\zm_x.<src>.sabl -> <item>\snd\<lang>\zm_x.<lang>.sabl
            snd = os.path.join(item_dir, "snd", src)
            if not os.path.isdir(snd):
                continue
            for name in sorted(os.listdir(snd)):
                infix = ".%s." % src
                if infix not in name:
                    continue
                head, _, tail = name.partition(infix)
                dest = os.path.join(item_dir, "snd", lang,
                                    "%s.%s.%s" % (head, lang, tail))
                if not os.path.exists(dest) and dest not in planned:
                    planned.append(dest)
                elif os.path.exists(dest) and dest not in existing:
                    existing.append(dest)
    return planned, existing, items


def main():
    game, forced_lang, forced_ws = parse_args(sys.argv)
    print("game folder : %s" % game)

    if forced_lang:
        lang, source = forced_lang, "forced by --lang"
    else:
        lang, source = detect_language(game)
    if not lang:
        print("language    : UNKNOWN -> the module would do nothing")
        return
    print("language    : %s  (from %s)" % (lang, source))

    root = os.path.normpath(forced_ws) if forced_ws else \
        os.path.normpath(os.path.join(game, WORKSHOP_REL))
    planned, existing, items = scan(root, lang)
    print("workshop    : %s" % root)
    print("items       : %d" % items)
    print("already ok  : %d" % len(existing))
    print("would add   : %d" % len(planned))
    for path in planned[:40]:
        print("   + %s" % path.replace(game, "<game>"))
    if len(planned) > 40:
        print("   ... and %d more" % (len(planned) - 40))


main()
