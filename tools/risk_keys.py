# -*- coding: utf-8 -*-
# How exposed is the dictionary to "a player name that happens to equal a key"?
# A key can only steal a player name if it is SHORT, has NO spaces and NO
# template placeholders - those are the ones a name could plausibly equal.
# Long sentences and '*'-templates can never collide with a name.
import os, re

ROOT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private"
DICT = os.path.join(ROOT, "translate", "translate_zh.txt")
OUT = os.path.join(ROOT, ".codebuddy", "ref", "risk_keys.txt")

raw = open(DICT, "rb").read().decode("utf-8")
rows = []
for ln in raw.split("\n"):
    if not ln or ln.startswith("#") or "=" not in ln:
        continue
    k, v = ln.split("=", 1)
    rows.append((k, v))

def bucket(k):
    body = k
    has_tpl = "*" in k
    # strip a leading colour-code / "^B..." marker
    core = re.sub(r"(\^[0-9A-Za-z])", "", body)
    core = re.sub(r"\$\([^)]*\)", "", core)
    core = core.strip()
    words = [w for w in re.split(r"[\s]+", core) if w]
    # a "bare single token" - the only shape a player name can collide with
    if not has_tpl and len(words) == 1 and re.fullmatch(r"[A-Za-z0-9_\-\.]{1,12}", words[0]):
        return "bare", words[0]
    return None, core

bare = []
for k, v in rows:
    kind, core = bucket(k)
    if kind == "bare":
        bare.append((core, v, k))

bare.sort(key=lambda t: t[0].lower())
o = []
o.append("== dictionary risk report ==")
o.append("  total entries            : %d" % len(rows))
o.append("  bare single-token keys   : %d  (%.1f%%)" % (len(bare), 100.0 * len(bare) / max(1, len(rows))))
o.append("  sentence / template keys : %d  <-- cannot collide with a player name"
         % (len(rows) - len(bare)))
o.append("")
o.append("== bare single-token keys (a player name could equal one of these) ==")
for core, v, k in bare:
    o.append("  %-28s -> %s" % (core, v[:40]))
o.append("")
o.append("== how many are 'real words' a player name would plausibly be? ==")
short = [b for b in bare if len(b[0]) <= 6]
o.append("  len<=6 : %d" % len(short))
for core, v, k in short:
    o.append("    %-20s -> %s" % (core, v[:30]))

open(OUT, "w", encoding="utf-8").write("\n".join(o))
print("bare=%d total=%d written %s" % (len(bare), len(rows), OUT))
