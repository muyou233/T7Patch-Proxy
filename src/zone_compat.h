#pragma once

// [LOCAL] Custom-map language compatibility.
//
// Every workshop map is packed per language, and the engine builds the zone
// name from the language the GAME is running in: "<lang>_zm_<map>.ff".  Most
// authors only ever export the English set, so anyone playing in another
// language gets "ERROR: Could not find zone 'sc_zm_...'" on the console and the
// map refuses to load at all - it is not a font problem, the level never
// starts.
//
// This creates the missing names by COPYING the English set.  It deliberately
// never edits an existing file and never touches a map that already ships the
// language, so the worst case is a few megabytes of duplicate names next to
// the originals.  Steam replacing the folder (a map update) simply removes the
// copies; the next launch recreates them.
namespace zone_compat
{
    struct Status
    {
        char language[16] = {}; // the prefix the zone names are built with
        unsigned maps = 0;      // workshop folders examined
        unsigned added = 0;     // files created this session
        char message[160] = {}; // one line for the UI; empty while unknown
    };

    // Starts the scan on a worker thread; returns immediately.  The scan is
    // pure file I/O next to the game folder, so it runs once at start-up and
    // then never again this session.
    void Start();

    // Snapshot for the UI.  Cheap enough to call every frame.
    Status Get();
}
