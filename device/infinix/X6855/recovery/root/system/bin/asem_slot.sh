#!/system/bin/sh
# ASEM Recovery - A/B slots through the phone's own boot HAL (bootctl), with REAL results.
# (TWRP 14.1's built-in switch only speaks the old HIDL interface; on this phone it
# failed and still showed "success".)
#   asem_slot.sh status [fresh]   refresh status files for the Slots page (fresh = drop old message)
#   asem_slot.sh set A|B      switch; exit 0 = done / already active, 1 = refused/failed
# Files in /tmp/asem_slot/ (the Slots page shows them with TWRP "fileexists"):
#   next_A|next_B  bootable_A|bootable_B  nohal
#   msg_done_X  msg_already_X  msg_refused_X  msg_fail  msg_nohal   (last action only)
# Refuses a slot the bootloader marked unbootable (after a Virtual A/B update the old
# slot has no working system - switching there would bootloop).
D=/tmp/asem_slot
say() { echo "$1"; echo "asem_slot: $1" >> /tmp/recovery.log; }
bc() { timeout 8 bootctl "$@" 2>/dev/null; }

status() {
    mkdir -p $D
    rm -f $D/next_* $D/bootable_* $D/nohal
    if [ "$(bc get-number-slots)" != 2 ]; then touch $D/nohal; return 1; fi
    case "$(bc get-active-boot-slot)" in 0) touch $D/next_A;; 1) touch $D/next_B;; esac
    [ "$(bc is-slot-bootable 0)" = 1 ] && touch $D/bootable_A
    [ "$(bc is-slot-bootable 1)" = 1 ] && touch $D/bootable_B
    return 0
}

case "$1" in
status)
    [ "$2" = fresh ] && rm -f $D/msg_*   # opening the Slots page from Home: no old message
    status
    exit 0
    ;;
set)
    case "$2" in a|A) n=0; L=A;; b|B) n=1; L=B;; *) say "usage: asem_slot.sh set A|B"; exit 2;; esac
    mkdir -p $D
    rm -f $D/msg_*
    if ! status; then touch $D/msg_nohal; say "Slot service not available - nothing was changed."; exit 1; fi
    if [ -e $D/next_$L ]; then
        touch $D/msg_already_$L; say "Slot $L is already the next-boot slot - nothing to change."; exit 0
    fi
    if [ ! -e $D/bootable_$L ]; then
        touch $D/msg_refused_$L
        say "Not switched: slot $L has no working system (marked unbootable). Nothing was changed."
        exit 1
    fi
    timeout 15 bootctl set-active-boot-slot $n >/dev/null 2>&1
    status
    if [ -e $D/next_$L ]; then
        touch $D/msg_done_$L; say "Done: slot $L will start at the next reboot."; exit 0
    fi
    touch $D/msg_fail; say "Switch failed - the next-boot slot is still the old one."
    exit 1
    ;;
*)
    say "usage: asem_slot.sh status | set A|B"
    exit 2
    ;;
esac
