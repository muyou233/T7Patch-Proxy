# [LOCAL] one-off: why is blackops3_dxgi.log still written?
import hashlib, os, time

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
T7 = os.path.join(GAME, "T7Patch")

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:8].upper()

print("== game dir key files ==")
for name in ("d3d11.dll", "d3d11.bak", "dxgi.dll", "d3d11_backend.dll", "blackops3_dxgi.log", "blackops3_d3d11.log", "dxvk.conf"):
    p = os.path.join(GAME, name)
    if os.path.exists(p):
        st = os.stat(p)
        print(f"{name:24s} {st.st_size:>12,d} B  {time.strftime('%m-%d %H:%M', time.localtime(st.st_mtime))}  {sha(p)}")
    else:
        print(f"{name:24s} MISSING")

print("\n== T7Patch\\dxvk ==")
d = os.path.join(T7, "dxvk")
if os.path.isdir(d):
    for n in sorted(os.listdir(d)):
        p = os.path.join(d, n)
        st = os.stat(p)
        print(f"{n:24s} {st.st_size:>12,d} B  {time.strftime('%m-%d %H:%M', time.localtime(st.st_mtime))}")
else:
    print("missing dir")

print("\n== deployed d3d11.dll contains DXVK_LOG_LEVEL? ==")
p = os.path.join(GAME, "d3d11.dll")
blob = open(p, "rb").read()
for label, pat in (("ascii", b"DXVK_LOG_LEVEL"), ("utf16", "DXVK_LOG_LEVEL".encode("utf-16le"))):
    print(label, "HIT" if pat in blob else "no")
print("ascii 'DXVK_CONFIG_FILE' hit:", b"DXVK_CONFIG_FILE" in blob or "DXVK_CONFIG_FILE".encode("utf-16le") in blob)

log = os.path.join(GAME, "blackops3_dxgi.log")
if os.path.exists(log):
    print("\n== blackops3_dxgi.log (head) ==")
    raw = open(log, "rb").read()
    try:
        text = raw.decode("utf-8", "replace")
    except Exception:
        text = raw.decode("latin-1", "replace")
    for line in text.splitlines()[:40]:
        print(line)

t7log = os.path.join(T7, "t7patch.log")
if os.path.exists(t7log):
    print("\n== t7patch.log lines mentioning dxvk/backend/dxgi (last 30) ==")
    raw = open(t7log, "rb").read().decode("utf-8", "replace")
    hits = [l for l in raw.splitlines() if any(k in l.lower() for k in ("dxvk", "backend", "dxgi"))]
    for line in hits[-30:]:
        print(line)
