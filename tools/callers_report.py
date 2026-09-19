"""分析 ui_callers.txt：把「哪条 UI 串来自哪个调用点」按调用点聚合。

背景（2026-09-16，线索二探针）：前端字符串的两条 hook 只有字符串本身，
唯一白送的上下文是调用者的返回地址 —— 游戏镜像内固定 RVA。这个脚本回答：

  1. 整个前端一共用到多少个调用点？（少 = 聚类有戏，多 = 无区分度）
  2. 每个调用点渲染的文本形态是什么？（界面词 vs 单 token 名字）
  3. 已知玩家名（conf 里自己的名字 + 之前 dump 里认出来的）落在哪些调用点？
  4. 和上一轮采集相比，**冒出了哪些新调用点** ⇒ 新界面（房间/局内）是不是独立通道。

判定「玩家名通道」的判据是**组合**，不是单条：
  · 样本词库命中率极低（≈0）
  · 样本几乎全是「无空格短 token」
  · 已知玩家名恰好落在它下面
  · 样本条数不大（专用通道，不是通用字符串处理器）

采集**分轮**（ui_callers.txt 是追加写，两轮混在一起就没法分界面了）：
  round1 = ui_callers_social_2051.txt（社交界面）
  round2 = ui_callers.txt（主菜单 / 房间 / 局内计分板）
换轮时必须**重启游戏**：探针预算按调用点 40 条（kCallerSamplesPerSite），
不重启就没有名额采新界面。

坐标：探针写的是镜像实际 RVA。offsets.h 里的地址常量是 February 映射，
September 更新把 0x1D29C20 之后的代码整体上移了 0x6C0，所以本脚本额外
换算一列 February RVA，好和 patch 自己的地址常量直接对照。

用法：
  python callers_report.py                         # 用默认路径
  python callers_report.py <callers.txt> [baseline.txt]
"""
import os
import sys
import collections

REF = os.path.dirname(os.path.abspath(__file__))
GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DEFAULT_CALLERS = os.path.join(GAME, r"T7Patch\ui_callers.txt")
DEFAULT_BASELINE = os.path.join(GAME, r"T7Patch\ui_callers_social_2051.txt")
DICT = os.path.join(GAME, r"T7Patch\translate_zh.txt")
OUT = os.path.join(REF, "callers_report.txt")

# 已知玩家名：自己的（conf 里 playername）+ dump 里人工认出来的。
# 用途是交叉验证 —— 它们扎堆的调用点就是候选的「玩家名通道」。
#
# ⚠️ 2026-09-16 补充：玩家名**不只在房间 roster**，社交界面还展示 Steam 好友
# （ui_dump.txt 741-782 行那一整片：FRIENDS / GROUPS / RECENT PLAYERS 下面的名字）。
# 这些名字不在 roster 的 12 槽里，所以 roster 方案救不了它们 —— 但也正因如此，
# 它们是「调用点聚类」最有价值的锚点：如果好友名和 roster 名落在**同一批 RVA**，
# 说明存在统一的玩家名通道，一次排除就全覆盖。
KNOWN_PLAYERS = [
    # 自己 + 对局里认出来的
    "muyou", "HanamaruZura", "Gimp", "cidshook",
    # 社交界面（Steam 好友 / RECENT PLAYERS）实测样本
    "Aquila13", "AyerRex", "Bruce", "Crowea", "happlyboy", "yasoft1",
    "JoeBidenshairyle", "Smirnoff[StPb]", "Oncent", "Ouicho", "#Mr.Nilsson#",
    "Peek Me Pookie",
    # 群组名（社交界面同时渲染，形状和玩家名一样）
    "Chinese Home", "Hardcore Group",
    # round2 局内（2026-09-16 21:09 欧服团队死斗，TAB 计分板实测 12 人）
    "LCN94z", "jackrabbit", "Harry_Scrodum", "maxitictac", "SuperSaiyanRos#",
    "cerrolazamarco", "Chromer", "nizko993", "kstzzz", "Silverlol",
]
# 注意故意**不**收录 `BB` / `J` / 单字母：太短，与界面缩写无从区分，当锚点会污染聚类。

