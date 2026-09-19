#include "zone_compat.h"

#include "framework.h"
#include "t7patch_log.h"

#include <atomic>
#include <cstdio>
#include <cstring>
#include <mutex>

namespace zone_compat
{
    namespace
    {
        std::mutex g_mutex;
        Status g_status;
        std::atomic<bool> g_started{ false };

        // BO3's workshop content folder for this title, relative to the game
        // folder: <steam>\steamapps\common\<game>\..\..\workshop\content\<appid>.
        constexpr const char* kWorkshopRel =
            "\\..\\..\\workshop\\content\\311210";

        // Refuse to walk an absurdly wide folder.  A real library has a few
        // dozen items; anything past this is not a workshop folder.
        constexpr unsigned kMaxItems = 4096;

        // ------------------------------------------------------------------
        // Paths
        // ------------------------------------------------------------------

        // The folder holding the executable, taken from the main module: the
        // process working directory is not necessarily the game folder.
        bool BuildGameDir(char* out, size_t outSize)
        {
            char exe[MAX_PATH] = {};
            if (GetModuleFileNameA(nullptr, exe, MAX_PATH) == 0)
                return false;
            char* slash = strrchr(exe, '\\');
            if (!slash)
                return false;
            *slash = '\0';
            const int n = snprintf(out, outSize, "%s", exe);
            return n > 0 && static_cast<size_t>(n) < outSize;
        }

        // ------------------------------------------------------------------
        // Language
        // ------------------------------------------------------------------

        // localization.txt opens with the language NAME; the zone files use a
        // two-letter code.  Only the names this title actually ships are
        // listed - an unknown name falls through to the zone-folder probe.
        const char* PrefixForLanguageName(const char* name)
        {
            struct Pair { const char* name; const char* prefix; };
            static const Pair kPairs[] =
            {
                { "english", "en" },
                { "french", "fr" },
                { "italian", "it" },
                { "german", "ge" },
                { "spanish", "es" },
                { "russian", "ru" },
                { "polish", "pl" },
                { "japanese", "jp" },
                { "koreana", "ko" },
                { "simplifiedchinese", "sc" },
                { "traditionalchinese", "tc" },
                { "portuguese", "bp" },
            };
            for (const Pair& p : kPairs)
            {
                if (strcmp(p.name, name) == 0)
                    return p.prefix;
            }
            return nullptr;
        }

        bool IsKnownPrefix(const char* p)
        {
            static const char* kPrefixes[] =
            {
                "en", "fr", "it", "ge", "es", "ru", "pl",
                "jp", "ko", "sc", "tc", "bp", "ea",
            };
            for (const char* k : kPrefixes)
            {
                if (p[0] == k[0] && p[1] == k[1])
                    return true;
            }
            return false;
        }

        // First line of <game>\localization.txt, lower-cased and trimmed.
        bool ReadLanguageName(char* out, size_t outSize)
        {
            char gameDir[MAX_PATH] = {};
            if (!BuildGameDir(gameDir, sizeof(gameDir)))
                return false;

            char path[MAX_PATH] = {};
            const int n = snprintf(path, sizeof(path), "%s\\localization.txt",
                gameDir);
            if (n <= 0 || static_cast<size_t>(n) >= sizeof(path))
                return false;

            FILE* f = nullptr;
            if (fopen_s(&f, path, "rb") != 0 || !f)
                return false;

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
            {
                begin = 3; // UTF-8 BOM
            }
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
            out[count] = 0;
            return true;
        }

        // Fallback: the game's own zone folder is packed with the language it
        // booted in (and only that one - the other languages are a separate
        // Steam download), so the most common known prefix there IS the
        // language.  "mp_"/"zm_" style mode prefixes are not in the table.
        bool DetectLanguageFromZoneDir(const char* gameDir, char* out,
            size_t outSize)
        {
            char pattern[MAX_PATH] = {};
            int n = snprintf(pattern, sizeof(pattern), "%s\\zone\\??_*.ff",
                gameDir);
            if (n <= 0 || static_cast<size_t>(n) >= sizeof(pattern))
                return false;

            struct Count { char prefix[3]; unsigned hits; };
            Count counts[16] = {};
            size_t used = 0;

            WIN32_FIND_DATAA fd = {};
            HANDLE h = FindFirstFileA(pattern, &fd);
            if (h == INVALID_HANDLE_VALUE)
                return false;
            do
            {
                if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)
                    continue;
                const char* name = fd.cFileName;
                if (strlen(name) < 3 || name[2] != '_')
                    continue;
                char two[3] = { name[0], name[1], 0 };
                if (!IsKnownPrefix(two))
                    continue;

                size_t i = 0;
                for (; i < used; ++i)
                {
                    if (counts[i].prefix[0] == two[0]
                        && counts[i].prefix[1] == two[1])
                    {
                        ++counts[i].hits;
                        break;
                    }
                }
                if (i == used && used < 16)
                {
                    counts[used].prefix[0] = two[0];
                    counts[used].prefix[1] = two[1];
                    counts[used].hits = 1;
                    ++used;
                }
            } while (FindNextFileA(h, &fd));
            FindClose(h);

