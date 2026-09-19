"""项目文本编码 / 行尾 / BOM 审计 + 归一（默认只读，--fix 才动手）。

## 为什么要有它（2026-09-18 的两次"幺蛾子"都出在编码）
  ① 用 GBK 读 UTF-8 的 t7patch.conf：多字节序列吞掉行尾 `\\r`，让"注释一行、键一行"看起来连成一行，
     于是误判"配置只有 4 个键"（实际 11 个）。
  ② 源文件里的中文（conf 注释）走编译器的"源字符集 → 执行字符集"转换，口径不一致时字面量会被改写。

## 统一口径（本脚本的判据）
  硬约束（HARD，必须 0 问题）：项目源码 / 工程文件 / 词库 / 文档 / 我的工具脚本 / skill / memory
        ⇒ **UTF-8 无 BOM + LF 行尾**（不得混合、不得无换行）
  软约束（SOFT，只报告）：`.codebuddy/**` 下的运行产物与日志 —— PowerShell 5.1 的 `Out-File -Encoding utf8`
        天生写 BOM，属工具习惯，不算项目违规（但仍会被 --fix 归一，读起来一致）。
  另外单独报告：vcxproj 的字符集开关、`.gitattributes`、`git core.autocrlf`。

用法：
    python encoding_audit.py          # 只读审计，落 ref/encoding_audit.txt
    python encoding_audit.py --fix    # 归一（去 BOM / 转 UTF-8 / 行尾统一 LF），只写真正变化的文件
"""
import os
import subprocess
import sys
from collections import Counter, defaultdict

REPO = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private"
OUT = os.path.join(REPO, r"tools\encoding_audit.txt")

SKIP_DIRS = {".git", "x64", ".vs", "T7Patch", "generated-images", "__pycache__", "node_modules"}
TEXT_EXT = {
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".inl", ".asm", ".inc",
    ".def", ".vcxproj", ".filters", ".slnx", ".sln", ".props", ".txt", ".md",
    ".py", ".json", ".toml", ".yml", ".yaml", ".conf", ".cfg", ".ini",
    ".cmd", ".bat", ".ps1", ".sh", ".gitignore", ".gitattributes",
}

ROOT_TEXT = {"readme.md", "readme.en.md", ".gitignore", ".gitattributes",
             "cppproperties.json", "t7patch.vcxproj", "t7patch.vcxproj.filters",
             "t7patch.slnx"}


def is_hard(rel):
    """项目文件（硬约束）还是 .codebuddy 下的工具产物（软约束）。"""
    low = rel.lower()
    if low.startswith("\\src\\") or low.startswith("\\proxy\\") or low.startswith("\\translate\\"):
        return True
    if os.path.basename(low) in ROOT_TEXT and low.count("\\") <= 1:
        return True
    if low.startswith("\\.codebuddy\\ref\\") and low.endswith(".py"):
        return True
    if low.startswith("\\.codebuddy\\skills\\") or low.startswith("\\.codebuddy\\memory\\"):
        return True
    return False


def read_text(data):
    """按 BOM/编码解出文本；返回 (text, encoding_label, bom)。"""
    if data[:3] == b"\xef\xbb\xbf":
        return data[3:].decode("utf-8", "replace"), "utf-8", "UTF-8 BOM"
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        enc = "utf-16-le" if data[:2] == b"\xff\xfe" else "utf-16-be"
        return data[2:].decode(enc, "replace"), "utf-8", "UTF-16"
    try:
        return data.decode("utf-8"), "utf-8", ""
    except UnicodeDecodeError:
        pass
    for enc in ("gbk", "latin-1"):
        try:
            return data.decode(enc), enc, ""
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", "replace"), "latin-1", ""


def eol_styles(text):
    crlf = text.count("\r\n")
    cr = text.count("\r") - crlf
    lf = text.count("\n") - crlf
    s = []
    if crlf:
        s.append("CRLF")
    if lf:
        s.append("LF")
    if cr:
        s.append("CR")
    return s


def collect():
    rows = []
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            ext = os.path.splitext(name)[1].lower()
            if ext not in TEXT_EXT and name.lower() not in (".gitignore", ".gitattributes"):
                continue
            p = os.path.join(root, name)
            rel = p[len(REPO):]
            data = open(p, "rb").read()
            text, enc, bom = read_text(data)
            styles = eol_styles(text)
            problems = []
            if enc != "utf-8":
                problems.append("非 UTF-8(%s)" % enc)
            if bom:
                problems.append(bom)
            if len(styles) > 1:
                problems.append("混合行尾(%s)" % "+".join(styles))
            if not styles:
                problems.append("无换行符")
            rows.append(dict(rel=rel, path=p, text=text, enc=enc, bom=bom,
                             styles=styles, hard=is_hard(rel), problems=problems))
    return rows


