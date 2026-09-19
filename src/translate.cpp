#include "translate.h"
#include "translate_res.h" // [LOCAL] IDR_TRANSLATE_DICT: the dictionary built into the dll
#include "framework.h"
#include "t7patch_log.h" // [LOCAL] diagnostics: one line per load attempt

#include <algorithm>
#include <atomic>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <fstream>

#include <fstream>
#include <mutex>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

namespace translate
{
    // [LOCAL] 2026-09-20: declared at this scope because the anonymous
    // namespace below calls them, while their definitions sit further down
    // (next to the loaders themselves, outside the anonymous namespace).
    void LoadHanziTable();
    void RefreshFallbackTablesIfChanged();

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

        // Compositional fragments: a dictionary entry whose KEY starts with '~'
        // may be substituted INSIDE a longer run, not only when it is the whole
        // run.  That is what keeps a NEW combination translatable in the part
        // that already has an agreed translation - "Rogue Run: Black Ops 3"
        // becomes "Rogue Run: 黑色行动 3" from one marked fragment, with no
        // hand-written entry for the combination and without having to invent a
        // translation for the mod name itself (see the skill's ambiguity rule).
        //
        // Deliberately OPT-IN, entry by entry: only a key a human marked can
        // fire.  A blanket "replace every dictionary key you find in the text"
        // pass was rejected - the short single words ("menu", "play", "rogue")
        // are exactly what player names, group names and workshop map names
        // collide with.
        //
        // Ordered longest key first (stable for equal lengths), so "black ops 3"
        // wins over a shorter fragment wherever both could match.
        struct Fragment
        {
            std::string key;   // lower-cased source text, marker already stripped
            std::string value; // the translation, used verbatim
        };
        std::vector<Fragment> g_fragments;

        // Shorter than this and a marked fragment is a typo rather than a rule:
        // a two-letter substring would fire inside unrelated words.
        constexpr size_t kMinFragmentKey = 3;

        std::mutex g_mutex; // guards the three tables above and g_dictStamp

        std::atomic<bool> g_enabled{ false }; // translate=1 AND the dictionary loaded
        std::atomic<bool> g_collect{ false }; // dev_tools=1

        // [LOCAL] Scene gate - "the player is inside a match, in a mode whose
        // 'do not translate this scene' switch is on" (see SetSceneBlocked in
        // translate.h; the switch itself lives in the config, the decision is
        // made in Protection.cpp's MainThread loop and only the RESULT arrives
        // here).  Deliberately separate from g_enabled: g_enabled is "the
        // dictionary is loaded and the feature is switched on", which stays true
        // through a match, so leaving and re-entering one costs nothing but this
        // flag - no reload, no log line, no dictionary parse.  The render thread
        // reads it on every UI string, hence the atomic; the MainThread writes it
        // at most once a second.
        std::atomic<bool> g_sceneBlocked{ false };

        // [LOCAL] 2026-09-19: the player told us this map's own font cannot draw
        // what we would write, so replace nothing here - the English original
        // is what that font CAN draw.  Kept as an atomic next to g_sceneBlocked
        // for the same reason: the render thread reads it for every string,
        // while the config write happens at most once a settings apply.
        std::atomic<bool> g_englishFallback{ false };



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

        // NOTE: the fallback table loaders are declared at translate:: scope
        // (see just below "namespace translate"), NOT inside this anonymous
        // namespace - a declaration in here would name a different function and
        // every call to it would be ambiguous.

        // [LOCAL] The start-up language gate runs once per session - see the
        // note at the top of Init().  exchange() is the guard, so two racing
        // Init calls (render thread + MainThread) still only run it once.
        std::atomic<bool> g_langGateDone{ false };

        struct LoadResult
        {
            size_t entries = 0;
            size_t templates = 0;
            size_t fragments = 0;
            size_t tooLong = 0;
        };

        // The game folder itself, from the main module location - the process
        // working directory is not guaranteed to be the game folder.
        bool BuildGameDir(char* dirOut, size_t dirSize)
        {
            char exe[MAX_PATH] = {};
            if (GetModuleFileNameA(nullptr, exe, MAX_PATH) == 0)
                return false;
            char* slash = strrchr(exe, '\\');
            if (!slash)
                return false;
            *slash = '\0';
            const int n = snprintf(dirOut, dirSize, "%s", exe);
            return n > 0 && static_cast<size_t>(n) < dirSize;
        }

        // "<game folder>\T7Patch" - where the patch keeps its runtime files.
        bool BuildDataDir(char* dirOut, size_t dirSize)
        {
            char gameDir[MAX_PATH] = {};
            if (!BuildGameDir(gameDir, sizeof(gameDir)))
                return false;
            const int n = snprintf(dirOut, dirSize, "%s\\T7Patch", gameDir);
            return n > 0 && static_cast<size_t>(n) < dirSize;
        }

