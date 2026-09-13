# T7Patch（d3d11.dll 代理版）

[English](README.md) | 中文

基于 [Scroptss/T7Patch-src](https://github.com/Scroptss/T7Patch-src) 的 fork。
T7Patch 是《使命召唤：黑色行动3》（BO3）的社区安全/反崩溃补丁；
本 fork 在上游能力之外，增加了 **无需注入器** 的安装方式：
把一个 `d3d11.dll` 丢进游戏目录即可完成安装。

## 与上游的差异

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

## 安装

1. 从 [Releases](../../releases) 页下载 `d3d11.dll`（或自行构建）
2. 关闭游戏，把 `d3d11.dll` 复制到游戏目录（与 `BlackOps3.exe` 同层）
3. 启动游戏，右上角出现 `Patch 3.06` 即安装成功；游戏目录会自动生成 `T7Patch\` 文件夹
4. **卸载**：删除该 `d3d11.dll` 即可，游戏本体未被修改

## 配置

编辑 `T7Patch\t7patch.conf`（保存后约 1 秒内热生效，无需重启游戏）：

| 键 | 说明 |
|---|---|
| `playername=` | 留空 = 使用 Steam 昵称；填值 = 覆盖游戏内昵称 |
| `isfriendsonly=` | `1` = 仅好友可加入/互动（推荐） |
| `networkpassword=` | 房间密码，配合仅好友使用 |
