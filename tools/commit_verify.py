# -*- coding: utf-8 -*-
# 只读：用 subprocess + UTF-8 直接读 git 提交信息，验证中文没被编码破坏
# （PowerShell 控制台是 GBK，它显示的乱码不代表对象内容坏了，必须这样验）。
import subprocess

GIT = "git"
out = []
for extra in ([], ["-1", "--skip=1"]):
    r = subprocess.run([GIT, "log", "--format=%h%n%B"] + extra,
                       capture_output=True)
    text = r.stdout.decode("utf-8", errors="replace")
    lines = text.splitlines()
    out.append("=== commit %s ===" % lines[0])
    out.extend(lines[1:8])
    out.append("  ...")

# 逐字节确认关键串
r = subprocess.run([GIT, "log", "-2", "--format=%B"], capture_output=True)
blob = r.stdout
out.append("")
for needle in ["链式".encode(), "DXVK 门禁".encode(), "zlib".encode(),
               "DXVK-LICENSE".encode(), "词库 926".encode()]:
    out.append("  %-20s in commit message: %s" % (needle.decode(), needle in blob))

r2 = subprocess.run([GIT, "status", "--porcelain"], capture_output=True)
out.append("  working tree clean: %s" % (r2.stdout.strip() == b""))

io_open = open(r"E:\MyProject\T7Patch\T7Patch-Proxy-Private\tools\commit_verify.txt",
               "w", encoding="utf-8")
io_open.write("\n".join(out))
io_open.close()
print("written")
