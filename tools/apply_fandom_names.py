"""按用户 2026-09-18 的新规则（Fandom 中文 > 灰机）把 9 处冲突名切到 Fandom 那版。

安全设计：
  · **只改"值"（第一个 `=` 右边）与片段的值**，绝不碰键 —— 键是引擎送来的英文原文，改了就再也匹配不上；
  · **不改注释** —— 那些注释是 2026-09-17/18 按旧规则写下的历史依据（「灰机亦作…Fandom 作…」），
    改掉它们会变成自相矛盾的句子；新决定另写一段带日期的说明（由人工加）；
  · 每处替换都带**期望条数断言**（普查得到的值侧条数），对不上就中止、不写盘；
  · `道具 → 强力奖励` 只作用在**键里含 powerup / power up** 的行（「道具」太泛，全局替换会误伤一大片）。
"""
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DICT = os.path.join(REPO, "translate", "translate_zh.txt")

# (旧名, 新名, 期望的"值侧"条数)  —— 条数来自 2026-09-18 的普查
REPL = [
    ("血浴之城", "血狱之城", 1),
    ("亡灵剧院", "死亡剧院", 2),
    ("阿森松", "上升", 1),
    ("快手可乐", "快手汽水", 2),
    ("快速复苏", "快速救援", 1),
    ("三枪烈酒", "三枪饮料", 1),
    ("厚血蛋酒", "厚血蛋奶酒", 2),
    ("技能可乐", "特长饮料", 1),
    ("神秘箱", "神秘宝箱", 4),
]
POWER_OLD, POWER_NEW = "道具", "强力奖励"


def main():
    with open(DICT, "r", encoding="utf-8", newline="\n") as fp:
        lines = fp.read().split("\n")

    counts = {old: 0 for old, _, _ in REPL}
    power_hits = 0
    out = []

    for ln in lines:
        s = ln.strip()
        if s.startswith("#") or "=" not in ln:
            out.append(ln)                      # 注释与无等号行原样保留
            continue
        key, value = ln.split("=", 1)
        for old, new, _ in REPL:
            if old in key:
                raise SystemExit("拒绝执行：键侧出现中文名 %r（键必须保持英文原文）" % old)
            if old in value:
                counts[old] += value.count(old)
                value = value.replace(old, new)
        kl = key.lower()
        if "powerup" in kl or "power up" in kl:
            if POWER_OLD in value:
                power_hits += value.count(POWER_OLD)
                value = value.replace(POWER_OLD, POWER_NEW)
        out.append(key + "=" + value)

    for old, new, want in REPL:
        assert counts[old] == want, "「%s」→「%s」期望 %d 条，实际 %d 条 ⇒ 中止" % (old, new, want, counts[old])
    assert power_hits > 0, "powerup 相关行里没找到「道具」⇒ 中止"

    with open(DICT, "w", encoding="utf-8", newline="\n") as fp:
        fp.write("\n".join(out))

    print("替换完成（行数 %d -> %d）：" % (len(lines), len(out)))
    for old, new, want in REPL:
        print("  %s -> %s   %d 处" % (old, new, counts[old]))
    print("  %s -> %s   %d 处（仅键含 powerup / power up 的行）" % (POWER_OLD, POWER_NEW, power_hits))


if __name__ == "__main__":
    main()
