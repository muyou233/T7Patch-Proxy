#include "dict_update.h"

#include "framework.h"
#include "t7patch_log.h" // [LOCAL] one line per attempt
#include "translate.h"   // where the dictionary lives, and how many entries it has

#include <atomic>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>

#include <winhttp.h>

#pragma comment(lib, "winhttp.lib")

// Windows 8.1+ picks up the system proxy automatically; on anything older the
// constant does not exist and we fall back to the registry-configured proxy.
#ifndef WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY
#define WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY 4
#endif

namespace dict_update
{
    namespace
    {
        // Hard-coded on purpose - see the header.  Points at the published copy
        // in the repo, which is the same file the sync tool deploys by hand.
        constexpr const wchar_t* kUrl =
            L"https://raw.githubusercontent.com/muyou233/T7Patch-src"
            L"/main/translate/translate_zh.txt";

        // Sanity limits.  The real file is ~45 KB; anything past the cap is an
        // error page or a stuck socket, not a dictionary.
        constexpr size_t kMaxDownload = 4u * 1024u * 1024u;

        // Refuse a download that would shrink the dictionary by more than this:
        // a truncated file or an error page must never replace a working one.
        constexpr double kMinKeepRatio = 0.8;

        std::atomic<int> g_state{ static_cast<int>(State::Idle) };
        std::atomic<unsigned> g_entries{ 0 };
        std::mutex g_messageMutex;
        char g_message[192] = {};

        void Logf(const char* fmt, ...)
        {
            char msg[512] = {};
            va_list ap;
            va_start(ap, fmt);
            vsnprintf(msg, sizeof(msg), fmt, ap);
            va_end(ap);
            t7log::Append("translate", msg);
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
            Logf("dictionary update failed: %s", msg);
        }

        // One bounded HTTPS GET.  Every wait has a timeout, so a black-holed
        // connection cannot leave the worker (and the "downloading" state)
        // stuck forever.
        bool HttpGet(std::string& body, std::string& err)
        {
            body.clear();
            err.clear();

            URL_COMPONENTS parts = {};
            parts.dwStructSize = sizeof(parts);
            wchar_t host[256] = {};
            wchar_t path[1024] = {};
            parts.lpszHostName = host;
            parts.dwHostNameLength = _countof(host);
            parts.lpszUrlPath = path;
            parts.dwUrlPathLength = _countof(path);
            if (!WinHttpCrackUrl(kUrl, 0, 0, &parts))
            {
                err = "cannot parse the download URL";
                return false;
            }

            HINTERNET session = WinHttpOpen(L"T7Patch dictionary update",
                static_cast<DWORD>(WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY),
                WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
            if (!session)
                session = WinHttpOpen(L"T7Patch dictionary update",
                    WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
                    WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
            if (!session)
            {
                err = "WinHttpOpen failed";
                return false;
            }
            WinHttpSetTimeouts(session, 10000, 10000, 15000, 20000);

            bool ok = false;
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
                            char buf[64] = {};
                            snprintf(buf, sizeof(buf), "HTTP %lu",
                                static_cast<unsigned long>(status));
                            err = buf;
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

        // Counts the lines the real parser would accept - same rules (a line with
        // '=' that is not a comment, within the line-length limit).  A count, not
        // a parse: this only has to be strict enough to reject an error page or a
        // truncated file, and the true parse happens in translate.cpp once the
        // file is in place.
        unsigned CountEntries(const std::string& blob)
        {
            unsigned count = 0;
            size_t at = 0;
            while (at < blob.size())
            {
                const char* start = blob.data() + at;
                const char* nl = static_cast<const char*>(
                    memchr(start, '\n', blob.size() - at));
                const size_t len = nl ? static_cast<size_t>(nl - start) : (blob.size() - at);
                at += len + (nl ? 1u : 0u);

                if (len == 0 || len > 1022)
                    continue;
                size_t i = 0;
                while (i < len && (start[i] == ' ' || start[i] == '\t'))
                    ++i;
                if (i >= len || start[i] == '#' || start[i] == ';')
                    continue;
                if (memchr(start + i, '=', len - i))
                    ++count;
            }
            return count;
        }

        void Worker()
        {
            std::string body;
            std::string err;
            if (!HttpGet(body, err))
            {
                Fail("%s", err.c_str());
                return;
            }

            const unsigned got = CountEntries(body);
            const unsigned have = translate::EntryCount();
            if (got == 0)
            {
                Fail("no usable entries (%u bytes)",
                    static_cast<unsigned>(body.size()));
                return;
            }
            if (have > 0 && got < static_cast<unsigned>(have * kMinKeepRatio))
            {
                Fail("refused: %u vs %u entries", got, have);
                return;
            }

            char path[MAX_PATH * 2] = {};
            if (!translate::DictionaryPath(path, sizeof(path)))
            {
                Fail("cannot resolve the dictionary path");
                return;
            }

            // Same directory, so the rename below is atomic; the write-time
            // change is also what makes the running game reload it.
            char tmp[MAX_PATH * 2 + 8] = {};
            const int n = snprintf(tmp, sizeof(tmp), "%s.new", path);
            if (n <= 0 || static_cast<size_t>(n) >= sizeof(tmp))
            {
                Fail("the dictionary path is too long");
                return;
            }

            bool written = false;
            FILE* f = nullptr;
            if (fopen_s(&f, tmp, "wb") == 0 && f)
            {
                written = fwrite(body.data(), 1, body.size(), f) == body.size();
                fclose(f);
            }
            if (!written)
            {
                DeleteFileA(tmp);
                Logf("dictionary update failed: cannot write %s", tmp);
                Fail("cannot write the file");
                return;
            }
            if (!MoveFileExA(tmp, path, MOVEFILE_REPLACE_EXISTING))
            {
                DeleteFileA(tmp);
                Fail("cannot replace the file (locked?)");
                return;
            }

            g_entries.store(got);
            SetMessage("%u entries", got);
            g_state.store(static_cast<int>(State::Ok));

            // Tell the translation layer to re-read on its next lookup instead of
            // waiting for (and depending on) the write-time poll.  This is the
            // case the whole button exists for: the game may have been running on
            // the built-in copy, and the file just written has to become the one
            // in force from here on - no restart, no waiting for a timestamp.
            translate::RequestReload();

            Logf("dictionary updated from the network: %u entries (was %u); "
                "reload requested - it lands on the next UI rebuild", got, have);
        }
    }

    void Start()
    {
        // CAS from whatever state we are in - Idle, Ok and Failed all start a
        // run, only Running refuses.  The first cut compared against Running as
        // the EXPECTED value, which can only succeed if a download is ALREADY
        // running - so Start() silently did nothing on every single click, and
        // the UI never showed a state because no state was ever entered.
        int current = g_state.load();
        if (current == static_cast<int>(State::Running))
            return; // a download is already in flight
        if (!g_state.compare_exchange_strong(current, static_cast<int>(State::Running)))
            return; // lost a race with another starter

        {
            std::lock_guard<std::mutex> lock(g_messageMutex);
            g_message[0] = 0;
        }
        Logf("dictionary update requested by the user");
        std::thread(Worker).detach();
    }

    Status Get()
    {
        Status status;
        status.state = static_cast<State>(g_state.load());
        status.entries = g_entries.load();

        std::lock_guard<std::mutex> lock(g_messageMutex);
        strncpy_s(status.message, g_message, _TRUNCATE);
        return status;
    }
}
