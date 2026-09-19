# -*- coding: utf-8 -*-
r"""词库排版小修：小节标题前的空行（纯样式，不动任何条目）。

原来这里是 4 条写死的 (old, new) 锚点，只对"某一轮插入的那几个小节"有效 ——
下一轮插了新小节，锚点就全部过期，脚本会报"找不到或不唯一"然后拒绝写盘。
改成通用规则，且**幂等**：

  1. 每个 "# ═══ ... ═══" 小节标题前恰好一个空行（多则压一、少则补一）；
  2. 文件末尾恰好一个换行。

只动空白，不动条目：跑完后条目数/最长行必须与跑之前一致（脚本自己断言）。
"""
import io
import re

DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"

HEADER = "# \u2550\u2550\u2550"   # "# ═══"

text = io.open(DICT, "r", encoding="utf-8", newline="").read()

before_entries = [ln for ln in text.split("\n")
                  if ln.strip() and not ln.lstrip().startswith("#") and "=" in ln]

# 1) 小节标题前恰好一个空行
text, n_headers = re.subn(r"\n+(" + re.escape(HEADER) + r")", r"\n\n\1", text)

# 2) 文件末尾恰好一个换行
text = text.rstrip("\n") + "\n"

after_entries = [ln for ln in text.split("\n")
                 if ln.strip() and not ln.lstrip().startswith("#") and "=" in ln]

assert before_entries == after_entries, \
    "条目发生了变化（%d -> %d）—— 这脚本只该动空行" % (len(before_entries), len(after_entries))

io.open(DICT, "w", encoding="utf-8", newline="").write(text)
print("polished: %d 个小节标题已规范化，条目 %d 条未变，%d 字符"
      % (n_headers, len(after_entries), len(text)))
