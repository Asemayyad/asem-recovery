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

## The ASEM theme (theme/)

Built in from the first build (no plain-TWRP stage):

- `theme/apply_theme.py` - applies the theme to the synced TWRP tree; `--check`
  validates every XML file, image, font, page link and string before compiling.
- `theme/tools/make_images.py` - draws all theme images (dark `_d` / light `_l`)
  from `tools/icon_sheet.png` (rendered from `tools/icons.html`) and the logo.
- `theme/tools/arabic.py` - joins Arabic letters and orders text right-to-left
  (TWRP cannot do this itself). Font: Tajawal (OFL), English + Arabic.
- `theme/tools/preview.py` - draws the generated pages on a PC at 1080x2337;
  results in `design/build_preview/`.
- Light theme: `ui_light.xml` + a 2-line patch in gui/pages.cpp and gui/gui.cpp.
- `TW_NO_REBOOT_RECOVERY := true`: no software reboot-to-recovery anywhere.

Licence: TWRP is GPLv3. Keeping this private is fine; when ASEM Recovery builds
are shared publicly, this source must be published with them.

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

**Test safety rules (so no data is lost):** while testing, do NOT use "Mount system as
read/write" (erofs cannot be written; may show errors), do NOT Format Data, do NOT wipe
anything. Mounting / unmounting partitions is safe. Enter a new build by hand (power off,
Power + Volume Up), not with `adb reboot recovery`, until it is proven to start.

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
| Reboot to: System / Bootloader / Fastbootd / Power off | |
| Reboot to: Recovery - DISABLED in the UI (shown as instructions: power off, hold Power + Volume Up). The Rescue Toolbox avoids software "reboot recovery" on this phone; only re-enable after a controlled test with backups ready. | |
| USB OTG | |
| Decryption (R3) | |

## Known risks and plan B (from comparing with OrangeFox X6855, Andrikurn, fox_14.1)

- **Slot switching:** that tree builds its own MediaTek boot-control HAL from
  source (ufs-bsg + boot region control) instead of using the stock one, which
  suggests the stock Android 16 HAL may not run under android-14.1. If the R1
  test fails, port that approach (credit the author).
- **Vibration / battery:** that tree patches TWRP for the LED-class vibrator
  (`/sys/class/leds/vibrator`) and the health HAL. R2.
- **USB:** that tree ships its own `init.recovery.usb.rc`. If ADB/MTP do not come
  up with the stock `init.recovery.mt6789.rc`, add one.
- **Decryption:** that tree carries the Trustonic TEE files (`mcRegistry`,
  `init.tee.rc`) - reference for R3.

## Roadmap

- R1 - plain TWRP base, all checklist items working.
- R2 - ASEM look, as in `design/asem_recovery_mockup.png` (v2, 15 screens):
  - Asem's logo (`design/assets/asem_logo*.png`) on splash and top bar.
  - Dark and light theme; every tile/option has a hint line; every screen has a
    one-line description and a "?" help sheet.
  - Settings: language English / Arabic, clock 12-hour (default) / 24-hour
    (TWRP built-in `tw_military_time`), theme, brightness, vibration, timeout.
  - Home "Reboot to..." chooser: System (green), Bootloader, Fastbootd, Power off.
    Shown as instructions only (greyed out, lock icon, no button action):
    - Recovery: power off, hold Power + Volume Up until the logo appears.
      Software "reboot recovery" stays disabled until tested safely.
    - BROM / EDL: one card for both chip families; its text and behaviour come
      from the device config. MediaTek (this phone): BROM cannot be entered from
      software - power off, hold Vol Up + Vol Down, plug in USB. Qualcomm
      (future): EDL - a real "reboot edl" button only on devices that allow it,
      otherwise instructions (key combo / test point).

## Long-term goal: universal ASEM Recovery

ASEM Recovery is meant to become universal (other MediaTek phones, later
Snapdragon). Rule for all work: keep the ASEM theme, texts, translations and
features device-independent; put everything phone-specific (partitions, offsets,
backlight path, slot HAL, BROM-vs-EDL card, which reboot targets are allowed)
in the device tree / a per-device config. X6855 is the first device.
  - Arabic: TWRP's text renderer does not join Arabic letters or do right-to-left
    by itself. Plan: ship a font with Arabic (e.g. Noto Sans Arabic) and convert
    the Arabic language file to pre-joined letter forms in visual order with a
    small script at build time; the layout XML gets a mirrored RTL variant.
  - "ASEM Transfer": an MTP storage in RAM so the PC can copy a ROM even when
    /data is encrypted or wiped.
- R3 - decryption (stock Trustonic KeyMint/Gatekeeper/mcDriverDaemon in recovery).
