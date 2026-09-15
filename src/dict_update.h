#pragma once

// [LOCAL] On-demand dictionary update.
//
// Deliberately NOT automatic: this patch never touches the network unless the
// player clicks the button in the overlay.  One click = one HTTPS GET of the
// published dictionary -> validate -> atomically replace
// <game>\T7Patch\translate_zh.txt.  The running game then picks the new file up
// through the usual write-time poll (about two seconds, no restart).
//
// What the download can and cannot do: the payload becomes UI text and nothing
// else.  It is never executed, never parsed as anything but "key=value" lines,
// and a file that fails validation is discarded without touching the dictionary
// currently in force.  That is also why the source URLs are hard-coded - a
// user-editable download URL would hand "what the UI says" to whoever set it.
// Three mirrors are tried in order: the jsDelivr CDN in front of the GitHub
// repo (best plain reachability from mainland China; its edge cache trails a
// fresh push by hours, purge on demand), then GitHub raw itself (always
// current), then Gitee (whose raw endpoint refuses anonymous downloads with
// HTTP 451, so the last fallback goes through Gitee's public contents API
// instead - same bytes, wrapped in JSON with a base64 payload, unwrapped
// after the download).  All anonymous; all the user's own published content.
namespace dict_update
{
    enum class State
    {
        Idle,     // nothing attempted yet this session
        Running,  // a download is in flight
        Ok,       // last attempt succeeded (Status::entries says how many arrived)
        Failed,   // last attempt failed (Status::message says why)
        UpToDate  // click landed inside the post-success cooldown; nothing ran
    };

    struct Status
    {
        State state = State::Idle;
        unsigned entries = 0;   // meaningful when state == Ok
        char message[192] = {}; // one line for the UI; empty while Idle
    };

    // Starts a download unless one is already running.  Returns immediately -
    // the work happens on a detached worker thread, because the caller is the
    // ImGui frame and must not block on a socket.
    void Start();

    // Snapshot for the UI.  Cheap enough to call every frame.
    Status Get();
}
