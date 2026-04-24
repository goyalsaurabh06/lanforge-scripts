import json
import requests
import time
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--host", required=True)
parser.add_argument("--device_name", required=True)
parser.add_argument("--stats_file", required=True)
args = parser.parse_args()

while True:
    try:
        with open(args.stats_file) as f:
            data = json.load(f)

        payload = {
            args.device_name: data["stats"]
        }

        requests.post(
            f"http://{args.host}:5002/youtube_stats",
            json=payload,
            timeout=3
        )
    except Exception:
        pass

    time.sleep(1)
