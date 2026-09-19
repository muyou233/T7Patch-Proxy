# -*- coding: utf-8 -*-
"""Verify both source URLs exist (as UTF-16) in the deployed d3d11.dll."""
DLL = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\d3d11.dll"
data = open(DLL, "rb").read()

def has_wide(s):
    return s.encode("utf-16-le") in data

print("github url :", has_wide("https://raw.githubusercontent.com/muyou233/T7Patch-Proxy/main/translate/translate_zh.txt"))
print("gitee  url :", has_wide("https://gitee.com/muyou2333/t7-patch-proxy-translate/raw/master/translate/translate_zh.txt"))
print("cooldown 60:", has_wide("cooldown (60 s)"))
