# -*- coding: utf-8 -*-
data = open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\x64\Release\d3d11.dll", "rb").read()
for label, s in [
    ("github raw url", "raw.githubusercontent.com/muyou233/T7Patch-Proxy"),
    ("gitee api url", "gitee.com/api/v5/repos/muyou23333"),
    ("jsdelivr url", "cdn.jsdelivr.net/gh/muyou233/T7Patch-Proxy@main"),
]:
    u = s.encode("utf-16-le")
    print("%-16s %s" % (label, "FOUND" if u in data else "ABSENT"))
