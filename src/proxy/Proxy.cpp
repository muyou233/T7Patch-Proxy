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
//  d3d11.dll is D3D11CreateDevice).  The system copy at
//  %SystemRoot%\System32\d3d11.dll is never touched - we load the real one
//  by absolute path.
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
#include "overlay.h"      // [LOCAL] in-game ImGui overlay
#include "t7patch_log.h"  // [LOCAL] the patch's single runtime log

#include <atomic>
#include <cstdio>
#include <cwchar>

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
    //  Written to the patch's log (T7Patch\t7patch.log) so the start-up
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
    //  Everything lands in the patch's single log, T7Patch\t7patch.log (see
    //  t7patch_log.h), tagged "proxy".  DllMain creates that folder before any
    //  of this can run.
    //
    //  DllMain runs with the loader lock held, and opening a file there is not
    //  allowed.  Messages logged during that window are therefore buffered and
    //  written out by the first message after the lock is released (their
    //  timestamp is the flush moment, a few milliseconds later in practice).
    // =================================================================
    constexpr int kMaxPendingLogs = 4;
    constexpr int kLogLineSize = 320;

    char g_pendingLogs[kMaxPendingLogs][kLogLineSize] = {};
    int g_pendingLogCount = 0;
    std::atomic<bool> g_loaderLockHeld{ false };

    void ProxyLog(const char* text)
    {
        OutputDebugStringA(text);

        if (!kWriteLog) return;

        if (g_loaderLockHeld.load(std::memory_order_acquire))
        {
            if (g_pendingLogCount < kMaxPendingLogs)
                strcpy_s(g_pendingLogs[g_pendingLogCount++], text);
            return;
        }

        for (int i = 0; i < g_pendingLogCount; ++i)
            t7log::Append("proxy", g_pendingLogs[i]);
        g_pendingLogCount = 0;

        t7log::Append("proxy", text);
    }

    // =================================================================
    //  Load the D3D11 implementation this proxy forwards to.
    //
    //  Default: %SystemRoot%\System32\d3d11.dll, exactly as before.
    //
    //  Optional chain: when a second D3D11 implementation is dropped next
    //  to the game executable under one of kBackendNames, that one becomes
    //  the primary provider and System32 only fills the gaps.  This exists
    //  because only ONE file can hold the name "d3d11.dll" in the game
    //  folder - and that slot is this proxy - so a drop-in translation
    //  layer (DXVK and friends) has no way in unless we carry it.
    //
    //  Every slot is resolved backend-first and System32-second, so no
    //  forwarder can end up null.  The reason is the export surface: a
    //  translation layer implements the D3D11 entry points only, while
    //  System32 also exports the D3DKMT*/D3D11Core* ordinals this proxy
    //  has always forwarded.  Nothing is called from both sides for one
    //  operation - a call goes to whichever module provided that export,
    //  and the split is written to the log.
    //
    //  A translation layer is only coherent together with its own DXGI:
    //  the game imports dxgi.dll statically, so a backend paired with
    //  Microsoft's DXGI would build swap chains across two unrelated
    //  implementations.  The chain is therefore armed by a DXVK-built
    //  dxgi.dll actually sitting in the game folder - that file is the
    //  switch the player flips, and moving the pair together is what keeps
    //  both halves in step.  A backend without it is ignored on purpose.
    //
    //  With no backend file present, behaviour is unchanged: one
    //  LoadLibraryW and the same 51 GetProcAddress calls as before.
    // =================================================================
    constexpr const wchar_t* kBackendNames[] = {
        L"d3d11_backend.dll",   // preferred: the name says what it is
        L"d3d11_dxvk.dll",      // alias, for a plainly renamed DXVK copy
    };

    // The translation layer's DXGI - the file that arms the chain.
    constexpr const wchar_t* kTranslationDxgi = L"dxgi.dll";

    // Read bound for the banner check.  Every DXVK module carries "DXVK" in
    // its version string around 0.9 MB in, so 2 MB covers what we ship while
    // staying cheap.  The buffer is static because this runs once, inside
    // InitOnceExecuteOnce - there is no second caller to race with.
    constexpr DWORD kMarkerScanBytes = 2 * 1024 * 1024;

    bool FileCarriesDxvkBanner(const wchar_t* path)
    {
        HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
            nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (file == INVALID_HANDLE_VALUE)
        {
            return false;
        }

        static char buffer[kMarkerScanBytes];
        DWORD read = 0;
        const BOOL ok = ReadFile(file, buffer, kMarkerScanBytes, &read, nullptr);
        CloseHandle(file);

        if (!ok || read < 4)
        {
            return false;
        }

        for (DWORD i = 0; i + 4 <= read; ++i)
        {
            if (buffer[i] == 'D' && buffer[i + 1] == 'X' &&
                buffer[i + 2] == 'V' && buffer[i + 3] == 'K')
            {
                return true;
            }
        }
        return false;
    }

    BOOL CALLBACK ResolveRealD3D11(PINIT_ONCE, PVOID, PVOID*)
    {
        // Absolute paths on purpose: a bare "d3d11.dll" would resolve back
        // to this very module and recurse forever.
        wchar_t systemPath[MAX_PATH] = { 0 };
        const UINT len = GetSystemDirectoryW(systemPath, MAX_PATH);
        if (!len || len >= MAX_PATH - 16)
        {
            ProxyLog("proxy: GetSystemDirectoryW failed, cannot load real d3d11.dll");
            return TRUE;
        }

        wcscat_s(systemPath, L"\\d3d11.dll");

        // --- optional backend, sitting next to the game's own executable ---
        wchar_t gameDir[MAX_PATH] = { 0 };
        wchar_t backendPath[MAX_PATH] = { 0 };
        wchar_t dxgiPath[MAX_PATH] = { 0 };
        wchar_t confPath[MAX_PATH] = { 0 };
        HMODULE backend = nullptr;
        const wchar_t* backendName = nullptr;

        const DWORD exeLength = GetModuleFileNameW(nullptr, gameDir, MAX_PATH);
        if (exeLength > 0 && exeLength < MAX_PATH)
        {
            wchar_t* lastSlash = wcsrchr(gameDir, L'\\');
            if (lastSlash)
            {
                *(lastSlash + 1) = L'\0';

                // The chain is armed by the translation layer's DXGI, not by
                // the backend - see the note above.  Content decides, not the
                // file name: a plain copy of the system DXGI sitting there
                // would leave the renderer just as unbalanced as no DXGI.
                bool translationDxgi = false;
                dxgiPath[0] = L'\0';
                if (wcscat_s(dxgiPath, gameDir) == 0
                    && wcscat_s(dxgiPath, kTranslationDxgi) == 0
                    && GetFileAttributesW(dxgiPath) != INVALID_FILE_ATTRIBUTES)
                {
                    translationDxgi = FileCarriesDxvkBanner(dxgiPath);
                }

                if (translationDxgi)
                {
                    // DXVK looks at $DXVK_CONFIG_FILE before ./dxvk.conf, so
                    // its settings can live with T7Patch's files instead of
                    // adding one more entry to the game folder.  Anything the
                    // player set themselves wins.
                    confPath[0] = L'\0';
                    if (wcscat_s(confPath, gameDir) == 0
                        && wcscat_s(confPath, L"T7Patch\\dxvk\\dxvk.conf") == 0
                        && GetFileAttributesW(confPath) != INVALID_FILE_ATTRIBUTES
                        && GetEnvironmentVariableW(L"DXVK_CONFIG_FILE", nullptr, 0) == 0)
                    {
                        SetEnvironmentVariableW(L"DXVK_CONFIG_FILE", confPath);
                    }

                    for (const wchar_t* candidate : kBackendNames)
                    {
                        backendPath[0] = L'\0';
                        if (wcscat_s(backendPath, gameDir) != 0) continue;
                        if (wcscat_s(backendPath, candidate) != 0) continue;
                        if (GetFileAttributesW(backendPath) == INVALID_FILE_ATTRIBUTES) continue;

                        backend = LoadLibraryW(backendPath);
                        if (backend)
                        {
                            backendName = candidate;
                            break;
                        }
                        ProxyLog("proxy: D3D11 backend found but could not be loaded");
                    }

                    if (!backend)
                    {
                        // The DXGI the game already bound cannot be taken back,
                        // so the only honest move left is to say what happened.
                        ProxyLog("proxy: the game folder has a translation-layer dxgi.dll "
                            "but no d3d11 backend - move both files together");
                        t7patch_warn_startup_failure(
                            "The game folder holds a DXVK dxgi.dll without a d3d11 backend "
                            "next to it, so the renderer is running a mixed setup and the "
                            "game may fail to start.  Move d3d11_backend.dll and dxgi.dll "
                            "as a pair, or take both of them out of the game folder.");
                    }
                }
                else
                {
                    // A backend on its own is a trap: the game would bind
                    // Microsoft's DXGI and never reach it.  Say so once rather
                    // than let the player wonder why nothing changed.
                    for (const wchar_t* candidate : kBackendNames)
                    {
                        backendPath[0] = L'\0';
                        if (wcscat_s(backendPath, gameDir) != 0) continue;
                        if (wcscat_s(backendPath, candidate) != 0) continue;
                        if (GetFileAttributesW(backendPath) == INVALID_FILE_ATTRIBUTES) continue;

                        ProxyLog("proxy: D3D11 backend present without a translation-layer "
                            "dxgi.dll - backend ignored, the two files move as a pair");
                        break;
                    }
                }
            }
        }

        g_realD3D11 = LoadLibraryW(systemPath);
        if (!g_realD3D11 && !backend)
        {
            ProxyLog("proxy: could not load the real System32\\d3d11.dll");
            return TRUE;
        }

        int fromBackend = 0;
        int fromSystem = 0;
        int missing = 0;
        for (int i = 0; i < kExportCount; ++i)
        {
            void* entry = backend
                ? reinterpret_cast<void*>(GetProcAddress(backend, kExportNames[i]))
                : nullptr;

            if (entry)
            {
                ++fromBackend;
            }
            else if (g_realD3D11)
            {
                entry = reinterpret_cast<void*>(GetProcAddress(g_realD3D11, kExportNames[i]));
                if (entry) ++fromSystem;
            }

            g_d3d11Targets[i] = entry;

            if (!entry)
            {
                ++missing;
                char msg[256] = { 0 };
                sprintf_s(msg, "proxy: no provider for export \"%s\" (ordinal %d)",
                    kExportNames[i], i);
                ProxyLog(msg);
            }
        }

        g_realCreateDevice = reinterpret_cast<PFN_D3D11CreateDevice>(
            g_d3d11Targets[21]);
        g_realCreateDeviceAndSwapChain = reinterpret_cast<PFN_D3D11CreateDeviceAndSwapChain>(
            g_d3d11Targets[22]);

        if (backend)
        {
            char msg[256] = { 0 };
            sprintf_s(msg,
                "proxy: D3D11 backend \"%ls\" in use (%d exports), System32 fills %d, %d missing",
                backendName, fromBackend, fromSystem, missing);
            ProxyLog(msg);
        }
        else
        {
            ProxyLog("proxy: real d3d11.dll resolved");
        }
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
            // [LOCAL] Name the two numbers the check above compared, in the log
            // and in the notice the player gets.  Without them a "the patch
            // stopped working" report cannot be told apart from "the game was
            // updated again", which is the case this guard exists for.  Both
            // read 0x00000000 when the headers could not be parsed at all.
            char unsupportedReason[160] = { 0 };
            const auto fingerprint = bo3::read_fingerprint();
            sprintf_s(unsupportedReason,
                "unsupported Black Ops III build (timestamp 0x%08X, image size 0x%08X)",
                static_cast<unsigned int>(fingerprint.timeDateStamp),
                static_cast<unsigned int>(fingerprint.imageSize));

            char unsupportedMsg[224] = { 0 };
            sprintf_s(unsupportedMsg, "proxy: %s, T7Patch not applied", unsupportedReason);
            ProxyLog(unsupportedMsg);

            // [LOCAL] And tell the player, not just the log.  Doing nothing in
            // silence is indistinguishable from a broken install, and this is
            // the one failure the user can act on (verify the game files, or
            // wait for a patch release that follows the game update).  The
            // notice runs on its own thread, so nothing here is blocked.
            t7patch_warn_startup_failure(unsupportedReason);
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
    {
        StartPatchOnce();
        overlay::OnDeviceCreated(ppDevice ? *ppDevice : nullptr,
            ppImmediateContext ? *ppImmediateContext : nullptr);
    }

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
    {
        StartPatchOnce();
        overlay::OnSwapChainCreated(
            ppSwapChain ? *ppSwapChain : nullptr,
            ppDevice ? *ppDevice : nullptr,
            ppImmediateContext ? *ppImmediateContext : nullptr);
    }

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
