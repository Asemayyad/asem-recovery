#!/usr/bin/env python3
"""ASEM vendor_boot tool for the Infinix X6855 (vendor_boot header v4).

On this phone the STOCK vendor_boot main ramdisk ("ramdisk0") also carries the
generic ramdisk (first-stage init). Normal boot depends on it, so ASEM Recovery
never rebuilds it: we keep the stock image and only swap the "recovery"
ramdisk fragment.

  info     <vendor_boot.img>
  extract  <vendor_boot.img> <name> <out_file>        dump one ramdisk fragment
  replace  <stock_vendor_boot.img> <recovery> <out.img>
           <recovery> = a ramdisk file, or a vendor_boot.img built by TWRP
           (its "recovery" fragment is taken)

Standard library only.
"""
import struct
import sys

MAGIC = b"VNDRBOOT"
HDR_FMT = "<8s5I2048sI16s2IQ4I"   # vendor_boot v4 header, 2128 bytes
ENTRY_FMT = "<3I32s64s"           # size, offset, type, name, board_id[16]
PARTITION_SIZE = 67108864         # vendor_boot_a/b on X6855
TYPES = {0: "none", 1: "platform", 2: "recovery", 3: "dlkm"}


def pad(n, page):
    return (n + page - 1) // page * page


def parse(data):
    if data[:8] != MAGIC:
        sys.exit("not a vendor_boot image")
    h = struct.unpack_from(HDR_FMT, data, 0)
    hdr = dict(zip(("magic", "version", "page", "kernel_addr", "ramdisk_addr", "vr_size",
                    "cmdline", "tags_addr", "name", "header_size", "dtb_size", "dtb_addr",
                    "table_size", "entry_num", "entry_size", "bootconfig_size"), h))
    if hdr["version"] != 4:
        sys.exit(f"vendor_boot header v{hdr['version']} not supported (need v4)")
    page = hdr["page"]
    off = pad(hdr["header_size"], page)
    vr = data[off:off + hdr["vr_size"]]
    off += pad(hdr["vr_size"], page)
    dtb = data[off:off + hdr["dtb_size"]]
    off += pad(hdr["dtb_size"], page)
    table = data[off:off + hdr["table_size"]]
    off += pad(hdr["table_size"], page)
    bootconfig = data[off:off + hdr["bootconfig_size"]]
    off += pad(hdr["bootconfig_size"], page)
    entries = []
    for i in range(hdr["entry_num"]):
        size, offset, rtype, name, board = struct.unpack_from(ENTRY_FMT, table, i * hdr["entry_size"])
        entries.append({"name": name.split(b"\0", 1)[0].decode(), "type": rtype,
                        "board": board, "data": vr[offset:offset + size]})
    return hdr, entries, dtb, bootconfig, off


def build(hdr, entries, dtb, bootconfig):
    page = hdr["page"]
    vr, table = b"", b""
    for e in entries:
        table += struct.pack(ENTRY_FMT, len(e["data"]), len(vr), e["type"],
                             e["name"].encode().ljust(32, b"\0"), e["board"])
        vr += e["data"]
    head = struct.pack(HDR_FMT, MAGIC, hdr["version"], page, hdr["kernel_addr"],
                       hdr["ramdisk_addr"], len(vr), hdr["cmdline"], hdr["tags_addr"],
                       hdr["name"], hdr["header_size"], len(dtb), hdr["dtb_addr"],
                       len(table), len(entries), struct.calcsize(ENTRY_FMT), len(bootconfig))
    out = b""
    for blob in (head, vr, dtb, table, bootconfig):
        out += blob + b"\0" * (pad(len(blob), page) - len(blob))
    return out


def find(entries, name):
    for e in entries:
        if e["name"] == name:
            return e
    sys.exit(f"no ramdisk fragment named '{name}' (have: {[e['name'] for e in entries]})")


def main(argv):
    if len(argv) < 2:
        sys.exit(__doc__)
    cmd = argv[1]
    if cmd == "info" and len(argv) == 3:
        hdr, entries, dtb, bc, end = parse(open(argv[2], "rb").read())
        print(f"header v{hdr['version']} page {hdr['page']} cmdline "
              f"'{hdr['cmdline'].split(b'\0', 1)[0].decode()}' dtb {len(dtb)} bytes, image data ends at {end}")
        for e in entries:
            print(f"  ramdisk '{e['name']}' type {TYPES.get(e['type'], e['type'])} {len(e['data'])} bytes")
        print("  bootconfig: " + bc.decode(errors="replace").replace("\n", " | "))
    elif cmd == "extract" and len(argv) == 5:
        _, entries, _, _, _ = parse(open(argv[2], "rb").read())
        open(argv[4], "wb").write(find(entries, argv[3])["data"])
    elif cmd == "replace" and len(argv) == 5:
        hdr, entries, dtb, bc, _ = parse(open(argv[2], "rb").read())
        new = open(argv[3], "rb").read()
        if new[:8] == MAGIC:
            new = find(parse(new)[1], "recovery")["data"]
        rec = find(entries, "recovery")
        if rec["type"] != 2:
            sys.exit("stock 'recovery' fragment is not type recovery - refusing")
        rec["data"] = new
        out = build(hdr, entries, dtb, bc)
        if len(out) > PARTITION_SIZE:
            sys.exit(f"result {len(out)} bytes does not fit vendor_boot ({PARTITION_SIZE})")
        open(argv[4], "wb").write(out)
        print(f"wrote {argv[4]}: {len(out)} bytes ({PARTITION_SIZE - len(out)} bytes free), "
              f"platform ramdisk kept byte-identical")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
