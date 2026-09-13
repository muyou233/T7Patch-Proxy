# T7Patch (d3d11.dll Proxy Edition)

English | [中文](README.zh-CN.md)

A fork of [Scroptss/T7Patch-src](https://github.com/Scroptss/T7Patch-src).
T7Patch is a community security / anti-crash patch for Call of Duty: Black Ops III.
On top of upstream, this fork adds an **injector-free** install path:
drop a single `d3d11.dll` into the game folder and you are done.

## What this fork changes (vs upstream)

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

## Install

1. Build (see below) to get `x64\Release\d3d11.dll`
2. Close the game, copy `d3d11.dll` next to `BlackOps3.exe`
3. Launch the game — `Patch 3.06` in the top-right corner means success; a `T7Patch\` folder is created automatically
4. **Uninstall**: delete that `d3d11.dll`; the game files are never modified

## Configuration

Edit `T7Patch\t7patch.conf` (hot-reloads within ~1 second of saving):

| Key | Meaning |
|---|---|
| `playername=` | empty = Steam persona name; set = override in-game name |
| `isfriendsonly=` | `1` = friends only (recommended) |
| `networkpassword=` | room password, use together with friends-only |

## Build

- Visual Studio 2022+ with Desktop C++ and the MASM component
- Open `T7Patch.slnx`, select **Release + x64** (Win32 is not supported), build only
- Output: `x64\Release\d3d11.dll` (proxy entry) and `T7Patch.dll` (same payload for the injector route)
- After code changes, copy the fresh `d3d11.dll` into the game folder manually (close the game first)

## Notes

- The patch relies on hard-coded offsets for a specific game build; it may **silently stop applying
  after a game update** (build fingerprint mismatch)
- Always play with `networkpassword` + `isfriendsonly=1`
- For educational purposes only. Not affiliated with Activision / Treyarch.

## Credits

- Upstream & original author: [Scroptss/T7Patch-src](https://github.com/Scroptss/T7Patch-src) (serious / Emma / ssno and contributors)
- Community contributions: SashaPrawn (compile-time SPOOF cleanup, incentive filter), Luisete2105, and others
