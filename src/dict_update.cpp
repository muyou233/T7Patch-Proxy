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
        // Hard-coded on purpose - see the header.  Three mirrors of the same
        // published file, tried in order: the jsDelivr CDN first (best plain
        // reachability from mainland China), GitHub raw second (always
        // current), Gitee last.  All three are anonymous and equally trusted
        // (jsDelivr serves the repo read-only).  Gitee's raw endpoint answers
        // HTTP 451 to anonymous downloaders, but its contents API serves the
        // same bytes as JSON with a base64 payload - so that mirror carries a
        // jsonApi flag and gets unwrapped after the download.  jsDelivr's
        // edge cache trails a fresh push by hours (a branch URL is cached,
        // not purged automatically) - acceptable for a file that changes
        // rarely, and the owner can purge it on demand.
        struct Source
        {
            const wchar_t* url;
            bool jsonApi;
        };
        // 2026-09-20: two published files now - the main dictionary and the
        // pinyin table the map-safe switch renders with.  Same three mirrors
        // each, same order (jsDelivr for mainland reachability, GitHub raw for
        // freshness, Gitee's JSON contents API last).
        constexpr Source kDictSources[] =
        {
            {
                L"https://cdn.jsdelivr.net/gh/muyou233/T7Patch-Proxy@main"
                L"/translate/translate_zh.txt",
                false
            },
            {
                L"https://raw.githubusercontent.com/muyou233/T7Patch-Proxy"
                L"/main/translate/translate_zh.txt",
                false
            },
            {
                L"https://gitee.com/api/v5/repos/muyou23333/"
                L"t7-patch-proxy-translate/contents/translate/translate_zh.txt"
                L"?ref=master",
                true
            },
        };
        constexpr Source kPinyinSources[] =
        {
            {
                L"https://cdn.jsdelivr.net/gh/muyou233/T7Patch-Proxy@main"
                L"/translate/translate_pinyin.txt",
                false
            },
            {
                L"https://raw.githubusercontent.com/muyou233/T7Patch-Proxy"
                L"/main/translate/translate_pinyin.txt",
                false
            },
            {
                L"https://gitee.com/api/v5/repos/muyou23333/"
                L"t7-patch-proxy-translate/contents/translate/translate_pinyin.txt"
                L"?ref=master",
                true
            },
        };

        // Sanity limits.  The real file is ~45 KB; anything past the cap is an
        // error page or a stuck socket, not a dictionary.
        constexpr size_t kMaxDownload = 4u * 1024u * 1024u;

        // Refuse a download that would shrink the dictionary by more than this:
        // a truncated file or an error page must never replace a working one.
        constexpr double kMinKeepRatio = 0.8;

        // Cooldown between two SUCCESSFUL runs.  Counted from the moment a
        // download passed every check and replaced the file - a failed or
        // refused run must never start the cooldown, or a user on a slow
        // connection would be locked out of retrying.  Rapid re-clicking
        // after a good update just hammers the source for an identical file.
        constexpr unsigned kCooldownMs = 60u * 1000u;

        std::atomic<int> g_state{ static_cast<int>(State::Idle) };
        std::atomic<unsigned> g_entries{ 0 };
        std::atomic<unsigned long long> g_lastRunMs{ 0 };
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
        bool HttpGet(const wchar_t* url, std::string& body, std::string& err)
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
            if (!WinHttpCrackUrl(url, 0, 0, &parts))
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
                err = "network error";
                return false;
            }
            // Response phases get 3 s each (user's spec: "switch if no
            // response in 3 s"): resolve, connect and send abandon a dead
            // mirror after exactly 3 s and the next one is tried.  Receive
            // is 0 = wait indefinitely (documented semantics), because a
            // slow-but-alive mirror must be allowed to stream the file at
            // its own pace - only the time to START answering is limited,
            // not the transfer itself.
            WinHttpSetTimeouts(session, 3000, 3000, 3000, 0);

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
                            // [LOCAL] The message goes straight to the overlay
                            // beside the button, so it stays plain text - no
                            // status codes, no numbers (user's call).  The
                            // technical detail lives in the log only.
                            Logf("dictionary update: the server answered HTTP %lu",
                                static_cast<unsigned long>(status));
                            err = (status == 404)
                                ? "the dictionary is not on the update source yet"
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

        // Standard base64; tolerates the line breaks Gitee embeds in the
        // payload, stops at the first '=' padding.  Returns false only when
        // nothing decodable came out.
        bool DecodeBase64(const std::string& in, std::string& out)
        {
            auto digit = [](char c) -> int
            {
                if (c >= 'A' && c <= 'Z') return c - 'A';
                if (c >= 'a' && c <= 'z') return c - 'a' + 26;
                if (c >= '0' && c <= '9') return c - '0' + 52;
                if (c == '+') return 62;
                if (c == '/') return 63;
                return -1;
            };

            out.clear();
            out.reserve(in.size() / 4 * 3);
            unsigned acc = 0;
            int bits = 0;
            for (char c : in)
            {
                if (c == '=')
                    break; // padding: whatever is accumulated is whole bytes
                const int v = digit(c);
                if (v < 0)
                    continue; // whitespace / line breaks inside the payload
                acc = (acc << 6) | static_cast<unsigned>(v);
                bits += 6;
                if (bits >= 8)
                {
                    bits -= 8;
                    out.push_back(static_cast<char>((acc >> bits) & 0xFF));
                }
            }
            return !out.empty();
        }

        // Gitee's contents API answers JSON: {"content":"<base64>",...}.
        // The base64 alphabet contains no quotes or backslashes, so the
        // payload is exactly the bytes between the opening quote and the
        // next one.  Anything unexpected is a plain source error.
        bool UnwrapGiteeJson(const std::string& body, std::string& out,
            std::string& err)
        {
            static const char kKey[] = "\"content\":\"";
            const size_t at = body.find(kKey);
            const size_t b64start =
                (at == std::string::npos) ? std::string::npos
                                          : at + sizeof(kKey) - 1;
            const size_t b64end = (b64start == std::string::npos)
                ? std::string::npos : body.find('"', b64start);
            if (b64start == std::string::npos || b64end == std::string::npos ||
                b64end - b64start > kMaxDownload ||
                !DecodeBase64(body.substr(b64start, b64end - b64start), out))
            {
                err = "the update source answered in an unexpected format";
                return false;
            }
            return true;
        }

        // One published file: try every mirror in order; the first one that
        // yields a plausible table wins.  'current' feeds the keep-ratio check
        // that refuses a truncated file or an error page.  On success 'body'
        // holds the text and 'got' its entry count.
        bool UpdateFile(const Source* sources, size_t sourceCount, unsigned current,
            std::string& body, std::string& err, unsigned& got)
        {
            body.clear();
            err = "all update sources are unreachable";
            got = 0;

            std::string decoded; // JSON-API payload lives here, outside the
                                 // loop, so it can be swapped into body below
            for (size_t i = 0; i < sourceCount; ++i)
            {
                const Source& src = sources[i];
                char urlName[192] = {};
                WideCharToMultiByte(CP_UTF8, 0, src.url, -1,
                    urlName, sizeof(urlName), nullptr, nullptr);

                std::string oneErr;
                if (!HttpGet(src.url, body, oneErr))
                {
                    Logf("dictionary update: source unavailable (%s): %s",
                        urlName, oneErr.c_str());
                    err = oneErr;
                    continue;
                }

                const std::string* payload = &body;
                if (src.jsonApi)
                {
                    if (!UnwrapGiteeJson(body, decoded, oneErr))
                    {
                        Logf("dictionary update: source unusable (%s): %s",
                            urlName, oneErr.c_str());
                        err = oneErr;
                        continue;
                    }
                    payload = &decoded;
                }

                got = CountEntries(*payload);
                if (got == 0)
                {
                    Logf("dictionary update: source has no usable entries "
                        "(%s): %u bytes",
                        urlName, static_cast<unsigned>(payload->size()));
                    err = "the downloaded file is not a dictionary";
                    continue;
                }
                if (current > 0 && got < static_cast<unsigned>(current * kMinKeepRatio))
                {
                    Logf("dictionary update: source looks incomplete (%s): "
                        "%u entries (currently %u)", urlName, got, current);
                    err = "the downloaded dictionary looks incomplete";
                    continue;
                }

                if (src.jsonApi)
                    body.swap(decoded); // body must hold the text itself -
                                        // the write below uses it
                Logf("dictionary update: using source %s (%u entries)",
                    urlName, got);
                err.clear();
                return true;
            }
            return false;
        }

        // Write 'body' over 'path' atomically: same directory, temporary file
        // first, then a rename.  The write-time change is also what makes the
        // running game reload the file.
        bool InstallDictionary(const std::string& body, const char* path)
        {
            char tmp[MAX_PATH * 2 + 8] = {};
            const int n = snprintf(tmp, sizeof(tmp), "%s.new", path);
            if (n <= 0 || static_cast<size_t>(n) >= sizeof(tmp))
                return false;

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
                return false;
            }
            return MoveFileExA(tmp, path, MOVEFILE_REPLACE_EXISTING) != 0;
        }

        void Worker()
        {
            // ---- 1. The main dictionary (required - the whole button exists
            // for it).  Try every source in order; the first one that yields a
            // valid dictionary wins.  A source that cannot be reached, or that
            // serves something that is not a usable dictionary, just moves the
            // attempt on to the next mirror - only when ALL of them fail does
            // the button report a failure (plain text; the log carries which
            // source said what).
            const unsigned have = translate::EntryCount();
            std::string body;
            std::string err;
            unsigned got = 0;
            if (!UpdateFile(kDictSources, std::size(kDictSources),
                    have, body, err, got))
            {
                Fail("%s", err.c_str());
                return;
            }

            char path[MAX_PATH * 2] = {};
            if (!translate::DictionaryPath(path, sizeof(path)))
            {
                Fail("cannot resolve the dictionary path");
                return;
            }
            if (!InstallDictionary(body, path))
            {
                Fail("cannot replace the dictionary file (locked?)");
                return;
            }

            // ---- 2. The pinyin table (best effort).  2026-09-20: the
            // map-safe switch renders pinyin from it, so an update that
            // refreshes the dictionary should refresh it too - but its absence
            // on a source (an older mirror not carrying the file yet) must not
            // fail the run: the dictionary itself already landed.
            char pinPath[MAX_PATH * 2] = {};
            std::string pinErr = "cannot resolve the pinyin path";
            unsigned pinGot = 0;
            bool pinOk = false;
            std::string pinBody;
            if (translate::HanziPath(pinPath, sizeof(pinPath)))
            {
                pinOk = UpdateFile(kPinyinSources, std::size(kPinyinSources),
                    translate::HanziCount(), pinBody, pinErr, pinGot)
                    && InstallDictionary(pinBody, pinPath);
                if (!pinOk)
                    pinErr = pinErr.empty() ? "cannot replace the file" : pinErr;
            }

            g_entries.store(got);
            if (pinOk)
                SetMessage("%u entries + %u pinyin", got, pinGot);
            else
                SetMessage("%u entries (pinyin not updated: %s)", got, pinErr.c_str());
            g_state.store(static_cast<int>(State::Ok));

            // Only a run that got this far starts the cooldown (see the
            // constant's comment): every failure path above returns without
            // touching the timestamp, so a retry is always immediate.
            g_lastRunMs.store(GetTickCount64());

            // Tell the translation layer to re-read on its next lookup instead of
            // waiting for (and depending on) the write-time poll.  This is the
            // case the whole button exists for: the game may have been running on
            // the built-in copy, and the file just written has to become the one
            // in force from here on - no restart, no waiting for a timestamp.
            translate::RequestReload();

            if (pinOk)
            {
                Logf("dictionary updated from the network: %u entries + %u pinyin "
                    "(was %u entries); reload requested - it lands on the next UI rebuild",
                    got, pinGot, have);
            }
            else
            {
                Logf("dictionary updated from the network: %u entries (was %u); "
                    "pinyin table NOT updated: %s", got, have, pinErr.c_str());
            }
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

        // Cooldown: NOT a failure - nothing ran and nothing is wrong.  Show the
        // neutral "already up to date" line beside the button; the log keeps
        // the precise reason.
        const unsigned long long nowMs = GetTickCount64();
        const unsigned long long lastMs = g_lastRunMs.load();
        if (lastMs != 0 && nowMs - lastMs < kCooldownMs)
        {
            g_state.store(static_cast<int>(State::UpToDate));
            Logf("dictionary update skipped: cooldown (%u s)",
                kCooldownMs / 1000u);
            return;
        }

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
