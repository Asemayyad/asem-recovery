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
repo sync -c --no-clone-bundle --no-tags --optimized-fetch --prune --force-sync -j"$(( $(nproc) * 4 ))"

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
