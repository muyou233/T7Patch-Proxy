# -*- coding: utf-8 -*-
"""Prove Gitee raw is anonymous-accessible for reviewed public repos."""
import urllib.request

ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}
targets = [
    ("well-known public repo README",
     "https://gitee.com/oschina/git-osc/raw/master/README.md"),
    ("user's repo raw",
     "https://gitee.com/muyou2333/t7-patch-proxy-translate/raw/master/translate/translate_zh.txt"),
]
for name, url in targets:
    try:
        req = urllib.request.Request(url, headers=ua)
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            print("%s: HTTP %s, %d bytes" % (name, getattr(r, "status", r.getcode()), len(body)))
    except Exception as e:
        print("%s: FAILED %s" % (name, e))
