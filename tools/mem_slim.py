# -*- coding: utf-8 -*-
"""把 MEMORY.md 里两段长文原样搬进 REF_notes.md，正文留精简版 + 指路。

搬（逐字，不重写）：
  1. `## 链式 D3D11 后端 + DXVK…` 整节
  2. `## 不兼容版本 → 玩家可见提示…` 整节
  3. `## 已知未修` 里四条长 bullet（方框 / 改英文 / mod 字体机制 / 字体救援）
写回：MEMORY.md（保留其余全部内容，断言行数守恒）
"""
import io
import os

MEM_DIR = os.path.dirname(os.path.abspath(__file__))
REF_DIR = os.path.join(os.path.dirname(MEM_DIR), "memory")
MEM = os.path.join(REF_DIR, "MEMORY.md")
REF = os.path.join(REF_DIR, "REF_notes.md")

src = io.open(MEM, encoding="utf-8").read()
assert src.count("\n") > 100, "MEMORY.md 读进来不对"
lines = src.split("\n")
assert os.path.exists(REF), "REF_notes.md 不存在：%s" % REF
ref_before = io.open(REF, encoding="utf-8").read()


def find(text):
    for i, l in enumerate(lines):
        if l.strip() == text:
            return i
    raise AssertionError("找不到标题: %r" % text)


def section_end(start):
    """从 start（标题行）到下一个 '## ' 之前。"""
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            return j
    return len(lines)


moved = []


def cut_section(title):
    s = find(title)
    e = section_end(s)
    body = lines[s:e]
    moved.append("\n".join(body))
    return s, e


STUB_DXVK = """## 链式 D3D11 后端 + DXVK → 细节见 REF_notes.md
- 游戏目录只能有一个 `d3d11.dll`（= 我们）⇒ 真后端改叫 `d3d11_backend.dll`（DXVK），`ResolveRealD3D11()` 逐个导出
  **先问后端、回退 System32**；**没有后端文件时行为与改动前完全一致**（可回滚，不用改 `thunks.asm`）。
- 门禁 = 只认「游戏目录里有翻译层 `dxgi.dll`」**且按内容识别**（扫前 2 MB 找 `DXVK`）；**语义 = 重启生效**
  （游戏静态导入 `dxgi.dll`，两文件必须同进同退）。实测 DXVK 3.1.1：`backend in use (4 exports), System32 fills 47`。
- **DXVK 日志静音（§62）**：`DXVK_LOG_LEVEL` 在 **DXVK 模块 Loader 期**就被 Logger 构造锁死（我们怎么设都晚），
  **`DXVK_LOG_PATH=none` 才是真正生效那个**（惰性读，首次写日志时）⇒ `DllMain` 里两个都设；玩家自己设过任一
  变量就完全不插手。⚠️ `dxvk.logLevel` **不是** conf 键（级别只能环境变量）。A/B 实证 = `ref/dxvk_logpath_ab.py`。
- conf 位置由 DXVK 定 ⇒ 代理在 `LoadLibraryW(后端)` **之前**设 `DXVK_CONFIG_FILE` 指到 `T7Patch\\dxvk\\dxvk.conf`
  （不覆盖用户已设；我们的 conf 不存在时不设；必须绝对路径）。工具 = `ref/dxvk_chain.py`（status/enable/disable/import）。
  ⚠️ 用了它之后**别点 PatchOpsIII 的 DXVK Install/Uninstall**（按文件名覆盖 = 把我们挤掉）。
- 发布包**不带** DXVK（内置下载，双源，许可 zlib ⇒ 分发要自附 `DXVK-LICENSE.txt`）。
  **待办**：overlay 的 DXVK 开关打磨 / 打包脚本（PE 位数校验）+ 两个 README / **T7Patch 自己的 LICENSE（仓库里还没有）**。
"""

