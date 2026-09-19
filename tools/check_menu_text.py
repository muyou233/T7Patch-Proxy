# -*- coding: utf-8 -*-
# Structural check on overlay.cpp's bilingual string tables.
#
# Why bother: a C++ aggregate initialiser silently zero-fills any member you
# forgot to give a value, so a dropped entry turns the LAST field into a null
# pointer with no warning at all - it only explodes when the UI reads it.  So
# the arity has to be checked explicitly.
#
# Parsing is done character by character (string/escape aware) rather than line
# by line: these entries are multi-line string-literal concatenations, and a
# naive "line ends with a comma" rule miscounts them.
import os
import re

_REPO = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private"
# overlay.cpp moved into src/ on 2026-09-15; fall back to the flat root layout.
ROOT = os.path.join(_REPO, "src") if os.path.exists(os.path.join(_REPO, "src", "overlay.cpp")) else _REPO
P = os.path.join(ROOT, "overlay.cpp")
OUT = os.path.join(_REPO, ".codebuddy", "ref", "menu_text_check.txt")

src = open(P, encoding="utf-8").read()
report = []


def brace_body(text, marker):
    """Return the text between the braces that follow `marker`."""
    i = text.index(marker)
    i = text.index("{", i)
    depth = 0
    start = i + 1
    while i < len(text):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start:i]
        i += 1
    raise ValueError("unbalanced braces after %r" % marker)


def split_top_level(body):
    """Split an aggregate body on commas that sit outside strings and parens."""
    parts = []
    cur = []
    in_str = False
    esc = False
    depth = 0
    for c in body:
        if in_str:
            cur.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
            cur.append(c)
        elif c == "(":
            depth += 1
            cur.append(c)
        elif c == ")":
            depth -= 1
            cur.append(c)
        elif c == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
    tail = "".join(cur).strip()
    if tail:
        parts.append(tail)
    return parts


def unescape(s):
    return s.replace("\\n", " / ").replace('"', "").replace("\\", "")


# ---------------------------------------------------------------- struct arity
struct_body = brace_body(src, "struct MenuText")
fields = re.findall(r"const char\s*\*\s*(\w+)\s*;", struct_body)

zh = split_top_level(brace_body(src, "constexpr MenuText kTextZh = {"))
en = split_top_level(brace_body(src, "constexpr MenuText kTextEn = {"))

report.append("struct MenuText : %d fields" % len(fields))
report.append("kTextZh         : %d entries" % len(zh))
report.append("kTextEn         : %d entries" % len(en))
report.append("")

ok = True
for label, got in (("kTextZh", len(zh)), ("kTextEn", len(en))):
    if got != len(fields):
        report.append("FAIL: struct has %d fields but %s has %d entries" % (len(fields), label, got))
        ok = False
if len(zh) != len(en):
    report.append("FAIL: the two tables disagree in length")
    ok = False
if "t7patch.conf" in src:
    report.append("FAIL: t7patch.conf still present in overlay.cpp")
    ok = False

# encoding sanity - the zh table must still carry CJK
cjk = re.findall(r"[\u4e00-\u9fff]", " ".join(zh))
report.append("CJK chars in kTextZh: %d" % len(cjk))
if len(cjk) < 40:
    report.append("WARN: suspiciously few CJK chars - possible encoding damage")
    ok = False

# ---------------------------------------------------------------- the 3 rewrites
report.append("")
report.append("--- field-by-field for the rewritten tooltips ---")
for nm in ("blockShaderTip", "friendsOnlyTip", "autoOpenTip"):
    i = fields.index(nm)
    report.append("%-16s zh | %s" % (nm, unescape(zh[i])))
    report.append("%-16s en | %s" % ("", unescape(en[i])))

report.append("")
report.append("RESULT: %s" % ("OK" if ok else "PROBLEM"))
open(OUT, "w", encoding="utf-8").write("\n".join(report) + "\n")
print("\n".join(report))
