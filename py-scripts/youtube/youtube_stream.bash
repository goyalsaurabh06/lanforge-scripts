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

# Kill any Chrome process
if [[ "$(uname)" == "Linux" ]]; then
    # Linux: Terminate Chrome processes
    pkill -f chrome || echo "No Chrome processes found."
    pkill -f chromedriver || echo "No ChromeDriver processes found."
elif [[ "$(uname)" == "Darwin" ]]; then
    # macOS: Terminate Chrome processes
    pkill -f "Google Chrome" || echo "No Google Chrome processes found."
    pkill -f chromedriver || echo "No ChromeDriver processes found."
else
    # Unsupported OS
    echo "Unsupported operating system."
    exit 1
fi


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
#python3 youtube.py $args
export DISPLAY=:0 && python3 youtube.py $args > youtube_test.log 2>&1

# Kill any Chrome process
if [[ "$(uname)" == "Linux" ]]; then
    # Linux: Terminate Chrome processes
    pkill -f chrome || echo "No Chrome processes found."
    pkill -f chromedriver || echo "No ChromeDriver processes found."
elif [[ "$(uname)" == "Darwin" ]]; then
    # macOS: Terminate Chrome processes
    pkill -f "Google Chrome" || echo "No Google Chrome processes found."
    pkill -f chromedriver || echo "No ChromeDriver processes found."
else
    # Unsupported OS
    echo "Unsupported operating system."
    exit 1
fi
