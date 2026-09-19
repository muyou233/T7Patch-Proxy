# -*- coding: utf-8 -*-
# Force-push the amended commit with an exact lease, capturing every byte of
# stdout/stderr plus the exit code - PowerShell layers have been eating both.
import subprocess

cmd = [
    "git", "push",
    "--force-with-lease=refs/heads/main:4b2caa3476f96c3cb483ea2240c7eb25656a6a7a",
    "origin", "main",
]
r = subprocess.run(cmd, capture_output=True, cwd=r"E:\MyProject\T7Patch\T7Patch-Proxy-Private")
lines = ["rc=%d" % r.returncode, "--- stdout ---", r.stdout.decode("utf-8", "replace"),
         "--- stderr ---", r.stderr.decode("utf-8", "replace")]
with open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\.codebuddy\push_py.txt", "wb") as f:
    f.write("\n".join(lines).encode("utf-8"))
print("done rc", r.returncode)
