#!/usr/bin/env python3
"""Find shared libraries that programs in the recovery ramdisk need but that are not in it.

    check_ramdisk_libs.py <recovery_root> [--fix <lib_dir> ...]

Reads DT_NEEDED of every ELF file under <recovery_root> (64-bit only) and looks the
names up in the ramdisk's lib64 folders. A missing library means that program cannot
start in recovery (if it is TWRP itself: black screen). TWRP copies libraries from a
fixed list that skips missing files silently, and decrypt builds link newer AIDL
library versions (keystore2-V4, keymint-V3, ...) than that list names.

--fix: copy each missing library (and what it needs, repeatedly) from the first
<lib_dir> that has it into <recovery_root>/system/lib64. Exit 1 if anything is still
missing afterwards. Standard library only.
"""
import os
import shutil
import struct
import sys

LIB_DIRS = ("system/lib64", "system/lib64/bootstrap", "vendor/lib64", "odm/lib64",
            "system_ext/lib64", "lib64")
# provided by the dynamic linker itself, no file
BUILTIN = {"ld-android.so"}


def needed(path):
    """DT_NEEDED names of a 64-bit little-endian ELF, or None if not one."""
    try:
        with open(path, "rb") as f:
            d = f.read()
    except OSError:
        return None
    if d[:4] != b"\x7fELF" or d[4] != 2 or d[5] != 1:
        return None
    shoff, = struct.unpack_from("<Q", d, 0x28)
    shentsize, shnum = struct.unpack_from("<HH", d, 0x3A)
    secs = [struct.unpack_from("<IIQQQQIIQQ", d, shoff + i * shentsize) for i in range(shnum)]
    out = []
    for name, typ, flags, addr, off, size, link, info, align, entsize in secs:
        if typ != 6:  # SHT_DYNAMIC
            continue
        stroff = secs[link][4]
        for i in range(0, size, 16):
            tag, val = struct.unpack_from("<qQ", d, off + i)
            if tag == 0:
                break
            if tag == 1:  # DT_NEEDED
                end = d.index(b"\0", stroff + val)
                out.append(d[stroff + val:end].decode())
    return out


def scan(root):
    have = set(BUILTIN)
    for ld in LIB_DIRS:
        p = os.path.join(root, ld)
        if os.path.isdir(p):
            have.update(os.listdir(p))
    missing = {}
    for dp, dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f)
            if os.path.islink(p) or p.endswith(".ko"):
                continue
            n = needed(p)
            for lib in n or ():
                if lib not in have:
                    missing.setdefault(lib, []).append(os.path.relpath(p, root))
    return missing


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    root = argv[1]
    fix = argv[3:] if len(argv) > 2 and argv[2] == "--fix" else []
    for _ in range(10):
        missing = scan(root)
        if not missing or not fix:
            break
        copied = 0
        for lib in sorted(missing):
            src = next((os.path.join(d, lib) for d in fix if os.path.isfile(os.path.join(d, lib))), None)
            if src:
                dst = os.path.join(root, "system", "lib64", lib)
                shutil.copy2(src, dst)
                print("added %s (needed by %s) from %s" % (lib, ", ".join(missing[lib][:3]), src))
                copied += 1
        if not copied:
            break
    for lib in sorted(missing):
        print("MISSING %s <- %s" % (lib, ", ".join(missing[lib][:5])))
    print("ramdisk library check: %d missing" % len(missing))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
