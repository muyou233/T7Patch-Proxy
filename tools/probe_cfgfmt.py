import os

DLL = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\x64\Release\d3d11.dll"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\probe_cfgfmt_out.txt"

data = open(DLL, "rb").read()

want = [
    b"config file was in an older format",
    b"%d setting(s) missing) - rewritten in the current format",
    b"config file is outdated but could not be rewritten",
    b"- is the T7Patch folder writable?",
]
gone = [
    b"IsSimplifiedGameLanguage",
]

lines = []
lines.append("dll: %s (%d bytes)" % (os.path.basename(DLL), len(data)))
lines.append("")
lines.append("-- must be present --")
bad = 0
for n in want:
    ok = n in data
    if not ok:
        bad += 1
    lines.append("%-5s %s" % ("OK" if ok else "MISS", n.decode("ascii")))
lines.append("")
lines.append("-- must be absent --")
for n in gone:
    ok = n not in data
    if not ok:
        bad += 1
    lines.append("%-5s %s" % ("OK" if ok else "FOUND", n.decode("ascii")))
lines.append("")
lines.append("RESULT: %s (%d problem(s))" % ("PASS" if bad == 0 else "FAIL", bad))

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
