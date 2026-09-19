import struct

P = r'C:\Windows\System32\ntdll.dll'
d = open(P, 'rb').read()
e_lfanew = struct.unpack_from('<I', d, 0x3C)[0]
assert d[e_lfanew:e_lfanew + 4] == b'PE\0\0'
coff = e_lfanew + 4
nsec, = struct.unpack_from('<H', d, coff + 2)
optsize, = struct.unpack_from('<H', d, coff + 16)
opt = coff + 20
magic, = struct.unpack_from('<H', d, opt)
ddir = opt + (112 if magic == 0x20b else 96)
edir_rva, edir_sz = struct.unpack_from('<II', d, ddir)
secs = []
so = opt + optsize
for i in range(nsec):
    name = d[so + i * 40: so + i * 40 + 8].rstrip(b'\0').decode()
    vsz, va, rsz, praw = struct.unpack_from('<IIII', d, so + i * 40 + 8)
    secs.append((name, va, vsz, praw, rsz))

def r2o(rva):
    for name, va, vsz, praw, rsz in secs:
        if va <= rva < va + max(vsz, rsz):
            return praw + (rva - va)
    return None

eo = r2o(edir_rva)
nfun, nnam = struct.unpack_from('<II', d, eo + 20)
afun, anam, aord = struct.unpack_from('<III', d, eo + 28)

want = None
for i in range(nnam):
    nrva, = struct.unpack_from('<I', d, anam + i * 4)
    o = r2o(nrva)
    nm = d[o:d.index(b'\0', o)].decode()
    if nm == 'KiUserExceptionDispatcher':
        want, = struct.unpack_from('<I', d, aord + i * 2)
        break

print('ntdll      :', P)
print('version    :', end=' ')
# optional header is enough; just show the file version resource instead
print('(see below)')
print('KiUserExceptionDispatcher RVA = 0x%X' % want)
o = r2o(want)
if o is None:
    print('  RVA not in file (forwarder?)')
else:
    blob = d[o:o + 24]
    first4, = struct.unpack_from('<I', blob, 0)
    print('  first bytes : ' + ' '.join('%02X' % b for b in blob[:16]))
    print('  dword[0]    : 0x%08X' % first4)
    print()
    print('  matches InstallHook pattern A (0x058B48FC) ?', first4 == 0x058B48FC)
    print('  matches InstallHook Wine  (0x248C8B48) ?', first4 == 0x248C8B48)
    print('  -> branch taken: ', end='')
    if first4 == 0x058B48FC:
        print('PATTERN A  (pointer-slot patch)')
    elif first4 == 0x248C8B48:
        print('WINE       (wine_installhook)')
    else:
        print('else  -> old_windows_installhook()  == EMPTY TODO STUB  => NO HOOK INSTALLED')

    # disassemble-by-eye: dump a few more bytes
    print()
    print('  first 48 bytes:')
    blob48 = d[o:o + 48]
    for i in range(0, 48, 16):
        print('    +%02X  %s' % (i, ' '.join('%02X' % b for b in blob48[i:i + 16])))
