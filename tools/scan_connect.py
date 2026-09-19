# Scan BlackOps3.exe for connect/matchmaking related cbuf command strings.
# Read-only reconnaissance: we only look for NUL-terminated command-like strings.
import re

EXE = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\BlackOps3.exe"
OUT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\connect_scan.txt"

with open(EXE, "rb") as fh:
    data = fh.read()

patterns = {
    "connect(exact)": rb"\x00connect\x00",
    "Connect(exact)": rb"\x00Connect\x00",
    "connect DWORD/ip hint": rb"connect\x00",
    "disconnect": rb"\x00disconnect\x00",
    "matchmaking": rb"matchmaking",
    "joinserver": rb"joinserver",
    "joinServer": rb"joinServer",
    "serverbrowser": rb"serverbrowser",
    "server_browser": rb"server_browser",
    "xbl": rb"\x00xbl",
    "dwJoin": rb"dwJoin",
    "DW_": rb"DW_",
    "Party_": rb"Party_",
    "lobby_connect": rb"lobby_connect",
}

out = []
out.append("exe size: %d bytes" % len(data))
for name, pat in patterns.items():
    hits = [m.start() for m in re.finditer(pat, data)]
    out.append("\n=== %s : %d hits ===" % (name, len(hits)))
    for off in hits[:12]:
        # show printable context around the hit
        start = max(0, off - 1)
        end = min(len(data), off + len(pat) + 48)
        chunk = data[start:end]
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        out.append("  0x%08X  %s" % (off, text))

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("done, hits written to", OUT)
