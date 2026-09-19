"""离线模拟新的 translate.cpp 匹配逻辑，用真实词库 + 真实采集串算「能翻多少」。

严格照抄 C++ 的语义：
  · 按控制字节切「片段」，片段两侧空格裁掉后查表
  · 命中优先：精确条目 > 模板（'*' 少的先试）> 可组合片段（键以 '~' 标记，最长的先试）
  · 模板：首个字面块必须在前、末块必须在后、中间块取最早出现；值里的 '*' 按序填回原文
  · 片段（2026-09-18 新增）：单遍左到右，命中最长的一条后跳过去，不回扫；值里的中文
    不会再被别的片段处理；一条都没命中就保持原文

默认检查**源词库**（`translate/translate_zh.txt`）——它才是"改完还没部署"时该模拟的对象；
源不存在才退回游戏目录那份。想指定别的文件：`match_sim.py <dict路径>`。
报告第一行会打印实际读的文件，避免"源/部署产物"同名不同版本把人绕进去。
"""
import os
import sys

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
REPO = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private"
SRC_DICT = os.path.join(REPO, r"translate\translate_zh.txt")
GAME_DICT = os.path.join(GAME, r"T7Patch\translate_zh.txt")
DICT = sys.argv[1] if len(sys.argv) > 1 else (SRC_DICT if os.path.exists(SRC_DICT) else GAME_DICT)
OUT = os.path.join(REPO, r"tools\match_sim.txt")

K_MAX_WILDCARDS = 8
K_MIN_FRAGMENT_KEY = 3   # 与 C++ 的 kMinFragmentKey 对齐


def trim_trailing(b):
    return b.rstrip(b" \t\r\n")


def parse_dict(path):
    exact, patterns, fragments, too_long = {}, [], [], 0
    for raw in open(path, "rb").read().split(b"\n"):
        if len(raw) > 1024:
            too_long += 1
            continue
        p = raw.lstrip(b" \t")
        if not p or p[:1] in (b"#", b";"):
            continue
        if b"=" not in p:
            continue
        k, v = p.split(b"=", 1)
        k, v = trim_trailing(k), trim_trailing(v)
        if not k or not v:
            continue
        k = k.lower()
        if k.startswith(b"~"):
            k = k[1:].lstrip(b" \t")
            if len(k) >= K_MIN_FRAGMENT_KEY:
                fragments.append((k, v))
            continue
        if b"*" in k:
            parts = k.split(b"*")
            if len(parts) - 1 > K_MAX_WILDCARDS:
                continue
            patterns.append((parts, v))
        else:
            exact[k] = v
    patterns.sort(key=lambda x: len(x[0]))     # stable: narrow first
    fragments.sort(key=lambda x: -len(x[0]))   # stable: longest first
    return exact, patterns, fragments, too_long


def match_template(parts, key):
    n = len(parts)
    if n < 2:
        return None
    head = parts[0]
    if not key.startswith(head):
        return None
    pos, caps = len(head), []
    for i in range(1, n - 1):
        at = key.find(parts[i], pos)
        if at < 0:
            return None
        caps.append((pos, at))
        pos = at + len(parts[i])
    tail = parts[-1]
    if not key.endswith(tail) or len(key) - len(tail) < pos:
        return None
    caps.append((pos, len(key) - len(tail)))
    if len(caps) != n - 1:
        return None
    return caps


def render2(value, original, caps, exact, fragments):
    """复刻 C++ RenderTemplate，含 2026-09-19 新增的「捕获段再过一次查表」。

    捕获段先按 `LookupCaptureLocked` 的语义查一遍（**只走精确 + 片段，不走模板** ——
    模板里再进模板就是递归），命中就写译文，否则原样抄。这样
    `... settings profile: Rogue Run: Black Ops 3` 里的 `black ops 3` 片段也能生效。
    """
    res = bytearray()
    nxt = 0
    for ch in value:
        if ch == 0x2A:
            if nxt < len(caps):
                a, b = caps[nxt]
                cap = original[a:b]
                if 0 < len(cap) < 1024:
                    low = cap.lower()   # bytes.lower() 只动 A-Z，与 C++ LowerInPlace 同口径
                    sub = exact.get(low)
                    if sub is not None:
                        res += sub
                    else:
                        comp = compose_fragments(cap, low, fragments)
                        res += comp if comp is not None else cap
                else:
                    res += cap
                nxt += 1
            continue
        res.append(ch)
    return bytes(res)


def compose_fragments(run, lower, fragments):
    """复刻 C++ ComposeFragments：单遍左到右，最长的片段先试，命中即跳过那一段。

    'run' 与 'lower' 必须字节对齐（lower 只改 A-Z），未命中的字节从 run 原样抄出来，
    所以替换点周围的原始大小写会被保留。
    """
    if not fragments:
        return None
    out, at, n, matched = bytearray(), 0, len(lower), False
    while at < n:
        hit = None
        for k, v in fragments:
            if lower.startswith(k, at):
                hit = (k, v)
                break
        if hit is None:
            out.append(run[at])
            at += 1
            continue
        out += hit[1]
        at += len(hit[0])
        matched = True
    return bytes(out) if matched else None


def translate_run(run, exact, patterns, fragments):
    key = run.lower()
    if key in exact:
        return exact[key]
    for parts, value in patterns:
        caps = match_template(parts, key)
        if caps is not None:
            return render2(value, run, caps, exact, fragments)
    return compose_fragments(run, key, fragments)


