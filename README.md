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
- **Performance**: removes the stuttering caused by DLC scanning
- **Legacy shader compiler opt-out**: renames the engine's `d3dcompiler_46.dll` to
  `d3dcompiler_46.dll.bak` at launch, so the engine cannot use it (renamed back when the
  toggle is switched off)
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
  - the config object (player name / room password / toggles) was read and written from three threads
    with no synchronization at all; it is now guarded by a single mutex, with engine calls kept
    outside the lock and the string getters switched to caller-supplied buffers
  - saving from the in-game menu used to write the file and stop there - the config watcher could not
    see the process's own write, so the new value never reached the engine and renaming yourself
    required a restart. Saves now hand the push to the background thread explicitly (~1 s, usually
    ~100 ms)
- **In-game ImGui overlay**: hooks Present, the window proc and the DXGI factory
  chain; card-style UI; hot-plugs the 46 block, applies config instantly,
  EN/中文 switch, custom hotkey
- All upstream features retained: connection-packet filtering, private-room prefix, non-friend invite
  blocking, Steam-name override, etc.

## Install

1. Get `d3d11.dll` from the [Releases](../../releases) page (or build it yourself)
2. Close the game, copy `d3d11.dll` next to `BlackOps3.exe`
3. Launch the game — `Patch 3.08` in the top-right corner means success; a `T7Patch\` folder is created automatically
4. **Uninstall**: delete that `d3d11.dll`. The patch touches exactly one game file besides: while the
   legacy-compiler switch is on, `d3dcompiler_46.dll` is renamed to `d3dcompiler_46.dll.bak` — switch
   that toggle off (or rename the file back, or run Steam's *Verify integrity*) to restore it

## In-game menu

Press `Insert` (changeable in the menu) once you are on the main menu:

![In-game menu](docs/menu_overlay.png)

- **Settings**: player name (prefilled with the game's current name) and room password -
  each row commits with its own `Save` button
- **Toggles**: friends-only (applies on click), opt out of the legacy shader compiler (renames the
  file; takes effect on the next launch), auto-open the menu on the main menu
- **Config**: English/Chinese switch and a custom hotkey (click the button, then press the
  new key; `ESC` cancels)
- Game input is ignored while the menu is open, zero interference when it is closed
- The hotkey only arms once the main menu is actually up; on the title screen and on the
  connecting screen it does nothing

## Configuration

Edit `T7Patch\t7patch.conf` (hot-reloads within ~1 second of saving):

| Key | Meaning |
|---|---|
| `playername=` | empty = the game's current name; set = override in-game name |
| `isfriendsonly=` | `1` = friends only (recommended) |
| `networkpassword=` | room password, use together with friends-only |
| `block_d3dcompiler46=` | `1` = rename `d3dcompiler_46.dll` to `.dll.bak` at launch (default on; also a menu toggle) |
| `menu_key=` | virtual-key code that opens the menu (default `45` = Insert) |
| `menu_auto_open=` | `1` = open the menu automatically once the main menu is up, ~1.5 s after it appears (default `0`) |
| `menu_lang=` | `1` = Chinese (default), `0` = English |

## Credits

- Original project: [shiversoftdev/t7patch](https://github.com/shiversoftdev/t7patch)
- Source upstream: [Scroptss/T7Patch-src](https://github.com/Scroptss/T7Patch-src)
