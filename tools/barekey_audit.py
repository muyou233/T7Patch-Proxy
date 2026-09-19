# -*- coding: utf-8 -*-
# Bare-key audit: a "bare" key (single token, no space, no '*') can only ever
# fire when that token IS a whole run by itself.  So for each of them ask the
# dump one question: does this token ever appear as a standalone run?
#
#   - yes -> the key earns its keep (it translates real UI text)
#   - no  -> dead key: it matches nothing in the captured UI, so its ONLY
#            possible effect is colliding with a player name that happens to
#            equal it.  Deleting such a key costs nothing visible.
import os, re

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\barekey_audit.txt"


def runs_of(line):
    out, i, n = [], 0, len(line)
    while i < n:
        while i < n and line[i] < 0x20:
            i += 1
        if i >= n:
            break
        j = i
        while j < n and line[j] >= 0x20:
            j += 1
        a, b = i, j
        while a < b and line[a] == 0x20:
            a += 1
        while b > a and line[b - 1] == 0x20:
            b -= 1
        if b > a:
            out.append(line[a:b])
        i = j
    return out


# ---- dictionary ----
bare = {}
for raw in open(DICT, "rb").read().split(b"\n"):
    p = raw.lstrip(b" \t")
    if not p or p[:1] in (b"#", b";") or b"=" not in p:
        continue
    k, v = p.split(b"=", 1)
    k, v = k.rstrip(b" \t\r\n"), v.rstrip(b" \t\r\n")
    if not k or not v or b"*" in k:
        continue
    core = re.sub(rb"(\^[0-9A-Za-z])", b"", k)
    core = re.sub(rb"\$\([^)]*\)", b"", core).strip()
    if re.fullmatch(rb"[A-Za-z0-9_\-\.]{1,12}", core):
        bare[core.lower()] = v

# ---- dump runs ----
seen, order, count = set(), [], {}
for raw in open(DUMP, "rb").read().split(b"\n"):
    b = raw.rstrip(b"\r")
    if not b:
        continue
    for run in runs_of(b):
        if run in seen:
            continue
        seen.add(run)
        order.append(run)

live, dead = [], []
for core in sorted(bare):
    inst = [r for r in order if r.lower() == core]
    if inst:
        live.append((core, bare[core], inst))
    else:
        dead.append((core, bare[core]))

o = []
o.append("== bare single-token keys vs the captured UI ==")
o.append("  bare keys total          : %d" % len(bare))
o.append("  appear as a standalone run: %d   <- earn their keep" % len(live))
o.append("  NEVER appear standalone   : %d   <- dead: only risk, no payoff" % len(dead))
o.append("  dump runs (deduped)       : %d" % len(order))
o.append("")
o.append("== DEAD bare keys (deleting them cannot change any captured UI text) ==")
for core, v in dead:
    o.append("  %-22s -> %s" % (core.decode(), v.decode("utf-8", "replace")[:36]))
o.append("")
o.append("== LIVE bare keys: what they actually translated (sample instance) ==")
for core, v, inst in live:
    o.append("  %-22s -> %-24s  instance=%s"
             % (core.decode(), v.decode("utf-8", "replace")[:22],
                inst[0].decode("ascii", "replace")[:40]))
o.append("")

open(OUT, "w", encoding="utf-8").write("\n".join(o))
print("bare=%d live=%d dead=%d runs=%d" % (len(bare), len(live), len(dead), len(order)))
