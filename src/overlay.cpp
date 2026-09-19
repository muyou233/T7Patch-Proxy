// overlay.cpp - in-game ImGui menu for T7Patch
//
// Wiring: the game creates its D3D11 device through our proxy; once we have
// seen the swap chain (either from D3D11CreateDeviceAndSwapChain or via a
// hooked IDXGIFactory::CreateSwapChain) we:
//   1. swap Present (vtable slot 8) with our own function,
//   2. hook the game window's WndProc so Insert toggles the menu and ImGui
//      receives input,
//   3. initialise ImGui (win32 + dx11 backends).
// From then on every frame runs through HookPresent below, which renders the
// menu right before the game's own present call.
//
// The menu itself (cards, theming, per-row save, 46 toggle) lives in
// DrawMenu(); the [LOCAL] comments document the thread-safety rules that
// apply to anything added there.

#include "framework.h"
#include <d3d11.h>
#include <dxgi.h>
#include <dxgi1_2.h> // IDXGIFactory2 / CreateSwapChainForHwnd live here, not in dxgi.h
#include <shellapi.h>    // ShellExecuteA - the bottom-right link hands the URL to the shell
#include "overlay.h"
#include "Hooks.h"       // [LOCAL] 46-block runtime toggle + interception counter
#include "t7patch_log.h" // [LOCAL] the patch's single runtime log
#include "GithubMark.h"  // [LOCAL] embedded alpha mask for the bottom-right link
#include "dict_update.h" // [LOCAL] on-demand dictionary update (button-triggered)
#include "dxvk_download.h" // [LOCAL] on-demand Vulkan backend download (button-triggered)
#include "imgui/imgui.h"
#include "imgui/backends/imgui_impl_dx11.h"
#include "imgui/backends/imgui_impl_win32.h"

// [LOCAL] The backend wraps this declaration in "#if 0" on purpose: callers
// are expected to copy it into their own .cpp (see imgui_impl_win32.h).
extern IMGUI_IMPL_API LRESULT ImGui_ImplWin32_WndProcHandler(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam);

#include <atomic>
#include <mutex>

namespace
{
    // [LOCAL] Palette - exact BO3 orange sampled by the user in Photoshop:
    // #FF7501 = rgb(255,117,1) = HSV(27, 99%, 100%), on near-black.
    constexpr ImVec4 kAccent = ImVec4(1.000f, 0.459f, 0.004f, 1.00f);  // #FF7501
    constexpr ImVec4 kTextMain = ImVec4(0.925f, 0.925f, 0.925f, 1.00f);

    // [LOCAL] Target of the GitHub mark pinned to the panel's bottom-right
    // corner.  Hard-coded on purpose: the icon opens it via the shell, so
    // anything user-editable here would be an injection vector for no gain.
    constexpr const char* kRepoUrl = "https://github.com/muyou233/T7Patch-Proxy";

    // [LOCAL] The mark is drawn from an alpha mask (GithubMark.h) into a WHITE
    // texture, so these two colours are a pure tint - the icon can be recoloured
    // here without regenerating the art.  Rest matches the dimmed hint text it
    // sits next to; hover switches to the accent so the icon reads as clickable
    // (the buttons in the cards deliberately have no hover tint, but a link has
    // nothing else to signal "press me").
    constexpr ImVec4 kIconRest = ImVec4(0.720f, 0.720f, 0.720f, 1.00f);
    constexpr ImVec4 kIconHover = kAccent;

    // [LOCAL] Tooltip timing, in seconds.  The panel is small and the pointer
    // has to cross most of it to reach anything, so the ImGui default (fire the
    // instant the pointer touches an item) meant a tooltip popped up on every
    // fly-by.  A tooltip now needs BOTH: the pointer to stop moving for
    // kTooltipStillSec, and then to rest on the item for kTooltipDelaySec.
    // Tune these two numbers to taste - they are the only knobs.
    constexpr float kTooltipStillSec = 0.20f;
    constexpr float kTooltipDelaySec = 0.60f;

    void ApplyOverlayTheme()
    {
        ImGuiStyle& s = ImGui::GetStyle();

        // [LOCAL] What ImGui::IsItemHovered(ImGuiHoveredFlags_ForTooltip) - used
        // by every tooltip in DrawMenu, directly or via SetItemTooltip() -
        // resolves to for the mouse.  Setting the style field (rather than the
        // flags per call site) keeps one definition for the whole panel, and
        // ImGui still picks the nav variant automatically for gamepads.
        s.HoverStationaryDelay = kTooltipStillSec;
        s.HoverDelayNormal = kTooltipDelaySec;
        s.HoverFlagsForTooltipMouse = ImGuiHoveredFlags_Stationary
            | ImGuiHoveredFlags_DelayNormal
            | ImGuiHoveredFlags_AllowWhenDisabled;

        s.WindowRounding = 6.0f;
        s.ChildRounding = 5.0f;
        s.FrameRounding = 4.0f;
        s.GrabRounding = 4.0f;
        s.WindowBorderSize = 1.5f;   // chunkier so the full-orange outline reads
        s.ChildBorderSize = 1.5f;
        s.FrameBorderSize = 1.0f;
        s.WindowPadding = ImVec2(12.0f, 10.0f);
        s.FramePadding = ImVec2(8.0f, 4.0f);
        s.ItemSpacing = ImVec2(8.0f, 6.0f);
        s.CellPadding = ImVec2(4.0f, 2.0f); // tight table rows for the settings grid

        auto& c = s.Colors;
        c[ImGuiCol_WindowBg] = ImVec4(0.055f, 0.055f, 0.055f, 0.96f);  // near-black
        c[ImGuiCol_ChildBg] = ImVec4(0.100f, 0.100f, 0.100f, 0.88f);   // card grey
        c[ImGuiCol_Border] = ImVec4(1.000f, 0.459f, 0.004f, 1.00f);    // full #FF7501
        c[ImGuiCol_Text] = kTextMain;
        c[ImGuiCol_TextDisabled] = ImVec4(0.580f, 0.580f, 0.580f, 1.00f);
        c[ImGuiCol_FrameBg] = ImVec4(0.140f, 0.140f, 0.140f, 1.00f);
        c[ImGuiCol_FrameBgHovered] = ImVec4(0.180f, 0.180f, 0.180f, 1.00f);
        c[ImGuiCol_FrameBgActive] = ImVec4(0.220f, 0.220f, 0.220f, 1.00f);
        c[ImGuiCol_Button] = ImVec4(0.160f, 0.160f, 0.160f, 1.00f);
        c[ImGuiCol_ButtonHovered] = ImVec4(0.160f, 0.160f, 0.160f, 1.00f); // no hover tint
        // [LOCAL] The held colour used to BE the accent (#FF7501), so a click
        // flashed the full orange for as long as the mouse stayed down (owner,
        // 2026-09-17: "按钮点了都会闪一下才是橙色").  Worse, held and SELECTED
        // looked identical, so a page/language tab read as "already selected"
        // before the button was even released.  One grey step above the resting
        // colour keeps the press visible while leaving the accent exactly one
        // meaning in this panel: selected.
        c[ImGuiCol_ButtonActive] = ImVec4(0.240f, 0.240f, 0.240f, 1.00f);
        c[ImGuiCol_CheckMark] = kAccent;
        c[ImGuiCol_SliderGrab] = kAccent;
        c[ImGuiCol_SliderGrabActive] = ImVec4(1.000f, 0.560f, 0.100f, 1.00f);
        c[ImGuiCol_Separator] = ImVec4(0.620f, 0.280f, 0.010f, 0.65f);
        c[ImGuiCol_Header] = ImVec4(0.160f, 0.160f, 0.160f, 1.00f);
        c[ImGuiCol_HeaderHovered] = ImVec4(0.620f, 0.280f, 0.010f, 1.00f);
        c[ImGuiCol_ScrollbarBg] = ImVec4(0.060f, 0.060f, 0.060f, 0.60f);
        c[ImGuiCol_ScrollbarGrab] = ImVec4(0.550f, 0.250f, 0.010f, 1.00f);
        c[ImGuiCol_TitleBg] = ImVec4(0.080f, 0.080f, 0.080f, 1.00f);
        c[ImGuiCol_TitleBgActive] = ImVec4(0.160f, 0.100f, 0.050f, 1.00f); // warm tint
    }

    std::mutex g_overlayMutex;
    ID3D11Device* g_device = nullptr;
    ID3D11DeviceContext* g_context = nullptr;
    IDXGISwapChain* g_swapChain = nullptr;
    HWND g_hwnd = nullptr;

    // [LOCAL] Shader resource view for the bottom-right GitHub mark.  Built once
    // from the embedded alpha mask (GithubMark.h) in InitImGuiLocked(), which is
    // the first point where the device is known; owned for the process lifetime
    // exactly like g_device above.  Null means "icon unavailable" and the draw
    // path simply skips it.
    ID3D11ShaderResourceView* g_linkIconSrv = nullptr;

    // [LOCAL] Cross-thread flags: written from the game thread (capture /
    // main-menu notify), from the WndProc thread (hotkey) and read every
    // frame by the render thread - atomics keep that honest.
    std::atomic<bool> g_imguiReady{ false };
    // [LOCAL] Full ImGui frames to run after init even with the menu closed
    // (cooks the CJK font atlas off the user's first hotkey press).  Only
    // touched by the render thread.
    int g_warmupFrames = 0;
    std::atomic<bool> g_menuOpen{ false };
    std::atomic<bool> g_mainMenuReached{ false }; // Insert is ignored until the main menu is up
    // [LOCAL] Deferred auto-open.  The gate opens the moment the main-menu
    // labels are rendered, which is a beat before the front-end has actually
    // settled - a menu that is already sitting on screen when the player
    // arrives reads as "it was waiting for me".  Opening kAutoOpenDelayMs later
    // makes it feel like a reply instead.  Passed by NotifyMainMenuReached,
    // consumed by HookPresent; 0 = nothing pending, and a press of the hotkey
    // cancels it (see OverlayWndProc).
    constexpr unsigned long long kAutoOpenDelayMs = 1500;
    std::atomic<unsigned long long> g_autoOpenDueMs{ 0 };
    // [LOCAL] "hotkey ignored" is logged once per session (see OverlayWndProc);
    // only the window thread touches this.
    bool g_hotkeyIgnoredLogged = false;
    // [LOCAL] When the user dismissed the "press ENTER" title screen (GetTickCount64
    // timestamp, 0 = not yet).  See OverlayWndProc - this is the gate signal.
    std::atomic<unsigned long long> g_titleDismissedMs{ 0 };
    bool g_wndProcHooked = false;
    WNDPROC g_origWndProc = nullptr;
    void* g_origPresent = nullptr;
    void** g_patchedVtableSlot = nullptr;
    void* g_origFactoryCreateSwapChain = nullptr;
    void** g_patchedFactorySlot = nullptr;
    void* g_origFactoryCreateSwapChainForHwnd = nullptr;
    void** g_patchedFactoryForHwndSlot = nullptr;

    // [LOCAL] imgui.ini target.  io.IniFilename keeps the pointer we give it,
    // so the buffer must be static and outlive ImGui.  Absolute path on
    // purpose: a relative one silently depends on the process working dir
    // (which is why a stray imgui.ini once appeared in the game root).
    char g_imguiIniPath[MAX_PATH] = {};

    // [LOCAL] Menu edit buffers.  Refreshed from the config every time the
    // menu transitions from closed to open, edited locally, then committed by
    // each row's own Save button (checkboxes apply instantly instead).
    char g_playerNameBuf[16] = {};
    char g_passwordBuf[1024] = {};
    // [LOCAL] Atomic, per the rule stated for the flags at the top of this
    // file: the WndProc thread clears g_editBufsLoaded when the hotkey opens
    // the menu (see OverlayWndProc), while the render thread reads it and does
    // the (re)load in DrawMenu.  g_playerNameAutofill is only touched by the
    // render thread today, but it is read in the same per-frame block, so
    // keeping the pair consistent is cheaper than remembering which one is safe.
    std::atomic<bool> g_editBufsLoaded{ false };
    // [LOCAL] True while the name box is still waiting for the ENGINE to come
    // up with a name (see the poll in DrawMenu).  Only ever affects the name
    // row, and only while its buffer is empty and untouched by the user.
    std::atomic<bool> g_playerNameAutofill{ false };
    // [LOCAL] A g_sessionStart timestamp used to live here, feeding a "session
    // uptime" readout that was removed from the menu; nothing reads it any more
    // (and it never did after that readout was dropped).

