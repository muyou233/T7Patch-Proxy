# -*- coding: utf-8 -*-
"""A/B proof for the DXVK log suppression in T7Patch.

The claim under test (from DXVK 3.1.1 src/util/log/log.cpp):

  * DXVK_LOG_LEVEL is read ONCE, in the Logger constructor - i.e. while the
    DXVK module itself is being loaded.  Whatever the env says at that moment
    is latched forever.
  * DXVK_LOG_PATH is read LAZILY, inside getFileName(), on the first line
    DXVK actually emits.  "none" makes getFileName() return an empty string,
    so no log file is ever opened.

That asymmetry is why the patch sets BOTH variables from d3d11.dll's DllMain:
the level one only reaches the modules we load ourselves (the d3d11 backend),
while the path one still lands in time for DXVK's dxgi - a module the game
loads before us.

This script reproduces both halves with the real DLL, in a scratch directory:

    mode=control : load dxgi.dll, set nothing, poke it -> python_dxgi.log
    mode=fix     : load dxgi.dll, THEN set DXVK_LOG_PATH=none, poke it
                   -> nothing written (this is what the game should see now)
    mode=level   : set DXVK_LOG_LEVEL=none BEFORE loading -> the control case
                   with the level latched correctly, i.e. also nothing

Usage: python dxvk_logpath_ab.py <scratch-dir> <control|fix|level>
"""
import ctypes
import os
import sys

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
DXGI = os.path.join(GAME, "dxgi.dll")

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
k32.SetEnvironmentVariableW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
k32.SetEnvironmentVariableW.restype = ctypes.c_int
k32.GetEnvironmentVariableW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
k32.GetEnvironmentVariableW.restype = ctypes.c_uint


def getenv(name):
    buf = ctypes.create_unicode_buffer(512)
    n = k32.GetEnvironmentVariableW(name, buf, 512)
    return buf.value if n else None


def main():
    scratch, mode = sys.argv[1], sys.argv[2]
    os.chdir(scratch)
    print("mode          : %s" % mode)
    print("cwd           : %s" % os.getcwd())
    print("before: LEVEL=%r PATH=%r" % (getenv("DXVK_LOG_LEVEL"), getenv("DXVK_LOG_PATH")))

    if mode == "level":
        k32.SetEnvironmentVariableW("DXVK_LOG_LEVEL", "none")

    # Step 1 - load DXVK's dxgi the way the game's static import does.  Its
    # Logger constructor runs here and latches the level it can see.
    lib = ctypes.WinDLL(DXGI)
    print("loaded        : %s" % DXGI)

    # Step 2 - what T7Patch's DllMain does.  Too late for the level, in time
    # for the path, which is the whole point of the experiment.
    if mode == "fix":
        k32.SetEnvironmentVariableW("DXVK_LOG_LEVEL", "none")
        k32.SetEnvironmentVariableW("DXVK_LOG_PATH", "none")

    # Step 3 - make DXVK emit its first info line.  Creating a factory builds
    # a DxvkInstance, which logs the banner.
    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16),
                    ("Data3", ctypes.c_uint16), ("Data4", ctypes.c_ubyte * 8)]

    iid_factory1 = GUID(0x770AAE78, 0xF26F, 0x4DBA,
                        (ctypes.c_ubyte * 8)(0xA8, 0x29, 0x25, 0x3C, 0x83, 0xD1, 0xB3, 0x87))
    out = ctypes.c_void_p()
    try:
        hr = lib.CreateDXGIFactory1(ctypes.byref(iid_factory1), ctypes.byref(out))
        print("CreateDXGIFactory1 hr=0x%08X" % (hr & 0xFFFFFFFF))
    except Exception as exc:  # noqa: BLE001 - the log file is the real evidence
        print("CreateDXGIFactory1 raised: %r" % (exc,))

    name = "python_dxgi.log"
    path = os.path.join(scratch, name)
    exists = os.path.exists(path)
    print("log file      : %s -> %s" % (name, "CREATED" if exists else "absent"))
    if exists:
        print("size          : %d bytes" % os.path.getsize(path))
    print("VERDICT       : %s" % ("no log file written" if not exists else "log file WAS written"))


if __name__ == "__main__":
    main()
