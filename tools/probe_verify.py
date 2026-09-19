"""部署前/后校验：新探针代码真的进了 dll 吗？

上次踩过的坑：构建失败时 rc 非 0 但旧产物会被照常部署，只看"部署成功"会误判。
Release 没有符号，所以用**字符串 + 词库锚点**做指纹：

  A. 探针字符串在不在（`ui_callers.txt`、表头里的 `caller-site probe`）
  B. 内置词库还在不在，且是不是当前源（首尾锚定 + version 行）
  C. 构建产物与部署产物的 sha256 是否一致

用法：probe_verify.py [--require-probe]
"""
import hashlib
import io
import os
import sys

SRC = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private"
BUILT = os.path.join(SRC, r"x64\Release\d3d11.dll")
GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DEPLOYED = os.path.join(GAME, "d3d11.dll")
DICT = os.path.join(SRC, r"translate\translate_zh.txt")
OUT = os.path.join(SRC, r"tools\probe_verify.txt")

PROBE_MARKERS = [b"ui_callers.txt", b"caller-site probe"]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    require_probe = "--require-probe" in sys.argv
    o = []

    if not os.path.exists(BUILT):
        o.append("找不到构建产物 %s" % BUILT)
        open(OUT, "w", encoding="utf-8").write("\n".join(o))
        print("written", OUT)
        return

    blob = open(BUILT, "rb").read()
    o.append("built:    %s  %d B  sha256 %s" % (
        os.path.basename(BUILT), len(blob), sha256(BUILT)[:16].upper()))

    o.append("")
    o.append("=== A. 探针指纹 ===")
    for marker in PROBE_MARKERS:
        n = blob.count(marker)
        o.append("  %-22s %s (x%d)" % (marker.decode(), "FOUND" if n else "MISSING", n))
    probe_ok = all(blob.count(m) for m in PROBE_MARKERS)

    # 内置词库：首尾锚定。rc.exe 嵌进去的区域不是源文件的等长副本，
    # 整文件搜索会假阴性（§65 教训），所以只锚首尾各 64 字节。
    o.append("")
    o.append("=== B. 内置词库 ===")
    raw = open(DICT, "rb").read()
    head, tail = raw[:64], raw[-64:]
    head_at, tail_at = blob.find(head), blob.find(tail)
    o.append("  源文件 %d B, 首行 %s" % (
        len(raw), raw.split(b"\n", 1)[0].decode("utf-8", "replace")))
    o.append("  首锚 @%s   尾锚 @%s" % (head_at, tail_at))
    dict_ok = head_at > 0 and tail_at > head_at
    o.append("  逐字节区间一致: %s" % (
        blob[head_at:tail_at + 64] == raw if dict_ok else "n/a"))

    o.append("")
    o.append("=== C. 部署产物 ===")
    if os.path.exists(DEPLOYED):
        same = sha256(DEPLOYED) == sha256(BUILT)
        o.append("  deployed: %d B, sha256 %s" % (
            os.path.getsize(DEPLOYED), sha256(DEPLOYED)[:16].upper()))
        o.append("  与构建产物一致: %s" % same)
    else:
        same = False
        o.append("  游戏目录里没有 d3d11.dll")

    o.append("")
    verdict = []
    verdict.append("probe strings: %s" % ("OK" if probe_ok else "MISSING"))
    verdict.append("embedded dict: %s" % ("OK" if dict_ok else "BROKEN"))
    verdict.append("deployed copy: %s" % ("OK" if same else "NOT DEPLOYED / DIFFERS"))
    if require_probe and not probe_ok:
        verdict.append("RESULT: FAIL - 构建产物里没有探针代码，这次构建没编进去")
    else:
        verdict.append("RESULT: %s" % ("PASS" if (probe_ok and dict_ok and same) else "CHECK ABOVE"))
    o.append(" | ".join(verdict))

    open(OUT, "w", encoding="utf-8").write("\n".join(o))
    print("written", OUT)


main()
