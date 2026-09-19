"""确认新构建里确实带着本轮改动（内置词库 / 新提示文案）。"""
DLL = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\x64\Release\d3d11.dll"
b = open(DLL, "rb").read()
probes = [
    ("词库版本号", "2026-09-16b".encode("utf-8")),
    ("内置新条目：工坊模组栈", "工坊模组栈 / 就绪".encode("utf-8")),
    ("内置新条目：聊天指令", "/tps：切换第三人称视角。".encode("utf-8")),
    ("新 tooltip（中）", "遇到卡顿时可尝试打开".encode("utf-8")),
    ("新 tooltip（英）", b"Try this if you see stutter"),
    ("旧默认注释痕迹（应为 0）", "default: enabled".encode("utf-8")),
]
for name, needle in probes:
    print("%-28s %s" % (name, "命中 x%d" % b.count(needle) if needle in b else "**缺失**"))
print("dll 大小", len(b))