def fix(rows):
    changed = []
    for r in rows:
        if not r["problems"]:
            continue
        new = r["text"].replace("\r\n", "\n").replace("\r", "\n")
        data = new.encode("utf-8")
        if data == open(r["path"], "rb").read():
            continue
        open(r["path"], "wb").write(data)
        changed.append((r["rel"], ",".join(r["problems"])))
    return changed


def main():
    rows = collect()
    changed = fix(rows) if "--fix" in sys.argv else []
    if changed:
        rows = collect()          # 修完重新采一遍，报告反映最终状态

    by_ext = defaultdict(Counter)
    hard_bad, soft_bad = [], []
    for r in rows:
        ext = os.path.splitext(r["rel"])[1].lower() or r["rel"]
        eol = "MIXED" if len(r["styles"]) > 1 else ("".join(r["styles"]) or "-")
        by_ext[ext][(r["enc"], r["bom"] or "-", eol,
                     "有中文" if any(b >= 0x80 for b in r["text"].encode("utf-8")) else "纯ASCII")] += 1
        if r["problems"]:
            (hard_bad if r["hard"] else soft_bad).append((r["rel"], r["problems"]))

    L = []
    L.append("# 项目文本编码 / 行尾 / BOM 审计（硬约束 = 源码/工程/词库/文档/工具；软约束 = .codebuddy 运行产物）")
    L.append("# 仓库：%s" % REPO)
    L.append("# 统一口径：硬约束文件 = UTF-8 无 BOM + LF")
    L.append("# 文本文件 %d 个；硬约束违规 %d 个；软约束（工具产物）%d 个" % (len(rows), len(hard_bad), len(soft_bad)))
    if changed:
        L.append("# 本次 --fix 改写了 %d 个文件" % len(changed))
        for rel, prob in sorted(changed)[:200]:
            L.append("#   fixed %-56s %s" % (rel, prob))
    L.append("")
    L.append("## 一、硬约束违规（必须修到 0）")
    L += ["- %-58s %s" % (rel, ",".join(p)) for rel, p in sorted(hard_bad)] or ["（无）"]
    L.append("")
    L.append("## 二、软约束（.codebuddy 运行产物 / 日志，只报告）")
    L.append("- 共 %d 个（多为 PowerShell `Out-File -Encoding utf8` 写的 BOM 日志）" % len(soft_bad))
    for rel, p in sorted(soft_bad)[:15]:
        L.append("     %-52s %s" % (rel, ",".join(p)))
    if len(soft_bad) > 15:
        L.append("     （另有 %d 个）" % (len(soft_bad) - 15))
    L.append("")
    L.append("## 三、按扩展名的口径分布（看'统一'到什么程度）")
    for ext in sorted(by_ext):
        L.append("### %s" % ext)
        for k, n in by_ext[ext].most_common():
            L.append("    %-44s %d 个" % (" ".join(str(x) for x in k), n))
    L.append("")
    L.append("## 四、编译器与 git 的口径")
    vcx = os.path.join(REPO, "T7Patch.vcxproj")
    if os.path.isfile(vcx):
        t = open(vcx, "rb").read().decode("utf-8", "replace")
        L.append("- vcxproj `/utf-8`：%s" % ("有（源字符集与执行字符集都是 UTF-8，中文字面量口径明确）" if "/utf-8" in t else "**没有**"))
    ga = os.path.join(REPO, ".gitattributes")
    L.append("- .gitattributes：%s" % ("存在" if os.path.isfile(ga) else "**不存在**"))
    if os.path.isfile(ga):
        L.append(open(ga, encoding="utf-8", errors="replace").read().rstrip())
    try:
        o = subprocess.run(["git", "config", "--get", "core.autocrlf"], cwd=REPO,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        L.append("- git core.autocrlf = %s" % (o.stdout.decode().strip() or "(未设置)"))
        o = subprocess.run(["git", "ls-files", "--eol"], cwd=REPO,
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        counter = Counter()
        for line in o.stdout.decode("utf-8", "replace").splitlines():
            counter[line.split("\t")[0]] += 1
        for k, v in counter.most_common():
            L.append("- git ls-files --eol 的 %s：%d 个" % (k, v))
    except OSError as e:
        L.append("- git 查询失败：%s" % e)

    open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("written %s" % OUT)
    print("  文本文件 %d；硬约束违规 %d；软约束 %d；本次修正 %d"
          % (len(rows), len(hard_bad), len(soft_bad), len(changed)))


if __name__ == "__main__":
    main()
