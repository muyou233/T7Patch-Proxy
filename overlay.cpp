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
// Phase 1 scope: skeleton window only.  Config integration comes next.

#include "framework.h"
#include <d3d11.h>
#include <dxgi.h>
#include <dxgi1_2.h> // IDXGIFactory2 / CreateSwapChainForHwnd live here, not in dxgi.h
#include <dxgi1_4.h> // for future-proofing of factory interface queries
#include "overlay.h"
#include "Hooks.h" // [LOCAL] 46-block runtime toggle + interception counter
#include "imgui/imgui.h"
#include "imgui/backends/imgui_impl_dx11.h"
#include "imgui/backends/imgui_impl_win32.h"

// [LOCAL] The backend wraps this declaration in "#if 0" on purpose: callers
// are expected to copy it into their own .cpp (see imgui_impl_win32.h).
extern IMGUI_IMPL_API LRESULT ImGui_ImplWin32_WndProcHandler(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam);

#include <mutex>

namespace
{
    std::mutex g_overlayMutex;
    ID3D11Device* g_device = nullptr;
    ID3D11DeviceContext* g_context = nullptr;
    IDXGISwapChain* g_swapChain = nullptr;
    HWND g_hwnd = nullptr;

    bool g_imguiReady = false;
    bool g_menuOpen = false;
    bool g_mainMenuReached = false; // Insert is ignored until the main menu is up
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
        std::error_code error;
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
    void LoadBackgroundTextureLocked(); // [LOCAL] defined further below

    // -----------------------------------------------------------------
    //  Menu drawing (card layout: one bordered card per section, drawn over
    //  the key-art background; title bar kept, no collapsibles)
    // -----------------------------------------------------------------

    // Card helpers: a semi-transparent child so the artwork shows through
    // while text stays readable.  AutoResizeY keeps each card hugging its
    // content instead of stretching.
    void BeginCard(const char* title)
    {
        ImGui::PushStyleColor(ImGuiCol_ChildBg, IM_COL32(0, 0, 0, 150));
        ImGui::BeginChild(title, ImVec2(0.0f, 0.0f),
            ImGuiChildFlags_AutoResizeY | ImGuiChildFlags_Borders);
        ImGui::TextUnformatted(title);
        ImGui::Separator();
    }

    void EndCard()
    {
        ImGui::EndChild();
        ImGui::PopStyleColor();
        ImGui::Spacing();
    }

