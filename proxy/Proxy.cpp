// =====================================================================
//  proxy/Proxy.cpp
// ---------------------------------------------------------------------
//  d3d11.dll proxy front-end for T7Patch.
//
//  WHY THIS EXISTS
//  ---------------
//  T7Patch is normally installed by running T7Patch.exe, which has to be
//  started next to the game and then injects T7Patch.dll into a running
//  Black Ops III process.  This file turns the very same DLL into a
//  drop-in proxy: rename the build output to "d3d11.dll", copy it into
//  the Black Ops III folder, and the game loads it by itself.
//
//  It works because BlackOps3.exe carries a *static* import of d3d11.dll
//  (verified against the retail binary: the only function it imports from
//  d3d11.dll is D3D11CreateDevice).  Changing %SystemRoot%\System32\
//  d3d11.dll is never touched - we load the real one by absolute path.
//
//  WHAT IT DOES NOT DO
//  -------------------
//  Nothing inside T7Patch itself is modified.  RunPatching() in
//  dllmain.cpp is called exactly as the injector would call it, with the
//  same configuration file (t7patch.conf) and the same behaviour.
//
//  HOW THE TIMING IS CHOSEN
//  ------------------------
//  A static import means our DllMain runs while the loader lock is held,
//  long before the engine exists.  Calling RunPatching() at that point
//  would crash: Protection::install() dereferences engine globals (dvar
//  table, lobby module) that are not built yet.
//
//  So instead we intercept D3D11CreateDevice - the moment the renderer
//  spins up.  By then the game has started for real, the loader lock is
//  long gone, and we are still far ahead of the main menu.  The patch is
//  then applied from a dedicated worker thread so the renderer thread is
//  never blocked.
// =====================================================================

#include "framework.h"

#include <atomic>
#include <cstdio>
#include <cwchar>

// [LOCAL] Same folder as t7patch.conf / crashes.log.
#define PROXY_LOG_FILE T7PATCH_DATA_DIR "\\t7patch_proxy.log"

// ---------------------------------------------------------------------
//  Provided by proxy/thunks.asm
// ---------------------------------------------------------------------
extern "C" void* g_d3d11Targets[51];

// ---------------------------------------------------------------------
//  Provided by dllmain.cpp - behaviour intentionally unchanged.
// ---------------------------------------------------------------------
void RunPatching();

namespace
{
    // =================================================================
    //  Tuning knobs
    // =================================================================
    //  Written to t7patch_proxy.log next to the DLL so the start-up
    //  sequence can be verified on a first run.
    constexpr bool kWriteLog = true;

    //  How long to wait for the engine's dvar table to appear before we
    //  give up waiting and just go ahead anyway.
    constexpr ULONGLONG kDvarWaitTimeoutMs = 30000;

    //  Extra grace period after the dvar table shows up, letting the rest
    //  of engine start-up finish before T7Patch touches it.
    //
    //  Back to 1500 after the 0 ms experiment.  With 0, the game failed to
    //  start on the first of two consecutive launches and worked on the
    //  second; the crash dump shows an access violation executing at an
    //  address outside every loaded module (DEP fault).  Intermittent
    //  control-flow corruption is exactly what patching code bytes while the
    //  renderer is still mid-initialisation can produce, so the safety margin
    //  goes back in.
    //
    //  Do not lower this again without a long soak test (many launches).
    constexpr DWORD kSettleMs = 1500;

    //  Engine global that Protection::install() dereferences while setting
    //  ui_error_callstack_ship / g_allowvote / maxvoicepacketsperframe.
    //  It is null until the dvar table has been published, which makes it
    //  a cheap and precise "engine is up" probe.  (Same address that
    //  Protection.cpp reads when it clears the dvar flags.)
    constexpr std::uintptr_t kDvarTableRva = 0x1686ED20;

    // =================================================================
    //  Export surface of the real d3d11.dll, indexed by ordinal.
    //  Keep in sync with proxy/d3d11.def and proxy/thunks.asm.
    // =================================================================
    constexpr int kExportCount = 51;

