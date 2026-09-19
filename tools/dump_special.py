"""列出采集里含 ^ (颜色码) 或 $ (绑定) 的串 —— 这些整串也能翻，只要把 ^..^ / $(..) 原样抄进词条。"""
import os

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\dump_special.txt"

seen = set()
rows = []
for ln in open(DUMP, "rb").read().split(b"\n"):
    b = ln.rstrip(b"\r")
    i, j = 0, len(b)
    while i < j and b[i] < 0x20:
        i += 1
    while j > i and b[j - 1] < 0x20:
        j -= 1
    b = b[i:j]
    if not b or any(c < 0x20 for c in b) or any(c >= 0x80 for c in b):
        continue
    if not any(c in b"^$" for c in b):
        continue
    t = b.decode("ascii")
    if t.lower() in seen:
        continue
    seen.add(t.lower())
    rows.append(t)

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("含 ^ / $ 的唯一串 %d 条：\n\n" % len(rows))
    fh.write("\n".join(rows))
print("written", OUT, len(rows))
