# -*- coding: utf-8 -*-
"""Check the Gitee mirror URL anonymously and compare bytes with the repo copy."""
import hashlib
import sys
import urllib.request

URL = ("https://gitee.com/muyou2333/t7-patch-proxy-translate"
       "/raw/master/translate/translate_zh.txt")
LOCAL = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"

out = []
req = urllib.request.Request(URL, headers={"User-Agent": "t7patch-check/1.0"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        out.append("HTTP %s" % getattr(r, "status", r.getcode()))
        body = r.read()
except Exception as e:
    out.append("FETCH FAILED: %r" % (e,))
    print("\n".join(out))
    sys.exit(1)

count = sum(
    1 for raw in body.split(b"\n")
    if (ln := len(raw.rstrip(b"\r"))) and 0 < ln <= 1022
    and (s := next((i for i in range(ln) if raw[i:i+1] not in (b" ", b"\t")), ln)) < ln
    and raw[s:s+1] not in (b"#", b";")
    and b"=" in raw[s:]
)
out.append("downloaded: %d bytes, entries: %d" % (len(body), count))
sha_r = hashlib.sha256(body).hexdigest()
sha_l = hashlib.sha256(open(LOCAL, "rb").read()).hexdigest()
out.append("remote: %s" % sha_r[:16])
out.append("local : %s" % sha_l[:16])
out.append("MATCH" if sha_r == sha_l else "MISMATCH")
print("\n".join(out))
