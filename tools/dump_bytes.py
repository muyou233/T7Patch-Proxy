"""看清 ui_dump.txt 里「带特殊字节」的串到底是什么字节（决定要不要做分段匹配）。"""
import os

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\dump_bytes.txt"

data = open(DUMP, "rb").read()
lines = data.split(b"\n")

odd = []
seen = set()
for ln in lines:
    raw = ln.rstrip(b"\r")
    body = raw
    i, j = 0, len(body)
    while i < j and body[i] < 0x20:
        i += 1
    while j > i and body[j - 1] < 0x20:
        j -= 1
    body = body[i:j]
    if not body:
        continue
    weird = [(k, b) for k, b in enumerate(body) if b < 0x20 or b > 0x7E]
    if not weird:
        continue
    key = bytes(b for _, b in weird)
    if key in seen:
        continue
    seen.add(key)
    odd.append((key, body))

out = ["带特殊字节的串 %d 条（按「出现的特殊字节组合」去重）" % len(odd), ""]
for key, body in odd[:40]:
    out.append("bytes=%s  %s" % (key.hex(" "), repr(body)[2:-1][:200]))

with open(OUT, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print("written", OUT)
