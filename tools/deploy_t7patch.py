# -*- coding: utf-8 -*-
# Deploy the freshly built drop-in proxy d3d11.dll into the Black Ops III folder.
#
# Overwrite-only on purpose: this machine's sandbox intercepts and refuses
# deletes outside the workspace (the "safe-delete" guard), so this script never
# removes anything.  The previous d3d11.dll is preserved as d3d11.dll.bak, which
# is the rollback point.  (The pristine, unpatched state is simply "no
# d3d11.dll at all" - Windows then resolves the real one from System32.)
#
# Re-running is safe and idempotent: if the installed DLL already matches the
# build output byte for byte, the script reports that and stops WITHOUT
# touching d3d11.dll.bak, so an existing rollback point can never be clobbered
# by a no-op deploy.
import hashlib
import os
import shutil
import time

SRC = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\x64\Release\d3d11.dll"
GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DST = os.path.join(GAME, "d3d11.dll")
BAK = os.path.join(GAME, "d3d11.dll.bak")
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\deploy_t7.txt"

# Literal embedded in overlay.cpp as kRepoUrl.  Used as a freshness probe: if a
# DLL claiming to be the current build does not contain it, we are looking at a
# stale artifact and must not overwrite a working install with it.
URL = b"https://github.com/muyou233/T7Patch-Proxy"

LOG = []


def say(msg):
    LOG.append(msg)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def stamp(path):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(path)))


def run():
    if not os.path.exists(SRC):
        say("FAIL: build output missing: %s" % SRC)
        return 1
    if not os.path.isdir(GAME):
        say("FAIL: game folder missing: %s" % GAME)
        return 1

    src_hash = sha(SRC)
    say("build output : %s" % SRC)
    say("  size=%d mtime=%s" % (os.path.getsize(SRC), stamp(SRC)))
    say("  sha256=%s" % src_hash)

    # Sources live under src/ since the 2026-09-15 reorganisation; keep the old
    # root-relative location as a fallback so the probe never silently vanishes.
    root = os.path.normpath(os.path.join(os.path.dirname(SRC), "..", ".."))
    overlay = next((p for p in (os.path.join(root, "src", "overlay.cpp"),
                                os.path.join(root, "overlay.cpp"))
                    if os.path.exists(p)), None)
    if overlay is None:
        say("WARN: overlay.cpp not found under %s - freshness probe skipped" % root)
    if overlay is not None:
        fresh = os.path.getmtime(SRC) >= os.path.getmtime(overlay)
        say("  newer than overlay.cpp (%s): %s" % (stamp(overlay), fresh))
        if not fresh:
            say("WARN: build output is older than overlay.cpp - rebuild before trusting this deploy")

    dst_exists = os.path.exists(DST)
    dst_hash = sha(DST) if dst_exists else None

    # ------------------------------------------------------------ game running
    # A loaded DLL cannot be replaced.  Windows would let the .old rename succeed
    # and then fail the copy, leaving the game folder with no d3d11.dll at all -
    # which is exactly what this check is here to prevent.  Opening the file for
    # writing is the cheapest reliable test: the loader holds the image without
    # FILE_SHARE_WRITE, so this raises while the game runs.
    if dst_exists:
        try:
            with open(DST, "r+b"):
                pass
        except OSError:
            say("FAIL: %s is open by another process (the game is running)." % DST)
            say("      Close the game and run this again.  Deploying over a loaded")
            say("      DLL cannot work, and a half-done copy would break the game.")
            return 1

    # ------------------------------------------------------------ idempotent
    if dst_exists and dst_hash == src_hash:
        say("installed    : %s" % DST)
        say("  size=%d mtime=%s" % (os.path.getsize(DST), stamp(DST)))
        say("  sha256=%s" % dst_hash)
        say("ALREADY UP TO DATE - nothing copied, backup left untouched at %s" % BAK)
        say("RESULT: OK (no-op)")
        return 0

    # ------------------------------------------------------------ freshness
    with open(SRC, "rb") as f:
        blob = f.read()
    has_url = URL in blob
    say("  contains kRepoUrl literal: %s" % has_url)
    if not has_url:
        say("FAIL: kRepoUrl not found in the built DLL - refusing to deploy a stale binary")
        return 1

    # ------------------------------------------------------------ backup
    if dst_exists:
        say("installed    : %s" % DST)
        say("  size=%d mtime=%s" % (os.path.getsize(DST), stamp(DST)))
        say("  sha256=%s" % dst_hash)
        # Plain byte copy, not a move: DST stays intact until the new bytes land.
        with open(DST, "rb") as fi, open(BAK, "wb") as fo:
            shutil.copyfileobj(fi, fo)
        say("  rollback point -> %s (%d bytes)" % (BAK, os.path.getsize(BAK)))
    else:
        say("installed    : (absent) - first install, no rollback point needed")

    # ------------------------------------------------------------ deploy
    with open(SRC, "rb") as fi, open(DST, "wb") as fo:
        shutil.copyfileobj(fi, fo, 1 << 20)

    final = sha(DST)
    say("deployed     : %s" % DST)
    say("  size=%d mtime=%s" % (os.path.getsize(DST), stamp(DST)))
    say("  sha256=%s" % final)
    say("  matches build output: %s" % (final == src_hash))
    say("  replaced: %s" % (dst_hash or "(nothing)"))

    ok = (final == src_hash)
    say("RESULT: %s" % ("OK" if ok else "MISMATCH"))
    return 0 if ok else 1


if __name__ == "__main__":
    rc = 1
    try:
        rc = run()
    except Exception as exc:  # noqa: BLE001 - report everything, this is a deploy tool
        say("EXCEPTION: %r" % (exc,))
        rc = 1
    text = "\n".join(LOG) + "\n"
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    raise SystemExit(rc)
