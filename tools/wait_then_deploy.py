# -*- coding: utf-8 -*-
# Wait until the installed d3d11.dll stops being held open, then deploy the
# freshly built one.  Rationale: a loaded image cannot be replaced, and the
# sandbox refuses to delete, so "game still running" is the only thing that
# blocks a deploy.  Waiting for the write handle to become available is the
# definitive test - the loader keeps the image open without FILE_SHARE_WRITE for
# the whole lifetime of the process, so a successful open means the game is gone.
#
#   python wait_then_deploy.py [--minutes 20]
import os
import subprocess
import sys
import time

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DST = os.path.join(GAME, "d3d11.dll")
REF = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools"
DEPLOY = os.path.join(REF, "deploy_t7patch.py")
OUT = os.path.join(REF, "wait_deploy.txt")

argv = sys.argv[1:]
MINUTES = float(argv[argv.index("--minutes") + 1]) if "--minutes" in argv else 20.0

_log = []


def say(msg):
    _log.append("[%s] %s" % (time.strftime("%H:%M:%S"), msg))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(_log) + "\n")


def locked():
    if not os.path.exists(DST):
        return False
    try:
        with open(DST, "r+b"):
            pass
        return False
    except OSError:
        return True


deadline = time.time() + MINUTES * 60
say("waiting for the game to release %s (up to %.0f min)" % (DST, MINUTES))
if not locked():
    say("not locked right now - deploying immediately")

while locked():
    if time.time() > deadline:
        say("TIMEOUT: still locked. Run deploy_t7patch.py once the game is closed.")
        raise SystemExit(2)
    time.sleep(5)

say("d3d11.dll is free - deploying")
r = subprocess.run([sys.executable, DEPLOY], capture_output=True, text=True)
say((r.stdout or "").strip())
if r.stderr:
    say("STDERR: " + r.stderr.strip()[-500:])
say("deploy rc=%d" % r.returncode)
raise SystemExit(r.returncode)
