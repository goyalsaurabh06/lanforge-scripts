#!/bin/bash
# Launch selenium YouTube viewer on a particular VRF.
# Usage: ./yt.bash <iface> <url> <host> <device_name> <duration> <res>

# Assign command line arguments to variables
IFACE=$1
URL=$2
HOST=$3
DURATION=$4


if [ -z "${DISPLAY}" ]; then
    DISPLAY=:1
fi

YTENV="--env SERVERS_CSV=$SERVERS_CSV --env LOCAL_DEV=$LOCAL_DEV --env LD_PRELOAD=$LD_PRELOAD"

# Display is set to the VNC display.
DISPLAY=$DISPLAY ./vrf_exec.bash $IFACE "python3 real_browser.py --url $URL --server $HOST  --duration $DURATION  $YTENV"
