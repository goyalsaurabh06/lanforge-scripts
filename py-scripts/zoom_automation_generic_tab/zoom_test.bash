#!/bin/bash
# Launch selenium YouTube viewer on a particular VRF.
# Usage: ./ct_zoom.bash <IP> <TYPE>

# Assign command line arguments to variables

IP=$1
TYPE=$2


if [ "$TYPE" == "host" ]; then
   python3 zoom_host.py --ip $IP 
   

elif [ "$TYPE" == "client" ]; then

   python3 zoom_client.py --ip $IP

else
    echo "Invalid TYPE specified. Please use 'host' or 'client'."
    exit 1
fi
