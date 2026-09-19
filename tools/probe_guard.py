# -*- coding: utf-8 -*-
# ?? translate.cpp ???????,????"????"????????
import sys, io
DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
K_MAX_WILDCARDS = 8
def trim(b): return b.rstrip(b" \t\r\n")
def parse(path):
    exact, pats = {}, []
    for raw in open(path,"rb").read().split(b"\n"):
        if len(raw) > 1024: continue
        p = raw.lstrip(b" \t")
        if not p or p[:1] in (b"#",b";") or b"=" not in p: continue
        k,v = p.split(b"=",1); k,v = trim(k), trim(v)
        if not k or not v: continue
        k = k.lower()
        if b"*" in k:
            parts = k.split(b"*")
            if len(parts)-1 <= K_MAX_WILDCARDS: pats.append(parts)
        else: exact[k]=v
    pats.sort(key=len)
    return exact,pats
def match_tpl(parts,key):
    n=len(parts)
    if n<2: return None
    head=parts[0]
    if not key.startswith(head): return None
    pos=len(head)
    for i in range(1,n-1):
        at=key.find(parts[i],pos)
        if at<0: return None
        pos=at+len(parts[i])
    tail=parts[-1]
    if not key.endswith(tail) or len(key)-len(tail)<pos: return None
    return True
exact,pats = parse(DICT)
probes = ["BLACK OPS","CDP","black ops","cdp","Team Deathmatch","EVAC","AQUARIUM","METRO","EXODUS","REDWOOD","BREACH","Redwood Snow","EVACUATION","Aquarium","Metro","Exodus","Redwood","Breach","NUKETOWN","COMBINE","FRINGE","HAVOC","INFECTION","STRONGHOLD","HUNTED","RISE","SPLASH","VERGE"]
print("templates:", len(pats), " exact:", len(exact))
print("--- templates with head length <= 2 (?????) ---")
for p in pats:
    if len(p[0])<=2: print("   ", b"*".join(p).decode("utf-8","replace"))
print("--- ??????? ---")
for s in probes:
    k=s.lower().encode()
    hit=None
    if k in exact: hit="EXACT -> "+exact[k].decode("utf-8","replace")
    else:
        for p in pats:
            if match_tpl(p,k): hit="TEMPLATE -> "+b"*".join(p).decode("utf-8","replace"); break
    print("  %-14s %s" % (s, hit or "(???,????)"))
