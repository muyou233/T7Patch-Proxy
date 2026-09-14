# T7Patch（d3d11.dll 代理版）

[English](README.md) | 中文

基于 [Scroptss/T7Patch-src](https://github.com/Scroptss/T7Patch-src) 的 fork。
T7Patch 是《使命召唤：黑色行动3》（BO3）的社区安全/反崩溃补丁；
本 fork 在上游能力之外，增加了 **无需注入器** 的安装方式：
把一个 `d3d11.dll` 丢进游戏目录即可完成安装。

## 补丁功能

- **联机防护**：拦截恶意数据包，抵御他人对你的攻击与干扰；非好友无法邀请你、拉你进房或与你互动
- **防崩溃**：抵御各类畸形数据包引发的游戏崩溃
- **缩小攻击面**：关闭创意工坊订阅与游戏内浏览器等高风险入口
- **性能优化**：消除 DLC 扫描与旧着色器编译器引起的卡顿
- **游戏内控制面板**：进入主菜单后按 `Insert` 呼出菜单，可视化开关全部功能，支持中英切换

## 与上游的差异

- **d3d11.dll 代理安装（injectorless）**
  - `BlackOps3.exe` 静态导入 `d3d11.dll`（仅导入 `D3D11CreateDevice`），本 fork 借此实现 DLL 劫持代理
- **数据目录集中**：配置与日志统一放在游戏目录的 `T7Patch\` 子文件夹
  （`t7patch.conf`、`t7patch_proxy.log`、`t7patch_block.log`、`crashes.log`）
- **线程安全修复**
  - `friends_set`（好友集合）与 `dlcContent`（DLC 缓存）原本为无锁共享状态，
    多线程并发下可能误判好友或崩溃；现已加互斥锁，Steam 调用保持在锁外
  - `hkqmemcpy`：`size < 0` 分支不再写源缓冲区（源可能是只读内存）
- **游戏内 ImGui 覆盖层**：Present / WndProc / DXGI 工厂三处 hook，
  卡片式界面；运行时装卸 46 拦截、配置即时生效、中英切换、快捷键自定义
- 保留上游全部功能：连接包过滤、私有房间前缀、防非好友邀请、Steam 昵称覆盖等

## 安装

1. 从 [Releases](../../releases) 页下载 `d3d11.dll`（或自行构建）
2. 关闭游戏，把 `d3d11.dll` 复制到游戏目录（与 `BlackOps3.exe` 同层）
3. 启动游戏，右上角出现 `Patch 3.07` 即安装成功；游戏目录会自动生成 `T7Patch\` 文件夹
4. **卸载**：删除该 `d3d11.dll` 即可，游戏本体未被修改

## 游戏内菜单

进入主菜单后按 `Insert`（可在菜单里改）呼出控制面板：

- **设置**：玩家昵称（默认显示游戏当前名字）、房间密码 —— 每行独立 `Save` 提交
- **开关**：屏蔽旧着色器编译器（运行时装卸，无需重启）、仅好友可加入（点击即生效）
- **配置**：中英文切换、呼出快捷键自定义（点按钮后按新键，`ESC` 取消）
- 菜单打开时游戏输入被屏蔽，不会误操作角色；关闭时对游戏零干扰
- 快捷键在**连接完成、进入主菜单后**才生效，避免启动阶段误触

## 配置

编辑 `T7Patch\t7patch.conf`（保存后约 1 秒内热生效，无需重启游戏）：

| 键 | 说明 |
|---|---|
| `playername=` | 留空 = 使用游戏当前昵称；填值 = 覆盖游戏内昵称 |
| `isfriendsonly=` | `1` = 仅好友可加入/互动（推荐） |
| `networkpassword=` | 房间密码，配合仅好友使用 |
| `block_d3dcompiler46=` | `1` = 拦截旧着色器编译器（默认开启，菜单里也可切换） |
| `menu_key=` | 呼出菜单的虚拟键码（默认 `45` = Insert） |
| `menu_auto_open=` | `1` = 进入主菜单后自动打开菜单（默认 `0`） |
| `menu_lang=` | `1` = 中文（默认），`0` = English |

## 致谢

- 原始项目：[shiversoftdev/t7patch](https://github.com/shiversoftdev/t7patch)
- 源码上游：[Scroptss/T7Patch-src](https://github.com/Scroptss/T7Patch-src)
