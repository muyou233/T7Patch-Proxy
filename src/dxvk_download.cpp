#include "dxvk_download.h"

#include "framework.h"
#include "t7patch_log.h" // [LOCAL] one line per attempt

#include <atomic>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>

#include <bcrypt.h>
#include <winhttp.h>

#pragma comment(lib, "bcrypt.lib")
#pragma comment(lib, "winhttp.lib")

// Windows 8.1+ picks up the system proxy automatically; on anything older the
// constant does not exist and we fall back to the registry-configured proxy.
#ifndef WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY
#define WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY 4
#endif

namespace dxvk_download
{
    namespace
    {
        // ---- the payload -------------------------------------------------
        //
        // One entry per file the chained backend needs, each with the SHA-256
        // of the exact upstream build we ship and the mirrors that publish
        // it.  Both hashes were taken from the copies committed under /dxvk
        // in this repository - the download exists to reproduce THOSE bytes.
        struct File
        {
            const char* name;          // also the on-disk file name
            const wchar_t* urls[2];    // jsDelivr first, GitHub raw second
            const char* sha256Hex;     // locked integrity of the payload
        };
        constexpr File kFiles[] =
        {
            {
                "d3d11_backend.dll",
                {
                    L"https://cdn.jsdelivr.net/gh/muyou233/T7Patch-Proxy@main"
                    L"/dxvk/d3d11_backend.dll",
                    L"https://raw.githubusercontent.com/muyou233/T7Patch-Proxy"
                    L"/main/dxvk/d3d11_backend.dll",
                },
                "0A203B6255C893430F0A8461C618962DF04E62AA41538D5A875B21868317CF9F",
            },
            {
                "dxgi.dll",
                {
                    L"https://cdn.jsdelivr.net/gh/muyou233/T7Patch-Proxy@main"
                    L"/dxvk/dxgi.dll",
                    L"https://raw.githubusercontent.com/muyou233/T7Patch-Proxy"
                    L"/main/dxvk/dxgi.dll",
                },
                "E3C1178EB7F0DD59F91BCFCC257549E5B9CFDB5E8508719293DE7F8704F53160",
            },
        };

        // The larger of the two payloads is 7.5 MB; anything past this cap is
        // an error page or a stuck socket, not a DXVK module.
        constexpr size_t kMaxDownload = 24u * 1024u * 1024u;

        // Cooldown between two SUCCESSFUL runs - same reasoning as the
        // dictionary: a failure must never start it, or a player on a slow
        // connection would be locked out of retrying.  Re-clicking after a
        // good run only re-verifies the local files, so the cooldown costs
        // nothing real.
        constexpr unsigned kCooldownMs = 60u * 1000u;

        std::atomic<int> g_state{ static_cast<int>(State::Idle) };
        std::atomic<unsigned long long> g_lastRunMs{ 0 };
        std::atomic<unsigned long long> g_downloadedKiB{ 0 };
        std::mutex g_messageMutex;
        char g_message[192] = {};

        void Logf(const char* fmt, ...)
        {
            char msg[512] = {};
            va_list ap;
            va_start(ap, fmt);
            vsnprintf(msg, sizeof(msg), fmt, ap);
            va_end(ap);
            t7log::Append("dxvk", msg);
        }

        void SetMessage(const char* fmt, ...)
        {
            std::lock_guard<std::mutex> lock(g_messageMutex);
            va_list ap;
            va_start(ap, fmt);
            vsnprintf(g_message, sizeof(g_message), fmt, ap);
            va_end(ap);
        }

        void Fail(const char* fmt, ...)
        {
            char msg[512] = {};
            va_list ap;
            va_start(ap, fmt);
            vsnprintf(msg, sizeof(msg), fmt, ap);
            va_end(ap);

            SetMessage("%s", msg);
            g_state.store(static_cast<int>(State::Failed));
            Logf("dxvk download failed: %s", msg);
        }

