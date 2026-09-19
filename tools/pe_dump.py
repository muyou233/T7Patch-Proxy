import struct, sys, os

def rva_to_off(sections, rva):
    for name, va, vsize, rawptr, rawsize in sections:
        if va <= rva < va + max(vsize, rawsize):
            return rawptr + (rva - va)
    return None

def parse(path):
    with open(path, 'rb') as f:
        data = f.read()
    e_lfanew = struct.unpack_from('<I', data, 0x3C)[0]
    assert data[e_lfanew:e_lfanew+4] == b'PE\0\0', 'not PE'
    coff = e_lfanew + 4
    machine, nsec, ts, _, _, optsize, chars = struct.unpack_from('<HHIIIHH', data, coff)
    opt = coff + 20
    magic = struct.unpack_from('<H', data, opt)[0]
    is64 = magic == 0x20b
    ddoff = opt + (112 if is64 else 96)
    sections = []
    secoff = opt + optsize
    for i in range(nsec):
        o = secoff + i*40
        name = data[o:o+8].rstrip(b'\0').decode('latin1')
        vsize, va, rawsize, rawptr = struct.unpack_from('<IIII', data, o+8)
        sections.append((name, va, vsize, rawptr, rawsize))
    # directories
    export_rva, export_size = struct.unpack_from('<II', data, ddoff)
    import_rva, import_size = struct.unpack_from('<II', data, ddoff+8)
    tls_rva, tls_size = struct.unpack_from('<II', data, ddoff + (9*8))
    return {
        'data': data, 'machine': machine, 'ts': ts, 'sections': sections,
        'chars': chars, 'is64': is64, 'export_rva': export_rva,
        'import_rva': import_rva, 'tls_rva': tls_rva,
        'entry': struct.unpack_from('<I', data, opt+16)[0],
        'size_of_image': struct.unpack_from('<I', data, opt+56)[0],
    }

def exports(p):
    data = p['data']; sections = p['sections']
    rva = p['export_rva']
    if not rva:
        return [], []
    off = rva_to_off(sections, rva)
    nfunc, nname = struct.unpack_from('<II', data, off+20)
    addr_func, addr_name, addr_ord = struct.unpack_from('<III', data, off+28)
    foff = rva_to_off(sections, addr_func)
    noff = rva_to_off(sections, addr_name)
    ooff = rva_to_off(sections, addr_ord)
    names = {}
    for i in range(nname):
        n_rva = struct.unpack_from('<I', data, noff + i*4)[0]
        s = rva_to_off(sections, n_rva)
        end = data.index(b'\0', s)
        names[struct.unpack_from('<H', data, ooff + i*2)[0]] = data[s:end].decode('latin1')
    out = []
    for i in range(nfunc):
        frva = struct.unpack_from('<I', data, foff + i*4)[0]
        nm = names.get(i)
        if frva == 0 and nm is None:
            continue
        fwd = None
        if frva and rva <= frva < rva + struct.unpack_from('<I', data, rva_to_off(sections, rva)+16)[0]:
            s = rva_to_off(sections, frva)
            end = data.index(b'\0', s)
            fwd = data[s:end].decode('latin1')
        out.append((i, nm, frva, fwd))
    return out, names

def imports(p):
    data = p['data']; sections = p['sections']
    rva = p['import_rva']
    if not rva:
        return []
    off = rva_to_off(sections, rva)
    res = []
    i = 0
    while True:
        o = off + i*20
        oft, ts, fc, namerva, fta = struct.unpack_from('<IIIII', data, o)
        if namerva == 0 and oft == 0:
            break
        ns = rva_to_off(sections, namerva)
        end = data.index(b'\0', ns)
        res.append(data[ns:end].decode('latin1'))
        i += 1
    return res

for path in sys.argv[1:]:
    print('='*70)
    print(path, os.path.getsize(path) if os.path.exists(path) else 'MISSING')
    p = parse(path)
    print('machine=%x ts=%08x image=%x entry=%x' % (p['machine'], p['ts'], p['size_of_image'], p['entry']))
    print('sections:', [(s[0], hex(s[1]), hex(s[2])) for s in p['sections']])
    print('TLS rva:', hex(p['tls_rva']))
    ex, names = exports(p)
    print('exports: %d' % len(ex))
    fwd = [e for e in ex if e[3]]
    print('forwarders: %d' % len(fwd))
    imp = imports(p)
    print('imports (%d): %s' % (len(imp), ', '.join(imp)))
    if fwd:
        for e in fwd[:20]:
            print('  FWD #%d %s -> %s' % (e[0], e[1], e[3]))
    print('export names:')
    print(', '.join('%s@%d' % (e[1], e[0]) for e in ex if e[1]))
