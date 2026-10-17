#!/usr/bin/env bash
#
# Build ASEM Recovery for the Infinix X6855 (Linux x86_64).
#
#   ./build.sh [work_dir]        default work_dir: ~/twrp-14.1
#   ASEM_DECRYPT=true ./build.sh  build with decryption (R3, experimental)
#
# Output: out/ASEM_Recovery_X6855_<version>.img  = STOCK vendor_boot with only the
# "recovery" ramdisk fragment replaced (normal-boot ramdisk stays byte-identical).
#
set -eo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
WORK=${1:-$HOME/twrp-14.1}
STOCK="$HERE/stock/vendor_boot-16.3.0.155SP15.img"
VERSION=$(sed -n 's/^TW_DEVICE_VERSION := //p' "$HERE/device/infinix/X6855/BoardConfig.mk")

echo "== checking stock vendor_boot"
(cd "$HERE/stock" && sha256sum -c SHA256SUMS.txt)
# Self-test the packing tool with this machine's Python now, not after a 2-hour build:
# stock recovery fragment -> repack -> must equal the stock image data byte for byte.
echo "== self-test: packing tool round trip on stock"
T=$(mktemp -d)
python3 "$HERE/tools/asem_vendor_boot.py" info "$STOCK"
python3 "$HERE/tools/asem_vendor_boot.py" extract "$STOCK" recovery "$T/rec.cpio"
python3 "$HERE/tools/asem_vendor_boot.py" replace "$STOCK" "$T/rec.cpio" "$T/rt.img"
cmp -n "$(stat -c %s "$T/rt.img")" "$T/rt.img" "$STOCK" && echo "   round trip byte-identical"
rm -rf "$T"

echo "== syncing TWRP android-14.1 into $WORK"
mkdir -p "$WORK"
cd "$WORK"
if [ ! -d .repo ]; then
    repo init --depth=1 -u https://github.com/minimal-manifest-twrp/platform_manifest_twrp_aosp.git -b twrp-14.1
fi
# Even the "minimal" twrp-14.1 tree is >45 GB with git objects + checkout, more than
# a free GitHub runner has. So: skip projects a recovery never uses, and sync in
# stages, deleting each stage's git objects right after checkout (the build does not
# need git history; bootable/recovery and vendor/twrp keep theirs).
mkdir -p .repo/local_manifests
cp "$HERE/device/asem-slim.xml" .repo/local_manifests/asem-slim.xml
SYNC="repo sync -c --no-clone-bundle --no-tags --optimized-fetch --prune --force-sync -j$(( $(nproc) * 4 ))"
BIG="prebuilts/clang/host/linux-x86 prebuilts/rust prebuilts/sdk prebuilts/tools prebuilts/gradle-plugin
     prebuilts/misc prebuilts/build-tools prebuilts/go/linux-x86 prebuilts/bazel/linux-x86_64
     prebuilts/jdk/jdk8 prebuilts/jdk/jdk11 prebuilts/jdk/jdk17 prebuilts/jdk/jdk21 prebuilts/vndk/v34
     prebuilts/clang-tools external/cronet external/skia external/llvm packages/modules/Bluetooth
     kernel/prebuilts/5.15/arm64 kernel/prebuilts/5.15/x86_64"
