# -*- coding: utf-8 -*-
# 离线复现 C++ 端的匹配逻辑：dump 串 -> lower -> 查词库
# 目的：区分「数据问题（隐藏字符/格式）」与「C++ 逻辑 bug」
import sys

GAME = r'F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III\T7Patch'
DICT = GAME + r'\translate_zh.txt'
DUMP = GAME + r'\ui_dump.txt'

# —— 复现 LoadDictionaryLocked ——
d = {}
with open(DICT, 'rb') as f:
    raw = f.read()
print('dict BOM:', raw[:3] == b'\xef\xbb\xbf')
text = raw.decode('utf-8-sig', errors='replace')
for ln in text.splitlines():
    s = ln
    # TrimTrailing 只去尾部
    s2 = s.rstrip(' \t\r\n')
    # loadfrom 侧：找第一个 '='
    if '=' not in s2:
        continue
    k, v = s2.split('=', 1)
    k = k.rstrip(' \t\r\n')
    v = v.strip()
    if not k or not v:
        continue
    d[k.lower()] = v
print('dict entries:', len(d))

# 抽查几个关键 key 是否在表里
for probe in ['switch user', 'campaign', 'multiplayer', 'press enter to start', 'zombies']:
    print(f'  key "{probe}" in dict: {probe in d}  -> {d.get(probe, "<MISSING>")}')

# —— 复现 Lookup：对 dump 每行 lower 后查表 ——
with open(DUMP, 'rb') as f:
    draw = f.read()
dt = draw.decode('utf-8-sig', errors='replace')
lines = dt.splitlines()
hits = 0
misses = []
for ln in lines:
    key = ln.strip().lower()
    if key in d:
        hits += 1
    else:
        misses.append(ln)
print(f'\ndump lines: {len(lines)}  hits: {hits}  misses: {len(misses)}')
print('\nfirst 25 misses (repr, 看隐藏字符):')
for m in misses[:25]:
    print('   ', repr(m))

# 特别检查 Switch User 的实际字节
print('\n--- "Switch User" 在 dump 里的原始字节 ---')
for ln in lines:
    if 'Switch' in ln:
        print('repr:', repr(ln))
        print('hex :', ln.encode('utf-8').hex())
        break
