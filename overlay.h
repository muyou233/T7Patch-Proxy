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
}
