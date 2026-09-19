# -*- coding: utf-8 -*-
r"""DXVK 后端的 启用 / 停用 / 收编 —— T7Patch 链式代理的配套工具。

布局
    游戏目录\
        d3d11.dll              我们的代理，唯一的入口，永远在这儿
        T7Patch\dxvk\          可选组件，默认停用（不占游戏目录）
            d3d11_backend.dll      DXVK 的 d3d11.dll（预先改好名）
            dxgi.dll               DXVK 的 dxgi.dll
            dxvk.conf              配置：代理会把它的路径喂给 DXVK，不用搬

    disable（默认）   两个 dll 都在 T7Patch\dxvk\   -> 游戏跑原生 D3D11
    enable            两个 dll 一起移到游戏目录     -> 游戏跑 Vulkan

为什么必须成对搬（这是本工具存在的唯一理由）
    游戏**静态导入** dxgi.dll，进程启动那一刻就绑定好了。于是：
      · 只有 backend、没有 dxgi -> 微软的 DXGI + DXVK 的 D3D11（混搭）
      · 只有 dxgi、没有 backend -> DXVK 的 DXGI + 微软的 D3D11（混搭）
    代理对第一种会主动忽略后端；第二种拦不住（dxgi 是游戏自己加载的），
    只能弹窗告诉玩家。所以两个文件永远一起进出 —— 成对搬是**结构性**要求。

用法
    dxvk_chain.py status                     看现在是哪一态
    dxvk_chain.py enable                     启用（两个 dll 搬到游戏目录）
    dxvk_chain.py disable                    停用（搬回 T7Patch\dxvk\）
    dxvk_chain.py import <DXVK 的 x64 目录>   收编一份下载好的 DXVK

原则：**只移动，绝不删除**；每步都打印；做完复验。
**并且校验位数**：DXVK 的发行包同时带 x32/ 与 x64/，拿错只会得到
ERROR_BAD_EXE_FORMAT (193)，而且游戏会安静地跑在系统 d3d11 上 —— 这种错误
必须在这里拦住，别指望玩家自己看出来。
"""
import io
import os
import shutil
import struct
import sys

GAME = r"F:\SteamLibrary\steamapps\common\Call of Duty Black Ops III"
STORE = os.path.join(GAME, "T7Patch", "dxvk")

FRONT = os.path.join(GAME, "d3d11.dll")
GAME_BACKEND = os.path.join(GAME, "d3d11_backend.dll")
GAME_DXGI = os.path.join(GAME, "dxgi.dll")

STORE_BACKEND = os.path.join(STORE, "d3d11_backend.dll")
STORE_DXGI = os.path.join(STORE, "dxgi.dll")

DXVK_MARKERS = (b"DXVK", b"dxvk")
OURS_MARKERS = (b"proxy: D3D11 backend", b"proxy: real d3d11.dll resolved")
MACHINE_X64 = 0x8664
MACHINE_X86 = 0x014C

PAIR = "d3d11_backend.dll + dxgi.dll"


def classify(path):
    """'ours' / 'dxvk' / 'other' / 'missing' —— 按内容判，不按大小/文件名。"""
    if not os.path.exists(path):
        return "missing"
    # 读整个文件：标记串在 .rdata，不一定落在前 64 KB 里。
    data = io.open(path, "rb").read()
    if any(m in data for m in OURS_MARKERS):
        return "ours"
    if any(m in data for m in DXVK_MARKERS):
        return "dxvk"
    return "other"


def machine(path):
    """('x64'|'x86'|'0x....'|'?', raw) —— 读 PE 头的 Machine 字段。"""
    try:
        with io.open(path, "rb") as fh:
            head = fh.read(0x400)
        if head[:2] != b"MZ":
            return "?", 0
        e = struct.unpack_from("<I", head, 0x3C)[0]
        if head[e:e + 4] != b"PE\0\0":
            return "?", 0
        raw = struct.unpack_from("<H", head, e + 4)[0]
    except Exception:                                    # noqa: BLE001
        return "?", 0
    if raw == MACHINE_X64:
        return "x64", raw
    if raw == MACHINE_X86:
        return "x86", raw
    return "0x%04X" % raw, raw


