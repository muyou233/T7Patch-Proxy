"""按 translate.cpp 的口径数一遍：精确条目 / 模板条目（含 '*'）。

补丁日志里的 "(822 entries, 16 templates)" 就是这两个数 —— 用来预测/核对
新词库加载后的那一行。
"""
DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
exact = tpl = 0
for line in open(DICT, "rb").read().decode("utf-8").splitlines():
    s = line.strip()
    if not s or s.startswith(("#", ";")) or "=" not in s:
        continue
    k = s.split("=", 1)[0]
    if "*" in k:
        tpl += 1
    else:
        exact += 1
print("精确 %d + 模板 %d = 合计 %d" % (exact, tpl, exact + tpl))