    constexpr const char* kExportNames[kExportCount] = {
        "D3D11CreateDeviceForD3D12",              //  0
        "D3DKMTCloseAdapter",                     //  1
        "D3DKMTDestroyAllocation",                //  2
        "D3DKMTDestroyContext",                   //  3
        "D3DKMTDestroyDevice",                    //  4
        "D3DKMTDestroySynchronizationObject",     //  5
        "D3DKMTPresent",                          //  6
        "D3DKMTQueryAdapterInfo",                 //  7
        "D3DKMTSetDisplayPrivateDriverFormat",    //  8
        "D3DKMTSignalSynchronizationObject",      //  9
        "D3DKMTUnlock",                           // 10
        "D3DKMTWaitForSynchronizationObject",     // 11
        "EnableFeatureLevelUpgrade",              // 12
        "OpenAdapter10",                          // 13
        "OpenAdapter10_2",                        // 14
        "CreateDirect3D11DeviceFromDXGIDevice",   // 15
        "CreateDirect3D11SurfaceFromDXGISurface", // 16
        "D3D11CoreCreateDevice",                  // 17
        "D3D11CoreCreateLayeredDevice",           // 18
        "D3D11CoreGetLayeredDeviceSize",          // 19
        "D3D11CoreRegisterLayers",                // 20
        "D3D11CreateDevice",                      // 21  (Proxy.cpp)
        "D3D11CreateDeviceAndSwapChain",          // 22  (Proxy.cpp)
        "D3D11On12CreateDevice",                  // 23
        "D3DKMTCreateAllocation",                 // 24
        "D3DKMTCreateContext",                    // 25
        "D3DKMTCreateDevice",                     // 26
        "D3DKMTCreateSynchronizationObject",      // 27
        "D3DKMTEscape",                           // 28
        "D3DKMTGetContextSchedulingPriority",     // 29
        "D3DKMTGetDeviceState",                   // 30
        "D3DKMTGetDisplayModeList",               // 31
        "D3DKMTGetMultisampleMethodList",         // 32
        "D3DKMTGetRuntimeData",                   // 33
        "D3DKMTGetSharedPrimaryHandle",           // 34
        "D3DKMTLock",                             // 35
        "D3DKMTOpenAdapterFromHdc",               // 36
        "D3DKMTOpenResource",                     // 37
        "D3DKMTQueryAllocationResidency",         // 38
        "D3DKMTQueryResourceInfo",                // 39
        "D3DKMTRender",                           // 40
        "D3DKMTSetAllocationPriority",            // 41
        "D3DKMTSetContextSchedulingPriority",     // 42
        "D3DKMTSetDisplayMode",                   // 43
        "D3DKMTSetGammaRamp",                     // 44
        "D3DKMTSetVidPnSourceOwner",              // 45
        "D3DKMTWaitForVerticalBlankEvent",        // 46
        "D3DPerformance_BeginEvent",              // 47
        "D3DPerformance_EndEvent",                // 48
        "D3DPerformance_GetStatus",               // 49
        "D3DPerformance_SetMarker",               // 50
    };

    // =================================================================
    //  Real d3d11.dll entry points we call through.
    // =================================================================
    using PFN_D3D11CreateDevice = HRESULT(WINAPI*)(
        void* pAdapter,
        int DriverType,
        HMODULE Software,
        UINT Flags,
        const int* pFeatureLevels,
        UINT FeatureLevels,
        UINT SDKVersion,
        void** ppDevice,
        int* pFeatureLevel,
        void** ppImmediateContext);

    using PFN_D3D11CreateDeviceAndSwapChain = HRESULT(WINAPI*)(
        void* pAdapter,
        int DriverType,
        HMODULE Software,
        UINT Flags,
        const int* pFeatureLevels,
        UINT FeatureLevels,
        UINT SDKVersion,
        const void* pSwapChainDesc,
        void** ppSwapChain,
        void** ppDevice,
        int* pFeatureLevel,
        void** ppImmediateContext);

    HMODULE g_realD3D11 = nullptr;
    PFN_D3D11CreateDevice g_realCreateDevice = nullptr;
    PFN_D3D11CreateDeviceAndSwapChain g_realCreateDeviceAndSwapChain = nullptr;

    INIT_ONCE g_resolveOnce = INIT_ONCE_STATIC_INIT;
    std::atomic<bool> g_patchStarted{ false };

    // =================================================================
    //  Logging (best effort - never blocks or fails the game start-up)
    //
    //  Lands in the same "T7Patch" folder as t7patch.conf.  DllMain creates
    //  that folder before any of this can run.
    //
    //  DllMain runs with the loader lock held, and opening a file there is not
    //  allowed.  Messages logged during that window are therefore buffered and
    //  written out by the first message after the lock is released, keeping
    //  their original timestamps.
    // =================================================================
    constexpr int kMaxPendingLogs = 4;
    constexpr int kLogLineSize = 320;

    char g_pendingLogs[kMaxPendingLogs][kLogLineSize] = {};
    int g_pendingLogCount = 0;
    std::atomic<bool> g_loaderLockHeld{ false };

