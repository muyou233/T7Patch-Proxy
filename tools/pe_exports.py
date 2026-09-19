import struct, sys

def rva_to_off(sections, rva):
    for name, va, vsize, rawptr, rawsize in sections:
        if va <= rva < va + max(vsize, rawsize):
            return rawptr + (rva - va)
    return None

path = sys.argv[1]
data = open(path, 'rb').read()
e = struct.unpack_from('<I', data, 0x3C)[0]
assert data[e:e + 4] == b'PE\0\0', 'not a PE'
coff = e + 4
machine, nsec, ts, _, _, optsize, chars = struct.unpack_from('<HHIIIHH', data, coff)
opt = coff + 20
magic = struct.unpack_from('<H', data, opt)[0]
is64 = magic == 0x20b
ddoff = opt + (112 if is64 else 96)

sections = []
secoff = opt + optsize
for i in range(nsec):
    o = secoff + i * 40
    nm = data[o:o + 8].rstrip(b'\0').decode('latin1')
    vsize, va, rawsize, rawptr = struct.unpack_from('<IIII', data, o + 8)
    sections.append((nm, va, vsize, rawptr, rawsize))

print('file      : %s' % path)
print('machine   : %04x  (%s)' % (machine, 'x64' if machine == 0x8664 else 'NOT x64'))
print('timestamp : %08x' % ts)

export_rva, export_size = struct.unpack_from('<II', data, ddoff)
if not export_rva:
    print('NO EXPORTS')
    sys.exit(0)

def cstr(o):
    return data[o:data.index(b'\0', o)].decode('latin1')

off = rva_to_off(sections, export_rva)
name_rva = struct.unpack_from('<I', data, off + 12)[0]
base = struct.unpack_from('<I', data, off + 16)[0]
nfunc = struct.unpack_from('<I', data, off + 20)[0]
nname = struct.unpack_from('<I', data, off + 24)[0]
addr_func = struct.unpack_from('<I', data, off + 28)[0]
addr_name = struct.unpack_from('<I', data, off + 32)[0]
addr_ord = struct.unpack_from('<I', data, off + 36)[0]

print('dll name  : %s' % cstr(rva_to_off(sections, name_rva)))
print('ord base  : %d   (real d3d11.dll uses 0)' % base)
print('EAT slots : %d' % nfunc)
print('named     : %d' % nname)
print()

foff = rva_to_off(sections, addr_func)
noff = rva_to_off(sections, addr_name)
ooff = rva_to_off(sections, addr_ord)

by_ord = {}
for i in range(nname):
    nr = struct.unpack_from('<I', data, noff + i * 4)[0]
    idx = struct.unpack_from('<H', data, ooff + i * 2)[0]
    by_ord[base + idx] = cstr(rva_to_off(sections, nr))

print('--- %d exported names ---' % len(by_ord))
for k in sorted(by_ord):
    frva = struct.unpack_from('<I', data, foff + (k - base) * 4)[0]
    fwd = ''
    if export_rva <= frva < export_rva + export_size:
        fwd = '  FORWARDER -> ' + cstr(rva_to_off(sections, frva))
    print('  %3d  %-42s rva=0x%06x%s' % (k, by_ord[k], frva, fwd))
