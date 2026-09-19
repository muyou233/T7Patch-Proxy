# -*- coding: utf-8 -*-
"""Anonymous-visitor check: repo home vs raw file."""
import urllib.request

targets = [
    ("repo home", "https://gitee.com/muyou2333/t7-patch-proxy-translate"),
    ("tree page", "https://gitee.com/muyou2333/t7-patch-proxy-translate/tree/master/translate"),
    ("raw file", "https://gitee.com/muyou2333/t7-patch-proxy-translate/raw/master/translate/translate_zh.txt"),
    ("gitee home", "https://gitee.com"),
]
ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}
for name, url in targets:
    try:
        req = urllib.request.Request(url, headers=ua)
        with urllib.request.urlopen(req, timeout=30) as r:
            print("%-10s HTTP %s" % (name, getattr(r, "status", r.getcode())))
    except Exception as e:
        print("%-10s FAILED: %s" % (name, e))
