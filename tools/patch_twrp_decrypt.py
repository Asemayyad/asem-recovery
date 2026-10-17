#!/usr/bin/env python3
"""Makefile fixes for TWRP 14.1 decryption builds (ASEM_DECRYPT=true).

    patch_twrp_decrypt.py <twrp_source_root>

Taken from open TWRP Gerrit changes (not merged upstream yet):
  7957 "recovery: support AIDL GateKeeper 2/2" - link + ship the AIDL GateKeeper
       library. This phone's GateKeeper is AIDL only (IGatekeeper/default); vold 14.1
       only spoke HIDL 1.0, so PIN/pattern/password unlock could never work.
       (Its vold half, 7920, is tools/patches/gerrit_7920_vold_aidl_gatekeeper.patch.)
  8745 (link part only) - libvold, linked statically into libtar and recovery, needs
       libasync_safe, libsysutils and libboot_control_client (#23 failed: undefined
       NetlinkEvent / async_safe_format_log / BootControlClient in libtar.so).
       8745's partition.cpp part is NOT used: it drops Decrypt_DE and the lock-type
       detection, which would break PIN/pattern unlock.
Stops with an error if any anchor line is missing or not unique.
"""
import os
import sys

MARK = "android.hardware.gatekeeper-V1-ndk"


def edit(path, pairs):
    s = open(path).read()
    if MARK in s:
        print("already patched:", path)
        return
    for old, new in pairs:
        if s.count(old) != 1:
            sys.exit("!! %s: expected exactly 1 of %r, found %d" % (path, old, s.count(old)))
        s = s.replace(old, new)
    open(path, "w").write(s)
    print("patched:", path)


def main(root):
    rec = os.path.join(root, "bootable", "recovery")
    gk = "        android.hardware.gatekeeper@1.0 \\\n"
    edit(os.path.join(rec, "libtar", "Android.mk"), [
        ("LOCAL_STATIC_LIBRARIES += libvold libscrypt_static\n",
         "LOCAL_STATIC_LIBRARIES += libvold libscrypt_static libasync_safe\n"),
        (gk, "        lib_android_keymaster_keymint_utils \\\n"
             "        android.hardware.gatekeeper-V1-ndk \\\n" + gk +
             "        libsysutils \\\n"
             "        libboot_control_client \\\n"),
    ])
    edit(os.path.join(rec, "Android.mk"), [
        (gk, "        lib_android_keymaster_keymint_utils \\\n"
             "        android.hardware.gatekeeper-V1-ndk \\\n" + gk),
        ("                          libboot_control_client \\\n",
         "                          libboot_control_client \\\n"
         "                          libsysutils \\\n"),
    ])
    so = "RECOVERY_LIBRARY_SOURCE_FILES += $(TARGET_OUT_SHARED_LIBRARIES)/android.hardware.gatekeeper@1.0.so\n"
    p = os.path.join(rec, "prebuilt", "Android.mk")
    s = open(p).read()
    i = s.find(so)
    if i < 0 or s.count(so) != 1:
        sys.exit("!! %s: gatekeeper@1.0.so line not found once" % p)
    indent = s[s.rfind("\n", 0, i) + 1:i]
    edit(p, [(indent + so, indent + so.replace("android.hardware.gatekeeper@1.0.so",
                                                "android.hardware.gatekeeper-V1-ndk.so") + indent + so)])

    # vold (after Gerrit 7920): the AIDL verify() result was never checked. When the HAL
    # call failed, rsp kept its defaults (statusCode 0 = STATUS_OK, empty token), TWRP
    # printed "GateKeeper status ok", skipped addAuthToken and failed later with the
    # misleading "Begin Operation failed". Stop there and print the real error.
    # vold Keystore(): AServiceManager_waitForService(keystore2) waits FOREVER. When the
    # TEE services cannot start, keystore2 crash-loops and TWRP freezes on the splash
    # screen (seen 2026-10-17, R3 run #25). Wait at most 60 s, then fail cleanly: every
    # caller already handles "no keystore" (if (!keystore) return false).
    p = os.path.join(root, "system", "vold", "Keystore.cpp")
    s = open(p).read()
    if "ASEM: bounded keystore2 wait" in s:
        print("already patched:", p)
    else:
        old = "    ::ndk::SpAIBinder binder(AServiceManager_waitForService(keystore2_service_name));\n"
        new = ("    // ASEM: bounded keystore2 wait (60 s) instead of waiting forever\n"
               "    ::ndk::SpAIBinder binder;\n"
               "    for (int i = 0; i < 120 && binder.get() == nullptr; i++) {\n"
               "        binder = ::ndk::SpAIBinder(AServiceManager_checkService(keystore2_service_name));\n"
               "        if (binder.get() == nullptr) usleep(500 * 1000);\n"
               "    }\n")
        inc_old = "#include \"Keystore.h\"\n"
        if s.count(old) != 1 or s.count(inc_old) != 1:
            sys.exit("!! %s: keystore2 wait / include not found once" % p)
        s = s.replace(old, new).replace(inc_old, inc_old + "\n#include <unistd.h>\n")
        open(p, "w").write(s)
        print("patched:", p)

    p = os.path.join(root, "system", "vold", "Decrypt.cpp")
    s = open(p).read()
    mark = "GateKeeper verify call failed"
    if mark in s:
        print("already patched:", p)
        return
    old = ("\t\t\t\tauto result = aidl_gk_device->verify(fakeUid(user_id), 0 /* challenge */, "
           "pwd_handle_hidl, gk_pwd_token_hidl, &rsp);\n\t\t\t\tfree(gk_pwd_token);\n")
    if s.count(old) != 1:
        sys.exit("!! %s: AIDL verify call not found once (Gerrit 7920 not applied?)" % p)
    s = s.replace(old, old + "\t\t\t\tif (!result.isOk()) {\n"
                  "\t\t\t\t\tprintf(\"" + mark + ": %s\\n\", result.getDescription().c_str());\n"
                  "\t\t\t\t\treturn Free_Return(retval, weaver_key, &pwd);\n\t\t\t\t}\n")
    open(p, "w").write(s)
    print("patched:", p)


if __name__ == "__main__":
    main(sys.argv[1])
