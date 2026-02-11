#!/bin/bash
# flake8: noqa

if [[ "$(uname)" == "Linux" ]]; then
	# --- Linux Configuration ---
	VENV_PYTHON="/home/lanforge/venv/bin/python"

	# Terminate Chrome processes
	pkill -f chrome
	pkill -f chromedriver
	sleep 5

	# Assign command line arguments to variables
	IFACE=$1
	IP=$2
	TYPE=$3

	if [ -z "${DISPLAY}" ]; then
		export DISPLAY=:1
	fi

	if [ "$TYPE" == "host" ]; then
		# Pass the VENV interpreter inside the command string to vrf_exec
		DISPLAY=$DISPLAY ./vrf_exec.bash "$IFACE" "$VENV_PYTHON gmeet_host.py --upstream_port_ip $IP"

	elif [ "$TYPE" == "client" ]; then
		DISPLAY=$DISPLAY ./vrf_exec.bash "$IFACE" "$VENV_PYTHON gmeet_client.py --upstream_port_ip $IP"
	else
		echo "Invalid TYPE specified. Please use 'host' or 'client'."
		exit 1
	fi

	# Terminate Chrome processes cleanup
	pkill -f chrome
	pkill -f chromedriver

elif [[ "$(uname)" == "Darwin" ]]; then
	# --- macOS Configuration ---
	VENV_PYTHON="/Users/lanforge/venv/bin/python"

	# Terminate Chrome processes
	pkill -f "Google Chrome"
	pkill -f chromedriver
	sleep 5

	# Assign command line arguments to variables
	IP=$1
	TYPE=$2

	if [ "$TYPE" == "host" ]; then
		"$VENV_PYTHON" gmeet_host.py --upstream_port_ip "$IP"

	elif [ "$TYPE" == "client" ]; then
		"$VENV_PYTHON" gmeet_client.py --upstream_port_ip "$IP"
	else
		echo "Invalid TYPE specified. Please use 'host' or 'client'."
		exit 1
	fi

	# Terminate Chrome processes cleanup
	pkill -f "Google Chrome"
	pkill -f chromedriver

else
	# Unsupported OS
	echo "Unsupported operating system."
	exit 1
fi