def describe(label, path):
    kind = classify(path)
    if kind == "missing":
        return "  %-24s (不存在)" % label
    arch, _ = machine(path)
    return "  %-24s %-5s %-4s %12d  %s" % (
        label, kind, arch, os.path.getsize(path), os.path.basename(path))


def where_backend():
    if classify(GAME_BACKEND) == "dxvk":
        return "game"
    if classify(STORE_BACKEND) == "dxvk":
        return "store"
    return "none"


def where_dxgi():
    if classify(GAME_DXGI) == "dxvk":
        return "game"
    if classify(STORE_DXGI) == "dxvk":
        return "store"
    return "none"


def show():
    print("游戏目录:", GAME)
    print("  [游戏目录]")
    print(describe("d3d11.dll", FRONT))
    print(describe("d3d11_backend.dll", GAME_BACKEND))
    print(describe("dxgi.dll", GAME_DXGI))
    print("  [T7Patch\\dxvk\\]")
    print(describe("d3d11_backend.dll", STORE_BACKEND))
    print(describe("dxgi.dll", STORE_DXGI))

    b, d = where_backend(), where_dxgi()
    print()
    if b == "game" and d == "game":
        print("=> 状态：DXVK 已启用（游戏跑 Vulkan + 补丁）")
    elif b == "store" and d == "store":
        print("=> 状态：DXVK 未启用（默认；游戏跑原生 D3D11 + 补丁）")
    elif b == "none" and d == "none":
        print("=> 状态：本机没有 DXVK 组件，用 import 收编一份")
    else:
        print("=> 状态：**半开** —— backend 在 %s，dxgi 在 %s" % (b, d))
        print("   这个状态是危险的（两套实现混搭）。跑一次 enable 或 disable 归一。")

    for label, path in (("后端", GAME_BACKEND), ("后端(停放)", STORE_BACKEND),
                        ("dxgi", GAME_DXGI), ("dxgi(停放)", STORE_DXGI)):
        if classify(path) != "missing" and machine(path)[1] == MACHINE_X86:
            print("!! %s 是 32 位 —— 64 位游戏加载它必然失败 (193)。"
                  "请换成 DXVK 发行包 x64/ 里的那份。" % label)
    return 0


def _require_store_x64():
    for label, path in (("d3d11_backend.dll", STORE_BACKEND), ("dxgi.dll", STORE_DXGI)):
        if classify(path) != "dxvk":
            print("停放目录里没有可用的 %s：%s" % (label, STORE))
            print("先跑: dxvk_chain.py import <DXVK 的 x64 目录>")
            return False
        arch, raw = machine(path)
        if raw != MACHINE_X64:
            print("拒绝启用：%s 是 %s（0x%04X），不是 x64。" % (label, arch, raw))
            return False
    return True


def enable():
    """两个 dll 一起从停放目录搬到游戏目录。"""
    if where_backend() == "game" and where_dxgi() == "game":
        print("已经是启用状态，无需操作。")
        return 0
    if where_backend() == "game" or where_dxgi() == "game":
        print("当前是半开状态 —— 先把游戏目录里的那一个 disable 再 enable。")
        return 1
    if classify(FRONT) != "ours":
        print("!! 游戏目录的 d3d11.dll 不是我们的代理（%s）—— 先让补丁就位。"
              % classify(FRONT))
        return 1
    if not _require_store_x64():
        return 1

    shutil.move(STORE_BACKEND, GAME_BACKEND)
    print("已搬到游戏目录: d3d11_backend.dll")
    shutil.move(STORE_DXGI, GAME_DXGI)
    print("已搬到游戏目录: dxgi.dll")

    if where_backend() == "game" and where_dxgi() == "game":
        print("复验通过：DXVK 已启用。**重启游戏**后生效。")
        return 0
    print("!! 复验失败，请手工检查")
    return 1