    void FormatLogLine(char* out, size_t outSize, const char* text)
    {
        SYSTEMTIME st{};
        GetLocalTime(&st);
        // _snprintf_s with _TRUNCATE rather than sprintf_s: an over-long
        // message must not trip the invalid-parameter handler, which would
        // abort the game process.
        _snprintf_s(out, outSize, _TRUNCATE, "[%02u:%02u:%02u.%03u] %s",
            st.wHour, st.wMinute, st.wSecond, st.wMilliseconds, text);
    }

    void ProxyLog(const char* text)
    {
        OutputDebugStringA(text);

        if (!kWriteLog) return;

        char line[kLogLineSize] = { 0 };
        FormatLogLine(line, kLogLineSize, text);

        if (g_loaderLockHeld.load(std::memory_order_acquire))
        {
            if (g_pendingLogCount < kMaxPendingLogs)
                strcpy_s(g_pendingLogs[g_pendingLogCount++], line);
            return;
        }

        // [LOCAL] Cap the log size: once t7patch_proxy.log grows past 64 KB,
        // rotate it to t7patch_proxy.log.old (replacing any previous .old) so
        // the file can never grow without bound while keeping one generation
        // of history for debugging.
        WIN32_FILE_ATTRIBUTE_DATA logAttr = {};
        if (GetFileAttributesExA(PROXY_LOG_FILE, GetFileExInfoStandard, &logAttr))
        {
            const long long logSize =
                ((long long)logAttr.nFileSizeHigh << 32) | logAttr.nFileSizeLow;
            if (logSize > 64 * 1024)
                MoveFileExA(PROXY_LOG_FILE, PROXY_LOG_FILE ".old",
                            MOVEFILE_REPLACE_EXISTING);
        }

        FILE* f = nullptr;
        if (fopen_s(&f, PROXY_LOG_FILE, "a") != 0 || !f) return;

        for (int i = 0; i < g_pendingLogCount; ++i)
            fprintf(f, "%s\n", g_pendingLogs[i]);
        g_pendingLogCount = 0;

        fprintf(f, "%s\n", line);
        fclose(f);
    }

    // =================================================================
    //  Load the genuine d3d11.dll from System32 and wire up every
    //  forwarder slot.
    // =================================================================
    BOOL CALLBACK ResolveRealD3D11(PINIT_ONCE, PVOID, PVOID*)
    {
        // Absolute path on purpose: a bare "d3d11.dll" would resolve back
        // to this very module and recurse forever.
        wchar_t path[MAX_PATH] = { 0 };
        const UINT len = GetSystemDirectoryW(path, MAX_PATH);
        if (!len || len >= MAX_PATH - 16)
        {
            ProxyLog("proxy: GetSystemDirectoryW failed, cannot load real d3d11.dll");
            return TRUE;
        }

        wcscat_s(path, L"\\d3d11.dll");

        g_realD3D11 = LoadLibraryW(path);
        if (!g_realD3D11)
        {
            ProxyLog("proxy: could not load the real System32\\d3d11.dll");
            return TRUE;
        }

        for (int i = 0; i < kExportCount; ++i)
        {
            g_d3d11Targets[i] = reinterpret_cast<void*>(
                GetProcAddress(g_realD3D11, kExportNames[i]));

            if (!g_d3d11Targets[i])
            {
                char msg[256] = { 0 };
                sprintf_s(msg, "proxy: real d3d11.dll has no export \"%s\" (ordinal %d)",
                    kExportNames[i], i);
                ProxyLog(msg);
            }
        }

        g_realCreateDevice = reinterpret_cast<PFN_D3D11CreateDevice>(
            g_d3d11Targets[21]);
        g_realCreateDeviceAndSwapChain = reinterpret_cast<PFN_D3D11CreateDeviceAndSwapChain>(
            g_d3d11Targets[22]);

        ProxyLog("proxy: real d3d11.dll resolved");
        return TRUE;
    }

    void EnsureRealD3D11()
    {
        InitOnceExecuteOnce(&g_resolveOnce, ResolveRealD3D11, nullptr, nullptr);
    }

    // =================================================================
    //  Deciding *when* T7Patch is allowed to start.
    // =================================================================
    bool CallerIsMainExecutable(const void* returnAddress)
    {
        HMODULE owner = nullptr;
        if (!RtlPcToFileHeader(const_cast<void*>(returnAddress),
                reinterpret_cast<PVOID*>(&owner)))
            return false;

        return owner != nullptr && owner == GetModuleHandleW(nullptr);
    }

