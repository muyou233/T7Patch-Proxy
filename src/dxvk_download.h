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
}
