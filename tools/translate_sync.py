r"""词库同步 / 更新（只碰数据，不碰二进制）。

约定：仓库里的 `translate/translate_zh.txt` 是**唯一源**；游戏目录那份是部署产物。

    python translate_sync.py status            # 对比 源 <-> 游戏目录（条目数/version/sha256）
    python translate_sync.py deploy            # 源 -> 游戏目录（校验 + 原子替换 + 留 .old）
    python translate_sync.py pull   [--url U]  # 远端 -> 源（HTTPS 下载 + 校验；默认取仓库 raw）
    python translate_sync.py update [--url U]  # pull + deploy
    python translate_sync.py clean             # 删掉 deploy/pull 留下的 .old/.new/.download

替换是**原子**的（同目录临时文件 -> os.replace），并且**一定会更新 mtime** —— 补丁的词库热加载
看的正是 mtime，所以换完之后不需要重启游戏，下一次构建界面文本时（约 2 秒）就会用上新词库。

下载校验：要求正文是 UTF-8、至少有一条 `=` 条目、且条目数不比现有源少太多（防止把 404 页面
或半截文件当成词库写进去）；不满足就拒绝、不覆盖。
"""
import argparse
import hashlib
import os
import re
import shutil
import sys
import urllib.request

GAME_DICT = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\T7Patch\translate_zh.txt"
REPO_DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
RAW_URL = "https://raw.githubusercontent.com/muyou233/T7Patch-Proxy/main/translate/translate_zh.txt"

VERSION_RE = re.compile(rb"^#\s*version:\s*(\S+)", re.I | re.M)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def entries(path):
    """非空、非注释的行数（补丁的加载口径：跳过 # / ; 开头和空行）。"""
    n = 0
    with open(path, "rb") as fh:
        for line in fh:
            s = line.strip()
            if s and not s.startswith((b"#", b";")) and b"=" in s:
                n += 1
    return n


def version(path):
    with open(path, "rb") as fh:
        m = VERSION_RE.search(fh.read(4096))
    return m.group(1).decode("ascii", "replace") if m else "(无)"


def describe(tag, path):
    if not os.path.exists(path):
        return "%-10s %s  <缺失>" % (tag, path)
    return "%-10s %-58s %6d 条  version=%-12s sha256=%s" % (
        tag, path, entries(path), version(path), sha256(path)[:16])


def atomic_write(src_path, dst_path, keep_old=True):
    """把 src 的内容原子地写到 dst；同目录临时文件 + os.replace。"""
    dst_dir = os.path.dirname(dst_path)
    tmp = os.path.join(dst_dir, os.path.basename(dst_path) + ".new")
    shutil.copyfile(src_path, tmp)
    if os.path.getsize(tmp) != os.path.getsize(src_path):
        os.remove(tmp)
        raise RuntimeError("复制不完整")
    if keep_old and os.path.exists(dst_path):
        shutil.copyfile(dst_path, dst_path + ".old")
    os.replace(tmp, dst_path)   # 原子；同时更新 mtime -> 触发游戏内热加载
    return True


def cmd_status(args):
    print(describe("source", REPO_DICT))
    print(describe("game", GAME_DICT))
    if os.path.exists(REPO_DICT) and os.path.exists(GAME_DICT):
        same = sha256(REPO_DICT) == sha256(GAME_DICT)
        print("一致" if same else "**不一致**（deploy 可同步；游戏里那份可能是临时手改的）")
    return 0


def cmd_deploy(args):
    if not os.path.exists(REPO_DICT):
        print("源不存在：%s" % REPO_DICT)
        return 1
    before = sha256(GAME_DICT) if os.path.exists(GAME_DICT) else ""
    atomic_write(REPO_DICT, GAME_DICT)
    print("已部署：%s" % describe("game", GAME_DICT))
    print("替换前 sha256=%s" % (before[:16] or "(原先不存在)"))
    print("旧的已留档：%s.old" % GAME_DICT)
    print("游戏内约 2 秒后热加载（无需重启游戏）。")
    return 0


def cmd_pull(args):
    url = args.url or RAW_URL
    print("下载：%s" % url)
    req = urllib.request.Request(url, headers={"User-Agent": "t7patch-dict-sync"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
    print("收到 %d 字节" % len(data))

    # 粗略校验：UTF-8、有注释头、条目数不至于腰斩（防 404 页面 / 半截文件）
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        print("拒绝：不是 UTF-8")
        return 1
    if "=" not in text or "#" not in text:
        print("拒绝：正文不像词库（没有 '=' 或 '#')")
        return 1
    new_n = sum(1 for ln in text.splitlines()
                if ln.strip() and not ln.lstrip().startswith(("#", ";")) and "=" in ln)
    old_n = entries(REPO_DICT) if os.path.exists(REPO_DICT) else 0
    if old_n and new_n < old_n * 0.8:
        print("拒绝：远端条目数 %d 明显少于本地 %d（疑似半截/异常文件）" % (new_n, old_n))
        return 1
    print("远端条目数 %d（本地 %d）" % (new_n, old_n))

    tmp = REPO_DICT + ".download"
    with open(tmp, "wb") as fh:
        fh.write(data)
    if os.path.exists(REPO_DICT):
        shutil.copyfile(REPO_DICT, REPO_DICT + ".old")
    os.replace(tmp, REPO_DICT)
    print("已更新源：%s" % describe("source", REPO_DICT))
    print("（下一步 deploy 才会进游戏目录；或直接 update）")
    return 0


def cmd_update(args):
    rc = cmd_pull(args)
    if rc != 0:
        return rc
    return cmd_deploy(args)


def cmd_clean(args):
    """删掉部署/下载留下的备份与临时文件。

    deploy 会先留一份 .old 再原子替换（游戏目录里那个"你从没创建过、
    也不知道哪来的" translate_zh.txt.old 就是它）。留着无害 —— 游戏只读
    translate_zh.txt，那个文件更不会堆积（名字固定，每次覆盖）—— 但有人
    会不想看到它，这就是那个"一步清掉"的动作。

    只删下面这几个**已知后缀**，不做任何通配匹配，也不动词库本体。
    """
    targets = (GAME_DICT + ".old", GAME_DICT + ".new",
               REPO_DICT + ".old", REPO_DICT + ".download")
    removed = [p for p in targets if os.path.exists(p)]
    for p in removed:
        os.remove(p)
    if removed:
        for p in removed:
            print("已删除：%s" % p)
    else:
        print("没有可清理的备份/临时文件。")
    print("（词库本体一个都没动：%s）" % GAME_DICT)
    return 0


def main():
    ap = argparse.ArgumentParser(description="T7Patch 词库同步 / 更新")
    ap.add_argument("cmd", choices=["status", "deploy", "pull", "update", "clean"])
    ap.add_argument("--url", default=None, help="覆盖下载地址")
    args = ap.parse_args()
    return {"status": cmd_status, "deploy": cmd_deploy,
            "pull": cmd_pull, "update": cmd_update,
            "clean": cmd_clean}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
