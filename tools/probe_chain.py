# -*- coding: utf-8 -*-
r"""验证部署件里确实带着"链式 D3D11 后端"这套逻辑，且它认得出 DXVK 后端。

宽字面量在二进制里是 UTF-16LE、窄字面量是 ASCII/UTF-8，两种编码都搜。
另外把 d3d11_backend.dll 也看一眼：确认它确实是 DXVK 的（不是我们的）。
"""
import io
import os

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
FRONT = os.path.join(GAME, "d3d11.dll")
BACKEND = os.path.join(GAME, "d3d11_backend.dll")
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\probe_chain.txt"

MUST_BE_PRESENT = [
    "d3d11_backend.dll",          # 首选后端文件名（宽）
    "d3d11_dxvk.dll",             # 别名
    "D3D11 backend",              # 日志格式串（窄）
    "System32 fills %d, %d missing",
    "no provider for export",
    "proxy: real d3d11.dll resolved",   # 无后端时的老路径仍在
]


def has(data, text):
    hits = []
    for enc in ("utf-16-le", "utf-8"):
        try:
            if text.encode(enc) in data:
                hits.append(enc)
        except UnicodeEncodeError:
            pass
    return hits


front = io.open(FRONT, "rb").read()
backend = io.open(BACKEND, "rb").read() if os.path.exists(BACKEND) else b""

lines = ["front   = d3d11.dll          %d bytes" % len(front),
         "backend = d3d11_backend.dll  %d bytes" % len(backend), ""]

ok = True
lines.append("== 部署件里必须有的串 ==")
for text in MUST_BE_PRESENT:
    enc = has(front, text)
    lines.append("   %-38s %s" % (text, ",".join(enc) if enc else "MISSING"))
    if not enc:
        ok = False

lines.append("")
lines.append("== 两边是不是各就各位 ==")
front_is_ours = has(front, "proxy: D3D11 backend") or has(front, "proxy: real d3d11.dll resolved")
backend_is_dxvk = b"DXVK" in backend or b"dxvk" in backend
backend_is_ours = has(backend, "proxy: D3D11 backend")
lines.append("   front 是我们的代理      : %s" % bool(front_is_ours))
lines.append("   backend 是 DXVK         : %s" % bool(backend_is_dxvk))
lines.append("   backend 不是我们的      : %s" % (not backend_is_ours))
if not (front_is_ours and backend_is_dxvk and not backend_is_ours):
    ok = False

lines.append("")
lines.append("RESULT: " + ("OK" if ok else "FAIL"))
io.open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("done")