            if (used == 0)
                return false;

            size_t best = 0;
            for (size_t i = 1; i < used; ++i)
            {
                if (counts[i].hits > counts[best].hits)
                    best = i;
            }
            if (static_cast<size_t>(2) >= outSize)
                return false;
            out[0] = counts[best].prefix[0];
            out[1] = counts[best].prefix[1];
            out[2] = 0;
            return true;
        }

        // Name first (authoritative), zone folder as the fallback for a
        // language name this build does not know.
        bool DetectLanguage(char* out, size_t outSize)
        {
            char name[64] = {};
            if (ReadLanguageName(name, sizeof(name)))
            {
                if (const char* prefix = PrefixForLanguageName(name))
                {
                    const int n = snprintf(out, outSize, "%s", prefix);
                    return n > 0 && static_cast<size_t>(n) < outSize;
                }
            }

            char gameDir[MAX_PATH] = {};
            if (!BuildGameDir(gameDir, sizeof(gameDir)))
                return false;
            return DetectLanguageFromZoneDir(gameDir, out, outSize);
        }

        // ------------------------------------------------------------------
        // Copying
        // ------------------------------------------------------------------

        bool FileExists(const char* path)
        {
            const DWORD attrs = GetFileAttributesA(path);
            return attrs != INVALID_FILE_ATTRIBUTES
                && !(attrs & FILE_ATTRIBUTE_DIRECTORY);
        }

        // Creates "dir\dest" as a copy of "dir\src" unless it is already there.
        bool CopyIfMissing(const char* dir, const char* srcName,
            const char* destName, unsigned* added)
        {
            char src[MAX_PATH * 2] = {};
            char dest[MAX_PATH * 2] = {};
            int n = snprintf(src, sizeof(src), "%s\\%s", dir, srcName);
            if (n <= 0 || static_cast<size_t>(n) >= sizeof(src))
                return false;
            n = snprintf(dest, sizeof(dest), "%s\\%s", dir, destName);
            if (n <= 0 || static_cast<size_t>(n) >= sizeof(dest))
                return false;

            if (FileExists(dest))
                return false; // already compatible
            if (!FileExists(src))
                return false;

            if (CopyFileA(src, dest, TRUE))
            {
                ++*added;
                return true;
            }
            return false;
        }

