#!/bin/bash

# Initialize variables
echo "Batch started"
url=""
host=""
port=""
device_name=""
duration=""
res=""
args=""

# Parse command line arguments
parseArgs() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --url)
                url="$2"
                shift 2
                ;;
            --host)
                host="$2"
                shift 2
                ;;
            --port)
                port="$2"
                shift 2
                ;;
            --device_name)
                device_name="$2"
                shift 2
                ;;
            --duration)
                duration="$2"
                shift 2
                ;;
            --res)
                res="$2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done
}

parseArgs "$@"

echo "Batch started1"

# Construct arguments for Python script
args=""
[[ -n "$url" ]] && args="$args --url $url"
[[ -n "$host" ]] && args="$args --host $host"
[[ -n "$port" ]] && args="$args --port $port"
[[ -n "$device_name" ]] && args="$args --device_name $device_name"
[[ -n "$duration" ]] && args="$args --duration $duration"
[[ -n "$res" ]] && args="$args --res $res"

echo "Running with arguments: $args"
python3 youtube.py $args