STUB_WARN = """## 不兼容版本 → 玩家可见提示 → 细节见 REF_notes.md
- 两条拒绝启动路径（代理的 `!bo3::supported_build()`、`RunPatching()` 里 `arxan_bypass::install()` 失败）
  都调 `t7patch_warn_startup_failure(reason)`。
- ⚠️ **硬约束：提示必须跑在独立线程**（`RunPatching()` 还有第二个调用者 = 导出函数 `zbr_run_gamemode_lui`，
  那条路径在游戏线程里，模态框会卡住游戏）。其它：每进程最多一次（`exchange`）、只在主模块弹、双语同框、日志带指纹。
"""

STUB_FONT = """- **界面中文方框 / 字体救援（§29–§35 定稿，别再重新论证；全文见 REF_notes.md）**：真凶 = **地图自带自定义字体
  只含拉丁字形**（判据 = 拉丁正常 + 汉字方框；其它地图没自带字体 ⇒ 汉化照常正常）。**补丁无解**（能换字符串、
  换不了字形）⇒ 玩这类图只能切英文（语言门会自动关汉化，正好避免负贡献）。
  ⚠️ **"兼容模式"开关不要新增 —— 面板里的「模组汉化」关掉就是它**。
  "在这张图里改回英文"/"自动检测字体"都做不到（字体与串在压缩的 `.ff` 里、磁盘看不见；词库单向、无中→英）。
"""

# --- 1) 两整节 ---
s, e = cut_section("## 链式 D3D11 后端 + DXVK（2026-09-16 落地并实测通过）")
lines[s:e] = STUB_DXVK.rstrip("\n").split("\n")

s, e = cut_section("## 不兼容版本 → 玩家可见提示（2026-09-16 落地）")
lines[s:e] = STUB_WARN.rstrip("\n").split("\n")

# --- 2) 已知未修里的四条长 bullet ---
BULLETS = [
    "- **界面中文方框（§29→§35 定稿）——别再重新论证**：",
    "- **\"在这张图里改回英文\"做不到（§34/§35）**：",
    "- **官方 mod 管线的字体/文本机制（§32，推翻旧结论）**：",
    "- **字体救援结论（§33）**：",
]
for head in BULLETS:
    i = next((k for k, l in enumerate(lines) if l.startswith(head)), None)
    assert i is not None, "找不到 bullet: %r" % head
    j = i + 1
    while j < len(lines) and lines[j].startswith("- ") is False and lines[j].strip() != "":
        # bullet 的续行（缩进），以及它内部的空行/子项
        if lines[j].startswith("## "):
            break
        j += 1
    # 把紧随其后的空行也并进来
    while j < len(lines) and lines[j].strip() == "":
        j += 1
    moved.append("\n".join(lines[i:j]))
    lines[i:j] = [] if head != BULLETS[0] else STUB_FONT.rstrip("\n").split("\n")

new_mem = "\n".join(lines)
assert len(new_mem) < len(src), "没变小？"

# --- 3) 追加到 REF_notes.md ---
hdr = ("\n\n---\n\n# 【2026-09-16 从 MEMORY.md 移出】原始长文（逐字保留，未重写）\n\n"
       "MEMORY.md 超出注入上限被截断，故把下面这些**不常查但必须留存**的长文搬到这里。\n"
       "需要细节时按标题来翻；MEMORY.md 里各自留了精简版 + 指路。\n")
io.open(REF, "w", encoding="utf-8").write(ref_before.rstrip("\n") + hdr + "\n" + "\n\n".join(moved) + "\n")

io.open(MEM, "w", encoding="utf-8").write(new_mem)

print("MEMORY.md: %d -> %d 字节 (-%d%%)" %
      (len(src.encode("utf-8")), len(new_mem.encode("utf-8")),
       100 - len(new_mem.encode("utf-8")) * 100 // max(1, len(src.encode("utf-8")))))
print("REF_notes.md: %d -> %d 字节" %
      (len(ref_before.encode("utf-8")),
       len(io.open(REF, encoding="utf-8").read().encode("utf-8"))))
print("搬走 %d 段，共 %d 字节" % (len(moved), sum(len(m.encode("utf-8")) for m in moved)))
