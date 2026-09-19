# -*- coding: utf-8 -*-
"""Test jsDelivr CDN for the GitHub dict, anonymously."""
import hashlib
import urllib.request

ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}
LOCAL = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
targets = [
    ("jsdelivr gh@main",
     "https://cdn.jsdelivr.net/gh/muyou233/T7Patch-Proxy@main/translate/translate_zh.txt"),
    ("jsdelivr purge-check (github raw)",
     "https://raw.githubusercontent.com/muyou233/T7Patch-Proxy/main/translate/translate_zh.txt"),
]
bodies = {}
for name, url in targets:
    try:
        req = urllib.request.Request(url, headers=ua)
        with urllib.request.urlopen(req, timeout=20) as r:
            body = r.read()
            bodies[name] = body
            print("%-36s HTTP %s len=%d sha=%s"
                % (name, getattr(r, "status", r.getcode()), len(body),
                   hashlib.sha256(body).hexdigest()[:12]))
    except Exception as e:
        print("%-36s FAILED: %s" % (name, e))

local = open(LOCAL, "rb").read()
print("local sha:", hashlib.sha256(local).hexdigest()[:12])
if "jsdelivr gh@main" in bodies:
    print("jsdelivr == local:", "MATCH" if bodies["jsdelivr gh@main"] == local else "MISMATCH")
