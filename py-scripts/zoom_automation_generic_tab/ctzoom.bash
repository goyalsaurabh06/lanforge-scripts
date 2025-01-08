#!/bin/bash
# Launch selenium zoom viewer on a particular VRF.
# Usage: ./ct_zoom.bash <IP> <TYPE>


if [[ "$(uname)" == "Linux" ]]; then
    # Linux: Terminate Chrome processes
    pkill -f chrome || echo "No Chrome processes found."
    pkill -f chromedriver || echo "No ChromeDriver processes found."
else
    # Unsupported OS
    echo "Unsupported operating system."
    exit 1
fi



# Assign command line arguments to variables
IFACE=$1
IP=$2
TYPE=$3



if [ -z "${DISPLAY}" ]; then
    DISPLAY=:1
fi


# Display is set to the VNC display.

YTENV="--env SERVERS_CSV=$SERVERS_CSV --env LOCAL_DEV=$LOCAL_DEV --env LD_PRELOAD=$LD_PRELOAD"
if [ "$TYPE" == "host" ]; then
    DISPLAY=$DISPLAY ./vrf_exec.bash $IFACE "python3 zoom_host.py --ip $IP $YTENV" > zoom_host.log 2>&1
   

elif [ "$TYPE" == "client" ]; then

   DISPLAY=$DISPLAY ./vrf_exec.bash $IFACE "python3 zoom_client.py --ip $IP $YTENV" > zoom_client.log 2>&1

else
    echo "Invalid TYPE specified. Please use 'host' or 'client'."
    exit 1
fi
