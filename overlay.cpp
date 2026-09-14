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
#include "overlay.h"
#include "Hooks.h" // [LOCAL] 46-block runtime toggle + interception counter
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

    void ApplyOverlayTheme()
    {
        ImGuiStyle& s = ImGui::GetStyle();
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
        c[ImGuiCol_ButtonActive] = ImVec4(1.000f, 0.459f, 0.004f, 1.00f); // #FF7501
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

    // [LOCAL] Cross-thread flags: written from the game thread (capture /
    // main-menu notify), from the WndProc thread (hotkey) and read every
    // frame by the render thread - atomics keep that honest.
    std::atomic<bool> g_imguiReady{ false };
    std::atomic<bool> g_menuOpen{ false };
    std::atomic<bool> g_mainMenuReached{ false }; // Insert is ignored until the main menu is up
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
    bool g_editBufsLoaded = false;
    const ULONGLONG g_sessionStart = GetTickCount64();

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
        wchar_t exePath[MAX_PATH]{};
        if (GetModuleFileNameW(nullptr, exePath, MAX_PATH) == 0)
            return;
        const auto path = std::filesystem::path(exePath).parent_path()
            / L"T7Patch" / L"t7patch_overlay.log";

        FILE* f = _wfopen(path.c_str(), L"a+");
        if (!f)
            return;
        SYSTEMTIME st{};
        GetLocalTime(&st);
        fprintf(f, "[%02u:%02u:%02u.%03u] %s\n",
            st.wHour, st.wMinute, st.wSecond, st.wMilliseconds, msg);
        fclose(f);
    }

    LRESULT CALLBACK OverlayWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam);
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
        const char* interceptionsFmt;
        const char* language;
        const char* hotkey;
        const char* pressAnyKey;
        const char* hint;
        const char* blockShaderTip;
        const char* friendsOnlyTip;
    };

    constexpr MenuText kTextZh = {
        "设置", "开关", "状态", "配置",
        "玩家昵称", "房间密码", "保存",
        "仅好友可加入", "屏蔽旧着色器编译器",
        "运行时长：%02u:%02u:%02u",
        "本次拦截旧着色器调用：%d 次",
        "语言", "呼出按键", "请按下新按键…",
        "按 %s 呼出/隐藏本窗口",
        "在进程内拦截旧版 d3dcompiler_46.dll。\n"
        "修复地图加载 / 首次特效时的卡顿。\n"
        "保存到 t7patch.conf，重启后保持。",
        "仅好友可以邀请/加入你。\n"
        "立即生效并保存到 t7patch.conf。"
    };
    constexpr MenuText kTextEn = {
        "SETTINGS", "TOGGLES", "STATUS", "CONFIG",
        "Player name", "Room password", "Save",
        "Friends only", "Block legacy shader compiler",
        "Session uptime: %02u:%02u:%02u",
        "d3dcompiler_46 interceptions this session: %d",
        "Language", "Hotkey", "Press any key...",
        "Press %s to toggle this window",
        "Intercepts the legacy d3dcompiler_46.dll in-process.\n"
        "Fixes the map-load / first-effect hitching.\n"
        "Saved to t7patch.conf, survives restarts.",
        "Only friends can invite/join you.\n"
        "Applies instantly and saves to t7patch.conf."
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

    // Small language selector button: the active language is drawn in accent.
    bool LangButton(const char* label, bool active)
    {
        if (active)
            ImGui::PushStyleColor(ImGuiCol_Button, kAccent);
        const bool clicked = ImGui::Button(label, ImVec2(56.0f, 0.0f));
        if (active)
            ImGui::PopStyleColor();
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
        const float boxY = pos.y + (totalHeight - boxSize) * 0.5f;

        ImGui::InvisibleButton(label,
            ImVec2(boxSize + style.ItemInnerSpacing.x + labelSize.x, totalHeight));
        const bool clicked = ImGui::IsItemClicked();
        if (clicked)
            *v = !*v;

        ImDrawList* dl = ImGui::GetWindowDrawList();
        const ImU32 fill = IM_COL32(255, 117, 1, 255);   // #FF7501
        const ImU32 outline = IM_COL32(150, 90, 20, 255);
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

        dl->AddText(ImVec2(p1.x + style.ItemInnerSpacing.x,
                pos.y + (totalHeight - lineHeight) * 0.5f),
            ImGui::GetColorU32(ImGuiCol_Text), label);

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
            // Player name: the conf value wins; when the conf has none, show
            // the game's CURRENT name so the box is never blank and the user
            // sees what the game is actually using.
            const char* confName = t7patch_cfg_playername();
            if (confName && confName[0] != '\0')
                strncpy_s(g_playerNameBuf, sizeof(g_playerNameBuf), confName, _TRUNCATE);
            else
                strncpy_s(g_playerNameBuf, sizeof(g_playerNameBuf),
                    t7patch_game_playername(), _TRUNCATE);

            strncpy_s(g_passwordBuf, sizeof(g_passwordBuf),
                t7patch_cfg_network_password(), _TRUNCATE);
            g_editBufsLoaded = true;
        }

        // [LOCAL] Fixed layout: the panel is laid out for exactly this size.
        // ImGuiCond_Always pins it every frame (imgui.ini cannot override),
        // the constraints lock out edges-dragging, and the NoScrollbar flags
        // keep the chrome clean.  Width was trimmed ~14% (fields do not need
        // that much room); height has slack so nothing gets clipped.
        const ImVec2 kPanelSize(395.0f, 415.0f);
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
                ImGui::InputText("##playername", g_playerNameBuf, sizeof(g_playerNameBuf));
                ImGui::TableSetColumnIndex(2);
                if (ImGui::Button("Save##playername", ImVec2(-FLT_MIN, 0.0f)))
                {
                    t7patch_cfg_set_playername(g_playerNameBuf);
                    t7patch_config_save();
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
            bool block46 = hooks::IsD3DCompilerBlockEnabled();
            if (SolidCheckbox(L()->blockShader, &block46))
                hooks::SetD3DCompilerBlock(block46);
            if (ImGui::IsItemHovered())
                ImGui::SetTooltip("%s", L()->blockShaderTip);

            // [LOCAL] All switches live together in this card - friends-only
            // used to sit in the settings table and looked out of place
            // between two text fields.
            bool friendsOnly = t7patch_cfg_friends_only();
            if (SolidCheckbox(L()->friendsOnly, &friendsOnly))
            {
                t7patch_cfg_set_friends_only(friendsOnly);
                t7patch_config_save();
            }
            if (ImGui::IsItemHovered())
                ImGui::SetTooltip("%s", L()->friendsOnlyTip);
        }
        EndCard();

        BeginCard(L()->config);
        {
            // Language: two small buttons, the active one drawn in accent.
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
            ImGui::TextUnformatted(L()->hotkey);
            ImGui::SameLine(100.0f);
            if (g_capturingHotkey.load())
            {
                ImGui::TextColored(kAccent, "%s", L()->pressAnyKey);
            }
            else if (ImGui::Button(VkName(t7patch_menu_key()), ImVec2(90.0f, 0.0f)))
            {
                g_capturingHotkey = true;
            }
        }
        EndCard();

        {
            char hint[128]{};
            snprintf(hint, sizeof(hint), L()->hint, VkName(t7patch_menu_key()));
            ImGui::TextDisabled("%s", hint);
        }

        ImGui::End();
    }

    // -----------------------------------------------------------------
    //  Init helpers
    // -----------------------------------------------------------------
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
                io.Fonts->AddFontDefault();
        }

        if (!ImGui_ImplWin32_Init(g_hwnd))
            return false;
        if (!ImGui_ImplDX11_Init(g_device, g_context))
            return false;

        g_imguiReady = true;
        // [LOCAL] menu_auto_open fires later, on the first DLC ownership
        // query (main menu reached) - see NotifyMainMenuReached().
        g_menuOpen = false;
        return true;
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
        if (g_imguiReady)
        {
            ImGui_ImplDX11_NewFrame();
            ImGui_ImplWin32_NewFrame();
            ImGui::NewFrame();

            if (g_menuOpen)
                DrawMenu();

            ImGui::Render();
            ImGui_ImplDX11_RenderDrawData(ImGui::GetDrawData());
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

        // Menu hotkey.  WM_KEYDOWN repeat (bit 30) is ignored so holding the
        // key does not strobe the menu.
        // [LOCAL] Hotkey is gated on the main menu: during the intro movies
        // and the connect screen the game engine is still mid-init, and
        // opening the overlay there is both useless and a crash risk.
        if (msg == WM_KEYDOWN && wParam == (WPARAM)t7patch_menu_key() && !(lParam & 0x40000000))
        {
            if (!g_mainMenuReached)
            {
                overlay_log("hotkey ignored (main menu not reached yet)");
            }
            else
            {
                g_menuOpen = !g_menuOpen.load();
                if (g_menuOpen.load())
                    g_editBufsLoaded = false; // re-read the text buffers from the conf
                overlay_log(g_menuOpen.load() ? "menu OPEN (hotkey)" : "menu CLOSE (hotkey)");
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

    void NotifyMainMenuReached()
    {
        static bool notified = false;
        if (notified)
            return;
        notified = true;
        g_mainMenuReached = true;

        if (t7patch_menu_auto_open())
        {
            g_menuOpen = true;
            overlay_log("menu AUTO-OPENED (main menu reached, menu_auto_open=1)");
        }
        else
        {
            overlay_log("main menu reached (Insert now armed)");
        }
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
