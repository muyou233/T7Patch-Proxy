"""Report the line-ending mix of the files we are about to edit.

Prints CRLF / lone-LF counts so an edit can pick the file's own convention
instead of guessing (the repo is mixed, see MEMORY).
"""
import os

ROOT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private"
FILES = [
    r"src\translate.cpp",
    r"src\overlay.cpp",
    r"src\Protection.cpp",
    r"src\framework.h",
    r"tools\fixcheck.py",
    r"tools\probe_lang.py",
    r"README.md",
    r"README_EN.md",
]

for rel in FILES:
    path = os.path.join(ROOT, rel)
    if not os.path.isfile(path):
        print("%-34s MISSING" % rel)
        continue
    with open(path, "rb") as f:
        data = f.read()
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    cr = data.count(b"\r") - crlf
    if crlf and lf:
        kind = "MIXED"
    elif crlf:
        kind = "CRLF"
    elif lf:
        kind = "LF"
    else:
        kind = "none"
    print("%-34s %-6s crlf=%-6d lf=%-6d lone_cr=%d" % (rel, kind, crlf, lf, cr))
