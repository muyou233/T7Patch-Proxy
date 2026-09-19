"""gen_github_mark.py - regenerate GithubMark.h from the source PNG.

Usage:
    python gen_github_mark.py [source.png] [output.h]

Defaults: source = E:\\Download\\github.png, output = <repo>\\GithubMark.h

Why this exists: the GitHub mark is embedded in the DLL as a 48x48 alpha mask
(see GithubMark.h for the reasoning).  This script is the only way to rebuild
that mask, so it lives next to the other one-off tooling in tools/.

Notes on the pipeline:
  * Pure Python - no Pillow / no WIC.  zlib + a hand-rolled PNG unfilter keeps
    the script dependency-free (the managed interpreter has no Pillow).
  * Only the ALPHA channel is kept.  The source art is a solid black circle with
    the octocat punched out as a transparent hole, so RGB carries no information
    the tint cannot supply, and black-on-near-black would be invisible anyway.
  * The crop is squared around the alpha bounding box before resampling, so the
    mark fills the mask exactly whatever margin the source PNG has.
  * Resampling is an area average (box filter), which is what gives the ring
    edges their antialiasing after the ~4x downscale from the 200x200 source.
"""

import struct
import sys
import zlib

SRC = r"E:\Download\github.png"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\GithubMark.h"
N = 48  # mask resolution (square); drawn at ~font line height, so this is ~2x headroom


def decode_png_rgba(path):
    """Return (width, height, alpha_bytes) for an 8-bit RGBA (colour type 6) PNG."""
    data = open(path, "rb").read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG: %s" % path)

    pos, idat = 8, b""
    w = h = None
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + ln]
        if typ == b"IHDR":
            w, h, bitdepth, colortype = struct.unpack(">IIBB", chunk[:10])
        elif typ == b"IDAT":
            idat += chunk
        elif typ == b"IEND":
            break
        pos += 12 + ln

    if bitdepth != 8 or colortype != 6:
        raise ValueError("expected 8-bit RGBA (colortype 6), got depth=%s type=%s"
                         % (bitdepth, colortype))

    raw = zlib.decompress(idat)
    bpp, stride = 4, w * 4
    alpha = bytearray(w * h)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        ft = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        # PNG per-scanline filters (see the PNG spec, section 9.2).
        if ft == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ft == 3:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 0xFF
        elif ft == 4:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b = prev[i]
                c = prev[i - bpp] if i >= bpp else 0
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        elif ft != 0:
            raise ValueError("unknown PNG filter type %d on row %d" % (ft, y))
        for x in range(w):
            alpha[y * w + x] = line[x * 4 + 3]
        prev = line
    return w, h, alpha


def alpha_bbox(w, h, alpha):
    x0, y0, x1, y1 = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            if alpha[y * w + x]:
                if x < x0: x0 = x
                if y < y0: y0 = y
                if x > x1: x1 = x
                if y > y1: y1 = y
    if x1 < 0:
        raise ValueError("the image is fully transparent")
    return x0, y0, x1, y1


def resample_square(w, h, alpha, x0, y0, cw, ch, n):
    """Area-average the alpha into an n*n grid, squared around (cw, ch)."""
    side = max(cw, ch)
    sx = x0 - (side - cw) // 2
    sy = y0 - (side - ch) // 2
    scale = side / n
    out = [0] * (n * n)
    for oy in range(n):
        sy0, sy1 = sy + oy * scale, sy + (oy + 1) * scale
        for ox in range(n):
            sx0, sx1 = sx + ox * scale, sx + (ox + 1) * scale
            total, covered = 0.0, 0.0
            for yy in range(int(sy0), int(sy1) + 1):
                if yy < 0 or yy >= h:
                    continue
                wy = min(sy1, yy + 1) - max(sy0, yy)
                if wy <= 0:
                    continue
                for xx in range(int(sx0), int(sx1) + 1):
                    if xx < 0 or xx >= w:
                        continue
                    wx = min(sx1, xx + 1) - max(sx0, xx)
                    if wx <= 0:
                        continue
                    total += alpha[yy * w + xx] * wx * wy
                    covered += wx * wy
            out[oy * n + ox] = int(total / covered + 0.5) if covered else 0
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else SRC
    out = sys.argv[2] if len(sys.argv) > 2 else OUT

    w, h, alpha = decode_png_rgba(src)
    x0, y0, x1, y1 = alpha_bbox(w, h, alpha)
    print("source %dx%d, alpha bbox (%d,%d)-(%d,%d)" % (w, h, x0, y0, x1, y1))

    vals = resample_square(w, h, alpha, x0, y0, x1 - x0 + 1, y1 - y0 + 1, N)
    opaque = sum(1 for v in vals if v > 128)
    print("mask %dx%d: %d/%d opaque (%.1f%%), %d partial (antialiased)"
          % (N, N, opaque, N * N, 100.0 * opaque / (N * N),
             sum(1 for v in vals if 0 < v <= 128)))

    hexstr = "".join("%02x" % v for v in vals)
    chunks = [hexstr[i:i + 96] for i in range(0, len(hexstr), 96)]

    body = [
        "// GithubMark.h - alpha mask of the GitHub mark, embedded in the binary.",
        "//",
        "// [LOCAL] Why embedded instead of a loose PNG next to the DLL: this patch",
        "// ships as a single d3d11.dll drop, so an external asset would add a file the",
        "// user can lose and a runtime image-decoding path (WIC/COM) that can fail.",
        "// %dx%d 8-bit alpha, row-major from the top-left, 2 hex digits per pixel." % (N, N),
        "//",
        "// The source art is a BLACK circle with the octocat punched out as a hole, and",
        "// every opaque pixel is pure black - drawing it as-is would be invisible on this",
        "// near-black panel.  Only alpha is kept: the texture is built white and tinted at",
        "// draw time, so the mark can be recoloured (rest/hover) without touching the art.",
        "//",
        "// Regenerate with tools/gen_github_mark.py (change the art there, not here).",
        "#pragma once",
        "",
        "constexpr int kGithubMarkSize = %d;" % N,
        "",
        "// 2 hex digits per pixel, %d pixels, row-major, top-left origin." % (N * N),
        "inline constexpr char kGithubMarkAlphaHex[] =",
    ]
    body += ['    "%s"' % c for c in chunks]
    body.append("    ;")

    with open(out, "w", newline="\n", encoding="utf-8") as f:
        f.write("\n".join(body) + "\n")
    print("wrote %s (%d hex chars)" % (out, len(hexstr)))


if __name__ == "__main__":
    main()