SHIFT_START = 0x1D29C20          # 从这里开始，零售镜像比 February 映射低 0x6C0
SHIFT_END = 0x2EFF000
DELTA = 0x6C0

K_MAX_WILDCARDS = 8


def to_february(rva):
    """镜像实际 RVA -> offsets.h 用的 February RVA（反向 translate_rva）。"""
    lo, hi = SHIFT_START - DELTA, SHIFT_END - DELTA
    return rva + DELTA if lo <= rva < hi else rva


def trim_trailing(b):
    return b.rstrip(b" \t\r\n")


def parse_dict(path):
    exact, patterns = {}, []
    for raw in open(path, "rb").read().split(b"\n"):
        if len(raw) > 1024:
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


def translates(run, exact, patterns):
    key = run.lower()
    if key in exact:
        return True
    for parts in patterns:
        if match_template(parts, key):
            return True
    return False


def looks_like_name(t):
    """单 token、短、非纯数字 —— 玩家名的形态。界面词大多带空格或已入库。"""
    if b" " in t or len(t) < 2 or len(t) > 24:
        return False
    if t.isdigit():
        return False
    return any(0x41 <= c <= 0x5A or 0x61 <= c <= 0x7A for c in t)


def load_probe(path):
    """按文件行序返回 [(rva, kind, text)]，保留写入顺序（时间线要用）。"""
    rows = []
    if not os.path.exists(path):
        return rows
    for raw in open(path, "rb").read().split(b"\n"):
        line = raw.rstrip(b"\r")
        if not line or line[:1] == b"#":
            continue
        parts = line.split(b"\t", 3)
        if len(parts) < 4:
            continue
        try:
            rva = int(parts[0], 16)
        except ValueError:
            continue
        rows.append((rva, parts[1].decode("ascii", "replace"), parts[3]))
    return rows


def build_channels(sites, max_gap=0x800):
    """把 model/seh 成对的调用点归并成「通道」，供时间线折叠用。

    两条 hook 是一次渲染的两条路（model 路 + seh 路），它们的返回地址成对出现、
    距离在 0x21~0x165 之间；不同界面之间则隔得很远。所以按 RVA 排序后贪心配对
    （kind 必须不同、距离 <= max_gap）就能还原出"哪个界面在渲染"。
    返回 {rva: 通道代表 rva}。
    """
    rvas = sorted(set(r for r, _ in sites))
    kind_of = {}
    for r, k in sites:
        kind_of[r] = k
    ch, i = {}, 0
    while i < len(rvas):
        cur = rvas[i]
        nxt = rvas[i + 1] if i + 1 < len(rvas) else None
        if nxt is not None and kind_of[nxt] != kind_of[cur] and (nxt - cur) <= max_gap:
            ch[cur] = cur
            ch[nxt] = cur
            i += 2
        else:
            ch[cur] = cur
            i += 1
    return ch


def write_out(lines):
    open(OUT, "w", encoding="utf-8").write("\n".join(lines))
    print("written", OUT)