        // [LOCAL] The language the GAME ITSELF booted with, straight out of the
        // localization.txt that sits next to the executable: its first line is
        // the language name ("simplifiedchinese", "traditionalchinese" and
        // "english" are the three values this machine has actually produced).
        // Comes back lower-cased and trimmed.
        //
        // Returns false when the file cannot be read or its first line is
        // empty, i.e. the language could not be determined.  The start-up gate
        // counts that as "not Chinese" too - see Init: the replacements need CJK
        // glyphs to draw at all, so a language we cannot prove to be Chinese has
        // to be treated the same way as one we know is not.
        bool ReadGameLanguage(char* out, size_t outSize)
        {
            if (!out || outSize < 2)
                return false;

            char gameDir[MAX_PATH * 2] = {};
            if (!BuildGameDir(gameDir, sizeof(gameDir)))
                return false;
            char path[MAX_PATH * 2] = {};
            const int n = snprintf(path, sizeof(path), "%s\\localization.txt", gameDir);
            if (n <= 0 || static_cast<size_t>(n) >= sizeof(path))
                return false;

            FILE* f = nullptr;
            if (fopen_s(&f, path, "rb") != 0 || !f)
                return false;

            // The first line is all we need - the rest of the file is the
            // game's localised system-dialog text.
            char buf[128] = {};
            const size_t got = fread(buf, 1, sizeof(buf) - 1, f);
            fclose(f);
            if (got == 0)
                return false;

            size_t end = 0;
            while (end < got && buf[end] != '\r' && buf[end] != '\n')
                ++end;
            size_t begin = 0;
            if (end >= 3 && static_cast<unsigned char>(buf[0]) == 0xEF
                && static_cast<unsigned char>(buf[1]) == 0xBB
                && static_cast<unsigned char>(buf[2]) == 0xBF)
                begin = 3; // UTF-8 BOM
            while (begin < end && (buf[begin] == ' ' || buf[begin] == '\t'))
                ++begin;
            while (end > begin && (buf[end - 1] == ' ' || buf[end - 1] == '\t'))
                --end;

            const size_t count = end - begin;
            if (count == 0 || count >= outSize)
                return false;
            for (size_t i = 0; i < count; ++i)
            {
                char c = buf[begin + i];
                if (c >= 'A' && c <= 'Z')
                    c = static_cast<char>(c + ('a' - 'A'));
                out[i] = c;
            }
            out[count] = '\0';
            return true;
        }

        // [LOCAL] Can this language pack use the dictionary at all?  Any Chinese
        // pack can, Simplified and Traditional alike:
        //   * the dictionary's replacements are all Simplified, and on
        //     2026-09-16 the owner tested a Traditional install: our Simplified
        //     text renders normally there - mixed scripts, but readable, and he
        //     liked the result.  Traditional is therefore accepted instead of
        //     being switched off;
        //   * everything else - English, Japanese, Russian, ... - ships no CJK
        //     glyphs at all, so the layer could only ever paint boxes (or
        //     invisible text) over the UI it touches.  That is what the gate is
        //     there to prevent.
        // Testing the "chinese" substring covers every spelling seen so far: the
        // retail names "simplifiedchinese" / "traditionalchinese" and the Steam
        // short forms "schinese" / "tchinese" all contain it.
        bool IsChineseGameLanguage(const char* lang)
        {
            if (!lang || !*lang)
                return false;
            return strstr(lang, "chinese") != nullptr;
        }

