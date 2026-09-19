# -*- coding: utf-8 -*-
import collections
P = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\ui_callers_round2.txt"
rows=[]
for line in open(P,"rb").read().split(b"\n"):
    if not line or line[:1]==b"#": continue
    p=line.split(b"\t",3)
    if len(p)<4: continue
    rows.append((p[0].decode(), p[1].decode(), p[2].decode("utf-8","replace"), p[3].decode("utf-8","replace")))
print("?? %d" % len(rows))
el=collections.Counter(e for _,_,e,_ in rows)
print("element ?????(? 10):", el.most_common(10))
print("element != '-' ???: %d" % sum(1 for _,_,e,_ in rows if e!="-"))
# ??????????
pair=collections.Counter((r,k) for r,k,_,_ in rows)
print("")
print("??????:")
for (r,k),c in sorted(pair.items()): print("   0x%s %-6s %d" % (r,k,c))

DICT = r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\translate\translate_zh.txt"
def trim(b): return b.rstrip(b" \t\r\n")
solo=[]
for raw in open(DICT,"rb").read().split(b"\n"):
    if len(raw)>1024: continue
    p=raw.lstrip(b" \t")
    if not p or p[:1] in (b"#",b";") or b"=" not in p: continue
    k,v=p.split(b"=",1); k,v=trim(k),trim(v)
    if not k or not v: continue
    if b"*" in k: continue
    if b" " in k: continue
    if all(97<=c<=122 for c in k) and len(k)<=9:
        solo.append((k.decode(),v.decode("utf-8","replace")))
solo.sort()
print("")
print("=== ? token ???? <=9 ?????(?????????):%d ? ===" % len(solo))
for i in range(0,len(solo),4):
    print("   ", "   ".join("%-11s=%-12s" % x for x in solo[i:i+4]))
