# -*- coding: utf-8 -*-
r"""Post-fix static self-check for the T7Patch code-review fixes.

1. Bracket balance after stripping comments + string/char literals.
2. Line-continuation-in-comment trap  (a "// ... \" ends the line and
   swallows the next one during translation phase 2).
3. Assert every fix actually landed, by grepping for its anchor text.
4. Assert the removed forms are really gone (negative tests on the CODE view,
   because the new comments deliberately quote the old buggy lines).
"""
import io, os, re, sys

_REPO = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private"
# Sources moved into src/ on 2026-09-15; fall back to the flat root layout.
ROOT = os.path.join(_REPO, "src") if os.path.isdir(os.path.join(_REPO, "src", "proxy")) else _REPO
out = []
fail = 0


def strip_code(src):
    """Remove // comments, /* */ comments and string/char literals."""
    res = []
    i, n = 0, len(src)
    mode = None  # None | 'line' | 'block' | 'str' | 'chr'
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ''
        if mode is None:
            if c == '/' and nxt == '/':
                mode = 'line'; res.append('  '); i += 2; continue
            if c == '/' and nxt == '*':
                mode = 'block'; res.append('  '); i += 2; continue
            if c == '"':
                mode = 'str'; res.append(' '); i += 1; continue
            if c == "'":
                mode = 'chr'; res.append(' '); i += 1; continue
            res.append(c); i += 1; continue
        if mode == 'line':
            if c == '\n':
                mode = None; res.append(c)
            else:
                res.append(' ')
            i += 1; continue
        if mode == 'block':
            if c == '*' and nxt == '/':
                mode = None; res.append('  '); i += 2; continue
            res.append('\n' if c == '\n' else ' '); i += 1; continue
        # str / chr
        if c == '\\':
            res.append('  '); i += 2; continue
        if (mode == 'str' and c == '"') or (mode == 'chr' and c == "'"):
            mode = None; res.append(' '); i += 1; continue
        res.append('\n' if c == '\n' else ' '); i += 1; continue
    return ''.join(res)


def check_file(rel, exts=('.cpp', '.h')):
    global fail
    p = os.path.join(ROOT, rel)
    raw = io.open(p, 'r', encoding='utf-8', newline='').read()
    code = strip_code(raw)
    oks = []
    bad = []

    # --- 1. bracket balance ------------------------------------------------
    pairs = {'}': '{', ')': '(', ']': '['}
    stack = []
    line = 1
    for ch in code:
        if ch == '\n':
            line += 1
        elif ch in '{([':
            stack.append((ch, line))
        elif ch in '})]':
            if not stack:
                bad.append("unmatched '%s' at line %d" % (ch, line)); break
            top, tl = stack.pop()
            if top != pairs[ch]:
                bad.append("mismatch: '%s' (line %d) closed by '%s' (line %d)"
                           % (top, tl, ch, line)); break
    if stack and not bad:
        bad.append("unclosed '%s' from line %d" % (stack[-1][0], stack[-1][1]))
    oks.append("bracket balance" if not bad else "")

    # --- 2. comment line-continuation trap ---------------------------------
    cont = []
    for i, ln in enumerate(raw.split('\n'), 1):
        if re.search(r'//.*\\[ \t]*$', ln):
            cont.append(i)

    # --- 3. no CR / no BOM sanity ------------------------------------------
    cr = raw.count('\r')

    out.append("== %s ==" % rel)
    out.append("   %s" % ("OK  " + oks[0] if not bad else "FAIL " + "; ".join(bad)))
    out.append("   comment-continuation lines: %s" % (cont if cont else "none"))
    out.append("   CR count: %d" % cr)
    if bad:
        fail += 1
    if cont:
        fail += 1
    return raw


for f in ("Protection.cpp", "Hooks.cpp", "dllmain.cpp", "overlay.cpp",
          "framework.h", "Protection.h", "Hooks.h", "t7patch_log.cpp",
          "translate.cpp", "translate.h",
          "dict_update.cpp", "dict_update.h",
          "dxvk_download.cpp", "dxvk_download.h",
          "proxy/Proxy.cpp", "proxy/d3d11.def"):
    check_file(f)

# ---------------------------------------------------------------------------
# 4. every fix must be physically present
# ---------------------------------------------------------------------------
src = {f: io.open(os.path.join(ROOT, f), 'r', encoding='utf-8', newline='').read()
       for f in ("Protection.cpp", "Hooks.cpp", "overlay.cpp",
                 "translate.cpp", "translate.h",
                 "dict_update.cpp", "dict_update.h",
                 "dxvk_download.cpp", "dxvk_download.h",
                 "proxy/d3d11.def", "t7patch_log.cpp", "framework.h",
                 # 2026-09-16: the start-up failure warning lives in dllmain.cpp
                 # and is raised from the proxy, so both files need anchors.
                 "dllmain.cpp", "proxy/Proxy.cpp")}
# Code-only view (comments and literals blanked) for the negative tests below:
# the new comments deliberately QUOTE the old buggy lines, so a raw substring
# search would report them as still present.
srcc = {f: strip_code(v) for f, v in src.items()}

