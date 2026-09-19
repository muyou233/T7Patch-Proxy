# -*- coding: utf-8 -*-
# 只读：UTF-8 直读最新提交验证中文无损。
import subprocess

r = subprocess.run(["git", "log", "-1", "--format=%h%n%s"], capture_output=True)
head = r.stdout.decode("utf-8", errors="replace")
r2 = subprocess.run(["git", "log", "-1", "--format=%B"], capture_output=True)
blob = r2.stdout
r3 = subprocess.run(["git", "status", "--porcelain"], capture_output=True)
r4 = subprocess.run(["git", "log", "--oneline", "-5"], capture_output=True)

out = ["=== HEAD ===", head, ""]
for needle in ["启用开关".encode(), "首装".encode(), "SolidCheckbox".encode(),
               "重启生效".encode()]:
    out.append("  %-14s in message: %s" % (needle.decode(), needle in blob))
out.append("  working tree clean: %s" % (r3.stdout.strip() == b""))
out.append("")
out.append(r4.stdout.decode("utf-8", errors="replace"))

with open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\commit4_verify.txt",
          "w", encoding="utf-8") as f:
    f.write("\n".join(out))
print("written")