def main():
    args = [a for a in sys.argv[1:]]
    callers = args[0] if len(args) > 0 else DEFAULT_CALLERS
    baseline = args[1] if len(args) > 1 else DEFAULT_BASELINE

    o = []
    rows = load_probe(callers)
    if not rows:
        o.append("找不到或为空: %s" % callers)
        o.append("说明探针还没采集过这一轮（或 dump_ui_strings 没开）。")
        write_out(o)
        return

    exact, patterns = parse_dict(DICT)

    seen = set()
    per_site = collections.defaultdict(lambda: {"n": 0, "ui": 0, "name": 0, "texts": []})
    per_text_sites = collections.defaultdict(set)
    # 大小写不敏感的全量索引 —— 已知玩家名的落点必须查这张表，
    # 不能查 per_site[s]["texts"]（那是**截断到 20 条**的展示用样本，
    # 样本多的调用点会把名字挤出去 ⇒ 假「没出现」）。
    lower_sites = collections.defaultdict(set)
    kind_count = collections.Counter()
    total = 0

    for rva, kind, text in rows:
        key = (rva, kind, text)
        if key in seen:
            continue
        seen.add(key)

        site = (rva, kind)
        total += 1
        kind_count[kind] += 1
        per_text_sites[text].add(site)
        lower_sites[text.lower()].add(site)
        info = per_site[site]
        info["n"] += 1
        if translates(text, exact, patterns):
            info["ui"] += 1
        elif looks_like_name(text):
            info["name"] += 1
        if len(info["texts"]) < 20:
            info["texts"].append(text)

    o.append("文件: %s" % os.path.basename(callers))
    o.append("记录行 %d，去重后 %d 条 (rva,kind,text)" % (len(rows), total))
    o.append("调用点 %d 个   kind 分布: %s" % (len(per_site), dict(kind_count)))
    o.append("")

    # 判定标签 —— 必须在下面第一张表之前定义（那张表要引用它）。
    def label(info):
        if info["n"] and info["ui"] == 0 and info["name"] >= max(2, info["n"] * 0.6):
            return "PLAYER?"
        if info["ui"] == 0 and info["n"] <= 3:
            return "RARE"
        if info["ui"] >= info["n"] * 0.5:
            return "UI"
        return "MIXED"

    # ── 跨轮对照：新冒出来的调用点 = 新界面的独立通道 ──────────────────
    base_rows = load_probe(baseline)
    if base_rows:
        base_sites = set((r, k) for r, k, _ in base_rows)
        base_texts = collections.defaultdict(set)
        for r, k, t in base_rows:
            base_texts[(r, k)].add(t)

        fresh = [s for s in per_site if s not in base_sites]
        shared = [s for s in per_site if s in base_sites]

        o.append("=== 与上一轮对照（基线 %s，%d 行 / %d 个调用点）===" %
                 (os.path.basename(baseline), len(base_rows), len(base_sites)))
        o.append("  本轮 %d 个调用点：新增 %d 个，与基线共有 %d 个" %
                 (len(per_site), len(fresh), len(shared)))
        o.append("")
        if fresh:
            o.append("  ★ 新增调用点（上一轮没见过 ⇒ 这段界面的独立通道）:")
            for s in sorted(fresh, key=lambda s: -per_site[s]["n"]):
                info = per_site[s]
                o.append("    0x%08X (feb 0x%08X) kind=%-6s 样本=%d 入库=%d 像名=%d 判定=%s" %
                         (s[0], to_february(s[0]), s[1], info["n"], info["ui"],
                          info["name"], label(info)))
                for t in info["texts"][:12]:
                    o.append("        %s" % t.decode("ascii", "replace")[:90])
        else:
            o.append("  ⚠️ 没有任何新调用点 —— 本轮走过的界面全部复用基线里的通道")
        o.append("")
        if shared:
            o.append("  基线已有、本轮又出现的调用点（同一通道被多个界面复用）:")
            for s in sorted(shared, key=lambda s: -per_site[s]["n"]):
                info = per_site[s]
                new_texts = [t for t in info["texts"] if t not in base_texts[s]]
                o.append("    0x%08X (feb 0x%08X) kind=%-6s 样本=%d 判定=%s 本轮新文本 %d 条" %
                         (s[0], to_february(s[0]), s[1], info["n"], label(info),
                          len(new_texts)))
                for t in new_texts[:8]:
                    o.append("        + %s" % t.decode("ascii", "replace")[:90])
        o.append("")

    # ── 已知玩家名的落点 ─────────────────────────────────────────────
    o.append("=== 已知玩家名落在哪些调用点 ===")
    o.append("  （社交好友名 / 房间玩家名 / 局内计分板名都算，「同一批 RVA」= 有统一通道）")
    name_site_count = collections.Counter()
    missing = []
    for name in KNOWN_PLAYERS:
        hits = sorted(lower_sites.get(name.lower().encode("ascii", "replace"), ()))
        for s in hits:
            name_site_count[s] += 1
        o.append("  %-18s -> %s" % (
            name,
            ", ".join("0x%08X/%s[%s]" % (s[0], s[1], label(per_site[s]))
                      for s in hits) if hits else "（本轮样本里没出现）"))
        if not hits:
            missing.append(name)
    if missing:
        o.append("  ⚠️ 没被采到的名字 %d 个: %s" % (len(missing), ", ".join(missing)))
        o.append("     （要么那个界面没走一遍，要么名字太长被 kRunMax 截了）")
    o.append("")
    if name_site_count:
        o.append("=== 名字共识调用点（≥2 个不同名字落在一起 = 玩家名通道）===")
        for s, c in name_site_count.most_common():
            o.append("  0x%08X (feb 0x%08X) kind=%-4s  %2d 个名字  判定=%s  样本=%d" %
                     (s[0], to_february(s[0]), s[1], c, label(per_site[s]), per_site[s]["n"]))
    else:
        o.append("=== 没有任何已知名字出现在样本里 —— 社交界面/大厅没走到，或本局没采集 ===")
    o.append("")

    order = sorted(per_site.items(), key=lambda kv: (-per_site[kv[0]]["n"]))
    o.append("=== 调用点一览（按样本数降序）===")
    o.append("  %-10s %-10s %-6s %5s %5s %5s %-8s %6s" %
             ("rva(img)", "rva(feb)", "kind", "样本", "入库", "像名", "判定", "独有"))
    for site, info in order:
        rva, kind = site
        uniq = sum(1 for t in per_site[site]["texts"] if len(per_text_sites[t]) == 1)
        o.append("  0x%08X 0x%08X %-6s %5d %5d %5d %-8s %6d" %
                 (rva, to_february(rva), kind, info["n"], info["ui"], info["name"],
                  label(info), uniq))
    o.append("")

    # ── 时间线：先把成对的 model/seh 归并成「通道」，再折叠连续段 ────────
    ch = build_channels(list(per_site.keys()))
    pairs = collections.defaultdict(list)
    for r, c in ch.items():
        pairs[c].append(r)
    o.append("=== 采样时间线（按写入顺序，同一通道连续出现折叠成段）===")
    o.append("  通道归并: " + "; ".join(
        "0x%08X = %s" % (c, "+".join("0x%08X" % x for x in sorted(v)))
        for c, v in sorted(pairs.items())))
    o.append("  段  通道        条数  首条文本")
    segs = []
    for rva, kind, text in rows:
        c = ch.get(rva, rva)
        if segs and segs[-1][0] == c:
            segs[-1][1] += 1
        else:
            segs.append([c, 1, text])
    for i, (c, n, first) in enumerate(segs[:120]):
        o.append("  %3d  0x%08X  %4d  %s" %
                 (i + 1, c, n, first.decode("ascii", "replace")[:44]))
    if len(segs) > 120:
        o.append("  … 还有 %d 段（截断）" % (len(segs) - 120))
    o.append("  段数合计 %d（段多 = 界面来回切换；段少而长 = 稳定停在某个界面）" % len(segs))
    o.append("")

    o.append("=== 每个调用点的样本文本 ===")
    for site, info in order:
        rva, kind = site
        o.append("")
        o.append("[%s] 0x%08X (feb 0x%08X) kind=%s  样本=%d 入库=%d 像名=%d" %
                 (label(info), rva, to_february(rva), kind, info["n"], info["ui"], info["name"]))
        for t in info["texts"]:
            flag = "UI " if translates(t, exact, patterns) else ("NM?" if looks_like_name(t) else "   ")
            o.append("    %s %s" % (flag, t.decode("ascii", "replace")[:100]))

    write_out(o)


main()
