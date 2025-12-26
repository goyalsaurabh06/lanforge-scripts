#!/bin/bash
# flake8: noqa

IFACE="${1:-}"
UPSTREAM_PORT="${2:-}"
DURATION="${3:-}"

if [[ "$(uname)" == "Linux" ]]; then
    # Linux: Terminate Chrome processes
    pkill -f chrome
    pkill -f chromedriver
    sleep 5

    VENV_PYTHON="/home/lanforge/venv/bin/python"
    SCRIPT_PATH="/home/lanforge/netflix.py"




    if [ -z "${DISPLAY}" ]; then
        DISPLAY=:1
    fi

    DISPLAY=$DISPLAY ./vrf_exec.bash "$IFACE" "$VENV_PYTHON" "$SCRIPT_PATH" --upstream_port "$UPSTREAM_PORT" --duration "$DURATION"
    # -------------------------------------------

    # Linux: Terminate Chrome processes
    pkill -f chrome
    pkill -f chromedriver

elif [[ "$(uname)" == "Darwin" ]]; then
    # macOS: Terminate Chrome processes
    pkill -f "Google Chrome"
    pkill -f chromedriver
    sleep 5

    VENV_PYTHON="/Users/lanforge/venv/bin/python"
    SCRIPT_PATH="/Users/lanforge/netflix.py"

    echo "Batch started1"
    #python3 youtube.py $args
    export DISPLAY=:0

    # Execute the Python script using the VENV interpreter
    # Execute the Python script directly using venv interpreter and named flags
    "$VENV_PYTHON" "$SCRIPT_PATH" --upstream_port "$UPSTREAM_PORT" --duration "$DURATION"
    # ------------------------------------

    # macOS: Terminate Chrome processes
    pkill -f "Google Chrome"
    pkill -f chromedriver
else
    # Unsupported OS
    echo "Unsupported operating system."
    exit 1
fi
