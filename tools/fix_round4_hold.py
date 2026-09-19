# -*- coding: utf-8 -*-
r"""修 dict_add4 漏掉的 "hold " 前缀。

字典里的键必须逐字节等于引擎送的**整个片段**。这一轮 17 条交互提示里，
两条 "Press ..." 和两条 "Reload" 我写对了，但那 15 条 "Hold ^3F^7 ..." 的键
被我从 ^3F 开始写（漏掉了开头的 "hold "）⇒ 逐条命验全是 MISS。

修两处：① 词库文件里那 15 行；② dict_add4.py 的表格（保持每轮脚本可重放）。
顺手把版本行 e -> f。
"""
import io

DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
ADD = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\dict_add4.py"
REPORT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\fix_round4_hold.txt"

raw = io.open(DICT, "rb").read()
EOL = b"\r\n" if b"\r\n" in raw else b"\n"
# 17 条提示里只有 14 条以 "Hold" 开头（另 1 条 Press、2 条 Reload 当初就写对了）
bad = EOL + b"^3f^7 "
n_bad = raw.count(bad)
good = EOL + b"hold ^3f^7 "
assert n_bad == 14, "词库里以 ^3f^7 开头的行数不是 14，而是 %d" % n_bad
assert raw.count(good) == 0, "已经有 hold ^3f^7 了，别重复加"
raw2 = raw.replace(bad, good)
assert raw2.count(good) == 14
assert b"# version: 2026-09-16e" in raw2
raw2 = raw2.replace(b"# version: 2026-09-16e", b"# version: 2026-09-16f", 1)
io.open(DICT, "wb").write(raw2)

src = io.open(ADD, encoding="utf-8").read()
n_src = src.count('"^3f^7 ')
assert n_src == 14, "dict_add4.py 里 \"^3f^7 出现 %d 次（期望 14）" % n_src
src2 = src.replace('"^3f^7 ', '"hold ^3f^7 ')
assert src2.count('"hold ^3f^7 ') == 14
io.open(ADD, "w", encoding="utf-8", newline="").write(src2)

io.open(REPORT, "w", encoding="utf-8").write(
    "词库：%d 行补上 hold 前缀，%d -> %d 字节，版本 e -> f\n"
    "dict_add4.py：%d 处表格同步修正\nEOL=%r\n"
    % (n_bad, len(raw), len(raw2), n_src, EOL))
print("fixed %d dict lines, %d script entries" % (n_bad, n_src))
