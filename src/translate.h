#pragma once

// [LOCAL] UI string translation layer.
//
// The game renders every front-end string through two functions we already
// hook (UI_DoModelStringReplacement and SEH_ReplaceDirectiveInStringWithBinding).
// Hooking that pipeline means the translation covers the base game AND every
// mod's UI text - mods display their text through the game's own UI framework,
// so no per-mod adaptation is ever needed.
//
// Matching happens per *run*: the front-end wraps every UI string in control
// bytes (0x15 ... 0x14) and composes longer text out of those wrapped
// fragments, so the text between the markers is what gets looked up.  Markers
// and padding are copied through unchanged, and a run that misses keeps its
// original text, so unrelated UI text is never corrupted.
//
// A dictionary key may contain '*' to match a varying tail ("level *" covers
// every level the game prints); the value then uses '*' as the placeholder for
// the captured text, in order.
//
// The dictionary is a plain text file next to t7patch.conf:
//     English source=中文译文
// so it can be edited and extended without touching the dll - the running game
// picks up a saved file within a couple of seconds (see Lookup).
//
// Two switches live in t7patch.conf:
//     translate=1        enable the replacement (default 0)
//     dump_ui_strings=1  collection mode: record every distinct English UI
//                        string into T7Patch\ui_dump.txt (for building the
//                        dictionary; default 0).  A run that already contains
//                        CJK text is skipped, so the game's own Chinese is
//                        never recorded - and English strings carrying
//                        typographic quotes or accents are kept.
namespace translate
{
    // Reads both switches from the config and loads the dictionary file.
    // Safe to call once at startup, from the worker thread.
    void Init();

    // Re-reads the dictionary on the very next lookup, skipping the write-time
    // poll (which can be up to kPollIntervalMs behind).  The updater calls this
    // right after it replaces the file, so "the player clicked update" switches
    // to the new file immediately AND without depending on the timestamp having
    // changed - the poll remains the safety net for hand edits, not the
    // mechanism the button relies on.
    void RequestReload();

    // True when the translate=1 switch is on (dictionary loaded and non-empty).
    bool Enabled();

    // Run-wise lookup.  On a hit, copies the translated string into 'out'
    // (bounded) and returns true; returns false when nothing matched or the
    // result would not fit, in which case the caller keeps the original text.
    // Also re-reads the dictionary file when it changed on disk.
    bool Lookup(const char* source, char* out, size_t outSize);

    // Collection mode: records a distinct UI string for the dictionary build.
    // Records the same runs Lookup can match.  No-op unless dump_ui_strings=1.
    // Deduplicated and capped, lock-protected.
    void Collect(const char* text);

    // Absolute path of the on-disk dictionary - the external file that wins over
    // the copy built into the dll.  Exposed so the updater writes to exactly the
    // file the lookup path reads.
    bool DictionaryPath(char* out, size_t outSize);

    // How many exact entries are in force right now.  The updater uses it to
    // refuse a download that would shrink the dictionary by a lot; nothing else
    // reads it.
    unsigned EntryCount();
}
