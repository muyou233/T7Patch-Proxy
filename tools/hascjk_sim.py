"""HasCjk 的逻辑复刻 + 边界用例（C++ 版在 src/translate.cpp）。

为什么要有这个：C++ 里那个判定决定了**采集器跳过什么**。判太宽 = 漏采
（英文串里的弯引号、重音字母会被当成"已翻译"丢掉，这正是本轮修的 bug）；
判太窄 = 把游戏自带中文采进 dump，白占 8000 条配额。

注意 UTF-8 三字节 lead 的范围 0xE0-0xEF 覆盖的不只是汉字：
  U+3040-U+30FF 日文假名（E3）        -> 不该跳
  U+AC00-U+D7AF 韩文（EA-ED）         -> 不该跳
  U+FF00-U+FFEF 全角标点（EF）        -> 不该跳
  U+1F600 表情（F0 开头，四字节）     -> 不该跳
只看 lead 字节会把这些全误判成中文 —— 所以必须解码后再判区间。
"""


def has_cjk(s):
    b = s.encode("utf-8")
    i = 0
    n = len(b)
    while i < n:
        c = b[i]
        if c < 0xE0 or c > 0xEF:
            i += 1
            continue
        if i + 2 >= n:
            i += 1
            continue
        b1, b2 = b[i + 1], b[i + 2]
        if not (0x80 <= b1 <= 0xBF and 0x80 <= b2 <= 0xBF):
            i += 1
            continue
        cp = ((c & 0x0F) << 12) | ((b1 & 0x3F) << 6) | (b2 & 0x3F)
        if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF or 0xF900 <= cp <= 0xFAFF:
            return True, "U+%04X %s" % (cp, s)
        i += 1
    return False, ""


CASES = [
    ("Settings", False),                       # 纯英文
    ("QUICK JOIN", False),
    ('the \u201cfirst raise\u201d animation', False),   # 弯引号 U+201C/201D
    ("caf\u00e9", False),                      # 重音 U+00E9（两字节）
    ("\u3053\u3093\u306b\u3061\u306f", False),# 日文假名
    ("\uc548\ub155\ud558\uc138\uc694", False), # 韩文
    ("\uff08\uff09\uff0c", False),             # 全角标点（无汉字）
    ("\u300a\u300b\u30fb", False),             # 书名号 + 间隔号
    ("\U0001F600", False),                     # 表情
    ("\u8bbe\u7f6e", True),                    # 中文
    ("\u4e00", True),                          # U+4E00 边界
    ("\u9fff", True),                          # U+9FFF 边界
    ("\u3400", True),                          # 扩展 A 下边界
    ("Hello\uff0cworld", False),               # 英文 + 全角逗号：必须采到
    ("Weapons, attachments, \u914d\u88c5", True),  # 中英混排：跳过
]

fails = 0
lines = []
for text, want in CASES:
    got, detail = has_cjk(text)
    ok = got == want
    if not ok:
        fails += 1
    lines.append("%-4s want=%-5s got=%-5s  %r%s" % (
        "OK" if ok else "FAIL", want, got, text, ("  <- " + detail) if detail else ""))

lines.append("")
lines.append("边界用例：%d 条，失败 %d 条" % (len(CASES), fails))
lines.append("")
lines.append("结论：判定必须解码到码点再比区间。只看 lead 字节（0xE0-0xEF）会把")
lines.append("日文假名/韩文/全角标点/书名号一起误判成中文，那些串就再也采不到了。")

txt = "\n".join(lines)
open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\hascjk.txt", "w",
     encoding="utf-8", newline="\n").write(txt)
print(txt)
