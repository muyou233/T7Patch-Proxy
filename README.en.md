# T7Patch (d3d11.dll Proxy Edition)

English | [中文](README.md)

Based on [T7Patch](https://github.com/Scroptss/T7Patch-src).
T7Patch is a community security / anti-crash patch for Call of Duty: Black Ops III.

## What the patch does

- **Online protection**: blocks malicious packets, shielding you from attacks and griefing;
  non-friends cannot invite you, pull you into lobbies, or interact with you
- **Crash protection**: guards against game crashes caused by malformed packets
- **Reduced attack surface**: closes risky entry points (workshop subscription, in-game browser)
- **Performance**: removes the stuttering caused by DLC scanning
- **UI localisation (mod translation)**: replaces the game's English UI text with a Chinese dictionary
  - **One-click dictionary update**: the menu's *Update dictionary* button fetches the latest
    version; live about 2 seconds later, no restart
  - **Per-scene exceptions**: Multiplayer and Zombies can each be left in English
    (default: **Multiplayer untranslated, Zombies translated**). The block applies once a session
    is established (rooms and lobbies included); the main menu and Campaign are never affected
  - On a game that is not running in Chinese the feature switches itself off at start-up (a
    non-Chinese install has no Chinese glyphs, so the text would show up as boxes)
- **Custom map language compatibility**: fills in the language files a Steam Workshop map is
  missing, so a map that shipped only some languages no longer fails with `Could not find zone`
  for everyone else. Handled automatically at start-up, no manual step; it only adds what is absent
  (never modifies the map's own files) and re-checks after a map update
- **Optional Vulkan rendering backend (DXVK)**: fetched from the menu's *Graphics* page (each file
  is verified after download), then turned on with the switch beside it and applied on the next
  launch; a Vulkan-capable GPU driver is required
- **In-game control panel**: press `Insert` on the main menu for a visual menu - toggle every
  feature, EN/中文 switch, no config editing needed

## Install

1. Get `d3d11.dll` from the [Releases](../../releases) page (or build it yourself)
2. Close the game, copy `d3d11.dll` next to `BlackOps3.exe`
3. Launch the game — `Patch 3.09` in the top-right corner means success; a `T7Patch\` folder is created automatically
4. **Uninstall**: delete that `d3d11.dll`; if `dxgi.dll` and `d3d11_backend.dll` are present (DXVK),
   delete them too - skip if absent. While the legacy shader compiler switch is on, `d3dcompiler_46.dll`
   is renamed to `.bak` - rename it back (off by default)

## In-game menu

Press `Insert` (changeable in the menu) once you are on the main menu:

![In-game menu](docs/menu_overlay.png)

Three pages:

- **General**
  - **Settings**: player name (prefilled with the game's current name) and room password -
    each row commits with its own `Save` button
  - **Toggles**: friends-only (applies on click), opt out of the legacy shader compiler (renames the
    file; takes effect on the next launch), auto-open the menu on the main menu
  - **Config**: English/Chinese switch and a custom hotkey (click the button, then press the
    new key; `ESC` cancels)
- **Graphics**: the optional DXVK backend - fetch / enable, plus HUD elements, frame-rate cap
  and tearing control
- **More**: the **mod translation** switch with its *Update dictionary* button, and two indented
  sub-switches below it - **Turn off Multiplayer translation** (on by default) and
  **Turn off Zombies translation** (off by default). Both are greyed out until mod translation is on
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
| `block_d3dcompiler46=` | `1` = rename `d3dcompiler_46.dll` to `.dll.bak` at launch (default off; also a menu toggle) |
| `menu_key=` | virtual-key code that opens the menu (default `45` = Insert) |
| `menu_auto_open=` | `1` = open the menu automatically once the main menu is up, ~1.5 s after it appears (default `1`) |
| `menu_lang=` | `1` = Chinese (default), `0` = English |
| `translate=` | `1` = replace English UI text with the mod-translation dictionary (default off; also a menu toggle). On a game that is not running in Chinese the start-up check switches it off and writes this back to `0` |
| `skip_pvp=` | `1` = leave Multiplayer untranslated (default `1`). The main menu is unaffected; needs `translate=1` |
| `skip_zm=` | `1` = leave Zombies untranslated (default `0`). Campaign is never affected; needs `translate=1` |
| `dev_tools=` | `1` = **development-tools mode**: collect English UI text. Default off, deliberately not a menu entry. The old key name `dump_ui_strings` is still read and is renamed on the next config rewrite |

**Upgrading from an older version**: you do not need to edit the file. Any setting it
does not mention uses the default from the table above, and on start-up the patch
rewrites the file in the current format - it **only fills in the missing settings and
comments, and never changes a value you already have**.

## Credits

- Original project: [shiversoftdev/t7patch](https://github.com/shiversoftdev/t7patch)
- Source upstream: [Scroptss/T7Patch-src](https://github.com/Scroptss/T7Patch-src)
- DXVK: [doitsujin/dxvk](https://github.com/doitsujin/dxvk)
