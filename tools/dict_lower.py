"""与引擎一致的"只小写 A-Z"（对应 `translate.cpp` 的 `LowerInPlace`）。

## 为什么不能直接用 `str.lower()`
Python 的 `str.lower()` 是 **Unicode 感知**的，会把 UTF-8 的 `Ü`(C3 9C) 变成 `ü`(C3 BC)；
而引擎的 `LowerInPlace()` **只对 A-Z 做 -0x20**，**非 ASCII 字节原样保留**
（`translate.cpp:317-322`，并在 `:638` 处理词库键、`:1118` 处理运行串）。

## 被这个差异坑过的实例（2026-09-18）
`Verrückt` 这张图在采集里有**两种字节形态**：`VERRÜCKT`(C3 9C) 与 `Verrückt`(C3 BC)。
引擎只小写 A-Z ⇒ 它们是**两个不同的键**，词库必须各写一条（`verrÜckt` / `verrückt`）。
而 `dict_verify.py` 当时用 `str.lower()` ⇒ 把两条键折叠成一条，**报了一个假重复键**，
并因为 `decode("ascii","replace")` 把 Ü 变成 `?` 而显示成 `verr??ckt`。

## 用法
    from dict_lower import dict_lower
    key = dict_lower(raw_bytes.decode("utf-8", "replace"))

注意：**直接对 `bytes` 调 `.lower()` 也是安全的**（Python 的 bytes.lower() 只动 A-Z，
与引擎等价），`match_sim.py` 正是这么做的，所以它不需要本模块。
"""


def dict_lower(s):
    """只把小写 A-Z 之外的东西原样保留（与引擎 LowerInPlace 同口径）。"""
    return "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in s)


def dict_lower_bytes(b):
    """bytes 版（等价于 bytes.lower()，写出来是为了让口径显式可见）。"""
    return bytes((x + 32) if 65 <= x <= 90 else x for x in b)