        // SHA-256 over Windows CNG: no third-party crypto comes in with this.
        // The whole blob is in memory by the time we get here (see HttpGet),
        // so a single hash update is fine.
        bool Sha256Hex(const std::string& data, char outHex[65])
        {
            BCRYPT_ALG_HANDLE alg = nullptr;
            if (BCryptOpenAlgorithmProvider(&alg, BCRYPT_SHA256_ALGORITHM,
                    nullptr, 0) != 0)
            {
                return false;
            }

            BCRYPT_HASH_HANDLE hash = nullptr;
            unsigned char digest[32] = {};
            bool ok = BCryptCreateHash(alg, &hash, nullptr, 0, nullptr, 0, 0) == 0;
            if (ok)
                ok = BCryptHashData(hash,
                        reinterpret_cast<PUCHAR>(const_cast<char*>(data.data())),
                        static_cast<ULONG>(data.size()), 0) == 0;
            if (ok)
                ok = BCryptFinishHash(hash, digest, sizeof(digest), 0) == 0;

            if (hash)
                BCryptDestroyHash(hash);
            BCryptCloseAlgorithmProvider(alg, 0);

            if (!ok)
                return false;

            static const char kHex[] = "0123456789abcdef";
            for (int i = 0; i < 32; ++i)
            {
                outHex[i * 2] = kHex[digest[i] >> 4];
                outHex[i * 2 + 1] = kHex[digest[i] & 0xF];
            }
            outHex[64] = 0;
            return true;
        }

        bool HexEquals(const char* a, const char* b)
        {
            for (int i = 0; i < 64; ++i)
            {
                char ca = a[i], cb = b[i];
                if (ca >= 'A' && ca <= 'F') ca = static_cast<char>(ca + 32);
                if (cb >= 'A' && cb <= 'F') cb = static_cast<char>(cb + 32);
                if (ca != cb)
                    return false;
            }
            return true;
        }

        // <game>\T7Patch\dxvk\<name>, the store the chained backend reads
        // from.  Wide characters throughout: the game folder may contain
        // non-ASCII and a DLL must not be written next to a mangled path.
        bool StorePath(const char* name, wchar_t* out, size_t outChars)
        {
            wchar_t gameDir[MAX_PATH] = {};
            const DWORD len = GetModuleFileNameW(nullptr, gameDir, MAX_PATH);
            if (len == 0 || len >= MAX_PATH)
                return false;
            wchar_t* slash = wcsrchr(gameDir, L'\\');
            if (!slash)
                return false;
            *(slash + 1) = L'\0';
            return swprintf_s(out, outChars, L"%sT7Patch\\dxvk\\%hs",
                gameDir, name) > 0;
        }

        // ---- install state ------------------------------------------------

        // Full path of one payload file, in the game folder or in the store.
        bool PathFor(const char* name, bool inGame, wchar_t* out, size_t outChars)
        {
            wchar_t gameDir[MAX_PATH] = {};
            const DWORD len = GetModuleFileNameW(nullptr, gameDir, MAX_PATH);
            if (len == 0 || len >= MAX_PATH)
                return false;
            wchar_t* slash = wcsrchr(gameDir, L'\\');
            if (!slash)
                return false;
            *(slash + 1) = L'\0';
            return swprintf_s(out, outChars,
                inGame ? L"%s%hs" : L"%sT7Patch\\dxvk\\%hs", gameDir, name) > 0;
        }

        bool PairPresent(bool inGame)
        {
            wchar_t a[MAX_PATH * 2] = {};
            wchar_t b[MAX_PATH * 2] = {};
            return PathFor("d3d11_backend.dll", inGame, a, _countof(a))
                && GetFileAttributesW(a) != INVALID_FILE_ATTRIBUTES
                && PathFor("dxgi.dll", inGame, b, _countof(b))
                && GetFileAttributesW(b) != INVALID_FILE_ATTRIBUTES;
        }

