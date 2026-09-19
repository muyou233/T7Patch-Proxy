# -*- coding: utf-8 -*-
# Verify the exact bytes of the last commit's subject line: PowerShell capture
# layers mangle non-ASCII, so read git's raw stdout bytes here.
import subprocess

out = subprocess.run(["git", "log", "-1", "--format=%s%n%H"],
                     capture_output=True, cwd=r"E:\MyProject\T7Patch\T7Patch-Proxy-Private")
with open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\.codebuddy\subj.txt", "wb") as f:
    f.write(out.stdout)
print("rc", out.returncode, "bytes", len(out.stdout))
