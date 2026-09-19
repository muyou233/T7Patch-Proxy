# -*- coding: utf-8 -*-
"""Remove the 2026-09-16 caller-site probe from the source tree.

Verdict (see tools/probe_verdict.md): the route is dead - the three
front-end channels all carry mixed traffic, and 53 measured player names hit
the dictionary 0 times, so filtering by call site has zero upside.  The probe
is therefore removed rather than left switched off.

Deletion is done by verified 1-based line range, back to front, so the ranges
stay valid as lines disappear.  Every range is asserted against the first and
last line of the block before anything is written; a mismatch aborts the whole
run with no file touched.
"""
import os
import shutil
import sys

SRC = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\src"
BACKUP = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\pre_probe_removal"

# path -> list of (first_line, last_line, first_needle, last_expect)
# last_expect is compared against the line with its trailing CR/LF stripped;
# b"" means "the line must be blank".
RANGES = {
    os.path.join(SRC, "Hooks.cpp"): [
        (168, 263, b"[LOCAL] Caller-site probe (2026-09-16, diagnostic only).", b""),
    ],
    os.path.join(SRC, "translate.cpp"): [
        (1085, 1146, b"void CollectCaller(unsigned callerRva", b"    }"),
        (1080, 1084, b"bool Collecting()", b""),
        (776, 813, b"// One line per (call site, text) pair.", b"        }"),
        (72, 95, b"[LOCAL] Caller-site probe (see CollectCaller", b""),
    ],
    os.path.join(SRC, "translate.h"): [
        (67, 89, b"// Collection mode, second file:", b"                       const char* text);"),
        (62, 65, b"// True while the collection mode is on.", b"    bool Collecting();"),
    ],
}

lines_out = []


def main():
    os.makedirs(BACKUP, exist_ok=True)

    # ---- pass 1: read + assert everything, touch nothing -------------------
    loaded = {}
    for path, ranges in RANGES.items():
        raw = open(path, "rb").read()
        if raw.startswith(b"\xef\xbb\xbf"):
            sys.exit("ABORT: %s starts with a BOM, refusing to rewrite" % path)
        lines = raw.splitlines(True)
        for first, last, needle, expect in ranges:
            if first < 1 or last > len(lines) or first > last:
                sys.exit("ABORT: bad range %d-%d in %s (%d lines)"
                         % (first, last, path, len(lines)))
            head = lines[first - 1]
            tail = lines[last - 1]
            if needle not in head:
                sys.exit("ABORT: %s line %d is not the expected block start\n  want: %r\n  got : %r"
                         % (path, first, needle, head[:120]))
            if tail.rstrip(b"\r\n") != expect:
                sys.exit("ABORT: %s line %d is not the expected block end\n  want: %r\n  got : %r"
                         % (path, last, expect, tail[:120]))
        loaded[path] = lines
        lines_out.append("%-14s %5d lines -> asserted %d range(s), deleting %d line(s)"
                         % (os.path.basename(path), len(lines), len(ranges),
                            sum(l - f + 1 for f, l, _, _ in ranges)))

    # ---- pass 2: back up, then delete back to front ------------------------
    for path, ranges in RANGES.items():
        shutil.copyfile(path, os.path.join(BACKUP, os.path.basename(path)))
        lines = loaded[path]
        for first, last, _, _ in sorted(ranges, key=lambda r: -r[0]):
            del lines[first - 1:last]
        with open(path, "wb") as fh:
            fh.write(b"".join(lines))
        lines_out.append("%-14s %5d lines after removal" % (os.path.basename(path), len(lines)))

    # ---- pass 3: the symbols must be gone ---------------------------------
    leftovers = []
    for name in ("CallerRva", "ProbeElementString", "RecordCallerSite",
                 "CollectCaller", "Collecting", "ui_callers", "g_caller",
                 "CallerSite", "AppendCallerLocked", "kCaller"):
        for path in RANGES:
            for num, line in enumerate(open(path, "rb").read().splitlines(), 1):
                if name.encode() in line:
                    leftovers.append("%s:%d still mentions %s" % (os.path.basename(path), num, name))
    if leftovers:
        lines_out.append("!! LEFTOVERS:")
        lines_out.extend("   " + x for x in leftovers)
    else:
        lines_out.append("OK: no probe symbol left in the three edited files")

    lines_out.append("backup dir: " + BACKUP)
    return 0 if not leftovers else 1


sys.exit(main())
