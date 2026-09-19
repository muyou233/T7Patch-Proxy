# -*- coding: utf-8 -*-
# 只读：把 DXVK 3.1.1 x64 里所有可打印 ASCII 串中的 conf 选项键名抽出来。
# DXVK 是运行时解析 dxvk.conf 的，所以它支持的每个键名都以字符串形式嵌在 DLL 里。
# 目的：确认 upstream 3.1.1 到底认不认 dxvk.enableAsync / dxvk.gplAsyncCache。
import io
import os
import re

TARGETS = [
    r"E:\Download\dxvk-3.1.1\x64\dxgi.dll",
    r"E:\Download\dxvk-3.1.1\x64\d3d11.dll",
]

KEY_RE = re.compile(r"^(?:dx|d3d)\w*\.[A-Za-z][A-Za-z0-9]{2,40}$")
SPLIT_RE = re.compile(r"[\s,;=]+")
ASCII_RE = re.compile(rb"[ -~]{4,200}")

PROBES = [
    "enableAsync",
    "gplAsyncCache",
    "enableGraphicsPipelineLibrary",
    "numCompilerThreads",
    "tearFree",
    "maxFrameRate",
    "maxFrameLatency",
    "dxvk.conf",
    "unknown option",
    "hud",
    "compiler",
]

out = []
for t in TARGETS:
    data = io.open(t, "rb").read()
    strs = [m.group().decode("ascii", "ignore") for m in ASCII_RE.finditer(data)]
    keys = set()
    for s in strs:
        for part in SPLIT_RE.split(s):
            if KEY_RE.match(part):
                keys.add(part)

    out.append("=== %s  (%.2f MB, %d strings) ===" % (os.path.basename(t), len(data) / 1048576.0, len(strs)))
    out.append("  -- 该 DLL 里出现的 conf 键名（共 %d）--" % len(keys))
    for k in sorted(keys):
        out.append("     " + k)
    out.append("")
    out.append("  -- 关键词探测 --")
    for kw in PROBES:
        hits = [s for s in strs if kw.lower() in s.lower()]
        sample = ""
        if hits:
            sample = hits[0].strip()[:100]
        out.append("     %-32s hits=%d   %s" % (kw, len(hits), sample))
    out.append("")

# 全局结论
out.append("=== 结论 ===")
blob = b""
for t in TARGETS:
    blob += io.open(t, "rb").read()
for kw in ["enableAsync", "gplAsyncCache", "enableGraphicsPipelineLibrary"]:
    out.append("  %-32s 存在于 3.1.1 x64 : %s" % (kw, kw.encode() in blob))

io.open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\dxvk_opts.txt", "w", encoding="utf-8").write("\n".join(out))
print("written")
