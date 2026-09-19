import os, collections

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
LANGS = {"en", "sc", "tc", "fr", "it", "de", "es", "ja", "ru", "pl", "pt", "ko", "esm"}

langs = collections.defaultdict(lambda: [0, 0])   # tag -> [files, bytes]
others = collections.defaultdict(lambda: [0, 0])  # 二级目录 -> [files, bytes]

for root, dirs, files in os.walk(GAME):
    if os.sep + "T7Patch" in root:
        continue
    rel = os.path.relpath(root, GAME)
    parts = [] if rel == "." else rel.split(os.sep)
    tag = None
    for p in parts:
        if p.lower() in LANGS:
            tag = p.lower()
            break
    if tag:
        s = sum(os.path.getsize(os.path.join(root, f)) for f in files if os.path.isfile(os.path.join(root, f)))
        langs[tag][0] += len(files)
        langs[tag][1] += s
    elif parts:
        key = parts[0]
        s = sum(os.path.getsize(os.path.join(root, f)) for f in files if os.path.isfile(os.path.join(root, f)))
        others[key][0] += len(files)
        others[key][1] += s

out = []
out.append("== 路径里出现语言目录名的（zone\\snd\\en 这类）==")
for k in sorted(langs, key=lambda x: -langs[x][1]):
    n, b = langs[k]
    out.append("   %-4s files=%-5d %9.1f MB" % (k, n, b / 1048576.0))
out.append("")
out.append("== zone 顶层各前缀 ==")
z = os.path.join(GAME, "zone")
pre = collections.defaultdict(lambda: [0, 0])
for n in os.listdir(z):
    p = os.path.join(z, n)
    if not os.path.isfile(p):
        continue
    key = n.split("_")[0] if len(n.split("_")[0]) == 2 else "(no-lang)"
    pre[key][0] += 1
    pre[key][1] += os.path.getsize(p)
for k in sorted(pre, key=lambda x: -pre[x][1]):
    n, b = pre[k]
    out.append("   %-8s files=%-5d %9.1f MB" % (k, n, b / 1048576.0))
out.append("")
out.append("== zone 下的子目录 ==")
for n in sorted(os.listdir(z)):
    p = os.path.join(z, n)
    if os.path.isdir(p):
        c = 0
        s = 0
        for root, ds, fs in os.walk(p):
            for f in fs:
                c += 1
                s += os.path.getsize(os.path.join(root, f))
        out.append("   %-20s files=%-5d %9.1f MB" % (n, c, s / 1048576.0))

with open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\lang_files.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
print("ok")