FIXES = [
    ("P0-1a SetNetworkPassword NULL guard", "Protection.cpp",
     "if (pass == nullptr || *pass == '\\0')"),
    # --- config synchronisation (2026-09-15, second pass) -----------------
    # These replace the old P0-1b/P0-1c anchors: the malloc-based password
    # handling they checked for is gone entirely, replaced by an inline buffer
    # and a lock.
    ("P0-1b config mutex", "Protection.cpp",
     "std::mutex g_config_mutex;"),
    ("P0-1c password is inline buffer", "Protection.cpp",
     "char networkpassword[1024];"),
    ("P0-1d snapshot capture helper", "Protection.cpp",
     "void capture_locked(values& v) const"),
    ("P0-1e snapshot publish helper", "Protection.cpp",
     "void publish_locked(const values& v)"),
    ("P0-1f publish is one step", "Protection.cpp", "publish_locked(v);"),
    ("P0-1g parse writes the copy", "Protection.cpp",
     "strncpy_s(v.networkpassword, sizeof(v.networkpassword), val.data(), _TRUNCATE);"),
    ("P0-1h apply copies out of lock", "Protection.cpp",
     "memcpy(playername, user_config.playername, sizeof(playername));"),
    ("P0-1i name getter copies", "Protection.cpp",
     "void t7patch_cfg_playername(char* dst, size_t dstSize)"),
    ("P0-1j password getter copies", "Protection.cpp",
     "void t7patch_cfg_network_password(char* dst, size_t dstSize)"),
    ("P0-1k watcher time locked", "Protection.cpp",
     "bool update_watcher_time_locked(const char* path)"),
    ("P0-1l saveto takes the lock", "Protection.cpp",
     "values v;\n        capture_locked(v);"),
    ("P0-1m menu uses copying getters", "overlay.cpp",
     "t7patch_cfg_playername(confName, sizeof(confName));"),
    ("P0-1n P0-1d set_playername NULL guard", "Protection.cpp",
     "    if (!v)\n        return; // strncpy_s with a null source"),
    ("P0-2  getline loop", "Protection.cpp",
     "while (std::getline(infile, line))"),
    ("P0-3  CRLF strip", "Protection.cpp",
     "if (!line.empty() && line.back() == '\\r')"),
    ("P0-3b empty value accepted", "Protection.cpp",
     "if (sep == std::string::npos)\n            {"),
    ("P0-2b OLD getline gone", "Protection.cpp", None),
    ("P1-1  strcpy_s guards", "Hooks.cpp",
     "if (strlen(source) > 4095)"),
    ("P1-2  PrepReadMsg clarified", "Hooks.cpp",
     "const bool primed = LobbyMsgRW_PrepReadMsg(lm);"),
    ("P1-2b second ReadByte stays conditional", "Hooks.cpp",
     "if (firstByte == ZBR_PREFIX_BYTE)"),
    ("P1-3  chat scan bounded", "Protection.cpp",
     "while (msgLen < msgCap && msg[msgLen] != '\\0')"),
    ("P1-4  swap records once", "Protection.cpp",
     "if (slots.find(vPointerIndex) == slots.end())"),
    ("P1-5  find() null guard", "Protection.cpp",
     "if (!func_ptr)\n            return 0;"),
    ("P1-5b ordinal skip", "Protection.cpp",
     "if (nameThunk[func_idx].u1.Ordinal & IMAGE_ORDINAL_FLAG64)"),
    ("P1-5c bound-import skip", "Protection.cpp",
     "if (iid->OriginalFirstThunk == 0)"),
    ("P2-1  atomic editBufsLoaded", "overlay.cpp",
     "std::atomic<bool> g_editBufsLoaded{ false };"),
    ("P2-1b atomic autofill", "overlay.cpp",
     "std::atomic<bool> g_playerNameAutofill{ false };"),
    ("P2-7  menu_key clamp", "Protection.cpp",
     "if (ivalread.fail() || v.menu_key < 1 || v.menu_key > 255)"),
    ("LNK4070 .def kept as d3d11", "proxy/d3d11.def", "LIBRARY d3d11"),
    ("CWD comment corrected", "t7patch_log.cpp",
     "Note the CWD is per-process, not per-thread"),
    # 2026-09-15: the gate is the screen label signal and NOTHING else - the
    # 60 s timer fallback popped the overlay over the idle "按ENTER开始" screen
    # and was removed outright (user call: "不要兜底吧").
    ("gate is label-signal only", "Protection.cpp",
     "const bool mainMenuUp = dismissed != 0 && hooks::UiMainMenuSeen();"),
    ("gate logs which signal fired", "Protection.cpp",
     "NotifyMainMenuReached(\"main-menu label rendered\")"),
    ("gate log carries a reason", "overlay.cpp",
     "menu auto-open in %llu ms (%s, menu_auto_open=1)"),
    # 2026-09-15 (later): the auto-open is DEFERRED by kAutoOpenDelayMs - a menu
    # already on screen the moment the player arrives reads as "it was waiting
    # for me" (user call: "改为进入主菜单之后延迟1.5s弹出").
    ("auto-open deferred 1.5 s", "overlay.cpp",
     "constexpr unsigned long long kAutoOpenDelayMs = 1500;"),
    ("Present fires the deferred open", "overlay.cpp",
     "if (autoOpenDue != 0 && GetTickCount64() >= autoOpenDue)"),
    ("deferred open re-reads the conf", "overlay.cpp",
     "g_editBufsLoaded = false; // re-read the text buffers from the conf"),
    ("hotkey cancels a pending auto-open", "overlay.cpp",
     "g_autoOpenDueMs = 0;\n\n                // [LOCAL] Menu open/close is not logged on purpose"),
    # 2026-09-15: "renaming needs a game restart" / "the picture stutters once at
    # start-up" - both became loggable facts instead of guesses.
    ("runtime rename mirrors the start-up write", "Protection.cpp",
     "memcpy((void*)PTR_Name1, Protection::CustomName, nameBytes);"),
    ("rename writes s_playerData too", "Protection.cpp",
     "memcpy((void*)(*(INT64*)s_playerData_ptr + 0x8), Protection::CustomName, nameBytes);"),
    ("rename apply is logged", "Protection.cpp",
     "playername applied to the front-end strings (%u bytes)"),
    # 2026-09-17: the log line states the ACTUAL result now.  saveto() reports a
    # short flush since this batch, so a fixed "written to disk" string was both
    # a stale anchor and a lie on the failure path.  The old form is checked as
    # a removal below.
    ("config write reports the actual result", "Protection.cpp",
     "overlay::DebugLog(written ? \"config written to disk\""),
    ("a failed config write is reported", "Protection.cpp",
     "\"config could not be written to disk\""),
    ("first warm-up frame is timed", "overlay.cpp",
     "first warm-up frame took %llu ms (font atlas + first ImGui pipeline)"),
    # 2026-09-15 (later): a menu Save never reached the engine.  saveto() stamps
    # the timestamp of the file it just wrote, so the watcher's next poll
    # legitimately reports "unchanged" and skipped the apply - playername /
    # networkpassword / isfriendsonly only took effect on the next game start.
    # Measured 11:37:35: "config written to disk" in the log, no "playername
    # applied to the front-end strings" after it, conf on disk carrying
    # playername=muyou233.  The fix hands the apply to MainThread explicitly.
    ("menu Save hands the apply to MainThread", "Protection.cpp",
     "g_config_apply_pending = true;"),
    ("MainThread consumes the pending apply", "Protection.cpp",
     "const bool menuSavePending = g_config_apply_pending.exchange(false);"),
    ("engine push is logged", "Protection.cpp",
     "overlay::DebugLog(\"settings applied to the engine\");"),
    # 2026-09-15 (later): tooltips fired the instant the pointer touched an item,
    # so crossing the (small) panel popped them up on the way to anything.  The
    # delay is defined ONCE in the style; the call sites just use the ForTooltip
    # hover test (SetItemTooltip() is that idiom spelled short).
    ("tooltip hover flags defined", "overlay.cpp",
     "s.HoverFlagsForTooltipMouse = ImGuiHoveredFlags_Stationary"),
    ("tooltip delay knobs exist", "overlay.cpp",
     "constexpr float kTooltipDelaySec = 0.60f;"),
    ("icon tooltip uses the delayed test", "overlay.cpp",
     "if (linkTipDue)\n                ImGui::SetTooltip(\"%s\", L()->about);"),
    # 2026-09-15 (latest): UI translation, second pass.  The first version
    # matched whole strings, which can never match the engine's composed text -
    # the front-end wraps fragments in control bytes and nests them (15 "Party
    # Privacy: " 15 "Open" 14).  Lookups now run per fragment, keys may carry a
    # '*' wildcard for the parts that change ("level *"), and a dictionary saved
    # while the game runs is picked up without a restart.
    ("translate splits runs at markers", "translate.cpp",
     "bool NextRun(const char*& cursor, Run& run)"),
    ("translate trims run padding both ends", "translate.cpp",
     "while (trimmed > begin && trimmed[-1] == ' ')"),
    ("translate template matcher exists", "translate.cpp",
     "bool MatchTemplate(const WildPattern& p, const char* key, size_t* captureBegin,"),
    ("translate renders captured text back", "translate.cpp",
     "bool RenderTemplate(const WildPattern& p, const char* original,"),
    ("translate exact entries beat templates", "translate.cpp",
     "const auto it = g_dict.find(lowerKey);"),
    ("translate templates sorted narrow first", "translate.cpp",
     "return a.parts.size() < b.parts.size();"),
    ("translate dictionary hot reloads", "translate.cpp",
     "void RefreshDictionaryIfChanged()"),
    ("translate publishes tables in one step", "translate.cpp",
     "g_dict.swap(dict);"),
    ("translate collector records runs", "translate.cpp",
     "// Same run split as Lookup: the dump has to hold exactly the pieces the"),
    ("translate rejects over-long lines", "translate.cpp",
     "if (len > sizeof(line) - 2)"),
    ("translate loader trims keys like the lookup", "translate.cpp",
     "TrimTrailing(p);"),
    # 2026-09-16: the lookup path stops paying for zero-initialised scratch
    # buffers (4 KB of memset per UI string) and the first-hit diagnostic copy
    # is length-exact instead of a flat 1 KB.
    ("translate key buffer is not zero-filled", "translate.cpp",
     "char key[kRunMax];"),
    ("translate replacement buffer is not zero-filled", "translate.cpp",
     "char replacement[kRunMax * 2];"),
    ("translate collector buffer is not zero-filled", "translate.cpp",
     "char clean[kRunMax];"),
    ("translate first-hit copy is length exact", "translate.cpp",
     "memcpy(firstHit, key, run.length);"),
    # 2026-09-16: collection skips real CJK, not "any non-ASCII byte" - the old
    # test also dropped English strings carrying typographic quotes.
    ("translate collection skips only CJK", "translate.cpp",
     "if (cp >= 0x4E00 && cp <= 0x9FFF)"),
    # --- 2026-09-16 (later): built-in dictionary + on-demand network update ---
    # The dictionary now ships inside the dll as the factory default (so an
    # install is self-contained and a lost file no longer kills the feature),
    # the external file still wins whenever it yields entries, and the network
    # is touched ONLY when the player clicks the button.
    ("dictionary parser takes a buffer (one parser, two sources)", "translate.cpp",
     "LoadResult ParseDictionaryBuffer(const char* data, size_t size,"),
    ("dictionary file is slurped into that parser", "translate.cpp",
     "LoadResult ParseDictionaryFile(const char* path,"),
    # UPDATED 2026-09-16 (later).  This anchor used to read
    # "FindResource(nullptr," - which was the BUG, not the fix.  A NULL hModule
    # means the PROCESS main module, i.e. BlackOps3.exe, while the RCDATA is
    # compiled into d3d11.dll - so the lookup could never succeed and the
    # built-in fallback was dead code.  Measured live: the owner renamed the
    # game's translate_zh.txt away and translation stopped entirely.  The anchor
    # now pins the FIX (our own handle, resolved from this function's address)
    # and the old form is a removal check below.
    ("built-in dictionary is read from our own module", "translate.cpp",
     "GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |"),
    ("external file wins, built-in is the fallback", "translate.cpp",
     "LoadResult LoadEffectiveDictionary(const char* path, unsigned long long stamp,"),
    ("dictionary source is named in the log", "translate.cpp",
     "SourceName(source),"),
    ("losing the file falls back to the built-in copy", "translate.cpp",
     "\"fell back to the built-in default\""),
    ("dictionary path is exposed for the updater", "translate.cpp",
     "bool DictionaryPath(char* out, size_t outSize)"),
    ("entry count is exposed for the updater", "translate.cpp",
     "unsigned EntryCount()"),
    ("built-in dictionary id comes from the shared header", "translate.cpp",
     "MAKEINTRESOURCE(IDR_TRANSLATE_DICT)"),
    ("update runs on a worker thread", "dict_update.cpp",
     "std::thread(Worker).detach();"),
    ("update is button-triggered, never automatic", "overlay.cpp",
     "dict_update::Start();"),
    # 2026-09-16: the switch of "which dictionary is in force" must not depend on
    # a timestamp changing - the updater forces the re-read instead, so a player
    # who was running on the built-in copy switches to the downloaded file on the
    # next UI rebuild without restarting.
    ("translate can be told to reload", "translate.cpp",
     "void RequestReload()"),
    ("forced reload skips the write-time poll", "translate.cpp",
     "const bool forced = g_reloadRequested.exchange(false);"),
    ("the updater forces that reload", "dict_update.cpp",
     "translate::RequestReload();"),
    # 2026-09-16: the miss sample is gone (see the negative test below); the hit
    # sample stays, because it is how you see from the log that the layer is live.
    ("translate still samples the first few hits", "translate.cpp",
     "if (replaced && hits.fetch_add(1) < 5)"),
    # 2026-09-16 (panel layout): the update button must NOT have a row of its own
    # (the panel is a fixed 395x440 and an extra row pushes the bottom line out
    # of sight), the hotkey reminder lives next to the hotkey it describes, and
    # the bottom line carries the update state beside the GitHub mark.
    # 2026-09-16 (later): the panel grew page tabs - the main page was full, so
    # the (low-frequency) update button moved to page 2 and the main page got its
    # row budget back.
    ("update button lives on the second page", "overlay.cpp",
     "BeginCardSized(L()->moreCard, toolsFill);"),
    ("page tabs render above the cards", "overlay.cpp",
     "LangButton(L()->pageGeneral, g_activePage == 0)"),
    # 2026-09-16 (last): the third tab.  The DXVK feature outgrew its borrowed
    # row on the tools page and moved to a page of its own - download, enable
    # and the three settings in one place.
    ("dxvk has its own page and tab", "overlay.cpp",
     "LangButton(L()->pageDxvk, g_activePage == 1)"),
    ("dxvk settings persist through dxvk.conf", "dxvk_download.cpp",
     "dxvk conf saved: maxFps=%d"),
    # The button must share the row with the mod-translation switch - this
    # SameLine was lost in an edit once and the button dropped to its own row
    # (2026-09-16, caught by the user's screenshot).
    ("update button shares the row with the switch", "overlay.cpp",
     "ImGui::SameLine();\n                char dictBtn[96]{};"),
    ("hotkey reminder sits beside the hotkey", "overlay.cpp",
     "snprintf(hint, sizeof(hint), L()->hint, VkName(t7patch_menu_key()));"),
    ("update state sits beside the button", "overlay.cpp",
     "ImGui::Text(L()->dictUpdatedFmt, du.entries);"),
    ("bottom row is the github mark alone", "overlay.cpp",
     "ImGui::SetCursorPosX(ImGui::GetWindowSize().x"),
    # 2026-09-16 (later): the mod-translation switch comes to the UI (page 2,
    # next to the update button), and the config-apply path must re-run
    # translate::Init() so turning the switch OFF takes effect too (EnsureLoaded
    # returned early while the layer was enabled); Init itself now short-circuits
    # a re-apply that changes nothing.
    ("translate has a config setter", "Protection.cpp",
     "void t7patch_cfg_set_translate(int enabled)"),
    ("config apply re-runs translate init", "Protection.cpp",
     "translate::Init();"),
    ("updater follows the system proxy", "dict_update.cpp",
     "WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY"),
    ("updater refuses a much smaller download", "dict_update.cpp",
     "kMinKeepRatio"),
    ("updater replaces the dictionary atomically", "dict_update.cpp",
     "MoveFileExA(tmp, path, MOVEFILE_REPLACE_EXISTING)"),
    # 2026-09-16 (last): the optional DXVK download.  Same shape as the
    # dictionary updater, but the validator is a pinned SHA-256 - a binary
    # payload cannot afford "looks plausible" heuristics, one wrong byte is
    # a DLL that must never reach the disk under its real name.
    ("dxvk downloader is button-triggered, never automatic", "overlay.cpp",
     "dxvk_download::Start();"),
    ("dxvk downloader runs on a worker thread", "dxvk_download.cpp",
     "std::thread(Worker).detach();"),
    ("dxvk downloader is single-flight", "dxvk_download.cpp",
     "g_state.compare_exchange_strong(current, static_cast<int>(State::Running))"),
    ("dxvk downloader has a success-only cooldown", "dxvk_download.cpp",
     "nowMs - lastMs < kCooldownMs"),
    ("dxvk downloads are locked to pinned hashes", "dxvk_download.cpp",
     "HexEquals(gotHex, file.sha256Hex)"),
    ("dxvk lands in the store, not loose in the game folder", "dxvk_download.cpp",
     "T7Patch\\\\dxvk\\\\%hs"),
    ("dxvk store directory is created on demand", "dxvk_download.cpp",
     "CreateDirectoryW(storeDir, nullptr);"),
    ("dxvk is replaced atomically", "dxvk_download.cpp",
     "MoveFileExW(tmpPath.c_str(), path, MOVEFILE_REPLACE_EXISTING)"),
    # 2026-09-16 (last): start-up language gate.  The replacements are Simplified
    # Chinese and a pack that is not Chinese has no CJK glyphs at all, so the first
    # Init of the session - and only that one - checks the game's own language and
    # switches the feature off unless that language IS Chinese.
    # BOTH Chinese scripts are accepted: the owner tested a Traditional install on
    # 2026-09-16 and our Simplified text renders normally there (mixed scripts, but
    # readable, and he liked the result), so the test is a plain "chinese"
    # substring - which also covers the Steam short forms schinese / tchinese.
    # The gate FAILS CLOSED: a language that cannot be read at all counts as "not
    # Chinese" too, because the rule is "translation only ever runs on a Chinese
    # game" - see the daily log for the owner's call.
    # It LATCHES the switch off rather than editing the config value: the first
    # Init comes from RunPatching(), and load_settings_initial() re-reads the conf
    # right after it - which silently undid the edit (2026-09-16 log: "switched
    # off" followed 3 ms later by "translate=1, dictionary loaded").
    ("game language is read from the game's localization file", "translate.cpp",
     "bool ReadGameLanguage(char* out, size_t outSize)"),
    ("language gate runs once, and only once, per session", "translate.cpp",
     "if (!g_langGateDone.exchange(true))"),
    ("language gate latches the switch off", "translate.cpp",
     "t7patch_cfg_block_translate(1);"),
    ("any chinese language pack is accepted", "translate.cpp",
     "bool IsChineseGameLanguage(const char* lang)"),
    ("the chinese test covers every spelling seen so far", "translate.cpp",
     "strstr(lang, \"chinese\") != nullptr"),
    ("the gate accepts traditional as well as simplified", "translate.cpp",
     "const bool chinese = known && IsChineseGameLanguage(lang);"),
    ("the latch masks the effective switch", "Protection.cpp",
     "!g_translate_language_block.load() && user_config.translate != 0"),
    ("a menu switch-on releases the latch", "Protection.cpp",
     "g_translate_language_block.store(false);"),
    ("mod translation tooltip states the chinese-only rule", "overlay.cpp",
     "开启自动模组汉化（游戏必须为中文）"),
    # The menu must draw the EFFECTIVE state, latch included.  A switch that
    # reads ON while the layer is held off is the same defect seen from the UI
    # side: the menu would promise translation that is not running.  The stored
    # value in the conf deliberately stays untouched (see the removals below),
    # so drawing the raw stored value is NOT an option here.
    ("the menu switch draws the effective state", "overlay.cpp",
     "bool modTrans = t7patch_cfg_translate_enabled();"),
    # 2026-09-16 (later): the gate's decision must OUTLIVE the session - the
    # owner's call was "just switch it off, the menu switch is how you turn it
    # back on", so the conf is written too.  translate.cpp only RAISES the
    # request, and only for a language it actually read; load_settings_initial()
    # owns the write, because that is the first moment the conf is known to be
    # loaded (the EarlyThread load happens before it, RunPatching before that).
    ("the gate asks for the switch-off to be persisted", "translate.cpp",
     "t7patch_cfg_persist_translate_off();"),
    ("the gate's decision is written off to the config", "Protection.cpp",
     "start-up language gate: mod translation switched off in the config"),
    # 2026-09-16 (last): an old config file is upgraded in place.  A file written
    # by an older build is missing settings this build knows, and loadfrom()
    # keeps the built-in default for a key the file does not mention - so the
    # setting works, but the file stops showing the player what there is to
    # configure and goes on looking like the current format.  The owner's call:
    # "if the file does not match, just generate a new one and overwrite the
    # old".  Three formats exist in the wild (see the daily log, 2026-09-16 27):
    # the upstream 3-key one, this fork's 7-key one, and the current 9.
    # The completeness test is a MASK, not a list of key names: every setting
    # gets one bit next to saveto()'s "outfile <<" line, so a key added there is
    # covered by the check automatically - an enumerated list would silently
    # stop noticing the newest setting.
    ("every recognised key is recorded as seen", "Protection.cpp",
     "v.keys_seen |= K_DEV_TOOLS;"),
    # 2026-09-18: the collection switch was renamed dump_ui_strings -> dev_tools.
    # The old spelling must STAY readable (an existing t7patch.conf keeps
    # collecting) and must deliberately NOT raise K_DEV_TOOLS - that is what
    # leaves keys_seen short of K_ALL and triggers the one-time rewrite that
    # migrates the file onto the new key name.
    ("the legacy collection key is still accepted", "Protection.cpp",
     'case FNV32("dump_ui_strings"):'),
    ("the legacy key does not count as the new one being present", "Protection.cpp",
     "// rewrite the file once, migrating the value onto the new key name."),
    ("dev_tools is the key that gets written out", "Protection.cpp",
     'outfile << "dev_tools=" << v.dev_tools << std::endl;'),
    ("the completeness test is a single mask comparison", "Protection.cpp",
     "missingKeys = patch_config::K_ALL & ~user_config.keys_seen;"),
    ("an outdated config file is rewritten in the current format",
     "Protection.cpp", "config file was in an older format"),
    ("a rewrite that fails is reported, not treated as fatal", "Protection.cpp",
     "config file is outdated but could not be rewritten"),
    ("the writer reports whether the file was written", "Protection.cpp",
     "bool saveto(const char* path)"),
    ("a successful write marks the file complete", "Protection.cpp",
     "keys_seen = K_ALL;"),
    # 2026-09-16: an unsupported game build (and a failed Arxan bypass) used to
    # be a silent no-op - one log line, and a player looking at a patch that
    # "does not work".  Both now raise a one-shot notice naming the build seen.
    #
    # The hard requirement is the thread: RunPatching() is reachable through the
    # zbr_run_gamemode_lui export, which a GSC menu can call on a game thread,
    # so a modal box on the calling thread would stall the game.  The notice is
    # therefore always shown from a thread of its own, while the patch keeps
    # refusing to run BEFORE anything is patched - "unsupported build" stays
    # "the game runs normally, just without the patch".
    ("the start-up notice exists", "dllmain.cpp",
     "void t7patch_warn_startup_failure(const char* reason)"),
    ("the notice is always shown from its own thread", "dllmain.cpp",
     "CreateThread(nullptr, 0, StartupWarningThread"),
    ("one notice per process", "dllmain.cpp",
     "if (warned.exchange(true)) return;"),
    ("the notice stays silent outside the game", "dllmain.cpp",
     "if (!ModuleIsBlackOps3()) return;"),
    ("the notice has a single reason line", "dllmain.cpp",
     "原因：%ls"),
    ("the proxy raises the notice as well as the log", "proxy/Proxy.cpp",
     "t7patch_warn_startup_failure(unsupportedReason);"),
    ("the proxy names the build it detected", "proxy/Proxy.cpp",
     "unsupported Black Ops III build (timestamp 0x%08X, image size 0x%08X)"),
    ("the arxan failure raises the notice too", "dllmain.cpp",
     "t7patch_warn_startup_failure(arxanMessage.c_str());"),
    # 2026-09-16: the proxy can carry a second D3D11 implementation (DXVK and
    # friends).  Only ONE file can own the name "d3d11.dll" in the game folder
    # and that slot is this proxy, so a drop-in translation layer has no way in
    # unless we forward to it.  Backend first, System32 for the ordinals the
    # backend lacks (it implements the D3D11 entry points only, while System32
    # also exports the D3DKMT*/D3D11Core* names this proxy has always
    # forwarded) - so no forwarder slot can ever be null.  With no backend file
    # present the old path is taken unchanged.
    ("the proxy can carry an alternate D3D11 backend", "proxy/Proxy.cpp",
     "kBackendNames[] = {"),
    ("the backend file is looked for next to the game", "proxy/Proxy.cpp",
     "L\"d3d11_backend.dll\","),
    ("every forwarder is filled backend-first", "proxy/Proxy.cpp",
     "void* entry = backend"),
    ("the export split is written to the log", "proxy/Proxy.cpp",
     "System32 fills %d, %d missing"),
    # 2026-09-16 (later): the chain is armed by the translation layer's DXGI,
    # NOT by the backend.  The game imports dxgi.dll statically, so a backend
    # paired with Microsoft's DXGI - or the reverse - would build swap chains
    # across two unrelated implementations.  Content decides, not the name;
    # and a backend without its DXGI is ignored instead of trusted.
    ("the dxgi that arms the chain is named in one place", "proxy/Proxy.cpp",
     "constexpr const wchar_t* kTranslationDxgi = L\"dxgi.dll\";"),
    ("the chain is armed by that dxgi, not by the backend", "proxy/Proxy.cpp",
     "bool translationDxgi = false;"),
    ("it is identified by content, not by file name", "proxy/Proxy.cpp",
     "translationDxgi = FileCarriesDxvkBanner(dxgiPath);"),
    ("the banner check looks for the DXVK marker", "proxy/Proxy.cpp",
     "buffer[i + 2] == 'V' && buffer[i + 3] == 'K'"),
    ("a half-installed pair raises the player-visible notice", "proxy/Proxy.cpp",
     "\"The game folder holds a DXVK dxgi.dll"),
    ("a bare backend is ignored and explained in the log", "proxy/Proxy.cpp",
     "backend ignored, the two files move as a pair"),
    ("DXVK's config lives outside the game folder by default", "proxy/Proxy.cpp",
     "SetEnvironmentVariableW(L\"DXVK_CONFIG_FILE\", confPath);"),
    # 2026-09-16 (later): the two "leave this scene untranslated" switches.
    # The owner's calls, in the order he made them: matches are the one place
    # the dictionary has nothing useful to say (player names, lobby names,
    # workshop map names) and the interface is shared with players who do not
    # read Chinese - so a Match is untranslated out of the box; Zombies was
    # added as a second, independent switch that ships OFF, i.e. Zombies is
    # translated like everything else until the player asks otherwise.
    #
    # Both are SUB-switches of translate, deliberately: with the feature off the
    # patch does not measure the scene at all (no engine call, no log line).
    # Both read as "skip = true", so the wording is identical and a third scene
    # would slot in without changing the shape.
    #
    # The gate is a SCENE, not a setting: it is folded into translate::Enabled()
    # rather than into t7patch_cfg_translate_enabled(), so the menu keeps drawing
    # the player's own switch value while the layer is held off.  The start-up
    # language latch does the opposite (it masks the menu's answer) because that
    # one is a decision about the player's file; this one changes by itself as
    # matches come and go, and a switch that un-ticked itself mid-match would
    # read as "my setting was lost".
    ("the Multiplayer sub-switch is a stored setting", "Protection.cpp",
     "v.keys_seen |= K_SKIP_PVP;"),
    ("the Zombies sub-switch is a stored setting", "Protection.cpp",
     "v.keys_seen |= K_SKIP_ZM;"),
    ("a Multiplayer match is untranslated by default", "Protection.cpp",
     "skip_pvp = 1;"),
    ("Zombies is translated by default", "Protection.cpp",
     "skip_zm = 0;"),
    ("both sub-switches are written to the config file", "Protection.cpp",
     "outfile << \"skip_zm=\" << v.skip_zm << std::endl;"),
    ("the sub-switches have menu-side setters", "Protection.cpp",
     "void t7patch_cfg_set_skip_zm(int skip)"),
    # The scene itself: two engine facts, read from the MainThread only.
    ("both match modes are recognised by their short codes",
     "Protection.cpp", "_stricmp(modeBuf, \"ZM\") == 0"),
    ("a scene is skipped only while its own switch is on", "Protection.cpp",
     "(zombies && t7patch_cfg_skip_zm())"),
    ("the scene is only measured while translation is on", "Protection.cpp",
     "translate::SetSceneBlocked(blocked);"),
    ("the mode that decided the gate is printed for verification",
     "Protection.cpp", "scene gate: session mode"),
    # The layer side.  Enabled() is the single funnel both hooks and the
    # collector already call, which is why Hooks.cpp needs no change at all.
    ("the scene gate is folded into the layer's own switch", "translate.cpp",
     "return g_enabled.load() && !g_sceneBlocked.load();"),
    ("the scene gate also silences the collector", "translate.cpp",
     "if (g_sceneBlocked.load())"),
    # Menu side: indented child rows, and they write through the config layer.
    ("the sub-switches are drawn as children of the translation switch",
     "overlay.cpp", "ImGui::Indent(12.0f);"),
    ("the menu writes the sub-switches through the config layer", "overlay.cpp",
     "t7patch_cfg_set_skip_zm(zmSkip ? 1 : 0);"),
    # --- 2026-09-17: the defect batch that came out of the source re-check ---
    # Every anchor below pins the new form of one of those fixes; each one was
    # verified against the code first, not taken from the review list.
    #
    # A second install() zeroes oIsProcessorFeaturePresent - detour_iat_ptr()
    # returns 0 once the IAT slot is already ours, and the live hook calls that
    # pointer - and starts a second MainThread.  Nothing in it is idempotent,
    # which is why a one-shot gate is the whole fix.
    ("install() is guarded by a one-shot gate", "Protection.cpp",
     "static std::atomic<bool> installDone{ false };"),
    ("the repeat install is ignored, not applied", "Protection.cpp",
     "if (installDone.exchange(true))"),
    # The throwing <filesystem> overloads turned an OS-level stat failure into
    # an uncaught exception on the MainThread's once-a-second poll, i.e. into
    # std::terminate.  fs_exists() lost its exists() call entirely (the
    # attribute call below it already answered) and the watcher uses the
    # error_code overload.
    ("the watcher stats without a throwing overload", "Protection.cpp",
     "std::filesystem::last_write_time(path, ec);"),
    # A dvar table that never appears used to be followed by install() writing
    # through the NULL pointer it read from the same slot.  The proxy refuses to
    # patch now, and the refusal is shown to the player.
    ("the proxy fails closed when the dvar table never appears", "proxy/Proxy.cpp",
     "if (*reinterpret_cast<volatile INT64*>(REBASE(kDvarTableRva)) == 0)"),
    ("that refusal reaches the player, not just the log", "proxy/Proxy.cpp",
     "\"T7 Patch could not start: the game"),
    # menu_lang defaults to Chinese, so a machine without any of the four CJK
    # fonts used to come up as a panel of boxes with nothing in the log.
    ("a missing CJK font is reported", "overlay.cpp",
     "\"font: no CJK system font found (tried MiSans, \""),
    # Two lines on purpose: a bare "t7patch_cfg_set_menu_lang(0);" also exists
    # on the menu's own EN button, so it would pass even with the fallback
    # deleted.  Pairing it with the AddFontDefault() call above pins the
    # fallback itself.
    ("and the menu falls back to English", "overlay.cpp",
     "io.Fonts->AddFontDefault();\n                t7patch_cfg_set_menu_lang(0);"),
    # "could not open" and "written by an older build" both leave keys_seen
    # short of K_ALL.  Only the second may be answered by rewriting the file -
    # after the first, a rewrite replaces the player's settings with defaults.
    ("a config read failure is remembered", "Protection.cpp",
     "bool read_failed;"),
    ("a read failure is not mistaken for an old format", "Protection.cpp",
     "if (missingKeys != 0 && readFailed)"),
    ("a failed config read is reported", "Protection.cpp",
     "\"config file is present but could not be read - \""),
    # close() is where the buffer is flushed.  A short write used to be stamped
    # as current, marked complete in memory and reported as success.
    ("a short config write is detected", "Protection.cpp",
     "\"config file could not be written completely - \""),
    # downloadProgress is reached from whichever threads Steam drives the
    # interface on, and its operator[] can rehash under a concurrent reader.
    ("the DLC download cache is guarded", "Protection.cpp",
     "std::mutex downloadProgress_mutex;"),
    ("and the guarded section excludes the engine call", "Protection.cpp",
     "std::lock_guard<std::mutex> lock(downloadProgress_mutex);"),
    # 2026-09-17 (later): enabling MOVES the pair out of T7Patch\dxvk into the
    # game folder, so the per-file store check below cannot see it - the worker
    # used to re-fetch both files (12.9 MB) back into the store, leaving the
    # pair in BOTH places.  That is the Mixed state Query() reports, which the
    # menu draws as an unticked toggle while DXVK is in fact on.  The guard
    # reads Query() on purpose: the menu toggle and the download then answer
    # from one source instead of two views that can drift apart.
    ("the download skips a pair that is already enabled", "dxvk_download.cpp",
     "inst == InstallState::Enabled || inst == InstallState::Mixed"),
    # 2026-09-17 (later): the two secondary consequences of that state.  Drawing
    # it as unticked told the player DXVK was off while it loaded at every
    # launch, and Disable() could never undo it because its move target - our
    # own parked copy - already existed.
    ("a pair in both places is drawn as enabled", "overlay.cpp",
     "|| inst == dxvk_download::InstallState::Mixed;"),
    ("turning DXVK off replaces a stale parked copy", "dxvk_download.cpp",
     "const DWORD flags = toGame ? 0 : MOVEFILE_REPLACE_EXISTING;"),
    # 2026-09-17 (later): a failed second half used to be left where it was -
    # the one state nothing recovers from (both PairPresent() tests go false, so
    # Query() says Absent and the next launch can only report the mixture).
    ("the pair is moved with a rollback", "dxvk_download.cpp",
     "bool MovePair(bool toGame)"),
    ("and the rollback says so in the log", "dxvk_download.cpp",
     "putting back what had "),
    # 2026-09-17 (later): page 1 used to depend on its three auto-sized cards
    # adding up to the panel height.  That is a coincidence with a fixed,
    # scrollbar-less panel - the next row added would leave a gap or be clipped.
    ("the first page's last card fills the page", "overlay.cpp",
     "BeginCardSized(L()->config, ImGui::GetContentRegionAvail().y);"),
    # 2026-09-17 (graphics page, screenshot-driven user calls): the three DXVK
    # settings are children of the DXVK switch - greyed AND indented while it is
    # off - and the FPS cap's step buttons are ours now, which is the only reason
    # they can be small.  The two tooltips are pinned here as well; the exact
    # tooltip COUNT is checked further down.
    ("dxvk settings follow the dxvk switch", "overlay.cpp",
     "const bool dxSettingsOn = dxAvailable && dxOn;"),
    ("graphics page tooltips are wired", "overlay.cpp",
     'ImGui::SetItemTooltip("%s", L()->dxvkTearTip);'),
    ("dxvk toggle explains what the backend is", "overlay.cpp",
     'ImGui::SetItemTooltip("%s", L()->dxvkToggleTip);'),
    # 2026-09-17 (row alignment; owner: "很多布局文本和组件都有轻微高低差，不是中心
    # 平行对齐").  ImGui aligns same-line items to the TOP of the line, so: a bare
    # Text() that leads a row sits one FramePadding (4 px) high, a short button
    # beside a taller field sits high, and SolidCheckbox's row used to be one text
    # line tall instead of the frame height.  All three are pinned here.
    ("the fps cap label is aligned to the frame padding", "overlay.cpp",
     "ImGui::AlignTextToFramePadding();\n"
     "                ImGui::TextUnformatted(L()->dxvkMaxFps);"),
    ("the fps cap step buttons are square and centred", "overlay.cpp",
     "const float fpsStepDrop = (fpsRowHeight - fpsStepSide) * 0.5f;"),
    ("the language label is aligned to the frame padding", "overlay.cpp",
     "ImGui::AlignTextToFramePadding();\n"
     "            ImGui::TextUnformatted(L()->language);"),
    ("the hotkey label is aligned to the frame padding", "overlay.cpp",
     "ImGui::AlignTextToFramePadding();\n"
     "            ImGui::TextUnformatted(L()->hotkey);"),
    ("a checkbox label sits at the frame padding", "overlay.cpp",
     "const float labelY = pos.y + style.FramePadding.y;"),
    # 2026-09-17 (button feedback): holding a button used to paint it in the
    # accent, which flashed on every click AND made "held" look identical to
    # "selected" (owner: "按钮点了都会闪一下才是橙色").
    ("a pressed button is not the accent", "overlay.cpp",
     "c[ImGuiCol_ButtonActive] = ImVec4(0.240f, 0.240f, 0.240f, 1.00f);"),
    # 2026-09-17 (later; owner: "这个DXVK的hud能提供更多设置显示吗…给一个勾选显示哪些"):
    # dxvk.hud became a per-element bitmask with one tick per element, instead of
    # one checkbox that always wrote the same fps,frametimes,gpuload trio.
    ("the HUD is one tick per element", "overlay.cpp",
     "void HudTick(const char* label, unsigned bit, dxvk_download::Conf& conf,"),
    # 2026-09-17 (bug found on the owner's screenshot): 3 + 3 ticks must be two
    # rows.  The helper's SameLine() glued the second row back onto the first and
    # the six ticks ran off the panel edge, so the row that starts the line
    # passes sameLine = false and is pinned here.
    ("the second tick row starts its own line", "overlay.cpp",
     "HudTick(L()->dxvkHudMemory, dxvk_download::HUD_MEMORY, dc, false);"),
    # 2026-09-17 (same screenshot): the font's +/- sat 3.5 px low and 1-2 px
    # right inside the 20 px step buttons (measured), because ImGui centres the
    # text LINE BOX and the glyphs hang off the baseline.  They are drawn now.
    ("the step buttons draw their own sign", "overlay.cpp",
     "bool StepButton(const char* id, float side, bool plus)"),
    ("and each tick writes its own dxvk.hud name", "dxvk_download.cpp",
     "for (const HudName& n : kHudNames)"),
    # 2026-09-17 (later; owner: "子选项设置跟主设置树状图的分支线 UI 效果…看着更有
    # 归类感"): the two indented sub-option blocks are now joined to their switch by
    # a drawn guide (vertical line + one elbow per sub-item).  The indent itself is
    # unchanged, so this costs no row budget - hence three anchors, not one: the
    # helper and BOTH call sites.
    ("the sub-option guide exists", "overlay.cpp",
     "dl->AddLine(ImVec2(lineX, topY),"),
    ("the dxvk settings are joined to the dxvk switch", "overlay.cpp",
     "// The guide that ties every row below to the switch above."),
    ("the scene sub-switches are joined to mod translation", "overlay.cpp",
     "// The guide that ties the two switches below to"),
    # 2026-09-18: the dictionary could only ever match a WHOLE run, so a new
    # combination of an already-translated name silently stopped translating
    # ("Rogue Run: Black Ops 3" stayed English although "rogue"=游侠 and
    # "black ops 3"=黑色行动 3 were both in the dictionary).  Marked fragments
    # ("~" key marker) are the fix.  Opt-in is the whole point: the short single
    # words are what player names, group names and workshop map names collide
    # with, so a blanket "replace every key you find in the text" pass was
    # explicitly rejected (see the removal anchor for the whole-string matcher).
    ("translate has a fragment table with a key-length floor", "translate.cpp",
     "constexpr size_t kMinFragmentKey = 3;"),
    ("translate composes marked fragments inside a run", "translate.cpp",
     "bool ComposeFragments(const char* lowerKey, const char* original, char* out,"),
    ("translate fragments are matched longest first", "translate.cpp",
     "return a.key.size() > b.key.size();"),
    ("translate fragments are opt-in per dictionary entry", "translate.cpp",
     "bool composable = false;\n                if (*p == '~')"),
    ("translate fragment substitution is the last channel", "translate.cpp",
     "return ComposeFragments(lowerKey, original, out, outSize);"),
    ("translate publishes the fragment table too", "translate.cpp",
     "g_fragments.swap(fragments);"),
    # 2026-09-18: the diagnostics budgets are back to their diagnostic defaults.
    # They were raised (128 -> 2048 and 100 -> 512) and force-enabled while
    # chasing the font question with a probe build; the probe is over, so these
    # two anchors pin the revert.  Leaving the raised budgets in a release build
    # would cost ~180 KB of .bss and write a few thousand log lines per session
    # for nobody.
    ("UI model path budget is back to its default", "Hooks.cpp",
     "constexpr int kUiPathLogMax = 128;"),
    ("UI string budget is back to its default", "Hooks.cpp",
     "constexpr int kUiStringLogMax = 100;"),
    # 2026-09-18: 第三条字符串通道（HUD/LUI 文字绘制出口，见 Hooks.cpp 的说明）。
    # 要点各一条锚点：① 转发之后仍按过滤条件记录（观察不改写）；② 只在 bo3::address() 认得出来的
    # build 上安装（未知 build 会拿到 February 的 RVA ⇒ 挂错指令 = 崩游戏）；③ 开关沿用 dev_tools；
    # ④ 翻译走「传我们自己的缓冲」（不写调用方的内存）；⑤ 去重按「将要存下来的那一份」比较。
    # ⚠️ offsets.h 不在本脚本的文件清单里，所以那条声明故意不设锚点（设了会 KeyError）。
    ("HUD draw-text probe records the string it drew", "Hooks.cpp",
     "if (text && DrawnTextProbeEnabled() && LooksLikeUiSentence(text))"),
    ("HUD draw-text probe is installed only on a known build", "Hooks.cpp",
     "if (bo3::current_build() != bo3::Build::Unknown)"),
    ("HUD draw-text translation passes its own buffer", "Hooks.cpp",
     "translate::Lookup(text, slot, kDrawnTextTranslateMax)"),
    ("drawn-text dedupe compares the stored copy", "Hooks.cpp",
     "char key[sizeof(g_drawnTextStorage[0])]{};"),
    # 2026-09-18: 探针的过滤判据必须与采集通道同口径（只挡真正的 CJK 汉字，放行排版标点）。
    # 旧判据（任何字节 >= 0x80 就丢）会把带 em dash / 排版引号的英文串整条藏起来 ——
    # 采集通道当年踩过同一个坑（见 removals 里的 "translate non-ascii filter removed"）。
    ("HUD draw-text probe filters CJK only, not all non-ascii", "Hooks.cpp",
     "bool HasCjkIdeograph(const char* s)"),
    ("HUD draw-text probe uses the CJK-only filter", "Hooks.cpp",
     "return n >= 8 && space && letter && !HasCjkIdeograph(text);"),
    # 2026-09-19: 菜单打开时必须同时具备这四件套，少任何一件都会退回
    # "画面不压暗 / 面板看得见但点不动"（用户实机反馈）。注意是**正锚点**（3 字段）——
    # 一开始误写成了 4 字段塞进 removals 列表，被脚本末尾那个结构守卫当场拦下。
    ("menu draws a dim overlay", "overlay.cpp",
     "ImGui::GetBackgroundDrawList()->AddRectFilled("),
    ("menu unclips the game cursor every frame", "overlay.cpp",
     "ClipCursor(nullptr);"),
    ("menu draws its own cursor", "overlay.cpp",
     "imguiIo.MouseDrawCursor = true;"),
    ("menu swallows WM_SETCURSOR", "overlay.cpp",
     "case WM_SETCURSOR:"),
    # 2026-09-19 第二层：光靠"每帧 ClipCursor(nullptr)"压不住游戏（它每帧都会重新锁），
    # 必须从源头拦这三个 user32 API；少了任何一个就退回"光标锁在中间 / 游戏仍读到鼠标移动"。
    ("cursor hook: ClipCursor intercepted", "overlay.cpp",
     "BOOL WINAPI HookClipCursor(const RECT* lpRect)"),
    ("cursor hook: SetCursorPos intercepted", "overlay.cpp",
     "BOOL WINAPI HookSetCursorPos(int x, int y)"),
    ("cursor hook: raw input polling intercepted", "overlay.cpp",
     "UINT WINAPI HookGetRawInputBuffer(PRAWINPUT pData, PUINT pcbSize, UINT cbSizeHeader)"),
]

