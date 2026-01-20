#!/bin/bash
# flake8: noqa

if [[ "$(uname)" == "Linux" ]]; then
    pkill -f chrome || true
    pkill -f chromedriver || true
    sleep 5

    VENV_PYTHON="/home/lanforge/venv/bin/python"
    SCRIPT_PATH="/home/lanforge/instagram.py"

    # Default interface if not provided
    IFACE="wlan0"

    # Parse optional --iface flag, keep others untouched
    PASSTHRU=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --iface)
                IFACE="$2"
                shift 2
                ;;
            *)
                PASSTHRU+=("$1")
                shift
                ;;
        esac
    done

    if [ -z "${DISPLAY}" ]; then
        export DISPLAY=:1
    fi

    echo "[INFO] Using interface: $IFACE"
    echo "[INFO] Running: $VENV_PYTHON $SCRIPT_PATH ${PASSTHRU[*]}"

    DISPLAY=$DISPLAY ./vrf_exec.bash "$IFACE" "$VENV_PYTHON" "$SCRIPT_PATH" "${PASSTHRU[@]}"

    pkill -f chrome || true
    pkill -f chromedriver || true

elif [[ "$(uname)" == "Darwin" ]]; then
    pkill -f "Google Chrome" || true
    pkill -f chromedriver || true
    sleep 5

    VENV_PYTHON="/Users/lanforge/venv/bin/python"
    SCRIPT_PATH="/Users/lanforge/instagram.py"

    export DISPLAY=:0

    echo "[INFO] Running: $VENV_PYTHON $SCRIPT_PATH $@"
    "$VENV_PYTHON" "$SCRIPT_PATH" "$@"

    pkill -f "Google Chrome" || true
    pkill -f chromedriver || true
else
    echo "Unsupported operating system."
    exit 1
fi
