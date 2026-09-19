r"""确认 t7patch.log 的编码：找到 hit: 行，把替换结果按原始字节 dump 出来，
再分别按 UTF-8 / GBK 解码，判断日志里存的是哪种编码、以及我们的译文本身是否有效。
"""
import io

LOG = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\T7Patch\t7patch.log"
REPORT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\log_encoding.txt"

data = open(LOG, "rb").read()
out = []
out.append("log = %s (%d bytes)" % (LOG, len(data)))
out.append("BOM: utf8=%s utf16le=%s" % (data[:3] == b"\xef\xbb\xbf", data[:2] == b"\xff\xfe"))

needle = b"quick join"
idx = data.rfind(needle)
out.append("")
out.append("last 'quick join' hit at offset %d" % idx)
if idx >= 0:
    end = data.find(b"\n", idx)
    line = data[idx:end if end > 0 else len(data)]
    out.append("raw line bytes (hex, first 96):")
    out.append("  " + " ".join("%02X" % b for b in line[:96]))
    out.append("as utf-8 : %r" % line.decode("utf-8", "replace"))
    out.append("as gbk   : %r" % line.decode("gbk", "replace"))
    out.append("as latin1: %r" % line.decode("latin-1", "replace"))

# How many lines in the log are valid utf-8 vs gbk as a whole?
u8_ok = gbk_ok = 0
for ln in data.split(b"\n"):
    try:
        ln.decode("utf-8")
        u8_ok += 1
    except UnicodeDecodeError:
        pass
    try:
        ln.decode("gbk")
        gbk_ok += 1
    except UnicodeDecodeError:
        pass
out.append("")
out.append("lines total=%d  decodable as utf-8=%d  as gbk=%d" %
           (len(data.split(b"\n")), u8_ok, gbk_ok))

with io.open(REPORT, "w", encoding="utf-8") as f:
    f.write("\n".join(out) + "\n")
print("report -> %s" % REPORT)
