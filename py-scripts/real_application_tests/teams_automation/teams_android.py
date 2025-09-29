import uiautomator2 as u2
import time
from ppadb.client import Client as AdbClient
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import traceback
from concurrent.futures import as_completed

class TeamsAndroid:
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
        self.total_serials = []
        self.audio = True
        self.video = True

    def get_devices(self):
        """Return list of connected ADB serials"""
        devices = self.client.devices()
        return [d.serial for d in devices]

    def connect_devices(self):
        """Connect to devices and create uiautomator2 sessions."""
        connected = []
        for serial in self.total_serials:
            try:
                device = self.client.device(serial)
                if not device:
                    print(f"ADB did not return device object for {serial}")
                    continue

                self.devices[serial] = device
                self.adb_serials[serial] = serial
                self.u2_sessions[serial] = u2.connect(serial)

                connected.append(serial)

            except Exception as e:
                print(f"Failed to connect to device {serial}: {e}")

        # Update test_serials with only successful connections
        self.test_serials = connected
        print(f"Active test_serials: {self.test_serials}")

    # def run_on_multiple_devices(self, device_serials, duration, max_workers=5):
    #     with ThreadPoolExecutor(max_workers=max_workers) as executor:
    #         futures = [
    #             executor.submit(self.open_chrome_incognito, serial, duration)
    #             for serial in device_serials
    #         ]
    #         # Wait for all to complete
    #         for future in futures:
    #             future.result()


    def run_on_multiple_devices(self, device_serials, duration, max_workers=5):
        def wrapper(serial):
            try:
                print(f"[{serial}] 🚀 Starting open_chrome_incognito")
                self.open_chrome_incognito(serial, duration)
                print(f"[{serial}] ✅ Completed successfully")
            except Exception as e:
                print(f"[{serial}] ❌ Failed with error: {e}")
                traceback.print_exc()
            return serial

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # submit tasks for each device
            futures = {executor.submit(wrapper, serial): serial for serial in device_serials}

            # log progress as each finishes
            for future in as_completed(futures, timeout=None):
                serial = futures[future]
                try:
                    future.result(timeout=120)  # per-device timeout
                except Exception as e:
                    print(f"[{serial}] ⚠️ Exception or timeout: {e}")

    def open_chrome_incognito(self, serial, duration):
        d = self.u2_sessions[serial]
        # Launch Chrome directly in incognito with Teams URL
        d.app_start("com.android.chrome")

        # Build selector, then wait for it
        btn = d(resourceId="com.android.chrome:id/menu_button")

        if btn.wait(timeout=10):  # <-- actively waits up to 5s
            btn.click()

        # Click "New Incognito tab"
        incog_row = d(resourceId="com.android.chrome:id/new_incognito_tab_menu_id")
        if incog_row.wait(timeout=10):
            incog_row.click()

        url_bar = d(resourceId="com.android.chrome:id/url_bar")
        if url_bar.wait(timeout=10):
            url_bar.click()
            d.send_keys("https://www.google.com", clear=True)
            d.press("enter")
        else:
            print("Laxmi Narayana")
            print(f"URL bar not found for device {d.serial}")
            return

        time.sleep(10)

        btn = d(resourceId="com.android.chrome:id/menu_button")

        if btn.wait(timeout=10):  # <-- actively waits up to 5s
            btn.click()

        node = d(resourceId="com.android.chrome:id/menu_item_text", text="Desktop site")
        if node.wait(timeout=10):
            desc = node.info.get("contentDescription")
            if "Turn off" in desc:
                print("Desktop site is ENABLED")
                incog_row = d(
                    resourceId="com.android.chrome:id/new_incognito_tab_menu_id"
                )
                if incog_row.wait(timeout=10):
                    incog_row.click()
            elif "Turn on" in desc:
                node.click()
                time.sleep(2)
                print("Desktop site is ENABLED Now Previously it was DISABLED")

        self.login_teams(d)

    def login_teams(self, d):
        # Wait for the URL bar and type the Teams URL
        url_bar = d(resourceId="com.android.chrome:id/url_bar")
        if url_bar.wait(timeout=10):
            url_bar.click()
            d.send_keys("https://teams.microsoft.com/v2", clear=True)
            d.press("enter")
        else:
            print(f"URL bar not found for device {d.serial}")
            return

        email_input = d.xpath('//*[@resource-id="i0116"]')
        if email_input.wait(timeout=30):
            d.send_keys("test2@ctipltest.onmicrosoft.com", clear=True)
            d.press("enter")
        else:
            print(f"Email input not found for device {d.serial}")
            return

        time.sleep(10)
        d.send_keys("R@006900206161aj", clear=True)

        d.press("enter")
        time.sleep(5)
        d.press("enter")
        time.sleep(20)
        self.enter_meeting(d)

    def enter_meeting(self, d):
        url_bar = d(resourceId="com.android.chrome:id/url_bar")
        if url_bar.wait(timeout=10):
            url_bar.click()
            d.send_keys(
                "https://teams.microsoft.com/meet/4950863846706?p=hR18cFksPeV0cbgMbz",
                clear=True,
            )
            d.press("enter")
        else:
            print(f"URL bar not found for device {d.serial}")
            return

        d.dump_hierarchy()
        time.sleep(10)

        while "Allow while visiting the site" not in d.dump_hierarchy():
            print("Waiting for Allow while visiting the site button to appear...")
            time.sleep(2)

        allow_btn = d(text="Allow while visiting the site")
        if allow_btn.wait(timeout=10):
            print("Allow while visiting the site button is present")
            info = allow_btn.info
            if info.get("enabled") and info.get("clickable"):
                allow_btn.click()

        else:
            print(
                f"Allow while visiting the site button not found for device {d.serial}"
            )
            return

        d.dump_hierarchy()
        time.sleep(5)

        camera_toggle_btn = d(text="Turn camera on (Ctrl+Shift+O)")
        if camera_toggle_btn.wait(timeout=60):
            camera_toggle_btn.click()
        else:
            print("Camera toggle button not found")
            return

        join_btn = d(resourceId="prejoin-join-button")
        if join_btn.wait(timeout=60):
            join_btn.click()
        else:
            print("Join button not found")
            return
        time.sleep(10)
        self.enable_stats(d)

    def enable_stats(self, d):
        time.sleep(10)
        xml = d.dump_hierarchy()
        while "callingButtons-showMoreBtn" not in xml:
            time.sleep(1)
            xml = d.dump_hierarchy()
            print("Waiting for More button to appear in call controls...")
        more_btn = d(resourceId="callingButtons-showMoreBtn")
        if more_btn.wait(timeout=180):
            more_btn.click()
        else:
            print("More button not found")
            return
        settings_btn = d(resourceId="SettingsMenuControl-id")
        if settings_btn.wait(timeout=60):
            settings_btn.click()
        else:
            print("Settings button not found")
            return
        call_health_btn = d(resourceId="call-health-button")
        if call_health_btn.wait(timeout=60):
            call_health_btn.click()
        else:
            print("Call health button not found")
            return

        # Run for 1 minute using datetime
        end_time = datetime.now() + timedelta(minutes=2)

        while datetime.now() < end_time:
            if self.audio:
                audio_stats = self.collect_audio_stats(d)
            if self.video:
                video_stats = self.collect_video_stats(d)
            self.send_stats_to_server(d.serial, audio_stats, video_stats)

        self.close_meeting(d)

    def close_meeting(self, d):
        d.app_stop("com.android.chrome")

    def collect_audio_stats(self, d):
        # Wait until "View more audio data" button appears
        while "View more audio data" not in d.dump_hierarchy():
            time.sleep(1)
            print(
                f"Waiting for View more audio data button to appear for {d.serial}..."
            )

        # Open panel
        if d(text="View more audio data").wait(timeout=10):
            try:
                d(text="View more audio data").click()
            except Exception as e:
                print(f"Retrying click due to stale element: {e}")
                time.sleep(5)
                d(text="View more audio data").click()
        else:
            print(f"Audio panel not found for device {d.serial}, skipping...")
            return

        # Wait for all resource-ids 0–7 to appear
        expected_ids = [str(i) for i in range(8)]
        timeout = 30
        start = time.time()

        while True:
            xml = d.dump_hierarchy()
            tree = ET.fromstring(xml)
            present_ids = {
                node.attrib.get("resource-id")
                for node in tree.findall(".//node")
                if node.attrib.get("resource-id")
            }

            missing = set(expected_ids) - present_ids
            if not missing:
                print(f"✅ All resource-ids found for {d.serial}")
                break

            if time.time() - start > timeout:
                print(f"⚠️ Timeout waiting for resource-ids {missing} on {d.serial}")
                break

            time.sleep(1)

        # Now safe to grab
        def grab(resource_id, default="NA", strip=""):
            try:
                parent = tree.find(f'.//*[@resource-id="{resource_id}"]')
                if parent is not None:
                    node = parent.find('node[@index="2"]')
                    if node is not None:
                        val = node.attrib.get("text", "")
                        if val:
                            return val.replace(strip, "").strip()
            except Exception as e:
                print(f"XML parse failed for {resource_id}: {e}")
            return default

        audio_stats_data = {
            "au_sent_bitrate": grab("0", "0", "Kbps"),
            "au_sent_pkts": grab("1", "0", "packets"),
            "au_rtt": grab("2", "0", "ms"),
            "au_sent_codec": grab("3", "NA"),
            "au_recv_jitter": grab("4", "0", "ms"),
            "au_recv_pkt_loss": grab("5", "0", "%"),
            "au_recv_pkts": grab("6", "0", "packets"),
            "au_recv_codec": grab("7", "NA"),
        }

        # print(audio_stats_data)

        while True:
            xml = d.dump_hierarchy()
            if "Go back to call health root panel" in xml:
                break
            time.sleep(1)
            print(f"Waiting for go back to call health panel for {d.serial}")

        if d(text="Go back to call health root panel").wait(timeout=10):
            try:
                d(text="Go back to call health root panel").click()
            except Exception as e:
                print(f"Retrying click due to stale element: {e}")
                time.sleep(5)
                d(text="Go back to call health root panel").click()

        return audio_stats_data

    def collect_video_stats(self, d):
        # Wait until "View more video data" button appears
        xml = d.dump_hierarchy()
        while "View more video data" not in xml:
            time.sleep(1)
            xml = d.dump_hierarchy()
            print(
                f"Waiting for View more video data button to appear for {d.serial}..."
            )

        if d(text="View more video data").wait(timeout=10):
            try:
                d(text="View more video data").click()
            except Exception as e:
                print(f"Retrying click due to stale element: {e}")
                time.sleep(5)
                d(text="View more video data").click()
        else:
            print(f"Video panel not found for device {d.serial}, skipping...")
            return

        # Wait for all 8 resource-ids (0–7) to appear
        expected_ids = [str(i) for i in range(8)]
        timeout = 30
        start = time.time()

        while True:
            xml = d.dump_hierarchy()
            tree = ET.fromstring(xml)

            present_ids = {
                node.attrib.get("resource-id")
                for node in tree.findall(".//node")
                if node.attrib.get("resource-id")
            }

            missing = set(expected_ids) - present_ids
            if not missing:
                print(f"✅ All video resource-ids found for {d.serial}")
                break

            if time.time() - start > timeout:
                print(
                    f"⚠️ Timeout waiting for video resource-ids {missing} on {d.serial}"
                )
                break

            time.sleep(1)

        # Grab helper
        def grab(resource_id, default="NA", strip=""):
            try:
                parent = tree.find(f'.//*[@resource-id="{resource_id}"]')
                if parent is not None:
                    node = parent.find('node[@index="2"]')
                    if node is not None:
                        val = node.attrib.get("text", "")
                        if val:
                            return val.replace(strip, "").strip()
            except Exception as e:
                print(f"XML parse failed for {resource_id}: {e}")
            return default

        # Collect video stats
        video_stats_data = {
            "vi_sent_bitrate": grab("0", "0", "Mbps"),
            "vi_recv_bitrate": grab("1", "0", "Mbps"),
            "vi_sent_frame_rate": grab("2", "0", "fps"),
            "vi_sent_res": grab("3", "NA", "px"),
            "vi_rtt": grab("4", "0", "ms"),
            "vi_sent_pkts": grab("5", "0", "packets"),
            "vi_sent_codec": grab("6", "NA"),
            "vi_processing": grab("7", "NA"),
        }

        while True:
            xml = d.dump_hierarchy()
            if "Go back to call health root panel" in xml:
                break
            time.sleep(1)
            print(f"Waiting for go back to call health panel for {d.serial}")

        if d(text="Go back to call health root panel").wait(timeout=10):
            try:
                d(text="Go back to call health root panel").click()
            except Exception as e:
                print(f"Retrying click due to stale element: {e}")
                time.sleep(5)
                d(text="Go back to call health root panel").click()

        return video_stats_data

    def send_stats_to_server(self, serial, audio_stats, video_stats):
        if self.audio:
            payload = {
                serial: {
                    "timestamp": datetime.now().isoformat(),
                    "audio_stats": audio_stats,
                }
            }
        if self.video:
            payload = {
                serial: {
                    "timestamp": datetime.now().isoformat(),
                    "video_stats": video_stats,
                }
            }
        if self.audio and self.video:
            payload = {
                serial: {
                    "timestamp": datetime.now().isoformat(),
                    "audio_stats": audio_stats,
                    "video_stats": video_stats,
                }
            }
        print(payload)

        # try:
        #     response = requests.post(f"{self.base_url}/upload_stats", json=payload)
        #     if response.status_code == 200:
        #         print(f"Stats uploaded for {hostname}")
        #     else:
        #         print(f"Failed to upload stats: {response.status_code} - {response.text}")
        # except Exception as e:
        #     print(f"Exception during upload: {e}")

    def dump_xml(self, d):
        xml = d.dump_hierarchy()
        with open(f"dump_{d.serial}.xml", "w", encoding="utf-8") as f:
            f.write(xml)


if __name__ == "__main__":
    teams_android = TeamsAndroid()
    teams_android.total_serials = teams_android.get_devices()
    print(f"Found devices: {teams_android.total_serials}")
    teams_android.connect_devices()
    teams_android.run_on_multiple_devices(
        teams_android.test_serials, duration=60, max_workers=len(teams_android.test_serials)
    )