    // IDXGISwapChain vtable: IUnknown(0-2), IDXGIObject(3-5),
    // IDXGIDeviceSubObject(6), GetDevice(7), Present(8).
    constexpr int kPresentVtableIndex = 8;
    // IDXGIFactory vtable: ... GetDevice(7), EnumAdapters(8),
    // GetWindowAssociation(9), CreateSwapChain(10), CreateSwapChainForHwnd(11).
    constexpr int kCreateSwapChainVtableIndex = 10;
    constexpr int kCreateSwapChainForHwndVtableIndex = 11;

    // [LOCAL] Overlay diagnostics: the input chain has too many silent failure
    // points (wrong swap chain path, wrong window), so every milestone lands
    // in its own log the user can read after the fact.
    void overlay_log(const char* msg)
    {
        // [LOCAL] The overlay shares the patch's single log (t7patch_log.h),
        // tagged "overlay" - it used to have a file of its own, which also had
        // no size cap at all.
        t7log::Append("overlay", msg);
    }

    LRESULT CALLBACK OverlayWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam);

// [LOCAL] 定义在文件下方（HookWndProcLocked 旁边），但 Init 里要调用 ⇒ 需要前置声明
// （漏了它就是 error C3861 找不到标识符，2026-09-19 实测踩过）。
void HookCursorApisLocked();
    HRESULT STDMETHODCALLTYPE HookPresent(IDXGISwapChain* self, UINT syncInterval, UINT flags);

    // -----------------------------------------------------------------
    //  Menu drawing (card layout: one bordered card per section, drawn over
    //  the key-art background; title bar kept, no collapsibles)
    // -----------------------------------------------------------------

    // Card helpers: grouped blocks whose background/border come from the
    // theme; section titles use the accent colour.
    void BeginCard(const char* title)
    {
        ImGui::BeginChild(title, ImVec2(0.0f, 0.0f),
            ImGuiChildFlags_AutoResizeY | ImGuiChildFlags_Borders);
        ImGui::PushStyleColor(ImGuiCol_Text, kAccent);
        ImGui::TextUnformatted(title);
        ImGui::PopStyleColor();
        ImGui::Separator();
    }

    void EndCard()
    {
        ImGui::EndChild();
        ImGui::Spacing();
    }

    // Same card with an EXPLICIT height (no auto-resize): page 2 uses it so its
    // single card fills the page instead of floating in an otherwise empty
    // panel.  Content shorter than the height just leaves breathing room.
    void BeginCardSized(const char* title, float height)
    {
        ImGui::BeginChild(title, ImVec2(0.0f, height), ImGuiChildFlags_Borders);
        ImGui::PushStyleColor(ImGuiCol_Text, kAccent);
        ImGui::TextUnformatted(title);
        ImGui::PopStyleColor();
        ImGui::Separator();
    }

    // -----------------------------------------------------------------
    //  Localisation: one string table per language.  menu_lang picks the
    //  table; switching is live (no restart, no rebuild).
    // -----------------------------------------------------------------
    struct MenuText
    {
        const char* settings;
        const char* toggles;
        const char* status;
        const char* config;
        const char* playerName;
        const char* roomPassword;
        const char* save;
        const char* friendsOnly;
        const char* blockShader;
        const char* uptimeFmt;
        // [LOCAL] Reserved status wording for the 46 file's DISK state (kept
        // with the other reserved strings; nothing renders it yet).  If a
        // caller ever appears, the argument is a word localized for the current
        // UI language, and the value comes from
        // t7patch_d3dcompiler46_file_state(): 0 = file in place, 1 = isolated
        // as .bak, 2 = missing, 3 = both copies.  Pass the DISK state, never
        // the switch value: the disk read exists precisely to expose a rename
        // that failed.  Localized words to use -
        //   zh: 未隔离（文件在原位）/ 已隔离（已改名 .bak）/ 文件不存在 / 两份并存（异常）
        //   en: not isolated / isolated (renamed to .bak) / file not found / both copies present
        const char* blockStateFmt;
        const char* language;
        const char* hotkey;
        const char* pressAnyKey;
        const char* hint;
        const char* blockShaderTip;
        const char* friendsOnlyTip;
        const char* autoOpen;
        const char* autoOpenTip;
        // [LOCAL] On-demand dictionary update - a button in the toggles card.
        // The patch never downloads by itself: this is the overlay's only
        // network entry point and it takes a deliberate click.
        const char* dictUpdate;
        const char* dictUpdateTip;
        const char* dictUpdating;
        const char* dictUpdatedFmt;
        const char* dictFailedFmt;
        const char* dictUpToDate;
        // [LOCAL] Optional Vulkan backend (DXVK) - download + verify.  Same
        // click-to-fetch discipline as the dictionary update above; nothing
        // is fetched until the player presses the button.
        const char* dxvkDownload;
        const char* dxvkDownloadTip;
        const char* dxvkDownloading;
        const char* dxvkOk;
        const char* dxvkFailedFmt;
        const char* dxvkUpToDate;
        // [LOCAL] The enable toggle plus its four state lines.  The toggle is
        // disabled until a verified pair exists, and flipping it MOVES the two
        // files between T7Patch\dxvk and the game folder - the pair's location
        // is the switch, not a config value.
        // [LOCAL] The enable toggle.  Grey until a verified pair exists; the
        // checkbox IS the switch - checked once the pair sits in the game
        // folder.  No extra state text: a row that reads like the translation
        // row needs no narration.
        const char* dxvkToggle;
        // [LOCAL] The three settings the DXVK page exposes - deliberately the
        // whole list.  Everything else stays at the documented default.
        const char* dxvkHud;
        const char* dxvkMaxFps;
        const char* dxvkTear;
        const char* dxvkTearAuto;
        const char* dxvkTearOn;
        const char* dxvkTearOff;
        const char* dxvkSettingsNote;
        // [LOCAL] Page tabs + the page-2 card title.  The panel is a fixed
        // 395x440 with no scrollbar and the first page was full, so new
        // functionality goes onto a second page instead of squeezing this one.
        const char* pageGeneral;
        const char* pageMore;
        const char* pageDxvk;
        const char* moreCard;
        const char* modTranslate;
        const char* modTranslateTip;
        // [LOCAL] Sub-switches of the row above: "leave this scene untranslated".
        // Worded the same way on purpose, so a third scene would slot in without
        // changing the shape.  Their defaults differ by design - a Multiplayer
        // match is untranslated out of the box, Zombies is translated.  They are
        // exceptions to the switch above, never a second way to switch
        // translation on; see translate::SetSceneBlocked.
        const char* pvpSkip;
        const char* pvpSkipTip;
        const char* zmSkip;
        const char* zmSkipTip;
        const char* about;
        // [LOCAL] Graphics-page tooltips (2026-09-17, user request).  Appended at
        // the TAIL on purpose: both tables below are positional, so appending
        // cannot silently shift an existing pair - and check_menu_text.py only
        // verifies arity, never order.
        const char* dxvkHudTip;
        const char* dxvkTearTip;
        // [LOCAL] What the backend IS (2026-09-17, user request: "再给 DXVK 增加
        // 一个说明").  Hangs off the enable toggle - the one control whose name
        // ("Enable DXVK") assumes the player already knows what DXVK is.
        const char* dxvkToggleTip;
        // [LOCAL] One label per dxvk.hud element (2026-09-17, user request:
        // "我只想显示某一个？给一个勾选显示哪些").  Tailed like the tooltips
        // above, for the same positional-table reason; this order is also the
        // order of the ticks and of the names written into dxvk.hud.
        const char* dxvkHudFps;
        const char* dxvkHudFrametimes;
        const char* dxvkHudGpuload;
        const char* dxvkHudMemory;
        const char* dxvkHudCompiler;
        const char* dxvkHudDevinfo;
    };

    constexpr MenuText kTextZh = {
        "设置", "开关", "状态", "配置",
        "玩家昵称", "房间密码", "保存",
        "仅好友可加入", "屏蔽旧着色器编译器",
        "运行时长：%02u:%02u:%02u",
        "旧着色器编译器状态：%s",
        "语言", "呼出按键", "请按下新按键…（ESC 取消）",
        "按 %s 呼出/隐藏",
        "遇到卡顿时可尝试打开：隔离游戏目录里的旧版着色器编译器。\n"
        "重启游戏后生效。",
        "仅好友可以邀请/加入你。\n"
        "立即生效，重启后保持。",
        "自动打开窗口",
        "进入主菜单后自动打开本窗口。\n"
        "下次启动生效。",
        "更新词库",
        "从网络下载最新的汉化词库，替换本机的词库文件。\n"
        "下载后约 2 秒内生效，无需重启游戏。",
        "下载中…",
        "已更新 %u 条",
        "更新失败：%s",
        "已是最新版",
        "获取DXVK",
        "约13MB，改用Vulkan渲染，也许能提升流畅度（因机而异）。\n"
        "重启生效。",
        "下载中…",
        "已下载",
        "下载失败：%s",
        "已是最新版",
        "启用 DXVK",
        "HUD 元素", "帧率上限", "撕裂控制", "自动", "无撕裂", "低延迟",
        "设置重启游戏后生效。",
        "常规", "更多", "图形", "工具",
        "mod 汉化",
        "开启自动模组汉化（游戏必须为中文）",
        "关闭多人对局翻译",
        "默认开启：多人对局保持英文。\n"
        "建立对局后生效（房间、大厅也算在内）；主菜单不受影响。\n"
        "（需先开启 mod 汉化）",
        "关闭僵尸对局翻译",
        "默认关闭：僵尸对局照常翻译。\n"
        "打开后僵尸对局也不翻译；战役不受影响。\n"
        "（需先开启 mod 汉化）",
        "关于",
        // 图形页提示（2026-09-17 用户要求）：HUD 说明显示什么；撕裂控制逐项说明效果。
        // 同日二次修订：HUD 改成逐项勾选后，这句改成"勾哪些就显示哪些"。
        "勾选要在画面上叠加显示的项。\n"
        "全部不勾选即关闭 HUD；重启游戏后生效。",
        "自动：交由 DXVK 判断。\n"
        "无撕裂：关垂直同步时改用 mailbox 呈现（部分系统不支持）。\n"
        "低延迟：开垂直同步时改用 relaxed fifo，可能撕裂、但卡顿更少。\n"
        "（这不是垂直同步开关 —— 垂直同步由游戏内设置控制。）",
        // 启用 DXVK 的说明（09-17 用户要求）：它是什么 + 什么时候值得试 + 代价。
        "把游戏的 D3D11 调用转译成 Vulkan 渲染。\n"
        "适合原本就卡顿的游戏：它在后台线程编译着色器，减少「边玩边编」引起的一顿一顿。\n"
        "需要显卡已装 Vulkan 驱动；改动重启游戏后生效。",
        // HUD 逐项（09-17 用户要求）：每一项都短，两行刚好放得下六个。
        "帧率", "帧时间", "GPU 负载", "显存", "着色器", "设备"
    };
    constexpr MenuText kTextEn = {
        "SETTINGS", "TOGGLES", "STATUS", "CONFIG",
        "Player name", "Room password", "Save",
        "Friends only", "Block legacy shader compiler",
        "Session uptime: %02u:%02u:%02u",
        "Legacy shader compiler status: %s",
        "Language", "Hotkey", "Press any key... (ESC cancels)",
        "Press %s to toggle",
        "Try this if you see stutter - it isolates the legacy shader compiler\n"
        "that ships in the game folder.\n"
        "Takes effect after a restart.",
        "Only friends can invite/join you.\n"
        "Applies instantly and is kept across restarts.",
        "Auto-open in main menu",
        "Opens this window automatically once the main menu is up.\n"
        "Takes effect on the next launch.",
        "Update dictionary",
        "Downloads the latest translation dictionary and replaces the local\n"
        "file.  Active within about two seconds - no restart needed.",
        "Downloading...",
        "Updated %u entries",
        "Update failed: %s",
        "Already up to date",
        "Get DXVK",
        "~13MB, switches to Vulkan rendering - may improve smoothness (varies by machine).\n"
        "Restart to apply.",
        "Downloading...",
        "Downloaded",
        "Download failed: %s",
        "Already up to date",
        "Enable DXVK",
        "HUD elements", "FPS cap", "Tear control", "Auto", "No tearing", "Low latency",
        "Settings take effect after a restart.",
        "General", "More", "Graphics", "Tools",
        "Mod translations",
        "Enables automatic mod translation (the game must be set to Chinese).",
        "Turn off Multiplayer translation",
        "On by default: Multiplayer is left in English.\n"
        "Applies once a session is established (rooms and lobbies included);\n"
        "the main menu is unaffected.  (Requires mod translation.)",
        "Turn off Zombies translation",
        "Off by default: Zombies is translated normally.  Tick this to leave\n"
        "Zombies untranslated as well.  Campaign is unaffected.\n"
        "(Requires mod translation.)",
        "About",
        "Tick the items to overlay on the screen.\n"
        "Untick everything to turn the HUD off; takes effect after a restart.",
        "Auto: DXVK decides.\n"
        "No tearing: mailbox presentation while Vsync is off (unsupported on some systems).\n"
        "Low latency: relaxed fifo while Vsync is on - may tear, but stutters less.\n"
        "(Not the Vsync switch - Vsync follows the game's own setting.)",
        "Renders the game through Vulkan: its D3D11 calls are translated to Vulkan.\n"
        "Worth trying when the game already stutters - it compiles shaders on worker\n"
        "threads, which cuts the hitches caused by compiling them while you play.\n"
        "Needs a Vulkan driver installed; takes effect after a restart.",
        "FPS", "Frametime", "GPU load", "VRAM", "Shaders", "Device"
    };

    const MenuText* L()
    {
        return t7patch_cfg_menu_lang() ? &kTextZh : &kTextEn;
    }

    // [LOCAL] True while the CONFIG card waits for the user to press the new
    // hotkey (the WndProc swallows the next key).
    std::atomic<bool> g_capturingHotkey{ false };

    // [LOCAL] Virtual-key code to a readable label.  Common keys get names,
    // letters/digits map to themselves, everything else shows as hex.
    const char* VkName(int vk)
    {
        static char buf[16];
        switch (vk)
        {
        case VK_INSERT: return "Insert";
        case VK_DELETE: return "Delete";
        case VK_HOME: return "Home";
        case VK_END: return "End";
        case VK_PRIOR: return "PageUp";
        case VK_NEXT: return "PageDown";
        case VK_TAB: return "Tab";
        case VK_SPACE: return "Space";
        case VK_OEM_3: return "`";
        case VK_OEM_MINUS: return "-";
        case VK_OEM_PLUS: return "=";
        default: break;
        }
        if (vk >= VK_F1 && vk <= VK_F12)
        {
            snprintf(buf, sizeof(buf), "F%d", vk - VK_F1 + 1);
            return buf;
        }
        if ((vk >= '0' && vk <= '9') || (vk >= 'A' && vk <= 'Z'))
        {
            snprintf(buf, sizeof(buf), "%c", (char)vk);
            return buf;
        }
        snprintf(buf, sizeof(buf), "VK 0x%02X", vk);
        return buf;
    }

    // Small selector button (language, page tabs): the ACTIVE one is drawn in
    // accent and STAYS that way.  All three button colours get pinned, because
    // ImGui switches to ButtonHovered/ButtonActive while the cursor is over the
    // button - an accent button that greys out on hover reads as "no longer
    // selected", which is exactly the flicker the user asked to remove.
    //
    // Inactive buttons keep the theme's hover feedback on purpose: that is the
    // "this one is clickable" cue.  The Save button is a plain ImGui::Button
    // elsewhere and is deliberately not affected by any of this.
    bool LangButton(const char* label, bool active)
    {
        if (active)
        {
            ImGui::PushStyleColor(ImGuiCol_Button, kAccent);
            ImGui::PushStyleColor(ImGuiCol_ButtonHovered, kAccent);
            ImGui::PushStyleColor(ImGuiCol_ButtonActive, kAccent);
        }
        const bool clicked = ImGui::Button(label, ImVec2(56.0f, 0.0f));
        if (active)
            ImGui::PopStyleColor(3);
        return clicked;
    }

    // [LOCAL] Solid-fill checkbox: compact box, no tick mark, and the box is
    // filled with the accent colour when ON.  The stock ImGui checkbox always
    // draws a tick, so this one is hand-drawn (InvisibleButton + DrawList).
    bool SolidCheckbox(const char* label, bool* v, float boxSize = 13.0f)
    {
        ImGuiStyle& style = ImGui::GetStyle();
        const ImVec2 labelSize = ImGui::CalcTextSize(label, nullptr, true);
        const ImVec2 pos = ImGui::GetCursorScreenPos();
        const float lineHeight = ImGui::GetTextLineHeight();
        const float totalHeight = (boxSize > lineHeight) ? boxSize : lineHeight;
        // [LOCAL] The label - and with it the box - is drawn at the FRAME
        // PADDING offset instead of at the top of the row.  Button/InputText put
        // their text there, so without this the box and its label sat 4 px above
        // the neighbouring button's text on every row that mixes the two
        // ("启用 DXVK" + "获取DXVK"), which is one half of the owner's
        // "轻微高低差 / 不是中心平行对齐" report (2026-09-17).
        // The ROW keeps its old height on purpose: ImGui::Checkbox() uses a full
        // frame height plus that same offset, but the panel is a fixed 395x440
        // with no scrollbar, and +8 px on every checkbox row pushes page 1's
        // last card past the bottom.
        const float labelY = pos.y + style.FramePadding.y;
        const float boxY = labelY + (lineHeight - boxSize) * 0.5f;

        ImGui::InvisibleButton(label,
            ImVec2(boxSize + style.ItemInnerSpacing.x + labelSize.x, totalHeight));
        const bool clicked = ImGui::IsItemClicked();
        if (clicked)
            *v = !*v;

        ImDrawList* dl = ImGui::GetWindowDrawList();
        // [LOCAL] Hand-drawn colours do not pick up style.Alpha on their own the
        // way Text() does, so a BeginDisabled()'d box would stay fully saturated
        // and keep looking clickable.  Fold the alpha in: the two scene
        // sub-switches on the Tools page are greyed out while mod 汉化 is off,
        // and that has to be visible on the box, not only on its label.
        const int boxAlpha = (int)(style.Alpha * 255.0f + 0.5f);
        const ImU32 fill = IM_COL32(255, 117, 1, boxAlpha);   // #FF7501
        const ImU32 outline = IM_COL32(150, 90, 20, boxAlpha);
        const ImVec2 p0(pos.x, boxY);
        const ImVec2 p1(pos.x + boxSize, boxY + boxSize);
        // [LOCAL] The on-state is an outline PLUS an inset core, so a sliver of
        // dark background stays visible between them - a full orange blob read
        // as "no checkbox" at a glance.  No hover tint (the user wants buttons
        // and boxes to stay visually quiet until clicked).
        const float inset = 2.5f;

        if (*v)
        {
            dl->AddRect(p0, p1, fill, 2.0f, 0, 1.4f);
            dl->AddRectFilled(ImVec2(p0.x + inset, p0.y + inset),
                ImVec2(p1.x - inset, p1.y - inset), fill, 1.0f);
        }
        else
        {
            dl->AddRect(p0, p1, outline, 2.0f, 0, 1.2f);
        }

        dl->AddText(ImVec2(p1.x + style.ItemInnerSpacing.x, labelY),
            ImGui::GetColorU32(ImGuiCol_Text), label);

        return clicked;
    }

    // One dxvk.hud element tick.  The bitmask in Conf is the only source of
    // truth, so the helper owns both the "is this bit on" read and the ConfSet
    // write; the call sites are one line each and normally follow the previous
    // item on the same line (that is what sameLine is for).  The first tick of
    // a NEW row passes sameLine = false - the ticks wrap onto a second row and
    // without this the helper would glue it back onto the first one, which is
    // exactly how the six ticks ended up running off the panel edge.
    void HudTick(const char* label, unsigned bit, dxvk_download::Conf& conf,
        bool sameLine = true)
    {
        if (sameLine)
            ImGui::SameLine();
        bool on = (conf.hud & bit) != 0;
        if (SolidCheckbox(label, &on))
        {
            conf.hud = on ? (conf.hud | bit) : (conf.hud & ~bit);
            dxvk_download::ConfSet(conf);
        }
    }

    // [LOCAL] Drawn guide for a block of indented sub-options: a vertical line
    // inside the indent gap plus one elbow per sub-item, so "these belong to the
    // switch above" is SHOWN and not merely implied by the indent (owner,
    // 2026-09-17: "子选项设置跟主设置树状图的分支线 UI 效果…看着更有归类感").
    // The indent stays exactly as it was - the line only explains it, so no row
    // budget is spent.
    //
    // Usage, inside the BeginDisabled + Indent pair:
    //     SubTree tree;
    //     ... sub-item 1 ...            tree.Row();   // after its LAST widget
    //     ... extra rows of item 1 ...               // no Row() - same item
    //     ... sub-item 2 ...            tree.Row();
    //     tree.Draw();
    //
    // It draws AFTER the items on purpose: the guide lives in the indent gap and
    // never crosses a widget, so no draw-list channel juggling is needed.
    struct SubTree
    {
        float lineX = 0.0f;    // the vertical line
        float elbowX = 0.0f;   // where the elbows stop, just short of the items
        float topY = 0.0f;     // starts at the parent row's bottom edge
        float ys[8] = {};      // elbow centres, in draw order
        int count = 0;

        SubTree()
        {
            // Indent() has already moved the cursor, so this is the sub-items'
            // left edge (parent + 12); the line and the elbows live inside that
            // gap.  The top is one ItemSpacing above the first row, i.e. the
            // parent row's bottom edge - the guide starts right under the switch
            // it belongs to, never over it.
            const ImVec2 p = ImGui::GetCursorScreenPos();
            lineX = p.x - 10.0f;
            elbowX = p.x - 4.0f;
            topY = p.y - ImGui::GetStyle().ItemSpacing.y;
        }

        // Once per sub-item, after its last widget.
        void Row()
        {
            if (count < (int)(sizeof(ys) / sizeof(ys[0])))
                ys[count++] = (ImGui::GetItemRectMin().y
                    + ImGui::GetItemRectMax().y) * 0.5f;
        }

        void Draw() const
        {
            if (count == 0)
                return;
            // Hand-drawn colours do not pick up style.Alpha by themselves - the
            // same reason SolidCheckbox folds it in - and a greyed block (DXVK
            // off, mod 汉化 off) must not keep a full-strength guide.  The hue is
            // the panel's own accent at low alpha: visible, never loud.
            const int a = (int)(ImGui::GetStyle().Alpha * 100.0f + 0.5f);
            const ImU32 col = IM_COL32(255, 117, 1, a);
            ImDrawList* dl = ImGui::GetWindowDrawList();
            dl->AddLine(ImVec2(lineX, topY),
                ImVec2(lineX, ys[count - 1]), col, 1.0f);
            for (int i = 0; i < count; ++i)
                dl->AddLine(ImVec2(lineX, ys[i]), ImVec2(elbowX, ys[i]), col, 1.0f);
        }
    };

    // [LOCAL] A step button that DRAWS its sign instead of using the font's
    // glyph.  ImGui centres the whole text LINE BOX in a button, and the font's
    // minus/plus are drawn around the baseline inside that box - which reserves
    // descent space below it - so in a 20 px button the signs landed 3.5 px low
    // and 1-2 px right (measured on the owner's screenshot, 2026-09-17:
    // "加减符号怎么靠右下了").  Two strokes we draw ourselves sit exactly on the
    // centre, and they match each other's weight - the font's thin hyphen and
    // heavier plus do not.
    bool StepButton(const char* id, float side, bool plus)
    {
        const bool clicked = ImGui::Button(id, ImVec2(side, side));
        const ImVec2 a = ImGui::GetItemRectMin();
        const ImVec2 b = ImGui::GetItemRectMax();
        const ImVec2 c((a.x + b.x) * 0.5f, (a.y + b.y) * 0.5f);
        const float arm = 3.5f;
        const ImU32 col = ImGui::GetColorU32(ImGuiCol_Text);
        ImDrawList* dl = ImGui::GetWindowDrawList();
        dl->AddLine(ImVec2(c.x - arm, c.y), ImVec2(c.x + arm, c.y), col, 1.5f);
        if (plus)
            dl->AddLine(ImVec2(c.x, c.y - arm), ImVec2(c.x, c.y + arm), col, 1.5f);
        return clicked;
    }

    void DrawMenu()
    {
        // (Re)load the text edit buffers once per menu-open (the hotkey
        // handler clears the flag), so in-game edits and manual conf edits
        // never fight each other.  The friends-only checkbox reads/writes the
        // config directly - no buffer involved.
        if (!g_editBufsLoaded)
        {
            // Player name: the conf value wins; when the conf has none, the
            // game's CURRENT name is shown instead, so the box is never blank
            // and the user sees what the game is actually using.  That fallback
            // is NOT resolved here though - see the poll below.
            // [LOCAL] Both getters copy under Protection.cpp's config lock, so
            // by the time we look at the value it is already a private snapshot
            // - the old versions handed back a pointer into the shared config
            // and the copy below happened after the lock was released.
            char confName[16];
            t7patch_cfg_playername(confName, sizeof(confName));
            if (confName[0] != '\0')
            {
                strncpy_s(g_playerNameBuf, sizeof(g_playerNameBuf), confName, _TRUNCATE);
                g_playerNameAutofill = false;
            }
            else
            {
                g_playerNameBuf[0] = '\0';
                g_playerNameAutofill = true;
            }

            t7patch_cfg_network_password(g_passwordBuf, sizeof(g_passwordBuf));
            g_editBufsLoaded = true;
        }

        // [LOCAL] Poll the engine's own name until it produces one.
        //
        // Why this exists: the engine writes its player name into pNameBuffer
        // only after the online profile has finished loading, while the menu is
        // auto-opened the very instant the main menu shows up.  Those two raced
        // on 2026-09-15 - the one-shot read above caught an empty buffer,
        // latched it, and the box stayed blank for the WHOLE session (closing
        // and reopening the menu was the only cure).  It read as a random
        // glitch because the profile load beating the menu is the common case,
        // not a guaranteed one.
        //
        // So keep asking, every frame the menu is open, until it answers.  It
        // stops the moment the user types (their input is never overwritten) or
        // a name arrives; a non-empty conf name never reaches this path at all.
        // Cost: one strncpy_s of at most 15 bytes, and only while unresolved.
        if (g_playerNameAutofill)
        {
            const char* gameName = t7patch_game_playername();
            if (gameName && gameName[0] != '\0')
            {
                strncpy_s(g_playerNameBuf, sizeof(g_playerNameBuf), gameName, _TRUNCATE);
                g_playerNameAutofill = false;
            }
        }

        // Which page is showing.  Function-level static on purpose: only the UI
        // thread ever touches it (it does not even cross threads, unlike
        // g_capturingHotkey which the message hook also sees).
        static int g_activePage = 0;

        // [LOCAL] Fixed layout: the panel is laid out for exactly this size.
        // ImGuiCond_Always pins it every frame (imgui.ini cannot override),
        // the constraints lock out edges-dragging, and the NoScrollbar flags
        // keep the chrome clean.  Width was trimmed ~14% (fields do not need
        // that much room); height has slack so nothing gets clipped.
        // [LOCAL] 半透明遮罩（用户 2026-09-19 反馈："还没做打开时的半透明遮罩"）：
        // 菜单打开时把整个画面压暗，把面板和游戏画面分开。用**背景绘制列表**画 —— 它在 NewFrame 之后、
        // Render 之前可用，属于最底层，不会挤占面板布局（放进窗口里会多一个子区域）。
        ImGui::GetBackgroundDrawList()->AddRectFilled(
            ImVec2(0.0f, 0.0f), ImGui::GetIO().DisplaySize, IM_COL32(0, 0, 0, 140));

        const ImVec2 kPanelSize(395.0f, 440.0f);
        ImGui::SetNextWindowSize(kPanelSize, ImGuiCond_Always);
        ImGui::SetNextWindowSizeConstraints(kPanelSize, kPanelSize);
        bool menuOpen = g_menuOpen.load();
        const bool visible = ImGui::Begin("T7Patch " ZBR_VERSION, &menuOpen,
            ImGuiWindowFlags_NoCollapse | ImGuiWindowFlags_NoResize |
            ImGuiWindowFlags_NoScrollbar | ImGuiWindowFlags_NoScrollWithMouse);
        if (menuOpen != g_menuOpen.load())
            g_menuOpen = menuOpen; // the title-bar close button was clicked
        if (!visible)
        {
            ImGui::End();
            return;
        }

        // [LOCAL] Page tabs.  The panel was full, so functionality beyond the
        // basics lives on a second page.  LangButton doubles as the tab control:
        // small, and the active one draws in accent - exactly what a tab needs.
        {
            if (LangButton(L()->pageGeneral, g_activePage == 0))
                g_activePage = 0;
            ImGui::SameLine();
            if (LangButton(L()->pageDxvk, g_activePage == 1))
                g_activePage = 1;
            ImGui::SameLine();
            if (LangButton(L()->pageMore, g_activePage == 2))
                g_activePage = 2;
        }

        if (g_activePage == 1)
        {
            // ---- page 2: DXVK - download, enable, configure ----------------
            // [LOCAL] The whole feature on one page: the toggle, the fetch
            // button and the three settings, on the card-fills-page pattern
            // the tools page established.  It moved here from the tools page
            // on purpose - a rendering backend is not a translation feature,
            // and the settings need the room.
            const float dxFill = ImGui::GetContentRegionAvail().y;
            BeginCardSized(L()->pageDxvk, dxFill);
            {
                const dxvk_download::Status dx = dxvk_download::Get();
                const bool dxDownloading = dx.state == dxvk_download::State::Running;
                const dxvk_download::InstallState inst = dxvk_download::Query();
                const bool dxAvailable = inst != dxvk_download::InstallState::Absent;
                // [LOCAL] "Enabled" means the pair is in the game folder, and
                // that is equally true of Mixed (the pair in BOTH places - a
                // machine an older build left behind, since the download no
                // longer produces it).  Drawing Mixed as unticked told the
                // player DXVK was off while it in fact loaded at every launch.
                bool dxOn = inst == dxvk_download::InstallState::Enabled
                    || inst == dxvk_download::InstallState::Mixed;

                ImGui::BeginDisabled(!dxAvailable);
                if (SolidCheckbox(L()->dxvkToggle, &dxOn) && dxAvailable)
                {
                    if (dxOn && inst == dxvk_download::InstallState::Parked)
                        dxvk_download::Enable();
                    else if (!dxOn)
                        dxvk_download::Disable();
                }
                ImGui::EndDisabled();
                // [LOCAL] What the backend actually IS - "启用 DXVK" assumes the
                // player already knows (2026-09-17, user request).  Reads while
                // greyed too, which is exactly when "should I get this at all?"
                // is the live question: the style carries AllowWhenDisabled, and
                // EndDisabled() only pops the item flag, so the preceding item is
                // still the checkbox.
                ImGui::SetItemTooltip("%s", L()->dxvkToggleTip);

                ImGui::SameLine();
                char dxBtn[96]{};
                snprintf(dxBtn, sizeof(dxBtn), "%s##dxvkdownload", L()->dxvkDownload);
                if (ImGui::Button(dxBtn, ImVec2(0.0f, 0.0f)) && !dxDownloading)
                    dxvk_download::Start();
                ImGui::SetItemTooltip("%s", L()->dxvkDownloadTip);

                if (dxDownloading)
                {
                    ImGui::SameLine();
                    ImGui::Text("%s %u KiB", L()->dxvkDownloading,
                        static_cast<unsigned>(dx.downloadedKiB));
                }
                else if (dx.state == dxvk_download::State::Ok)
                {
                    ImGui::SameLine();
                    ImGui::TextUnformatted(L()->dxvkOk);
                }
                else if (dx.state == dxvk_download::State::Failed)
                {
                    ImGui::SameLine();
                    ImGui::Text(L()->dxvkFailedFmt, dx.message);
                }
                else if (dx.state == dxvk_download::State::UpToDate)
                {
                    ImGui::SameLine();
                    ImGui::TextUnformatted(L()->dxvkUpToDate);
                }

                // ---- the three settings -----------------------------------
                // Same disabled-until-downloaded rule as the toggle above: a
                // conf for a backend that is not on disk is dead weight.  All
                // three rewrite dxvk.conf and take effect on the next launch -
                // DXVK parses the file once, at device creation.
                //
                // [LOCAL] They are ALSO disabled - and indented - while the DXVK
                // switch above is off.  Owner's calls, 2026-09-17: "当 DXVK 被
                // 关闭的时候那些子选项应该被禁用" and "这个布局没有体现是他的子
                // 选项".  Deliberately the same two idioms the scene sub-switches
                // on the first page use (BeginDisabled + Indent(12)), so the two
                // places read alike.  Indent only narrows the row, never adds
                // one: the panel is a fixed 395x440 with no scrollbar.
                dxvk_download::Conf dc = dxvk_download::ConfGet();

                const bool dxSettingsOn = dxAvailable && dxOn;
                ImGui::BeginDisabled(!dxSettingsOn);
                ImGui::Indent(12.0f);
                // The guide that ties every row below to the switch above.
                SubTree tree;

                // [LOCAL] The HUD used to be one on/off checkbox that always
                // wrote the same fps,frametimes,gpuload trio.  It is one tick
                // per element now (owner, 2026-09-17: "我只想显示某一个？给一个
                // 勾选显示哪些"), and "nothing ticked" IS "no dxvk.hud line" -
                // so there is no master switch that could disagree with the
                // ticks.  Six ticks, two rows: the second row is indented under
                // the FIRST TICK (not under the label) so the block reads as one.
                ImGui::AlignTextToFramePadding();
                ImGui::TextUnformatted(L()->dxvkHud);
                // Readable while greyed on purpose: the style carries
                // ImGuiHoveredFlags_AllowWhenDisabled, which is exactly the state
                // where "what does this show?" needs an answer.
                ImGui::SetItemTooltip("%s", L()->dxvkHudTip);
                HudTick(L()->dxvkHudFps, dxvk_download::HUD_FPS, dc);
                HudTick(L()->dxvkHudFrametimes, dxvk_download::HUD_FRAMETIMES, dc);
                HudTick(L()->dxvkHudGpuload, dxvk_download::HUD_GPULOAD, dc);
                tree.Row();   // the HUD item; the tick row under it is its own

                const float hudTickIndent = ImGui::CalcTextSize(L()->dxvkHud).x
                    + ImGui::GetStyle().ItemSpacing.x;
                ImGui::Indent(hudTickIndent);
                // Starts the line: the three ticks would otherwise wrap right
                // back onto the row above and run off the panel (owner's
                // screenshot, 2026-09-17).
                HudTick(L()->dxvkHudMemory, dxvk_download::HUD_MEMORY, dc, false);
                HudTick(L()->dxvkHudCompiler, dxvk_download::HUD_COMPILER, dc);
                HudTick(L()->dxvkHudDevinfo, dxvk_download::HUD_DEVINFO, dc);
                ImGui::Unindent(hudTickIndent);

                // Own row since 2026-09-17: it used to share its line with the
                // HUD switch, which is two rows of ticks now.
                const char* tearWord = (dc.tearFree == 1) ? L()->dxvkTearOn
                    : (dc.tearFree == 2) ? L()->dxvkTearOff : L()->dxvkTearAuto;
                char tearBtn[96]{};
                snprintf(tearBtn, sizeof(tearBtn), "%s: %s##dxvktear",
                    L()->dxvkTear, tearWord);
                if (ImGui::Button(tearBtn, ImVec2(0.0f, 0.0f)))
                {
                    dc.tearFree = (dc.tearFree + 1) % 3;
                    dxvk_download::ConfSet(dc);
                }
                // Spells out all three values, because the label alone cannot
                // (DXVK's own doc ties each value to the Vsync state).
                ImGui::SetItemTooltip("%s", L()->dxvkTearTip);
                tree.Row();   // the tear-control row

                // [LOCAL] Row alignment (owner's report, 2026-09-17: "很多布局文本
                // 和组件都有轻微高低差，不是中心平行对齐").  ImGui aligns same-line
                // items to the TOP of the line, so anything that is not a full
                // frame height - and any bare Text() - lands a few pixels high.
                // That is the whole of the "slight height difference" he saw.
                // Two consequences on this row:
                //   * the label is the FIRST item on the line, so it needs
                //     AlignTextToFramePadding() by hand - exactly the call the
                //     settings table below makes for its column labels.  A Text()
                //     that follows a frame on the same line inherits the offset
                //     through SameLine() and must NOT be given a second one.
                //   * the +/- pair is a SQUARE of its own (frame height - 6) and
                //     is dropped by half the height difference to sit centred on
                //     the row.  Full frame height made two tall pills (owner,
                //     2026-09-17: "这个加减按钮不美观"), and letting ImGui do the
                //     centring does not work either - same-line items are top
                //     aligned.  The drop is derived, and cannot grow the row:
                //     3 + 20 < 26.  They replace the integer widget's own step
                //     buttons, which read as two empty boxes beside a 120 px
                //     field ("加减按钮弄小点，太大了很空").
                int prevFps = dc.maxFps;
                ImGui::AlignTextToFramePadding();
                ImGui::TextUnformatted(L()->dxvkMaxFps);
                ImGui::SameLine();
                ImGui::SetNextItemWidth(90.0f);
                ImGui::InputInt("##dxvkmaxfps", &dc.maxFps, 0, 0);
                if (dc.maxFps < 0)
                    dc.maxFps = 0;
                if (dc.maxFps > 1000)
                    dc.maxFps = 1000;
                if (ImGui::IsItemDeactivatedAfterEdit() && dc.maxFps != prevFps)
                    dxvk_download::ConfSet(dc);

                const float fpsRowHeight = ImGui::GetFrameHeight();
                const float fpsStepSide = fpsRowHeight - 6.0f;          // 20 x 20
                const float fpsStepDrop = (fpsRowHeight - fpsStepSide) * 0.5f;
                ImGui::SameLine(0.0f, 4.0f);
                ImVec2 fpsStepPos = ImGui::GetCursorScreenPos();
                ImGui::SetCursorScreenPos(ImVec2(fpsStepPos.x, fpsStepPos.y + fpsStepDrop));
                if (StepButton("##dxvkfpsminus", fpsStepSide, false))
                {
                    dc.maxFps = (dc.maxFps > 0) ? dc.maxFps - 1 : 0;
                    dxvk_download::ConfSet(dc);
                }
                ImGui::SameLine(0.0f, 4.0f);
                fpsStepPos = ImGui::GetCursorScreenPos();
                ImGui::SetCursorScreenPos(ImVec2(fpsStepPos.x, fpsStepPos.y + fpsStepDrop));
                if (StepButton("##dxvkfpsplus", fpsStepSide, true))
                {
                    dc.maxFps = (dc.maxFps < 1000) ? dc.maxFps + 1 : 1000;
                    dxvk_download::ConfSet(dc);
                }
                tree.Row();   // the FPS-cap row - the last branch
                tree.Draw();

                ImGui::Unindent(12.0f);
                ImGui::EndDisabled();

                ImGui::TextUnformatted(L()->dxvkSettingsNote);
            }
            EndCard();
        }
        else if (g_activePage == 2)
        {
            // ---- page 3: tools - things that do not need a slot on the main page ----
            // [LOCAL] The card FILLS the page: a lone auto-sized card floating in
            // an otherwise empty panel reads as broken.  Height = everything
            // above the mark's band: that band is exactly one icon tall plus one
            // spacing, and the mark itself is pinned to the BOTTOM of the content
            // area below - so the card can grow right up against it and any
            // leftover from layout rounding lands INSIDE the card, not between
            // the card and the mark.
            const float toolsFill = ImGui::GetContentRegionAvail().y
                - (ImGui::GetTextLineHeight() + ImGui::GetStyle().ItemSpacing.y);
            BeginCardSized(L()->moreCard, toolsFill);
            {
                // [LOCAL] The mod-translation switch sits beside the update
                // button on purpose: both are "Chinese text" features, so the
                // row reads as one grouped action instead of two stray ones.
                // The switch only writes the config; it taking effect is the
                // config-apply path re-running translate::Init().
                bool modTrans = t7patch_cfg_translate_enabled();
                if (SolidCheckbox(L()->modTranslate, &modTrans))
                {
                    t7patch_cfg_set_translate(modTrans ? 1 : 0);
                    t7patch_config_save();
                }
                ImGui::SetItemTooltip("%s", L()->modTranslateTip);

                // [LOCAL] The update button lives here now: it is a low-frequency
                // action, and it had already cost the main page its bottom line
                // once (see the layout note in MEMORY.md - the panel is a fixed
                // 395x440).  Auto width - the fixed 140px read like a progress
                // bar around a four-character label.  The result text sits right
                // beside the button and is kept SHORT: a glanceable status, the
                // details live in the log.
                const dict_update::Status du = dict_update::Get();
                const bool downloading = du.state == dict_update::State::Running;

                // Same row as the switch above - that grouping is the whole point
                // of this row.  (This SameLine got lost in a later edit once and
                // the button dropped to its own row; the fixcheck anchor below
                // exists so it stays found.)
                ImGui::SameLine();
                char dictBtn[96]{};
                snprintf(dictBtn, sizeof(dictBtn), "%s##dictupdate", L()->dictUpdate);
                if (ImGui::Button(dictBtn, ImVec2(0.0f, 0.0f)) && !downloading)
                    dict_update::Start();
                ImGui::SetItemTooltip("%s", L()->dictUpdateTip);

                if (downloading)
                {
                    ImGui::SameLine();
                    ImGui::TextUnformatted(L()->dictUpdating);
                }
                else if (du.state == dict_update::State::Ok)
                {
                    ImGui::SameLine();
                    ImGui::Text(L()->dictUpdatedFmt, du.entries);
                }
                else if (du.state == dict_update::State::Failed)
                {
                    ImGui::SameLine();
                    ImGui::Text(L()->dictFailedFmt, du.message);
                }
                else if (du.state == dict_update::State::UpToDate)
                {
                    // A click inside the post-success cooldown: nothing ran and
                    // nothing failed, so it gets its own neutral line.
                    ImGui::SameLine();
                    ImGui::TextUnformatted(L()->dictUpToDate);
                }
                // [LOCAL] The translation switch's SUB-switches, on their own
                // lines and indented, because that is what they are: they only
                // ever have an effect while the switch above is on (the patch
                // does not even measure the scene otherwise - see the MainThread
                // loop in Protection.cpp).
                //
                // [LOCAL] Greyed out while that switch is off - the owner's call,
                // 2026-09-16 ("关了之后这两子开关变为不可点选项").  This once
                // went the other way, for a reason that no longer holds: a
                // disabled item used to swallow hover, which would have left the
                // tooltips - the one place the dependency is spelled out -
                // unreadable.  imgui 1.92's tooltip flags carry
                // AllowWhenDisabled (HoverFlagsForTooltipMouse), so they still
                // show; the box itself honours style.Alpha, see SolidCheckbox.
                const bool transOn = t7patch_cfg_translate_enabled();
                ImGui::BeginDisabled(!transOn);
                ImGui::Indent(12.0f);
                // The guide that ties the two switches below to mod 汉化.
                SubTree tree;

                bool pvpSkip = t7patch_cfg_skip_pvp();
                if (SolidCheckbox(L()->pvpSkip, &pvpSkip))
                {
                    t7patch_cfg_set_skip_pvp(pvpSkip ? 1 : 0);
                    t7patch_config_save();
                }
                ImGui::SetItemTooltip("%s", L()->pvpSkipTip);
                tree.Row();

                bool zmSkip = t7patch_cfg_skip_zm();
                if (SolidCheckbox(L()->zmSkip, &zmSkip))
                {
                    t7patch_cfg_set_skip_zm(zmSkip ? 1 : 0);
                    t7patch_config_save();
                }
                ImGui::SetItemTooltip("%s", L()->zmSkipTip);
                tree.Row();
                tree.Draw();

                ImGui::Unindent(12.0f);
                ImGui::EndDisabled();

                // [LOCAL] The DXVK row used to live here; it moved to the DXVK
                // page together with its settings (a rendering backend is not
                // a translation feature).
            }
            EndCard();
        }
        else
        {
        // ---- page 1: everything that was here before ----
        BeginCard(L()->settings);
        {
            // [LOCAL] Table layout: fixed label column, stretched field column,
            // fixed button column.  Rows line up vertically no matter how long
            // a label or value is - tidier than manual SameLine offsets and it
            // stays compact.
            if (ImGui::BeginTable("##settings", 3, ImGuiTableFlags_NoPadOuterX))
            {
                ImGui::TableSetupColumn("label", ImGuiTableColumnFlags_WidthFixed, 100.0f);
                ImGui::TableSetupColumn("field", ImGuiTableColumnFlags_WidthFixed, 175.0f);
                ImGui::TableSetupColumn("btn", ImGuiTableColumnFlags_WidthFixed, 54.0f);

                // Row 1: player name
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                ImGui::AlignTextToFramePadding();
                ImGui::TextUnformatted(L()->playerName);
                ImGui::TableSetColumnIndex(1);
                ImGui::SetNextItemWidth(-FLT_MIN);
                // InputText returns true whenever it modified the buffer, so
                // this is exactly "the user is typing" - and the strongest
                // signal to stop auto-filling over their input.
                if (ImGui::InputText("##playername", g_playerNameBuf, sizeof(g_playerNameBuf)))
                    g_playerNameAutofill = false;
                // A focused-but-not-yet-typed field counts as taken over too:
                // never drop a name in under the user's cursor.
                if (ImGui::IsItemActive())
                    g_playerNameAutofill = false;
                ImGui::TableSetColumnIndex(2);
                if (ImGui::Button("Save##playername", ImVec2(-FLT_MIN, 0.0f)))
                {
                    t7patch_cfg_set_playername(g_playerNameBuf);
                    t7patch_config_save();
                    g_playerNameAutofill = false;
                }

                // Row 2: room password
                ImGui::TableNextRow();
                ImGui::TableSetColumnIndex(0);
                ImGui::AlignTextToFramePadding();
                ImGui::TextUnformatted(L()->roomPassword);
                ImGui::TableSetColumnIndex(1);
                ImGui::SetNextItemWidth(-FLT_MIN);
                ImGui::InputText("##password", g_passwordBuf, sizeof(g_passwordBuf),
                    ImGuiInputTextFlags_Password);
                ImGui::TableSetColumnIndex(2);
                if (ImGui::Button("Save##password", ImVec2(-FLT_MIN, 0.0f)))
                {
                    t7patch_cfg_set_network_password(g_passwordBuf);
                    t7patch_config_save();
                }

                ImGui::EndTable();
            }
        }
        EndCard();

        BeginCard(L()->toggles);
        {
            bool friendsOnly = t7patch_cfg_friends_only();
            if (SolidCheckbox(L()->friendsOnly, &friendsOnly))
            {
                t7patch_cfg_set_friends_only(friendsOnly);
                t7patch_config_save();
            }
            // [LOCAL] SetItemTooltip() is the "IsItemHovered(ForTooltip) then
            // SetTooltip()" idiom, so it inherits the panel-wide hover delay
            // from ApplyOverlayTheme: rest on the item, no fly-by popups.
            // (There used to be an explicit IsItemHovered() here, with no flags
            // - that is the instant version.)
            ImGui::SetItemTooltip("%s", L()->friendsOnlyTip);

            bool block46 = hooks::IsD3DCompilerBlockEnabled();
            if (SolidCheckbox(L()->blockShader, &block46))
                hooks::SetD3DCompilerBlock(block46);
            ImGui::SetItemTooltip("%s", L()->blockShaderTip);

            // [LOCAL] Auto-open: open the window by itself once the main menu
            // is reached (same signal as the hotkey gate).  Only takes effect
            // on the NEXT run after a change - the auto-open decision for this
            // session was already made when the main menu came up.
            bool autoOpen = t7patch_menu_auto_open();
            if (SolidCheckbox(L()->autoOpen, &autoOpen))
            {
                t7patch_cfg_set_menu_auto_open(autoOpen);
                t7patch_config_save();
            }
            ImGui::SetItemTooltip("%s", L()->autoOpenTip);
        }
        EndCard();

        // [LOCAL] The last card of the page FILLS it, exactly like the DXVK and
        // tools pages already do.  Page 1 used to rely on its three auto-sized
        // cards happening to add up to the panel height - which is precisely
        // why it looked tidy AND why the next row added here would either leave
        // a gap or be clipped outright: the panel is a fixed 395x440 with no
        // scrollbar, so overflow has nowhere to go.  Filling removes the row
        // budget from this card (adding a row moves its content, not its
        // border) and levels the bottom edge of all three pages, which is what
        // "the gap at the bottom differs between pages" was.
        //
        // The height is measured AFTER the two cards above, so it needs no
        // constant of its own.
        BeginCardSized(L()->config, ImGui::GetContentRegionAvail().y);
        {
            // Language: two small buttons, the active one drawn in accent.
            // The label leads its line, so it needs the frame padding offset by
            // hand (see the FPS cap row on the graphics page).
            ImGui::AlignTextToFramePadding();
            ImGui::TextUnformatted(L()->language);
            ImGui::SameLine(100.0f);
            const bool zhActive = t7patch_cfg_menu_lang() != 0;
            if (LangButton("中文", zhActive))
            {
                t7patch_cfg_set_menu_lang(1);
                t7patch_config_save();
            }
            ImGui::SameLine();
            if (LangButton("EN", !zhActive))
            {
                t7patch_cfg_set_menu_lang(0);
                t7patch_config_save();
            }

            // Hotkey: click the button, then press the new key (ESC cancels).
            // Same leading-label offset as the language row; the inline hint at
            // the end of this line inherits it through SameLine().
            ImGui::AlignTextToFramePadding();
            ImGui::TextUnformatted(L()->hotkey);
            ImGui::SameLine(100.0f);
            // [LOCAL] While waiting for the new key the button STAYS - same size,
            // stable ID - and only its label becomes "...".  It used to be
            // replaced by a text label, which changed the column width and
            // dragged the whole card (and its border) along with it.
            const bool capturingKey = g_capturingHotkey.load();
            char hotkeyBtn[64]{};
            snprintf(hotkeyBtn, sizeof(hotkeyBtn), "%s##hotkeybtn",
                capturingKey ? "..." : VkName(t7patch_menu_key()));
            if (ImGui::Button(hotkeyBtn, ImVec2(90.0f, 0.0f)) && !capturingKey)
                g_capturingHotkey = true;
            if (capturingKey)
            {
                // [LOCAL] Same delayed tooltip as the rest of the panel.  It is
                // the only place the "press a key" prompt is spelled out now that
                // the reminder sits inline - the full prompt would not fit this
                // column (it is wider than the whole row in English).
                ImGui::SetItemTooltip("%s", L()->pressAnyKey);
            }
            else
            {
                // [LOCAL] "Press <key> to toggle" moved here from the bottom of
                // the panel.  Two reasons: it belongs next to the key it
                // describes, and its old line is what now pays for the update
                // button's row (the panel is a fixed 395x440 with no scrollbar,
                // so every line is spoken for).  Shortened to fit this column -
                // the English wording had to lose "this window".
                char hint[160]{};
                snprintf(hint, sizeof(hint), L()->hint, VkName(t7patch_menu_key()));
                ImGui::SameLine();
                ImGui::TextDisabled("%s", hint);
            }
        }
        EndCard();
        } // end of page 1 (the if above was page 2's branch)

        // [LOCAL] GitHub mark: TOOLS PAGE ONLY.  Page 1's cards auto-size and flow
        // edge-to-edge with no band reserved at the bottom, so pinning the mark
        // to the panel bottom drew it on top of the config card there (2026-09-16,
        // user screenshot).  The tools page is the one whose full-height card
        // leaves an exact band for it - and the user explicitly preferred it that
        // way.  The DXVK page (added later) deliberately has no mark either: one
        // repo link in one place is enough.
        if (g_activePage == 2)
        {
            const float iconSize = ImGui::GetTextLineHeight();
            constexpr float kIconPad = 4.0f;
            const float iconItemWidth = iconSize + kIconPad * 2.0f;
            ImGui::SetCursorPosY(ImGui::GetWindowSize().y
                - ImGui::GetStyle().WindowPadding.y - iconSize);
            ImGui::SetCursorPosX(ImGui::GetWindowSize().x
                - ImGui::GetStyle().WindowPadding.x - iconItemWidth);

            // InvisibleButton + AddImage rather than ImageButton: ImageButton
            // always paints the regular button background behind the image,
            // which would drop a grey square onto the panel.  Same hand-drawn
            // pattern SolidCheckbox above uses.  The hit area is a few pixels
            // wider than the glyph so it is comfortable to click.
            const bool linkPressed = ImGui::InvisibleButton("##githublink",
                ImVec2(iconItemWidth, iconSize));
            const bool linkHovered = ImGui::IsItemHovered();
            // [LOCAL] Two different hover tests on purpose.  The tooltip is
            // delayed like every other one (see ApplyOverlayTheme), but the
            // cursor and the icon tint below stay INSTANT: those are the "this
            // is clickable" feedback, and feedback that lags the pointer just
            // feels broken.
            const bool linkTipDue = ImGui::IsItemHovered(ImGuiHoveredFlags_ForTooltip);
            const ImVec2 linkMin = ImGui::GetItemRectMin();
            const ImVec2 linkMax = ImGui::GetItemRectMax();

            if (g_linkIconSrv)
            {
                ImGui::GetWindowDrawList()->AddImage(
                    (ImTextureID)(intptr_t)g_linkIconSrv,
                    ImVec2(linkMin.x + kIconPad, linkMin.y),
                    ImVec2(linkMax.x - kIconPad, linkMax.y),
                    ImVec2(0.0f, 0.0f), ImVec2(1.0f, 1.0f),
                    ImGui::GetColorU32(linkHovered ? kIconHover : kIconRest));
            }

            if (linkHovered)
                ImGui::SetMouseCursor(ImGuiMouseCursor_Hand);

            // Label only.  The URL is deliberately NOT part of the tooltip -
            // a raw "https://github.com/..." line reads like debug output
            // next to the rest of the panel's copy.
            if (linkTipDue)
                ImGui::SetTooltip("%s", L()->about);

            if (linkPressed)
            {
                // [LOCAL] Hand the URL to the shell so it opens in the default
                // browser.  A failure is logged, not surfaced in the UI - there
                // is nothing the player could do about it mid-match.
                if ((INT_PTR)ShellExecuteA(nullptr, "open", kRepoUrl,
                        nullptr, nullptr, SW_SHOWNORMAL) <= 32)
                    overlay_log("github link: ShellExecuteA failed");
            }
        }

        ImGui::End();
    }

    // -----------------------------------------------------------------
    //  Init helpers
    // -----------------------------------------------------------------

    // [LOCAL] Build the GitHub mark texture from the embedded alpha mask.
    // RGBA8 with RGB forced to WHITE: the DX11 backend multiplies the vertex
    // colour by the sampled texel, so a white texture turns the per-frame draw
    // tint into the icon's actual colour (see kIconRest / kIconHover).  The
    // source art is black-on-transparent, so only its alpha is meaningful here.
    // Caller must hold g_overlayMutex.
    void CreateLinkIconTextureLocked()
    {
        if (g_linkIconSrv || !g_device)
            return;

        constexpr int kSize = kGithubMarkSize;
        static_assert(kGithubMarkSize * kGithubMarkSize * 2 == sizeof(kGithubMarkAlphaHex) - 1,
            "GithubMark.h: mask length does not match kGithubMarkSize");

        const auto hexNibble = [](char c) -> unsigned char
        {
            return (unsigned char)((c <= '9') ? (c - '0') : ((c | 0x20) - 'a' + 10));
        };

        unsigned char pixels[kSize * kSize * 4] = {};
        for (int i = 0; i < kSize * kSize; ++i)
        {
            const char* hex = &kGithubMarkAlphaHex[i * 2];
            // RGB is pinned to white on purpose; the draw-time tint supplies
            // the actual colour.  (Deliberately written as three plain lines -
            // a trailing backslash in a // comment would splice the NEXT line
            // into the comment and silently drop an assignment.)
            pixels[i * 4 + 0] = 0xFF;
            pixels[i * 4 + 1] = 0xFF;
            pixels[i * 4 + 2] = 0xFF;
            pixels[i * 4 + 3] = (unsigned char)((hexNibble(hex[0]) << 4) | hexNibble(hex[1]));
        }

        D3D11_TEXTURE2D_DESC desc{};
        desc.Width = kSize;
        desc.Height = kSize;
        desc.MipLevels = 1;
        desc.ArraySize = 1;
        desc.Format = DXGI_FORMAT_R8G8B8A8_UNORM;
        desc.SampleDesc.Count = 1;
        desc.Usage = D3D11_USAGE_IMMUTABLE;
        desc.BindFlags = D3D11_BIND_SHADER_RESOURCE;

        D3D11_SUBRESOURCE_DATA init{};
        init.pSysMem = pixels;
        init.SysMemPitch = kSize * 4;

        ID3D11Texture2D* texture = nullptr;
        if (FAILED(g_device->CreateTexture2D(&desc, &init, &texture)))
        {
            overlay_log("link icon: CreateTexture2D FAILED (icon hidden)");
            return;
        }

        D3D11_SHADER_RESOURCE_VIEW_DESC srvDesc{};
        srvDesc.Format = desc.Format;
        srvDesc.ViewDimension = D3D11_SRV_DIMENSION_TEXTURE2D;
        srvDesc.Texture2D.MipLevels = 1;
        const HRESULT hr = g_device->CreateShaderResourceView(texture, &srvDesc, &g_linkIconSrv);
        texture->Release();

        if (FAILED(hr))
        {
            g_linkIconSrv = nullptr;
            overlay_log("link icon: CreateShaderResourceView FAILED (icon hidden)");
        }
        else
        {
            overlay_log("link icon texture created");
        }
    }

    bool InitImGuiLocked()
    {
        if (g_imguiReady || !g_device || !g_context || !g_swapChain || !g_hwnd)
            return false;

        ImGui::CreateContext();
        ApplyOverlayTheme();
        ImGuiIO& io = ImGui::GetIO();
        // [LOCAL] Keep imgui.ini inside T7Patch\ (window positions/sizes are
        // remembered between launches, next to the other patch files).  Built
        // as an absolute path from the exe location, stored in the static
        // buffer above (ImGui keeps the pointer, it must outlive the context).
        {
            wchar_t exePath[MAX_PATH]{};
            if (GetModuleFileNameW(nullptr, exePath, MAX_PATH))
            {
                const auto iniPath = std::filesystem::path(exePath).parent_path()
                    / L"T7Patch" / L"imgui.ini";
                WideCharToMultiByte(CP_UTF8, 0, iniPath.c_str(), -1,
                    g_imguiIniPath, sizeof(g_imguiIniPath), nullptr, nullptr);
                io.IniFilename = g_imguiIniPath;
            }
        }

        // [LOCAL] The stock ProggyClean font has no CJK glyphs and this user
        // runs the zh-CN config template, so load a system CJK font first and
        // fall back to the default only if none exists.
        {
            // [LOCAL] CJK font tune-up: MiSans first (modern, screen-optimised),
            // then DengXian / YaHei / SimHei.  Oversampling is kept LOW (2x1)
            // with pixel snapping ON - ImGui's defaults (3x1, no snap) make
            // hanzi look mushy; RasterizerMultiply brightens thin strokes.
            bool fontLoaded = false;
            const char* cjkFonts[] = {
                "C:\\Windows\\Fonts\\MiSans-Regular.otf",
                "C:\\Windows\\Fonts\\Deng.ttf",
                "C:\\Windows\\Fonts\\msyh.ttc",
                "C:\\Windows\\Fonts\\simhei.ttf",
            };
            ImFontConfig fontCfg;
            fontCfg.OversampleH = 2;
            fontCfg.OversampleV = 1;
            fontCfg.PixelSnapH = true;
            fontCfg.RasterizerMultiply = 1.10f;
            for (const char* fontPath : cjkFonts)
            {
                if (GetFileAttributesA(fontPath) == INVALID_FILE_ATTRIBUTES)
                    continue;
                if (io.Fonts->AddFontFromFileTTF(fontPath, 18.0f, &fontCfg,
                        io.Fonts->GetGlyphRangesChineseSimplifiedCommon()))
                {
                    char msg[128]{};
                    snprintf(msg, sizeof(msg), "font loaded: %s", fontPath);
                    overlay_log(msg);
                    fontLoaded = true;
                    break;
                }
            }
            if (!fontLoaded)
            {
                // [LOCAL] This machine has none of the CJK fonts above.  The
                // default font carries ASCII glyphs only, while menu_lang
                // defaults to Chinese - so the panel would come up as a screen
                // of boxes with nothing in the log to explain it.  Say so, and
                // fall back to the English text table so it stays usable (the
                // setting is saved, so the conf agrees with what is on screen).
                overlay_log("font: no CJK system font found (tried MiSans, "
                    "DengXian, YaHei, SimHei) - menu switched to English");
                io.Fonts->AddFontDefault();
                t7patch_cfg_set_menu_lang(0);
                t7patch_config_save();
            }
        }

        if (!ImGui_ImplWin32_Init(g_hwnd))
            return false;
        if (!ImGui_ImplDX11_Init(g_device, g_context))
            return false;

        // [LOCAL] Resource for the bottom-right link.  Independent of ImGui,
        // but built here so it only exists once the overlay is actually up
        // (and so a failed overlay init does not leak the texture).
        CreateLinkIconTextureLocked();

        // [LOCAL] 装第二层鼠标 hook（见 HookCursorApisLocked 上方说明）。放在 ImGui 初始化之后、
        // 开门（g_imguiReady）之前 —— 它不依赖 ImGui，这个位置只是让日志顺序更好读。
        HookCursorApisLocked();

        g_imguiReady = true;
        // [LOCAL] menu_auto_open fires later, on the first DLC ownership
        // query (main menu reached) - see NotifyMainMenuReached().
        g_menuOpen = false;
        // [LOCAL] Present-frame warm-up: run this many full ImGui frames even
        // while the menu is closed, so the CJK font atlas (~2500 glyphs) is
        // rasterised during the intro movie instead of on the first Insert
        // press (which would show as a visible hitch).
        g_warmupFrames = 2;
        return true;
    }

    // [LOCAL] 菜单打开时"接管鼠标"的**第二层**（用户 2026-09-19 反馈："鼠标是出来了，但是还是被锁在中间，
    // 游戏还是能读取到鼠标的移动"）。第一层（Present 里每帧 `ClipCursor(nullptr)` + ImGui 自绘光标）只能让
    // 光标**露出来** —— 游戏**每帧都会重新** ClipCursor 把光标压回中间，谁后调谁生效，所以我们每帧解一次
    // 根本压不住。必须**从源头拦**：
    //   ① `ClipCursor`        —— 游戏调用时直接忽略（菜单开着 ⇒ 永不裁剪）；
    //   ② `SetCursorPos`      —— 防止游戏每帧把光标拽回屏幕中心；
    //   ③ `GetRawInputBuffer` —— 游戏读鼠标位移的**轮询**通道（不走 `WM_INPUT`，所以"吞消息"对它无效，
    //      这正是"游戏还能读到鼠标移动"的原因）。照常调原函数把缓冲**消费掉**（否则关菜单后会一次性涌出
    //      积压位移、视角猛地甩一下），但对游戏**谎报 0 条**。
    // ⚠️ 特意**不** hook `GetCursorPos`：`imgui_impl_win32.cpp:337` 靠它算鼠标位置，拦了会把 ImGui 自己的
    // 光标一起钉死。三个 hook 都只作用于本进程（这个 DLL 就在游戏进程里）。
    // ⚠️ 每个 hook **首次被调用**时记一行日志 —— 否则"游戏根本没走这条通道"和"hook 没装上"在日志里长得
    // 一模一样（横幅取证时已经踩过一次这个坑）。
    using ClipCursorFn = BOOL(WINAPI*)(const RECT*);
    using SetCursorPosFn = BOOL(WINAPI*)(int, int);
    using GetRawInputBufferFn = UINT(WINAPI*)(PRAWINPUT, PUINT, UINT);
    ClipCursorFn g_origClipCursor = nullptr;
    SetCursorPosFn g_origSetCursorPos = nullptr;
    GetRawInputBufferFn g_origGetRawInputBuffer = nullptr;
    std::atomic<bool> g_clipCursorSeen{ false };
    std::atomic<bool> g_setCursorPosSeen{ false };
    std::atomic<bool> g_rawInputBufferSeen{ false };

    BOOL WINAPI HookClipCursor(const RECT* lpRect)
    {
        if (!g_clipCursorSeen.exchange(true))
            overlay_log("cursor: game called ClipCursor (hook armed)");
        if (g_menuOpen.load())
            return g_origClipCursor ? g_origClipCursor(nullptr) : TRUE; // 菜单开着 ⇒ 永不裁剪
        return g_origClipCursor ? g_origClipCursor(lpRect) : TRUE;
    }

    BOOL WINAPI HookSetCursorPos(int x, int y)
    {
        if (!g_setCursorPosSeen.exchange(true))
            overlay_log("cursor: game called SetCursorPos (hook armed)");
        if (g_menuOpen.load())
            return TRUE; // 菜单开着 ⇒ 不理会游戏把光标拽回中心
        return g_origSetCursorPos ? g_origSetCursorPos(x, y) : TRUE;
    }

    UINT WINAPI HookGetRawInputBuffer(PRAWINPUT pData, PUINT pcbSize, UINT cbSizeHeader)
    {
        if (!g_rawInputBufferSeen.exchange(true))
            overlay_log("cursor: game called GetRawInputBuffer (hook armed)");
        const UINT count = g_origGetRawInputBuffer
            ? g_origGetRawInputBuffer(pData, pcbSize, cbSizeHeader) : 0;
        if (g_menuOpen.load())
            return 0; // 数据已被消费掉，但对游戏谎称"没有数据"
        return count;
    }

    void HookCursorApisLocked()
    {
        HMODULE user32 = GetModuleHandleW(L"user32.dll");
        if (!user32)
        {
            overlay_log("cursor: user32 not found - cursor hooks skipped");
            return;
        }
        const LPVOID clipAddr = reinterpret_cast<LPVOID>(GetProcAddress(user32, "ClipCursor"));
        const LPVOID posAddr = reinterpret_cast<LPVOID>(GetProcAddress(user32, "SetCursorPos"));
        const LPVOID rawAddr = reinterpret_cast<LPVOID>(GetProcAddress(user32, "GetRawInputBuffer"));
        MH_STATUS sClip = MH_ERROR_NOT_INITIALIZED;
        MH_STATUS sPos = MH_ERROR_NOT_INITIALIZED;
        MH_STATUS sRaw = MH_ERROR_NOT_INITIALIZED;
        if (clipAddr)
            sClip = MH_CreateHook(clipAddr, (LPVOID)&HookClipCursor, (LPVOID*)&g_origClipCursor);
        if (posAddr)
            sPos = MH_CreateHook(posAddr, (LPVOID)&HookSetCursorPos, (LPVOID*)&g_origSetCursorPos);
        if (rawAddr)
            sRaw = MH_CreateHook(rawAddr, (LPVOID)&HookGetRawInputBuffer, (LPVOID*)&g_origGetRawInputBuffer);
        // 逐个启用（不用 MH_ALL_HOOKS，免得顺带动到别的 hook）。
        if (clipAddr && sClip == MH_OK)
            MH_EnableHook(clipAddr);
        if (posAddr && sPos == MH_OK)
            MH_EnableHook(posAddr);
        if (rawAddr && sRaw == MH_OK)
            MH_EnableHook(rawAddr);
        char cursorMsg[192]{};
        snprintf(cursorMsg, sizeof(cursorMsg),
            "cursor hooks: ClipCursor=%d SetCursorPos=%d GetRawInputBuffer=%d (0=MH_OK)",
            static_cast<int>(sClip), static_cast<int>(sPos), static_cast<int>(sRaw));
        overlay_log(cursorMsg);
    }

    void HookWndProcLocked()
    {
        if (g_wndProcHooked || !g_hwnd)
            return;

        g_origWndProc = reinterpret_cast<WNDPROC>(
            SetWindowLongPtrW(g_hwnd, GWLP_WNDPROC,
                reinterpret_cast<LONG_PTR>(OverlayWndProc)));
        g_wndProcHooked = (g_origWndProc != nullptr);
    }

    void HookPresentLocked()
    {
        if (g_origPresent || !g_swapChain)
            return;

        void** vtable = *reinterpret_cast<void***>(g_swapChain);
        g_origPresent = vtable[kPresentVtableIndex];
        g_patchedVtableSlot = &vtable[kPresentVtableIndex];

        DWORD oldProtect = 0;
        if (VirtualProtect(g_patchedVtableSlot, sizeof(void*),
                PAGE_EXECUTE_READWRITE, &oldProtect))
        {
            *g_patchedVtableSlot = reinterpret_cast<void*>(&HookPresent);
            VirtualProtect(g_patchedVtableSlot, sizeof(void*), oldProtect, &oldProtect);
        }
        else
        {
            g_origPresent = nullptr;
            g_patchedVtableSlot = nullptr;
        }
    }

    // Caller must hold g_overlayMutex.
    void CaptureSwapChainLocked(IDXGISwapChain* swapChain)
    {
        g_swapChain = swapChain;

        DXGI_SWAP_CHAIN_DESC desc{};
        if (SUCCEEDED(g_swapChain->GetDesc(&desc)))
            g_hwnd = desc.OutputWindow;

        if (!g_device && SUCCEEDED(g_swapChain->GetDevice(__uuidof(ID3D11Device),
                reinterpret_cast<void**>(&g_device))))
        {
            // context comes along with it
            if (g_device)
                g_device->GetImmediateContext(&g_context);
        }

        HookPresentLocked();
        HookWndProcLocked();
        InitImGuiLocked();

        char msg[160]{};
        snprintf(msg, sizeof(msg),
            "swap chain captured: presentHook=%d wndProcHook=%d imguiReady=%d hwnd=%p",
            g_origPresent ? 1 : 0, g_wndProcHooked ? 1 : 0,
            g_imguiReady ? 1 : 0, (void*)g_hwnd);
        overlay_log(msg);
    }

    // Takes the lock itself (called from the factory hooks).
    void OnSwapChainCaptured(IDXGISwapChain* swapChain)
    {
        std::lock_guard<std::mutex> lock(g_overlayMutex);
        if (g_swapChain) // first swap chain wins; rebuilds share the patched vtable
            return;

        CaptureSwapChainLocked(swapChain);
    }

    // -----------------------------------------------------------------
    //  Hook implementations
    // -----------------------------------------------------------------
    HRESULT STDMETHODCALLTYPE HookPresent(IDXGISwapChain* self, UINT syncInterval, UINT flags)
    {
        // [LOCAL] Deferred auto-open.  Checked here rather than down in the
        // frame block: during those 1.5 s the menu is still closed, so runFrame
        // is false and that block is skipped - a pending open parked down there
        // would never fire.
        const unsigned long long autoOpenDue = g_autoOpenDueMs.load();
        if (autoOpenDue != 0 && GetTickCount64() >= autoOpenDue)
        {
            g_autoOpenDueMs = 0;
            g_menuOpen = true;
            g_editBufsLoaded = false; // re-read the text buffers from the conf
            overlay_log("menu AUTO-OPENED (1500 ms after the gate opened)");
        }

        // [LOCAL] Menu-closed fast path: skip the entire ImGui frame.  A cooked
        // but empty frame still costs the DX11 backend's state save/restore on
        // every present (tens of microseconds per frame, ~0.5-1% at 144 FPS).
        // The warm-up frames run right after init so the font atlas is built
        // during the intro movie, not on the user's first hotkey press.  The
        // next NewFrame re-queries the display size, so resuming is seamless.
        // [LOCAL] Run the full ImGui frame every present.  A short-lived
        // optimisation skipped it while the menu was closed, but that froze
        // the Win32 backend's io state updates between menu sessions and,
        // inside a match, the whole UI stopped reacting to clicks (the clicks
        // themselves still landed).  The empty-frame cost is a few dozen
        // microseconds - correctness wins.
        if (g_imguiReady.load())
        {
            // [LOCAL] Time the first warm-up frame.  Its real work is ImGui's CJK
            // font atlas: ~2500 glyphs get rasterised in one go the first time
            // the DX11 backend is asked to build the font texture, which can
            // show as a visible hitch.  Logging it turns "the picture stutters
            // once at start-up" into a number that either matches what the user
            // saw or rules the overlay out - guessing between "the patch" and
            // "the game" is exactly what this line exists to stop.
            const bool timedFrame = (g_warmupFrames == 2);
            const unsigned long long frameStart = timedFrame ? GetTickCount64() : 0;

            if (g_warmupFrames > 0)
                --g_warmupFrames;

            ImGui_ImplDX11_NewFrame();
            ImGui_ImplWin32_NewFrame();
            ImGui::NewFrame();

            // [LOCAL] 菜单打开时**接管鼠标**（用户 2026-09-19 反馈："正在玩的时候打开鼠标还没释放没法操作我们的 UI"）。
            //   ① `ClipCursor(nullptr)`：游戏把光标裁剪并锁在窗口里（每帧重设）⇒ 我们**每帧压过它**。
            //      不做这一步，ImGui 拿到的鼠标位置会一直卡在原地，表现就是"面板看得见但点不动"。
            //   ② `io.MouseDrawCursor = true`：游戏用 `ShowCursor(FALSE)` 把系统光标藏了，而 `ShowCursor`
            //      是**引用计数**（我们无法可靠地把它顶回可见）⇒ 直接让 ImGui 自绘一个箭头，不依赖系统光标。
            // 关掉菜单只需撤掉自绘光标：光标裁剪与隐藏游戏自己会恢复，不需要我们做逆操作。
            ImGuiIO& imguiIo = ImGui::GetIO();
            if (g_menuOpen)
            {
                ClipCursor(nullptr);
                imguiIo.MouseDrawCursor = true;
                DrawMenu();
            }
            else
            {
                imguiIo.MouseDrawCursor = false;
            }

            ImGui::Render();
            ImGui_ImplDX11_RenderDrawData(ImGui::GetDrawData());

            if (timedFrame)
            {
                char frameMsg[128]{};
                snprintf(frameMsg, sizeof(frameMsg),
                    "first warm-up frame took %llu ms (font atlas + first ImGui pipeline)",
                    GetTickCount64() - frameStart);
                overlay_log(frameMsg);
            }
        }

        using PresentFn = HRESULT(STDMETHODCALLTYPE*)(IDXGISwapChain*, UINT, UINT);
        return reinterpret_cast<PresentFn>(g_origPresent)(self, syncInterval, flags);
    }

    HRESULT STDMETHODCALLTYPE HookFactoryCreateSwapChain(IDXGIFactory* self, IUnknown* pDevice,
        DXGI_SWAP_CHAIN_DESC* pDesc, IDXGISwapChain** ppSwapChain)
    {
        using Fn = HRESULT(STDMETHODCALLTYPE*)(IDXGIFactory*, IUnknown*, DXGI_SWAP_CHAIN_DESC*, IDXGISwapChain**);
        overlay_log("factory CreateSwapChain called");
        const HRESULT hr = reinterpret_cast<Fn>(g_origFactoryCreateSwapChain)(self, pDevice, pDesc, ppSwapChain);
        if (SUCCEEDED(hr) && ppSwapChain && *ppSwapChain)
            OnSwapChainCaptured(*ppSwapChain);
        return hr;
    }

    // [LOCAL] Windows 8+ path: some games prefer CreateSwapChainForHwnd
    // (vtable slot 11 on IDXGIFactory2+).  Signature differs from slot 10.
    HRESULT STDMETHODCALLTYPE HookFactoryCreateSwapChainForHwnd(IDXGIFactory2* self, IUnknown* pDevice,
        HWND hWnd, const void* pDesc, const void* pFullscreenDesc, void* pRestrictToOutput,
        void** ppSwapChain)
    {
        using Fn = HRESULT(STDMETHODCALLTYPE*)(IDXGIFactory2*, IUnknown*, HWND, const void*,
            const void*, void*, void**);
        overlay_log("factory CreateSwapChainForHwnd called");
        const HRESULT hr = reinterpret_cast<Fn>(g_origFactoryCreateSwapChainForHwnd)(self, pDevice,
            hWnd, pDesc, pFullscreenDesc, pRestrictToOutput, ppSwapChain);
        if (SUCCEEDED(hr) && ppSwapChain && *ppSwapChain)
            OnSwapChainCaptured(reinterpret_cast<IDXGISwapChain*>(*ppSwapChain));
        return hr;
    }

    LRESULT CALLBACK OverlayWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
    {
        // [LOCAL] Hotkey capture mode (CONFIG card): the next key press becomes
        // the new toggle key; Escape cancels.  Checked before the normal
        // hotkey handling below.
        if (g_capturingHotkey.load() && (msg == WM_KEYDOWN || msg == WM_SYSKEYDOWN))
        {
            int vk = static_cast<int>(wParam);

            // [LOCAL] An IME can swallow the keypress and report VK_PROCESSKEY
            // (0xE5) instead of the real key - that is exactly how pressing the
            // tilde key once produced "VK 0xE5".  Recover the true key from
            // the scan code in the message.
            if (vk == VK_PROCESSKEY)
            {
                const UINT scanCode = (static_cast<UINT>(lParam) >> 16) & 0xFFu;
                const UINT mapped = MapVirtualKeyW(scanCode, MAPVK_VSC_TO_VK_EX);
                if (mapped != 0)
                    vk = static_cast<int>(mapped);
            }

            g_capturingHotkey = false;
            if (vk != VK_ESCAPE)
            {
                t7patch_cfg_set_menu_key(vk);
                t7patch_config_save();
                overlay_log("hotkey changed from the menu");
            }
            else
            {
                overlay_log("hotkey capture cancelled");
            }
            return TRUE;
        }

        // [LOCAL] Gate signal: the front-end opens on a "press ENTER" title
        // screen, and nothing in the game's state separates that screen from the
        // main menu (seven polled candidates plus the UI-model marker were all
        // measured and failed - the marker turned out to fire on a fixed
        // front-end timer while the title screen is still up).  What DOES mark
        // the transition is the user leaving that screen, and we already see the
        // window's input: note the dismissing ENTER or click and let
        // Protection.cpp arm the hotkey a moment later.
        if (!g_mainMenuReached.load() && g_titleDismissedMs.load() == 0)
        {
            const bool dismissKey = (msg == WM_KEYDOWN && wParam == VK_RETURN);
            const bool dismissClick = (msg == WM_LBUTTONDOWN || msg == WM_RBUTTONDOWN);
            if (dismissKey || dismissClick)
            {
                g_titleDismissedMs = GetTickCount64();
                overlay_log(dismissKey ? "title screen dismissed (ENTER)"
                                       : "title screen dismissed (click)");
            }
        }

        // Menu hotkey.  WM_KEYDOWN repeat (bit 30) is ignored so holding the
        // key does not strobe the menu.
        // [LOCAL] Hotkey is gated on the main menu: during the intro movies
        // and the connect screen the game engine is still mid-init, and
        // opening the overlay there is both useless and a crash risk.
        if (msg == WM_KEYDOWN && wParam == (WPARAM)t7patch_menu_key() && !(lParam & 0x40000000))
        {
            if (!g_mainMenuReached)
            {
                // [LOCAL] Logged once per session: the player usually taps the
                // key a few times while the gate is still shut, and repeating
                // the same line adds nothing to the log.
                if (!g_hotkeyIgnoredLogged)
                {
                    g_hotkeyIgnoredLogged = true;
                    overlay_log("hotkey ignored (main menu not reached yet)");
                }
            }
            else
            {
                // [LOCAL] Cancel a pending deferred auto-open: if the player
                // already opened (or opened and closed) the menu themselves
                // inside those 1.5 s, popping it back up would fight them.
                g_autoOpenDueMs = 0;

                // [LOCAL] Menu open/close is not logged on purpose: it is pure
                // UI interaction, and one line per key press would drown the
                // handful of lines that actually matter (start-up, gate, 46
                // block).
                g_menuOpen = !g_menuOpen.load();
                if (g_menuOpen.load())
                    g_editBufsLoaded = false; // re-read the text buffers from the conf
            }
        }

        if (g_imguiReady)
            ImGui_ImplWin32_WndProcHandler(hwnd, msg, wParam, lParam);

        // [LOCAL] While the menu is open the game must not see input.  ImGui
        // has already taken whatever it needed above; letting WASD/mouse/raw
        // input through would steer the player and swing the camera behind the
        // menu.  Non-input messages (focus, sizing, activation) still reach
        // the game through CallWindowProc below.
        if (g_menuOpen.load())
        {
            switch (msg)
            {
            case WM_KEYDOWN: case WM_KEYUP:
            case WM_SYSKEYDOWN: case WM_SYSKEYUP:
            case WM_CHAR: case WM_SYSCHAR:
            case WM_MOUSEMOVE:
            case WM_LBUTTONDOWN: case WM_LBUTTONUP: case WM_LBUTTONDBLCLK:
            case WM_RBUTTONDOWN: case WM_RBUTTONUP: case WM_RBUTTONDBLCLK:
            case WM_MBUTTONDOWN: case WM_MBUTTONUP: case WM_MBUTTONDBLCLK:
            case WM_MOUSEWHEEL: case WM_MOUSEHWHEEL:
            case WM_INPUT: // raw input - BO3 reads mouse movement this way
                return TRUE;
            // [LOCAL] 同一道理：菜单开着时别让游戏改光标（BO3 会把光标设成 NULL 藏起来）。
            // 直接回"已处理"，游戏就没机会把它藏掉，配合 ImGui 自绘光标才能真正点得动。
            case WM_SETCURSOR:
                return TRUE;
            }
        }

        return CallWindowProc(g_origWndProc, hwnd, msg, wParam, lParam);
    }
} // namespace

