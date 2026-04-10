#!/bin/zsh
set -e

# Default values for arguments
EXTRA_MODULES=""
USB_DEBUG=0
ZMK_ROOT=""

usage() {
    echo "Usage: $0 [-e|--extra-modules EXTRA_MODULES] [-u|--usb-debug] [-r|--root ZMK_ROOT]" >&2
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--extra-modules) EXTRA_MODULES="$2"; shift 2 ;;
        -u|--usb-debug) USB_DEBUG=1; shift ;;
        -r|--root) ZMK_ROOT="$2"; shift 2 ;;
        *) usage; exit 1 ;;
    esac
done

# Ensure ZMK_ROOT is set
if [ -z "$ZMK_ROOT" ]; then
    echo "Error: ZMK_ROOT must be specified using the -r or --root option." >&2
    usage
    exit 1
fi

CUR=$(pwd)

rm -f *.uf2 || :
cd $ZMK_ROOT
source .venv/bin/activate
cd app

# Append default EXTRA_MODULES paths if not provided
if [ -z "$EXTRA_MODULES" ]; then
    EXTRA_MODULES="$CUR"
    EXTRA_MODULES="$EXTRA_MODULES;$CUR/dep/zmk-nice-oled"
    EXTRA_MODULES="$EXTRA_MODULES;$CUR/dep/zmk-dongle-display-091-oled"
    EXTRA_MODULES="$EXTRA_MODULES;$CUR/dep/zmk-dongle-display"
    EXTRA_MODULES="$EXTRA_MODULES;$CUR/dep/nice-view-anim"
fi

export USB_DEBUG

function build_reset() {
    echo "Building reset..."
    west build -p -d build/reset -b nice_nano_v2 -- -DSHIELD="settings_reset"

    cp build/reset/zephyr/zmk.uf2 $CUR/reset.uf2
}

function build_central() {
    NAME=$1
    BOARD=$2
    SHIELD=$3
    echo "Building central $NAME..."

    # Conditionally add -S zmk-usb-logging if USB_DEBUG=1
    USB_DEBUG_FLAG=""
    if [ "$USB_DEBUG" -eq 1 ]; then
        USB_DEBUG_FLAG="-S zmk-usb-logging"
    fi

    west build -p -d build/central-$NAME -b $BOARD -S studio-rpc-usb-uart $USB_DEBUG_FLAG -- -DSHIELD="$SHIELD" \
        -DZMK_CONFIG=$CUR/config -DCONFIG_ZMK_STUDIO=y -DZMK_EXTRA_MODULES=$EXTRA_MODULES
    cp build/central-$NAME/zephyr/zmk.uf2 $CUR/central-$NAME.uf2
}

function build_peripheral() {
    NAME=$1
    BOARD=$2
    SHIELD=$3
    ARGS=$4
    echo "Building peripheral $NAME..."
    west build -p -d build/peripheral-$NAME -b $BOARD -- -DSHIELD="$SHIELD" \
        -DZMK_CONFIG=$CUR/config -DZMK_EXTRA_MODULES=$EXTRA_MODULES -DCONFIG_ZMK_SPLIT_ROLE_CENTRAL=n
    cp build/peripheral-$NAME/zephyr/zmk.uf2 $CUR/peripheral-$NAME.uf2
}

# reset
# build_reset

# nice view
# left
build_central left-nice-view nice_nano_v2 "chunchun_left nice_view_adapter_rgb nice_epaper" &
# build_peripheral left-nice-view nice_nano_v2 "chunchun_left nice_view_adapter nice_epaper" &
# build_peripheral left-nice-view-planet nice_nano_v2 "chunchun_left nice_view_adapter nice_view_anim" &
# build_peripheral left-nice-view-astronaut nice_nano_v2 "chunchun_left nice_view_adapter nice_view_anim" "-DCONFIG_ZMK_NICE_VIEW_ANIM_VARIANT=1" &
# right
# build_peripheral right-nice-view nice_nano_v2 "chunchun_right nice_view_adapter nice_epaper" &
# build_peripheral right-nice-view-planet nice_nano_v2 "chunchun_right nice_view_adapter nice_view_anim" &
# build_peripheral right-nice-view-astronaut nice_nano_v2 "chunchun_right nice_view_adapter nice_view_anim" "-DCONFIG_ZMK_NICE_VIEW_ANIM_VARIANT=1" &
wait

# # oled
# build_central dongle-oled-091 nice_nano_v2 "chunchun_dongle dongle_display_091_oled" &
# build_central dongle-oled nice_nano_v2 "chunchun_dongle dongle_display" &
# build_central left-oled nice_nano_v2 "chunchun_left nice_oled" &
# build_peripheral left-oled nice_nano_v2 "chunchun_left nice_oled" &
# build_peripheral right-oled nice_nano_v2 "chunchun_right nice_oled" &
# wait
