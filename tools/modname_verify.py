# -*- coding: utf-8 -*-
# 用与 translate.cpp 相同的算法（ParseDictionaryBuffer / NextRun / LookupKeyLocked）
# 拿游戏目录 ui_dump.txt 的原始字节做全量回放，看新条目到底命中什么、输出长什么样。
import os, hashlib

REPO = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
DUMP = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\T7Patch\ui_dump.txt"
K_MAX_WILDCARDS = 8

def trim_trailing(b):
    return b.rstrip(b" \t\r\n")

def parse(path):
    exact, pats, dup = {}, [], []
    for raw in open(path, "rb").read().split(b"\n"):
        if len(raw) > 1024 - 2:
            continue
        p = raw.lstrip(b" \t")
        if not p or p[:1] in (b"#", b";") or b"=" not in p:
            continue
        k, v = p.split(b"=", 1)
        k, v = trim_trailing(k), trim_trailing(v)
        if not k or not v:
            continue
        k = k.lower()
        if b"*" in k:
            parts = k.split(b"*")
            if len(parts) - 1 <= K_MAX_WILDCARDS:
                pats.append(parts)
        else:
            if k in exact:
                dup.append(k)
            exact[k] = v
    pats.sort(key=len)          # 窄模板先试（stable_sort 等价）
    return exact, pats, dup

def next_runs(s):
    """返回 run 的 (body 字节) 列表：只按 <0x20 的真控制字节切段，首尾只裁空格。"""
    out, i, n = [], 0, len(s)
    while i < n:
        while i < n and s[i] < 0x20:
            i += 1
        if i >= n:
            break
        j = i
        while j < n and s[j] >= 0x20:
            j += 1
        b, e = i, j
        while b < e and s[b] == 0x20:
            b += 1
        while e > b and s[e - 1] == 0x20:
            e -= 1
        if e > b:
            out.append(s[b:e])
        i = j
    return out

def match_template(parts, key):
    if len(parts) < 2:
        return None
    head = parts[0]
    if not key.startswith(head):
        return None
    pos = len(head)
    for mid in parts[1:-1]:
        at = key.find(mid, pos)
        if at < 0:
            return None
        pos = at + len(mid)
    tail = parts[-1]
    if not key.endswith(tail) or len(key) - len(tail) < pos:
        return None
    return True

exact, pats, dup = parse(REPO)
out = []
out.append("词库：%s" % os.path.basename(REPO))
out.append("词库解析：精确 %d / 模板 %d / 重复键 %d" % (len(exact), len(pats), len(dup)))
for d in dup:
    out.append("   !! 重复键: %s" % d.decode("utf-8", "replace"))

# 新条目的键是否真的在表里（直接查表，绕开一切匹配歧义）
NEW_KEYS = [
    b"^1[zm] ^3all-around enhancement v3.9.5 ^7lite",
    b"^1[zm] ^3all-around enhancement v3.9.5",
    b"[ + ]  ^1[zm] ^3all-around enhancement v3.9.5 ^7lite",
    b"[ + ]  ^1[zm] ^3all-around enhancement v3.9.5",
]
out.append("")
out.append("=== 新条目在精确表里的查表结果 ===")
for k in NEW_KEYS:
    v = exact.get(k)
    out.append("  %s  ->  %s" % ("OK " if v else "MISS", v.decode("utf-8", "replace") if v else "(不在表里!)"))

hits = {}
scanned = 0
for line in open(DUMP, "rb").read().split(b"\n"):
    if not line:
        continue
    scanned += 1
    for run in next_runs(line):
        key = run.lower()
        rep = exact.get(key)
        if rep is None:
            for p in pats:
                if match_template(p, key):
                    rep = b"<template>"
                    break
        if rep is not None:
            hits.setdefault((run, rep), 0)
            hits[(run, rep)] += 1

out.append("")
out.append("回放（真实算法跑 dump 的每个片段）：dump %d 行，命中 %d 种 (原文 → 译文) 组合"
           % (scanned, len(hits)))
out.append("")
out.append("=== 与 All-around 相关的命中 ===")
n = 0
for (run, rep), c in sorted(hits.items(), key=lambda kv: -kv[1]):
    if b"all-around" in run.lower():
        n += 1
        out.append("  x%-3d %s" % (c, run.decode("utf-8", "replace")))
        out.append("       -> %s" % rep.decode("utf-8", "replace"))
if n == 0:
    out.append("  (一条都没命中 —— 有问题！)")
out.append("")
out.append("=== 词库 sha / 规模 ===")
b = open(REPO, "rb").read()
out.append("  %d B  sha256=%s  行数=%d" % (len(b), hashlib.sha256(b).hexdigest().upper()[:16], b.count(b"\n")))

open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\modname_verify.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
print("ok")
