#!/bin/bash
# ==========================================
# YouTube SHORTS – macOS generic endpoint

set +e
cd /Users/lanforge || exit 1

LOG="youtube_shorts_macos.log"

echo "===== START $(date) =====" >> "$LOG"
echo "USER=$(whoami)" >> "$LOG"
echo "PWD=$(pwd)" >> "$LOG"

# Ensure environment
export DISPLAY=:0
export PATH="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$PATH"

# Kill previous browsers
pkill -f "Google Chrome" >> "$LOG" 2>&1
pkill -f chromedriver >> "$LOG" 2>&1
pkill -f Safari >> "$LOG" 2>&1
sleep 2

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --scroll) SCROLL="$2"; shift 2 ;;
        --duration) DURATION="$2"; shift 2 ;;
        --host) HOST="$2"; shift 2 ;;
        --device_name) DEVICE="$2"; shift 2 ;;
        *) shift ;;
    esac
done

echo "SCROLL=$SCROLL DURATION=$DURATION HOST=$HOST DEVICE=$DEVICE" >> "$LOG"

# Run python (DO NOT background it)
python3 youtube_shorts.py \
    --scroll "$SCROLL" \
    --duration "$DURATION" \
    --host "$HOST" \
    --device_name "$DEVICE" >> "$LOG" 2>&1

echo "===== END $(date) =====" >> "$LOG"
exit 0
