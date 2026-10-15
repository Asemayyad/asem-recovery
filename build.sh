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
$SYNC $SMALL
drop_git_objects; disk
for p in $BIG; do
    printf '%s\n' $ALL | grep -qxF "$p" || continue
    echo "   stage 2: $p"
    $SYNC "$p"
    drop_git_objects
    echo "   $(du -sh "$p" | cut -f1)  $p"; disk
done
# keep only the clang versions the build files name (prebuilts/clang has many)
CL=prebuilts/clang/host/linux-x86
KEEP=$(grep -rhoE 'clang-r[0-9]+[a-z]?' build/soong build/make prebuilts/rust 2>/dev/null | sort -u)
echo "   clang versions referenced: $(echo $KEEP)"
for d in "$CL"/clang-r*; do
    [ -d "$d" ] && [ ! -L "$d" ] || continue
    v=$(basename "$d")
    echo "$KEEP" | grep -qxF "$v" && continue
    readlink "$CL"/* 2>/dev/null | grep -q "$v" && continue
    echo "   removing unused $v ($(du -sh "$d" | cut -f1))"; rm -rf "$d"
done
disk

echo "== applying the ASEM theme (validated before compiling)"
git -C bootable/recovery checkout -q -- .
git -C bootable/recovery clean -fdq
python3 "$HERE/theme/apply_theme.py" --check "$WORK"

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
