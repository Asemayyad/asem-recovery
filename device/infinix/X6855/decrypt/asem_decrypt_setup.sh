#!/system/bin/sh
# ASEM Recovery - decryption set-up (only in ASEM_DECRYPT builds).
# Makes the phone's OWN vendor files available to the stock Trustonic TEE / KeyMint /
# Gatekeeper services, READ-ONLY:
#   real vendor partition  -> /mnt/asem_vendor (erofs, ro)
#   its bin, lib64, app (55 MB of TEE apps, too big for vendor_boot), firmware
#                          -> bind-mounted at /vendor/<dir>, so every stock path works
#   /vendor/etc stays the recovery's own (asem_decrypt.xml declares the HALs)
#   persist (TEE registry) -> /mnt/vendor/persist, ro + noload (no journal replay),
#                             only mcRegistry/failure_records.dat gets a RAM copy (below)
# Nothing is written to any partition.
log() { /system/bin/log -t asem_decrypt "$1"; echo "asem_decrypt: $1" >> /tmp/recovery.log; }

SLOT=$(getprop ro.boot.slot_suffix)
DEV=/dev/block/mapper/vendor$SLOT
i=0
while [ ! -e "$DEV" ] && [ $i -lt 120 ]; do sleep 0.5; i=$((i + 1)); done
[ -e "$DEV" ] || { log "vendor$SLOT never mapped - decryption services not started"; exit 1; }

mkdir -p /mnt/asem_vendor
grep -q " /mnt/asem_vendor " /proc/mounts || mount -t erofs -o ro "$DEV" /mnt/asem_vendor \
    || { log "cannot mount vendor$SLOT read-only"; exit 1; }
for d in bin lib64 app firmware; do
    [ -d /mnt/asem_vendor/$d ] || continue
    mkdir -p /vendor/$d
    grep -q " /vendor/$d " /proc/mounts || mount -o bind,ro /mnt/asem_vendor/$d /vendor/$d
done
mkdir -p /mnt/vendor/persist /data/vendor/mcRegistry
grep -q " /mnt/vendor/persist " /proc/mounts \
    || mount -t ext4 -o ro,noload /dev/block/by-name/persist /mnt/vendor/persist \
    || log "persist not mounted (TEE may still work)"
# GateKeeper writes its wrong-PIN counter backup to mcRegistry/failure_records.dat after
# EVERY verify; on the read-only persist that write fails and the HAL returns an error
# reply although the PIN was right (TWRP: "Begin Operation failed", found 2026-10-17).
# Give it a RAM copy of just that one file. Store_1.tf (TEE secure storage) stays
# read-only on purpose: a RAM copy of it could look like a rollback to the TEE later.
FR=/mnt/vendor/persist/mcRegistry/failure_records.dat
if [ -f "$FR" ] && ! grep -q " $FR " /proc/mounts; then
    cp -p "$FR" /tmp/asem_failure_records.dat \
        && mount --bind /tmp/asem_failure_records.dat "$FR" \
        || log "failure_records.dat RAM copy failed - PIN unlock may fail"
fi

log "vendor$SLOT mounted read-only, starting TEE services"
setprop asem.decrypt.vendor 1
