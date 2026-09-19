# -*- coding: utf-8 -*-
data = open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\x64\Release\d3d11.dll", "rb").read()
for label, s in [
    ("gitee api url", "gitee.com/api/v5/repos/muyou23333"),
    ("gitee raw url (old, should be gone)", "gitee.com/muyou2333/t7-patch-proxy-translate/raw"),
    ("github url", "raw.githubusercontent.com/muyou233/T7Patch-Proxy"),
]:
    u = s.encode("utf-16-le")
    print("%-38s %s" % (label, "FOUND" if u in data else "ABSENT"))
