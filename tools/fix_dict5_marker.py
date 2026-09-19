# -*- coding: utf-8 -*-
"""修掉第五轮写入时值里的双空格：`=^BBUTTON_PURCHASABLE_ICON^  崛起` -> 单空格。

（键是 `^bbutton_...` 小写，所以按大写形态匹配只会命中「值」那一侧。）
"""
import io

DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
MK = b"^BBUTTON_PURCHASABLE_ICON^"

raw = open(DICT, "rb").read()
n = raw.count(MK + b"  ")
assert n == 16, "双空格出现 %d 次（期望 16）" % n
new = raw.replace(MK + b"  ", MK + b" ")
assert new.count(MK + b"  ") == 0
# 16 条条目 + 1 行小节注释（注释里也写了这个标记）
assert new.count(MK + b" ") == 17, "单空格出现 %d 次（期望 17）" % new.count(MK + b" ")
io.open(DICT, "wb").write(new)
print("fixed:", n, "处，字节", len(raw), "->", len(new))