        // One half of the pair, park->game (enable) or game->park (disable).
        //
        // [LOCAL] The two directions treat a copy already sitting at the
        // destination DIFFERENTLY, and that is deliberate:
        //
        //   * enable (destination = the game folder) keeps refusing to
        //     overwrite.  Something else may have put a DXVK there - PatchOpsIII
        //     and dxvk_chain.py both write these two file names - and silently
        //     replacing it would hand the player a mixture nobody chose.  The
        //     move stops there, the log names the file it stopped on, and
        //     nothing is lost.
        //   * disable (destination = T7Patch\dxvk) overwrites.  A copy sitting
        //     there can only be our own redundant one - that is what "the pair
        //     is in both places" means - and the game folder's copy is the
        //     authoritative one: DXVK loads THAT file, and the same rule already
        //     governs the d3dcompiler_46 rename.  Refusing here left the toggle
        //     permanently stuck, because turning the backend off works by
        //     moving these very files back.
        bool MoveOne(const char* name, bool toGame)
        {
            wchar_t from[MAX_PATH * 2] = {};
            wchar_t to[MAX_PATH * 2] = {};
            if (!PathFor(name, !toGame, from, _countof(from))
                || !PathFor(name, toGame, to, _countof(to)))
            {
                return false;
            }

            // Logged explicitly: replacing the parked copy is the only place
            // this feature throws a file away, and "why did my back-up copy
            // change" deserves to be answerable from the log.
            if (!toGame && GetFileAttributesW(to) != INVALID_FILE_ATTRIBUTES)
            {
                Logf("dxvk install: %s also existed in T7Patch\\dxvk - the game "
                    "folder's copy is authoritative, the parked one is replaced",
                    name);
            }

            // MOVEFILE_REPLACE_EXISTING only in the disable direction; 0 leaves
            // MoveFileExW behaving exactly like the MoveFileW it replaces.
            const DWORD flags = toGame ? 0 : MOVEFILE_REPLACE_EXISTING;
            if (!MoveFileExW(from, to, flags))
            {
                char msg[256] = {};
                sprintf_s(msg, "dxvk install: cannot move %s (%lu)",
                    name, static_cast<unsigned long>(GetLastError()));
                Logf("%s", msg);
                return false;
            }
            return true;
        }

        // Moves the whole pair, and puts back whatever already moved when one
        // of the two fails.
        //
        // Why this matters: the half-moved state is the one state nothing else
        // recovers from.  One file ends up in the game folder and the other in
        // the store, so PairPresent() is false on both sides - Query() reports
        // Absent (the toggle greys out and claims DXVK was never installed),
        // and the next launch can only REPORT the mixture: a translation-layer
        // dxgi with no backend beside it raises the player-visible notice.
        // Putting the first file back turns all of that into "the switch did
        // nothing and the log says why", which is what the player expects.
        //
        // The rollback can itself fail - for the very reason the move did.
        // Then the log says so and the start-up notice is still the net.
        bool MovePair(bool toGame)
        {
            static const char* names[] = { "d3d11_backend.dll", "dxgi.dll" };
            const int count = static_cast<int>(_countof(names));

            int moved = 0;
            for (; moved < count; ++moved)
            {
                if (MoveOne(names[moved], toGame))
                    continue;

                Logf("dxvk install: %s aborted at %s - putting back what had "
                    "already moved", toGame ? "enabling" : "disabling",
                    names[moved]);

                for (int i = moved - 1; i >= 0; --i)
                {
                    if (!MoveOne(names[i], !toGame))
                    {
                        Logf("dxvk install: could not put %s back - the pair is "
                            "half moved (see the start-up notice)", names[i]);
                    }
                }
                return false;
            }
            return true;
        }