# Structure guard: FIXES entries are (name, file, needle).  A 4-field entry is a
# NEGATIVE check that belongs in the removals list - one of those slipping in
# here used to crash the unpack with "too many values to unpack", which killed
# the whole script AFTER the report file was last written, so a stale report sat
# there reading as PASS while stderr was swallowed by the caller.
for _entry in FIXES:
    assert len(_entry) == 3, (
        "FIXES entry has %d fields - negative checks (4 fields, with a src dict) "
        "belong in the removals list: %r" % (len(_entry), _entry[0]))

out.append("")
out.append("== fix anchors ==")
for name, f, needle in FIXES:
    if needle is None:
        # negative test: the old buggy form must be gone from the CODE
        present = "!std::getline(infile, line).eof()" in srcc[f]
        out.append("   %-38s %s" % (name, "FAIL (old code still present)" if present else "OK"))
        if present:
            fail += 1
        continue
    ok = needle in src[f]
    out.append("   %-38s %s" % (name, "OK" if ok else "FAIL (anchor missing)"))
    if not ok:
        fail += 1

# removed dead code must really be gone
out.append("")
out.append("== removals ==")
# g_sessionStart: a comment now mentions it, so search the CODE view.
# printf("\n"): the string literal is blanked by strip_code, so search raw.
for name, f, needle, view in (
    ("g_sessionStart removed", "overlay.cpp", "g_sessionStart", srcc),
    ("printf(\"\\n\") removed", "Protection.cpp", 'printf("\\n")', src),
    # 2026-09-17: the FPS cap field no longer draws the integer widget's own step
    # buttons.  Raw view on purpose - the needle contains a string literal, which
    # strip_code() blanks into spaces.
    ("old InputInt FPS step buttons removed", "overlay.cpp",
     'ImGui::InputInt("##dxvkmaxfps", &dc.maxFps);', src),
    # The whole malloc/free ownership dance on networkpassword is gone - that is
    # what closes the NULL window for good rather than just narrowing it.
    ("config password malloc removed", "Protection.cpp", "malloc(bufsize)", srcc),
    ("config password free removed", "Protection.cpp", "free(networkpassword)", srcc),
    ("__playername() helper removed", "Protection.cpp", "__playername", srcc),
    # 2026-09-18: the font-investigation probe build is reverted.  It raised the
    # diagnostics budgets (see the two anchors above) and force-enabled the
    # observer on every launch.  A re-appearing EnableUiModelPathLog(true) here
    # means a diagnostic build leaked into a release - exactly the kind of
    # "temporary" that otherwise stays forever.  Code view on purpose: the comment
    # that explains the revert mentions the same call, and strip_code() blanks it.
    ("font-investigation probe switch removed", "Protection.cpp",
     "EnableUiModelPathLog(true)", srcc),
    # 2026-09-18: 去重的旧写法（拿完整原串与截断副本比较）必须消失 —— 它让长串按帧刷屏。
    ("drawn-text dedupe no longer compares the full string", "Hooks.cpp",
     "strcmp(g_drawnTextSeen[i], text)", srcc),
    # 2026-09-18: 探针里那条裸非 ASCII 判据必须消失 —— 与 translate.cpp 当年
    # "HasNonAscii" 的坑同源：它把带排版标点/重音字母的英文原文整条藏起来。
    ("drawn-text probe no longer drops every non-ascii string", "Hooks.cpp",
     "if (c >= 0x80)", srcc),
    # 2026-09-18: 横幅那一路的备选出口探针**已全部拆除**（探索结案，结论见 offsets.h 的说明）——
    # 它们只是为了一次性取证而挂的 log-only 诊断，不该留在正式构建里。
    ("drawn-text alt-out padding probe removed", "Hooks.cpp",
     "LogDrawnText(\"drawtext2\"", srcc),
    ("drawn-text alt-out physical probe removed", "Hooks.cpp",
     "LogDrawnText(\"drawtext3\"", srcc),
    ("drawn-text game message probe removed", "Hooks.cpp",
     "LogDrawnText(\"gamemsg\"", srcc),
    ("drawn-text hook install logging removed", "Hooks.cpp",
     "LogHookStatus(", srcc),
    ("drawn-text first-call logging removed", "Hooks.cpp",
     "NoteFirstCall(", srcc),
    # The whole-string matcher of the first translation pass is gone: it could
    # never match composed UI text (see the translate anchors above).
    ("translate whole-string matcher removed", "translate.cpp", "FindCore", srcc),
    # 2026-09-16: the blunt non-ASCII collector filter is gone (it hid English
    # strings with curly quotes from the dump); HasCjk replaced it.
    ("translate non-ascii filter removed", "translate.cpp", "HasNonAscii", srcc),
    # 2026-09-16: the dictionary is no longer read line-by-line out of a file -
    # one buffer parser now serves both the external file and the built-in copy,
    # which is what keeps their behaviour identical.
    ("translate line-by-line file reader removed", "translate.cpp", "fgets(", srcc),
    # 2026-09-16: miss samples are no longer logged - a dozen lines per launch
    # saying "still English" is noise once the dictionary has settled, and
    # dev_tools=1 (formerly dump_ui_strings=1) answers "what is still English" properly.
    ("translate miss logging removed", "translate.cpp", "misses.fetch_add", srcc),
    # 2026-09-16: EnsureLoaded is gone entirely - the config-apply path re-runs
    # translate::Init() instead (which itself no-ops when nothing changed), so
    # turning the switch OFF takes effect too (EnsureLoaded returned early while
    # the layer was still enabled, which would have made the menu toggle a no-op
    # in the OFF direction).
    ("ensureloaded removed (init is unconditional)", "translate.cpp",
     "EnsureLoaded", srcc),
    # 2026-09-16: the start-up language gate must NOT write the conf file itself.
    # It raises a request (t7patch_cfg_persist_translate_off) and
    # load_settings_initial() - the config layer, positioned right after the
    # loadfrom that would otherwise undo the latch - owns the write.
    # translate.cpp runs from the engine path, where a file write is the last
    # thing it should be doing; a save() appearing here again is a regression.
    ("language gate does not write the conf", "translate.cpp",
     "t7patch_config_save", srcc),
    # 2026-09-16: ...and it must not edit the stored switch either.  The gate used
    # to set translate=0 in the config, and load_settings_initial() read
    # translate=1 straight back out of the conf 3 ms later - the feature came back
    # on and the player saw Chinese on a non-Chinese game.  The latch is what
    # makes the decision stick and the config layer is what writes it down; a
    # t7patch_cfg_set_translate() creeping back into translate.cpp is a
    # regression, not a simplification.
    ("language gate does not edit the stored switch", "translate.cpp",
     "t7patch_cfg_set_translate", srcc),
    # 2026-09-16 (last): the gate must not go back to a SIMPLIFIED-ONLY test.
    # It did that until the owner actually ran the game in Traditional Chinese and
    # saw our Simplified text render correctly, which settled the question the
    # helper's old comment was hedging about (unverified glyph coverage).  The rule
    # is now "any Chinese pack" - IsChineseGameLanguage, a plain substring test.
    # Re-introducing the narrow helper would switch translation off for a language
    # that is known to work, so it is a regression, not a safety measure.
    ("simplified-only language helper removed", "translate.cpp",
     "IsSimplifiedGameLanguage", srcc),
    # 2026-09-15: the gate has no timer and no on/off knob any more.
    ("uiLevelOnset removed", "Protection.cpp", "uiLevelOnset", srcc),
    ("kGateFallbackMs removed", "Protection.cpp", "kGateFallbackMs", srcc),
    ("fallbackPassed removed", "Protection.cpp", "fallbackPassed", srcc),
    ("menu_gate config key removed", "Protection.cpp", "menu_gate", srcc),
    ("t7patch_menu_gate removed", "framework.h", "t7patch_menu_gate", srcc),
    # 2026-09-15: NotifyMainMenuReached must SCHEDULE the open now, not perform
    # it - the immediate `g_menuOpen = true` there is what made the menu look
    # like it was already waiting on the main menu.
    ("NotifyMainMenuReached no longer opens the menu", "overlay.cpp",
     "if (t7patch_menu_auto_open())\n        {\n            g_menuOpen = true;", srcc),
    # 2026-09-15 (later): the watcher must no longer be the ONLY apply trigger.
    # This exact branch silently dropped every menu Save, because saveto()
    # stamps the mtime it just wrote - the poll then sees "unchanged".
    ("watcher-only apply branch removed", "Protection.cpp",
     "if (user_config.update_watcher_time(PATCH_CONFIG_LOCATION))\n        {\n"
     "            user_config.loadfrom(PATCH_CONFIG_LOCATION);\n"
     "            apply_settings();\n        }", srcc),
    # 2026-09-15 (later): the tooltip that used to hang off a bare
    # IsItemHovered() inside the icon's hover block.  The icon must use the
    # delayed test now; its cursor/tint stay on the instant one (checked below).
    ("icon tooltip no longer nested in instant hover", "overlay.cpp",
     "ImGui::SetMouseCursor(ImGuiMouseCursor_Hand);\n"
     "                // Label only.", srcc),
    # 2026-09-16: the unsupported-build log line must not lose the fingerprint
    # again.  A bare "not applied" reads like a broken install when a player
    # reports it, and those two numbers are the whole reason the guard can
    # distinguish "the game was updated again" from "something is wrong".
    # Raw view: the message is a string literal, which strip_code blanks out.
    ("fingerprint-less unsupported-build log removed", "proxy/Proxy.cpp",
     "unsupported executable, T7Patch not applied", src),
    # 2026-09-16 (later): the Multiplayer scene gate must not write the player's
    # sub-switch from inside translate.cpp, for the same reason the language
    # latch must not: the gate decides what is drawn RIGHT NOW, the stored value
    # is the player's preference, and they live in different layers on purpose.
    # A setter appearing here would mean a match could rewrite a setting.
    ("the scene gate never writes the sub-switch itself", "translate.cpp",
     "t7patch_cfg_set_skip_pvp", srcc),
    # 2026-09-16 (later): and the built-in dictionary must not be looked up in
    # the PROCESS again - see the rewritten anchor above.  A NULL hModule is the
    # main module (BlackOps3.exe), never the caller, and the resource ships in
    # d3d11.dll: the old form made the built-in fallback silently unreachable,
    # which only showed up as "translation stopped" once the external file was
    # renamed away.
    ("built-in dictionary looked up in the process module removed", "translate.cpp",
     "FindResource(nullptr", srcc),
    # 2026-09-17: the config-write log assumed success.  Raw view, because the
    # string literal is what distinguishes the old form from the new one.
    ("config write success no longer assumed", "Protection.cpp",
     "overlay::DebugLog(\"config written to disk\");", src),
    # 2026-09-17: and the throwing overloads must not come back either.  Code
    # view on purpose - the new comment in fs_exists() names
    # std::filesystem::exists() to explain why it is gone.
    ("throwing filesystem exists() removed", "Protection.cpp",
     "std::filesystem::exists(", srcc),
    ("throwing last_write_time removed", "Protection.cpp",
     "std::filesystem::last_write_time(path);", srcc),
    # 2026-09-17: the accent must not come back as the HELD colour - see the
    # "a pressed button is not the accent" anchor above.
    ("pressed buttons no longer borrow the accent", "overlay.cpp",
     "c[ImGuiCol_ButtonActive] = ImVec4(1.000f, 0.459f, 0.004f, 1.00f);", srcc),
    # 2026-09-17: and the FPS step buttons must not go back to the full-height
    # shape - two tall pills beside a 26 px field (owner: "这个加减按钮不美观").
    ("tall fps step buttons removed", "overlay.cpp",
     "ImVec2(fpsStepWidth, fpsRowHeight)", srcc),
    # 2026-09-17: the HUD must not go back to a fixed trio - what it shows is
    # whatever the player ticked.  Raw view: the needle contains a literal.
    ("the fixed hud trio is gone", "dxvk_download.cpp",
     'out += "dxvk.hud=fps,frametimes,gpuload\\n";', src),
):
    present = needle in view[f]
    out.append("   %-38s %s" % (name, "FAIL (still present)" if present else "OK"))
    if present:
        fail += 1

