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
                    L"https://cdn.jsdelivr.net/gh/muyou233/T7Patch-src@main"
                    L"/dxvk/d3d11_backend.dll",
                    L"https://raw.githubusercontent.com/muyou233/T7Patch-src"
                    L"/main/dxvk/d3d11_backend.dll",
                },
                "0A203B6255C893430F0A8461C618962DF04E62AA41538D5A875B21868317CF9F",
            },
            {
                "dxgi.dll",
                {
                    L"https://cdn.jsdelivr.net/gh/muyou233/T7Patch-src@main"
                    L"/dxvk/dxgi.dll",
                    L"https://raw.githubusercontent.com/muyou233/T7Patch-src"
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
        bool MoveOne(const char* name, bool toGame)
        {
            wchar_t from[MAX_PATH * 2] = {};
            wchar_t to[MAX_PATH * 2] = {};
            if (!PathFor(name, !toGame, from, _countof(from))
                || !PathFor(name, toGame, to, _countof(to)))
            {
                return false;
            }
            // MoveFile refuses to overwrite - exactly what we want: an
            // unexpected file at the destination must stop us, not vanish.
            if (!MoveFileW(from, to))
            {
                char msg[256] = {};
                sprintf_s(msg, "dxvk install: cannot move %s (%lu)",
                    name, static_cast<unsigned long>(GetLastError()));
                Logf("%s", msg);
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

    void EnsureConfLoaded()
    {
        if (g_confLoaded)
            return;
        g_confLoaded = true;

        std::string body;
        if (!ReadConfFile(body) || body.empty())
            return; // defaults: hud on, uncapped, tearFree Auto

        const std::string hud = ConfValue(body, "dxvk.hud=");
        g_confCache.hud = !hud.empty();
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
        if (c.hud)
            out += "dxvk.hud=fps,frametimes,gpuload\n";
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
        static const char* names[] = { "d3d11_backend.dll", "dxgi.dll" };
        for (const char* name : names)
        {
            if (!MoveOne(name, true))
            {
                Logf("dxvk install: enabling aborted at %s", name);
                return false;
            }
        }
        Logf("dxvk install: enabled - both files moved into the game folder, "
            "takes effect on the next launch");
        return true;
    }

    bool Disable()
    {
        if (!PairPresent(true))
            return true; // already off
        static const char* names[] = { "d3d11_backend.dll", "dxgi.dll" };
        for (const char* name : names)
        {
            if (!MoveOne(name, false))
            {
                Logf("dxvk install: disabling aborted at %s", name);
                return false;
            }
        }
        Logf("dxvk install: disabled - both files moved back to T7Patch\\dxvk, "
            "takes effect on the next launch");
        return true;
    }
}
