# -*- coding: utf-8 -*-
"""????? + ??????????? UTF-8 ??(?? stdout,?? PS ??????? mojibake)?"""
import os

REF = os.path.dirname(os.path.abspath(__file__))
DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
PROBE = os.path.join(REF, "ui_callers_round2.txt")
OUT = os.path.join(REF, "namecheck.txt")
K_MAX_WILDCARDS = 8


def trim(b):
    return b.rstrip(b" \t\r\n")


def parse(path):
    exact, pats = {}, []
    for raw in open(path, "rb").read().split(b"\n"):
        if len(raw) > 1024:
            continue
        p = raw.lstrip(b" \t")
        if not p or p[:1] in (b"#", b";") or b"=" not in p:
            continue
        k, v = p.split(b"=", 1)
        k, v = trim(k), trim(v)
        if not k or not v:
            continue
        k = k.lower()
        if b"*" in k:
            parts = k.split(b"*")
            if len(parts) - 1 <= K_MAX_WILDCARDS:
                pats.append(parts)
        else:
            exact[k] = v
    pats.sort(key=len)
    return exact, pats


def match_tpl(parts, key):
    n = len(parts)
    if n < 2:
        return None
    head = parts[0]
    if not key.startswith(head):
        return None
    pos = len(head)
    for i in range(1, n - 1):
        at = key.find(parts[i], pos)
        if at < 0:
            return None
        pos = at + len(parts[i])
    tail = parts[-1]
    if not key.endswith(tail) or len(key) - len(tail) < pos:
        return None
    return True


def hit(k, exact, pats):
    if k in exact:
        return "EXACT -> " + exact[k].decode("utf-8", "replace")
    for p in pats:
        if match_tpl(p, k):
            return "TEMPLATE -> " + b"*".join(p).decode("utf-8", "replace")
    return None


exact, pats = parse(DICT)

OBSERVED = [
    "muyou", "Aquila13", "AyerRex", "Bruce", "Crowea", "happlyboy", "yasoft1",
    "JoeBidenshairyle", "Smirnoff[StPb]", "Oncent", "Ouicho", "#Mr.Nilsson#",
    "Peek Me Pookie", "Chinese Home", "Hardcore Group",
    "LCN94z", "jackrabbit", "Harry_Scrodum", "maxitictac", "SuperSaiyanRos#",
    "cerrolazamarco", "Chromer", "nizko993", "kstzzz", "Silverlol",
    "BB", "J", "Reverose", "Shuma_6orath", "KazamiHayato", "Drsdavi",
    "yayu", "abdxlr04", "AUmyoua", "Cypas_Nya", "Ironic*", "king", "LIQLXU",
    "NaNaKo", "NerSo", "nick", "Porridge-", "Unknown Soldier", "x chen", "Ju",
    "M", "S", "B", "R", "N", "U", "P", "O",
]

seen = set(o.lower() for o in OBSERVED)
extra = []
if os.path.exists(PROBE):
    for line in open(PROBE, "rb").read().split(b"\n"):
        if not line or line[:1] == b"#":
            continue
        p = line.split(b"\t", 3)
        if len(p) < 4:
            continue
        t = trim(p[3]).decode("utf-8", "replace")
        if not t or " " in t or len(t) > 24:
            continue
        if not any(0x41 <= c <= 0x5A or 0x61 <= c <= 0x7A for c in t.encode()):
            continue
        if t.lower() in seen:
            continue
        seen.add(t.lower())
        extra.append(t)

o = []
o.append("=== ?????????????(%d ?)===" % len(OBSERVED))
bad = []
for s in OBSERVED:
    h = hit(s.lower().encode(), exact, pats)
    if h:
        bad.append((s, h))
if bad:
    for s, h in bad:
        o.append("  !!! %-20s %s" % (s, h))
else:
    o.append("  \u2705 ????? -- 0 / %d ???" % len(OBSERVED))

o.append("")
o.append("=== ?????????????? token(%d ?)===" % len(extra))
bad2 = []
for s in extra:
    h = hit(s.lower().encode(), exact, pats)
    if h:
        bad2.append((s, h))
if bad2:
    for s, h in bad2:
        o.append("  ?? %-20s %s" % (s, h))
else:
    o.append("  \u2705 ?????")
o.append("  (??:%s)" % " ".join(sorted(extra)))

o.append("")
o.append("=== ???????????????????? ===")
solo = sorted(k.decode() for k in exact
              if b" " not in k and all(32 < c < 127 for c in k))
solo_short = [k for k in solo if len(k) <= 9 and k.isalpha()]
o.append("  ???? %d ??? + %d ???" % (len(exact), len(pats)))
o.append("  ? token ????        : %d ?" % len(solo))
o.append("  ?????? <=9 ??    : %d ?   <-- ???????????" % len(solo_short))
o.append("  ??(????????)  : %d ?   <-- ??????????" % (len(exact) - len(solo)))
o.append("")
o.append("  ???????(??? perk / ???? / ???,???):")
risk = ["ghost", "talon", "rogue", "nomad", "outlaw", "moon", "rift", "rise",
        "insane", "hidden", "popular", "spire", "stoked", "infinite", "empire",
        "citadel", "verge", "hunted", "reaper", "seraph", "spectre", "prophet",
        "ruin", "battery", "firebreak", "blackjack", "outrider"]
o.append("  " + "  ".join("%s=%s" % (k, exact[k.encode()].decode())
                          for k in risk if k.encode() in exact))

o.append("")
o.append("=== ??????:???????? ===")
for s in ["BLACK OPS", "CDP", "Black Ops", "cdp"]:
    h = hit(s.lower().encode(), exact, pats)
    o.append("  %-12s %s" % (s, h or "\u2705 ???,????"))

open(OUT, "w", encoding="utf-8").write("\n".join(o) + "\n")
print("written", OUT)