namespace overlay
{
    void DebugLog(const char* msg)
    {
        overlay_log(msg);
    }

    unsigned long long TitleScreenDismissedMs()
    {
        return g_titleDismissedMs.load();
    }

    void NotifyMainMenuReached(const char* reason)
    {
        static bool notified = false;
        if (notified)
            return;
        notified = true;
        g_mainMenuReached = true;

        // [LOCAL] The reason is part of the line on purpose: when two gate
        // signals logged the same text, the 2026-09-15 title-screen popup (the
        // timer fallback firing on an idle "按ENTER开始" screen) looked exactly
        // like the real screen signal and took a log dig to attribute.  The
        // timer is gone now, but the name stays - whoever reads this log next
        // gets the answer for free.
        char msg[192]{};
        if (t7patch_menu_auto_open())
        {
            // [LOCAL] Scheduled, not opened: see kAutoOpenDelayMs.  HookPresent
            // performs the open and logs it, so this line says "in 1500 ms"
            // rather than "AUTO-OPENED" - the old wording would have been a lie
            // for 1.5 s.  The reason stays in this line, so the log still shows
            // WHICH gate signal armed it.
            g_autoOpenDueMs = GetTickCount64() + kAutoOpenDelayMs;
            snprintf(msg, sizeof(msg), "menu auto-open in %llu ms (%s, menu_auto_open=1)",
                kAutoOpenDelayMs, reason ? reason : "unknown");
        }
        else
        {
            snprintf(msg, sizeof(msg), "gate opened (%s; Insert now armed)",
                reason ? reason : "unknown");
        }
        overlay_log(msg);
    }

