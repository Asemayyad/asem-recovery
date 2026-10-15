#
# ASEM Recovery - Infinix NOTE 50 Pro 4G (X6855), MT6789
# Base: TWRP android-14.1 (minimal-manifest-twrp, branch twrp-14.1) - the newest TWRP
# base; Android 15/16 MediaTek devices use it with the version spoof below.
# Target phone firmware: XOS 16.3.0.155SP15, Android 16, kernel 6.12 GKI.
#
# All device values are measured on the phone (see X6855_device_tree\3_live_info).
#

DEVICE_PATH := device/infinix/X6855

# Feature switches (override on the command line, e.g. ASEM_DECRYPT=true)
ASEM_DECRYPT ?= false

# Build
ALLOW_MISSING_DEPENDENCIES := true
BUILD_BROKEN_DUP_RULES := true
BUILD_BROKEN_ELF_PREBUILT_PRODUCT_COPY_FILES := true

# Architecture - 64-bit only, 2x Cortex-A76 + 6x Cortex-A55
TARGET_ARCH := arm64
TARGET_ARCH_VARIANT := armv8-2a-dotprod
TARGET_CPU_ABI := arm64-v8a
TARGET_CPU_VARIANT := generic
TARGET_CPU_VARIANT_RUNTIME := cortex-a76
TARGET_SUPPORTS_64_BIT_APPS := true
TARGET_IS_64_BIT := true

# Platform
TARGET_BOARD_PLATFORM := mt6789
TARGET_BOOTLOADER_BOARD_NAME := mt6789
TARGET_NO_BOOTLOADER := true
TARGET_USES_UEFI := false
BOARD_HAS_MTK_HARDWARE := true

# A/B + Virtual A/B
AB_OTA_UPDATER := true
AB_OTA_PARTITIONS += \
    boot \
    vendor_boot \
    dtbo \
    vbmeta \
    vbmeta_system \
    vbmeta_vendor \
    system \
    system_ext \
    product \
    vendor \
    odm \
    vendor_dlkm \
    odm_dlkm \
    system_dlkm
BOARD_USES_RECOVERY_AS_BOOT := false
TW_INCLUDE_REPACKTOOLS := true

# Kernel - stock prebuilt (only used to satisfy the vendor_boot build;
# the image we flash is the STOCK vendor_boot with a new recovery fragment)
BOARD_BOOT_HEADER_VERSION := 4
BOARD_KERNEL_BASE := 0x3fff8000
BOARD_KERNEL_PAGESIZE := 4096
BOARD_KERNEL_OFFSET := 0x00008000
BOARD_RAMDISK_OFFSET := 0x26f08000
BOARD_KERNEL_TAGS_OFFSET := 0x07c88000
BOARD_DTB_OFFSET := 0x07c88000
BOARD_VENDOR_CMDLINE := bootopt=64S3,32N2,64N2
BOARD_BOOTCONFIG := \
    kernel.rcu_nocbs=all \
    kernel.rcutree.enable_rcu_lazy=1 \
    kernel.rcupdate.rcu_cpu_stall_cputime=1
BOARD_MKBOOTIMG_ARGS += --header_version $(BOARD_BOOT_HEADER_VERSION)
BOARD_MKBOOTIMG_ARGS += --kernel_offset $(BOARD_KERNEL_OFFSET)
BOARD_MKBOOTIMG_ARGS += --ramdisk_offset $(BOARD_RAMDISK_OFFSET)
BOARD_MKBOOTIMG_ARGS += --tags_offset $(BOARD_KERNEL_TAGS_OFFSET)
BOARD_MKBOOTIMG_ARGS += --dtb_offset $(BOARD_DTB_OFFSET)
TARGET_PREBUILT_KERNEL := $(DEVICE_PATH)/prebuilt/kernel
BOARD_INCLUDE_DTB_IN_BOOTIMG := true
BOARD_PREBUILT_DTBIMAGE_DIR := $(DEVICE_PATH)/prebuilt/dtb
BOARD_KERNEL_IMAGE_NAME := Image.lz4
BOARD_RAMDISK_USE_LZ4 := true
BOARD_USES_GENERIC_KERNEL_IMAGE := true

# Kernel modules: NOT packed here. The stock vendor_boot platform ramdisk (kept
# byte-identical) has all 249 modules + modules.load.recovery (239), and
# first-stage init loads them in recovery mode (touch, display, USB, UFS ...).

# Recovery lives in vendor_boot (stock: fragment "recovery", type 2)
TARGET_NO_RECOVERY := true
BOARD_MOVE_RECOVERY_RESOURCES_TO_VENDOR_BOOT := true
BOARD_INCLUDE_RECOVERY_RAMDISK_IN_VENDOR_BOOT := true
BOARD_EXCLUDE_KERNEL_FROM_RECOVERY_IMAGE := true

