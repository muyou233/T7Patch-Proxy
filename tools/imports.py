import struct, sys, os

def rva_to_off(sections, rva):
    for name, va, vsize, rawptr, rawsize in sections:
        if va <= rva < va + max(vsize, rawsize):
            return rawptr + (rva - va)
    return None

def parse(path):
    with open(path, 'rb') as f:
        data = f.read()
    e = struct.unpack_from('<I', data, 0x3C)[0]
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
        nm = data[o:o+8].rstrip(b'\0').decode('latin1')
        vsize, va, rawsize, rawptr = struct.unpack_from('<IIII', data, o+8)
        sections.append((nm, va, vsize, rawptr, rawsize))
    import_rva, _ = struct.unpack_from('<II', data, ddoff + 8)
    return data, sections, import_rva, is64

def cstr(data, off):
    end = data.index(b'\0', off)
    return data[off:end].decode('latin1')

def imports_named(path):
    data, sections, import_rva, is64 = parse(path)
    if not import_rva:
        return {}
    off = rva_to_off(sections, import_rva)
    res = {}
    i = 0
    while True:
        o = off + i * 20
        oft, ts, fc, namerva, fta = struct.unpack_from('<IIIII', data, o)
        if namerva == 0 and oft == 0 and fta == 0:
            break
        dll = cstr(data, rva_to_off(sections, namerva))
        thunk_rva = oft or fta
        t = rva_to_off(sections, thunk_rva)
        names = []
        j = 0
        step = 8 if is64 else 4
        while True:
            val = struct.unpack_from('<Q' if is64 else '<I', data, t + j*step)[0]
            if val == 0:
                break
            if is64:
                hi = val >> 63
                lo = val & 0x7fffffff
            else:
                hi = val >> 31
                lo = val & 0x7fffffff
            if hi:
                names.append(cstr(data, rva_to_off(sections, lo)))
            else:
                names.append('Ordinal#%d' % lo)
            j += 1
        res[dll] = names
        i += 1
    return res

for path in sys.argv[1:]:
    print('=' * 70)
    print(os.path.basename(path))
    imps = imports_named(path)
    for dll, names in imps.items():
        print('  %s -> %s' % (dll, ', '.join(names)))