        // "<item>\en_zm_map.ff" / ".xpak" -> "<item>\<lang>_zm_map.ff".  The
        // body after the language prefix is shared by every language, so the
        // destination name is just the prefix swapped.
        unsigned AddLanguageZones(const char* itemDir, const char* lang,
            unsigned* added)
        {
            char pattern[MAX_PATH * 2] = {};
            int n = snprintf(pattern, sizeof(pattern), "%s\\en_*", itemDir);
            if (n <= 0 || static_cast<size_t>(n) >= sizeof(pattern))
                return 0;

            unsigned seen = 0;
            WIN32_FIND_DATAA fd = {};
            HANDLE h = FindFirstFileA(pattern, &fd);
            if (h == INVALID_HANDLE_VALUE)
                return 0;
            do
            {
                if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)
                    continue;
                const char* name = fd.cFileName;
                if (_strnicmp(name, "en_", 3) != 0)
                    continue;
                if (++seen > kMaxItems)
                    break;

                char dest[MAX_PATH * 2] = {};
                const int m = snprintf(dest, sizeof(dest), "%s_%s", lang,
                    name + 3);
                if (m <= 0 || static_cast<size_t>(m) >= sizeof(dest))
                    continue;

                CopyIfMissing(itemDir, name, dest, added);
            } while (FindNextFileA(h, &fd));
            FindClose(h);
            return seen;
        }

        // Sound libraries keep the language code in the MIDDLE of the name:
        // "snd\en\zm_map.en.sabl" -> "snd\<lang>\zm_map.<lang>.sabl".
        void AddLanguageSounds(const char* itemDir, const char* lang,
            unsigned* added)
        {
            char srcDir[MAX_PATH * 2] = {};
            char destDir[MAX_PATH * 2] = {};
            int n = snprintf(srcDir, sizeof(srcDir), "%s\\snd\\en", itemDir);
            if (n <= 0 || static_cast<size_t>(n) >= sizeof(srcDir))
                return;
            n = snprintf(destDir, sizeof(destDir), "%s\\snd\\%s", itemDir, lang);
            if (n <= 0 || static_cast<size_t>(n) >= sizeof(destDir))
                return;
            if (GetFileAttributesA(srcDir) == INVALID_FILE_ATTRIBUTES)
                return; // this item carries no sounds
            if (!CreateDirectoryA(destDir, nullptr)
                && GetLastError() != ERROR_ALREADY_EXISTS)
            {
                return;
            }

            char pattern[MAX_PATH * 2] = {};
            n = snprintf(pattern, sizeof(pattern), "%s\\*", srcDir);
            if (n <= 0 || static_cast<size_t>(n) >= sizeof(pattern))
                return;

            WIN32_FIND_DATAA fd = {};
            HANDLE h = FindFirstFileA(pattern, &fd);
            if (h == INVALID_HANDLE_VALUE)
                return;
            do
            {
                if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)
                    continue;
                const char* name = fd.cFileName;
                const char* at = strstr(name, ".en.");
                if (!at)
                    continue;
                if (strlen(name) >= MAX_PATH)
                    continue;

                char dest[MAX_PATH] = {};
                const size_t head = static_cast<size_t>(at - name);
                const int m = snprintf(dest, sizeof(dest), "%.*s.%s.%s",
                    static_cast<int>(head), name, lang, at + 4);
                if (m <= 0 || static_cast<size_t>(m) >= sizeof(dest))
                    continue;

                CopyIfMissing(srcDir, name, dest, added);
            } while (FindNextFileA(h, &fd));
            FindClose(h);
        }

        // ------------------------------------------------------------------
        // Scan
        // ------------------------------------------------------------------

        void Scan()
        {
            Status result;

            char lang[16] = {};
            if (!DetectLanguage(lang, sizeof(lang)))
            {
                result.message[0] = 0;
                snprintf(result.message, sizeof(result.message),
                    "custom-map compatibility off: unknown game language");
                std::lock_guard<std::mutex> lock(g_mutex);
                g_status = result;
                t7log::Append("zone", "language unknown - nothing to do");
                return;
            }
            snprintf(result.language, sizeof(result.language), "%s", lang);

            // English is what the authors ship, so there is nothing to add.
            if (strcmp(lang, "en") == 0)
            {
                snprintf(result.message, sizeof(result.message),
                    "custom-map compatibility off: the game runs in English");
                std::lock_guard<std::mutex> lock(g_mutex);
                g_status = result;
                t7log::Append("zone", "language is en - nothing to do");
                return;
            }

            char gameDir[MAX_PATH] = {};
            if (!BuildGameDir(gameDir, sizeof(gameDir)))
                return;

            char root[MAX_PATH * 2] = {};
            int n = snprintf(root, sizeof(root), "%s%s", gameDir, kWorkshopRel);
            if (n <= 0 || static_cast<size_t>(n) >= sizeof(root))
                return;

            char pattern[MAX_PATH * 2] = {};
            n = snprintf(pattern, sizeof(pattern), "%s\\*", root);
            if (n <= 0 || static_cast<size_t>(n) >= sizeof(pattern))
                return;

            WIN32_FIND_DATAA fd = {};
            HANDLE h = FindFirstFileA(pattern, &fd);
            if (h == INVALID_HANDLE_VALUE)
            {
                snprintf(result.message, sizeof(result.message),
                    "custom-map compatibility: no workshop folder found");
                std::lock_guard<std::mutex> lock(g_mutex);
                g_status = result;
                t7log::Append("zone", "no workshop folder - nothing to do");
                return;
            }
            do
            {
                if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY))
                    continue;
                if (fd.cFileName[0] == '.')
                    continue;
                if (result.maps >= kMaxItems)
                    break;
                ++result.maps;

                char item[MAX_PATH * 2] = {};
                n = snprintf(item, sizeof(item), "%s\\%s", root, fd.cFileName);
                if (n <= 0 || static_cast<size_t>(n) >= sizeof(item))
                    continue;

                AddLanguageZones(item, lang, &result.added);
                AddLanguageSounds(item, lang, &result.added);
            } while (FindNextFileA(h, &fd));
            FindClose(h);

            snprintf(result.message, sizeof(result.message),
                "custom-map compatibility: %s, %u file(s) added across %u item(s)",
                lang, result.added, result.maps);

            {
                std::lock_guard<std::mutex> lock(g_mutex);
                g_status = result;
            }
            t7log::Append("zone", result.message);
        }

        DWORD WINAPI ScanThread(LPVOID)
        {
            Scan();
            return 0;
        }
    }

    void Start()
    {
        if (g_started.exchange(true))
            return;
        if (!CreateThread(nullptr, 0, ScanThread, nullptr, 0, nullptr))
        {
            OutputDebugStringA("T7 Patch: could not create the zone scan thread\n");
        }
    }

    Status Get()
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        return g_status;
    }
}
