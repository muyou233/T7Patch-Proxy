# Simulate the exact loop the user is worried about, in a throwaway folder:
#   Steam verify  -> d3dcompiler_46.dll appears in the GAME folder
#   game launch   -> our startup reconciliation parks it (game\X.dll -> T7Patch\X.dll.bak)
# Repeated 3 times with a DIFFERENT file size each round, so both questions are
# answered at once: does the folder grow, and is the parked copy the latest one?
import ctypes, os, shutil

REPLACE_EXISTING = 0x1
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.MoveFileExW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
k32.MoveFileExW.restype = ctypes.c_int

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_movesim")
if os.path.isdir(root):
    shutil.rmtree(root)
game = os.path.join(root, "game")
park = os.path.join(game, "T7Patch")
os.makedirs(park)

dll = os.path.join(game, "d3dcompiler_46.dll")
bak = os.path.join(park, "d3dcompiler_46.dll.bak")


def listing(tag):
    g = [n for n in sorted(os.listdir(game)) if os.path.isfile(os.path.join(game, n))]
    p = sorted(os.listdir(park))
    sz = os.path.getsize(bak) if os.path.exists(bak) else None
    print("%-22s game=%s  T7Patch=%s  parked_count=%d  parked_size=%s"
          % (tag, g, p, len(p), sz))


listing("initial")

for i in range(1, 4):
    size = 100 * i                      # round 3 delivers a bigger file than round 1
    with open(dll, "wb") as f:
        f.write(b"\x00" * size)
    print("")
    print("cycle %d step1  steam verify -> game\\d3dcompiler_46.dll written, %d B" % (i, size))
    listing("cycle %d after verify" % i)

    ok = k32.MoveFileExW(dll, bak, REPLACE_EXISTING)
    err = ctypes.get_last_error()
    print("cycle %d step2  game launch  -> MoveFileExW(REPLACE_EXISTING) ret=%d err=%d" % (i, ok, err))
    listing("cycle %d after launch" % i)

print("")
print("(the real patch logs '46 file: stale parked copy found - replacing it' on rounds 2 and 3)")
shutil.rmtree(root, ignore_errors=True)
