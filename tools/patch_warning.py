# -*- coding: utf-8 -*-
r"""Simplify the start-up warning to a single message template.

Why this pass exists:
  * the owner asked for the safest / simplest shape ("不兼容直接自己不启动也行,
    怎么保险怎么简单来"); two hand-written bilingual templates is neither;
  * the specifics belong to the caller - proxy/Proxy.cpp knows the fingerprint,
    RunPatching() knows the Arxan reason - so the dialog needs one shape only.

Both files are LF; read and written with newline='' so nothing is translated.
Region replace is [start, end) with both markers asserted present, and `end`
is put back, so a bad marker can never silently eat code.
"""
import io

ROOT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\src"


def patch(path, start, end, replacement, sanity):
    text = io.open(path, 'r', encoding='utf-8', newline='').read()

    assert text.count(start) == 1, "start marker not unique: %r" % start[:70]
    assert sanity in text, "sanity text missing from the original"

    begin = text.index(start)
    stop = text.find(end, begin)
    assert stop != -1, "end marker not found after start"
    assert stop < len(text), "end marker at EOF"

    out = text[:begin] + replacement + text[stop:]
    assert out != text, "replacement was a no-op"
    assert out.count(end) >= 1, "end marker lost"

    io.open(path, 'w', encoding='utf-8', newline='').write(out)
    print("patched %s (%d -> %d bytes)" % (path, len(text), len(out)))


# --- 1. dllmain.cpp: one template instead of two --------------------------
DLLMAIN_NEW = """    // One template for every failure: the caller owns the specifics, so this
    // does not grow a branch per reason.
    swprintf_s(g_startupWarning,
        L"T7 Patch 未能启动 —— 游戏本体没有被修改，游戏会照常运行。\\n"
        L"\\n"
        L"原因：%ls\\n"
        L"\\n"
        L"如果游戏刚更新过，请先让 Steam 校验一次游戏文件：\\n"
        L"「库」→ 右键 Call of Duty: Black Ops III → 属性 → 已安装文件 → "
        L"验证游戏文件的完整性。\\n"
        L"若校验之后仍然如此，说明补丁还没跟上这次游戏更新，等新版本即可。\\n"
        L"\\n"
        L"补丁版本 %hs；详细记录：T7Patch\\\\t7patch.log\\n"
        L"\\n"
        L"------------------------------------------------------------\\n"
        L"T7 Patch could not start - the game itself was left untouched and "
        L"runs as usual.\\n"
        L"\\n"
        L"Reason: %ls\\n"
        L"\\n"
        L"If the game has just been updated, have Steam verify the game files "
        L"first: Library > right-click Call of Duty: Black Ops III > Properties "
        L"> Installed Files > Verify integrity of game files.\\n"
        L"If it still happens after that, the patch has not caught up with this "
        L"update yet - a newer release will fix it.\\n"
        L"\\n"
        L"Patch %hs; details: T7Patch\\\\t7patch.log",
        wideReason, ZBR_VERSION, wideReason, ZBR_VERSION);

"""

patch(ROOT + r"\dllmain.cpp",
      "    const auto fingerprint = bo3::read_fingerprint();",
      "    // The thread reads the static buffer above;",
      DLLMAIN_NEW,
      "诊断信息")

# --- 2. proxy/Proxy.cpp: share one reason string with the log -------------
PROXY_NEW = """            // [LOCAL] Name the two numbers the check above compared, in the log
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
"""

patch(ROOT + r"\proxy\Proxy.cpp",
      "            // [LOCAL] Carry the two numbers the check above compared into the",
      "            return 0;",
      PROXY_NEW,
      "proxy: unsupported executable (timestamp")

print("all patches applied")
