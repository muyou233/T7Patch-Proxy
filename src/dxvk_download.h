#pragma once

// [LOCAL] On-demand DXVK download (the optional Vulkan backend).
//
// Deliberately NOT automatic, exactly like the dictionary update: this patch
// never touches the network unless the player clicks the button in the
// overlay.  One click fetches the two files that arm the chained D3D11
// backend (see proxy/Proxy.cpp) - d3d11_backend.dll and dxgi.dll - into
// <game>\T7Patch\dxvk\.  Nothing there is ever loaded until the player also
// moves the pair into the game folder, so downloading is a harmless no-op
// for anyone who only wants the protection features.
//
// Integrity: every file carries a hard-coded SHA-256 that the blob must
// match byte-for-byte before it is allowed to land.  A truncated download,
// an error page or a tampered mirror therefore cannot reach the disk as a
// usable DLL - and since the hash also pins the exact upstream build, a
// DXVK update is a deliberate change to this file, not something that
// silently drifts.  The hash is the only validator that matters for
// binary payloads; the heuristics the dictionary can afford (entry counts,
// shrink ratios) make no sense here.
//
// Sources: two mirrors of the same published files, tried in order - the
// jsDelivr CDN in front of the GitHub repo first (best plain reachability
// from mainland China; its edge cache trails a fresh push by hours, purge
// on demand), then GitHub raw itself (always current).  Deliberately no
// Gitee: its anonymous-only endpoint is the contents API, whose base64
// JSON wrapper would inflate a 7.5 MB DLL into a ~17 MB parse inside the
// game process - the wrong shape for a payload this size.
//
// Concurrency: one CAS-guarded worker (a second click while a download is
// in flight does nothing), and a 60 s cooldown that only a fully successful
// run starts - a failed or refused attempt must always allow an immediate
// retry.
namespace dxvk_download
{
    enum class State
    {
        Idle,     // nothing attempted yet this session
        Running,  // a download is in flight
        Ok,       // last attempt succeeded - both files verified in place
        Failed,   // last attempt failed (Status::message says why)
        UpToDate  // click landed inside the post-success cooldown; nothing ran
    };

    struct Status
    {
        State state = State::Idle;
        unsigned long long downloadedKiB = 0; // bytes received for the file
                                              // currently being fetched,
                                              // rounded to KiB
        char message[192] = {};               // one line for the UI; empty
                                              // while Idle
    };

    // Starts a download unless one is already running.  Returns immediately -
    // the work happens on a detached worker thread, because the caller is the
    // ImGui frame and must not block on a socket.
    void Start();

    // Snapshot for the UI.  Cheap enough to call every frame.
    Status Get();

    // ---- enabling the backend --------------------------------------------
    //
    // The toggle the player flips is the pair's LOCATION, not a config value:
    // both files parked in T7Patch\dxvk means "downloaded, off", both in the
    // game folder means "on at next launch".  (The game imports d3d11/dxgi
    // statically, so nothing can switch at runtime and the files must move
    // together - see proxy/Proxy.cpp for the gate that enforces the same
    // rule from the loading side.)
    enum class InstallState
    {
        Absent,   // no complete pair anywhere - the toggle is disabled
        Parked,   // both in T7Patch\dxvk - downloaded, not enabled
        Enabled,  // both in the game folder - active from the next launch
        Mixed     // split across the two - must not happen; re-download
    };

    // Presence-only check: two GetFileAttributesW calls, no hashing.  The UI
    // polls this every frame, which is exactly why integrity is enforced at
    // download time (a file that arrived is a file that verified) and never
    // re-checked here.
    InstallState Query();

    // Move the pair park->game (Enable) or game->park (Disable).  Same-volume
    // renames, so both return in milliseconds and are safe to call inside the
    // ImGui frame.  false means a file was missing, locked, or the target
    // already existed - Query() keeps reporting the old state, and the log
    // says which move failed.
    bool Enable();
    bool Disable();

    // ---- dxvk.conf settings (the DXVK page) -------------------------------
    //
    // The overlay exposes exactly three knobs, persisted by rewriting
    // T7Patch\dxvk\dxvk.conf - the file the proxy points DXVK at via
    // DXVK_CONFIG_FILE.  DXVK reads it once when the device is created, so
    // changes land on the next launch, same as the enable toggle.
    //
    // Deliberately a WRITE-ONLY template, not a parser-plus-merger: the file
    // is ours (the download feature never fetches a conf), so regenerating
    // the whole file from the UI state cannot lose edits we do not know
    // about.  Everything the page does not expose stays at the documented
    // default, stated in the generated comments - the three most tempting
    // bad ideas (tearFree off Auto, pipeline library off, async) are exactly
    // the ones this interface keeps boring.
    struct Conf
    {
        unsigned hud = 0;    // dxvk.hud as a bitmask of HudElement.  0 writes no
                             // dxvk.hud line at all, i.e. the HUD stays off -
                             // the ticks ARE the switch, there is no second
                             // master checkbox to keep in sync with them.
        int maxFps = 0;      // dxgi.maxFrameRate - 0 = uncapped
        int tearFree = 0;    // dxvk.tearFree - 0 Auto / 1 True / 2 False
    };

    // dxvk.hud takes a comma-separated list of elements; DXVK 3.1.1's README
    // is the authority on the names.  The page exposes the six a player can
    // act on - the rest (submissions, pipelines, descriptors, allocations, cs,
    // samplers, swvp) are engine counters that mean nothing in a game overlay.
    // Note it is a plain bitmask: the conf layer writes the names, the overlay
    // only sets and clears bits.
    enum HudElement
    {
        HUD_FPS        = 1u << 0,   // fps - the frame rate
        HUD_FRAMETIMES = 1u << 1,   // frametimes - the frame time graph
        HUD_GPULOAD    = 1u << 2,   // gpuload - approximate, DXVK says so too
        HUD_MEMORY     = 1u << 3,   // memory - device memory allocated / used
        HUD_COMPILER   = 1u << 4,   // compiler - shader compile activity
        HUD_DEVINFO    = 1u << 5,   // devinfo - GPU name + driver version
    };

    // Cached read of the conf (documented defaults when absent).  The file is
    // read at most once per process; afterwards the overlay's own cache is
    // the truth, so the frame loop never touches the disk.
    Conf ConfGet();

    // Updates the cache and atomically rewrites the conf (tmp + rename, and
    // the store directory is created on demand).  Call only when a value
    // actually changed.
    void ConfSet(const Conf& c);
}