    void DrawMenu()
    {
        // Refresh the text edit buffers once per menu-open, so in-game edits
        // and manual conf edits never fight each other.  (The friends-only
        // checkbox reads/writes the config directly - no buffer involved.)
        if (!g_editBufsLoaded)
        {
            strncpy_s(g_playerNameBuf, sizeof(g_playerNameBuf),
                t7patch_cfg_playername(), _TRUNCATE);
            strncpy_s(g_passwordBuf, sizeof(g_passwordBuf),
                t7patch_cfg_network_password(), _TRUNCATE);
            g_editBufsLoaded = true;
        }

        ImGui::SetNextWindowSize(ImVec2(480.0f, 430.0f), ImGuiCond_FirstUseEver);
        // [LOCAL] NoCollapse: the window must not be collapsible into its
        // title bar (the "▼" arrow) - title stays, content always visible.
        if (!ImGui::Begin("T7Patch 3.07", &g_menuOpen, ImGuiWindowFlags_NoCollapse))
        {
            ImGui::End();
            return;
        }

        BeginCard("Status");
        {
            const ULONGLONG upSec = (GetTickCount64() - g_sessionStart) / 1000ULL;
            ImGui::Text("Session uptime: %02u:%02u:%02u",
                (unsigned)(upSec / 3600), (unsigned)((upSec / 60) % 60), (unsigned)(upSec % 60));
            ImGui::Text("d3dcompiler_46 interceptions this session: %d",
                hooks::GetD3DCompilerBlockCount());
        }
        EndCard();

        BeginCard("Toggles");
        {
            bool block46 = hooks::IsD3DCompilerBlockEnabled();
            if (ImGui::Checkbox("Block legacy d3dcompiler_46.dll (stutter fix)", &block46))
                hooks::SetD3DCompilerBlock(block46);
            if (ImGui::IsItemHovered())
                ImGui::SetTooltip("Intercepts the old shader compiler in-process.\n"
                    "Saved to t7patch.conf, survives restarts.");
        }
        EndCard();

        BeginCard("Settings");
        {
            // [LOCAL] Label on the LEFT of each field (ImGui's InputText puts
            // its label on the right by default; use a hidden "##id" label and
            // draw our own text first).  One Save button per row.
            ImGui::Text("Player name");
            ImGui::SameLine();
            ImGui::SetNextItemWidth(190.0f);
            ImGui::InputText("##playername", g_playerNameBuf, sizeof(g_playerNameBuf));
            ImGui::SameLine();
            if (ImGui::Button("Save##playername"))
            {
                t7patch_cfg_set_playername(g_playerNameBuf);
                t7patch_config_save();
            }

            bool friendsOnly = t7patch_cfg_friends_only();
            if (ImGui::Checkbox("Friends only (applies instantly)", &friendsOnly))
            {
                t7patch_cfg_set_friends_only(friendsOnly);
                t7patch_config_save();
            }

            ImGui::Text("Room password");
            ImGui::SameLine();
            ImGui::SetNextItemWidth(190.0f);
            ImGui::InputText("##password", g_passwordBuf, sizeof(g_passwordBuf),
                ImGuiInputTextFlags_Password);
            ImGui::SameLine();
            if (ImGui::Button("Save##password"))
            {
                t7patch_cfg_set_network_password(g_passwordBuf);
                t7patch_config_save();
            }
            ImGui::TextDisabled("Text fields commit on their Save button. Checkboxes apply on click.");
        }
        EndCard();

        ImGui::TextDisabled("Insert toggles this window (menu_key in t7patch.conf).");
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
            bool fontLoaded = false;
            const char* cjkFonts[] = {
                "C:\\Windows\\Fonts\\msyh.ttc",   // Microsoft YaHei (Win8+)
                "C:\\Windows\\Fonts\\msyh.ttf",
                "C:\\Windows\\Fonts\\simhei.ttf", // SimHei fallback
            };
            for (const char* fontPath : cjkFonts)
            {
                if (GetFileAttributesA(fontPath) == INVALID_FILE_ATTRIBUTES)
                    continue;
                if (io.Fonts->AddFontFromFileTTF(fontPath, 17.0f, nullptr,
                        io.Fonts->GetGlyphRangesChineseSimplifiedCommon()))
                {
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

    // Caller must hold g_overlayMutex.
    void OnSwapChainCaptured(IDXGISwapChain* swapChain)
    {
        std::lock_guard<std::mutex> lock(g_overlayMutex);
        if (g_swapChain) // already captured; Phase 1 ignores swap chain rebuilds
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
                g_menuOpen = !g_menuOpen;
                overlay_log(g_menuOpen ? "menu OPEN (hotkey)" : "menu CLOSE (hotkey)");
            }
        }

        if (g_imguiReady)
        {
            if (ImGui_ImplWin32_WndProcHandler(hwnd, msg, wParam, lParam) && g_menuOpen)
                return TRUE; // menu is open: input it consumed stays consumed
        }

        return CallWindowProc(g_origWndProc, hwnd, msg, wParam, lParam);
    }
} // namespace

namespace overlay
{
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

        g_device = static_cast<ID3D11Device*>(device);
        g_context = static_cast<ID3D11DeviceContext*>(immediateContext);

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
            g_device = static_cast<ID3D11Device*>(device);
            g_context = static_cast<ID3D11DeviceContext*>(immediateContext);
        }

        if (swapChain && !g_swapChain) // capture the first swap chain we see
            CaptureSwapChainLocked(static_cast<IDXGISwapChain*>(swapChain));
    }
} // namespace overlay
