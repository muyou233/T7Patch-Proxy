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
    bool g_wndProcHooked = false;
    WNDPROC g_origWndProc = nullptr;
    void* g_origPresent = nullptr;
    void** g_patchedVtableSlot = nullptr;
    void* g_origFactoryCreateSwapChain = nullptr;
    void** g_patchedFactorySlot = nullptr;
    void* g_origFactoryCreateSwapChainForHwnd = nullptr;
    void** g_patchedFactoryForHwndSlot = nullptr;

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

    // -----------------------------------------------------------------
    //  Menu drawing (Phase 1 skeleton)
    // -----------------------------------------------------------------
    void DrawMenu()
    {
        ImGui::SetNextWindowSize(ImVec2(430.0f, 260.0f), ImGuiCond_FirstUseEver);
        if (!ImGui::Begin("T7Patch 3.07", &g_menuOpen))
        {
            ImGui::End();
            return;
        }

        ImGui::Text("Overlay online.");
        ImGui::TextDisabled("Press Insert (configurable) to toggle this window.");
        ImGui::Separator();

        // Phase 2: wire the real config toggles in here.
        ImGui::TextDisabled("Settings integration: next phase");

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
        if (!ImGui_ImplWin32_Init(g_hwnd))
            return false;
        if (!ImGui_ImplDX11_Init(g_device, g_context))
            return false;

        g_imguiReady = true;
        g_menuOpen = t7patch_menu_auto_open(); // conf switch, default off
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
        if (msg == WM_KEYDOWN && wParam == (WPARAM)t7patch_menu_key() && !(lParam & 0x40000000))
        {
            g_menuOpen = !g_menuOpen;
            overlay_log(g_menuOpen ? "menu OPEN (hotkey)" : "menu CLOSE (hotkey)");
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
