"""社交界面（Steam 好友 / RECENT PLAYERS）里的名字，会不会被我们的词库翻掉？

背景（2026-09-16，用户提醒）：玩家名不只出现在房间 roster，社交界面还展示
Steam 好友。roster 方案（只读 12 槽）覆盖不到这些名字，所以必须知道：
  1. 这些名字是否真的经过我们的 hook？（判据：它们在 ui_dump.txt 里，
     而 ui_dump.txt 由 translate::Collect() 写出 —— 即 Lookup 那一步）
  2. 今天这份词库里，有几个会被翻掉？

判据复刻 match_sim.py：按控制字节切片段 -> 小写 -> 精确优先 / 模板窄先。
读：ui_dump.txt（社交区）、translate_zh.txt
写：social_names.txt
"""
import os
import io

REF = os.path.dirname(os.path.abspath(__file__))
GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
DICT = os.path.join(GAME, r"T7Patch\translate_zh.txt")
OUT = os.path.join(REF, "social_names.txt")

K_MAX_WILDCARDS = 8
# 控制字节 = < 0x20，外加 UI 里当分隔用的那几个高字节（与 C++ 的 NextRun 同口径）
CTRL_HI = (0x14, 0x15, 0x16, 0x17)


def is_ctrl(c):
    return c < 0x20 or c in CTRL_HI


def runs(s):
    """按控制字节切片段 —— 与 translate.cpp 的 NextRun 同口径。"""
    out, cur = [], bytearray()
    for c in s:
        if is_ctrl(c):
            if cur:
                out.append(bytes(cur))
                cur = bytearray()
        else:
            cur.append(c)
    if cur:
        out.append(bytes(cur))
    return out


def parse_dict(path):
    exact, patterns = {}, []
    for raw in open(path, "rb").read().split(b"\n"):
        if len(raw) > 1024:
            continue
        p = raw.lstrip(b" \t")
        if not p or p[:1] in (b"#", b";") or b"=" not in p:
            continue
        k, v = p.split(b"=", 1)
        k, v = k.rstrip(b" \t\r"), v.rstrip(b" \t\r\n")
        if not k or not v:
            continue
        k = k.lower()
        if b"*" in k:
            parts = k.split(b"*")
            if len(parts) - 1 <= K_MAX_WILDCARDS:
                patterns.append(parts)
        else:
            exact[k] = v
    patterns.sort(key=len)
    return exact, patterns


def match_template(parts, key):
    n = len(parts)
    if n < 2:
        return None
    head = parts[0]
    if not key.startswith(head):
        return None
    pos = len(head)
    for i in range(1, n - 1):
        at = key.find(parts[i], pos)
        if at < 0:
            return None
        pos = at + len(parts[i])
    tail = parts[-1]
    if not key.endswith(tail) or len(key) - len(tail) < pos:
        return None
    return True


def lookup(run, exact, patterns):
    """返回译文（bytes）或 None。"""
    key = run.lower()
    if key in exact:
        return exact[key]
    for parts in patterns:
        if match_template(parts, key):
            return b"<template:%s>" % b"*".join(parts)
    return None


def looks_like_name(t):
    if b" " in t or len(t) < 2 or len(t) > 24:
        return False
    if t.isdigit():
        return False
    return any(0x41 <= c <= 0x5A or 0x61 <= c <= 0x7A for c in t)


# dump 社交区（735-782 行）里人工认出来的名字。给 cluster 用，也给这里用。
FRIENDS = [
    "Aquila13", "AyerRex", "BB", "Bruce", "Crowea", "J", "happlyboy",
    "yasoft1", "JoeBidenshairyle", "Smirnoff[StPb]", "Oncent", "Ouicho",
    "#Mr.Nilsson#", "Peek Me Pookie",
    "muyou", "HanamaruZura", "Gimp",
]
# 同区里明显是界面词/组名的，当对照（应该被翻或已在库里）
CONTRAST = ["FRIENDS", "RECENT PLAYERS", "Online", "Offline", "Main Menu",
            "Prestige 2", "Invites", "Yes", "No", "Back"]


def main():
    o = []
    exact, patterns = parse_dict(DICT)
    o.append("词库: %d 条精确 + %d 条模板   (%s)" %
             (len(exact), len(patterns), os.path.basename(DICT)))

    dump = open(DUMP, "rb").read().split(b"\n")
    dump_set = set(x.strip() for x in dump)

    o.append("")
    o.append("=== 好友/玩家名（社交界面实测样本）===")
    o.append("  %-20s %-8s %s" % ("名字", "结果", "说明"))
    hits = []
    for nm in FRIENDS:
        b = nm.encode("utf-8")
        # 1) 该名字是否真在 dump 里（= 真的过了我们的 hook）
        in_dump = b in dump_set
        # 2) 是否会被翻
        got = lookup(b, exact, patterns)
        if got:
            hits.append((nm, got))
            verdict = "会被翻!"
        else:
            verdict = "原样"
        note = "dump 里有" if in_dump else "dump 里没有(未被捕捉)"
        o.append("  %-20s %-8s %s  -> %s" %
                 (nm, verdict, note, got.decode("utf-8", "replace") if got else "-"))

    o.append("")
    o.append("=== 对照组（界面词，应该被翻的那批）===")
    for nm in CONTRAST:
        b = nm.encode("utf-8")
        got = lookup(b, exact, patterns)
        o.append("  %-20s %s" % (nm, got.decode("utf-8", "replace") if got else "(未入库 -> 待补)"))

    o.append("")
    o.append("=== 全 dump 的「像名字的裸 token」碰撞面 ===")
    n_like = n_hit = 0
    collided = []
    for raw in dump:
        t = raw.strip()
        if not looks_like_name(t):
            continue
        n_like += 1
        got = lookup(t, exact, patterns)
        if got:
            n_hit += 1
            collided.append((t.decode("ascii", "replace"),
                             got.decode("utf-8", "replace")))
    o.append("  像名字的片段 %d 条，其中会被词库翻掉 %d 条" % (n_like, n_hit))
    o.append("  （这批就是「同一个串既是界面词又是用户名」的歧义集合）")
    for a, b in collided[:40]:
        o.append("    %-24s -> %s" % (a, b))
    if len(collided) > 40:
        o.append("    … 另 %d 条" % (len(collided) - 40))

    o.append("")
    o.append("结论：好友名命中 %d / %d" % (len(hits), len(FRIENDS)))

    io.open(OUT, "w", encoding="utf-8").write("\n".join(o))
    print("\n".join(o))


main()
