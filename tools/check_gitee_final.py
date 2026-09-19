# -*- coding: utf-8 -*-
"""Try Gitee API contents endpoint (base64 JSON) as alternative to raw."""
import base64
import hashlib
import json
import urllib.request

ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}
LOCAL = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"

# 1) repo meta
req = urllib.request.Request(
    "https://gitee.com/api/v5/repos/muyou23333/t7-patch-proxy-translate", headers=ua)
with urllib.request.urlopen(req, timeout=30) as r:
    d = json.loads(r.read().decode("utf-8"))
print("repo        :", d.get("full_name"))
print("private     :", d.get("private"))
lic = d.get("license")
print("license     :", lic if isinstance(lic, str) else (lic or {}).get("name"))
print("default br  :", d.get("default_branch"))

# 2) contents API
url = ("https://gitee.com/api/v5/repos/muyou23333/t7-patch-proxy-translate"
       "/contents/translate/translate_zh.txt?ref=master")
req = urllib.request.Request(url, headers=ua)
with urllib.request.urlopen(req, timeout=30) as r:
    body = json.loads(r.read().decode("utf-8"))
print("contents api: HTTP 200, name =", body.get("name"), ", size =", body.get("size"))
raw = base64.b64decode(body.get("content"))
local = open(LOCAL, "rb").read()
sr = hashlib.sha256(raw).hexdigest()[:16]
sl = hashlib.sha256(local).hexdigest()[:16]
print("remote      :", sr)
print("local       :", sl)
print("MATCH" if sr == sl else "MISMATCH")

# 3) retry raw with different variations to pin down the 451 rule
for label, u in [
    ("raw plain", "https://gitee.com/muyou23333/t7-patch-proxy-translate/raw/master/translate/translate_zh.txt"),
    ("raw ?raw=1", "https://gitee.com/muyou23333/t7-patch-proxy-translate/raw/master/translate/translate_zh.txt?raw=1"),
]:
    try:
        req = urllib.request.Request(u, headers=ua)
        with urllib.request.urlopen(req, timeout=30) as r:
            print("%-12s HTTP %s len=%d" % (label, getattr(r, "status", r.getcode()), len(r.read())))
    except Exception as e:
        print("%-12s FAILED: %s" % (label, e))
