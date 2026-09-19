# -*- coding: utf-8 -*-
# 从 v3.2.4 发布 DLL 里把"人话"字符串捞出来：UI 标签 / tooltip / 日志文案。
# 目的：枚举它的功能与性能相关项（源快照是 8 月的，DLL 是 9 月的，以 DLL 为准）。
import re

DLL = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\Scropts.QOL.v3.2.4.dll"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\scropts_dll_human.txt"

data = open(DLL, "rb").read()

# 窄 ASCII 字符串（编译器把相邻字符串连成一串，先按长度>=6 切）
cands = set()
for m in re.finditer(rb"[\x20-\x7E]{6,}", data):
    s = m.group().decode("latin1")
    cands.add(s)

def human(s):
    if len(s) > 400:
        return False
    letters = sum(1 for c in s if c.isalpha() or c == " ")
    if letters / max(1, len(s)) < 0.85:
        return False
    return " " in s and sum(1 for c in s if c.isalpha()) >= 8

hits = sorted(s for s in cands if human(s))

# 性能/菜单/卡顿 相关关键词
KEY = re.compile(r"stutter|fps|frame|lag|freeze|hitch|smooth|menu|tick|latency|"
                 r"performance|optimi|render|interval|delay|cooldown|throttl", re.I)

lines = []
def w(s=""):
    lines.append(s)

w("=== 命中 性能/菜单 关键词的人话字符串 (%d 条候选中) ===" % len(hits))
n = 0
for s in hits:
    if KEY.search(s):
        n += 1
        w("  * " + s)
w("  小计 %d" % n)

w("")
w("=== 全部人话字符串（%d 条，按字母排序）===" % len(hits))
for s in hits:
    w("  " + s)

open(OUT, "w", encoding="utf-8", errors="replace").write("\n".join(lines))
print("done", len(hits))
