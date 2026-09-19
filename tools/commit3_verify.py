# -*- coding: utf-8 -*-
# 只读：UTF-8 直读最新提交，验证中文与关键串（PowerShell 控制台乱码不代表对象坏）。
import subprocess

r = subprocess.run(["git", "log", "-1", "--format=%h%n%s"], capture_output=True)
head = r.stdout.decode("utf-8", errors="replace")
r2 = subprocess.run(["git", "log", "-1", "--format=%B"], capture_output=True)
blob = r2.stdout
r3 = subprocess.run(["git", "status", "--porcelain"], capture_output=True)

out = ["=== HEAD ===", head, ""]
for needle in ["双源".encode(), "SHA256 锁定".encode(), "仅成功起算".encode(),
               "dxvk_download".encode(), "tooltip 计数".encode()]:
    out.append("  %-14s in message: %s" % (needle.decode(), needle in blob))
out.append("  working tree clean: %s" % (r3.stdout.strip() == b""))
out.append("")
out.append(subprocess.run(["git", "log", "--oneline", "-4"],
                          capture_output=True).stdout.decode("utf-8", errors="replace"))

with open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\commit3_verify.txt",
          "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("written")
