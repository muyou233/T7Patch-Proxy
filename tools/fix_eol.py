# -*- coding: utf-8 -*-
r"""Restore the original line-ending style of files the editor touched.

The Edit tool inserts LF.  Two of the files it touched are CRLF files, so a
mixed-ending file would show up as a whole-file diff on the next commit.
Nothing else is changed: no BOM is added, no content is rewritten.
"""
import io, os

REPO = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private"
CRLF_FILES = [r"src\GameBuild.h", r"src\framework.h"]


def counts(data):
    crlf = data.count(b"\r\n")
    lf = data.count(b"\n") - crlf
    return crlf, lf


for rel in CRLF_FILES:
    path = os.path.join(REPO, rel)
    data = io.open(path, "rb").read()
    assert not data.startswith(b"\xef\xbb\xbf"), "unexpected BOM in " + rel

    before = counts(data)
    normalised = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    io.open(path, "wb").write(normalised)
    after = counts(io.open(path, "rb").read())
    print("%-22s CRLF/LF-only %s -> %s" % (rel, before, after))
    assert after[1] == 0, "still mixed: " + rel

print("ok")