def runs_of(line):
    """复刻 NextRun：跳过控制字节，片段两端空格裁掉，全空格的跳过。"""
    out, i, n = [], 0, len(line)
    while i < n:
        while i < n and line[i] < 0x20:
            i += 1
        if i >= n:
            break
        j = i
        while j < n and line[j] >= 0x20:
            j += 1
        a, b = i, j
        while a < b and line[a] == 0x20:
            a += 1
        while b > a and line[b - 1] == 0x20:
            b -= 1
        if b > a:
            out.append((line[a:b], a, b))
        i = j
    return out


def probes(exact, patterns, fragments):
    """可选：把 ref/match_probes.txt 里逐行的串翻译一遍并打印（验具体条目时用）。

    这是给"我加了一条，它到底命中吗"这种问题用的最小验证口：不用开游戏，
    也不用在 dump 里大海捞针。文件不存在就跳过。
    """
    path = os.path.join(os.path.dirname(OUT), "match_probes.txt")
    if not os.path.exists(path):
        return []
    o = ["", "=== ref/match_probes.txt 逐条命验 ==="]
    for raw in open(path, "rb").read().split(b"\n"):
        probe = raw.rstrip(b"\r")
        if not probe or probe.lstrip()[:1] == b"#":
            continue
        r = translate_run(probe, exact, patterns, fragments)
        if r is None:
            o.append("  MISS   %s" % probe.decode("ascii", "replace")[:90])
        else:
            o.append("  OK     %s\n         -> %s"
                     % (probe.decode("ascii", "replace")[:90], r.decode("utf-8", "replace")[:90]))
    return o


def main():
    exact, patterns, fragments, too_long = parse_dict(DICT)
    lines, seen = [], set()
    for raw in open(DUMP, "rb").read().split(b"\n"):
        b = raw.rstrip(b"\r")
        if not b:
            continue
        # 采集器写的是「片段」，但旧 dump 里混着整串（带控制字节）——两种都照 NextRun 处理
        for run, _, _ in runs_of(b):
            if run in seen:
                continue
            seen.add(run)
            lines.append(run)

    full, partial, miss = [], [], []
    miss_runs = {}
    for line in lines:
        rs = runs_of(line)
        if not rs:
            continue
        hit = trans = 0
        texts = []
        for run, _, _ in rs:
            r = translate_run(run, exact, patterns, fragments)
            if r is None:
                texts.append(run.decode("ascii", "replace"))
            else:
                hit += 1
                texts.append(r.decode("utf-8", "replace"))
            trans += 1
        if hit == 0:
            miss.append(line)
            for t in texts:
                miss_runs[t] = miss_runs.get(t, 0) + 1
        elif hit == trans:
            full.append(" / ".join(texts))
        else:
            partial.append((line.decode("ascii", "replace"), " / ".join(texts)))

    o = []
    o.append("模拟词库：%s" % DICT)
    o.append("词库：%d 条精确 + %d 条模板 + %d 条可组合片段（超长被跳过的行 %d）"
             % (len(exact), len(patterns), len(fragments), too_long))
    o.append("采集去重片段 %d 条（按新规则切分）" % len(lines))
    o.append("  · 完全命中（整条都出中文）: %d" % len(full))
    o.append("  · 部分命中（片段级，部分仍英文）: %d" % len(partial))
    o.append("  · 完全未命中: %d" % len(miss))
    o.append("")
    o.append("=== 部分命中样本（前 25）：原文 → 结果 ===")
    for a, b in partial[:25]:
        o.append("  %s\n      -> %s" % (a[:90], b[:110]))
    o.append("")
    o.append("=== 仍未命中的片段，按出现次数排序（前 40）：应只剩专有名词/数字/图标 ===")
    for t, c in sorted(miss_runs.items(), key=lambda x: -x[1])[:40]:
        o.append("  %3d  %s" % (c, t[:100]))
    o.append("")
    o.append("=== 模板实际生效的样本（前 20）：")
    used = 0
    for line in lines:
        rs = runs_of(line)
        if len(rs) != 1:
            continue
        run = rs[0][0]
        if run.lower() in exact:
            continue
        r = translate_run(run, exact, patterns, fragments)
        if r is not None:
            o.append("  %-46s -> %s" % (run.decode("ascii", "replace")[:46], r.decode("utf-8", "replace")[:70]))
            used += 1
            if used >= 20:
                break

    # 只有"精确和模板都落空、靠片段才出中文"的串才算片段的真实收益 —— 否则会把
    # 本来就能整串命中的条目算进来，看着像收益其实是噪声。
    o.append("")
    o.append("=== 可组合片段生效样本（精确/模板都落空，靠片段才出中文；前 25）===")
    shown = 0
    for run in lines:
        key = run.lower()
        if key in exact:
            continue
        if any(match_template(parts, key) is not None for parts, _ in patterns):
            continue
        r = compose_fragments(run, key, fragments)
        if r is not None:
            o.append("  %-52s -> %s"
                     % (run.decode("ascii", "replace")[:52], r.decode("utf-8", "replace")[:70]))
            shown += 1
            if shown >= 25:
                break
    if shown == 0:
        o.append("  (无：当前采集里没有出现需要组合的串)")

    o += probes(exact, patterns, fragments)

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(o))
    print("written", OUT)


main()
