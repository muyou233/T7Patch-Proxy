"""首字母分桶 vs 哈希：谁更划算？用真实词库算一遍。

三个问题：
  1) 精确条目按首字母分桶，平均桶多大？（= 分桶后还要线性扫几条）
  2) 模板条目按首字母分桶可行吗？多少条以 '*' 开头（= 没有首字母）？
  3) 若改为「按第一个字面字符分桶」，模板的桶分布如何？查找时能跳过多少条？
"""
import io
import os
import collections

DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"

exact = []
templ = []
with io.open(DICT, "r", encoding="utf-8", newline="") as fh:
    for ln in fh:
        ln = ln.rstrip("\r\n")
        if not ln or ln.lstrip().startswith("#"):
            continue
        if "=" not in ln:
            continue
        k = ln.split("=", 1)[0].strip()
        if "*" in ln.split("=", 1)[0]:
            templ.append(k)
        else:
            exact.append(k)

out = []
out.append("词库总条目：%d（精确 %d + 模板 %d）" % (len(exact) + len(templ), len(exact), len(templ)))

# ---- 1) 精确条目按首字母分桶 ----
buckets = collections.Counter((k[:1].lower() or "?") for k in exact)
out.append("")
out.append("【1】精确条目按首字母分桶：共 %d 个桶" % len(buckets))
top = buckets.most_common(8)
out.append("     最大的桶：" + "  ".join("%s=%d 条" % (c, n) for c, n in top))
avg = len(exact) / float(max(1, len(buckets)))
out.append("     平均桶大小 = %.1f 条/桶  ⇒ 分桶后每次查找仍需线性比对这么多条" % avg)

# ---- 2) 模板条目：首字符统计 ----
star = sum(1 for k in templ if k.startswith("*"))
out.append("")
out.append("【2】模板条目共 %d 条；以 '*' 开头的 %d 条（这些没有「首字母」可言）" % (len(templ), star))
out.append("     分布的桶（按首字符）：")
for c, n in sorted(collections.Counter(k[:1] for k in templ).items()):
    out.append("        %-4s %d" % ("'*'" if c == "*" else c, n))

# ---- 3) 模板改按「第一个字面字符」分桶 ----
def first_literal(k):
    for ch in k:
        if ch != "*":
            return ch.lower()
    return "?"

lb = collections.Counter(first_literal(k) for k in templ)
out.append("")
out.append("【3】模板若按「跳过前导 * 后的第一个字面字符」分桶：%d 个桶" % len(lb))
out.append("     " + "  ".join("%s=%d" % (c, n) for c, n in sorted(lb.items())))
out.append("     查找时按同一规则取桶键 ⇒ 平均只需试 %.1f 条模板（现在是无条件试 %d 条）"
           % (len(templ) / float(max(1, len(lb))), len(templ)))

# ---- 4) 反例：模板前导 * 能吃掉任意文本，桶键取「串的首字符」会错 ----
out.append("")
out.append("【4】取「被查串的首字符」当桶键为什么不行：")
out.append("     模板 '* hit (*)' 要匹配的串可能是 '1 Hit (35%)'（首字符 '1'），")
out.append("     也可能是 ' explosion hit (x)'（首字符 ' '）⇒ 桶键必须从**模板**端推导，")
out.append("     且要处理「模板以 * 开头」⇒ 只能按「第一个字面块」定位，不能按「首字符」。")

txt = "\n".join(out)
io.open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\bucket_sim.txt", "w",
        encoding="utf-8", newline="\n").write(txt)
print(txt)
