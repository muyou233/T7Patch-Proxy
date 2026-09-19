r"""BO3 语言包备份 / 还原（只复制，不删除任何东西）。

背景：Steam 只为「当前选中的语言」安装对应的本地化文件，切成别的语言时旧语言文件会被删掉，
切回来就要重新下载。把语言包复制一份到别处，万一误切可以直接拷回来，不用重下。

用法（Python 在 C:\\Users\\muyou\\.workbuddy\\binaries\\python\\versions\\3.13.12\\python.exe）：
    python langpack_backup.py list      [备份目录]   仅列出会被处理的文件与合计大小
    python langpack_backup.py backup    [备份目录]   游戏目录 -> 备份目录
    python langpack_backup.py restore   [备份目录]   备份目录 -> 游戏目录
    python langpack_backup.py status    [备份目录]   对比两边
备份目录默认 <项目>/.codebuddy/langpack_backup（被 git 忽略）。

判定「哪些是语言文件」的规则：游戏目录的 localization.txt + `zone\` **顶层**里文件名以语言前缀开头的文件
（如 `en_core_ui.ff` / `sc_base.xpak`）。
⚠️ 只取 zone 顶层：`zone\snd\<lang>\` 那类音频目录**不随语言切换**（实测切成中文后 `zone\snd\en`
的 6.8 GB 英语语音仍在原地），把它们算进来会让备份从 174 MB 变成 6.8 GB。
实测体积（2026-09-15）：英文 189 个 / 171 MB，中文 189 个 / 174 MB，其中 125 个文件两边**字节数完全相同**
（语言无关的资源），真正的语言差异约 12 MB。
"""
import os
import shutil
import sys

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DEFAULT_DST = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\.codebuddy\langpack_backup"
LANGS = ("en", "sc", "tc", "ch", "zh", "es", "fr", "de", "ge", "it", "ja", "po", "ru", "ea", "bp")


def collect():
    """只收 zone 顶层的语言前缀文件 + localization.txt（见文件头说明）。"""
    out = []
    zone = os.path.join(GAME, "zone")
    if os.path.isdir(zone):
        for name in os.listdir(zone):
            full = os.path.join(zone, name)
            if not os.path.isfile(full):
                continue
            if any(name.lower().startswith(lang + "_") for lang in LANGS):
                out.append(os.path.join("zone", name))
    loc = "localization.txt"
    if os.path.exists(os.path.join(GAME, loc)):
        out.append(loc)
    return sorted(out)


def human(n):
    return "%s B (%.1f MB)" % (format(n, ","), n / 1048576.0)


def cmd_list(dst):
    files = collect()
    total = sum(os.path.getsize(os.path.join(GAME, f)) for f in files)
    print("游戏目录：%s" % GAME)
    print("语言相关文件 %d 个，合计 %s" % (len(files), human(total)))
    for f in files[:15]:
        print("   %s" % f)
    if len(files) > 15:
        print("   ...（其余 %d 个）" % (len(files) - 15))


def cmd_backup(dst):
    files = collect()
    total = 0
    for rel in files:
        src = os.path.join(GAME, rel)
        out = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shutil.copy2(src, out)
        n = os.path.getsize(src)
        total += n
        if os.path.getsize(out) != n:
            print("!! 大小不一致：%s" % rel)
            return 1
    print("已备份 %d 个文件到 %s（%s）" % (len(files), dst, human(total)))
    print("以后误切语言：python langpack_backup.py restore \"%s\"" % dst)
    return 0


def cmd_restore(dst):
    if not os.path.isdir(dst):
        print("备份目录不存在：%s" % dst)
        return 1
    files = []
    for root, _dirs, fs in os.walk(dst):
        for name in fs:
            full = os.path.join(root, name)
            files.append(os.path.relpath(full, dst))
    total = 0
    for rel in files:
        src = os.path.join(dst, rel)
        out = os.path.join(GAME, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shutil.copy2(src, out)
        total += os.path.getsize(src)
        if os.path.getsize(out) != os.path.getsize(src):
            print("!! 大小不一致：%s" % rel)
            return 1
    print("已从备份还原 %d 个文件到游戏目录（%s）" % (len(files), human(total)))
    print("注意：还原后请在 Steam 里把游戏语言设成备份对应的语言，否则 Steam 可能又把它删掉。")
    return 0


def cmd_status(dst):
    files = collect()
    print("游戏目录语言文件 %d 个" % len(files))
    same = diff = 0
    for rel in files:
        b = os.path.join(dst, rel)
        if not os.path.exists(b):
            diff += 1
            continue
        if os.path.getsize(b) == os.path.getsize(os.path.join(GAME, rel)):
            same += 1
        else:
            diff += 1
    print("与备份一致 %d 个，不一致/缺失 %d 个" % (same, diff))


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else "list"
    dst = args[1] if len(args) > 1 else DEFAULT_DST
    if cmd == "list":
        return cmd_list(dst)
    if cmd == "backup":
        return cmd_backup(dst)
    if cmd == "restore":
        return cmd_restore(dst)
    if cmd == "status":
        return cmd_status(dst)
    print(__doc__)
    return 2


sys.exit(main())
