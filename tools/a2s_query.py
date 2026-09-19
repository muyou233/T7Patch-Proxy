"""
A2S (Source Engine Query) probe for Call of Duty: Black Ops III (appid 311210).

Purpose: decide whether a server list can be obtained WITHOUT touching game
memory -- i.e. by talking to Valve's master server directly.

Step 1: ask the master server for BO3 servers (A2M_GET_SERVERS_BATCH2, 0x31).
Step 2: pick a few and ask each one for its info (A2S_INFO).

Read-only: sends only well-formed queries, stores nothing.
"""
import socket
import struct
import sys

APPID = 311210
MASTERS = [
    ("hl2master.steampowered.com", 27011),
    ("208.64.200.52", 27011),      # hl2master A record (fallback)
]
REGION_WORLD = 0xFF

OUT = []


def log(s):
    OUT.append(s)
    print(s, flush=True)


def master_query(host, port, timeout=6.0):
    """Return list of 'ip:port' strings, or raise."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        # A2M_GET_SERVERS_BATCH2
        req = (b"\xFF\xFF\xFF\xFF" + b"\x31" + bytes([REGION_WORLD])
               + b"0.0.0.0:0\x00" + ("\\appid\\%d" % APPID).encode() + b"\x00")
        s.sendto(req, (host, port))
        served, count, cur = [], 0, b"0.0.0.0:0"
        while True:
            data, addr = s.recvfrom(4096)
            if not data.startswith(b"\xFF\xFF\xFF\xFF"):
                break
            body = data[4:]
            if body[:1] != b"\x0A":   # 0x0A = S2A_SERVERS
                break
            body = body[1:]
            parts = body.split(b"\x00")
            done = False
            for p in parts:
                if not p:
                    continue
                t = p.decode("latin-1")
                if t == "0.0.0.0:0":
                    done = True
                    break
                served.append(t)
            count += 1
            if done or not served or count >= 12:
                break
        return served
    finally:
        s.close()


def a2s_info(ip, port, timeout=2.5):
    """One A2S_INFO. Returns dict or None."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        req = b"\xFF\xFF\xFF\xFFTSource Engine Query\x00"
        s.sendto(req, (ip, port))
        data, _ = s.recvfrom(4096)
        if not data.startswith(b"\xFF\xFF\xFF\xFF"):
            return None
        body = data[4:]
        hdr = body[:1]
        if hdr == b"\x41":            # 'A' -> challenge, retry once
            ch = body[1:5]
            s.sendto(b"\xFF\xFF\xFF\xFFTSource Engine Query\x00" + ch, (ip, port))
            data, _ = s.recvfrom(4096)
            body = data[4:]
            hdr = body[:1]
        if hdr != b"\x49":            # 'I' = Source
            return {"raw_header": hdr.hex(), "raw": body[:64].hex()}
        o = 1
        proto = body[o]; o += 1
        def rstr():
            nonlocal o
            e = body.index(b"\x00", o)
            v = body[o:e].decode("latin-1", "replace")
            o = e + 1
            return v
        name = rstr(); mapname = rstr(); folder = rstr(); game = rstr()
        appid = struct.unpack_from("<H", body, o)[0]; o += 2
        players = body[o]; o += 1
        maxplayers = body[o]; o += 1
        bots = body[o]
        return {"proto": proto, "name": name, "map": mapname, "folder": folder,
                "game": game, "appid": appid,
                "players": players, "max": maxplayers, "bots": bots}
    except Exception as e:
        return {"error": type(e).__name__ + ": " + str(e)}
    finally:
        s.close()


def main():
    log("=== A2S probe for appid %d ===" % APPID)
    got = None
    for host, port in MASTERS:
        try:
            log("[master] querying %s:%d ..." % (host, port))
            got = master_query(host, port)
            log("[master] %s:%d -> %d server entries" % (host, port, len(got)))
            if got:
                break
        except Exception as e:
            log("[master] %s:%d FAILED: %s: %s" % (host, port, type(e).__name__, e))
    if not got:
        log("RESULT: master server gave nothing (blocked, filtered, or protocol differs)")
        return
    log("first 15 entries:")
    for e in got[:15]:
        log("   " + e)
    log("--- A2S_INFO on a sample ---")
    ok = 0
    for e in got[:8]:
        ip, _, prt = e.rpartition(":")
        r = a2s_info(ip, int(prt))
        if r and "error" not in r and "name" in r:
            ok += 1
            log("   %-22s %s | map=%s | %d/%d | appid=%s" %
                (e, r["name"][:40], r["map"], r["players"], r["max"], r["appid"]))
        else:
            log("   %-22s -> %s" % (e, r))
    log("RESULT: info_ok=%d/%d" % (ok, min(8, len(got))))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("FATAL: %s: %s" % (type(e).__name__, e))
    with open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\a2s_query.txt", "w",
              encoding="utf-8") as f:
        f.write("\n".join(OUT) + "\n")
