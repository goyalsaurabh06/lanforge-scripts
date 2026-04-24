#!/bin/bash
# YouTube Shorts Automation (Linux)

set -e

# -----------------------------
# LOG SETUP

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

TS=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/youtube_shorts_${TS}.log"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "===== YOUTUBE SHORTS LINUX SCRIPT STARTED ====="

# -----------------------------
# FIRST ARG = INTERFACE (VRF)

IFACE="$1"
shift

echo "Using VRF interface: $IFACE"

# -----------------------------
# DEFAULT VALUES

SCROLL=10
DURATION=60
HOST=""
DEVICE_NAME="linux-device"

# -----------------------------
# PARSE ARGUMENTS

while [[ $# -gt 0 ]]; do
    case "$1" in
        --scroll)
            SCROLL="$2"
            shift 2
            ;;
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        --device_name)
            DEVICE_NAME="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

echo "Scroll Interval : $SCROLL"
echo "Total Duration  : $DURATION"
echo "Flask Host     : $HOST"
echo "Device Name    : $DEVICE_NAME"

# -----------------------------
# CLEAN OLD CHROME

echo "Killing existing Chrome sessions..."
pkill -f chrome || true
pkill -f chromedriver || true
sleep 3

# -----------------------------
# DISPLAY

if [ -z "${DISPLAY}" ]; then
    DISPLAY=:1
fi
export DISPLAY

# -----------------------------
# STATS FILE (SHARED BETWEEN VRF + ROOT)

STATS_FILE="/tmp/youtube_shorts_${DEVICE_NAME}_stats.json"
rm -f "$STATS_FILE"

echo "Stats file: $STATS_FILE"

# -----------------------------
# START STATS SENDER (ROOT NAMESPACE)

echo "Starting YouTube stats sender (root namespace)..."

python3 youtube_shorts_stats_sender.py \
    --host "$HOST" \
    --device_name "$DEVICE_NAME" \
    --stats_file "$STATS_FILE" &

SENDER_PID=$!
echo "Stats sender PID: $SENDER_PID"

# -----------------------------
# RUN PYTHON INSIDE VRF 

echo "Launching YouTube Shorts inside VRF..."

DISPLAY=$DISPLAY ./vrf_exec.bash "$IFACE" \
"python3 youtube_shorts.py \
    --scroll $SCROLL \
    --duration $DURATION \
    --device_name $DEVICE_NAME \
    --stats_file $STATS_FILE"

RET=$?

# -----------------------------
# STOP STATS SENDER

echo "Stopping stats sender..."
kill $SENDER_PID 2>/dev/null || true
wait $SENDER_PID 2>/dev/null || true

echo "Exit code: $RET"
echo "===== YOUTUBE SHORTS LINUX SCRIPT FINISHED ====="
exit $RET
