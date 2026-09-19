# -*- coding: utf-8 -*-
# Build T7Patch Release x64 and report the d3d11.dll artifact.
#
#   python build_t7patch.py [--rebuild] [--proj <vcxproj>] [--log <file>]
#
# Defaults target this repo (E:\MyProject\T7Patch\T7Patch-Proxy-Private).  --proj lets the
# same script build a different checkout (e.g. a git worktree holding the
# pre-refactor layout), which is how a layout change is A/B verified.
import subprocess, os, sys

DEFAULT_PROJ = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\T7Patch.vcxproj"
DEFAULT_LOG = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\t7_build_log.txt"
MSBUILD = r"C:\Program Files\Microsoft Visual Studio\18\Community\MSBuild\Current\Bin\MSBuild.exe"

argv = sys.argv[1:]
def opt(name, default):
    return argv[argv.index(name) + 1] if name in argv else default

PROJ = opt("--proj", DEFAULT_PROJ)
OUT = opt("--log", DEFAULT_LOG)
PROJDIR = os.path.dirname(PROJ)

log = open(OUT, "w", encoding="utf-8", buffering=1)
env = dict(os.environ)
for k in [k for k in env if k.lower() in ("http_proxy", "https_proxy")]:
    del env[k]

log.write("building %s Release|x64 ...\n" % PROJ)
args = [MSBUILD, PROJ, "/m:1", "/v:minimal",
        "/p:Configuration=Release", "/p:Platform=x64"]
if "--rebuild" in argv:
    args.append("/t:Rebuild")
    log.write("(full rebuild requested)\n")
# [LOCAL] Name the encoding, and keep a lossy fallback.
#
# MSBuild writes UTF-8 to the pipe.  The old "text=True" with no encoding used
# the locale default (cp936 here), which cannot decode that, and it did not fail
# gracefully: the reader thread raised UnicodeDecodeError and r.stdout came back
# EMPTY, so the log lost every diagnostic including the warnings (measured
# 2026-09-17).
#
# The exact byte proves which codec is right: the banner's first line,
# "适用于 .NET Framework MSBuild ...", puts 0x8E at position 8 - the last byte
# of 于 - and that is the byte the error named.  0x8E is a valid UTF-8
# continuation byte but an impossible GBK sequence, so the stream is UTF-8.
#
# (An earlier fix here asked for the locale encoding plus errors="replace".  It
# stopped the crash but decoded "适用" as "閫傜敤" - mojibake, which is the
# signature of UTF-8 read as GBK.  Ask for UTF-8; keeping errors="replace" only
# guards against the toolchain ever changing its mind again.)
r = subprocess.run(args, cwd=PROJDIR, capture_output=True, timeout=3600, env=env,
                   encoding="utf-8", errors="replace")
log.write((r.stdout or "")[-6000:])
if r.stderr:
    log.write((r.stderr or "")[-2000:])
log.write("\n[rc=%d]\n" % r.returncode)

dll = os.path.join(PROJDIR, "x64", "Release", "d3d11.dll")
log.write("d3d11.dll: %s (size=%s, mtime=%s)\n" % (
    os.path.exists(dll),
    os.path.getsize(dll) if os.path.exists(dll) else 0,
    os.path.getmtime(dll) if os.path.exists(dll) else 0))
log.close()
print("t7 build done, rc=%d, dll=%s" % (r.returncode, dll))
