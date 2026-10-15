# ASEM Recovery - Infinix NOTE 50 Pro 4G (X6855)

PRIVATE - not published. Based on TWRP (android-14.1); "based on TWRP" must stay
on the About screen (TWRP licence and community courtesy).

| | |
|---|---|
| Phone | Infinix NOTE 50 Pro 4G, X6855, MT6789, UFS, A/B + Virtual A/B |
| Firmware it is made for | XOS 16.3.0.155SP15, **Android 16**, kernel 6.12.38 GKI |
| Recovery base | TWRP android-14.1 (newest TWRP; Android 15/16 MTK devices use it) |
| Where it lives | the "recovery" ramdisk fragment inside `vendor_boot` |

## How it is built (and why it is safe for normal boot)

On this phone Transsion put the whole generic ramdisk (first-stage `init`, stock
recovery, adbd, fastbootd, the MTK boot-control HAL) into the **platform** ramdisk
of `vendor_boot`, and `init_boot` is empty. Normal boot uses only that platform
ramdisk; recovery mode loads platform + "recovery" fragment.

So ASEM Recovery does NOT rebuild vendor_boot. `build.sh` builds TWRP, takes only
its recovery ramdisk, and `tools/asem_vendor_boot.py` puts it into the **stock**
vendor_boot (`stock/`). The platform ramdisk, DTB, bootconfig and header stay
byte-identical (round-trip test: rebuilding stock gives a byte-identical image).

The stock image has an AVB hash footer; ours has none. With the unlocked
bootloader (state "orange") this is accepted, same as the Magisk-patched boot.

## Build

Linux x86_64, ~60-80 GB free, `repo`, Python 3, the usual AOSP build packages.

    ./build.sh                      # -> out/ASEM_Recovery_X6855_ASEM_R1.img
    ASEM_DECRYPT=true ./build.sh    # R3 experiment

## Flash (only when you are ready - it replaces the recovery on that slot)

Use the X6855 Rescue Toolbox, option 3 "Flash custom recovery" (it saves the
current vendor_boot first), or by hand in bootloader fastboot:

    fastboot flash vendor_boot_b ASEM_Recovery_X6855_ASEM_R1.img     (active slot)

Undo: Rescue Toolbox option 4 "vendor_boot only", or flash
`stock/vendor_boot-16.3.0.155SP15.img`. Bootloader fastboot does not depend on
vendor_boot, so this is always reachable (Power + Volume Down).
Enter recovery by hand: power off, hold Power + Volume Up.

## Android 16 notes

- `PLATFORM_VERSION 99.87.36` / `PLATFORM_SECURITY_PATCH 2099-12-31`: lets the
  Android 16 KeyMint accept the recovery (needed for decryption). Same as the
  Android 16 MediaTek TWRP trees with working decryption.
- Kernel modules are the stock Android 16 ones (loaded from the kept platform ramdisk).
- Data: f2fs + FBE v2 (`inlinecrypt_optimized`) + metadata encryption, from stock fstab.
- System partitions are erofs (read-only) - TWRP can mount, back up and flash them.
- Installing an **Android 16 ROM zip** uses TWRP's android-14.1 update engine. If a
  LineageOS 23 payload is too new for it, install the ROM from the PC through
  **fastbootd** (ASEM Recovery > Advanced > Fastboot) - that path is version-independent.

## R1 test checklist (fill in on the phone)

| Feature | Result |
|---|---|
| Boots to ASEM Recovery | |
| Normal boot still works after flashing | |
| Touch | |
| Display / brightness | |
| ADB (`adb devices` shows recovery) | |
| MTP (phone visible on PC) | |
| Fastbootd (`fastboot devices` in userspace) | |
| Flash image from file picker | |
| Mount / unmount system, vendor, data | |
| A/B slot switch (stock MTK boot HAL) | |
| Wipe cache / dalvik / data | |
| Backup boot / vendor_boot / nvram | |
| USB OTG | |
| Decryption (R3) | |

## Roadmap

- R1 - plain TWRP base, all checklist items working.
- R2 - ASEM look: logo + splash, dark and light theme, clock, new buttons;
  "ASEM Transfer": an MTP storage in RAM so the PC can copy a ROM even when /data
  is encrypted or wiped.
- R3 - decryption (stock Trustonic KeyMint/Gatekeeper/mcDriverDaemon in recovery).
