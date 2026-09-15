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

    // [LOCAL] Called by Protection.cpp when the overlay gate opens - and since
    // 2026-09-15 the only way it can open is the measured main-menu label signal
    // (the timer fallback was removed; see MainThread).  Arms the hotkey
    // immediately, and when menu_auto_open is set *schedules* the menu to open
    // 1.5 s later (a menu that is already on screen the instant the player
    // arrives reads as "it was waiting for me" - see kAutoOpenDelayMs); a press
    // of the hotkey in the meantime cancels the scheduled open.  `reason` is what
    // gets logged, so the log always says WHICH signal opened the gate.
    void NotifyMainMenuReached(const char* reason = "main menu reached");

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
