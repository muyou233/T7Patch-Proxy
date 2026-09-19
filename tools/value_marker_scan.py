"""译文里的格式标记自检。

为什么需要它：Hooks.cpp 在两个翻译 hook 里，是**先替换文本、再扫描标记**的
    Lookup() -> strcpy_s(input, translated) -> 扫 '^B...^' -> 扫 '$(...)' -> 交给原函数
所以「值」里的标记同样会被引擎解释。两种出错方式都有后果：
    值里**少了**标记  -> 颜色/图标丢失，或按键绑定不被替换（显示问题）
    值里**多了**标记  -> 引擎会去找绑定，且未配对的 '^' / '$(' 会被上游代码改写成 '.'
                        （Hooks.cpp: input[i] = '.'），屏幕上出现莫名其妙的点

期望：精确条目的值与键**标记序列完全一致**（我们只做保留，不自己造标记）。
模板条目的值里 '*' 会把捕获的原文（含标记）原样填回，所以不参与逐条比对。
"""
import io
import os
import re

DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
MARK = re.compile(r"\^[0-9A-Za-z]")


def marks(s):
    return [m.group(0).lower() for m in MARK.finditer(s)]


rows = []
with io.open(DICT, "r", encoding="utf-8", newline="") as fh:
    for ln in fh:
        ln = ln.rstrip("\r\n")
        if not ln.strip() or ln.lstrip().startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        rows.append((k.strip(), v.strip()))

same = fewer = more = 0
templ = 0
problems = []
marker_uses = []
for k, v in rows:
    km, vm = marks(k), marks(v)
    if not km and not vm:
        continue
    if "*" in k:
        templ += 1
        continue
    if km == vm:
        same += 1
    elif len(vm) < len(km):
        fewer += 1
        problems.append(("值缺标记", k, v, km, vm))
    else:
        more += 1
        problems.append(("值多标记", k, v, km, vm))
    marker_uses.append((k, km, vm))

total_templ = sum(1 for k, _ in rows if "*" in k)
out = []
out.append("词库条目 %d 条；其中模板 %d 条（模板不参与逐条比对 —— 它会把捕获到的原文原样填回，"
           "标记自然跟着回来）" % (len(rows), total_templ))
out.append("带标记的精确条目：值标记一致 %d / 值缺标记 %d / 值多标记 %d"
           % (same, fewer, more))

out.append("")
out.append("=== 全部带标记的精确条目（键标记 -> 值标记）===")
for k, km, vm in marker_uses:
    flag = "OK " if km == vm else "!! "
    out.append("  %s%-22s -> %s" % (flag, " ".join(km) or "-", " ".join(vm) or "-"))
    out.append("      键：%s" % k[:88])
    out.append("      值：%s" % dict((kk, vv) for kk, vv in rows).get(k, "")[:88])

if problems:
    out.append("")
    out.append("=== 需要人工确认的 %d 条 ===" % len(problems))
    for kind, k, v, km, vm in problems:
        out.append("  [%s] 键=%s  值=%s" % (kind, " ".join(km), " ".join(vm)))
        out.append("      %s" % k[:88])
else:
    out.append("")
    out.append("=== 没有问题条目：所有精确条目的值都与键的标记序列一致 ===")

# 其他可能被引擎二次解释的字符
out.append("")
out.append("=== 值里出现的其他“有含义”字符（逐条核对是否故意）===")
for ch, label in (("$(", "$() 属性绑定"), ("[{", "[{...}] 令牌"), ("%", "百分号"),
                  ("\\", "反斜杠")):
    hit = [(k, v) for k, v in rows if ch in v]
    out.append("  %-16s 命中 %d 条" % (label, len(hit)))
    for k, v in hit[:4]:
        out.append("      %s = %s" % (k[:60], v[:60]))

txt = "\n".join(out)
print(txt)
