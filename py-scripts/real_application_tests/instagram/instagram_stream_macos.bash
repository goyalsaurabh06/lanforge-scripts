#!/bin/bash
# flake8: noqa

if [[ "$(uname)" == "Darwin" ]]; then
    # macOS: Terminate Chrome processes
    pkill -f "Google Chrome"
    pkill -f chromedriver
    sleep 5

    # ---- CONFIG ----
    VENV_PYTHON="/Users/lanforge/venv/bin/python"
    SCRIPT_PATH="/Users/lanforge/instagram.py"

    
    USERNAME=""
    PASSWORD=""
    DURATION=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --username)
                USERNAME="$2"
                shift 2
                ;;
            --password)
                PASSWORD="$2"
                shift 2
                ;;
            --duration)
                DURATION="$2"
                shift 2
                ;;
            *)
                echo "Unknown argument: $1"
                echo "Usage: $0 --username <user> --password <pass> --duration <minutes>"
                exit 1
                ;;
        esac
    done

    if [[ -z "$USERNAME" || -z "$PASSWORD" || -z "$DURATION" ]]; then
        echo "Usage: $0 --username <user> --password <pass> --duration <minutes>"
        exit 1
    fi

    echo "Batch started (Instagram macOS)"

    # macOS env fixes for Chrome under automation
    export LANG=en_US.UTF-8
    export LC_ALL=en_US.UTF-8
    export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

    # Some automation setups expect DISPLAY to be set
    export DISPLAY=:0


    LOG_DIR="$HOME/.insta_automation/logs"
    mkdir -p "$LOG_DIR"
    LOG_FILE="$LOG_DIR/insta_$(date +%Y%m%d_%H%M%S).log"
    echo "[INFO] Log file: $LOG_FILE"

    # Execute the Python script using the VENV interpreter
    "$VENV_PYTHON" "$SCRIPT_PATH" \
        --username "$USERNAME" \
        --password "$PASSWORD" \
        --duration "$DURATION" \
        >> "$LOG_FILE" 2>&1

    # macOS: Terminate Chrome processes
    pkill -f "Google Chrome"
    pkill -f chromedriver

else
    echo "Unsupported operating system (this script is for macOS)."
    exit 1
fi
