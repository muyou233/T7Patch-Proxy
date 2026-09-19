#include "t7patch_log.h"
#include "framework.h"

#include <atomic>
#include <cstdio>
#include <cstring>

namespace t7log
{
    namespace
    {
        // [LOCAL] 2026-09-20: off until the config layer says otherwise - the
        // default for a normal player.  Atomic because Append() runs on several
        // threads (render, MainThread, the updater worker) while SetEnabled()
        // comes from wherever the config is applied.
        std::atomic<bool> g_enabled{ false };

        // Fills `dirOut` with "<game folder>\T7Patch" and `fileOut` with the log
        // path inside it.  The path is built from the main module location, not
        // the working directory: the process working directory is NOT guaranteed
        // to be the game folder - Steam normally sets it, but a launcher or a
        // debugger can leave it elsewhere - and a relative path would then
        // silently write the log into the wrong place (the trap the block log
        // hit before).  Note the CWD is per-process, not per-thread; the earlier
        // wording here blamed the thread.
        bool BuildPaths(char* dirOut, size_t dirSize, char* fileOut, size_t fileSize)
        {
            char exe[MAX_PATH] = {};
            if (GetModuleFileNameA(nullptr, exe, MAX_PATH) == 0)
                return false;

            char* slash = strrchr(exe, '\\');
            if (!slash)
                return false;
            *slash = '\0';

            const int nd = snprintf(dirOut, dirSize, "%s\\T7Patch", exe);
            if (nd <= 0 || static_cast<size_t>(nd) >= dirSize)
                return false;

            const int nf = snprintf(fileOut, fileSize, "%s\\t7patch.log", dirOut);
            return nf > 0 && static_cast<size_t>(nf) < fileSize;
        }
    }

    void SetEnabled(bool enabled)
    {
        g_enabled.store(enabled);
    }

    void Append(const char* tag, const char* message)
    {
        if (!g_enabled.load())
            return; // the default: a normal player carries no runtime log

        char dir[MAX_PATH * 2] = {};
        char path[MAX_PATH * 2] = {};
        if (!BuildPaths(dir, sizeof(dir), path, sizeof(path)))
            return;

        // The patch's own init creates the folder, but the proxy logs before
        // that can happen, so make sure it exists here as well.
        CreateDirectoryA(dir, nullptr);

        // Rotate first: keep exactly one generation of history.
        WIN32_FILE_ATTRIBUTE_DATA attr = {};
        if (GetFileAttributesExA(path, GetFileExInfoStandard, &attr))
        {
            const long long size =
                (static_cast<long long>(attr.nFileSizeHigh) << 32) | attr.nFileSizeLow;
            if (size > kMaxBytes)
            {
                char oldPath[MAX_PATH * 2] = {};
                snprintf(oldPath, sizeof(oldPath), "%s.old", path);
                MoveFileExA(path, oldPath, MOVEFILE_REPLACE_EXISTING);
            }
        }

        FILE* f = nullptr;
        if (fopen_s(&f, path, "a") != 0 || !f)
            return;

        SYSTEMTIME st{};
        GetLocalTime(&st);
        fprintf(f, "[%02u:%02u:%02u.%03u] [%s] %s\n",
            st.wHour, st.wMinute, st.wSecond, st.wMilliseconds,
            tag ? tag : "?", message ? message : "");
        fclose(f);
    }
}