        // One bounded HTTPS GET.  Every wait has a timeout, so a black-holed
        // connection cannot leave the worker (and the "downloading" state)
        // stuck forever - same semantics the dictionary update settled on:
        // resolve, connect and send get 3 s each, receive waits because a
        // slow-but-alive mirror must be allowed to stream a 7.5 MB DLL at
        // its own pace.
        bool HttpGet(const wchar_t* url, std::string& body, std::string& err)
        {
            body.clear();
            err.clear();
            g_downloadedKiB.store(0);

            URL_COMPONENTS parts = {};
            parts.dwStructSize = sizeof(parts);
            wchar_t host[256] = {};
            wchar_t path[1024] = {};
            parts.lpszHostName = host;
            parts.dwHostNameLength = _countof(host);
            parts.lpszUrlPath = path;
            parts.dwUrlPathLength = _countof(path);
            if (!WinHttpCrackUrl(url, 0, 0, &parts))
            {
                err = "cannot parse the download URL";
                return false;
            }

            HINTERNET session = WinHttpOpen(L"T7Patch DXVK download",
                static_cast<DWORD>(WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY),
                WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
            if (!session)
                session = WinHttpOpen(L"T7Patch DXVK download",
                    WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
                    WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
            if (!session)
            {
                err = "network error";
                return false;
            }
            WinHttpSetTimeouts(session, 3000, 3000, 3000, 0);

            bool ok = false;
            unsigned long long received = 0;
            HINTERNET connect = WinHttpConnect(session, host, parts.nPort, 0);
            if (!connect)
            {
                err = "cannot reach the server";
            }
            else
            {
                HINTERNET request = WinHttpOpenRequest(connect, L"GET", path, nullptr,
                    WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, WINHTTP_FLAG_SECURE);
                if (!request)
                {
                    err = "cannot create the request";
                }
                else
                {
                    if (!WinHttpSendRequest(request, WINHTTP_NO_ADDITIONAL_HEADERS, 0,
                            WINHTTP_NO_REQUEST_DATA, 0, 0, 0) ||
                        !WinHttpReceiveResponse(request, nullptr))
                    {
                        err = "no connection (proxy?)";
                    }
                    else
                    {
                        DWORD status = 0;
                        DWORD statusSize = sizeof(status);
                        if (!WinHttpQueryHeaders(request,
                                WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                                WINHTTP_HEADER_NAME_BY_INDEX, &status, &statusSize,
                                WINHTTP_NO_HEADER_INDEX))
                        {
                            err = "cannot read the HTTP status";
                        }
                        else if (status != 200)
                        {
                            Logf("dxvk download: the server answered HTTP %lu",
                                static_cast<unsigned long>(status));
                            err = (status == 404)
                                ? "the backend files are not on the update source yet"
                                : "the update source is not responding correctly";
                        }
                        else
                        {
                            ok = true;
                            for (;;)
                            {
                                char chunk[8192];
                                DWORD got = 0;
                                if (!WinHttpReadData(request, chunk, sizeof(chunk), &got))
                                {
                                    ok = false;
                                    err = "the download was interrupted";
                                    break;
                                }
                                if (got == 0)
                                    break;
                                if (body.size() + got > kMaxDownload)
                                {
                                    ok = false;
                                    err = "the file is too large";
                                    break;
                                }
                                body.append(chunk, got);
                                received += got;
                                g_downloadedKiB.store(received / 1024u);
                            }
                        }
                    }
                    WinHttpCloseHandle(request);
                }
                WinHttpCloseHandle(connect);
            }
            WinHttpCloseHandle(session);

            return ok;
        }

        void Worker()
        {
            // A fresh install has no T7Patch\dxvk - the first download is what
            // fills it, the folder is NOT part of the package.  Create it
            // before anything else; the call is a harmless no-op when it is
            // already there.  (First real-world run pulled 7.5 MB from both
            // mirrors and then died on fopen because the folder was missing -
            // the network was never the problem, the assumption was.)
            wchar_t storeDir[MAX_PATH * 2] = {};
            if (StorePath("", storeDir, _countof(storeDir)))
                CreateDirectoryW(storeDir, nullptr);

            SetMessage("checking local files...");

            // [LOCAL] The case the per-file check below cannot see: the pair is
            // already INSTALLED in the game folder.
            //
            // Enabling MOVES both files out of T7Patch\dxvk into the game folder
            // (Enable/MoveOne use MoveFileW, not a copy), so once DXVK is on the
            // store is empty - and every file below then looks missing.  This
            // worker used to re-download all 12.9 MB in that situation and put
            // the pair back into the store, leaving it in BOTH places: exactly
            // the Mixed state Query() reports, which the menu draws as an
            // unticked toggle while DXVK is in fact enabled, and which
            // Disable() then refuses to undo because its move target exists.
            //
            // The authority here is the state the toggle itself draws, not a
            // second look into the game folder: one question, one answer, so the
            // button and the download cannot disagree about where the pair is.
            // Both non-Absent states with the pair in the game folder count -
            // Enabled (only there) and Mixed (there and in the store, which is
            // how a machine broken by an older build reports itself).
            const InstallState inst = Query();
            if (inst == InstallState::Enabled || inst == InstallState::Mixed)
            {
                Logf("dxvk download: the pair is already in the game folder "
                    "(state %d) - nothing to fetch", static_cast<int>(inst));
                SetMessage("already downloaded");
                g_state.store(static_cast<int>(State::Ok));
                g_lastRunMs.store(GetTickCount64());
                return;
            }

            for (const File& file : kFiles)
            {
                wchar_t path[MAX_PATH * 2] = {};
                if (!StorePath(file.name, path, _countof(path)))
                {
                    Fail("cannot resolve the store path");
                    return;
                }

                // Already there and byte-identical?  Then this file is done.
                // The hash is the only test that counts for a DLL, and it also
                // makes a re-click after a good run cheap and quiet: nothing
                // is fetched, the local copies are just re-verified.
                {
                    std::string existing;
                    FILE* f = nullptr;
                    if (_wfopen_s(&f, path, L"rb") == 0 && f)
                    {
                        char chunk[65536];
                        size_t got = 0;
                        while ((got = fread(chunk, 1, sizeof(chunk), f)) > 0)
                            existing.append(chunk, got);
                        fclose(f);
                    }
                    char localHex[65] = {};
                    if (!existing.empty() && Sha256Hex(existing, localHex)
                        && HexEquals(localHex, file.sha256Hex))
                    {
                        Logf("dxvk download: %s already in place and verified",
                            file.name);
                        continue;
                    }
                }

                // Fetch it.  Two mirrors per file; the hash decides, not the
                // transport - a mirror that serves different bytes is dropped
                // exactly like an unreachable one.
                bool valid = false;
                std::string err = "both update sources are unreachable";
                for (const wchar_t* url : file.urls)
                {
                    char urlName[192] = {};
                    WideCharToMultiByte(CP_UTF8, 0, url, -1,
                        urlName, sizeof(urlName), nullptr, nullptr);

                    SetMessage("downloading %s...", file.name);
                    std::string body;
                    std::string oneErr;
                    if (!HttpGet(url, body, oneErr))
                    {
                        Logf("dxvk download: source unavailable (%s): %s",
                            urlName, oneErr.c_str());
                        err = oneErr;
                        continue;
                    }

                    char gotHex[65] = {};
                    if (!Sha256Hex(body, gotHex))
                    {
                        Logf("dxvk download: hashing failed (%s)", urlName);
                        err = "cannot verify the download";
                        continue;
                    }
                    if (!HexEquals(gotHex, file.sha256Hex))
                    {
                        Logf("dxvk download: hash mismatch (%s): got %.16s..., "
                            "want %.16s...", urlName, gotHex, file.sha256Hex);
                        err = "the downloaded file did not verify";
                        continue;
                    }

                    // Atomic replace, same trick as the dictionary: write next
                    // to the target, then a single rename over it.  A
                    // half-written DLL can never exist under the real name.
                    const std::wstring widePath = path;
                    const std::wstring tmpPath = widePath + L".new";
                    FILE* f = nullptr;
                    bool written = false;
                    if (_wfopen_s(&f, tmpPath.c_str(), L"wb") == 0 && f)
                    {
                        written = fwrite(body.data(), 1, body.size(), f) == body.size();
                        fclose(f);
                    }
                    if (!written)
                    {
                        Logf("dxvk download: cannot write the temporary file");
                        err = "cannot write the file";
                        continue;
                    }
                    if (!MoveFileExW(tmpPath.c_str(), path, MOVEFILE_REPLACE_EXISTING))
                    {
                        DeleteFileW(tmpPath.c_str());
                        Logf("dxvk download: cannot replace the previous copy");
                        err = "cannot replace the file (locked?)";
                        continue;
                    }

                    Logf("dxvk download: %s fetched and verified (%u KiB, %s)",
                        file.name,
                        static_cast<unsigned>(body.size() / 1024u), urlName);
                    valid = true;
                    break;
                }

                if (!valid)
                {
                    Fail("%s: %s", file.name, err.c_str());
                    return;
                }
            }

            SetMessage("both files verified");
            g_state.store(static_cast<int>(State::Ok));

            // Only a run that got this far starts the cooldown - every failure
            // path above returns without touching the timestamp, so a retry
            // is always immediate.
            g_lastRunMs.store(GetTickCount64());

            Logf("dxvk download: both files verified in T7Patch\\dxvk - move "
                "d3d11_backend.dll and dxgi.dll into the game folder to enable "
                "the Vulkan backend");
        }
    }

    void Start()
    {
        // CAS from whatever state we are in - Idle, Ok and Failed all start a
        // run, only Running refuses.  (Same trap as the dictionary's first
        // cut: comparing against Running as the EXPECTED value would make
        // Start() silently do nothing on every single click.)
        int current = g_state.load();
        if (current == static_cast<int>(State::Running))
            return; // a download is already in flight

        // Cooldown: NOT a failure - nothing ran and nothing is wrong.
        const unsigned long long nowMs = GetTickCount64();
        const unsigned long long lastMs = g_lastRunMs.load();
        if (lastMs != 0 && nowMs - lastMs < kCooldownMs)
        {
            g_state.store(static_cast<int>(State::UpToDate));
            Logf("dxvk download skipped: cooldown (%u s)",
                kCooldownMs / 1000u);
            return;
        }

        if (!g_state.compare_exchange_strong(current, static_cast<int>(State::Running)))
            return; // lost a race with another starter

        {
            std::lock_guard<std::mutex> lock(g_messageMutex);
            g_message[0] = 0;
        }
        Logf("dxvk download requested by the user");
        std::thread(Worker).detach();
    }

    Status Get()
    {
        Status status;
        status.state = static_cast<State>(g_state.load());
        status.downloadedKiB = g_downloadedKiB.load();

        std::lock_guard<std::mutex> lock(g_messageMutex);
        strncpy_s(status.message, g_message, _TRUNCATE);
        return status;
    }

    InstallState Query()
    {
        const bool inGame = PairPresent(true);
        const bool parked = PairPresent(false);
        if (inGame && parked)
            return InstallState::Mixed;
        if (inGame)
            return InstallState::Enabled;
        if (parked)
            return InstallState::Parked;
        return InstallState::Absent;
    }

    // ---- dxvk.conf settings ----------------------------------------------

    Conf g_confCache;
    bool g_confLoaded = false;

    // The store directory must exist before the conf can land in it - same
    // first-install gap the downloader hit (CreateDirectory is a no-op when
    // the folder is already there).
    void EnsureStoreDir()
    {
        wchar_t storeDir[MAX_PATH * 2] = {};
        if (StorePath("", storeDir, _countof(storeDir)))
            CreateDirectoryW(storeDir, nullptr);
    }

    bool ReadConfFile(std::string& body)
    {
        wchar_t path[MAX_PATH * 2] = {};
        if (!StorePath("dxvk.conf", path, _countof(path)))
            return false;
        FILE* f = nullptr;
        if (_wfopen_s(&f, path, L"rb") != 0 || !f)
            return false;
        char chunk[4096];
        size_t got = 0;
        while ((got = fread(chunk, 1, sizeof(chunk), f)) > 0)
            body.append(chunk, got);
        fclose(f);
        return true;
    }

    // Value of "key=<rest of line>", or "" when the key is absent.
    std::string ConfValue(const std::string& body, const char* key)
    {
        size_t at = body.find(key);
        if (at == std::string::npos)
            return {};
        at += strlen(key);
        const size_t end = body.find('\n', at);
        return body.substr(at,
            (end == std::string::npos) ? std::string::npos : end - at);
    }

    // The six names, in the order the page draws the ticks and the order they
    // are written into dxvk.hud.
    struct HudName { unsigned bit; const char* name; };
    const HudName kHudNames[] = {
        { HUD_FPS,        "fps" },
        { HUD_FRAMETIMES, "frametimes" },
        { HUD_GPULOAD,    "gpuload" },
        { HUD_MEMORY,     "memory" },
        { HUD_COMPILER,   "compiler" },
        { HUD_DEVINFO,    "devinfo" },
    };

    void EnsureConfLoaded()
    {
        if (g_confLoaded)
            return;
        g_confLoaded = true;

        std::string body;
        if (!ReadConfFile(body) || body.empty())
            return; // defaults: hud off, uncapped, tearFree Auto

        // One substring test per name, on the comma list we wrote ourselves
        // (and "anything not listed runs at the default" is exactly right
        // here).  The fixed trio the earlier builds wrote - fps,frametimes,
        // gpuload - resolves to those same three ticks, so an upgrade keeps
        // the player's HUD instead of silently turning it off.
        const std::string hud = ConfValue(body, "dxvk.hud=");
        g_confCache.hud = 0;
        for (const HudName& n : kHudNames)
            if (hud.find(n.name) != std::string::npos)
                g_confCache.hud |= n.bit;
        const std::string fps = ConfValue(body, "dxgi.maxFrameRate=");
        if (!fps.empty())
            g_confCache.maxFps = atoi(fps.c_str());
        const std::string tear = ConfValue(body, "dxvk.tearFree=");
        if (tear.find("True") != std::string::npos)
            g_confCache.tearFree = 1;
        else if (tear.find("False") != std::string::npos)
            g_confCache.tearFree = 2;
    }

    std::string ConfText(const Conf& c)
    {
        const char* tear = (c.tearFree == 1) ? "True"
            : (c.tearFree == 2) ? "False" : "Auto";

        // Write-only template, stated flat: whatever the page does not expose
        // stays at the documented default, and the comment says so - the three
        // keys the UI keeps boring are the three most tempting bad ideas.
        std::string out;
        out += "# DXVK settings - generated by the T7Patch overlay.\n";
        out += "# Rewritten whenever a setting changes on the DXVK page; hand\n";
        out += "# edits to the keys below will be overwritten.  The proxy points\n";
        out += "# DXVK here via DXVK_CONFIG_FILE - this file does not belong in\n";
        out += "# the game folder.  Anything not listed below runs at the default.\n";
        std::string hud;
        for (const HudName& n : kHudNames)
            if (c.hud & n.bit)
            {
                if (!hud.empty())
                    hud += ",";
                hud += n.name;
            }
        if (!hud.empty())
            out += "dxvk.hud=" + hud + "\n";
        if (c.maxFps > 0)
            out += "dxgi.maxFrameRate=" + std::to_string(c.maxFps) + "\n";
        out += std::string("dxvk.tearFree=") + tear + "\n";
        return out;
    }

    Conf ConfGet()
    {
        EnsureConfLoaded();
        return g_confCache;
    }

    void ConfSet(const Conf& c)
    {
        EnsureConfLoaded();
        g_confCache = c;

        EnsureStoreDir();

        wchar_t path[MAX_PATH * 2] = {};
        if (!StorePath("dxvk.conf", path, _countof(path)))
        {
            Logf("dxvk conf: cannot resolve the path");
            return;
        }
        const std::string text = ConfText(c);
        const std::wstring tmpPath = std::wstring(path) + L".new";
        FILE* f = nullptr;
        bool written = false;
        if (_wfopen_s(&f, tmpPath.c_str(), L"wb") == 0 && f)
        {
            written = fwrite(text.data(), 1, text.size(), f) == text.size();
            fclose(f);
        }
        if (!written)
        {
            Logf("dxvk conf: cannot write the temporary file");
            return;
        }
        if (!MoveFileExW(tmpPath.c_str(), path, MOVEFILE_REPLACE_EXISTING))
        {
            DeleteFileW(tmpPath.c_str());
            Logf("dxvk conf: cannot replace the file");
            return;
        }
        Logf("dxvk conf saved: maxFps=%d, tearFree=%d", c.maxFps, c.tearFree);
    }

    bool Enable()
    {
        if (PairPresent(true))
            return true; // already on - idempotent, the checkbox just agrees
        if (!MovePair(true))
            return false;
        Logf("dxvk install: enabled - both files moved into the game folder, "
            "takes effect on the next launch");
        return true;
    }

    bool Disable()
    {
        if (!PairPresent(true))
            return true; // already off
        if (!MovePair(false))
            return false;
        Logf("dxvk install: disabled - both files moved back to T7Patch\\dxvk, "
            "takes effect on the next launch");
        return true;
    }
}
