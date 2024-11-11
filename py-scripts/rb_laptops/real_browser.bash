#!/bin/bash

# Initialize variables
echo "Batch started"
url=""
host=""
port=""
duration=""
args=""

# Parse command line arguments
parseArgs() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --url)
                url="$2"
                shift 2
                ;;
            --server)
                host="$2"
                shift 2
                ;;
            
            --duration)
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
[[ -n "$server" ]] && args="$args --host $host"
[[ -n "$duration" ]] && args="$args --duration $duration"

echo "Running with arguments: $args"
python3 real_browser.py $args
