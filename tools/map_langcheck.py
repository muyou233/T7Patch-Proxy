# -*- coding: utf-8 -*-
"""map_langcheck.py - how much per-language content does each workshop item ship?

Read-only report.  Nothing is written into the game or the workshop folder.

Why this matters (2026-09-16, project log section 29):
BO3 keeps the CJK glyph atlas inside the *language-specific* zone file.  Proof
from the owner's own library: in the two "All-around Enhancement" mods the
Japanese/Chinese variants are 29.7 MB while every Latin language is 43-50 KB,
and only ja_/sc_/tc_ ever grow that way.  A mod that repacks the game's core or
UI assets while shipping a KB-sized sc_ file therefore has no Chinese glyphs to
draw with, and in a Chinese game its whole interface comes out as boxes.

Reading the verdict column:
  * core-repacking mods (core_mod / cp_mod / mp_mod ...) - the size of the
    language files IS the signal, because the game's UI fonts live in there.
  * plain map zones (zm_*) - a KB-sized language file is normal, a map simply
    has little text; it says nothing about the font.  Only a live test proves
    those.
"""

import json
import os
import re

ROOT = r"F:\SteamLibrary\steamapps\workshop\content\311210"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\map_langcheck.txt"

LANGS = ["bp", "ea", "en", "es", "fr", "ge", "it", "ja", "po", "ru", "sc", "tc"]
CJK = ("sc", "tc", "ja")
LANG_RE = re.compile(r"^([a-z]{2})_(.+)$")

GLYPH_MIN = 1 << 20      # 1 MiB: a real atlas is tens of MB, a stub is KB
CJK_RATIO = 4.0          # CJK variant this much bigger than the Latin ones?
CORE_HINT = ("core", "cp_", "mp_", "zm_")


def human(n):
    if n >= (1 << 20):
        return "%.1f MB" % (n / float(1 << 20))
    if n >= (1 << 10):
        return "%.1f KB" % (n / float(1 << 10))
    return "%d B" % n


def item_title(folder, fallback):
    path = os.path.join(folder, "workshop.json")
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                for key in ("title", "Title", "name", "Name"):
                    if data.get(key):
                        return str(data[key])
        except Exception:
            pass
    return fallback


def scan():
    """-> [(item_id, title, zone, {lang: size})]"""
    rows = []
    if not os.path.isdir(ROOT):
        return rows
    for item in sorted(os.listdir(ROOT)):
        folder = os.path.join(ROOT, item)
        if not os.path.isdir(folder):
            continue
        zones = {}
        for fn in os.listdir(folder):
            if not fn.lower().endswith(".ff"):
                continue
            stem = fn[:-3]
            try:
                size = os.path.getsize(os.path.join(folder, fn))
            except OSError:
                continue
            m = LANG_RE.match(stem)
            if m and m.group(1) in LANGS:
                zones.setdefault(m.group(2), {})[m.group(1)] = size
            else:
                zones.setdefault(stem, {})["base"] = size
        title = item_title(folder, item)
        for zone, langs in sorted(zones.items()):
            rows.append((item, title, zone, langs))
    return rows


def verdict(zone, langs):
    cjk = [langs[k] for k in CJK if k in langs]
    latin = [v for k, v in langs.items() if k not in CJK and k != "base"]
    cjk_max = max(cjk) if cjk else 0
    latin_max = max(latin) if latin else 0
    is_map = zone.startswith("zm_")
    if not cjk and not latin:
        return ("none", "该 zone 没有语言变体（单文件 zone）")
    if cjk_max >= GLYPH_MIN:
        return ("ok", "语言包 %s —— 符合「自带 CJK 字形」的特征" % human(cjk_max))
    if latin_max and cjk_max > latin_max * CJK_RATIO:
        return ("maybe", "中日文变体比拉丁大 %.0f 倍（%s vs %s）—— 可能含字形子集"
                % (cjk_max / float(latin_max), human(cjk_max), human(latin_max)))
    if is_map:
        return ("na", "语言包只有 %s —— 地图没什么文本属正常，中文能否显示要看实测"
                % human(max(cjk_max, latin_max)))
    return ("bad", "语言包只有 %s —— 这类 mod 重打包了游戏界面，却没有中文语言包"
            % human(max(cjk_max, latin_max)))


def main():
    rows = scan()
    lines = ["BO3 workshop mod / 地图 语言包体积清单（只读报告）",
             "根目录：%s" % ROOT,
             "判据：<语言>_<zone>.ff 是否装了该语言的字形图集（真含 = 十几 MB 以上，空壳 = 几 KB）",
             ""]
    tally = {}
    for item, title, zone, langs in rows:
        body = " | ".join("%s %s" % (k, human(v)) for k, v in sorted(langs.items()))
        tag, text = verdict(zone, langs)
        tally[tag] = tally.get(tag, 0) + 1
        lines.append("=== %s   %s" % (item, title))
        lines.append("    zone %s" % zone)
        lines.append("      %s" % body)
        lines.append("    判定：[%s] %s" % (tag, text))
        lines.append("")

    lines.append("--- 汇总：zone 共 %d 个" % len(rows))
    for tag in ("ok", "maybe", "bad", "na", "none"):
        if tag in tally:
            lines.append("      [%s] %d 个" % (tag, tally[tag]))
    lines.append("")
    lines.append("怎么读这张表：")
    lines.append("  1. 只有重打包游戏核心 / 界面的 mod（core_mod、cp_mod、mp_mod、zm_mod）")
    lines.append("     才会影响整个界面的字体 —— 这类 mod 的语言包是 KB 级，中文模式下")
    lines.append("     界面文字就没有字形可用，整屏方框。")
    lines.append("  2. 纯地图 zone（zm_xxx）的语言包是 KB 级属于正常 —— 地图本来就没多少")
    lines.append("     文本，这条不能拿来断定地图能不能用中文。")
    lines.append("  3. 体积只能说明「打包了什么」，最终结论请用一次实测确认：")
    lines.append("     把游戏语言切英文进同一张图，界面恢复正常即证明缺的是字形。")

    text = "\n".join(lines) + "\n"
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    main()
