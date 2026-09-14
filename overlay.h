// overlay.h - in-game ImGui overlay for T7Patch
//
// The overlay is wired onto the swap chain's Present entry point.  Two paths
// lead there, both driven from the proxy's intercepted D3D11 entry points:
//   - D3D11CreateDeviceAndSwapChain hands us the swap chain directly
//   - D3D11CreateDevice only hands us the device, so we hook the DXGI
//     factory's CreateSwapChain to capture it when the game creates one
#pragma once

namespace overlay
{
    // Called from proxy/Proxy.cpp after a successful D3D11CreateDevice.
    // Pointers may be null on failure; the overlay ignores those.
    void OnDeviceCreated(void* device, void* immediateContext);

    // Called from proxy/Proxy.cpp after a successful
    // D3D11CreateDeviceAndSwapChain.
    void OnSwapChainCreated(void* swapChain, void* device, void* immediateContext);

    // [LOCAL] Called by Protection.cpp once the overlay gate opens (online
    // Demonware sign-in, or the front-end-uptime fallback when the game is
    // offline - see MainThread).  Arms the hotkey, and opens the menu right
    // away when menu_auto_open is set.
    void NotifyMainMenuReached();

    // [LOCAL] Write a line to the patch's log (T7Patch\t7patch.log, tagged
    // "overlay") from other translation units - Protection.cpp's gate, Hooks.cpp's
    // UI-model observer.
    void DebugLog(const char* msg);

    // [LOCAL] GetTickCount64() stamp of the moment the user dismissed the
    // front-end's "press ENTER" title screen (0 = not dismissed yet).  This is
    // the gate signal: it is the only measured event that actually separates
    // that screen from the main menu (see OverlayWndProc).
    unsigned long long TitleScreenDismissedMs();
}