    void OnDeviceCreated(void* device, void* immediateContext)
    {
        std::lock_guard<std::mutex> lock(g_overlayMutex);
        if (g_device)
            return;

        // [LOCAL] Hold our own references: the interceptors hand us borrowed
        // pointers (owned by the game's swap chain) and we keep them for the
        // process lifetime - matching what the GetDevice() path does.
        g_device = static_cast<ID3D11Device*>(device);
        if (g_device)
            g_device->AddRef();
        g_context = static_cast<ID3D11DeviceContext*>(immediateContext);
        if (g_context)
            g_context->AddRef();

        // The game may still create its swap chain later through the DXGI
        // factory.  The parent chain is device -> adapter -> factory (TWO
        // GetParent hops - calling GetParent(IDXGIFactory2) on the device
        // fails, which is exactly what the first overlay attempt did wrong).
        // Hook BOTH creation paths: CreateSwapChain (slot 10) and
        // CreateSwapChainForHwnd (slot 11, IDXGIFactory2+).
        IDXGIDevice* dxgiDevice = nullptr;
        if (g_device && SUCCEEDED(g_device->QueryInterface(__uuidof(IDXGIDevice),
                reinterpret_cast<void**>(&dxgiDevice))))
        {
            IDXGIAdapter* adapter = nullptr;
            if (SUCCEEDED(dxgiDevice->GetParent(__uuidof(IDXGIAdapter),
                    reinterpret_cast<void**>(&adapter))))
            {
                IDXGIFactory2* factory = nullptr;
                if (SUCCEEDED(adapter->GetParent(__uuidof(IDXGIFactory2),
                        reinterpret_cast<void**>(&factory))))
                {
                    void** vtable = *reinterpret_cast<void***>(factory);

                    // slot 10: CreateSwapChain (legacy signature)
                    g_origFactoryCreateSwapChain = vtable[kCreateSwapChainVtableIndex];
                    g_patchedFactorySlot = &vtable[kCreateSwapChainVtableIndex];
                    DWORD old10 = 0;
                    if (VirtualProtect(g_patchedFactorySlot, sizeof(void*),
                            PAGE_EXECUTE_READWRITE, &old10))
                    {
                        *g_patchedFactorySlot = reinterpret_cast<void*>(&HookFactoryCreateSwapChain);
                        VirtualProtect(g_patchedFactorySlot, sizeof(void*), old10, &old10);
                        overlay_log("factory CreateSwapChain hooked");
                    }
                    else
                    {
                        g_origFactoryCreateSwapChain = nullptr;
                        g_patchedFactorySlot = nullptr;
                        overlay_log("factory slot 10 VirtualProtect FAILED");
                    }

                    // slot 11: CreateSwapChainForHwnd (IDXGIFactory2+ only)
                    g_origFactoryCreateSwapChainForHwnd = vtable[kCreateSwapChainForHwndVtableIndex];
                    g_patchedFactoryForHwndSlot = &vtable[kCreateSwapChainForHwndVtableIndex];
                    DWORD old11 = 0;
                    if (VirtualProtect(g_patchedFactoryForHwndSlot, sizeof(void*),
                            PAGE_EXECUTE_READWRITE, &old11))
                    {
                        *g_patchedFactoryForHwndSlot = reinterpret_cast<void*>(&HookFactoryCreateSwapChainForHwnd);
                        VirtualProtect(g_patchedFactoryForHwndSlot, sizeof(void*), old11, &old11);
                        overlay_log("factory CreateSwapChainForHwnd hooked");
                    }
                    else
                    {
                        g_origFactoryCreateSwapChainForHwnd = nullptr;
                        g_patchedFactoryForHwndSlot = nullptr;
                        overlay_log("factory slot 11 VirtualProtect FAILED");
                    }
                    factory->Release();
                }
                else
                {
                    overlay_log("adapter GetParent(IDXGIFactory2) FAILED");
                }
                adapter->Release();
            }
            else
            {
                overlay_log("device GetParent(IDXGIAdapter) FAILED");
            }
            dxgiDevice->Release();
        }
        else
        {
            overlay_log("device QueryInterface(IDXGIDevice) FAILED");
        }
    }

    void OnSwapChainCreated(void* swapChain, void* device, void* immediateContext)
    {
        std::lock_guard<std::mutex> lock(g_overlayMutex);

        if (swapChain && !g_device)
        {
            // Same ownership rule as OnDeviceCreated above.
            g_device = static_cast<ID3D11Device*>(device);
            if (g_device)
                g_device->AddRef();
            g_context = static_cast<ID3D11DeviceContext*>(immediateContext);
            if (g_context)
                g_context->AddRef();
        }

        if (swapChain && !g_swapChain) // capture the first swap chain we see
            CaptureSwapChainLocked(static_cast<IDXGISwapChain*>(swapChain));
    }
} // namespace overlay
