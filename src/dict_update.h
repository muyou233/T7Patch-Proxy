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
// currently in force.  That is also why the URL is hard-coded - a user-editable
// download URL would hand "what the UI says" to whoever set it.
namespace dict_update
{
    enum class State
    {
        Idle,    // nothing attempted yet this session
        Running, // a download is in flight
        Ok,      // last attempt succeeded (Status::entries says how many arrived)
        Failed   // last attempt failed (Status::message says why)
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
