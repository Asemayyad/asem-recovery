#!/system/bin/sh
# ASEM Recovery - releases the dynamic partitions (X6855: Virtual A/B + decryption).
# Decryption starts TEE services (keystore2, gatekeeper, keymint, tee-service, mobicore) that run
# from /vendor and keep vendor_b mounted 6 times (/mnt/asem_vendor, /vendor + binds). While that is
# so, nothing can unmap / remap the dynamic partitions: Format Data fails ("Unable to unmap dynamic
# partitions") and zips that write logical partitions fail ("could not map vendor_b writable").
#
#   asem_preformat.sh install   before every zip install (Install + ADB Sideload; hooked in
#                               twinstall.cpp by build.sh): stop the TEE services, unmount every
#                               mount of a dynamic partition. /data stays mounted and unlocked.
#   asem_preformat.sh pre       Format Data (Check_Pending_Merges, hooked by build.sh): the same,
#                               plus unmount /data (+ /data/user/0 ...), delete the decryption
#                               mapping, and mount /metadata (the snapshot code reads /metadata/ota)
#   asem_preformat.sh unmap     Format Data, after TWRP unmapped the partitions in its fstab:
#                               unmap the rest (the 8 tr_* ...) so libsnapshot's
#                               HandleImminentDataWipe() can map all of super fresh
# Only stops services, unmounts and unmaps. Never writes to any partition.
say() { echo "asem_preformat: $1"; }

release() {
    for s in keystore2 vendor.gatekeeper-default vendor.keymint-trustonic tee-service mobicore; do
        [ "$(getprop init.svc.$s)" = running ] && { setprop ctl.stop $s; say "stopped $s"; }
    done
    n=0
    while [ $n -lt 20 ] && [ "$(getprop init.svc.mobicore)" = running ]; do sleep 0.25; n=$((n+1)); done
    for d in /dev/block/mapper/*_a /dev/block/mapper/*_b; do
        [ -e "$d" ] || continue
        real=$(readlink -f "$d")
        for m in $(grep -e "^$d " -e "^$real " /proc/mounts | cut -d' ' -f2 | sort -r); do
            umount "$m" 2>/dev/null && say "unmounted $m" || say "could not unmount $m"
        done
    done
}

# Format Data after decryption (found on R5, 2026-10-23):
#  1. the data device is also mounted at /data/user/0 (maybe /sdcard ...): umount /data fails
#     "Device or resource busy" -> unmount those extra mounts (deepest first), then /data
#  2. the decryption device-mapper node "userdata" (dm-default-key) still sits on the partition:
#     mke2fs / make_f2fs refuse it ("apparently in use by the system") -> delete the node
#     (lptools unmap = delete the dm device by name only, the partition table is not touched)
#  3. TWRP still formats the decrypted device path /dev/block/mapper/userdata; without the node it
#     stops "Block device not present, cannot format Data" -> put a link there to the partition
#     itself, so mke2fs / make_f2fs format the plain partition (tested by hand 2026-10-24: OK)
release_data() {
    dev=$(grep " /data " /proc/mounts | head -1 | cut -d' ' -f1)
    if [ -n "$dev" ]; then
        for m in $(grep "^$dev " /proc/mounts | cut -d' ' -f2 | sort -r); do
            umount "$m" 2>/dev/null && say "unmounted $m" || say "could not unmount $m"
        done
    fi
    if [ -e /dev/block/mapper/userdata ] && ! grep -q " /data " /proc/mounts; then
        lptools unmap userdata >/dev/null 2>&1 && say "removed the decryption mapping (userdata)" \
            || say "could not remove the decryption mapping (userdata)"
    fi
    raw=$(readlink -f /dev/block/by-name/userdata)
    if [ ! -e /dev/block/mapper/userdata ] && [ -b "$raw" ]; then
        ln -s "$raw" /dev/block/mapper/userdata && say "userdata -> $raw (format the partition itself)" \
            || say "could not link userdata to $raw"
    fi
}

case "$1" in
install)
    release
    ;;
pre)
    release
    release_data
    if ! grep -q " /metadata " /proc/mounts; then
        mkdir -p /metadata
        mount -t ext4 -o rw,noatime,nosuid,nodev,discard /dev/block/by-name/metadata /metadata \
            && say "mounted /metadata" || say "could not mount /metadata"
    fi
    ;;
unmap)
    for d in /dev/block/mapper/*_a /dev/block/mapper/*_b; do
        [ -e "$d" ] || continue
        n=${d##*/}
        real=$(readlink -f "$d")
        if grep -q -e "^$d " -e "^$real " /proc/mounts; then say "$n is still mounted - left mapped"; continue; fi
        lptools unmap "$n" >/dev/null 2>&1 && say "unmapped $n" || say "could not unmap $n"
    done
    ;;
*)
    echo "usage: asem_preformat.sh install|pre|unmap"; exit 2;;
esac
exit 0