# Google's source server sometimes answers HTTP 503 - retry instead of failing the run
sync() {
    local i
    for i in 1 2 3 4; do
        $SYNC "$@" && return 0
        echo "   repo sync failed (try $i of 4) - cleaning the partial download, retrying in $((i * 60)) s"
        # A broken fetch leaves its half-downloaded pack behind (#16: clang, several GB),
        # and the retry then ran out of disk. Remove temporary packs; in stage 2 (one big
        # project at a time) also drop that project's partial git objects.
        find .repo -type f \( -name 'tmp_pack_*' -o -name 'tmp_idx_*' -o -name 'incoming-*' \) -delete 2>/dev/null
        [ "${SYNC_STAGE:-1}" = 2 ] && drop_git_objects
        df -h --output=avail . | tail -1 | sed 's/^/   free now: /'
        sleep $((i * 60))
    done
    return 1
}
drop_git_objects() {
    find .repo/project-objects .repo/projects -mindepth 1 -maxdepth 8 -type d -name '*.git' -prune \
        ! -name 'android_bootable_recovery.git' ! -name 'android_vendor_twrp.git' \
        ! -path '*/bootable/recovery.git' ! -path '*/vendor/twrp.git' \
        -exec rm -rf {} + 2>/dev/null || true
}
disk() { echo "   [disk] $(df -h --output=used,avail . | tail -1 | awk '{print $1" used, "$2" free"}')"; }
ALL=$(repo list -a -p)
SMALL=$(printf '%s\n' $ALL | grep -vxF -f <(printf '%s\n' $BIG))
echo "   stage 1: $(echo "$SMALL" | wc -l) small projects"
sync $SMALL
drop_git_objects; disk
# Trim a just-synced prebuilt down to what a Linux build uses (sizes measured on a
# runner: clang 13 GB with 6 versions, rust 17 GB with 3 versions x 4 host OSes).
trim() {
    local p=$1 d v keep
    case $p in
    # Mac/Windows copies: only where no Android.bp names files inside them
    # (prebuilts/misc's license module does - removing its darwin dirs breaks soong)
    prebuilts/rust|prebuilts/jdk/*)
        find "$p" -mindepth 1 -maxdepth 2 -type d \( -name 'darwin-*' -o -name 'windows-*' \) -prune -exec rm -rf {} + ;;
    esac
    case $p in
    prebuilts/clang/host/linux-x86)
        keep=$(grep -rhoE 'clang-r[0-9]+[a-z]?' build/soong build/make 2>/dev/null | sort -u)
        echo "   clang versions named by the build: $(echo $keep)"
        for d in "$p"/clang-r*; do
            [ -d "$d" ] && [ ! -L "$d" ] || continue
            v=$(basename "$d")
            echo "$keep" | grep -qxF "$v" && continue
            readlink "$p"/* 2>/dev/null | grep -q "$v" && continue
            echo "   removing unused $v"; rm -rf "$d"
        done ;;
    prebuilts/rust)
        keep=$(sed -n 's/^\s*RustDefaultVersion\s*=\s*"\([^"]*\)".*/\1/p' build/soong/rust/config/global.go)
        echo "   rust version used by the build: $keep"
        [ -n "$keep" ] && [ -d "$p/linux-x86/$keep" ] || { echo "   (not found - rust left as is)"; return; }
        rm -rf "$p/linux-musl-x86"
        for d in "$p"/linux-x86/*; do
            v=$(basename "$d")
            [ "$v" = "$keep" ] || [ "$v" = stable ] || { echo "   removing unused rust $v"; rm -rf "$d"; }
        done ;;
    esac
}
SYNC_STAGE=2   # retries may now drop the failed project's partial objects
for p in $BIG; do
    printf '%s\n' $ALL | grep -qxF "$p" || continue
    echo "   stage 2: $p"
    sync "$p"
    drop_git_objects
    trim "$p"
    echo "   $(du -sh "$p" | cut -f1)  $p"; disk
done

echo "== applying the ASEM theme (validated before compiling)"
git -C bootable/recovery checkout -q -- .
git -C bootable/recovery clean -fdq
python3 "$HERE/theme/apply_theme.py" --check "$WORK"
# smooth sliders (partial redraw) + render timing log - see tools/patch_twrp_gui.py
# (re-enabled at Asem's request 2026-10-16; not compile-tested on the PC - no compiler)
python3 "$HERE/tools/patch_twrp_gui.py" "$WORK"
grep -q "// ASEM: partial slider redraw" bootable/recovery/gui/slider.cpp || { echo "!! slider patch did not apply"; exit 1; }
# TWRP 14.1 bug: twrp_ramdisk copies system/etc/task_profiles.json but requires it only
# with TW_INCLUDE_CRYPTO, so without crypto the copy can run before the file exists.
# Required modules are built first (main.mk add-required-deps), so add it there.
sed -i 's/^LOCAL_REQUIRED_MODULES += init_second_stage\.recovery /LOCAL_REQUIRED_MODULES += task_profiles.json init_second_stage.recovery /' \
    bootable/recovery/prebuilt/Android.mk
grep -q '^LOCAL_REQUIRED_MODULES += task_profiles.json init_second_stage.recovery' bootable/recovery/prebuilt/Android.mk \
    || { echo "!! task_profiles.json patch did not apply"; exit 1; }
# SELinux permissive in recovery. R1 ran Enforcing (TWRP's policy) and crash-looped on
# denials (black screen). Usual fix is androidboot.selinux=permissive on the cmdline, but
# here cmdline/bootconfig are shared with normal boot, so patch TWRP's init instead: that
# init only exists in the recovery fragment; normal boot keeps the stock one.
grep -q '// ASEM Recovery: always permissive' system/core/init/selinux.cpp || sed -i 's|^bool IsEnforcing() {$|bool IsEnforcing() {\n    return false;  // ASEM Recovery: always permissive (this init is recovery-only)|' \
    system/core/init/selinux.cpp
grep -q 'return false;  // ASEM Recovery: always permissive' system/core/init/selinux.cpp \
    || { echo "!! SELinux permissive patch did not apply"; exit 1; }
# Decryption builds: TWRP 14.1's Android.mk and libtar/Android.mk still name the old
# "-ndk_platform" security libraries, which Android 14 no longer generates (#21 failed:
# "android.security.apc-ndk_platform ... missing and no known rule"). TeamWin's own
# android-14.1 vold already uses the modern names - use the same ones here.
for mk in bootable/recovery/Android.mk bootable/recovery/libtar/Android.mk; do
    sed -i -e 's/android\.security\.apc-ndk_platform/android.security.apc-ndk/g' \
           -e 's/android\.security\.authorization-ndk_platform/android.security.authorization-ndk/g' \
           -e 's/android\.security\.maintenance-ndk_platform/android.security.maintenance-ndk/g' \
           -e 's/android\.system\.keystore2-V1-ndk_platform/android.system.keystore2-V4-ndk/g' "$mk"
done
! grep -n "ndk_platform" bootable/recovery/Android.mk bootable/recovery/libtar/Android.mk \
    || { echo "!! old -ndk_platform library names still present"; exit 1; }
# lptools "map" (used by ASEM Stock Restore to get a WRITABLE mapping of a logical
# partition) hard-codes LP metadata slot 0 = the _a layout. On this Virtual A/B phone
# running slot b, slot 0 has no *_b partitions, so map failed. Use the current slot's
# metadata, like fs_mgr does at boot.
python3 - external/lptools/lptools.cc <<'PYEOF'
import sys
p = sys.argv[1]; s = open(p).read()
mark = "// ASEM: current slot metadata"
if mark not in s:
    i = s.index('strcmp(argv[1], "map") == 0')
    j = s.index(".metadata_slot = 0,", i)
    s = s[:j] + ('.metadata_slot = SlotNumberForSlotSuffix(::android::base::GetProperty('
                 '"ro.boot.slot_suffix", "")),  ' + mark) + s[j + len(".metadata_slot = 0,"):]
    open(p, "w").write(s)
PYEOF
grep -q '// ASEM: current slot metadata' external/lptools/lptools.cc \
    || { echo "!! lptools map patch did not apply"; exit 1; }

echo "== copying device tree"
rm -rf device/infinix/X6855
mkdir -p device/infinix
cp -r "$HERE/device/infinix/X6855" device/infinix/X6855

echo "== building"
export ALLOW_MISSING_DEPENDENCIES=true
export ASEM_DECRYPT=${ASEM_DECRYPT:-false}
set +u
source build/envsetup.sh
lunch twrp_X6855-ap2a-eng
mka vendorbootimage
set -u

echo "== packing ASEM Recovery into stock vendor_boot"
mkdir -p "$HERE/out"
# keep the raw TWRP build too, so a packing problem never loses a finished build
cp out/target/product/X6855/vendor_boot.img "$HERE/out/twrp_built_vendor_boot.img"
IMG="$HERE/out/ASEM_Recovery_X6855_${VERSION}$([ "$ASEM_DECRYPT" = true ] && echo _decrypt).img"
python3 "$HERE/tools/asem_vendor_boot.py" replace "$STOCK" out/target/product/X6855/vendor_boot.img "$IMG"
python3 "$HERE/tools/asem_vendor_boot.py" info "$IMG"
(cd "$HERE/out" && sha256sum "$(basename "$IMG")" > "$(basename "$IMG").sha256")
echo "== done: $IMG"
