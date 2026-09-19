// t7patch_log.h - the patch's single runtime log
//
// One file for everything that is not a crash dump: <game>\T7Patch\t7patch.log,
// every line tagged with its source ("proxy", "block", "overlay").  The patch
// used to keep three separate logs - t7patch_proxy.log, t7patch_block.log and
// t7patch_overlay.log - whose combined bookkeeping was larger than the
// information in them, and the overlay log had no size cap at all.
//
// Kept separate on purpose:
//   t7patch.conf  - read by the patch, written by the user
//   crashes.log   - written by the exception handler; it must stay a
//                   self-contained dump that survives whatever the crash broke
#pragma once

namespace t7log
{
    // Rotate to t7patch.log.old (one generation kept) past this size, so the
    // log can never grow without bound.  5 MB is the budget for the single
    // merged log - each of the three logs it replaced was capped at 24 KB, but
    // with one file there is no reason to be that stingy: a full session
    // writes a few dozen lines, so the cap only matters for a long-running
    // problem that keeps logging.
    constexpr long long kMaxBytes = 5 * 1024 * 1024;

    // [LOCAL] 2026-09-20: the runtime log is OFF unless the player asks for it
    // (the "log" key in t7patch.conf, default 0).  A normal player never reads
    // t7patch.log, and the debug trail is large enough to matter on a long
    // session.  The switch is PUSHED in from the config layer rather than read
    // by Append(): the config layer logs too, so a getter call here would take
    // its mutex a second time on the same thread and deadlock.
    void SetEnabled(bool enabled);

    // Appends "[HH:MM:SS.mmm] [tag] message" to T7Patch\t7patch.log.
    // Best effort by design: it never throws, never blocks the game and does
    // nothing at all if the file cannot be opened - or if the log is switched
    // off, which is the default.
    void Append(const char* tag, const char* message);
}
