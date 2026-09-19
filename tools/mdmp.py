import struct, sys

path = sys.argv[1]
data = open(path, 'rb').read()

sig, ver, nstreams, dirstream, checksum, tds, flags = struct.unpack_from('<IIIIIIQ', data, 0)
print('file      : %s  (%d bytes)' % (path, len(data)))
print('signature : %08x  (%s)' % (sig, 'MDMP' if sig == 0x504D444D else 'NOT A MINIDUMP'))
print('streams   : %d' % nstreams)
print()

streams = {}
for i in range(nstreams):
    stype, dsize, rva = struct.unpack_from('<III', data, dirstream + i * 12)
    streams[stype] = (dsize, rva)

MODULE_LIST, THREAD_LIST, EXCEPTION, SYSTEM_INFO, MEMORY_LIST, MEMORY_INFO = 4, 3, 6, 7, 9, 16

def mdstring(rva):
    n = struct.unpack_from('<I', data, rva)[0]
    return data[rva + 4:rva + 4 + n].decode('utf-16-le', 'replace')

modules = []
if MODULE_LIST in streams:
    _, rva = streams[MODULE_LIST]
    n = struct.unpack_from('<I', data, rva)[0]
    for i in range(n):
        off = rva + 4 + i * 108
        base, size, cs, ts, namerva = struct.unpack_from('<QIIII', data, off)
        try:
            name = mdstring(namerva)
        except Exception:
            name = '<bad>'
        modules.append((base, size, ts, name))

def resolve(addr):
    for base, size, ts, name in modules:
        if base <= addr < base + size:
            return '%s + 0x%X' % (name, addr - base)
    return '<not in any module>'

if SYSTEM_INFO in streams:
    _, rva = streams[SYSTEM_INFO]
    arch, lvl, rev, ncpu, ptype, major, minor, build = struct.unpack_from('<HHHBBIII', data, rva)
    print('system    : arch=%d  %d.%d.%d  cpus=%d' % (arch, major, minor, build, ncpu))
    print()

print('=== modules (%d) ===' % len(modules))
for base, size, ts, name in sorted(modules, key=lambda m: m[0]):
    print('  %016X  size %08X  ts %08X  %s' % (base, size, ts, name))
print()

if EXCEPTION in streams:
    _, rva = streams[EXCEPTION]
    tid, _align = struct.unpack_from('<II', data, rva)
    code, eflags, rec, eaddr, nparams, _u = struct.unpack_from('<IIQQII', data, rva + 8)
    params = struct.unpack_from('<15Q', data, rva + 8 + 32)
    ctx_size, ctx_rva = struct.unpack_from('<II', data, rva + 8 + 152)

    print('=== exception ===')
    print('thread id      : %d' % tid)
    print('exception code : %08X' % code)
    print('exception addr : %016X   ->  %s' % (eaddr, resolve(eaddr)))
    print('flags          : %08X' % eflags)
    print('num params     : %d' % nparams)
    for i in range(min(nparams, 15)):
        print('   param[%d]    : %016X' % (i, params[i]))
    print('context size   : %d at %08X' % (ctx_size, ctx_rva))
    print()

    ctx = data[ctx_rva:ctx_rva + ctx_size]
    def reg(off, name):
        return '%s = %016X' % (name, struct.unpack_from('<Q', ctx, off)[0])
    print('=== faulting thread registers ===')
    for off, nm in [(0x78,'Rax'),(0x80,'Rcx'),(0x88,'Rdx'),(0x90,'Rbx'),
                    (0x98,'Rsp'),(0xA0,'Rbp'),(0xA8,'Rsi'),(0xB0,'Rdi'),
                    (0xB8,'R8'),(0xC0,'R9'),(0xC8,'R10'),(0xD0,'R11'),
                    (0xD8,'R12'),(0xE0,'R13'),(0xE8,'R14'),(0xF0,'R15'),
                    (0xF8,'Rip'),(0x44,'EFlags')]:
        print('  ' + reg(off, nm))
    rip = struct.unpack_from('<Q', ctx, 0xF8)[0]
    rsp = struct.unpack_from('<Q', ctx, 0x98)[0]
    print('  -> Rip resolves to: %s' % resolve(rip))
    print('  -> Rsp = %016X' % rsp)
else:
    print('no exception stream')