def disable():
    """两个 dll 一起搬回停放目录（游戏目录里的代理不动）。"""
    moved = 0
    if classify(GAME_BACKEND) == "dxvk":
        if os.path.exists(STORE_BACKEND):
            print("停放目录已有 d3d11_backend.dll，拒绝覆盖 —— 请先处理冲突。")
            return 1
        shutil.move(GAME_BACKEND, STORE_BACKEND)
        print("已搬回: d3d11_backend.dll -> T7Patch\\dxvk\\")
        moved += 1
    if classify(GAME_DXGI) == "dxvk":
        if os.path.exists(STORE_DXGI):
            print("停放目录已有 dxgi.dll，拒绝覆盖 —— 请先处理冲突。")
            return 1
        shutil.move(GAME_DXGI, STORE_DXGI)
        print("已搬回: dxgi.dll -> T7Patch\\dxvk\\")
        moved += 1

    if moved == 0:
        print("游戏目录里没有 DXVK 的两个文件，已经是停用状态。")
        return 0
    if where_backend() == "store" and where_dxgi() == "store":
        print("复验通过：DXVK 已停用，游戏目录只剩我们的 d3d11.dll。**重启游戏**后生效。")
        return 0
    print("!! 复验失败，请手工检查")
    return 1


def do_import(src_dir):
    """把一份下载好的 DXVK(x64) 收编进停放目录。"""
    src_dir = os.path.abspath(src_dir)
    src_d3d11 = os.path.join(src_dir, "d3d11.dll")
    src_dxgi = os.path.join(src_dir, "dxgi.dll")
    for p in (src_d3d11, src_dxgi):
        if not os.path.exists(p):
            print("源目录里没有 %s：%s" % (os.path.basename(p), src_dir))
            print("提示：DXVK 的发行包解压后是 x32/ 与 x64/ 两个子目录，指向 x64/。")
            return 1

    for label, p in (("d3d11.dll", src_d3d11), ("dxgi.dll", src_dxgi)):
        arch, raw = machine(p)
        if raw != MACHINE_X64:
            print("拒绝收编：%s 是 %s（0x%04X），不是 x64 —— "
                  "起它只会得到 ERROR_BAD_EXE_FORMAT (193)。" % (label, arch, raw))
            return 1

    if not os.path.isdir(STORE):
        os.makedirs(STORE)
        print("已创建停放目录: T7Patch\\dxvk")

    for dst, label in ((STORE_BACKEND, "d3d11_backend.dll"), (STORE_DXGI, "dxgi.dll")):
        if os.path.exists(dst):
            print("停放目录里已经有 %s —— 拒绝覆盖（先自己备份或删掉它）。" % label)
            return 1

    shutil.copy2(src_d3d11, STORE_BACKEND)
    print("已收编: d3d11.dll -> T7Patch\\dxvk\\d3d11_backend.dll (x64)")
    shutil.copy2(src_dxgi, STORE_DXGI)
    print("已收编: dxgi.dll -> T7Patch\\dxvk\\dxgi.dll (x64)")
    print("（用的是复制，源目录那份留着）")
    print("启用: dxvk_chain.py enable")
    return 0


def main():
    argv = sys.argv[1:]
    cmd = (argv[0] if argv else "status").lower()

    if cmd == "status":
        return show()
    if cmd == "enable":
        rc = enable(); print(); show(); return rc
    if cmd == "disable":
        rc = disable(); print(); show(); return rc
    if cmd == "import":
        if len(argv) < 2:
            print("用法: dxvk_chain.py import <DXVK 的 x64 目录>")
            return 2
        rc = do_import(argv[1]); print(); show(); return rc

    print("未知命令:", cmd)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
