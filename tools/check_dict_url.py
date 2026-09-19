# -*- coding: utf-8 -*-
"""End-to-end check of the dictionary update source.

Fetches the exact URL hard-coded in src/dict_update.cpp, counts entries
with the same rules as CountEntries(), and compares the bytes with the
repo copy translate/translate_zh.txt.
"""
import hashlib
import sys
import urllib.request

URL = ("https://raw.githubusercontent.com/muyou233/T7Patch-Proxy"
       "/main/translate/translate_zh.txt")
LOCAL = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"

out = []

def say(s):
    out.append(s)

req = urllib.request.Request(URL, headers={"User-Agent": "t7patch-check/1.0"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        status = getattr(r, "status", r.getcode())
        body = r.read()
except Exception as e:
    say("FETCH FAILED: %r" % (e,))
    print("\n".join(out))
    sys.exit(1)

say("HTTP %s" % status)
say("downloaded: %d bytes" % len(body))

# Same entry-counting rules as dict_update.cpp CountEntries():
# skip blank lines and lines longer than 1022, skip leading-space
# comments starting with '#' or ';', count lines containing '='.
count = 0
version_line = None
for raw in body.split(b"\n"):
    line = raw.rstrip(b"\r")
    ln = len(line)
    if ln == 0 or ln > 1022:
        continue
    i = 0
    while i < ln and line[i:i+1] in (b" ", b"\t"):
        i += 1
    if i >= ln or line[i:i+1] in (b"#", b";"):
        if line[i:i+9] == b"# version" and version_line is None:
            version_line = line.decode("utf-8", "replace")
        continue
    if b"=" in line[i:]:
        count += 1
say("entries (CountEntries rules): %d" % count)
say("version line: %s" % (version_line or "(none)"))
sha_remote = hashlib.sha256(body).hexdigest()

with open(LOCAL, "rb") as f:
    local = f.read()
sha_local = hashlib.sha256(local).hexdigest()
say("remote sha256: %s" % sha_remote[:16] + "...")
say("local  sha256: %s" % sha_local[:16] + "...")
say("MATCH" if sha_remote == sha_local else "MISMATCH")
print("\n".join(out))
