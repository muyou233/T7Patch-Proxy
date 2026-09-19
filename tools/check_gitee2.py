# -*- coding: utf-8 -*-
import hashlib, sys, urllib.request
URL = "https://gitee.com/muyou2333/t7-patch-proxy-translate/raw/master/translate/translate_zh.txt"
LOCAL = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
out = []
for ua in ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"]:
    req = urllib.request.Request(URL, headers={"User-Agent": ua, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            out.append("HTTP %s (ua=%s...)" % (getattr(r, "status", r.getcode()), ua[:20]))
            body = r.read()
        break
    except Exception as e:
        out.append("FAILED (%s...): %r" % (ua[:20], e))
        body = None
if body is not None:
    count = 0
    for raw in body.split(b"\n"):
        line = raw.rstrip(b"\r")
        ln = len(line)
        if ln == 0 or ln > 1022: continue
        i = 0
        while i < ln and line[i:i+1] in (b" ", b"\t"): i += 1
        if i >= ln or line[i:i+1] in (b"#", b";"): continue
        if b"=" in line[i:]: count += 1
    out.append("bytes=%d entries=%d" % (len(body), count))
    sha_r = hashlib.sha256(body).hexdigest()
    sha_l = hashlib.sha256(open(LOCAL, "rb").read()).hexdigest()
    out.append("remote: " + sha_r[:16])
    out.append("local : " + sha_l[:16])
    out.append("MATCH" if sha_r == sha_l else "MISMATCH")
print("\n".join(out))
