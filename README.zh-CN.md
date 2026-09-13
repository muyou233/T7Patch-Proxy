# T7Patch（d3d11.dll 代理版）

[English](README.md) | 中文

基于 [Scroptss/T7Patch-src](https://github.com/Scroptss/T7Patch-src) 的 fork。
T7Patch 是《使命召唤：黑色行动3》（BO3）的社区安全/反崩溃补丁；
本 fork 在上游能力之外，增加了 **无需注入器** 的安装方式：
把一个 `d3d11.dll` 丢进游戏目录即可完成安装。

## 补丁功能

- **联机防护**：连接包白名单过滤（只放行合法包），私有房间密码与消息前缀校验
- **仅好友模式**：非好友无法邀请你、拉你进房、与你互动
- **防远程崩溃**：针对各类畸形包与越界访问的防护（消息类型、模型/脚本索引、字符串替换、内存拷贝边界等十余处）
- **缩小攻击面**：关闭创意工坊 UGC 订阅、禁用游戏内浏览器打开
- **昵称覆盖**：通过配置文件覆盖游戏内昵称，留空则使用 Steam 昵称
- **性能相关调整**：缓存 Steam DLC/所有权查询结果，缓解 Steam 反复扫描 DLC 产生的卡顿；提升进程调度优先级；
  拦截游戏加载老旧的着色器编译器，改用系统自带的编译器

## 与上游的差异

- **d3d11.dll 代理安装（injectorless）**
  - `BlackOps3.exe` 静态导入 `d3d11.dll`（仅导入 `D3D11CreateDevice`），本 fork 借此实现 DLL 劫持代理
- **数据目录集中**：配置与日志统一放在游戏目录的 `T7Patch\` 子文件夹
  （`t7patch.conf`、`t7patch_proxy.log`、`t7patch_block.log`、`crashes.log`）
- **线程安全修复**
  - `friends_set`（好友集合）与 `dlcContent`（DLC 缓存）原本为无锁共享状态，
    多线程并发下可能误判好友或崩溃；现已加互斥锁，Steam 调用保持在锁外
  - `hkqmemcpy`：`size < 0` 分支不再写源缓冲区（源可能是只读内存）
- 保留上游全部功能：连接包过滤、私有房间前缀、防非好友邀请、Steam 昵称覆盖等

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

## 致谢

- 原始项目：[shiversoftdev/t7patch](https://github.com/shiversoftdev/t7patch)
- 源码上游：[Scroptss/T7Patch-src](https://github.com/Scroptss/T7Patch-src)
