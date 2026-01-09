#!/usr/bin/env python3
from ppadb.client import Client as AdbClient
import uiautomator2 as u2
import xml.etree.ElementTree as ET
import re
import time
from datetime import datetime
import argparse
from concurrent.futures import ThreadPoolExecutor
import requests
import json
import logging

logging.basicConfig(
    filename="netflix_test.log",
    filemode="w",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


class Adb:
    def __init__(self, host="127.0.0.1", port=5037, upstream_port=None):
        self.host = host
        self.port = port
        self.client = AdbClient(host=self.host, port=self.port)
        self.devices = {}
        self.adb_serials = {}
        self.u2_sessions = {}
        self.stats = {}
        self.upstream_port = upstream_port
        self.test_serials = []
        self.stop_signal = False

    def get_devices(self):
        """Return list of connected ADB serials without side-effects."""
        devices = self.client.devices()
        return [d.serial for d in devices]

    def connect_devices(self):
        """Connect to devices and create uiautomator2 sessions."""
        for serial in self.test_serials:
            try:
                device = self.client.device(serial)
                self.devices[serial] = device
                self.adb_serials[serial] = serial
                self.u2_sessions[serial] = u2.connect(serial)
                logging.info(f"Connected to device: {serial}")
            except Exception as e:
                logging.info(f"Failed to connect to device {serial}: {e}")

    def execute_cmd(self, device_serial, cmd):
        return self.devices[device_serial].shell(cmd)

    def execute_tap(self, device_serial, x, y):
        self.devices[device_serial].input_tap(x, y)

    def execute_keyevent(self, device_serial, key_code):
        self.devices[device_serial].input_keyevent(key_code)

    def open_interop_app(self, serial):
        d = self.u2_sessions[serial]
        d.app_start("com.candela.wecan")
        count = 0
        while "com.candela.wecan:id/enter_button" not in d.dump_hierarchy():
            time.sleep(1)
            logging.info(f"Waiting for Interop app to load on device {d.serial}...")
            count += 1
            if count > 15:
                raise Exception(
                    f"❌ Interop app did not load in time for device {d.serial}"
                )
        enter_test_room = d(resourceId="com.candela.wecan:id/enter_button")
        if enter_test_room.wait(timeout=10):
            enter_test_room.click()
        else:
            raise Exception(
                f"Enter button not found in Interop app for device {d.serial}"
            )
        logging.info(f"Opened Interop app on device {d.serial}")

    def check_stop_signal(self):
        """Check the stop signal from the Flask server."""
        try:
            endpoint_url = f"http://{self.upstream_port}:5010/check_stop"

            response = requests.get(endpoint_url)
            if response.status_code == 200:

                stop_signal_from_server = response.json().get("stop", False)

                if stop_signal_from_server:
                    self.stop_signal = True
                    logging.info(
                        "Stop signal received from the server. Exiting the loop."
                    )
                else:

                    logging.info("No stop signal received from the server. Continuing.")
            return self.stop_signal
        except Exception as e:
            logging.info(f"Error checking stop signal: {e}")

    def run_on_device(self, serial, video_url, delay, duration):
        # Force-stop YouTube app if running
        self.execute_cmd(serial, "am force-stop com.google.android.youtube")
        time.sleep(10)

        # Launch YouTube video
        self.execute_cmd(
            serial,
            f"am start -a android.intent.action.VIEW -d {video_url} -n com.netflix.mediaclient/.ui.launch.UIWebViewActivity",
        )
        time.sleep(delay)

        start_time = time.time()
        end_time = start_time + duration  # duration is in seconds

        while time.time() < end_time:
            time.sleep(1)  # control polling frequency
            if self.check_stop_signal():
                break
        self.execute_cmd(serial, "am force-stop com.netflix.mediaclient")
        self.open_interop_app(serial)
        logging.info(f"[{serial}] Test completed or stopped.")

    def run_on_multiple_devices(
        self, device_serials, video_url, delay, duration, max_workers=5
    ):
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self.run_on_device, serial, video_url, delay, duration)
                for serial in device_serials
            ]
            # Wait for all to complete
            for future in futures:
                future.result()


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Play Netflix video automation with ad skipping"
    )
    parser.add_argument(
        "--url", type=str, required=True, help="Netflix video URL to play"
    )
    parser.add_argument(
        "--duration", type=int, default=30, help="Video play duration in Minutes"
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=0,
        help="Delay before starting video playback (in seconds)",
    )
    parser.add_argument(
        "--devices",
        type=str,
        required=True,
        help="Comma-separated list of device serials to run the test on",
    )
    parser.add_argument(
        "--upstream_port",
        type=str,
        required=True,
        help="Upstream port for LANforge",
    )
    args = parser.parse_args()

    video_url = args.url
    duration = int(args.duration) * 60  # minutes to seconds
    delay = args.delay
    adb_client = Adb(upstream_port=args.upstream_port)
    device_serials = adb_client.get_devices()
    requested = args.devices.split(",")
    test_serials = [s for s in requested if s in device_serials]
    logging.info(f"Running test on devices: {test_serials}")
    logging.info(f"All connected devices: {device_serials}")
    adb_client.test_serials = test_serials
    adb_client.connect_devices()
    if test_serials:
        adb_client.run_on_multiple_devices(
            test_serials,
            video_url,
            delay,
            duration,
            max_workers=len(test_serials),
        )
