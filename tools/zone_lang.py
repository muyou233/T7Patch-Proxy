import os, collections, io

ZONE = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\zone"
GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"

out = io.StringIO()
try:
    names = [n for n in os.listdir(ZONE) if os.path.isfile(os.path.join(ZONE, n))]
except OSError as e:
    print("zone listdir failed:", e)
    raise SystemExit(1)

buckets = collections.Counter()
sizes = collections.defaultdict(int)
other = []
for n in names:
    pre = n.split("_")[0]
    if len(pre) == 2 and pre.isalpha() and n[2:3] == "_":
        buckets[pre] += 1
        sizes[pre] += os.path.getsize(os.path.join(ZONE, n))
    else:
        other.append(n)

out.write("zone 文件总数 = %d\n" % len(names))
out.write("带 <lang>_ 前缀的 = %d\n" % sum(buckets.values()))
for k in sorted(buckets):
    out.write("   %-6s x%-4d %8.1f MB\n" % (k, buckets[k], sizes[k] / 1048576.0))
out.write("不带前缀样本：%s\n" % ", ".join(sorted(other)[:10]))

# 游戏根目录最大文件（找语言包落点）
big = []
for root, dirs, files in os.walk(GAME):
    if "T7Patch" in root:
        continue
    for f in files:
        p = os.path.join(root, f)
        try:
            big.append((os.path.getsize(p), p[len(GAME) + 1:]))
        except OSError:
            pass
big.sort(reverse=True)
out.write("\n游戏目录最大的 8 个文件：\n")
for s, p in big[:8]:
    out.write("   %8.1f MB  %s\n" % (s / 1048576.0, p))

with open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\zone_lang.txt", "w", encoding="utf-8") as f:
    f.write(out.getvalue())
print("ok")
