#
# ASEM Recovery - X6855
#

LOCAL_PATH := device/infinix/X6855

# Virtual A/B with compression (stock: VABC, userspace snapshots) - brings snapuserd
$(call inherit-product, $(SRC_TARGET_DIR)/product/virtual_ab_ota/vabc_features.mk)

# Dynamic partitions
PRODUCT_USE_DYNAMIC_PARTITIONS := true

# Fastbootd
PRODUCT_PACKAGES += \
    android.hardware.fastboot-service.example_recovery \
    fastbootd

# Boot control (A/B slot switching):
# No boot HAL is built here on purpose. The stock vendor_boot platform ramdisk
# (kept as-is and loaded in recovery mode too) already contains the MediaTek one:
#   /system/bin/hw/android.hardware.boot-service.mtk_recovery
#   /system/etc/init/android.hardware.boot-service.mtk_recovery.rc
# R1 test: does "Reboot > Slot A/B" work? If the stock Android 16 binary fails
# against the android-14.1 libraries, plan B is to ship it with its own libs.

# Soong namespaces
PRODUCT_SOONG_NAMESPACES += \
    $(LOCAL_PATH)

# Decryption (ASEM_DECRYPT=true builds only): stock Trustonic TEE / KeyMint / Gatekeeper
# run from the phone's own vendor partition (read-only) - see decrypt/*.
ifeq ($(ASEM_DECRYPT),true)
PRODUCT_COPY_FILES += \
    $(LOCAL_PATH)/decrypt/init.recovery.asem_decrypt.rc:$(TARGET_COPY_OUT_RECOVERY)/root/init.recovery.asem_decrypt.rc \
    $(LOCAL_PATH)/decrypt/asem_decrypt_setup.sh:$(TARGET_COPY_OUT_RECOVERY)/root/system/bin/asem_decrypt_setup.sh \
    $(LOCAL_PATH)/decrypt/prebuilt/libasem_shim.so:$(TARGET_COPY_OUT_RECOVERY)/root/system/lib64/libasem_shim.so \
    $(LOCAL_PATH)/decrypt/asem_decrypt.xml:$(TARGET_COPY_OUT_RECOVERY)/root/vendor/etc/vintf/manifest/asem_decrypt.xml
endif
