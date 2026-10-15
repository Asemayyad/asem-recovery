#
# ASEM Recovery - X6855
#

LOCAL_PATH := $(call my-dir)

ifeq ($(TARGET_DEVICE),X6855)
include $(call all-subdir-makefiles,$(LOCAL_PATH))
endif
