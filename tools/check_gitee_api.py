# -*- coding: utf-8 -*-
"""Gitee API v5 check: does the repo exist publicly?"""
import json
import urllib.request

ua = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0"}
targets = [
    ("repo api", "https://gitee.com/api/v5/repos/muyou2333/t7-patch-proxy-translate"),
    ("raw via api ref", "https://gitee.com/api/v5/repos/muyou2333/t7-patch-proxy-translate/contents/translate/translate_zh.txt?ref=master"),
]
for name, url in targets:
    try:
        req = urllib.request.Request(url, headers=ua)
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8", "replace")
            print("%-16s HTTP %s len=%d" % (name, getattr(r, "status", r.getcode()), len(body)))
            if name == "repo api":
                d = json.loads(body)
                print("  full_name =", d.get("full_name"))
                print("  private   =", d.get("private"))
                print("  license   =", (d.get("license") or {}).get("name"))
                print("  default_branch =", d.get("default_branch"))
    except Exception as e:
        print("%-16s FAILED: %s" % (name, e))
