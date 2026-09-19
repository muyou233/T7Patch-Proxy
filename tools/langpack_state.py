import os, collections

d = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\.codebuddy\langpack_backup"
lines = []
lines.append("backup dir exists = %s" % os.path.isdir(d))
if os.path.isdir(d):
    n = 0
    tot = 0
    pre = collections.Counter()
    sample = []
    for root, ds, fs in os.walk(d):
        for f in fs:
            p = os.path.join(root, f)
            n += 1
            tot += os.path.getsize(p)
            pre[f.split("_")[0][:6]] += 1
            if len(sample) < 8:
                sample.append((f, os.path.getsize(p)))
    lines.append("files = %d, total = %.1f MB" % (n, tot / 1048576.0))
    lines.append("name-prefix counts: %s" % dict(pre))
    lines.append("sample: %s" % sample)

# 也看看 ref/langpack_list.txt 里记的是什么
lp = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\langpack_list.txt"
if os.path.isfile(lp):
    with open(lp, "r", encoding="utf-8", errors="replace") as f:
        txt = f.read().splitlines()
    lines.append("\nlangpack_list.txt 共 %d 行，前 12 行：" % len(txt))
    lines.extend("   " + t for t in txt[:12])

with open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\langpack_state.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("ok")
