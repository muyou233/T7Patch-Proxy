import struct, sys

path = sys.argv[1]
data = open(path, 'rb').read()
sig, ver, nstreams, dirstream, cs, tds, flags = struct.unpack_from('<IIIIIIQ', data, 0)
streams = {}
for i in range(nstreams):
    st, ds, rv = struct.unpack_from('<III', data, dirstream + i * 12)
    streams[st] = (ds, rv)

def mdstring(rva):
    n = struct.unpack_from('<I', data, rva)[0]
    return data[rva + 4:rva + 4 + n].decode('utf-16-le', 'replace')

modules = []
_, rva = streams[4]
n = struct.unpack_from('<I', data, rva)[0]
for i in range(n):
    off = rva + 4 + i * 108
    base, size, c, ts, namerva = struct.unpack_from('<QIIII', data, off)
    modules.append((base, size, mdstring(namerva)))
modules.sort(key=lambda m: m[0])

regions = []
_, mrva = streams[5]
nr = struct.unpack_from('<I', data, mrva)[0]
for i in range(nr):
    start, sz, r = struct.unpack_from('<QII', data, mrva + 4 + i * 16)
    regions.append((start, sz, r))
regions.sort()

def resolve(a):
    for base, size, name in modules:
        if base <= a < base + size:
            return '%s+0x%X' % (name.rsplit('\\', 1)[-1], a - base)
    for start, sz, r in regions:
        if start <= a < start + sz:
            return '<dump region %016X (%d KB, %s)>' % (start, sz // 1024, 'STACK' if '754E' in '%X' % start or '754C' in '%X' % start or '754D' in '%X' % start else 'heap/other')
    return '<not captured>'

def where(addr):
    for start, sz, r in regions:
        if start <= addr < start + sz:
            return r + (addr - start)
    return None

TARGETS = [
    (0x7FF727D04700, 'FATAL execute target'),
    (0xFFEEDDCC44332212, 'lobbymsgprints sentinel'),
]

for val, label in TARGETS:
    print()
    print('=== searching memory for %016X  (%s) ===' % (val, label))
    needle = struct.pack('<Q', val)
    hits = 0
    for start, sz, r in regions:
        blob = data[r:r + sz]
        i = blob.find(needle)
        while i >= 0:
            addr = start + i
            ctx = blob[max(0, i - 32):i + 40]
            print('  at %016X  (region %016X, %s)  -> contains: %s' % (addr, start, resolve(addr), resolve(addr)))
            print('       surrounding qwords:')
            base_ctx = max(0, (i - 16))
            for j in range(base_ctx, min(len(blob) - 7, i + 24), 8):
                v = struct.unpack_from('<Q', blob, j)[0]
                mark = '   <<<<' if j == i else ''
                print('         %016X: %016X  %s%s' % (start + j, v, resolve(v) if v > 0x10000 else '', mark))
            hits += 1
            i = blob.find(needle, i + 1)
    if hits == 0:
        print('  (no occurrence in the captured memory)')

# a broader look: any qword in high-image neighbourhood 0x7FF72xxxxxxx / 0x7FF73xxx etc
print()
print('=== qwords in the 0x7FF72x / 0x7FF73x range anywhere in captured memory ===')
pat_lo = 0x7FF720000000
pat_hi = 0x7FF740000000
found = 0
for start, sz, r in regions:
    blob = data[r:r + sz]
    step = 1
    for i in range(0, len(blob) - 7, 8):
        v = struct.unpack_from('<Q', blob, i)[0]
        if pat_lo <= v < pat_hi:
            print('  value %016X found at %016X  -> %s' % (v, start + i, resolve(start + i)))
            found += 1
            if found > 60:
                break
    if found > 60:
        break
if found == 0:
    print('  (none)')
