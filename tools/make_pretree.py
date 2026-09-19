# -*- coding: utf-8 -*-
# Build a byte-exact copy of the PRE-refactor layout, so a directory reorg can be
# A/B verified: the only difference between the two builds is then where the
# files live + the paths written in the .vcxproj.
#
#   python make_pretree.py
#
# Sources are copied from the repo's current src/ (byte-for-byte, so line endings
# are preserved exactly); the project/filters/solution files are pulled out of
# HEAD, where the pre-refactor layout still exists.
import os, shutil, subprocess

REPO = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private"
DST = os.path.join(os.environ["TEMP"], "t7_pretree")
HEAD_FILES = ["T7Patch.vcxproj", "T7Patch.vcxproj.filters", "T7Patch.slnx",
              "T7Patch.vcxproj.user"]
THIRD_PARTY = ["imgui", "minhook", "detours", "docs"]

if os.path.exists(DST):
    shutil.rmtree(DST)
os.makedirs(DST)
os.makedirs(os.path.join(DST, "proxy"))

for d in THIRD_PARTY:
    shutil.copytree(os.path.join(REPO, d), os.path.join(DST, d))

root_src = os.path.join(REPO, "src")
n = 0
for name in os.listdir(root_src):
    p = os.path.join(root_src, name)
    if os.path.isfile(p) and name.lower().endswith((".cpp", ".h")):
        shutil.copy2(p, os.path.join(DST, name))
        n += 1
for name in os.listdir(os.path.join(root_src, "proxy")):
    shutil.copy2(os.path.join(root_src, "proxy", name),
                 os.path.join(DST, "proxy", name))

for name in HEAD_FILES:
    blob = subprocess.run(["git", "-C", REPO, "show", "HEAD:" + name],
                          capture_output=True).stdout
    assert blob, "git show failed for " + name
    with open(os.path.join(DST, name), "wb") as f:
        f.write(blob)

print("pre-refactor tree built at %s" % DST)
print("  source files at root : %d" % n)
print("  vcxproj from HEAD    : %s" % ", ".join(HEAD_FILES))
