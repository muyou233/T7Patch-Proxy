import re, sys, collections

path = sys.argv[1]
data = open(path, 'rb').read()

pats = [rb'SteamAPI_[A-Za-z0-9_]{2,80}', rb'BIsDlcInstalled', rb'CheckAppOwnership',
        rb'GetDLCCount', rb'GetDLCDataByIndex', rb'IsAppInstalled']

found = collections.Counter()
for p in pats:
    for m in re.finditer(p + rb'\x00', data):
        found[m.group()[:-1].decode('latin1')] += 1

print('=== Steam-related strings in bo3.exe ===')
for s, n in sorted(found.items()):
    print('  %-60s x%d' % (s, n))
print()

dlc = [s for s in found if any(k in s for k in
       ('Dlc', 'DLC', 'Ownership', 'IsAppInstalled', 'Subscribed', 'License'))]
print('=== DLC / ownership related ===')
for s in sorted(dlc):
    print('  ' + s)