        bool BuildDictionaryPath(char* pathOut, size_t pathSize)
        {
            char dir[MAX_PATH * 2] = {};
            if (!BuildDataDir(dir, sizeof(dir)))
                return false;
            // Only one dictionary ships now: the Chinese one.  A pinyin variant
            // used to sit next to it for maps whose own font has no CJK glyphs;
            // that was dropped - the garbled-text switch turns the Chinese back
            // into English instead, which reads better.
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

        // Defined further down (after ComposeFragments), but RenderTemplate needs
        // it: a capture handed back by a template gets exactly one more look-up -
        // the exact entries and the marked fragments, never the templates, since
        // re-entering the template table from inside a template is the one way
        // this could recurse.
        bool LookupCaptureLocked(const char* lowerKey, const char* original,
            char* out, size_t outSize);

        // Fills 'out' from a template value, replacing each '*' with the matching
        // capture taken from the ORIGINAL text (so "Most Used: hvk-30" keeps the
        // user's casing in the Chinese sentence).  A capture the dictionary can
        // translate IN PART is translated in part (see LookupCaptureLocked);
        // whatever it cannot match is copied out byte for byte.
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

                    // The capture is data no dictionary can enumerate (a player
                    // name, a weapon, a mod name, a number) - but it can still
                    // CONTAIN something the dictionary does know: the settings
                    // profile "Rogue Run: Black Ops 3" carries the marked
                    // fragment "black ops 3".  Without this second look-up the
                    // capture stayed fully Latin even though the fragment was
                    // right there.
                    const size_t capFrom = captureBegin[next];
                    const size_t capTo = captureEnd[next];
                    const size_t capLen = capTo - capFrom;
                    bool copied = false;

                    if (capLen > 0 && capLen < kRunMax)
                    {
                        char subKey[kRunMax];
                        char subOut[kRunMax * 2];
                        memcpy(subKey, original + capFrom, capLen);
                        subKey[capLen] = 0;
                        LowerInPlace(subKey);
                        if (LookupCaptureLocked(subKey, original + capFrom, subOut,
                                sizeof(subOut)))
                        {
                            const size_t subLen = strlen(subOut);
                            if (written + subLen + 1 > outSize)
                                return false;
                            memcpy(out + written, subOut, subLen);
                            written += subLen;
                            copied = true;
                        }
                    }

                    if (!copied)
                    {
                        for (size_t k = capFrom; k < capTo; ++k)
                        {
                            if (written + 1 >= outSize)
                                return false;
                            out[written++] = original[k];
                        }
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

        // Substitutes the marked fragments inside a run.  'lowerKey' and
        // 'original' hold the same text - LowerInPlace only rewrites A-Z, so the
        // two stay byte-for-byte index-aligned - and every untouched byte is
        // copied out of 'original', which is what preserves the game's own casing
        // around a replacement.
        //
        // Single left-to-right pass: at each position the longest matching
        // fragment wins and the cursor jumps past it, so a replacement is never
        // re-scanned and a fragment value containing Latin text cannot feed
        // another fragment.  Returns false when nothing matched, in which case
        // the caller keeps the game's text, exactly like an exact-entry miss.
        bool ComposeFragments(const char* lowerKey, const char* original, char* out,
            size_t outSize)
        {
            const size_t len = strlen(lowerKey);
            size_t written = 0;
            size_t at = 0;
            bool matched = false;

            while (at < len)
            {
                const Fragment* hit = nullptr;
                for (const Fragment& f : g_fragments)
                {
                    if (f.key.size() <= len - at
                        && memcmp(lowerKey + at, f.key.data(), f.key.size()) == 0)
                    {
                        hit = &f; // longest first: the first hit is the specific one
                        break;
                    }
                }

                if (!hit)
                {
                    if (written + 1 >= outSize)
                        return false;
                    out[written++] = original[at];
                    ++at;
                    continue;
                }

                if (written + hit->value.size() + 1 > outSize)
                    return false;
                memcpy(out + written, hit->value.data(), hit->value.size());
                written += hit->value.size();
                at += hit->key.size();
                matched = true;
            }

            if (!matched)
                return false;
            out[written] = 0;
            return true;
        }

        // Caller holds g_mutex.  One more look-up for a capture a TEMPLATE just
        // handed back: exact entries first, then the marked fragments - and
        // deliberately NOT the templates, because this input came out of a
        // template and matching another one is the only way it could recurse.
        //
        // Returns false when nothing matched; the caller then copies the capture
        // out byte for byte, exactly like an exact-entry miss.
        bool LookupCaptureLocked(const char* lowerKey, const char* original,
            char* out, size_t outSize)
        {
            const auto it = g_dict.find(lowerKey);
            if (it != g_dict.end())
            {
                if (it->second.size() + 1 > outSize)
                    return false;
                memcpy(out, it->second.c_str(), it->second.size() + 1);
                return true;
            }
            if (!g_fragments.empty())
                return ComposeFragments(lowerKey, original, out, outSize);
            return false;
        }

        // [LOCAL] 2026-09-19: turn Chinese back into English, word by word.
        //
        // The English switch cannot simply step aside.  Stepping aside only
        // brings OUR replacements back to English - those had an English
        // original to begin with.  Strings the game and the map wrote themselves
        // are Chinese and STAY Chinese, and a map whose font has no CJK glyphs
        // draws them as boxes no matter what we do.  So they get translated
        // here, using the dictionary reversed (tools/make_zh_to_en.py).  Words
        // the table does not know are left as they are - those stay Chinese,
        // which is the one case this switch cannot help with.
        //
        // Longest match wins, walking left to right, so a table holding both
        // "剩余" and "剩余敌人" picks the longer one.
        // [LOCAL] Full-width punctuation lives in the CJK ranges, so a font with
        // Latin glyphs only draws it as a box exactly like a Han character does.
        // These are the ones the game actually emits, each mapped to its ASCII
        // counterpart.  "…" expands to three characters, which is why this
        // returns a string rather than a char.
        const char* AsciiForFullWidth(const char* ch)
        {
            struct Pair { const char* from; const char* to; };
            static const Pair kPairs[] = {
                { "，", "," }, { "。", "." }, { "！", "!" }, { "？", "?" },
                { "：", ":" }, { "；", ";" }, { "、", "," }, { "（", "(" },
                { "）", ")" }, { "「", "\"" }, { "」", "\"" }, { "『", "\"" },
                { "』", "\"" }, { "【", "[" }, { "】", "]" }, { "《", "<" },
                { "》", ">" }, { "—", "-" }, { "–", "-" }, { "～", "~" },
                { "…", "..." }, { "　", " " }, { "“", "\"" }, { "”", "\"" },
                { "‘", "'" }, { "’", "'" }, { "％", "%" },
            };
            for (const Pair& kv : kPairs)
                if (memcmp(ch, kv.from, 3) == 0)
                    return kv.to;
            return nullptr;
        }

        // [LOCAL] The fallback writes its English in capitals on purpose - it is
        // standing in for text the map cannot draw, and block capitals sit
        // better next to the game's own all-caps labels.  ONLY what the table
        // produced is upper-cased; text copied through untouched keeps whatever
        // case the game or the map gave it.
        void CopyUpper(const char* from, char* to)
        {
            while (*from)
            {
                const unsigned char c = static_cast<unsigned char>(*from++);
                *to++ = static_cast<char>(c >= 'a' && c <= 'z' ? c - 32 : c);
            }
            *to = 0;
        }

        // ASCII letter or digit - the only characters that need a space between
        // them when two translated words end up adjacent.  Punctuation, Han
        // characters and control bytes all glue fine.
        bool IsAsciiAlnum(char c)
        {
            return (c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z')
                || (c >= 'a' && c <= 'z');
        }

        // [LOCAL] 2026-09-20: memoized per-run translations for the fallback
        // switch.  The same label is drawn EVERY frame, and the table walk is
        // dozens of hashes per run - at the official maps' text volume that was
        // enough to stall the render thread (BlackOps3.exe went unresponsive at
        // 0:55 with the uncached 45-byte walk).  Guarded by g_mutex, which the
        // caller holds; cleared when the table reloads.
        constexpr size_t kRenderCacheMax = 2048;
        std::unordered_map<std::string, std::string> g_renderCache;

        // [LOCAL] 2026-09-20: one Han character -> its pinyin (camel case, one
        // syllable per entry).  The map-safe switch spells Chinese out with it,
        // character by character - replacement cannot reorder a sentence the
        // way English translation does, needs no phrase table, and covers every
        // character GB2312 lists, so nothing is ever left as boxes.
        std::unordered_map<std::string, std::string> g_hanzi;
        unsigned long long g_hanziStamp = 0; // guarded by g_mutex

        // sourceLen is the length of THIS RUN, which is not strlen(source): the
        // hooks hand over a pointer into the middle of a longer label, so the
        // bytes after the run belong to the next one.
        bool RenderPinyinInner(const char* source, size_t sourceLen, char* out,
            size_t outSize)
        {
            const unsigned char* p = reinterpret_cast<const unsigned char*>(source);
            const size_t total = sourceLen;

            // A run without a single Han character has nothing to spell out -
            // skip the whole walk for it.  Front-end labels are often pure
            // ASCII and this is the cheap way out for those.
            bool hasHan = false;
            for (size_t i = 0; i < total; ++i)
            {
                if (p[i] >= 0xE0)
                {
                    hasHan = true;
                    break;
                }
            }
            if (!hasHan)
                return false;

            size_t written = 0;
            bool converted = false;
            // True right after a syllable was written: the NEXT syllable needs
            // a space before it ("Dan Yao", never "DanYao"), and so does plain
            // ASCII the run already had ("An" then "ENTER" stays two words).
            bool afterWord = false;

            for (size_t at = 0; at < total;)
            {
                    // Six                 // UTF-8 length from the lead byte, verified against the
                    // continuation range so a stray byte cannot swallow its
                    // neighbour.
                    size_t len = 1;
                    if ((p[at] & 0xE0u) == 0xC0u)
                        len = 2;
                    else if ((p[at] & 0xF0u) == 0xE0u)
                        len = 3;
                    else if ((p[at] & 0xF8u) == 0xF0u)
                        len = 4;
                    for (size_t i = 1; i < len && at + i < total; ++i)
                    {
                        if ((p[at + i] & 0xC0) != 0x80)
                        {
                            len = 1;
                            break;
                        }
                    }
                    if (at + len > total)
                        len = total - at;

                    // Multi-character phrases first: a 多音字 needs context - "重建"
                    // is Chong Jian, never Zhong.  The table carries the common
                    // phrase readings; longest match beats the single characters
                    // below.  (Cap 18 bytes = 6 characters.  'pl-- > 6', not
                    // 'pl >= 6; --pl': size_t would wrap past zero and loop forever.)
                    if (len >= 6)
                    {
                        size_t maxLen = 18;
                        if (maxLen > total - at)
                            maxLen = total - at;
                        bool phraseHit = false;
                        for (size_t pl = maxLen + 1; pl-- > 6; )
                        {
                            if ((p[at + pl] & 0xC0) == 0x80)
                                continue;
                            char cand[19] = {};
                            memcpy(cand, p + at, pl);
                            const auto pit = g_hanzi.find(cand);
                            if (pit == g_hanzi.end())
                                continue;
                            const std::string& v = pit->second; // may hold spaces
                            if (written && IsAsciiAlnum(out[written - 1]))
                            {
                                if (written + v.size() + 2 > outSize)
                                    return false;
                                out[written++] = ' ';
                            }
                            else if (written + v.size() + 1 > outSize)
                                return false;
                            memcpy(out + written, v.c_str(), v.size());
                            written += v.size();
                            at += pl;
                            converted = true;
                            afterWord = true;
                            phraseHit = true;
                            break;
                        }
                        if (phraseHit)
                            continue;
                    }

                    if (len == 3)
                    {
                        char ch[4] = {};
                        memcpy(ch, p + at, 3);
                        if (const char* ascii = AsciiForFullWidth(ch))
                        {
                            const size_t n = strlen(ascii);
                            if (written + n + 1 > outSize)
                                return false;
                            memcpy(out + written, ascii, n);
                            written += n;
                            at += 3;
                            converted = true;
                            afterWord = false; // punctuation closes a word
                            continue;
                        }

                        // A Han character: spell it out.  The space before the
                        // syllable - after the previous syllable, or after ASCII
                        // the run already had - is what keeps "DanYaoQuanMan"
                        // readable as "Dan Yao Quan Man".
                        const auto hit = g_hanzi.find(std::string(ch, 3));
                        if (hit != g_hanzi.end())
                        {
                            const size_t n = hit->second.size();
                            if (written && IsAsciiAlnum(out[written - 1]))
                            {
                                if (written + n + 2 > outSize)
                                    return false;
                                out[written++] = ' ';
                            }
                            else if (written + n + 1 > outSize)
                                return false;
                            memcpy(out + written, hit->second.c_str(), n);
                            written += n;
                            at += 3;
                            converted = true;
                            afterWord = true;
                            continue;
                        }
                    }

                    // Not in the table, or not a Han character: copy through as it
                    // is - ASCII the run already had, a rare ideograph outside the
                    // table, a typographic quote.  Nothing here needs a space.
                    if (afterWord)
                    {
                        if (IsAsciiAlnum(char(p[at])))
                        {
                            if (written + len + 2 > outSize)
                                return false;
                            out[written++] = ' ';
                        }
                        afterWord = false;
                    }
                    if (written + len + 1 > outSize)
                        return false;
                    memcpy(out + written, p + at, len);
                    written += len;
                    at += len;
                    }

                    if (!converted)
                    return false; // nothing to spell out - the caller keeps it
                    out[written] = 0;
                    return true;
                    }

        // [LOCAL] 2026-09-20: memoizing wrapper.  The same label is redrawn
        // EVERY frame, and without this the table walk - up to 40 hashes per
        // run, each building a temporary std::string - ran at the official
        // maps' text volume and stalled the render thread far enough for
        // Windows to call the game unresponsive.  With it the walk happens
        // once per distinct run and every redraw after that is one hash
        // lookup.  Callers hold g_mutex; the cache is dropped whenever the
        // table it was built from reloads.
        bool RenderPinyin(const char* source, size_t sourceLen, char* out, size_t outSize)
        {
            if (!g_englishFallback.load() || g_hanzi.empty())
                return false;

            std::string key(source, sourceLen);
            const auto cached = g_renderCache.find(key);
            if (cached != g_renderCache.end())
            {
                const std::string& v = cached->second;
                if (v.empty())
                    return false; // a remembered miss: leave the run alone
                if (v.size() + 1 > outSize)
                    return false;
                memcpy(out, v.c_str(), v.size() + 1);
                return true;
            }

            char buf[4096]; // a run is at most kRunMax and each syllable adds a
                            // handful of bytes, so this never runs out in practice
            const bool ok = RenderPinyinInner(source, sourceLen, buf, sizeof(buf));
            if (g_renderCache.size() >= kRenderCacheMax)
                g_renderCache.clear(); // simple bound; the UI refills it within a frame
            if (ok)
                g_renderCache.emplace(key, buf);
            else
                g_renderCache.emplace(key, std::string());
            if (!ok)
                return false;
            const size_t n = strlen(buf);
            if (n + 1 > outSize)
                return false;
            memcpy(out, buf, n + 1);
            return true;
        }

        // Caller holds g_mutex.  Exact entries first, then templates
        // narrow-to-wide, then the marked fragments (composition) - the most
        // specific rule always gets the first say.
        bool LookupKeyLocked(const char* lowerKey, const char* original, size_t originalLen,
            char* out, size_t outSize)
        {
            // [LOCAL] The garbled-text switch.  On a map whose own font cannot
            // draw Chinese the dictionary must not run at all - its Chinese
            // output is exactly what turns into boxes.  Every Han character is
            // spelled out in pinyin instead (user's final call: per-character
            // replacement cannot reorder a sentence and needs no phrase table),
            // while anything we never touched was English to begin with.
            if (g_englishFallback.load())
                return RenderPinyin(original, originalLen, out, outSize);

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

            if (!g_fragments.empty())
                return ComposeFragments(lowerKey, original, out, outSize);
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
        // A key starting with '~' marks a COMPOSABLE fragment: it is usable
        // inside a longer run as well as on its own (see Fragment).  The marker
        // is checked before the '*' test, so a marked entry can never be mistaken
        // for a template, and the marker itself is never part of the key.
        //
        // Parses into caller-owned tables (never the live ones): the parsing
        // happens outside g_mutex, and only the final publish is locked - same
        // rule as patch_config's loadfrom.
        LoadResult ParseDictionaryBuffer(const char* data, size_t size,
            std::unordered_map<std::string, std::string>& dict,
            std::vector<WildPattern>& patterns,
            std::vector<Fragment>& fragments)
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

                // The '~' marker turns an entry into a composable fragment (see
                // Fragment).  It is stripped here, before anything else looks at
                // the key, so no table ever holds the marker.  A marked key that
                // is too short is dropped instead of loaded - it would fire
                // inside unrelated words.
                bool composable = false;
                if (*p == '~')
                {
                    composable = true;
                    ++p;
                    while (*p == ' ' || *p == '\t')
                        ++p;
                    if (strlen(p) < kMinFragmentKey)
                        continue; // typo, not a rule
                }

                if (composable)
                {
                    Fragment fragment;
                    fragment.key = p;
                    fragment.value = value;
                    fragments.push_back(fragment);
                    ++result.fragments;
                }
                else if (strchr(p, '*'))
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
            //
            // [LOCAL] Known limitation, deliberately NOT fixed - the owner's call
            // (2026-09-18): "if the price cannot be translated, leave it, it does
            // not hurt reading".  Specificity really means "how much literal text
            // is pinned down", so a two-wildcard rule such as
            //   hold ^3f^7 for ^3*^7 [cost: *]     (28 literal chars)
            // is MORE specific than the one-wildcard
            //   hold ^3f^7 for *                   (15 literal chars)
            // - but this sort puts the latter first, and every template is matched
            // against the whole run, so the first one swallows the runs the
            // "[cost: *]" family was written for: that family can never fire and
            // every price keeps a hand-written exact entry instead.  The owner
            // accepted that, so this stays as it is - the fix, if it is ever
            // wanted, is to compare total literal length (descending) first.
            std::stable_sort(patterns.begin(), patterns.end(),
                [](const WildPattern& a, const WildPattern& b)
                { return a.parts.size() < b.parts.size(); });

            // Longest fragment first, for the same reason: at one position the
            // longest key is the most specific rule.  Equal lengths keep the
            // file's order, which keeps the outcome predictable.
            std::stable_sort(fragments.begin(), fragments.end(),
                [](const Fragment& a, const Fragment& b)
                { return a.key.size() > b.key.size(); });

            return result;
        }

        // Slurps the dictionary file and hands it to the parser above.  Reading
        // it whole (instead of line by line) is what lets the external file and
        // the built-in resource share one parser; the file is tens of kilobytes
        // and this runs at most once per save, so the extra copy is free.
        LoadResult ParseDictionaryFile(const char* path,
            std::unordered_map<std::string, std::string>& dict,
            std::vector<WildPattern>& patterns,
            std::vector<Fragment>& fragments)
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

            return ParseDictionaryBuffer(blob.data(), blob.size(), dict, patterns,
                fragments);
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
            // The RCDATA lives in THIS module, so this module is what has to be
            // asked for it.  A NULL hModule does not mean "the caller" - it means
            // "the module the process was created from", i.e. BlackOps3.exe, which
            // carries no RT_RCDATA at all.  Asking there always failed, so every
            // install without an external translate_zh.txt silently ran with the
            // whole feature off.  Resolve our own handle from the address of this
            // very function: no global, no init-order dependency.
            HMODULE self = nullptr;
            if (!GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                    GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                    reinterpret_cast<LPCWSTR>(&LoadBuiltinDictionary), &self) || !self)
                return false;

            // TCHAR flavour on purpose: RT_RCDATA and MAKEINTRESOURCE expand to
            // their WIDE forms in this project, and pairing them with an explicit
            // ...A call is a type error (C2664).
            const HRSRC res = FindResource(self,
                MAKEINTRESOURCE(IDR_TRANSLATE_DICT), RT_RCDATA);
            if (!res)
                return false;
            const DWORD size = SizeofResource(self, res);
            const HGLOBAL handle = LoadResource(self, res);
            if (!handle || size == 0)
                return false;
            const void* data = LockResource(handle);
            if (!data)
                return false;

            out.assign(static_cast<const char*>(data), static_cast<size_t>(size));
            return true;
        }

        // Is this parse result worth publishing?  Entries are the normal case,
        // but a dictionary may legitimately consist of templates or of the marked
        // fragments alone.  What must NOT count as usable is an empty or corrupt
        // file - that is what makes an emptied translate_zh.txt fall back to the
        // copy inside the dll.
        bool Usable(const LoadResult& r)
        {
            return r.entries + r.templates + r.fragments > 0;
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
            std::vector<Fragment> fragments;
            LoadResult result;
            source = DictSource::None;

            if (stamp != 0)
            {
                result = ParseDictionaryFile(path, dict, patterns, fragments);
                if (Usable(result))
                    source = DictSource::File;
            }

            if (source == DictSource::None)
            {
                std::string builtin;
                if (LoadBuiltinDictionary(builtin))
                {
                    dict.clear();
                    patterns.clear();
                    fragments.clear();
                    result = ParseDictionaryBuffer(builtin.data(), builtin.size(),
                        dict, patterns, fragments);
                    if (Usable(result))
                        source = DictSource::Builtin;
                }
            }

            if (source == DictSource::None)
                return result; // nothing usable: keep the tables we already have

            {
                std::lock_guard<std::mutex> lock(g_mutex);
                g_dict.swap(dict);
                g_patterns.swap(patterns);
                g_fragments.swap(fragments);
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

            // [LOCAL] 2026-09-20: the English fallback switch reads its own two
            // tables, and until now nothing watched them - they were read once in
            // Init() and then stayed as they were.  Editing a word table looked
            // like it did nothing at all until the game was restarted or the
            // settings were applied, which is exactly what it was doing.  They
            // are polled here with the same interval, and the same "only on
            // change" rule.
            RefreshFallbackTablesIfChanged();

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

            Logf("dictionary reloaded (%s): %u entries, %u templates, %u fragments%s",
                source == DictSource::File
                    ? (forced ? "update applied" : "file changed")
                    : "fell back to the built-in default",
                static_cast<unsigned>(result.entries), static_cast<unsigned>(result.templates),
                static_cast<unsigned>(result.fragments),
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

    // [LOCAL] 2026-09-20: keeps the pinyin table in step with the file while
    // the game runs.  It is the table a collected string is added to, so "I
    // edited the word list and nothing happened" was the normal result before
    // this - the table was only ever read from Init(), which needs the
    // settings to be applied or the game to be restarted.
    // [LOCAL] 2026-09-20: the per-character pinyin table the map-safe switch
    // renders with.  One syllable per entry ("An"); the engine spaces the
    // syllables itself.  GB2312 scope (no rare ideographs) - see the generator.
    void LoadHanziTable()
    {
        char dir[MAX_PATH * 2] = {};
        if (!BuildDataDir(dir, sizeof(dir)))
            return;

        char path[MAX_PATH * 2] = {};
        const int n = snprintf(path, sizeof(path), "%s\\translate_pinyin.txt", dir);
        if (n <= 0 || static_cast<size_t>(n) >= sizeof(path))
            return;

        std::ifstream in(path, std::ios::binary);
        if (!in)
        {
            Logf("init: no pinyin table (%s) - Chinese cannot be spelled out", path);
            return;
        }

        std::unordered_map<std::string, std::string> table;
        std::string line;
        while (std::getline(in, line))
        {
            if (!line.empty() && line.back() == '\r')
                line.pop_back();
            if (line.empty() || line[0] == '#')
                continue;
            const size_t eq = line.find('=');
            if (eq == std::string::npos || eq == 0 || eq + 1 >= line.size())
                continue;
            table[line.substr(0, eq)] = line.substr(eq + 1);
        }

        std::lock_guard<std::mutex> lock(g_mutex);
        g_hanzi.swap(table);
        g_hanziStamp = FileStamp(path);
        g_renderCache.clear(); // the memoized answers were built from the old table
        Logf("init: pinyin table %u character(s) loaded",
            static_cast<unsigned>(g_hanzi.size()));
    }

    void RefreshFallbackTablesIfChanged()
    {
        char dir[MAX_PATH * 2] = {};
        if (!BuildDataDir(dir, sizeof(dir)))
            return;

        // The same path LoadHanziTable builds.
        char zhPath[MAX_PATH * 2] = {};
        const int b = snprintf(zhPath, sizeof(zhPath), "%s\\translate_pinyin.txt", dir);
        if (b <= 0 || static_cast<size_t>(b) >= sizeof(zhPath))
            return;

        const unsigned long long zhStamp = FileStamp(zhPath);

        {
            std::lock_guard<std::mutex> lock(g_mutex);
            if (zhStamp == g_hanziStamp)
                return; // unchanged - nothing to re-read
        }

        // Re-read whole: the loader latches its own stamp, quietly this time.
        LoadHanziTable();
        Logf("english fallback: pinyin table reloaded (%u characters)",
            static_cast<unsigned>(g_hanzi.size()));
    }

    void Init()
    {
        // [LOCAL] Start-up language gate - ONCE per session.  Every replacement
        // in the dictionary is Simplified Chinese, and a language pack that is
        // not Chinese ships no CJK glyphs at all, so on an English game the layer
        // could only ever paint boxes (or invisible text) over the UI it touches.
        // The first Init of the session (RunPatching(), dllmain.cpp, i.e. the
        // earliest one - apply_settings() runs it a second time a few ms later)
        // therefore checks the game's own language and latches the switch off
        // unless that language IS Chinese - Simplified and Traditional both
        // qualify, see IsChineseGameLanguage.
        //
        // Fail closed: "not Chinese" includes a language that could not be read
        // at all.  The rule is "translation only ever runs on a Chinese game", so
        // anything that cannot be positively identified as one - another
        // language, or no answer at all - ends up switched off.
        //
        // Deliberately one-shot: a player who turns the feature back on from the
        // menu afterwards is left alone for the rest of the session - their call,
        // their eyes.
        //
        // This function only ever touches MEMORY (a latch, so the
        // load_settings_initial() re-read 3 ms later cannot undo it) and asks the
        // config layer to write the decision down - see g_translate_language_block
        // and t7patch_cfg_persist_translate_off in Protection.cpp.
        if (!g_langGateDone.exchange(true))
        {
            char lang[64] = {};
            const bool known = ReadGameLanguage(lang, sizeof(lang));
            const bool chinese = known && IsChineseGameLanguage(lang);
            if (!chinese)
            {
                // Latch it - and never edit the config from HERE: this first Init
                // runs from RunPatching(), and load_settings_initial() re-reads the
                // conf immediately afterwards, which would put translate=1 back
                // into memory and re-enable the layer behind the gate's back.  The
                // write belongs to load_settings_initial(), and the request is only
                // raised for a language we actually read (an unreadable one is
                // still held off for the session, but does not rewrite the file).
                t7patch_cfg_block_translate(1);
                if (known)
                {
                    t7patch_cfg_persist_translate_off();
                    Logf("init: the game's own language is \"%s\", not Chinese - "
                        "mod translation switched off (turn it back on in the menu if you "
                        "want it anyway)", lang);
                }
                else
                    Logf("init: cannot read the game's own language (localization.txt) - "
                        "treating it as not Chinese, mod translation off for this "
                        "session only (turn it back on in the menu if you want it anyway)");
            }
        }

        const bool wantTranslate = t7patch_cfg_translate_enabled();
        const bool wantCollect = t7patch_cfg_dev_tools();
        // Read before the early-outs below: the map-safe switch has to follow the
        // config even while translation itself is off, otherwise turning it back
        // on would silently resurrect replacements on a map the player exempted.
        g_englishFallback.store(t7patch_cfg_english_fallback());
        // exchange, not load-then-store: the PREVIOUS collect flag is part of
        // the change-detection key below, so a flipped dev_tools still
        // falls through to a real (re)load and gets its log line.
        const bool prevCollect = g_collect.exchange(wantCollect);

        // [LOCAL] Loaded BEFORE the early-outs below: the map-safe switch reads
        // this table, and it is meant to work for a player whose only problem is
        // one map's font - they may well run with the dictionary switched off.
        LoadHanziTable();

        if (!wantTranslate)
        {
            std::lock_guard<std::mutex> lock(g_mutex);
            if (g_dict.empty() && !g_enabled.load())
                return; // already down - a config re-apply is a no-op, not news
            g_dict.clear();
            g_patterns.clear();
            g_fragments.clear();
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
        const unsigned long long stamp = FileStamp(path);

        // [LOCAL] The config-apply path re-runs Init on every menu Save, and
        // at start-up this runs twice (RunPatching, then the first apply).
        // Ungated, each pass re-parsed the whole dictionary and re-logged the
        // init line - six identical "init:" lines for one settings session.
        // A re-apply that changes nothing (same switch, same collect flag,
        // same dictionary file in force) is a no-op: skip it silently.  The
        // per-frame poll below still catches hand edits to the file itself.
        {
            std::lock_guard<std::mutex> lock(g_mutex);
            if (g_enabled.load() && g_dictStamp == stamp
                && prevCollect == wantCollect)
                return;
        }

        // File first, built-in second - see LoadEffectiveDictionary.  The log
        // line says which one won, because the two are indistinguishable in game.
        DictSource source = DictSource::None;
        const LoadResult result = LoadEffectiveDictionary(path, stamp, source);

        Logf("init: translate=1, dictionary %s (%u entries, %u templates, %u fragments, collect=%d)",
            SourceName(source),
            static_cast<unsigned>(result.entries), static_cast<unsigned>(result.templates),
            static_cast<unsigned>(result.fragments),
            wantCollect ? 1 : 0);
    }

    void RequestReload()
    {
        g_reloadRequested.store(true);
    }

    bool Enabled()
    {
        // Two independent questions, one answer for the callers: is the feature
        // on (dictionary loaded, switch on, language gate passed), and is this
        // moment one the player asked to leave alone.  Folding the scene gate in
        // HERE is what keeps Hooks.cpp untouched - both hooks and the collector
        // already ask Enabled().
        // The garbled-text switch is not folded in as a plain "off": it does not
        // silence the layer, it replaces what the layer does (see LookupKeyLocked
        // - English passes through, Chinese is translated word by word).
        //
        // It can hold the gate open on its own, though, because that mode never
        // touches the dictionary: a player running with translation off can
        // still make one unreadable map readable.
        const bool layerOn = g_enabled.load() || g_englishFallback.load();
        return layerOn && !g_sceneBlocked.load();
    }

    void SetSceneBlocked(bool blocked)
    {
        g_sceneBlocked.store(blocked);
    }

    bool DictionaryPath(char* out, size_t outSize)
        {
            if (!out || outSize == 0)
                return false;
            return BuildDictionaryPath(out, outSize);
        }

    // [LOCAL] 2026-09-20: the pinyin table the map-safe switch renders with.
    bool HanziPath(char* out, size_t outSize)
        {
            char dir[MAX_PATH * 2] = {};
            if (!out || outSize == 0 || !BuildDataDir(dir, sizeof(dir)))
                return false;
            const int n = snprintf(out, outSize, "%s\\translate_pinyin.txt", dir);
            return n > 0 && static_cast<size_t>(n) < outSize;
        }

    unsigned HanziCount()
        {
            std::lock_guard<std::mutex> lock(g_mutex);
            return static_cast<unsigned>(g_hanzi.size());
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
                hit = LookupKeyLocked(key, run.body, run.length, replacement, sizeof(replacement));
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
        // dev_tools=1 answers properly, with counts and without guessing.
        static std::atomic<int> hits{ 0 };
        if (replaced && hits.fetch_add(1) < 5)
            Logf("hit: \"%s\" -> \"%s\"", firstHit, out);
        return replaced;
    }

    void Collect(const char* text)
    {
        if (!g_collect.load() || !text || !text[0])
            return;

        // [LOCAL] The scene gate covers collection too, and that is the point of
        // it here: inside a Multiplayer match the front-end strings the game
        // builds are first and foremost PLAYER NAMES, lobby names and workshop
        // map names - exactly the noise that used to fill ui_dump.txt and make
        // the "what is still English?" worklist unusable.  With the sub-switch on
        // the dump stays clean for free.
        if (g_sceneBlocked.load())
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

            // [LOCAL] 2026-09-19 probe: record the game's OWN Chinese too.
            // Collection used to skip CJK runs ("they are the game's own
            // Chinese" - see HasCjk), which is exactly why we had no list of
            // them.  On a map whose font lacks CJK glyphs those runs draw as
            // boxes just like our replacements do, and the only way to say
            // anything about them is to see them first.  Bare numbers and
            // symbols (neither an ASCII letter nor CJK) are still skipped.
            if (!HasAsciiLetter(clean) && !HasCjk(clean))
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
