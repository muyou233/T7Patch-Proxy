# -*- coding: utf-8 -*-
"""Inventory every chat-style string in ui_dump.txt.

Two shapes show up for the same mod announcement (learned 2026-09-16):
  plain  :  "<name>: I'm downed!"
  colour :  "^7^2<name>^7: ^7I'm downed!^7"
Only the colour one is what the chat actually renders; the plain one is the
same text pushed through the other hook.  Templates have to cover both, and the
name (a player) plus any weapon name must stay untouched, so the inventory
prints the two families separately with their exact bytes.
"""
import io
import os
import re
from collections import OrderedDict

DUMP = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\T7Patch\ui_dump.txt"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\chat_inventory.txt"

with io.open(DUMP, "r", encoding="utf-8", errors="replace") as f:
    lines = [ln.rstrip("\n").rstrip("\r") for ln in f]

colour = OrderedDict()
plain = OrderedDict()
for ln in lines:
    if not ln.strip():
        continue
    if "^7^2" in ln or (ln.startswith("^") and ": " in ln and "^7" in ln):
        colour.setdefault(ln, 0)
        colour[ln] += 1
    elif re.match(r"^[A-Za-z0-9_\[\]\-\. ]{2,24}: \S", ln):
        plain.setdefault(ln, 0)
        plain[ln] += 1

buf = []
buf.append("=== colour-coded chat lines (%d unique) ===" % len(colour))
for k, n in colour.items():
    buf.append("[%dx] %s" % (n, k))
buf.append("")
buf.append("=== plain \"name: text\" lines (%d unique) ===" % len(plain))
for k, n in plain.items():
    buf.append("[%dx] %s" % (n, k))

with io.open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(buf) + "\n")
print("wrote %s (%d lines)" % (OUT, len(buf)))
