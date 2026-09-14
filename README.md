# T7Patch (d3d11.dll Proxy Edition)

English | [中文](README.zh-CN.md)

A fork of [Scroptss/T7Patch-src](https://github.com/Scroptss/T7Patch-src).
T7Patch is a community security / anti-crash patch for Call of Duty: Black Ops III.
On top of upstream, this fork adds an **injector-free** install path:
drop a single `d3d11.dll` into the game folder and you are done.

## What the patch does

- **Online protection**: blocks malicious packets, shielding you from attacks and griefing;
  non-friends cannot invite you, pull you into lobbies, or interact with you
- **Crash protection**: guards against game crashes caused by malformed packets
- **Reduced attack surface**: closes risky entry points (workshop subscription, in-game browser)
- **Performance**: removes the stuttering caused by DLC scanning and the legacy shader compiler
- **In-game control panel**: press `Insert` on the main menu for a visual menu - toggle every
  feature above, EN/中文 switch, no config editing needed

## What this fork changes (vs upstream)

- **Injector-free install via d3d11.dll proxy**
  - `BlackOps3.exe` statically imports `d3d11.dll` (only `D3D11CreateDevice`); this fork turns that into a DLL-hijack proxy
- **Centralized data folder**: config and logs live in a `T7Patch\` subfolder of the game directory
  (`t7patch.conf`, `t7patch.log`, `crashes.log`)
- **Thread-safety fixes**
  - `friends_set` and the `dlcContent` cache were unsynchronized shared state; concurrent access could
    misjudge friends or crash. Both are now mutex-guarded, with Steam calls kept outside the lock
  - `hkqmemcpy`: the `size < 0` branch no longer writes to the source buffer (which may be read-only)
- **In-game ImGui overlay**: hooks Present, the window proc and the DXGI factory
  chain; card-style UI; hot-plugs the 46 block, applies config instantly,
  EN/中文 switch, custom hotkey
- All upstream features retained: connection-packet filtering, private-room prefix, non-friend invite
  blocking, Steam-name override, etc.

## Install

1. Get `d3d11.dll` from the [Releases](../../releases) page (or build it yourself)
2. Close the game, copy `d3d11.dll` next to `BlackOps3.exe`
3. Launch the game — `Patch 3.07` in the top-right corner means success; a `T7Patch\` folder is created automatically
4. **Uninstall**: delete that `d3d11.dll`; the game files are never modified

## In-game menu

Press `Insert` (changeable in the menu) once you are on the main menu:

![In-game menu](docs/menu_overlay.png)

- **Settings**: player name (prefilled with the game's current name) and room password -
  each row commits with its own `Save` button
- **Toggles**: friends-only (applies on click), block the legacy shader compiler
  (hot plug/unplug, no restart), auto-open the menu on the main menu
- **Config**: English/Chinese switch and a custom hotkey (click the button, then press the
  new key; `ESC` cancels)
- Game input is ignored while the menu is open, zero interference when it is closed
- The hotkey only arms after the game is connected and the main menu is up

## Configuration

Edit `T7Patch\t7patch.conf` (hot-reloads within ~1 second of saving):

| Key | Meaning |
|---|---|
| `playername=` | empty = the game's current name; set = override in-game name |
| `isfriendsonly=` | `1` = friends only (recommended) |
| `networkpassword=` | room password, use together with friends-only |
| `block_d3dcompiler46=` | `1` = block the legacy shader compiler (default on; also a menu toggle) |
| `menu_key=` | virtual-key code that opens the menu (default `45` = Insert) |
| `menu_auto_open=` | `1` = open the menu automatically at the main menu (default `0`) |
| `menu_lang=` | `1` = Chinese (default), `0` = English |

## Credits

- Original project: [shiversoftdev/t7patch](https://github.com/shiversoftdev/t7patch)
- Source upstream: [Scroptss/T7Patch-src](https://github.com/Scroptss/T7Patch-src)