# Partitions (bytes, measured)
BOARD_FLASH_BLOCK_SIZE := 262144
BOARD_BOOTIMAGE_PARTITION_SIZE := 67108864
BOARD_VENDOR_BOOTIMAGE_PARTITION_SIZE := 67108864
BOARD_DTBOIMG_PARTITION_SIZE := 8388608
BOARD_SUPER_PARTITION_SIZE := 12803551232
BOARD_SUPER_PARTITION_GROUPS := main
BOARD_MAIN_SIZE := 12801454080
BOARD_MAIN_PARTITION_LIST := system system_ext product vendor odm vendor_dlkm odm_dlkm system_dlkm
BOARD_USES_METADATA_PARTITION := true
TARGET_USERIMAGES_USE_EXT4 := true
TARGET_USERIMAGES_USE_F2FS := true
TARGET_COPY_OUT_SYSTEM_EXT := system_ext
TARGET_COPY_OUT_PRODUCT := product
TARGET_COPY_OUT_VENDOR := vendor
TARGET_COPY_OUT_ODM := odm
TARGET_COPY_OUT_VENDOR_DLKM := vendor_dlkm
TARGET_COPY_OUT_ODM_DLKM := odm_dlkm
TARGET_COPY_OUT_SYSTEM_DLKM := system_dlkm

# Recovery fstab
TARGET_RECOVERY_FSTAB := $(DEVICE_PATH)/recovery.fstab
# MTK panels usually need BGRA_8888 (also used by the OrangeFox X6855 tree).
# If colours look swapped (blue/red), try RGBX_8888.
TARGET_RECOVERY_PIXEL_FORMAT := BGRA_8888

# Android 16 - version spoof so the Android 16 KeyMint (Trustonic) accepts the
# android-14.1 recovery (same approach as working Android 16 MediaTek TWRP trees)
PLATFORM_VERSION := 99.87.36
PLATFORM_VERSION_LAST_STABLE := $(PLATFORM_VERSION)
PLATFORM_SECURITY_PATCH := 2099-12-31
BOOT_SECURITY_PATCH := $(PLATFORM_SECURITY_PATCH)
VENDOR_SECURITY_PATCH := $(PLATFORM_SECURITY_PATCH)

# Decryption (R3). Stock: FBE v2 + metadata encryption, Trustonic Kinibi TEE.
# Needs the stock vendor KeyMint/Gatekeeper/mcDriverDaemon in the recovery ramdisk.
ifeq ($(ASEM_DECRYPT),true)
TW_INCLUDE_CRYPTO := true
TW_INCLUDE_CRYPTO_FBE := true
TW_INCLUDE_FBE_METADATA_DECRYPT := true
TW_USE_FSCRYPT_POLICY := 2
BOARD_USES_METADATA_PARTITION := true
endif

# ---------------- TWRP / ASEM ----------------
TW_DEVICE_VERSION := ASEM_R1
TW_THEME := portrait_hdpi
TW_FRAMERATE := 60
TW_DEFAULT_LANGUAGE := en
# ASEM ships only English + Arabic (its own font); the CJK extra fonts are ~16 MB.
TW_EXTRA_LANGUAGES := false

# No software "reboot to recovery" anywhere on this phone (the Rescue Toolbox
# avoids it too). ASEM shows the key combo instead: power off, Power + Volume Up.
TW_NO_REBOOT_RECOVERY := true

# Display 1080x2436, centre punch hole 99 px tall (from stock DisplayCutout)
TW_Y_OFFSET := 99
TW_H_OFFSET := -99
TW_STATUS_ICONS_ALIGN := center

# Backlight /sys/class/leds/lcd-backlight (max_brightness 5119; Android sat at 516)
TW_BRIGHTNESS_PATH := "/sys/class/leds/lcd-backlight/brightness"
TW_MAX_BRIGHTNESS := 5119
TW_DEFAULT_BRIGHTNESS := 1200
TW_NO_SCREEN_BLANK := true

# Tools
TW_USE_TOOLBOX := true
TW_INCLUDE_RESETPROP := true
TW_INCLUDE_LIBRESETPROP := true
TW_INCLUDE_LPDUMP := true
TW_INCLUDE_LPTOOLS := true
TW_INCLUDE_NTFS_3G := true
TW_INCLUDE_FUSE_NTFS := true
TW_INCLUDE_FUSE_EXFAT := true
TARGET_USES_MKE2FS := true
TW_EXCLUDE_APEX := true
TW_EXCLUDE_TWRPAPP := true

# Fastbootd (flash ROM images from the PC)
TW_INCLUDE_FASTBOOTD := true

# Storage / USB - MTP is on by default in TWRP (PC sees the phone);
# USB controller "musb-hdrc" is set by the stock init.recovery.mt6789.rc
RECOVERY_SDCARD_ON_DATA := true

# Logging
TWRP_INCLUDE_LOGCAT := true
TARGET_USES_LOGD := true
