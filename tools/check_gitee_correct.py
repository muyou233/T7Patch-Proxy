# -*- coding: utf-8 -*-
import urllib.request
ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}
targets = [
    ("repo home",  "https://gitee.com/muyou23333/t7-patch-proxy-translate"),
    ("raw file",   "https://gitee.com/muyou23333/t7-patch-proxy-translate/raw/master/translate/translate_zh.txt"),
    ("repo api",   "https://gitee.com/api/v5/repos/muyou23333/t7-patch-proxy-translate"),
]
for name, url in targets:
    try:
        req = urllib.request.Request(url, headers=ua)
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            print("%-10s HTTP %s len=%d" % (name, getattr(r, "status", r.getcode()), len(body)))
            if name == "raw file":
                import hashlib
                local = open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt", "rb").read()
                sr = hashlib.sha256(body).hexdigest()[:16]
                sl = hashlib.sha256(local).hexdigest()[:16]
                print("  entries-check & hash:")
                print("  remote:", sr, " local:", sl, " MATCH" if sr == sl else " MISMATCH")
                count = 0
                for raw in body.split(b"\n"):
                    line = raw.rstrip(b"\r")
                    if b"=" in line and not line.lstrip().startswith(b"#") and len(line) <= 1024:
                        count += 1
                print("  entries:", count)
    except Exception as e:
        print("%-10s FAILED: %s" % (name, e))
