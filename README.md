# T7Patch（d3d11.dll 代理版）/ T7Patch (d3d11.dll Proxy Edition)

基于 [Scroptss/T7Patch-src](https://github.com/Scroptss/T7Patch-src) 的 fork。
T7Patch 是《使命召唤：黑色行动3》（BO3）的社区安全/反崩溃补丁；
本 fork 在上游能力之外，增加了 **无需注入器** 的安装方式：
把一个 `d3d11.dll` 丢进游戏目录即可完成安装。

A fork of [Scroptss/T7Patch-src](https://github.com/Scroptss/T7Patch-src).
T7Patch is a community security / anti-crash patch for Call of Duty: Black Ops III.
On top of upstream, this fork adds an **injector-free** install path:
drop a single `d3d11.dll` into the game folder and you are done.

---

## 中文

### 与上游的差异

- **d3d11.dll 代理安装（injectorless）**
  - `BlackOps3.exe` 静态导入 `d3d11.dll`（仅导入 `D3D11CreateDevice`），本 fork 借此实现 DLL 劫持代理
  - `proxy/`：51 个导出全部经汇编转发桩（`mov rax,[slot]; jmp rax`）转发给真正的 `System32\d3d11.dll`，按原始序号对齐
  - 拦截 `D3D11CreateDevice` / `D3D11CreateDeviceAndSwapChain`，在渲染器初始化时机由独立线程执行补丁
    （先等 dvar 表发布，再等 1500ms 缓冲——该缓冲经验证是必要的，勿删）
- **数据目录集中**：配置与日志统一放在游戏目录的 `T7Patch\` 子文件夹
  （`t7patch.conf`、`t7patch_proxy.log`、`crashes.log`）
- **线程安全修复**
  - `friends_set`（好友集合）与 `dlcContent`（DLC 缓存）原本为无锁共享状态，
    多线程并发下可能误判好友或崩溃；现已加互斥锁，Steam 调用保持在锁外
  - `hkqmemcpy`：`size < 0` 分支不再写源缓冲区（源可能是只读内存）
- **游戏内版本串**简化为 `Patch 3.06`（`framework.h` 的 `ZBR_VERSION_FULL`）
- 保留上游全部功能：连接包过滤、私有房间前缀、防非好友邀请、Steam 昵称覆盖（conf 留空则使用 Steam 昵称）等

### 安装

1. 构建（见下文），得到 `x64\Release\d3d11.dll`
2. 关闭游戏，把 `d3d11.dll` 复制到游戏目录（与 `BlackOps3.exe` 同层）
3. 启动游戏，右上角出现 `Patch 3.06` 即安装成功；游戏目录会自动生成 `T7Patch\` 文件夹
4. **卸载**：删除该 `d3d11.dll` 即可，游戏本体未被修改

### 配置

编辑 `T7Patch\t7patch.conf`（保存后约 1 秒内热生效，无需重启游戏）：

| 键 | 说明 |
|---|---|
| `playername=` | 留空 = 使用 Steam 昵称；填值 = 覆盖游戏内昵称 |
| `isfriendsonly=` | `1` = 仅好友可加入/互动（推荐） |
| `networkpassword=` | 房间密码，配合仅好友使用 |

### 构建

- Visual Studio 2022+（含 Desktop C++ 与 MASM 组件）
- 打开 `T7Patch.slnx`，选 **Release + x64**（Win32 平台不可用），仅"生成"
- 产物：`x64\Release\d3d11.dll`（代理入口）与 `T7Patch.dll`（注入器路线备用，载荷相同）
- 更改代码后需手动把新的 `d3d11.dll` 覆盖到游戏目录（先关游戏）

### 注意

- 补丁内含大量针对当前游戏构建的硬编码偏移；**游戏更新后可能静默失效**（版本指纹不匹配时补丁不会应用）
- 联机建议始终开启 `networkpassword` + `isfriendsonly=1`
- 本项目仅供学习研究，与 Activision / Treyarch 无关

### 致谢

- 上游与原作者：[Scroptss/T7Patch-src](https://github.com/Scroptss/T7Patch-src)（serious / Emma / ssno 及贡献者）
- 社区贡献：SashaPrawn（编译期 SPOOF 清理、incentive 过滤）、Luisete2105 等

---

## English

### What this fork changes (vs upstream)

- **Injector-free install via d3d11.dll proxy**
  - `BlackOps3.exe` statically imports `d3d11.dll` (only `D3D11CreateDevice`); this fork turns that into a DLL-hijack proxy
  - `proxy/`: all 51 exports are forwarded to the real `System32\d3d11.dll` through assembly thunks
    (`mov rax,[slot]; jmp rax`), ordinals aligned with the genuine DLL
  - `D3D11CreateDevice` / `D3D11CreateDeviceAndSwapChain` are intercepted; patching runs on a dedicated
    worker thread at renderer-init time (waits for the dvar table, then a 1500 ms settle delay —
    verified necessary, do not remove)
- **Centralized data folder**: config and logs live in a `T7Patch\` subfolder of the game directory
  (`t7patch.conf`, `t7patch_proxy.log`, `crashes.log`)
- **Thread-safety fixes**
  - `friends_set` and the `dlcContent` cache were unsynchronized shared state; concurrent access could
    misjudge friends or crash. Both are now mutex-guarded, with Steam calls kept outside the lock
  - `hkqmemcpy`: the `size < 0` branch no longer writes to the source buffer (which may be read-only)
- **In-game version string** trimmed to `Patch 3.06` (`ZBR_VERSION_FULL` in `framework.h`)
- All upstream features retained: connection-packet filtering, private-room prefix, non-friend invite
  blocking, Steam-name override (leave the conf value empty to keep your Steam name), etc.

### Install

1. Build (see below) to get `x64\Release\d3d11.dll`
2. Close the game, copy `d3d11.dll` next to `BlackOps3.exe`
3. Launch the game — `Patch 3.06` in the top-right corner means success; a `T7Patch\` folder is created automatically
4. **Uninstall**: delete that `d3d11.dll`; the game files are never modified

### Configuration

Edit `T7Patch\t7patch.conf` (hot-reloads within ~1 second of saving):

| Key | Meaning |
|---|---|
| `playername=` | empty = Steam persona name; set = override in-game name |
| `isfriendsonly=` | `1` = friends only (recommended) |
| `networkpassword=` | room password, use together with friends-only |

### Build

- Visual Studio 2022+ with Desktop C++ and the MASM component
- Open `T7Patch.slnx`, select **Release + x64** (Win32 is not supported), build only
- Output: `x64\Release\d3d11.dll` (proxy entry) and `T7Patch.dll` (same payload for the injector route)
- After code changes, copy the fresh `d3d11.dll` into the game folder manually (close the game first)

### Notes

- The patch relies on hard-coded offsets for a specific game build; it may **silently stop applying
  after a game update** (build fingerprint mismatch)
- Always play with `networkpassword` + `isfriendsonly=1`
- For educational purposes only. Not affiliated with Activision / Treyarch.

### Credits

- Upstream & original author: [Scroptss/T7Patch-src](https://github.com/Scroptss/T7Patch-src) (serious / Emma / ssno and contributors)
- Community contributions: SashaPrawn (compile-time SPOOF cleanup, incentive filter), Luisete2105, and others
