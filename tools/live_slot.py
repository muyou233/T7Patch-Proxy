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
k32.CreateToolhelp32Snapshot.restype = w.HANDLE
k32.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]

h = k32.GetModuleHandleW('ntdll.dll')
local_base = ctypes.cast(h, ctypes.c_void_p).value
fn = k32.GetProcAddress(h, b'KiUserExceptionDispatcher')
rva = fn - local_base

# decode the dispatcher prologue to get the pointer slot it calls through
code = ctypes.string_at(fn, 32)
disp = struct.unpack_from('<i', code, 4)[0]          # mov rax,[rip+disp32] at +1
slot_rva = rva + 8 + disp
print('dispatcher RVA     : %X' % rva)
print('prologue           : ' + ' '.join('%02X' % b for b in code[:8]))
print('  FC = cld, 48 8B 05 disp32 = mov rax,[rip+disp32]')
print('pointer slot RVA   : %X  (= rva + 8 + %X)' % (slot_rva, disp))

# local (this python process) value of that slot == ntdll's default
local_slot = struct.unpack('<Q', ctypes.string_at(local_base + slot_rva, 8))[0]
print('local slot value   : %016X' % local_slot)

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
        pid = pe.th32ProcessID; break
    ok = k32.Process32Next(snap, ctypes.byref(pe))
k32.CloseHandle(snap)
if not pid:
    sys.exit('game not running')
print()
print('BlackOps3 pid      : %d' % pid)

class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize', w.DWORD), ('th32ModuleID', w.DWORD), ('th32ProcessID', w.DWORD),
                ('GlblcntUsage', w.DWORD), ('ProccntUsage', w.DWORD),
                ('modBaseAddr', ctypes.POINTER(ctypes.c_byte)), ('modBaseSize', w.DWORD),
                ('hModule', w.HMODULE), ('szModule', ctypes.c_wchar * 256),
                ('szExePath', ctypes.c_wchar * 260)]

snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, pid)
me = MODULEENTRY32W(); me.dwSize = ctypes.sizeof(me)
allmods = []
ok = k32.Module32FirstW(snap, ctypes.byref(me))
while ok:
    allmods.append((ctypes.cast(me.modBaseAddr, ctypes.c_void_p).value, me.modBaseSize,
                    me.szModule, me.szExePath))
    ok = k32.Module32NextW(snap, ctypes.byref(me))
k32.CloseHandle(snap)

print()
print('=== modules named *d3d11* / *d3dcompiler* in the game process ===')
for base, size, name, path in allmods:
    if 'd3d11' in name.lower() or 'd3dcompiler' in name.lower():
        print('  %016X  size %-8X  %-22s  %s' % (base, size, name, path))

def which(addr):
    for base, size, name, path in allmods:
        if base <= addr < base + size:
            return '%s+0x%X  (%s)' % (name, addr - base, path)
    return '<not in any module>'

hproc = k32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
tbase = [m for m in allmods if m[2].lower() == 'ntdll.dll'][0][0]
buf = ctypes.create_string_buffer(8)
got = ctypes.c_size_t(0)
r = k32.ReadProcessMemory(hproc, ctypes.c_void_p(tbase + slot_rva), buf, 8, ctypes.byref(got))
print()
print('=== THE DECISIVE CHECK: ntdll exception-dispatcher callback slot ===')
if not r:
    print('  ReadProcessMemory FAILED')
else:
    val = struct.unpack('<Q', buf.raw[:8])[0]
    print('  target slot addr : %016X' % (tbase + slot_rva))
    print('  target value     : %016X' % val)
    print('  -> resolves to   : %s' % which(val))
    print('  local default    : %016X' % local_slot)
    if val == local_slot:
        print()
        print('  >>> SLOT UNCHANGED  => the patch exception hook is NOT installed in this process')
    elif val != 0:
        print()
        print('  >>> SLOT PATCHED    => the patch exception hook IS installed (called for EVERY')
        print('      user-mode exception, process-wide)')
k32.CloseHandle(hproc)
