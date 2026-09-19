"""对比 en_*（历史清单 loc_probe.txt）与当前 sc_* 的体积差 —— 差在哪、差多少。
用途：判断「中文包里新增的字节」是文本还是字形（字体图集会是几 MB 的整数级跳变）。"""
import os
import re

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
EN_LIST = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\loc_probe.txt"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\lang_delta.txt"

en = {}
for line in open(EN_LIST, "rb").read().decode("utf-8", "replace").splitlines():
    m = re.match(r"\s*([\d,]+)\s+(en_[A-Za-z0-9_.]+)\s*$", line)
    if m:
        en[m.group(2)] = int(m.group(1).replace(",", ""))

sc = {}
for name in os.listdir(os.path.join(GAME, "zone")):
    if name.startswith("sc_"):
        sc[name] = os.path.getsize(os.path.join(GAME, "zone", name))

rows = []
for name, size in sc.items():
    counterpart = "en_" + name[3:]
    old = en.get(counterpart)
    if old is None:
        rows.append((name, size, None))
    else:
        rows.append((name, size, size - old))

deltas = [r for r in rows if r[2] is not None]
same = [r for r in deltas if r[2] == 0]
big = sorted([r for r in deltas if r[2] != 0], key=lambda r: -abs(r[2]))

out = []
out.append("en 清单条目 %d；sc 现有 %d；能配对的 %d（其中体积完全相同 %d）"
           % (len(en), len(sc), len(deltas), len(same)))
out.append("sc 合计 %s 字节；en 历史合计 %s 字节" % (format(sum(sc.values()), ","),
                                              format(sum(en.get("en_" + k[3:], 0) for k in sc), ",")))
out.append("")
out.append("=== 体积有差异的（按绝对差排序，前 25）===")
for name, size, d in big[:25]:
    out.append("  %+12d  sc=%12s  %s" % (d, format(size, ","), name))
out.append("")
out.append("=== 只在 sc 里有 / 只差 0 的文件都不列 ===")
out.append("差异合计 %s 字节" % format(sum(r[2] for r in deltas), ","))

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("written", OUT)
