#!/bin/bash
# flake8: noqa
# --- Positional Arguments ---
IFACE="$1"        # Network interface (e.g., enp0s31f6)
MODE="$2"         # host or client
MEDIA="$3"        # media file (host only, else use '-')
MCAST_IP="$4"     # multicast IP
PORT="$5"         # multicast port
DURATION="$6"     # duration in seconds
CLIENT_ID="$7"    # client id
LFSERVER="$8"   # server ip:port

DISPLAY_ID=":1"
SCRIPT="ctvlc.py"

# Getting os
OS=$(uname)

# --- Validate inputs ---
if [[ -z "$IFACE" || -z "$MODE" || -z "$MCAST_IP" || -z "$PORT" || -z "$DURATION" ]]; then
  echo "ERROR Usage: $0 <iface> <host|client> <media|- > <mcast_ip> <port> <duration>"
  exit 1
fi

if [[ "$MODE" != "host" && "$MODE" != "client" ]]; then
  echo "ERROR Second argument must be 'host' or 'client'"
  exit 1
fi

if [[ "$MODE" == "host" ]]; then
  if [[ "$MEDIA" == "-" || -z "$MEDIA" ]]; then
    echo "ERROR Host mode requires a valid media file (3rd argument)"
    exit 1
  fi
  if [[ ! -f "$MEDIA" ]]; then
    echo "ERROR Media file not found: $MEDIA"
    exit 1
  fi
fi

# --- Multicast IP validation ---
if [[ ! "$MCAST_IP" =~ ^(22[4-9]|23[0-9])\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]; then
  echo "ERROR Invalid multicast IP: $MCAST_IP"
  exit 1
fi

# --- Port and duration check ---
if ! [[ "$PORT" =~ ^[0-9]+$ ]] || [[ "$PORT" -lt 1024 || "$PORT" -gt 65535 ]]; then
  echo "ERROR Invalid port: $PORT"
  exit 1
fi

if ! [[ "$DURATION" =~ ^[0-9]+$ ]]; then
  echo "ERROR Invalid duration: $DURATION"
  exit 1
fi

# --- Set DISPLAY environment ---
export DISPLAY=$DISPLAY_ID

# --- Build Python command ---
CMD=(python3 "$SCRIPT" "$MODE" --mcast_ip "$MCAST_IP" --port "$PORT" --duration "$DURATION")
if [[ "$MODE" == "host" ]]; then
  CMD+=(--media "$MEDIA")
fi

# adding client_id
if [[ -n "$CLIENT_ID" ]]; then
  CMD+=(--client_id "$CLIENT_ID")
fi

# Flask server address
if [[ -n "$LFSERVER" ]]; then
  CMD+=(--fserver "$LFSERVER")
fi
echo "${CMD[@]}"
if [[ "$OS" == "Darwin" ]]; then
  echo "Detected macOS.Pre-cleanup: Killing any old VLC processes..."
  pkill -f "/Applications/VLC.app/Contents/MacOS/VLC"
  sleep 2
  "${CMD[@]}"
  echo "Terminating VLC on macOS..."
  pkill -f "/Applications/VLC.app/Contents/MacOS/VLC"
else
  echo "Detected $OS.Pre-cleanup: Killing any old VLC processes..."
  pkill -9 vlc
  sleep 2
  ./vrf_exec.bash "$IFACE" "${CMD[@]}"
  echo "Killing VLC on Linux..."
  pkill -9 vlc
fi