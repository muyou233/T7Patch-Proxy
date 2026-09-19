# -*- coding: utf-8 -*-
r"""复现 "D3D11 backend found but could not be loaded"，把真实错误码读出来。

LoadLibrary 失败时 GetLastError 才是判据（我们现在的日志没记它，这是缺口）：
  126  = ERROR_MOD_NOT_FOUND      依赖模块找不到
  1114 = ERROR_DLL_INIT_FAILED    DllMain 返回 FALSE / 初始化失败
  193  = ERROR_BAD_EXE_FORMAT     位数不对
  5    = ERROR_ACCESS_DENIED
  998  = ERROR_NOACCESS           映射失败（常见于"被改名但仍被映射的镜像"）

在**独立进程**里加载，不碰游戏；DXVK 的 DllMain 会在本进程跑一遍，
这正是我们要复现的路径。
"""
import ctypes
import io
import os

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\probe_backend_load.txt"

TARGETS = [
    ("DXVK dxgi（原名，作为对照）", os.path.join(GAME, "dxgi.dll")),
    ("DXVK d3d11（收编后改名）", os.path.join(GAME, "d3d11_backend.dll")),
    ("我们的代理（对照）", os.path.join(GAME, "d3d11.dll")),
]

MEANING = {
    0: "OK",
    2: "ERROR_FILE_NOT_FOUND",
    5: "ERROR_ACCESS_DENIED",
    126: "ERROR_MOD_NOT_FOUND（依赖模块找不到）",
    127: "ERROR_PROC_NOT_FOUND（依赖里缺函数）",
    193: "ERROR_BAD_EXE_FORMAT（位数/格式不对）",
    998: "ERROR_NOACCESS（映射失败）",
    1114: "ERROR_DLL_INIT_FAILED（DllMain 初始化失败）",
    1157: "ERROR_DLL_NOT_FOUND（依赖清单里的模块缺失）",
}

lines = []
for label, path in TARGETS:
    if not os.path.exists(path):
        lines.append("%-28s (不存在)" % label)
        continue
    try:
        ctypes.WinDLL(path)
        lines.append("%-28s 加载成功（0 / OK）" % label)
    except OSError as exc:
        err = getattr(exc, "winerror", None)
        if err is None:
            err = ctypes.get_last_error()
        lines.append("%-28s 失败  错误码=%s  %s   (%s)"
                     % (label, err, MEANING.get(err, "?"), str(exc)[:80]))

lines.append("")
lines.append("对照：DXVK 的 dxgi 若能用原名加载成功，而 d3d11 改名后失败，")
lines.append("     就说明问题出在'改名'本身，而不是依赖缺失。")
io.open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print("\n".join(lines))
