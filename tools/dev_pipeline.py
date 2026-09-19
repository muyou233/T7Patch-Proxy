"""开发工具流水线（一个开关：`t7patch.conf` 里的 `dump_ui_strings`）。

## 为什么合到一个开关
用户要求（2026-09-18）："把这两功能开关组合起来，不用放进UI，就在配置文件我自己开关，这属于开发工具。"
两件功能原本各管一段、互不知情：
    ① 采集   —— DLL 侧：`dump_ui_strings=1` ⇒ 游戏把每个 distinct 英文 UI run 追加进 `T7Patch\\ui_dump.txt`
    ② 发现   —— 脚本侧：`dict_triage.py`（正向分桶）+ `fragment_candidates.py`（反向找该升格的片段）
现在 ② **读同一个 conf 键**来做准入判定：键开 = 两段一起可用；键关 = 本脚本直接拒绝运行。
⇒ 一个开关，两段生效；不进 UI；不碰 DLL。

## 用法
    python dev_pipeline.py                 # 读游戏目录里的 t7patch.conf
    python dev_pipeline.py --conf <路径>   # 换一份 conf（自测 / 离线用）
    python dev_pipeline.py --quiet         # 只打印汇总

开关关着时**故意不跑**（exit 2）并说明怎么开 —— 免得拿着关闭状态下的旧快照当结论。
只读：不改词库、不改采集文件、不改 conf。
"""
import argparse
import os
import re
import subprocess
import sys
import time

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
CONF = os.path.join(GAME, r"T7Patch\t7patch.conf")
DUMP = os.path.join(GAME, r"T7Patch\ui_dump.txt")
REF = os.path.dirname(os.path.abspath(__file__))

SWITCH = "dev_tools"                # 2026-09-18 起的正式键名（DLL 写出的就是它）
SWITCH_LEGACY = "dump_ui_strings"   # 旧键名，DLL 仍读取（下次重写配置时自动改名）
STEPS = [("dict_triage.py", 2), ("fragment_candidates.py", 0)]


def read_conf(path):
    """conf 的真实编码。2026-09-18 实测：游戏写出来的 conf 是 **UTF-8、无 BOM**（不是 GBK）。
    顺序：带 BOM 的 UTF-8 → 无 BOM 的 UTF-8 → GBK → latin-1 兜底，并把实际用的编码报出来。"""
    raw = open(path, "rb").read()
    if raw[:3] == b"\xef\xbb\xbf":
        return raw.decode("utf-8-sig"), "utf-8 (BOM)"
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", "replace"), "latin-1"


def conf_values(text):
    """取 `key=value`。注意本 conf 的注释与键**同在一行**（注释在前），所以不能按行首匹配。"""
    vals = {}
    for m in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\s#]*)", text):
        vals[m.group(1).lower()] = m.group(2).strip()
    return vals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conf", default=CONF)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    if not os.path.isfile(a.conf):
        print("找不到 conf：%s" % a.conf)
        return 2
    text, enc = read_conf(a.conf)
    vals = conf_values(text)
    used, state = SWITCH, vals.get(SWITCH)
    if state is None and SWITCH_LEGACY in vals:
        used, state = SWITCH_LEGACY, vals[SWITCH_LEGACY]

    print("=" * 72)
    print("开发工具流水线（开关：%s，读自 %s，编码 %s）" % (used, a.conf, enc))
    print("=" * 72)
    if state is None:
        print("  %s 未出现在 conf 里 ⇒ 按默认值 0（关）处理。" % SWITCH)
    elif used != SWITCH:
        print("  %s=%s（旧键名，仍然有效；DLL 下次重写配置时会改成 %s）" % (used, state, SWITCH))
    else:
        print("  %s=%s" % (SWITCH, state))
    if str(state) != "1":
        print("")
        print("开关关着 ⇒ 不跑。要开就在 %s 里写：" % os.path.basename(a.conf))
        print("    %s=1" % SWITCH)
        print("（这键同时控制 DLL 侧采集与本次流水线；改了之后进游戏才会产生新采集。）")
        return 2

    if os.path.isfile(DUMP):
        st = os.stat(DUMP)
        age = (time.time() - st.st_mtime) / 3600.0
        print("  采集文件：%s" % DUMP)
        print("            %d 字节，最后写入 %s（%.1f 小时前）"
              % (st.st_size, time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)), age))
        if age > 24:
            print("            ⚠️ 超过一天没更新：结论只代表这份快照，别当「当前游戏里还有什么」。")
    else:
        print("  ⚠️ 采集文件还不存在：%s" % DUMP)
        print("     开关虽然开着，但还没进过游戏 ⇒ 先玩一次（进菜单/对局/僵尸）再跑本脚本。")
        return 3

    print("")
    for script, _ in STEPS:
        path = os.path.join(REF, script)
        print("--- 运行 %s ---" % script)
        r = subprocess.run([sys.executable, path], cwd=REF,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = r.stdout.decode("utf-8", "replace").strip()
        if not a.quiet or r.returncode != 0:
            print(out)
        if r.returncode != 0:
            print("!! %s 退出码 %d" % (script, r.returncode))
            return r.returncode

    # ------------------------------------------------------------------ 汇总
    def read_txt(name):
        p = os.path.join(REF, name)
        return open(p, encoding="utf-8").read() if os.path.isfile(p) else ""

    tri, cand = read_txt("dict_triage.txt"), read_txt("fragment_candidates.txt")

    def count(head, text=tri):
        m = re.search(re.escape(head) + r"\s+(\d+)", text)
        return int(m.group(1)) if m else -1

    print("")
    print("=" * 72)
    print("汇总（细节看 ref\\dict_triage.txt 与 ref\\fragment_candidates.txt）")
    print("=" * 72)
    print("  要翻的界面文本（triage「界面文本候选」）：%d 条" % count("界面文本候选 <<< 工作清单"))
    print("  待人工过目（单 token）                ：%d 条" % count("待人工过目（单 token）"))
    promo = re.findall(r"^- `~([^`]+)`", cand, re.M)
    fresh = re.findall(r"^- `([^`~][^`]*)`\s+出现 \d+ 条", cand, re.M)
    print("  该升格的片段（A 段）                  ：%d 个%s"
          % (len(promo), ("  " + ", ".join("~" + p for p in promo[:8])) if promo else ""))
    print("  全新专名候选（B 段，需查权威名）      ：%d 个%s"
          % (len(fresh), ("  " + ", ".join(fresh[:6])) if fresh else ""))
    print("")
    print("下一步：A 段我确认后加 `~`；B 段拿英文原名去灰机 / Fandom 查中文，查不到就保留原文。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
