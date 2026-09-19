r"""en_gap.py - list every Chinese string the English fallback still cannot handle.

Reads the table the patch ships (translate_en.txt) plus the collected game
strings (ui_dump.txt), replays the engine's own longest-match walk over each of
them, and prints the ones that still contain untranslated Chinese.  That list IS
the worklist - everything on it is a word or phrase missing from the table.

The point is to stop fixing this one screenshot at a time: run the game once
with dev_tools on, run this, and the whole remaining gap arrives in one go.

    python en_gap.py [--min N] [--limit N]
"""

import io
import os
import re
import sys
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
TABLE = os.path.join(HERE, "..", "translate", "translate_en.txt")

# Where the game keeps its collected strings.
GAME_DIRS = [
	r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\T7Patch",
]
DUMP_NAME = "ui_dump.txt"

HAN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")

# Mirrors AsciiForFullWidth() in src/translate.cpp - these are replaced, so they
# are not "missing words".
FULL_WIDTH = set("，。！？：；、（）「」『』【】《》—–～…　“”‘’％")

# How the engine walks a string (RenderEnglish): a whole string of exactly one
# character may use a one-character entry; inside a longer string matching
# starts at two characters.  2026-09-20: the engine ceiling is 45 BYTES, i.e.
# 15 Han characters - phrases longer than that could never match as a whole.
MAX_WORD = 15


def load_table(path):
	table = {}
	if not os.path.exists(path):
		sys.exit("missing table: %s" % os.path.normpath(path))
	with io.open(path, "r", encoding="utf-8", newline="") as fh:
		for raw in fh:
			line = raw.rstrip("\r\n")
			if not line or line.startswith("#") or "=" not in line:
				continue
			k, v = line.split("=", 1)
			table[k] = v
	return table


def render(s, table):
	"""Return (text, leftover_chinese, unknown_pieces)."""
	if len(s) == 1 and s in table:
		return table[s], 0, []

	out = []
	leftover = 0
	pieces = []
	i = 0
	while i < len(s):
		best = None
		bl = 0
		for L in range(2, MAX_WORD + 1):
			if i + L <= len(s) and s[i:i + L] in table:
				best = table[s[i:i + L]]
				bl = L
		if bl:
			out.append(best)
			i += bl
			continue

		ch = s[i]
		out.append(ch if ch in FULL_WIDTH else ch)
		if HAN.match(ch):
			leftover += 1
			# Extend the unknown piece as far as it goes - the whole run is
			# what the translator actually needs to see.
			j = i
			while j < len(s) and HAN.match(s[j]):
				j += 1
			pieces.append(s[i:j])
			i = j
		else:
			i += 1
	return "".join(out), leftover, pieces


def find_dump():
	for d in GAME_DIRS:
		p = os.path.join(d, DUMP_NAME)
		if os.path.exists(p):
			return p
	p = os.path.join(HERE, DUMP_NAME)
	return p if os.path.exists(p) else None


def main():
	args = sys.argv[1:]
	min_chars = 1
	limit = 200
	for i, a in enumerate(args):
		if a == "--min" and i + 1 < len(args):
			min_chars = int(args[i + 1])
		if a == "--limit" and i + 1 < len(args):
			limit = int(args[i + 1])

	table = load_table(TABLE)
	dump = find_dump()
	if not dump:
		sys.exit("no %s found" % DUMP_NAME)

	seen = set()
	clean_rows = []   # pure Chinese: definitely missing from the table
	mixed_rows = []   # Chinese + Latin: usually a translated string collected again
	piece_count = collections.Counter()
	mixed_piece = collections.Counter()   # the same, but from the mixed strings
	LATIN = re.compile(r"[A-Za-z]")

	with io.open(dump, "rb") as fh:
		for raw in fh:
			t = raw.rstrip(b"\r\n").decode("utf-8", "replace")
			if not t or not HAN.search(t) or t in seen:
				continue
			seen.add(t)
			_, leftover, pieces = render(t, table)
			if leftover < min_chars:
				continue
			# A string that still has Latin in it was very likely written BY the
			# fallback earlier in the session and collected on a later draw - the
			# dump holds both.  Those are not missing words, so they are kept
			# apart rather than mixed into the worklist.
			#
			# Their Chinese pieces are still counted, though, and that matters:
			# the labels the game builds itself ("Press ^3F^7 to Drink a Perk")
			# arrive with a colour code in the middle, so they are "mixed" by
			# this test even though nothing has translated them yet.  Dropping
			# them here is exactly how a word like 喝下 stayed invisible for so
			# long - it never appears in a pure-Chinese string.
			if LATIN.search(t):
				mixed_rows.append((leftover, t))
				for p in pieces:
					mixed_piece[p] += 1
				continue
			clean_rows.append((leftover, t))
			for p in pieces:
				piece_count[p] += 1

	clean_rows.sort(key=lambda r: (-r[0], r[1]))

	print("table entries : %d" % len(table))
	print("collected     : %d distinct strings" % len(seen))
	print("missing words : %d pure-Chinese strings (>= %d char)" % (len(clean_rows), min_chars))
	print("(%d strings mix in Latin - re-collected output, or game labels with a "
		"colour code in them)" % len(mixed_rows))
	print()
	print("=== 缺的中文片段（按出现次数，取自纯中文串）===")
	for piece, n in piece_count.most_common(80):
		print("  %4d  %s" % (n, piece))
	print()
	print("=== 缺的中文片段（来自含拉丁字符的串；此处多为游戏自带标签）===")
	for piece, n in mixed_piece.most_common(60):
		print("  %4d  %s" % (n, piece))
	print()
	print("=== 纯中文缺口（前 %d 条）===" % limit)
	for leftover, t in clean_rows[:limit]:
		print("  [%2d] %s" % (leftover, t[:110]))


main()
