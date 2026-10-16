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
        echo "   repo sync failed (try $i of 4) - waiting $((i * 60)) s and retrying"
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
# TWRP 14.1 bug: twrp_ramdisk copies system/etc/task_profiles.json but requires it only
# with TW_INCLUDE_CRYPTO, so without crypto the copy can run before the file exists.
# Required modules are built first (main.mk add-required-deps), so add it there.
sed -i 's/^LOCAL_REQUIRED_MODULES += init_second_stage\.recovery /LOCAL_REQUIRED_MODULES += task_profiles.json init_second_stage.recovery /' \
    bootable/recovery/prebuilt/Android.mk
grep -q '^LOCAL_REQUIRED_MODULES += task_profiles.json init_second_stage.recovery' bootable/recovery/prebuilt/Android.mk \
    || { echo "!! task_profiles.json patch did not apply"; exit 1; }

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
IMG="$HERE/out/ASEM_Recovery_X6855_${VERSION}.img"
python3 "$HERE/tools/asem_vendor_boot.py" replace "$STOCK" out/target/product/X6855/vendor_boot.img "$IMG"
python3 "$HERE/tools/asem_vendor_boot.py" info "$IMG"
(cd "$HERE/out" && sha256sum "$(basename "$IMG")" > "$(basename "$IMG").sha256")
echo "== done: $IMG"
