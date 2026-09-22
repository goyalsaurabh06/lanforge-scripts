import time
import re
import sys
import pytz
from datetime import datetime
import argparse
import os
import requests
import socket

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


class ZoomClient:
    def __init__(self, server_ip=None):
        self.server_ip = server_ip
        self.base_url = f"http://{self.server_ip}:5000"
        self.new_login_url = None
        self.new_login_passwd = None
        self.meeting_link = None

        # Playwright objects
        self._playwright = None
        self.browser = None
        self.context = None
        self.page = None

        # zoom_frame is a FrameLocator — used for all element interactions
        # inside the #webclient iframe (equivalent to driver.switch_to.frame)
        self.zoom_frame = None

        self.start_time = None
        self.end_time = None
        self.tz = pytz.timezone("Asia/Kolkata")
        self.hostname = socket.gethostname()
        self.audio = True
        self.video = True
        self.stop_signal = False
        self.audio_stats = ["0", "0", "0", "0", "0", "0", "0", "0"]
        self.video_stats = ["0", "0", "0", "0", "0", "0", "0", "0", "0", "0"]

    # Driver / Browser Setup

    def setupdriver(self):
        self._playwright = sync_playwright().start()

        self.browser = self._playwright.chromium.launch(
            headless=False,
            args=[
                # Media flags — suppress permission popups
                "--use-fake-ui-for-media-stream",

                # Stability
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-notifications",
                "--disable-extensions",
                "--disable-infobars",

                # Performance (mirrors original chrome_options)
                "--process-per-site",
                "--renderer-process-limit=4",
                "--disable-background-timer-throttling",
                "--disable-backgrounding-occluded-windows",
                "--enable-low-res-tiling",
                "--force-gpu-mem-available-mb=4096",
                "--memory-pressure-thresholds-mb=2048",
            ],
        )

        self.context = self.browser.new_context(
            permissions=["camera", "microphone", "notifications"],
        )

        # Global default timeout — equivalent to WebDriverWait(driver, 90)
        self.context.set_default_timeout(90_000)

        self.page = self.context.new_page()
        self.page.set_viewport_size({"width": 1920, "height": 1080})

    # Zoom Login — Join as Guest

    def zoom_login(self):
        self.page.goto("https://app.zoom.us/wc/join")

        # Format meeting ID with spaces: "123 4567 8901"
        formatted_login_url = (
            self.new_login_url[:3]
            + " "
            + self.new_login_url[3:7]
            + " "
            + self.new_login_url[7:]
        )

        # Fill meeting ID input
        # Original used pyautogui.write() on Linux to work around send_keys issues.
        # Playwright's page.keyboard.type() works reliably on all platforms.
        meeting_id_input = self.page.locator("#joinMeeting input.join-meetingId")
        meeting_id_input.wait_for(state="attached")
        meeting_id_input.click()
        self.page.keyboard.type(formatted_login_url)

        # Click the Join button
        self.page.locator("#joinMeeting ~ footer button.btn-join").click()
        time.sleep(1)

        # ---- Switch into #webclient iframe ----
        # From this point all Zoom UI interactions go through self.zoom_frame
        self.zoom_frame = self.page.frame_locator("#webclient")

        # Fill password
        pass_element = self.zoom_frame.locator("#input-for-pwd")
        pass_element.wait_for(state="attached")
        pass_element.click()
        # Same as above — keyboard.type() replaces pyautogui.write() cross-platform
        self.page.keyboard.type(self.new_login_passwd)
        time.sleep(1)

        # Fill display name (hostname)
        host_element = self.zoom_frame.locator("#input-for-name")
        host_element.wait_for(state="attached")
        host_element.click()
        host_element.fill(self.hostname)
        time.sleep(1)

        # Click the final Join button on the preview screen
        self.zoom_frame.locator(
            ".preview-meeting-info button.preview-join-button"
        ).click()
        time.sleep(1)

        # Simulate mouse movement (same as ActionChains.move_by_offset)
        self.page.mouse.move(10, 20)
        time.sleep(1)

        # Audio Join 
        audio_join_btn = self.zoom_frame.locator(
            "button.footer-button-base__button.join-audio-container__btn"
        )
        audio_join_btn.wait_for(state="attached")

        # Click once to trigger audio join
        audio_join_btn.dispatch_event("click")
        time.sleep(1)

        btn_text = audio_join_btn.inner_text().lower()
        if btn_text == "join audio":
            print("Audio not joined — clicking again.")
            audio_join_btn.dispatch_event("click")
        elif btn_text == "unmute":
            print("Audio is muted — unmuting.")
            audio_join_btn.dispatch_event("click")
        elif btn_text == "mute":
            print("Audio already unmuted.")

        # Open audio options menu
        self.zoom_frame.locator("#audioOptionMenu").wait_for(state="attached")
        self.zoom_frame.locator("#audioOptionMenu button").dispatch_event("click")
        time.sleep(2)

        # Click "Audio Settings" inside the dropdown
        setting_options = self.zoom_frame.locator("#audioOptionMenu a").all()
        for el in setting_options:
            if el.inner_text() == "Audio Settings":
                el.click()
                break
        time.sleep(1)

        # Click the #video tab inside the Audio Settings panel
        self.zoom_frame.locator("#video").wait_for(state="attached")
        self.zoom_frame.locator("#video").dispatch_event("click")
        time.sleep(1)

        # Video Join
        video_join_btn = self.zoom_frame.locator(
            "button.footer-button-base__button.send-video-container__btn"
        )
        video_join_btn.wait_for(state="attached")
        video_join_btn.dispatch_event("click")

        btn_text = video_join_btn.inner_text().lower()
        if btn_text in ("join video", "start video"):
            print("Video not joined — clicking again.")
            video_join_btn.dispatch_event("click")
        elif btn_text == "stop video":
            print("Video already on.")

        # Open stats panel
        self.zoom_frame.locator("#stats").wait_for(state="attached")
        self.zoom_frame.locator("#stats").dispatch_event("click")
        time.sleep(1)

    # Stop / Leave Meeting

    def stop_zoom(self):
        # Click the Leave button in the footer
        self.zoom_frame.locator(
            ".footer__leave-btn-container button"
        ).wait_for(state="attached")
        self.zoom_frame.locator(
            ".footer__leave-btn-container button"
        ).dispatch_event("click")
        time.sleep(1)

        # Client sees "Leave Meeting" (not "End Meeting for All" which is host-only)
        # Using get_by_text to avoid strict mode violation if multiple buttons appear
        self.zoom_frame.get_by_text("Leave Meeting").wait_for(state="attached")
        self.zoom_frame.get_by_text("Leave Meeting").dispatch_event("click")
        time.sleep(1)

        self.browser.close()
        self._playwright.stop()

    # Start Zoom — Full flow including timing loop (mirrors original start_zoom)

    def start_zoom(self):
        self.setupdriver()

        self.get_meetin_link_and_password()
        self.zoom_login()

        self.get_stats_flags()
        time.sleep(5)

        # Wait for start/end time from server (up to 5 minutes)
        count = 0
        while self.start_time is None or self.end_time is None:
            count += 1
            if count > 60:
                print("Failed to retrieve start and end time after 5 minutes.")
                self.stop_zoom()
                sys.exit(1)
            self.get_start_and_end_time()
            time.sleep(5)

        print("end_time and start_time is", self.start_time, self.end_time)

        # Parse and localise times
        try:
            start_dt = datetime.fromisoformat(self.start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(self.end_time.replace("Z", "+00:00"))
            if start_dt.tzinfo is None:
                start_dt = self.tz.localize(start_dt)
            else:
                start_dt = start_dt.astimezone(self.tz)
            if end_dt.tzinfo is None:
                end_dt = self.tz.localize(end_dt)
            else:
                end_dt = end_dt.astimezone(self.tz)
        except Exception as e:
            print(f"Invalid start/end time format from server: {e}")
            self.stop_zoom()
            sys.exit(1)

        # Wait for test start time
        while start_dt > datetime.now(self.tz):
            time.sleep(2)
            print("Waiting for the start time...")

        # Run test monitoring loop
        while end_dt > datetime.now(self.tz):
            print("Monitoring the test...")
            if self.check_stop_signal():
                break
            stats = self.collecting_stats()  # uncomment to enable live stat capture
            self.send_stats_to_api(self.audio_stats, self.video_stats)
            time.sleep(1)

        print("Test has been completed.")
        self.stop_zoom()

    # Meeting ID / Password Fetch

    def get_meetin_link_and_password(self):
        try:
            self.get_login_id()
            self.get_login_passwd()
            print("Password and meeting ID fetched successfully for login.")
        except Exception as e:
            print("Error getting password and meeting ID:", e)

    # Stats Capture — Audio

    def capture_audio_stats(self):
        self.zoom_frame.locator("xpath=//*[@id='Audio']").click(force=True)
        time.sleep(2)

        def cell(row, col):
            return self.zoom_frame.locator(
                f"xpath=//*[@id='Audio-tab']/div/table/tbody/tr[{row}]/td[{col}]"
            ).inner_text()

        freq        = cell(1, 2).replace(" khz", "")
        freq_rec    = cell(1, 3).replace(" khz", "")
        lat         = cell(2, 2).replace(" ms", "")
        lat_rec     = cell(2, 3).replace(" ms", "")
        jitt        = cell(3, 2).replace(" ms", "")
        jitt_rec    = cell(3, 3).replace(" ms", "")
        pack        = re.sub(r"\s*\(.*?\)", "", cell(4, 2)).replace("%", "")
        pack_rec    = re.sub(r"\s*\(.*?\)", "", cell(4, 3)).replace("%", "")

        def z(v):
            return "0" if v == "-" else v

        return [z(freq), z(lat), z(jitt), z(pack),
                z(freq_rec), z(lat_rec), z(jitt_rec), z(pack_rec)]

    # Stats Capture — Video

    def capture_video_stats(self):
        self.zoom_frame.locator("xpath=//*[@id='Video']").click(force=True)
        time.sleep(2)

        def cell(row, col):
            return self.zoom_frame.locator(
                f"xpath=//*[@id='Video-tab']/div/table/tbody/tr[{row}]/td[{col}]"
            ).inner_text()

        latency        = cell(1, 2).replace(" ms", "")
        latency_rec    = cell(1, 3).replace(" ms", "")
        jitter         = cell(2, 2).replace(" ms", "")
        jitter_rec     = cell(2, 3).replace(" ms", "")
        pl             = re.sub(r"\s*\(.*?\)", "", cell(3, 2)).replace("%", "")
        pl_rec         = re.sub(r"\s*\(.*?\)", "", cell(3, 3)).replace("%", "")
        resolution     = cell(4, 2)
        resolution_rec = cell(4, 3)
        fps            = cell(5, 2).replace(" fps", "")
        fps_rec        = cell(5, 3).replace(" fps", "")

        def z(v):
            return "0" if v == "-" else v

        return [z(latency), z(jitter), z(pl), z(resolution), z(fps),
                z(latency_rec), z(jitter_rec), z(pl_rec), z(resolution_rec), z(fps_rec)]

    # Collecting Stats

    def collecting_stats(self):
        if self.audio:
            self.audio_stats = self.capture_audio_stats()
        else:
            self.audio_stats = ["0"] * 8
        if self.video:
            self.video_stats = self.capture_video_stats()
        else:
            self.video_stats = ["0"] * 10
        return self.audio_stats + self.video_stats

    # Flask API Calls (unchanged from original)

    def check_stop_signal(self):
        try:
            endpoint_url = f"{self.base_url}/check_stop"
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                stop_signal_from_server = response.json().get("stop", False)
                if stop_signal_from_server:
                    self.stop_signal = True
                    print("Stop signal received from the server. Exiting the loop.")
                else:
                    print("No stop signal received from the server. Continuing.")
            return self.stop_signal
        except Exception as e:
            print(f"Error checking stop signal: {e}")

    def get_stats_flags(self):
        endpoint_url = f"{self.base_url}/stats_opt"
        try:
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                data = response.json()
                self.audio = data.get("audio_stats")
                self.video = data.get("video_stats")
            else:
                print(f"Failed to fetch stats flag. Status code: {response.status_code}")
        except requests.RequestException as e:
            print(f"Request error: {e}")
        return None

    def send_stats_to_api(self, audio_stats, video_stats):
        endpoint_url = f"{self.base_url}/upload_stats"
        data = {
            self.hostname: {
                "timestamp": self.get_formated_time(datetime.now(self.tz).isoformat()),
                "audio_stats": {
                    "frequency_sent":      audio_stats[0],
                    "latency_sent":        audio_stats[1],
                    "jitter_sent":         audio_stats[2],
                    "packet_loss_sent":    audio_stats[3],
                    "frequency_received":  audio_stats[4],
                    "latency_received":    audio_stats[5],
                    "jitter_received":     audio_stats[6],
                    "packet_loss_received": audio_stats[7],
                },
                "video_stats": {
                    "latency_sent":               video_stats[0],
                    "jitter_sent":                video_stats[1],
                    "packet_loss_sent":           video_stats[2],
                    "resolution_sent":            video_stats[3],
                    "frames_per_second_sent":     video_stats[4],
                    "latency_received":           video_stats[5],
                    "jitter_received":            video_stats[6],
                    "packet_loss_received":       video_stats[7],
                    "resolution_received":        video_stats[8],
                    "frames_per_second_received": video_stats[9],
                },
            }
        }
        try:
            response = requests.post(endpoint_url, json=data)
            if response.status_code == 200:
                print("Stats sent successfully.")
            else:
                print(f"Failed to send stats. Status code: {response.status_code}")
        except requests.RequestException as e:
            print(f"Request error: {e}")

    def get_formated_time(self, timestamp_str):
        timestamp = datetime.fromisoformat(timestamp_str)
        return f"{timestamp.date()} {timestamp.hour}:{timestamp.minute:02}:{timestamp.second:02}"

    def get_login_id(self):
        endpoint_url = f"{self.base_url}/login_url"
        print(endpoint_url)
        try:
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                print("Remote login URL fetched successfully.")
                data = response.json()
                print(data, str(data))
                print(type(data))
                self.new_login_url = data.get("login_url")
                print("checking self.new_login_url", self.new_login_url)
            else:
                print(f"Failed to fetch remote login URL. Status code: {response.status_code}")
        except requests.RequestException as e:
            print(f"Request error: {e}")

    def get_login_passwd(self):
        endpoint_url = f"{self.base_url}/login_passwd"
        try:
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                print("Remote login password fetched successfully.")
                data = response.json()
                self.new_login_passwd = data.get("login_passwd")
                print("checking self.new_login_passwd", self.new_login_passwd)
            else:
                print(f"Failed to fetch remote login password. Status code: {response.status_code}")
        except requests.RequestException as e:
            print(f"Request error: {e}")

    def get_start_and_end_time(self):
        endpoint_url = f"{self.base_url}/get_start_end_time"
        try:
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                data = response.json()
                self.start_time = data.get("start_time")
                self.end_time = data.get("end_time")
            else:
                print(f"Failed to fetch start/end time. Status code: {response.status_code}")
        except requests.RequestException as e:
            print(f"Request error: {e}")
        return None



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zoom Client Automation Script (Playwright)")
    parser.add_argument("--ip", required=True, help="Server endpoint IP")
    parser.add_argument("--env", action="extend", nargs="+", default=[])

    args = parser.parse_args()
    for argument in args.env:
        key, val = argument.split("=", 1)
        os.environ[key] = val
    print(os.environ)

    zoom_client = ZoomClient(server_ip=args.ip)
    zoom_client.start_zoom()