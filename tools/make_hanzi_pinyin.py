#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build translate/translate_pinyin.txt - one Han character -> its pinyin.

Why this exists (2026-09-20, user's final decision)
---------------------------------------------------
The map-safe switch renders Chinese by replacing each Han character with its
pinyin, one character at a time.  Per-character replacement cannot reorder a
sentence the way English translation can, needs no phrase table, and covers
every character it lists - so nothing is ever left as boxes on a map whose own
font carries Latin glyphs only.

Scope: GB2312 level 1 + 2 only (6763 characters).  The user asked to skip
rare ideographs - this game never prints them, and the runtime table the
render path walks is smaller for it.  GB2312 covers every character in
common use, which is exactly the filter "no rare characters" means.

Output format:  <character>=<PinYin>, one per line, '#' starts a comment.
Each syllable is capitalised ("An"); the engine puts the spaces between
syllables itself, so the table stays one syllable per entry.

Multi-pronunciation characters (多音字): a lone character gets its most common
reading, which is often wrong in context ("重建" is Chong Jian, never Zhong).
The PHRASES list below carries the common phrase readings - pypinyin reads the
whole phrase with context - and the engine matches phrases (longest first)
BEFORE single characters.
"""

import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "translate", "translate_pinyin.txt")

# The basic CJK block.  Extension A is left out: those characters are rare by
# definition, and every entry costs memory in the runtime table.
START, END = 0x4E00, 0x9FFF

# Phrases whose reading differs from the per-character default.  pypinyin reads
# the whole phrase with context, so just listing the phrase fixes the reading.
# Game-flavoured first (重建障碍 is a Zombies staple); extend as reports come in
# - the table hot-reloads.
PHRASES = [
	"重建", "重新", "重复", "重庆", "重量", "重要", "沉重", "重量级",
	"长大", "生长", "队长", "家长", "增长", "长江", "长城",
	"银行", "行李", "行业", "行列", "行列式",
	"音乐", "乐器", "乐器行", "快乐", "乐趣", "乐园", "娱乐",
	"发现", "头发", "出发", "发射",
	"干净", "干燥", "干活", "干部", "能干", "骨干",
	"还有", "归还", "还钱", "还原",
	"歌曲", "弯曲", "曲线", "扭曲",
	"参加", "参与", "人参", "参照",
	"差别", "出差", "差不多", "参差",
	"教学", "教育", "教书",
	"下降", "降落", "投降", "降低",
	"系统", "关系", "联系", "系鞋带",
	"效率", "效率高", "率领", "概率", "利率",
	"弹药", "弹簧", "弹跳", "弹力", "弹壳", "子弹",
	"调整", "调节", "调查", "音调", "声调", "空调",
	"种子", "种类", "种类多", "种植", "种地",
	"爱好", "好奇", "喜好",
	"应该", "答应", "反应", "应答",
	"倒下", "颠倒", "倒计时",
	"省份", "反省", "节省",
	"风扇", "扇区",
	"数学", "数量", "数字", "数数",
	"宿舍", "星宿",
	"宝藏", "西藏", "收藏", "躲藏", "埋藏",
	"挣扎", "扎针", "扎根",
	"强大", "强壮", "勉强", "倔强", "强调",
	"一切", "切开", "切割", "切换", "切除",
	"宁静", "安宁", "宁可",
	"折断", "折磨", "折腾", "折扣", "曲折",
	"处理", "相处", "到处", "四处", "住处", "好处",
	"相互", "相同", "相反", "相片",
	"喝水", "喝彩", "喝下",
	"荷花", "负荷", "荷载",
	"卡片", "关卡", "卡住",
	"奇怪", "奇数", "传奇", "奇迹",
	"角度", "角色", "主角", "角落", "三角",
	"解决", "理解", "押解", "解释",
	"禁止", "禁用", "情不自禁",
	"埋伏", "埋怨", "掩埋",
	"闷热", "烦闷", "苦闷",
	"灾难", "遇难", "难民", "困难", "疑难",
	"散步", "分散", "散开", "散弹",
	"扫帚", "打扫", "扫描",
	"回答", "答疑", "报答",
	"混乱", "混入", "混合",
	"上当", "当时", "当年", "当作", "恰当", "适当",
	"担心", "承担", "重担",
	"了解", "了不起",
	"看守", "看管", "看门",
	"积累", "劳累", "累赘", "累计",
	"提供", "供品", "供给",
	"屏幕", "屏息", "屏住",
	"创造", "创作", "创伤", "重创",
	"首都", "都市", "都会",
	"方便", "便利", "便宜",
	"薄弱", "单薄",
	"重启", "重装", "重创", "重构",
	"存活", "生存", "存活率",
]


def to_camel(syl_list):
	return " ".join("".join(part.capitalize() for part in s) for s in syl_list)


def main():
    try:
        from pypinyin import pinyin, Style
    except ImportError:
        sys.exit("pypinyin is required: pip install pypinyin")

    rows = []

    # Phrase entries first: the engine matches longest-first, so a phrase
    # reading ("重建=Chong Jian") always beats the single characters inside it.
    for phrase in PHRASES:
        try:
            syl = pinyin(phrase, style=Style.NORMAL, errors="ignore")
        except Exception:
            continue
        if not syl or len(syl) != len(phrase):
            continue
        rows.append("%s=%s" % (phrase, to_camel(syl)))

    for cp in range(START, END + 1):
        ch = chr(cp)
        # GB2312 membership IS the "common use" filter the user asked for:
        # level 1 (3755 frequent) + level 2 (3008 less frequent), everything
        # rarer - the actual rare ideographs - fails the encode and is skipped.
        try:
            ch.encode("gb2312")
        except UnicodeEncodeError:
            continue

        # Style.NORMAL keeps it plain ASCII - tone marks would be unrenderable
        # by the very font this table exists for.
        try:
            syl = pinyin(ch, style=Style.NORMAL, errors="ignore")
        except Exception:
            continue
        if not syl or not syl[0] or not syl[0][0]:
            continue
        word = "".join(part.capitalize() for part in syl[0])
        if not word:
            continue
        rows.append("%s=%s" % (ch, word))

    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# [LOCAL] One Han character -> pinyin, for the map-safe switch.\n")
        fh.write("# Generated by tools/make_hanzi_pinyin.py - do not edit by hand.\n")
        fh.write("#\n")
        fh.write("# GB2312 level 1+2 only (6763 characters): the user asked to skip\n")
        fh.write("# rare ideographs, this game never prints them.  Every listed\n")
        fh.write("# character is replaced by its pinyin (camel case, spaced by the\n")
        fh.write("# engine), which any Latin font can draw.\n")
        for line in rows:
            fh.write(line + "\n")

    print("characters : %d" % len(rows))
    print("out        : %s" % os.path.normpath(OUT))


if __name__ == "__main__":
    main()
