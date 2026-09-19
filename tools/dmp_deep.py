import struct, sys

path = sys.argv[1]
data = open(path, 'rb').read()
sig, ver, nstreams, dirstream, checksum, tds, flags = struct.unpack_from('<IIIIIIQ', data, 0)

NAMES = {3: 'ThreadList', 4: 'ModuleList', 5: 'MemoryList', 6: 'Exception', 7: 'SystemInfo',
         8: 'ThreadExList', 9: 'Memory64List', 10: 'CommentA', 11: 'CommentW',
         12: 'HandleData', 13: 'FunctionTable', 14: 'UnloadedModuleList', 15: 'MiscInfo',
         16: 'MemoryInfoList', 17: 'ThreadInfoList', 19: 'Token', 21: 'SystemMemoryInfo',
         22: 'ProcessVmCounters'}

streams = {}
print('=== streams (%d) ===' % nstreams)
for i in range(nstreams):
    stype, dsize, rva = struct.unpack_from('<III', data, dirstream + i * 12)
    streams[stype] = (dsize, rva)
    print('  type %2d  %-22s size %8d  rva %08X' % (stype, NAMES.get(stype, '?'), dsize, rva))

MODULE_LIST, THREAD_LIST, EXCEPTION, MEMORY_LIST, MEMORY_INFO = 4, 3, 6, 5, 16

def mdstring(rva):
    n = struct.unpack_from('<I', data, rva)[0]
    return data[rva + 4:rva + 4 + n].decode('utf-16-le', 'replace')

modules = []
_, rva = streams[MODULE_LIST]
n = struct.unpack_from('<I', data, rva)[0]
for i in range(n):
    off = rva + 4 + i * 108
    base, size, cs, ts, namerva = struct.unpack_from('<QIIII', data, off)
    try:
        name = mdstring(namerva)
    except Exception:
        name = '<bad>'
    modules.append((base, size, name))
modules.sort(key=lambda m: m[0])

def resolve(addr):
    best = None
    for base, size, name in modules:
        if base <= addr < base + size:
            return '%s + 0x%X' % (name.rsplit('\\', 1)[-1], addr - base)
    return None

MINE = [m for m in modules if 'Call of Duty Black Ops III' in m[2] and 'd3d11' in m[2]]
print()
print('=== our proxy module ===')
for base, size, name in MINE:
    print('  %016X  size %X  %s' % (base, size, name))

# ---- exception ----
_, rva = streams[EXCEPTION]
tid = struct.unpack_from('<I', data, rva)[0]
code, eflags, rec, eaddr, nparams, _u = struct.unpack_from('<IIQQII', data, rva + 8)
params = struct.unpack_from('<15Q', data, rva + 8 + 32)
ctx_size, ctx_rva = struct.unpack_from('<II', data, rva + 8 + 152)
print()
print('=== exception ===  tid=%d  code=%08X  addr=%016X  param0=%d' % (tid, code, eaddr, params[0]))

# ---- memory regions available in the dump ----
regions = []
if MEMORY_LIST in streams:
    _, mrva = streams[MEMORY_LIST]
    n = struct.unpack_from('<I', data, mrva)[0]
    for i in range(n):
        start, sz, r = struct.unpack_from('<QII', data, mrva + 4 + i * 16)
        regions.append((start, sz, r))
if 9 in streams:
    _, mrva = streams[9]
    nreg, base_rva = struct.unpack_from('<QQ', data, mrva)
    for i in range(nreg):
        start, sz = struct.unpack_from('<QQ', data, mrva + 16 + i * 16)
        regions.append((start, sz, base_rva))
regions.sort()
print()
print('=== memory regions in dump: %d ===' % len(regions))
hit = [r for r in regions if r[0] <= eaddr < r[0] + r[1]]
print('  does the fault address have a page in the dump?  %s' % ('YES' if hit else 'NO (unmapped / not captured)'))

def read_mem(addr, nbytes):
    for start, sz, r in regions:
        if start <= addr < start + sz:
            off = r + (addr - start)
            avail = min(nbytes, start + sz - addr)
            return data[off:off + avail]
    return None

# ---- threads ----
print()
print('=== threads ===')
threads = []
_, trva = streams[THREAD_LIST]
nt = struct.unpack_from('<I', data, trva)[0]
for i in range(nt):
    off = trva + 4 + i * 48
    tid_i, susp, prio_c, prio, teb, stack_start, stack_size, stack_rva = \
        struct.unpack_from('<IIIIQQII', data, off)
    ctx_sz, ctx_off = struct.unpack_from('<II', data, off + 40)
    threads.append((tid_i, stack_start, stack_size, stack_rva, ctx_off, ctx_sz))
    mark = '  <== FAULTING' if tid_i == tid else ''
    print('  tid %-6d stack %016X size %08X  captured_rva %08X%s'
          % (tid_i, stack_start, stack_size, stack_rva, mark))

# ---- registers of the faulting thread ----
ctx = data[ctx_rva:ctx_rva + ctx_size]
regs = {}
for off, nm in [(0x78,'Rax'),(0x80,'Rcx'),(0x88,'Rdx'),(0x90,'Rbx'),(0x98,'Rsp'),(0xA0,'Rbp'),
                (0xA8,'Rsi'),(0xB0,'Rdi'),(0xB8,'R8'),(0xC0,'R9'),(0xC8,'R10'),(0xD0,'R11'),
                (0xD8,'R12'),(0xE0,'R13'),(0xE8,'R14'),(0xF0,'R15'),(0xF8,'Rip')]:
    regs[nm] = struct.unpack_from('<Q', ctx, off)[0]

print()
print('=== registers resolved ===')
for nm in ('Rip','Rax','Rbx','Rcx','Rdx','Rsi','Rdi','R8','R9','R10','R11','R12','R13','R14','R15','Rsp','Rbp'):
    v = regs[nm]
    r = resolve(v)
    print('  %-4s %016X  %s' % (nm, v, r if r else ('<heap/data>' if v > 0x10000 else '<small>')))

# ---- scan the faulting thread's stack ----
ft = [t for t in threads if t[0] == tid]
print()
if ft:
    _, ss, ssz, srva, _, _ = ft[0]
    print('=== stack of faulting thread (from Rsp upward) ===')
    rsp = regs['Rsp']
    start_scan = rsp
    end_scan = min(ss + ssz, rsp + 0x600)
    prev = start_scan
    n_mod = 0
    for a in range(start_scan & ~7, end_scan, 8):
        mem = read_mem(a, 8)
        if not mem or len(mem) < 8:
            continue
        v = struct.unpack('<Q', mem)[0]
        r = resolve(v)
        if r:
            n_mod += 1
            flag = ''
            if 'd3d11' in r and 'Call of Duty' in r:
                flag = '   <<< OUR PROXY'
            print('  [%016X] %016X  ->  %s%s' % (a, v, r, flag))
    print('  (%d stack slots resolved into modules)' % n_mod)
else:
    print('faulting thread not in thread list')
