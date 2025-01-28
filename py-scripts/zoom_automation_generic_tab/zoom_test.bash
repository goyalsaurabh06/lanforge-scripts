#!/bin/bash
# Launch selenium YouTube viewer on a particular VRF.
# Usage: ./ct_zoom.bash <IP> <TYPE>

# Kill any Chrome process
if [[ "$(uname)" == "Darwin" ]]; then
    # macOS: Terminate Chrome processes
    pkill -f "Google Chrome" || echo "No Google Chrome processes found."
    pkill -f chromedriver || echo "No ChromeDriver processes found."
else
    # Unsupported OS
    echo "Unsupported operating system."
    exit 1
fi
# Assign command line arguments to variables

IP=$1
TYPE=$2


if [ "$TYPE" == "host" ]; then
    python3 zoom_host.py --ip $IP > zoom_host.log 2>&1
elif [ "$TYPE" == "client" ]; then
    python3 zoom_client.py --ip $IP > zoom_client.log 2>&1
else
    echo "Invalid TYPE specified. Please use 'host' or 'client'."
    exit 1
fi