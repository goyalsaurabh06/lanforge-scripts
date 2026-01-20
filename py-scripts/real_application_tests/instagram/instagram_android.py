#!/usr/bin/env python3
from ppadb.client import Client as AdbClient
import uiautomator2 as u2
import time
import argparse
from concurrent.futures import ThreadPoolExecutor
import requests


class InstagramADB:
    def __init__(self, host="127.0.0.1", port=5037, upstream_port=None):
        self.client = AdbClient(host=host, port=port)
        self.devices = {}
        self.u2_sessions = {}
        self.test_serials = []
        self.upstream_port = upstream_port
        self.stop_signal = False

    # Device handling
    def get_devices(self):
        return [d.serial for d in self.client.devices()]

    def connect_devices(self):
        for serial in self.test_serials:
            try:
                self.devices[serial] = self.client.device(serial)
                self.u2_sessions[serial] = u2.connect(serial)
                print(f" Connected to device: {serial}")
            except Exception as e:
                print(f" Failed to connect to {serial}: {e}")

    # Stop signal (LANforge)
    def check_stop_signal(self):
        if not self.upstream_port:
            return False
        try:
            url = f"http://{self.upstream_port}:5002/check_stop"
            r = requests.get(url, timeout=2)
            if r.status_code == 200 and r.json().get("stop", False):
                print(" Stop signal received from server")
                self.stop_signal = True
        except Exception:
            pass
        return self.stop_signal

    # Instagram launch + Reels
    def open_instagram_reels(self, serial):
        d = self.u2_sessions[serial]

        # Ensure primary user
        self.devices[serial].shell("am switch-user 0")
        time.sleep(1)

        # Kill Instagram if running
        self.devices[serial].shell("am force-stop com.instagram.android")
        time.sleep(3)

        # Launch Instagram safely (MOST IMPORTANT FIX)
        self.devices[serial].shell(
            "monkey -p com.instagram.android -c android.intent.category.LAUNCHER 1"
        )

        # Wait for Instagram UI
        for _ in range(20):
            if "com.instagram.android" in d.dump_hierarchy():
                print(f"Instagram opened on {serial}")
                break
            time.sleep(1)
        else:
            raise Exception(f" Instagram did not open on {serial}")

        time.sleep(5)

        # Open Reels tab
        if d(descriptionContains="Reels").exists:
            d(descriptionContains="Reels").click()
        elif d(resourceId="com.instagram.android:id/tab_reels").exists:
            d(resourceId="com.instagram.android:id/tab_reels").click()
        else:
            # Fallback: bottom-center tap
            w, h = d.window_size()
            d.click(w // 2, int(h * 0.9))

        print(f"Reels opened on {serial}")
        time.sleep(3)

    # Play reels loop
    def play_reels(self, serial, duration_sec):
        d = self.u2_sessions[serial]
        start_time = time.time()

        while time.time() - start_time < duration_sec:
            if self.check_stop_signal():
                break

            # Keep video active

            # Watch current reel
            time.sleep(5)

            # Scroll to next reel
            d.swipe_ext("up", scale=0.8)
            time.sleep(2)

        # Stop Instagram
        self.devices[serial].shell("am force-stop com.instagram.android")
        print(f"Instagram test completed on {serial}")

    # Per-device runner
    def run_on_device(self, serial, duration_sec):
        try:
            self.open_instagram_reels(serial)
            self.play_reels(serial, duration_sec)
        except Exception as e:
            print(f"Error on {serial}: {e}")

    # Multi-device runner
    def run_on_multiple_devices(self, duration_sec):
        with ThreadPoolExecutor(max_workers=len(self.test_serials)) as executor:
            futures = [
                executor.submit(self.run_on_device, serial, duration_sec)
                for serial in self.test_serials
            ]
            for f in futures:
                f.result()


# Main
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Instagram Reels Android Automation (ADB + uiautomator2)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        required=True,
        help="Test duration in minutes"
    )
    parser.add_argument(
        "--devices",
        type=str,
        required=True,
        help="Comma-separated ADB device serials"
    )
    parser.add_argument(
        "--upstream_port",
        type=str,
        required=False,
        help="LANforge upstream IP (optional)"
    )

    args = parser.parse_args()

    duration_sec = args.duration * 60
    requested_devices = args.devices.split(",")

    adb = InstagramADB(upstream_port=args.upstream_port)
    all_devices = adb.get_devices()

    adb.test_serials = [d for d in requested_devices if d in all_devices]

    print(" Connected devices :", all_devices)
    print("Running on devices :", adb.test_serials)

    if not adb.test_serials:
        print("No valid devices selected")
        exit(1)

    adb.connect_devices()
    adb.run_on_multiple_devices(duration_sec)

