import re, sys

path = sys.argv[1]
data = open(path, 'rb').read()

# All NUL-terminated ASCII strings in the image, we look for d3d11 / dxgi / xinput names
cands = [
    b'D3D11CreateDevice', b'D3D11CreateDeviceAndSwapChain', b'D3D11On12CreateDevice',
    b'D3D11CoreCreateDevice', b'D3D11CoreRegisterLayers', b'D3D11CoreGetLayeredDeviceSize',
    b'D3D11CoreCreateLayeredDevice', b'CreateDirect3D11DeviceFromDXGIDevice',
    b'CreateDirect3D11SurfaceFromDXGISurface', b'EnableFeatureLevelUpgrade',
    b'OpenAdapter10', b'OpenAdapter10_2', b'D3D11CreateDeviceForD3D12',
    b'XInputGetState', b'XInputSetState', b'XInputEnable',
]
print('--- hits in %s ---' % path)
for c in cands:
    n = data.count(c + b'\x00')
    if n:
        print('  %-45s exact-nul-term x%d' % (c.decode(), n))

print('--- every null-terminated string starting with D3D11CreateDevice ---')
for m in re.finditer(rb'D3D11CreateDevice[A-Za-z0-9_]*\x00', data):
    print('   ', m.group()[:-1].decode())

print('--- every null-terminated string containing XInput ---')
seen = set()
for m in re.finditer(rb'XInput[A-Za-z0-9_]*\x00', data):
    s = m.group()[:-1].decode()
    if s not in seen:
        seen.add(s)
        print('   ', s)
