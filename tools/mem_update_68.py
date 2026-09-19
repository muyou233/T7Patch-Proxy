# -*- coding: utf-8 -*-
"""按 §68 的采集结果更新 MEMORY.md（精确替换 + 全量断言，避免手滑静默失败）。"""
import io, os

REF = os.path.dirname(os.path.abspath(__file__))
MEM = os.path.join(os.path.dirname(REF), "memory", "MEMORY.md")

EDITS = []

# 1) 探针状态：未采集 -> 已采集
EDITS.append((
    r"""  回滚点 `.bak` = `6AD5F2B0…`。**探针结果 `T7Patch\ui_callers.txt` 尚未采集**（等用户上游戏）。""",
    r"""  回滚点 `.bak` = `6AD5F2B0…`。**探针已采集**（157 条）→ 裁决 `ref/probe_verdict.md`。""",
))

# 2) 本机状态：繁体/translate=0 已过期
EDITS.append((
    r"""- **⚠️ 本机 conf 现状（别忘）**：游戏语言 = `traditionalchinese`，而 conf 里 `translate=0` 是上一轮英文启动被
  语言门写下的 —— 繁体**不触发门**、不会自动写回 1 ⇒ 下次进游戏汉化是**关的**，要菜单手动点开一次。""",
    r"""- **本机现状（2026-09-16 20:50 实测，旧记的"繁体 + translate=0"作废）**：`localization.txt` =
  **`simplifiedchinese`**，conf `translate=1` / `dump_ui_strings=1` / `menu_lang=1`；
  本局 init 载入 **970 entries + 32 templates = 1002** ✓ 与 `2026-09-16g` 一致。""",
))

# 3) 玩家名撞车：整段升级为裁决版
OLD3 = r"""- **玩家名撞车（进行中，§66）**：裸单 token 键 267/1002 理论上会被玩家名撞上；**"删死键"已实测否掉**
  （251/267 真在翻 UI 文本，16 条含 `settings`/`play`/`kill` ⇒ dump 覆盖不全而非死键）。
  ⚠️ roster 方案（只读固定 RVA 12 槽，零风险）**盖不到社交界面的 Steam 好友名**（用户 09-16 指出）——
  `ui_dump.txt` 741–782 行那片就是好友名，且**确实走我们管线**（dump 是 `translate::Collect()` 写的，必经 Lookup）；
  实测 17 个好友名**今天 0 命中**，但 dump 里 1191 个"像名字的裸 token"有 **378 个就是词库键**
  （`Back`/`New`/`Yes`/`No`/`Select`/`Menu`/`STORE`…）⇒ 好友叫这类词就会被翻（脚本 `ref/social_names.py`）。
  **当前在试「调用点指纹」**：探针已部署（`translate::CollectCaller` + `Hooks.cpp` 的
  `CallerRva` / `ProbeElementString` / `RecordCallerSite` → `ui_callers.txt`；`_ReturnAddress()` **必须在 hook
  体内求值**；预算**按调用点** 40 条 / 512 点 / 共 12000 行，否则稀有调用点被挤掉）。分析器 = `ref/callers_report.py`
  （好友名已作锚点；名字落点查**全量**大小写不敏感索引 `lower_sites`，别查截断到 12 条的展示样本；
  另有「名字共识调用点」表）。判读：名字扎堆少数 RVA ⇒ 可按调用点跳过（界面级排除，主菜单/社交全覆盖）；
  与普通 UI 同通道 ⇒ 退回 roster。顺带同采 `element` 试读结果。
  **采集动作**：`dump_ui_strings=1` 已开 ⇒ 走【大厅 + **社交界面** + 一局】→ 退出 → 跑分析器。"""

NEW3 = r"""- **玩家名撞车（§66→§68，裁决已出，等用户选档）**：裸单 token 键 267/1002；"删死键"实测否掉（251/267
  真在翻 UI 文本）。**调用点指纹已采集**（`ui_callers.txt` 157 条；分析器 `ref/callers_report.py`，裁决
  `ref/probe_verdict.md`）：三个调用区（每区 model+seh 一对，相距 0x21）——
  ⭐**R2 = `026951AF`/`026951D0`（feb `0269586F`/`02695890`）整片是用户数据**：17 条全是玩家名/群组名、
  词库命中 **0** ⇒ 可硬跳过，就是**社交列表的行**（8 好友 + 2 群组 + 7 最近玩家，与用户截图逐行对上）；
  R1 `026953AE`/`026953CF`、R3 `01F28303`/`01F28468` 是**混合通道**（真 UI 文本 + 名字），同一批名字三个
  界面都渲染 ⇒ 只跳 R2 救不了主菜单/队伍面板。
  **`element` 线索否掉**（157/157 读不出字符串 ⇒ 空指针或结构体指针）。
  推荐两层：① R2 硬跳过（零副作用）② 「用户文本集」＝R2 见过的串在其它通道也跳过（代价：好友名恰等于
  词库键时该词别处也不翻，如好友叫 `Menu` ⇒ 主菜单 `MENU` 保持英文 —— 字节层无法两全，已告知用户）。
  探针实现要点（复用价值）：`_ReturnAddress()` 必须在 hook 体内求值；样本预算**按调用点** 40 条 / 512 点 /
  共 12000 行，否则稀有调用点被挤掉。
- **`正在Infection上进行团队死斗` 不是漏翻**（用户已指示维持默认，别追）：dump 2964 行**含汉字 0 行**
  ＋ dump 里躺着**未解析指令**（`$(lobbyFriends.onlineCount) playing Black Ops 3`）⇒ **绑定值在我们之后才注入**
  ⇒ 绑定里的地图名结构上够不着（该句模板本身已是中文）；词库 `infection=感染区` 本身有效（地图列表里
  那种独立片段照翻）。"""

EDITS.append((OLD3, NEW3))

# 4) 未提交清单范围
EDITS.append((
    r"""- **未提交**：`1be733f` 之上积了 §58–§66 —— """,
    r"""- **未提交**：`1be733f` 之上积了 §58–§68 —— """,
))

s = io.open(MEM, encoding="utf-8").read()
before = len(s.encode("utf-8"))

for i, (old, new) in enumerate(EDITS, 1):
    assert old in s, "第 %d 条：原文找不到" % i
    assert s.count(old) == 1, "第 %d 条：原文出现 %d 次" % (i, s.count(old))
    assert new not in s, "第 %d 条：新文已存在（重复执行？）" % i
    s = s.replace(old, new)

io.open(MEM, "w", encoding="utf-8").write(s)
after = len(s.encode("utf-8"))

print("MEMORY.md: %d -> %d 字节（%+d）" % (before, after, after - before))
for i, (old, new) in enumerate(EDITS, 1):
    print("  条 %d ok: %s" % (i, new.splitlines()[0][:64]))
