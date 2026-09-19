import ctypes, ctypes.wintypes as w, struct, sys

k32 = ctypes.WinDLL('kernel32', use_last_error=True)
k32.GetModuleHandleW.restype = w.HMODULE
k32.GetModuleHandleW.argtypes = [w.LPCWSTR]
k32.GetProcAddress.restype = ctypes.c_void_p
k32.GetProcAddress.argtypes = [w.HMODULE, ctypes.c_char_p]
k32.OpenProcess.restype = w.HANDLE
k32.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
k32.ReadProcessMemory.restype = w.BOOL
k32.ReadProcessMemory.argtypes = [w.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                  ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.CloseHandle.argtypes = [w.HANDLE]
k32.CreateToolhelp32Snapshot.restype = w.HANDLE
k32.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]

# --- local ntdll: get the RVA of KiUserExceptionDispatcher ---
h = k32.GetModuleHandleW('ntdll.dll')
local_base = ctypes.cast(h, ctypes.c_void_p).value
fn = k32.GetProcAddress(h, b'KiUserExceptionDispatcher')
rva = fn - local_base
print('local ntdll base   : %016X' % local_base)
print('KiUserExceptionDispatcher + RVA = %016X' % rva)
local_bytes = ctypes.string_at(fn, 48)
print('local first bytes  : ' + ' '.join('%02X' % b for b in local_bytes[:16]))
d0 = struct.unpack_from('<I', local_bytes, 0)[0]
print('local dword[0]     : 0x%08X' % d0)
print('  -> pattern A (0x058B48FC)? %s   Wine (0x248C8B48)? %s' %
      (d0 == 0x058B48FC, d0 == 0x248C8B48))

# --- find the game process ---
TH32CS_SNAPMODULE, TH32CS_SNAPPROCESS = 0x8, 0x2
PROCESS_VM_READ, PROCESS_QUERY_INFORMATION = 0x10, 0x400

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [('dwSize', w.DWORD), ('cntUsage', w.DWORD), ('th32ProcessID', w.DWORD),
                ('th32DefaultHeapID', ctypes.POINTER(ctypes.c_ulong)), ('th32ModuleID', w.DWORD),
                ('cntThreads', w.DWORD), ('th32ParentProcessID', w.DWORD), ('pcPriClassBase', ctypes.c_long),
                ('dwFlags', w.DWORD), ('szExeFile', ctypes.c_char * 260)]

snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
pe = PROCESSENTRY32(); pe.dwSize = ctypes.sizeof(pe)
pid = 0
ok = k32.Process32First(snap, ctypes.byref(pe))
while ok:
    if pe.szExeFile.lower() == b'blackops3.exe':
        pid = pe.th32ProcessID
        break
    ok = k32.Process32Next(snap, ctypes.byref(pe))
k32.CloseHandle(snap)
print()
print('BlackOps3 pid      :', pid)
if not pid:
    sys.exit('game not running')

class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize', w.DWORD), ('th32ModuleID', w.DWORD), ('th32ProcessID', w.DWORD),
                ('GlblcntUsage', w.DWORD), ('ProccntUsage', w.DWORD),
                ('modBaseAddr', ctypes.POINTER(ctypes.c_byte)), ('modBaseSize', w.DWORD),
                ('hModule', w.HMODULE), ('szModule', ctypes.c_wchar * 256),
                ('szExePath', ctypes.c_wchar * 260)]

snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, pid)
me = MODULEENTRY32W(); me.dwSize = ctypes.sizeof(me)
mods = {}
ok = k32.Module32FirstW(snap, ctypes.byref(me))
while ok:
    mods[me.szModule.lower()] = (ctypes.cast(me.modBaseAddr, ctypes.c_void_p).value, me.modBaseSize)
    ok = k32.Module32NextW(snap, ctypes.byref(me))
k32.CloseHandle(snap)

for want in ('ntdll.dll', 'd3d11.dll', 'kernel32.dll'):
    if want in mods:
        print('target %-14s base %016X size %X' % (want, mods[want][0], mods[want][1]))

tbase = mods['ntdll.dll'][0]
hproc = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
print('OpenProcess        :', hex(hproc))
buf = ctypes.create_string_buffer(48)
got = ctypes.c_size_t(0)
addr = tbase + rva
r = k32.ReadProcessMemory(hproc, ctypes.c_void_p(addr), buf, 48, ctypes.byref(got))
print('ReadProcessMemory  :', bool(r), 'bytes=%d' % got.value, 'at %016X' % addr)
if r:
    live = buf.raw[:got.value]
    print('LIVE first bytes   : ' + ' '.join('%02X' % b for b in live[:16]))
    print()
    if live[:16] == local_bytes[:16]:
        print('>>> LIVE == LOCAL (clean ntdll)  => the patch exception hook is NOT installed')
        print('    (InstallHook fell into the else branch: old_windows_installhook = empty TODO stub)')
    else:
        print('>>> LIVE != LOCAL  => ntdll code HAS BEEN PATCHED  => exception hook IS installed')
    print()
    print('live first 48 bytes:')
    for i in range(0, 48, 16):
        print('   +%02X  %s' % (i, ' '.join('%02X' % b for b in live[i:i + 16])))
    print('local first 48 bytes:')
    for i in range(0, 48, 16):
        print('   +%02X  %s' % (i, ' '.join('%02X' % b for b in local_bytes[i:i + 16])))
k32.CloseHandle(hproc)