# 2026-09-15 (later): tooltip hover policy.  A bare IsItemHovered() is the
# instant form - the one that popped a tooltip on every fly-by.  Exactly ONE
# may remain in the file: the GitHub mark's cursor/tint, which must not lag the
# pointer.  Checked on the stripped view so the new comments (which mention the
# old idiom by name) cannot satisfy or break the count.
out.append("")
out.append("== tooltip hover policy ==")
_bare = srcc["overlay.cpp"].count("ImGui::IsItemHovered()")
out.append("   %-38s %s" % ("bare IsItemHovered() == 1 (icon tint only)",
                            "OK" if _bare == 1 else "FAIL (%d found)" % _bare))
if _bare != 1:
    fail += 1
_tips = srcc["overlay.cpp"].count("ImGui::SetItemTooltip(") \
    + srcc["overlay.cpp"].count("ImGui::SetTooltip(")
# 13 since 2026-09-17 (later): the twelve before, plus the DXVK toggle's "what is
# this backend" tip.
# (Deliberately an exact count - the point is that a tooltip cannot quietly
# disappear or appear without this line being revisited.)
out.append("   %-38s %s" % ("all 13 tooltips still present",
                            "OK" if _tips == 13 else "FAIL (%d found)" % _tips))
if _tips != 13:
    fail += 1

out.append("")
out.append("RESULT: %s (%d failure(s))" % ("PASS" if fail == 0 else "FAIL", fail))

io.open(os.path.join(_REPO, r"tools\fixcheck.txt"), "w",
        encoding="utf-8").write("\n".join(out) + "\n")
print("\n".join(out))
sys.exit(0)