    DWORD WINAPI PatchWorker(LPVOID)
    {
        // Refuse to do anything in a process that is not a known Black Ops
        // III build.  Any other application could in principle load this
        // file by accident, and the hard-coded offsets below would be
        // meaningless there.
        if (!bo3::supported_build())
        {
            ProxyLog("proxy: unsupported executable, T7Patch not applied");
            return 0;
        }

        // Wait for the engine to publish its dvar table before handing
        // over to T7Patch.
        ULONGLONG waited = 0;
        while (waited < kDvarWaitTimeoutMs)
        {
            if (*reinterpret_cast<volatile INT64*>(REBASE(kDvarTableRva)) != 0)
                break;
            Sleep(50);
            waited += 50;
        }

        char msg[160] = { 0 };
        sprintf_s(msg, "proxy: dvar table ready after %llu ms, settling %u ms",
            waited, kSettleMs);
        ProxyLog(msg);

        Sleep(kSettleMs);

        ProxyLog("proxy: calling RunPatching()");
        RunPatching();
        ProxyLog("proxy: RunPatching() returned");

        return 0;
    }

    void StartPatchOnce()
    {
        bool expected = false;
        if (!g_patchStarted.compare_exchange_strong(expected, true))
            return;

        ProxyLog("proxy: D3D11 device created by the game, starting T7Patch");

        if (!CreateThread(nullptr, 0, PatchWorker, nullptr, 0, nullptr))
        {
            ProxyLog("proxy: CreateThread failed");
            return;
        }
    }
}

// =====================================================================
//  The two intercepted entry points.
//
//  Both call straight through to the real d3d11.dll first, so device
//  creation is never delayed or altered, and only then consider waking
//  T7Patch up - never from inside the renderer's own call stack.
// =====================================================================

extern "C" HRESULT WINAPI D3D11CreateDevice(
    void* pAdapter,
    int DriverType,
    HMODULE Software,
    UINT Flags,
    const int* pFeatureLevels,
    UINT FeatureLevels,
    UINT SDKVersion,
    void** ppDevice,
    int* pFeatureLevel,
    void** ppImmediateContext)
{
    // _ReturnAddress() has to be sampled here, not inside a helper, so
    // that it really is our caller.
    const void* caller = _ReturnAddress();

    EnsureRealD3D11();
    if (!g_realCreateDevice)
        return E_FAIL;

    const HRESULT hr = g_realCreateDevice(pAdapter, DriverType, Software, Flags,
        pFeatureLevels, FeatureLevels, SDKVersion,
        ppDevice, pFeatureLevel, ppImmediateContext);

    // Trigger on any call from the game, not only a successful one.  A failed
    // device creation (driver problem, the safe-mode prompt, ...) must not
    // quietly disable T7Patch: RunPatching() does not need the device to exist,
    // and the dvar / Steam / lobby gates in PatchWorker are what actually keep
    // it safe.  This also matches what the T7Patch.exe injector does.
    if (CallerIsMainExecutable(caller))
        StartPatchOnce();

    return hr;
}

extern "C" HRESULT WINAPI D3D11CreateDeviceAndSwapChain(
    void* pAdapter,
    int DriverType,
    HMODULE Software,
    UINT Flags,
    const int* pFeatureLevels,
    UINT FeatureLevels,
    UINT SDKVersion,
    const void* pSwapChainDesc,
    void** ppSwapChain,
    void** ppDevice,
    int* pFeatureLevel,
    void** ppImmediateContext)
{
    const void* caller = _ReturnAddress();

    EnsureRealD3D11();
    if (!g_realCreateDeviceAndSwapChain)
        return E_FAIL;

    const HRESULT hr = g_realCreateDeviceAndSwapChain(pAdapter, DriverType, Software,
        Flags, pFeatureLevels, FeatureLevels, SDKVersion, pSwapChainDesc,
        ppSwapChain, ppDevice, pFeatureLevel, ppImmediateContext);

    // See the note in D3D11CreateDevice: a failed creation must not stop
    // T7Patch from loading.
    if (CallerIsMainExecutable(caller))
        StartPatchOnce();

    return hr;
}

// =====================================================================
//  Called from DllMain so that every forwarder slot in proxy/thunks.asm
//  points at a real d3d11.dll entry point before any module can reach
//  one.  D3D11CreateDevice would resolve lazily anyway, but a module
//  importing one of the D3DKMT*/D3DPerformance_* entries would not.
// =====================================================================
extern "C" void ProxyResolveExports()
{
    // We are inside DllMain here, i.e. the loader lock is held.  Nothing on
    // this path may open a file, so ProxyLog defers its writes for the
    // duration and the next message flushes them.
    g_loaderLockHeld.store(true, std::memory_order_release);
    EnsureRealD3D11();
    g_loaderLockHeld.store(false, std::memory_order_release);
}
