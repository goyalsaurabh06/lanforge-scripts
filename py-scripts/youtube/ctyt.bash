#!/bin/bash
# Launch selenium YouTube viewer on a particular VRF.
# Usage: ./yt.bash <iface> <url> <host> <device_name> <duration> <res>

# Assign command line arguments to variables
IFACE=$1
URL=$2
HOST=$3
DEVICE_NAME=$4
DURATION=$5
RES=$6

# Kill any Chrome process
if [[ "$(uname)" == "Linux" ]]; then
    # Linux: Terminate Chrome processes
    pkill -f chrome || echo "No Chrome processes found."
    pkill -f chromedriver || echo "No ChromeDriver processes found."
elif [[ "$(uname)" == "Darwin" ]]; then
    # macOS: Terminate Chrome processes
    pkill -f "Google Chrome" || echo "No Google Chrome processes found."
    pkill -f chromedriver || echo "No ChromeDriver processes found."
else
    # Unsupported OS
    echo "Unsupported operating system."
    exit 1
fi

if [ -z "${DISPLAY}" ]; then
    DISPLAY=:1
fi

YTENV="--env SERVERS_CSV=$SERVERS_CSV --env LOCAL_DEV=$LOCAL_DEV --env LD_PRELOAD=$LD_PRELOAD"

# Display is set to the VNC display.
DISPLAY=$DISPLAY ./vrf_exec.bash $IFACE "python3 youtube.py --url $URL --host $HOST --device_name $DEVICE_NAME --duration $DURATION --res $RES $YTENV" > youtube_test.log 2>&1


# Kill any Chrome process
if [[ "$(uname)" == "Linux" ]]; then
    # Linux: Terminate Chrome processes
    pkill -f chrome || echo "No Chrome processes found."
    pkill -f chromedriver || echo "No ChromeDriver processes found."
elif [[ "$(uname)" == "Darwin" ]]; then
    # macOS: Terminate Chrome processes
    pkill -f "Google Chrome" || echo "No Google Chrome processes found."
    pkill -f chromedriver || echo "No ChromeDriver processes found."
else
    # Unsupported OS
    echo "Unsupported operating system."
    exit 1
fi
