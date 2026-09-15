#include "translate.h"
#include "translate_res.h" // [LOCAL] IDR_TRANSLATE_DICT: the dictionary built into the dll
#include "framework.h"
#include "t7patch_log.h" // [LOCAL] diagnostics: one line per load attempt

#include <algorithm>
#include <atomic>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace translate
{
    namespace
    {
        // Exact entries: lower-cased English source -> translation.
        std::unordered_map<std::string, std::string> g_dict;

        // Template entries (keys containing '*'), for the UI text that carries
        // data the dictionary can never enumerate: "LEVEL 46", "Most Used: HVK-30",
        // "Stoked II".  Kept narrow-to-wide (fewest '*' first) and always tried
        // after the exact entries, so a specific line always beats a general one.
        struct WildPattern
        {
            std::vector<std::string> parts; // literal chunks between the '*'
            std::string value;              // translation, '*' = the captured text
        };
        std::vector<WildPattern> g_patterns;

        std::mutex g_mutex; // guards the two tables above and g_dictStamp

        std::atomic<bool> g_enabled{ false }; // translate=1 AND the dictionary loaded
        std::atomic<bool> g_collect{ false }; // dump_ui_strings=1

        // [LOCAL] Diagnostics.  "I turned translation on and nothing happened"
        // has to be answerable from the log alone: these lines say whether the
        // switch was seen, which dictionary won, and whether lookups ever match.
        void Logf(const char* fmt, ...)
        {
            char msg[512] = {};
            va_list ap;
            va_start(ap, fmt);
            vsnprintf(msg, sizeof(msg), fmt, ap);
            va_end(ap);
            t7log::Append("translate", msg);
        }

        // Collection budget: a front-end walk produces a few thousand distinct
        // strings; the cap keeps a pathological mod from growing the file
        // without bound.
        constexpr size_t kCollectMax = 8000;

        // Longest single visible run we translate.  Runs are fragments of a UI
        // string (see NextRun); the longest real one measured is ~330 bytes.
        constexpr size_t kRunMax = 1024;

        // A template with more '*' than this is a typo, not a template.
        constexpr size_t kMaxWildcards = 8;

        // How often the lookup path re-checks the dictionary file.  Editing the
        // dictionary then only costs a restart of the *screen*, not the game.
        constexpr unsigned long long kPollIntervalMs = 2000;

        std::unordered_set<std::string> g_seen;
        unsigned g_collected = 0;

        std::atomic<unsigned long long> g_lastPollMs{ 0 };
        std::atomic<bool> g_reloadRequested{ false }; // set by the updater, see RequestReload
        unsigned long long g_dictStamp = 0; // guarded by g_mutex

        struct LoadResult
        {
            size_t entries = 0;
            size_t templates = 0;
            size_t tooLong = 0;
        };

        // "<game folder>\T7Patch" from the main module location - the process
        // working directory is not guaranteed to be the game folder.
        bool BuildDataDir(char* dirOut, size_t dirSize)
        {
            char exe[MAX_PATH] = {};
            if (GetModuleFileNameA(nullptr, exe, MAX_PATH) == 0)
                return false;
            char* slash = strrchr(exe, '\\');
            if (!slash)
                return false;
            *slash = '\0';
            const int n = snprintf(dirOut, dirSize, "%s\\T7Patch", exe);
            return n > 0 && static_cast<size_t>(n) < dirSize;
        }

        bool BuildDictionaryPath(char* pathOut, size_t pathSize)
        {
            char dir[MAX_PATH * 2] = {};
            if (!BuildDataDir(dir, sizeof(dir)))
                return false;
            const int n = snprintf(pathOut, pathSize, "%s\\translate_zh.txt", dir);
            return n > 0 && static_cast<size_t>(n) < pathSize;
        }

        // Last write time of the dictionary file; 0 when it does not exist.
        unsigned long long FileStamp(const char* path)
        {
            WIN32_FILE_ATTRIBUTE_DATA fad = {};
            if (!GetFileAttributesExA(path, GetFileExInfoStandard, &fad))
                return 0;
            return (static_cast<unsigned long long>(fad.ftLastWriteTime.dwHighDateTime) << 32) |
                static_cast<unsigned long long>(fad.ftLastWriteTime.dwLowDateTime);
        }

        // True when the text carries a CJK ideograph.  Collection mode skips
        // those runs: they are the game's own Chinese (or another language we do
        // not handle), and translated text must never be fed back in.
        //
        // Deliberately NARROWER than a plain "any byte >= 0x80" test.  English
        // source strings legitimately carry typographic quotes and accented
        // letters - "Speed Cola: ... the "first raise" animation ..." is exactly
        // that case - and the old test skipped them, so they never reached
        // ui_dump.txt and the sentence could not be proof-read into the
        // dictionary.  Only real CJK is skipped now.
        bool HasCjk(const char* s)
        {
            for (const unsigned char* p = reinterpret_cast<const unsigned char*>(s);
                *p; ++p)
            {
                if (*p < 0xE0 || *p > 0xEF)
                    continue; // not a three-byte UTF-8 lead

                const unsigned char b1 = p[1];
                const unsigned char b2 = p[2];
                if (b1 < 0x80 || b1 > 0xBF || b2 < 0x80 || b2 > 0xBF)
                    continue; // malformed: keep scanning byte by byte

                const unsigned cp = (static_cast<unsigned>(*p & 0x0Fu) << 12) |
                    (static_cast<unsigned>(b1 & 0x3Fu) << 6) |
                    static_cast<unsigned>(b2 & 0x3Fu);

                if (cp >= 0x4E00 && cp <= 0x9FFF)
                    return true; // unified ideographs
                if (cp >= 0x3400 && cp <= 0x4DBF)
                    return true; // extension A
                if (cp >= 0xF900 && cp <= 0xFAFF)
                    return true; // compatibility ideographs
            }
            return false;
        }

        bool HasAsciiLetter(const char* s)
        {
            for (const char* p = s; *p; ++p)
            {
                if ((*p >= 'A' && *p <= 'Z') || (*p >= 'a' && *p <= 'z'))
                    return true;
            }
            return false;
        }

        void TrimTrailing(char* s)
        {
            size_t len = strlen(s);
            while (len > 0 && (s[len - 1] == ' ' || s[len - 1] == '\t' ||
                s[len - 1] == '\r' || s[len - 1] == '\n'))
            {
                s[--len] = '\0';
            }
        }

        // Lower-cases in place.  The dictionary keys are stored lower-cased and
        // lookups lower-case the source, because the front-end renders the same
        // label as "Settings", "SETTINGS" or "settings" depending on the widget;
        // one entry then covers every casing instead of three.
        void LowerInPlace(char* s)
        {
            for (; *s; ++s)
            {
                if (*s >= 'A' && *s <= 'Z')
                    *s = static_cast<char>(*s - 'A' + 'a');
            }
        }

        // ------------------------------------------------------------------
        // Runs
        // ------------------------------------------------------------------
        //
        // The front-end wraps every UI string in control characters and composes
        // longer text out of those wrapped fragments - measured byte-level on
        // 2026-09-15: 0x15 in front and 0x14 behind, so a simple label arrives as
        // 15 "Switch User" 14, and a composed one as 15 "Party Privacy: " 15
        // "Open" 14 (the fragment is nested inside the surrounding sentence).
        //
        // A whole-string lookup can never match a composed string, which is why
        // the *runs* between the markers are translated one at a time: the marker
        // bytes and the spaces around a run are copied through untouched (they
        // are part of the game's own text format), each run is looked up on its
        // own, and a run that misses keeps its original text.  This mirrors what
        // the collector records, so dump and dictionary stay in step.
        struct Run
        {
            const char* body; // first byte of the trimmed visible text
            size_t length;    // bytes of the trimmed visible text
        };

        // Returns the next run at or after *cursor and moves *cursor to its end
        // (the byte after the trimmed text).  False at the end of the string.
        bool NextRun(const char*& cursor, Run& run)
        {
            for (;;)
            {
                // Marker bytes: not part of any run, copied through verbatim.
                while (*cursor && static_cast<unsigned char>(*cursor) < 0x20)
                    ++cursor;
                if (!*cursor)
                    return false;

                const char* end = cursor;
                while (*end && static_cast<unsigned char>(*end) >= 0x20)
                    ++end;

                // Both ends are trimmed for the lookup, because the game pads
                // some labels with a trailing space and the dictionary loader
                // trims its keys the same way.  The skipped bytes are not lost:
                // the caller copies everything around a run verbatim.
                const char* begin = cursor;
                const char* trimmed = end;
                while (begin < trimmed && *begin == ' ')
                    ++begin;
                while (trimmed > begin && trimmed[-1] == ' ')
                    --trimmed;

                if (trimmed > begin)
                {
                    run.body = begin;
                    run.length = static_cast<size_t>(trimmed - begin);
                    cursor = trimmed;
                    return true;
                }

                cursor = end; // nothing but spaces: not a run, keep looking
            }
        }

        // ------------------------------------------------------------------
        // Templates
        // ------------------------------------------------------------------

        // Matches a template against a lower-cased key.  Each '*' captures the
        // text between two literal chunks; the captures index into the key, and
        // line up with the original text because lower-casing is 1:1.
        bool MatchTemplate(const WildPattern& p, const char* key, size_t* captureBegin,
            size_t* captureEnd, size_t captureCap, size_t& captureCount)
        {
            captureCount = 0;
            if (p.parts.size() < 2)
                return false;

            const size_t len = strlen(key);

            const std::string& head = p.parts.front();
            if (len < head.size() || memcmp(key, head.c_str(), head.size()) != 0)
                return false;
            size_t pos = head.size();

            // Middle chunks: the earliest occurrence wins, so the first '*'
            // takes as little as it can - "most used: *" stops at the next
            // literal instead of swallowing the rest of the sentence.
            for (size_t i = 1; i + 1 < p.parts.size(); ++i)
            {
                const std::string& mid = p.parts[i];
                bool found = false;
                for (size_t at = pos; at + mid.size() <= len; ++at)
                {
                    if (memcmp(key + at, mid.c_str(), mid.size()) == 0)
                    {
                        if (captureCount < captureCap)
                        {
                            captureBegin[captureCount] = pos;
                            captureEnd[captureCount] = at;
                            ++captureCount;
                        }
                        pos = at + mid.size();
                        found = true;
                        break;
                    }
                }
                if (!found)
                    return false;
            }

            const std::string& tail = p.parts.back();
            if (len < pos + tail.size() ||
                memcmp(key + len - tail.size(), tail.c_str(), tail.size()) != 0)
            {
                return false;
            }
            if (captureCount < captureCap)
            {
                captureBegin[captureCount] = pos;
                captureEnd[captureCount] = len - tail.size();
                ++captureCount;
            }
            return captureCount == p.parts.size() - 1;
        }

        // Fills 'out' from a template value, replacing each '*' with the matching
        // capture taken from the ORIGINAL text (so "Most Used: hvk-30" keeps the
        // user's casing in the Chinese sentence).
        bool RenderTemplate(const WildPattern& p, const char* original,
            const size_t* captureBegin, const size_t* captureEnd, size_t captureCount,
            char* out, size_t outSize)
        {
            size_t written = 0;
            size_t next = 0;
            for (size_t i = 0; i < p.value.size(); ++i)
            {
                if (p.value[i] == '*')
                {
                    if (next >= captureCount)
                        continue; // more placeholders than captures: drop it
                    for (size_t k = captureBegin[next]; k < captureEnd[next]; ++k)
                    {
                        if (written + 1 >= outSize)
                            return false;
                        out[written++] = original[k];
                    }
                    ++next;
                    continue;
                }
                if (written + 1 >= outSize)
                    return false;
                out[written++] = p.value[i];
            }
            out[written] = 0;
            return written > 0;
        }

        // Caller holds g_mutex.  Exact first, then templates narrow-to-wide.
        bool LookupKeyLocked(const char* lowerKey, const char* original, char* out,
            size_t outSize)
        {
            const auto it = g_dict.find(lowerKey);
            if (it != g_dict.end())
            {
                if (it->second.size() + 1 > outSize)
                    return false;
                memcpy(out, it->second.c_str(), it->second.size() + 1);
                return true;
            }

            for (const WildPattern& p : g_patterns)
            {
                size_t begin[kMaxWildcards] = {};
                size_t end[kMaxWildcards] = {};
                size_t count = 0;
                if (MatchTemplate(p, lowerKey, begin, end, kMaxWildcards, count))
                    return RenderTemplate(p, original, begin, end, count, out, outSize);
            }
            return false;
        }

        // ------------------------------------------------------------------
        // Dictionary file
        // ------------------------------------------------------------------

        // Parses the dictionary out of a memory buffer.  EVERY source goes
        // through here - the external file (slurped, then parsed) and the copy
        // that ships inside the dll as a resource - so there is exactly one
        // parser to keep correct.
        //
        // One entry per line, "English=中文"; lines without '=' and lines
        // starting with '#' (or ';') are skipped, so the file can carry comments
        // and keep the same style as t7patch.conf.
        //
        // A key containing '*' matches a varying tail: "level *" covers every
        // level the game prints without enumerating them.  The value uses '*' as
        // the placeholder for the captured text, in order.
        //
        // Parses into caller-owned tables (never the live ones): the parsing
        // happens outside g_mutex, and only the final publish is locked - same
        // rule as patch_config's loadfrom.
        LoadResult ParseDictionaryBuffer(const char* data, size_t size,
            std::unordered_map<std::string, std::string>& dict,
            std::vector<WildPattern>& patterns)
        {
            LoadResult result;
            if (!data || size == 0)
                return result;

            char line[1024]; // the line limit the loader always had
            size_t at = 0;
            while (at < size)
            {
                const char* start = data + at;
                const char* nl = static_cast<const char*>(memchr(start, '\n', size - at));
                const size_t len = nl ? static_cast<size_t>(nl - start) : (size - at);
                at += len + (nl ? 1u : 0u);

                // Longer than the line buffer: dropped rather than split into two
                // bogus entries (what the file version always did).
                if (len > sizeof(line) - 2)
                {
                    ++result.tooLong;
                    continue;
                }
                if (len == 0)
                    continue;

                memcpy(line, start, len);
                line[len] = 0;

                char* p = line;
                while (*p == ' ' || *p == '\t')
                    ++p;
                if (*p == '#' || *p == ';' || *p == '\n' || *p == '\r' || *p == 0)
                    continue;

                char* eq = strchr(p, '=');
                if (!eq)
                    continue;
                *eq = '\0';

                TrimTrailing(p);
                char* value = eq + 1;
                TrimTrailing(value);
                if (!*p || !*value)
                    continue;

                LowerInPlace(p); // keys are stored lower-cased; see LowerInPlace

                if (strchr(p, '*'))
                {
                    WildPattern pattern;
                    const char* chunk = p;
                    for (;;)
                    {
                        const char* star = strchr(chunk, '*');
                        if (!star)
                        {
                            pattern.parts.push_back(chunk);
                            break;
                        }
                        pattern.parts.push_back(
                            std::string(chunk, static_cast<size_t>(star - chunk)));
                        chunk = star + 1;
                    }
                    if (pattern.parts.size() - 1 > kMaxWildcards)
                        continue; // typo, not a template
                    pattern.value = value;
                    patterns.push_back(pattern);
                    ++result.templates;
                }
                else
                {
                    dict[p] = value;
                    ++result.entries;
                }
            }

            // Narrow templates first: fewer '*' means more literal text, which is
            // the more specific rule.  std::stable_sort keeps the file's order
            // between equally narrow templates.
            std::stable_sort(patterns.begin(), patterns.end(),
                [](const WildPattern& a, const WildPattern& b)
                { return a.parts.size() < b.parts.size(); });

            return result;
        }

        // Slurps the dictionary file and hands it to the parser above.  Reading
        // it whole (instead of line by line) is what lets the external file and
        // the built-in resource share one parser; the file is tens of kilobytes
        // and this runs at most once per save, so the extra copy is free.
        LoadResult ParseDictionaryFile(const char* path,
            std::unordered_map<std::string, std::string>& dict,
            std::vector<WildPattern>& patterns)
        {
            LoadResult result;

            FILE* f = nullptr;
            if (fopen_s(&f, path, "rb") != 0 || !f)
                return result;

            std::string blob;
            char chunk[4096];
            size_t got = 0;
            while ((got = fread(chunk, 1, sizeof(chunk), f)) > 0)
                blob.append(chunk, got);
            fclose(f);

            return ParseDictionaryBuffer(blob.data(), blob.size(), dict, patterns);
        }

        // Where the dictionary currently in force came from.  Worth logging: the
        // two cases look identical in game, and "why is my edit not showing up"
        // is almost always "the file is not there, so the built-in copy is".
        enum class DictSource { None, File, Builtin };

        const char* SourceName(DictSource source)
        {
            switch (source)
            {
            case DictSource::File: return "loaded from file";
            case DictSource::Builtin: return "loaded from the built-in default";
            default: return "NOT loaded - no file and no usable built-in copy";
            }
        }

        // Pulls the dictionary that ships inside the dll.  Read through the
        // resource API so it costs nothing until it is actually needed - Windows
        // pages it in from the image on demand.
        bool LoadBuiltinDictionary(std::string& out)
        {
            // TCHAR flavour on purpose: RT_RCDATA and MAKEINTRESOURCE expand to
            // their WIDE forms in this project, and pairing them with an explicit
            // ...A call is a type error (C2664).
            const HRSRC res = FindResource(nullptr,
                MAKEINTRESOURCE(IDR_TRANSLATE_DICT), RT_RCDATA);
            if (!res)
                return false;
            const DWORD size = SizeofResource(nullptr, res);
            const HGLOBAL handle = LoadResource(nullptr, res);
            if (!handle || size == 0)
                return false;
            const void* data = LockResource(handle);
            if (!data)
                return false;

            out.assign(static_cast<const char*>(data), static_cast<size_t>(size));
            return true;
        }

        // Loads whichever dictionary should be in force and publishes it.
        //
        // The external file wins whenever it yields entries: it is the one the
        // user edits, and honouring it is what keeps "save the file, see it in
        // game two seconds later, no rebuild" working.  The built-in copy is the
        // fallback - it is what makes the install self-contained (nothing to drop
        // next to d3d11.dll) and what keeps translation alive when that file is
        // missing, emptied or corrupt.  Before this, losing that one file
        // silently disabled the whole feature.
        LoadResult LoadEffectiveDictionary(const char* path, unsigned long long stamp,
            DictSource& source)
        {
            std::unordered_map<std::string, std::string> dict;
            std::vector<WildPattern> patterns;
            LoadResult result;
            source = DictSource::None;

            if (stamp != 0)
            {
                result = ParseDictionaryFile(path, dict, patterns);
                if (result.entries > 0)
                    source = DictSource::File;
            }

            if (source == DictSource::None)
            {
                std::string builtin;
                if (LoadBuiltinDictionary(builtin))
                {
                    dict.clear();
                    patterns.clear();
                    result = ParseDictionaryBuffer(builtin.data(), builtin.size(),
                        dict, patterns);
                    if (result.entries > 0)
                        source = DictSource::Builtin;
                }
            }

            if (source == DictSource::None)
                return result; // nothing usable: keep the tables we already have

            {
                std::lock_guard<std::mutex> lock(g_mutex);
                g_dict.swap(dict);
                g_patterns.swap(patterns);
                g_dictStamp = stamp;
                g_enabled.store(true);
            }
            return result;
        }

        // The external dictionary is a file the user edits while the game runs -
        // that is the whole point of keeping it outside the dll - so the lookup
        // path re-checks it: one stat every kPollIntervalMs, and a reload only
        // when the write time changed.  Watching this file is safe where watching
        // t7patch.conf is not: its only writers are deliberate user actions
        // (saving the file by hand, or the overlay's update button), so "the file
        // changed" always means "somebody just replaced it".  patch_config
        // watches a file it also writes itself, which is why that one needs the
        // mtime dance and this one does not.
        //
        // The same poll keeps the built-in copy honest in both directions: losing
        // the file (stamp 0 while we were serving the file) falls back to the
        // built-in default, and the file reappearing later takes precedence again.
        void RefreshDictionaryIfChanged()
        {
            // The updater forces the next lookup to re-read (see RequestReload);
            // hand edits go through the periodic stat below.
            const bool forced = g_reloadRequested.exchange(false);

            const unsigned long long now = GetTickCount64();
            if (!forced && now - g_lastPollMs.load() < kPollIntervalMs)
                return;
            g_lastPollMs.store(now);

            char path[MAX_PATH * 2] = {};
            if (!BuildDictionaryPath(path, sizeof(path)))
                return;

            const unsigned long long stamp = FileStamp(path);
            {
                std::lock_guard<std::mutex> lock(g_mutex);
                if (stamp == g_dictStamp)
                    return; // unchanged - including "still no file, still built-in"
            }

            DictSource source = DictSource::None;
            const LoadResult result = LoadEffectiveDictionary(path, stamp, source);
            if (source == DictSource::None)
                return; // nothing usable: the tables in force are left alone

            Logf("dictionary reloaded (%s): %u entries, %u templates%s",
                source == DictSource::File
                    ? (forced ? "update applied" : "file changed")
                    : "fell back to the built-in default",
                static_cast<unsigned>(result.entries), static_cast<unsigned>(result.templates),
                result.tooLong ? " (some lines were too long and skipped)" : "");
        }

        void AppendCollectedLocked(const char* text)
        {
            char dir[MAX_PATH * 2] = {};
            if (!BuildDataDir(dir, sizeof(dir)))
                return;
            char path[MAX_PATH * 2] = {};
            const int n = snprintf(path, sizeof(path), "%s\\ui_dump.txt", dir);
            if (n <= 0 || static_cast<size_t>(n) >= sizeof(path))
                return;

            FILE* f = nullptr;
            if (fopen_s(&f, path, "ab") != 0 || !f)
                return;
            fprintf(f, "%s\n", text);
            fclose(f);
        }
    }

    void Init()
    {
        const bool wantTranslate = t7patch_cfg_translate_enabled();
        const bool wantCollect = t7patch_cfg_dump_ui_strings();

        g_collect.store(wantCollect);

        if (!wantTranslate)
        {
            std::lock_guard<std::mutex> lock(g_mutex);
            g_dict.clear();
            g_patterns.clear();
            g_dictStamp = 0;
            g_enabled.store(false);
            Logf("init: translate=0 (disabled by config)");
            return;
        }

        char path[MAX_PATH * 2] = {};
        if (!BuildDictionaryPath(path, sizeof(path)))
        {
            Logf("init: cannot resolve the dictionary path");
            return;
        }

        // File first, built-in second - see LoadEffectiveDictionary.  The log
        // line says which one won, because the two are indistinguishable in game.
        DictSource source = DictSource::None;
        const LoadResult result = LoadEffectiveDictionary(path, FileStamp(path), source);

        Logf("init: translate=1, dictionary %s (%u entries, %u templates, collect=%d)",
            SourceName(source),
            static_cast<unsigned>(result.entries), static_cast<unsigned>(result.templates),
            wantCollect ? 1 : 0);
    }

    void RequestReload()
    {
        g_reloadRequested.store(true);
    }

    bool Enabled()
    {
        return g_enabled.load();
    }

    bool DictionaryPath(char* out, size_t outSize)
    {
        if (!out || outSize == 0)
            return false;
        return BuildDictionaryPath(out, outSize);
    }

    unsigned EntryCount()
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        return static_cast<unsigned>(g_dict.size());
    }

    bool Lookup(const char* source, char* out, size_t outSize)
    {
        if (!source || !out || outSize == 0)
            return false;

        // Picks up a dictionary the user saved while the game was running.
        RefreshDictionaryIfChanged();

        // No zero-initialisation: every one of these is fully written before it
        // is read ('key' by memcpy plus an explicit NUL, 'replacement' by
        // LookupKeyLocked, 'firstHit' only up to the matching run).  Writing
        // them with '= {}' meant ~4 KB of memset for every UI string the
        // front-end builds, which was this layer's largest constant cost.
        char key[kRunMax];
        char replacement[kRunMax * 2];
        char firstHit[kRunMax];
        size_t written = 0;
        size_t emitted = 0; // bytes of 'source' already copied into 'out'
        bool replaced = false;

        const char* cursor = source;
        Run run{};
        while (NextRun(cursor, run))
        {
            const size_t bodyAt = static_cast<size_t>(run.body - source);
            if (bodyAt < emitted)
                break; // defensive: a run must never move backwards

            // Everything between the previous run and this one - markers and the
            // spaces the game pads labels with - is copied through verbatim.
            for (size_t i = emitted; i < bodyAt; ++i)
            {
                if (written + 1 >= outSize)
                    return false;
                out[written++] = source[i];
            }

            bool hit = false;
            if (run.length < kRunMax)
            {
                memcpy(key, run.body, run.length);
                key[run.length] = 0;
                LowerInPlace(key);

                std::lock_guard<std::mutex> lock(g_mutex);
                hit = LookupKeyLocked(key, run.body, replacement, sizeof(replacement));
            }

            if (hit)
            {
                if (!replaced)
                {
                    memcpy(firstHit, key, run.length);
                    firstHit[run.length] = 0;
                }
                replaced = true;
                for (const char* p = replacement; *p; ++p)
                {
                    if (written + 1 >= outSize)
                        return false;
                    out[written++] = *p;
                }
            }
            else
            {
                for (size_t i = 0; i < run.length; ++i)
                {
                    if (written + 1 >= outSize)
                        return false;
                    out[written++] = run.body[i];
                }
            }

            emitted = bodyAt + run.length;
        }

        // Trailing spaces and markers after the last run.
        for (const char* p = source + emitted; *p; ++p)
        {
            if (written + 1 >= outSize)
                return false;
            out[written++] = *p;
        }
        out[written] = 0;

        // Sampled diagnostics outside the lock (logging writes a file and the UI
        // thread calls this every frame, so only the first few hits are recorded;
        // five is enough to prove the layer is live).
        //
        // Misses are deliberately NOT logged any more.  With the dictionary
        // settled they are pure noise - a dozen lines every launch saying "still
        // English" - and "which strings are still English in game" is what
        // dump_ui_strings=1 answers properly, with counts and without guessing.
        static std::atomic<int> hits{ 0 };
        if (replaced && hits.fetch_add(1) < 5)
            Logf("hit: \"%s\" -> \"%s\"", firstHit, out);
        return replaced;
    }

    void Collect(const char* text)
    {
        if (!g_collect.load() || !text || !text[0])
            return;

        // Same run split as Lookup: the dump has to hold exactly the pieces the
        // dictionary can match, otherwise a composed string would be recorded as
        // one unmatchable blob - control bytes and all (that is what the first
        // round of collection produced).
        const char* cursor = text;
        Run run{};
        while (NextRun(cursor, run))
        {
            if (run.length >= kRunMax)
                continue;
            char clean[kRunMax];
            memcpy(clean, run.body, run.length);
            clean[run.length] = 0;

            // English sources only: a run without an ASCII letter is a number or
            // a symbol, and one carrying CJK is the game's own Chinese (see
            // HasCjk).
            if (!HasAsciiLetter(clean) || HasCjk(clean))
                continue;

            std::lock_guard<std::mutex> lock(g_mutex);
            if (g_collected >= kCollectMax)
                return;
            if (!g_seen.insert(clean).second)
                continue;
            ++g_collected;
            AppendCollectedLocked(clean);
        }
    }
}
