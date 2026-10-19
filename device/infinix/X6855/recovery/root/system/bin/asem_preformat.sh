#!/system/bin/sh
# ASEM Recovery - makes Format Data work on the X6855 (Virtual A/B + decryption).
# Called by TWRP's Check_Pending_Merges() (patched in build.sh), which Format Data runs first:
#   asem_preformat.sh pre     before TWRP unmaps the dynamic partitions:
#                             - stop the TEE services that decryption started (they run from
#                               /vendor and keep it busy -> "Unable to unmap dynamic partitions")
#                             - unmount every mount of a logical partition (/vendor + its binds)
#                             - mount /metadata if needed (the snapshot code reads /metadata/ota)
#   asem_preformat.sh unmap   after TWRP unmapped the partitions in its fstab: unmap the rest
#                             (the 8 tr_* partitions ...). Otherwise libsnapshot's
#                             HandleImminentDataWipe() cannot map all of super fresh
#                             -> "Unable to check merge status" and Format Data stops.
# Only stops services, unmounts and unmaps. Never writes to any partition.
say() { echo "asem_preformat: $1"; }

case "$1" in
pre)
    for s in keystore2 vendor.gatekeeper-default vendor.keymint-trustonic tee-service mobicore; do
        [ "$(getprop init.svc.$s)" = running ] && { setprop ctl.stop $s; say "stopped $s"; }
    done
    n=0
    while [ $n -lt 20 ] && [ "$(getprop init.svc.mobicore)" = running ]; do sleep 0.25; n=$((n+1)); done
    for d in /dev/block/mapper/*_a /dev/block/mapper/*_b; do
        [ -e "$d" ] || continue
        real=$(readlink -f "$d")
        for m in $(grep -E "^($d|$real) " /proc/mounts | cut -d' ' -f2 | sort -r); do
            umount "$m" 2>/dev/null && say "unmounted $m" || say "could not unmount $m"
        done
    done
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
        if grep -qE "^($d|$real) " /proc/mounts; then say "$n is still mounted - left mapped"; continue; fi
        lptools unmap "$n" >/dev/null 2>&1 && say "unmapped $n" || say "could not unmap $n"
    done
    ;;
*)
    echo "usage: asem_preformat.sh pre|unmap"; exit 2;;
esac
exit 0
