# -*- coding: utf-8 -*-
"""Append the prepared section to today's daily log (append-only, UTF-8, no BOM)."""
import io
import os

DAY = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\.codebuddy\memory\2026-09-16.md"
SEC = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\sec62_append.txt"

with io.open(SEC, "r", encoding="utf-8") as f:
    section = f.read()

with io.open(DAY, "r", encoding="utf-8", newline="") as f:
    body = f.read()

marker = "## §62 "
if marker in body:
    raise SystemExit("already appended, refusing to duplicate")

if not body.endswith("\n"):
    body += "\n"

with io.open(DAY, "w", encoding="utf-8", newline="") as f:
    f.write(body + section)

size = os.path.getsize(DAY)
tail = (body + section)[-500:]
with io.open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\append_sec.txt", "w", encoding="utf-8") as f:
    f.write("day log now %d bytes\n---- tail ----\n%s" % (size, tail))
print("ok %d" % size)
