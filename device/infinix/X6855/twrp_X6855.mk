#
# ASEM Recovery - X6855
#

# Inherit from those products. Most specific first.
$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit_only.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/base.mk)

# Inherit some common TWRP stuff.
$(call inherit-product, vendor/twrp/config/common.mk)

# Inherit from device
$(call inherit-product, device/infinix/X6855/device.mk)

PRODUCT_DEVICE := X6855
PRODUCT_NAME := twrp_X6855
PRODUCT_BRAND := Infinix
PRODUCT_MODEL := Infinix X6855
PRODUCT_MANUFACTURER := INFINIX
PRODUCT_RELEASE_NAME := Infinix NOTE 50 Pro 4G

PRODUCT_GMS_CLIENTID_BASE := android-transsion
