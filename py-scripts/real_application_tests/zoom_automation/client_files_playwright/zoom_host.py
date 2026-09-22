import time
import csv
import sys
import re
import pytz
import os
import requests
import socket
import argparse
import json

from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


class ZoomHost:
    def __init__(self, server_ip=None):
        self.server_ip = server_ip
        self.base_url = f"http://{self.server_ip}:5000"
        self.new_login_url = None
        self.new_login_passwd = None
        self.login_email = None
        self.login_passwd = None
        self.meeting_link = None

        # Playwright objects
        self._playwright = None
        self.browser = None
        self.context = None
        self.page = None

        # zoom_frame is a FrameLocator — used for all element interactions
        # inside the #webclient iframe (equivalent to driver.switch_to.frame)
        self.zoom_frame = None

        # zoom_frame_handle is the actual Frame object — needed for:
        #   - frame.url  (to extract meeting link)
        #   - frame.evaluate()  (to run JS inside the iframe)
        self.zoom_frame_handle = None

        self.participants = None
        self.participants_required = None
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
                # Media / screen share flags (equivalent to Selenium chrome_options)
                "--use-fake-ui-for-media-stream",
                "--auto-select-desktop-capture-source=Entire screen",

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

        # Restore saved session if it exists (replaces pickle cookie logic)
        state_file = "state.json"
        context_args = dict(
            permissions=["camera", "microphone", "notifications"],
            accept_downloads=True,
        )
        if os.path.exists(state_file):
            context_args["storage_state"] = state_file
            print("Found saved session — will attempt to restore.")

        self.context = self.browser.new_context(**context_args)

        # Global default timeout — equivalent to WebDriverWait(driver, 90)
        self.context.set_default_timeout(90_000)

        self.page = self.context.new_page()
        self.page.set_viewport_size({"width": 1920, "height": 1080})

    # Session / Cookie Helpers

    def saveCookies(self):
        """Save full browser session (cookies + localStorage) to state.json.
        Replaces pickle-based cookie save."""
        self.context.storage_state(path="state.json")
        print("Session saved to state.json.")

    def loadCookies(self):
        """No-op: session restoration is handled at context creation in setupdriver().
        Kept so call-sites in zoom_login() don't need changing."""
        pass

    # Zoom Login

    def zoom_login(self):
        print("Getting host email and password")
        self.login_email = self.get_host_email().strip()
        self.login_passwd = self.get_host_password().strip()
        print(self.login_email)
        print(self.login_passwd)

        login_data = {
            "login_email": self.login_email,
            "login_passwd": self.login_passwd,
        }
        credentials_match = False
        file_path = "login_data.json"

        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    existing_data = {}
            if existing_data == login_data:
                credentials_match = True
        else:
            existing_data = {}

        if not credentials_match:
            with open(file_path, "w") as f:
                json.dump(login_data, f, indent=4)
            credentials_match = False

        # Navigate to Zoom web client
        self.page.goto("https://app.zoom.us/wc")

        if credentials_match:
            # loadCookies() is a no-op — session already loaded at context creation
            self.loadCookies()
            self.page.reload()

        # Try clicking "Sign In" button if present (new session)
        try:
            sign_in_btn = self.page.locator("button[aria-label='Sign In']")
            sign_in_btn.wait_for(state="attached", timeout=5_000)
            sign_in_btn.click()
            print("Clicked Sign In button.")
        except PlaywrightTimeoutError:
            print("Loaded session through saved state.")

        # If redirected to signin page, perform full login
        if "signin" in self.page.url:
            print(self.login_email)
            print(self.login_passwd)
            self.page.locator("input#email").fill(self.login_email)
            time.sleep(1)
            self.page.locator("#signin_btn_next > span").click()
            self.page.locator("input#password").fill(self.login_passwd)
            time.sleep(5)
            self.page.locator("button#js_btn_login").click()
            self.page.wait_for_selector("button.main__action-btn")
            time.sleep(5)
            self.saveCookies()
        else:
            print("Previous session loaded.")

        # Click "New Meeting" button specifically (page has 3 .main__action-btn buttons:
        # New Meeting, Join, Schedule — we always want the host to start a new meeting)
        self.page.locator("button.main__action-btn[aria-label='New meeting']").click()

        # Handle #webclient iframe 
        # Check if user was already in a meeting and needs to end it first
        try:
            webclient_frame = self.page.frame_locator("#webclient")
            end_btn = webclient_frame.locator("#btn_end_meeting")
            end_btn.wait_for(state="attached", timeout=10_000)
            end_btn.click()
            print("User was already in the meeting — ended previous session.")
        except PlaywrightTimeoutError:
            print("New user login.")
        except Exception as e:
            print(f"Iframe check error: {e}")

        time.sleep(2)
        print("After 2 sec sleep")

        # Get a persistent FrameLocator for all subsequent in-meeting interactions
        # (equivalent to driver.switch_to.frame(vel) — but Playwright never "forgets"
        #  the outer page, so no switch_to.default_content() needed)

        self.page.locator("#webclient").wait_for(timeout=30000)

        self.zoom_frame = self.page.frame_locator("#webclient")

        # Also keep a direct Frame handle for .url and .evaluate() calls
        self._refresh_frame_handle()

        time.sleep(2)
        print("Iframe context ready.")

        # Simulate mouse movement (same as ActionChains.move_by_offset)
        self.page.mouse.move(10, 20)

        timeout = time.time() + 15
        meeting_url = None

        while time.time() < timeout:
            self._refresh_frame_handle()
            if self.zoom_frame_handle:
                current_url = self.zoom_frame_handle.url
                # print("Current iframe URL:", current_url)

                if "pwd=" in current_url:
                    meeting_url = current_url
                    break

            time.sleep(1)

        self.meeting_link = self.page.url
        # print("page url:", self.page.url)
        # print("frame url:", self.zoom_frame_handle.url)
        # print("frame href:", self.zoom_frame_handle.evaluate("window.location.href"))
        # print(f"Meeting link: {self.meeting_link}")

        # # Grab the meeting URL from inside the iframe
        # self.meeting_link = self.zoom_frame_handle.url if self.zoom_frame_handle else self.page.url
        print(f"Meeting link: {self.meeting_link}")

        self.page.mouse.move(10, 20)
        time.sleep(1)

        self.keep_footer_visible()

        try:
            time.sleep(3)
            self.share_screen()
        except Exception as e:
            print(f"Error sharing screen: {e}")

        #  Audio Join 
        audio_join_btn = self.zoom_frame.locator(
            "button.footer-button-base__button.join-audio-container__btn"
        )
        audio_join_btn.wait_for(state="attached")

        # Click once to trigger the join
        self.zoom_frame.locator(
            "button.footer-button-base__button.join-audio-container__btn"
        ).dispatch_event("click")
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
            text = el.inner_text()
            print(text)
            if text == "Audio Settings":
                print("Clicking Audio Settings")
                el.click()
                break
        time.sleep(1)

        # Click the #video tab (inside Audio Settings panel)
        self.zoom_frame.locator("#video").wait_for(state="attached")
        self.zoom_frame.locator("#video").dispatch_event("click")
        time.sleep(1)

        #  Video Join 
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

        self.send_meetin_link_and_password()

    # Screen Share

    def share_screen(self):
        print("Sharing screen now...")
        try:
            share_btn = self.zoom_frame.locator(
                ".footer-button-base__button.sharing-entry-button-container"
            )
            share_btn.wait_for(state="attached")
            share_btn.dispatch_event("click")
            print("[INFO] Share Screen clicked in Zoom UI.")

            time.sleep(2)
            print("[INFO] Entire Screen shared successfully via Chrome flags.")

            # Mute the screen share audio if the button appears
            try:
                pause_audio_btn = self.zoom_frame.locator(
                    "button[aria-label='Pause Audio Share']"
                )
                pause_audio_btn.wait_for(state="attached", timeout=5_000)
                pause_audio_btn.dispatch_event("click")
                print("[INFO] Screen share audio has been muted/paused.")
            except PlaywrightTimeoutError:
                print("[INFO] No 'Pause Audio Share' button found — skipping.")

        except Exception as e:
            print(f"Error in sharing screen: {e}")

    # Footer Visibility

    def keep_footer_visible(self):
        print("[INFO] Locking Zoom footer visible...")
        try:
            js_script = """
                if (!window.keepZoomActiveInterval) {
                    window.keepZoomActiveInterval = setInterval(() => {
                        document.dispatchEvent(new MouseEvent('mousemove', {
                            bubbles: true,
                            cancelable: true,
                            clientX: 100,
                            clientY: 100
                        }));
                    }, 2000);
                }
            """
            # Run on the iframe's JS context so Zoom's own event listeners react
            if self.zoom_frame_handle:
                self.zoom_frame_handle.evaluate(js_script)
            else:
                self.page.evaluate(js_script)
            print("[INFO] Footer is now locked to visible.")
        except Exception as e:
            print(f"[ERROR] Failed to lock footer visibility: {e}")

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

        latency     = cell(1, 2).replace(" ms", "")
        latency_rec = cell(1, 3).replace(" ms", "")
        jitter      = cell(2, 2).replace(" ms", "")
        jitter_rec  = cell(2, 3).replace(" ms", "")

        pl          = re.sub(r"\s*\(.*?\)", "", cell(3, 2)).replace("%", "")
        pl_rec      = re.sub(r"\s*\(.*?\)", "", cell(3, 3)).replace("%", "")

        resolution     = cell(4, 2)
        resolution_rec = cell(4, 3)

        fps     = cell(5, 2).replace(" fps", "")
        fps_rec = cell(5, 3).replace(" fps", "")

        def z(v):
            return "0" if v == "-" else v

        return [z(latency), z(jitter), z(pl), z(resolution), z(fps),
                z(latency_rec), z(jitter_rec), z(pl_rec), z(resolution_rec), z(fps_rec)]

    # Participant Count Monitor

    def monitor_client_count(self):
        try:
            counter_text = self.zoom_frame.locator(
                ".footer-button__number-counter"
            ).inner_text().strip()

            if not counter_text:
                return 1
            if not counter_text.isdigit():
                print(f"Unexpected participant counter value: {counter_text!r}")
                return 1
            return int(counter_text)
        except Exception as e:
            print("Meeting UI unavailable, assuming meeting ended.")
            return 0

    # Wait for Clients to Exit

    def wait_for_exit(self):
        print("Waiting for clients to disconnect...")
        tries = 0
        count = self.monitor_client_count()
        print(count, "participant count")

        while count > 1:
            print(count, "participant count")
            time.sleep(2)
            tries += 1
            if tries > 20:
                print("Max tries reached for client disconnection wait.")
                break
            count = self.monitor_client_count()

    # Stop / Leave Meeting

    def stop_zoom(self):
        self.zoom_frame.locator(
            ".footer__leave-btn-container button"
        ).wait_for(state="attached")
        self.zoom_frame.locator(
            ".footer__leave-btn-container button"
        ).dispatch_event("click")
        time.sleep(1)

        # Two buttons share the same class: "End Meeting for All" and "Leave Meeting"
        # As host we always want "End Meeting for All"
        self.zoom_frame.get_by_text("End Meeting for All").wait_for(state="attached")
        self.zoom_frame.get_by_text("End Meeting for All").dispatch_event("click")

        print("Waiting for dashboard to register past meeting...")
        download_csv = self.get_download_csv_flag()
        if download_csv:
            time.sleep(100)
            self.download_csv()

        self.browser.close()
        self._playwright.stop()

    # Download CSV from Zoom Dashboard

    def download_csv(self):
        print("Meeting link is", self.new_login_url)

        # Navigate away from the meeting — back to main page context
        self.page.goto(
            "https://www.zoom.us/account/metrics/dashboard/home/#/pastMeetings"
        )

        cleaned_id = (
            self.new_login_url[:3]
            + " "
            + self.new_login_url[3:7]
            + " "
            + self.new_login_url[7:]
        )
        print(self.new_login_url, "cleaned_id:", cleaned_id)

        xpath = f"//p[contains(@class, 'ellipsis') and contains(text(), '{cleaned_id}')]"

        # Find meeting row — retry logic preserved from original
        current_elem = self.page.locator(f"xpath={xpath}")
        try:
            current_elem.wait_for(state="attached")
        except PlaywrightTimeoutError:
            print("Meeting row not found — retrying in 15 seconds...")
            time.sleep(15)
            self.page.reload()
            current_elem.wait_for(state="attached")

        outer_html = current_elem.evaluate("el => el.outerHTML")
        print("current outer", outer_html)
        print("current text", current_elem.inner_text())

        # Find the anchor tag in the parent element
        anchor = current_elem.locator("xpath=../a")
        try:
            anchor.wait_for(state="attached", timeout=5_000)
        except PlaywrightTimeoutError:
            print("Anchor not found — refreshing in 15 seconds...")
            time.sleep(15)
            try:
                self.page.reload()
                current_elem.wait_for(state="attached")
                anchor.wait_for(state="attached", timeout=5_000)
            except PlaywrightTimeoutError:
                print("Still no anchor — waiting 60 seconds for last attempt...")
                time.sleep(60)
                self.page.reload()
                current_elem.wait_for(state="attached")
                anchor.wait_for(state="attached")

        href = anchor.get_attribute("href")
        print(href)

        # Navigate to meeting detail dashboard
        self.page.goto(href)

        export_xpath = "//div[contains(@class, 'detail-operation') and contains(@class, 'detial-operation')]//button[.//span[contains(translate(., 'EXPORT', 'export'), 'export')]]"
        export_btn = self.page.locator(f"xpath={export_xpath}")
        export_btn.wait_for(state="visible")
        export_btn.click()
        print("Clicked Export button.")

        # Handle modal -> "Go to Downloads Page"
        try:
            modal_btn = self.page.locator(
                "xpath=//button[.//span[contains(text(), 'Go to Downloads Page')]]"
            )
            modal_btn.wait_for(state="visible", timeout=25_000)
            modal_btn.click()
            print("Clicked 'Go to Downloads Page'.")
        except PlaywrightTimeoutError:
            print("Modal did not appear — refreshing and retrying export...")
            self.page.reload()
            export_btn.wait_for(state="visible")
            export_btn.click()
            modal_btn.wait_for(state="visible")
            modal_btn.click()
            print("Clicked 'Go to Downloads Page' after retry.")

        print("Waiting for download page to load...")
        time.sleep(15)

        # Switch to the newly opened tab (equivalent to driver.switch_to.window)
        pages = self.context.pages
        download_page = pages[-1]
        download_page.bring_to_front()
        download_page.reload()
        download_page.wait_for_load_state("networkidle")

        filename = download_page.locator(
            "table#download_queue_list tbody tr:nth-of-type(1) td.col1"
        ).inner_text()
        print(f"Download file is: {filename}")

        # Use Playwright's download event to capture the file
        with self.context.expect_page() as _:
            pass  # absorb any extra page events

        with download_page.expect_download() as download_info:
            download_page.locator(
                "table#download_queue_list tbody tr:nth-of-type(1) button"
            ).click()
            print("Clicked 'Download' button.")

        download = download_info.value
        save_path = os.path.join(os.getcwd(), filename + ".csv")
        download.save_as(save_path)
        print(f"File saved to: {save_path}")

        self._process_downloaded_csv(save_path, filename)

    def _process_downloaded_csv(self, file_path, filename):
        """Read the downloaded CSV and POST it to the Flask server."""
        try:
            with open(file_path, newline="") as csvfile:
                reader = csv.reader(csvfile)
                rows = list(reader)

            endpoint_url = f"{self.base_url}/upload_csv"
            print(endpoint_url)
            payload = {"filename": os.path.basename(file_path), "rows": rows}
            print(payload)
            requests.post(endpoint_url, json=payload)
        except Exception as e:
            print(f"Error reading/uploading CSV: {e}")

    # Meeting Link / Password Extraction

    # def send_meetin_link_and_password(self):
    #     pattern = r"https://\S+?\.zoom\.us/(?:j|wc)/(?P<meeting_id>\d+)\S*?pwd=(?P<password>[^\s&]+)"
    #     match = re.search(pattern, self.meeting_link)
    #     if match:
    #         self.new_login_url = match.group("meeting_id")
    #         self.new_login_passwd = match.group("password")
    #         print("Meeting ID and password:", self.new_login_url, self.new_login_passwd)
    #         if self.new_login_url:
    #             self.update_login_email(self.new_login_url)
    #         if self.new_login_passwd:
    #             self.update_login_passwd(self.new_login_passwd)
    #         print("Password and meeting ID updated successfully.")

    def send_meetin_link_and_password(self):
        pattern = r"https://\S+?\.zoom\.us/(?:j|wc)/(?P<meeting_id>\d+)(?:\S*?pwd=(?P<password>[^\s&]+))?"
        match = re.search(pattern, self.meeting_link)

        if match:
            self.new_login_url = match.group("meeting_id")
            self.new_login_passwd = match.group("password")

            print("Meeting ID:", self.new_login_url)
            print("Password:", self.new_login_passwd)

            if self.new_login_url:
                self.update_login_email(self.new_login_url)

            if self.new_login_passwd:
                self.update_login_passwd(self.new_login_passwd)

    # Start Zoom (entry point)

    def start_zoom(self):
        self.setupdriver()
        self.participants_required = self.get_required_participants()
        self.zoom_login()
        self.update_login_completed()
        time.sleep(1)

    # Internal Helper — Frame Handle Refresh

    def _refresh_frame_handle(self):
        try:
            iframe_el = self.page.locator("#webclient").element_handle()
            if iframe_el:
                self.zoom_frame_handle = iframe_el.content_frame()
            else:
                self.zoom_frame_handle = None
        except Exception as e:
            print(f"Could not resolve frame handle: {e}")
            self.zoom_frame_handle = None

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

    # Test Start / Participant Tracking

    def set_start_test(self, flag=False):
        try:
            self.participants = self.monitor_client_count()
            self.set_participants()
            print(self.participants_required, self.participants)
            if self.participants_required == self.participants:
                self.update_start_test()
            elif flag:
                self.update_start_test()
        except Exception as e:
            print("Error in set_start_test:", e)

    # Time Formatting

    def get_formated_time(self, timestamp_str):
        timestamp = datetime.fromisoformat(timestamp_str)
        return f"{timestamp.date()} {timestamp.hour}:{timestamp.minute:02}:{timestamp.second:02}"

    # Flask API Calls (unchanged from original)

    def get_host_email(self):
        endpoint_url = f"{self.base_url}/get_host_email"
        print(endpoint_url)
        try:
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                return response.json().get("host_email", None)
            print(f"Failed to fetch host email. Status: {response.status_code}")
        except requests.RequestException as e:
            print(f"Request error: {e}")
        return None

    def get_host_password(self):
        endpoint_url = f"{self.base_url}/get_host_passwd"
        try:
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                return response.json().get("host_passwd", None)
            print(f"Failed to fetch host password. Status: {response.status_code}")
        except requests.RequestException as e:
            print(f"Request error: {e}")
        return None

    def update_login_email(self, new_login_url):
        endpoint_url = f"{self.base_url}/login_url"
        try:
            response = requests.post(endpoint_url, json={"login_url": new_login_url})
            if response.status_code == 200:
                print("Remote login URL updated successfully.")
            else:
                print(f"Failed to update login URL. Status: {response.status_code}")
        except requests.RequestException as e:
            print(f"Request error: {e}")

    def update_login_passwd(self, new_login_passwd):
        endpoint_url = f"{self.base_url}/login_passwd"
        try:
            response = requests.post(endpoint_url, json={"login_passwd": new_login_passwd})
            if response.status_code == 200:
                print("Remote login password updated successfully.")
            else:
                print(f"Failed to update login password. Status: {response.status_code}")
        except requests.RequestException as e:
            print(f"Request error: {e}")

    def update_login_completed(self):
        endpoint_url = f"{self.base_url}/login_completed"
        try:
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                print("Login completed status updated successfully.")
            else:
                print(f"Failed to update login completed. Status: {response.status_code}")
        except requests.RequestException as e:
            print(f"Request error: {e}")

    def update_start_test(self):
        endpoint_url = f"{self.base_url}/test_started"
        try:
            response = requests.post(endpoint_url, json={"test_started": True})
            if response.status_code == 200:
                print("Test started status updated successfully.")
            else:
                print(f"Failed to update test started. Status: {response.status_code}")
        except requests.RequestException as e:
            print(f"Request error: {e}")

    def set_participants(self):
        endpoint_url = f"{self.base_url}/set_participants_joined"
        try:
            response = requests.post(
                endpoint_url, json={"participants_joined": self.participants}
            )
            if response.status_code == 200:
                print("Participants joined updated successfully.")
            else:
                print(f"Failed to update participants. Status: {response.status_code}")
        except requests.RequestException as e:
            print(f"Request error: {e}")

    def get_required_participants(self):
        endpoint_url = f"{self.base_url}/get_participants_req"
        try:
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                return response.json().get("participants", None)
            print(f"Failed to fetch required participants. Status: {response.status_code}")
        except requests.RequestException as e:
            print(f"Request error: {e}")
        return None

    def get_start_and_end_time(self):
        endpoint_url = f"{self.base_url}/get_start_end_time"
        try:
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                data = response.json()
                self.start_time = data.get("start_time")
                self.end_time = data.get("end_time")
            else:
                print(f"Failed to fetch start/end time. Status: {response.status_code}")
        except requests.RequestException as e:
            print(f"Request error: {e}")
        return None

    def send_client_disconnection(self):
        endpoint_url = f"{self.base_url}/clients_disconnected"
        try:
            response = requests.post(
                endpoint_url, json={"clients_disconnected": True}
            )
            if response.status_code == 200:
                print("Client disconnection updated successfully.")
            else:
                print(f"Failed to update disconnection. Status: {response.status_code}")
        except requests.RequestException as e:
            print(f"Request error: {e}")

    def get_stats_flags(self):
        endpoint_url = f"{self.base_url}/stats_opt"
        try:
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                data = response.json()
                self.audio = data.get("audio_stats")
                self.video = data.get("video_stats")
            else:
                print(f"Failed to fetch stats flags. Status: {response.status_code}")
        except requests.RequestException as e:
            print(f"Request error: {e}")
        return None

    def check_stop_signal(self):
        try:
            endpoint_url = f"{self.base_url}/check_stop"
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                stop_signal_from_server = response.json().get("stop", False)
                if stop_signal_from_server:
                    self.stop_signal = True
                    print("Stop signal received from server.")
                else:
                    print("No stop signal. Continuing.")
            return self.stop_signal
        except Exception as e:
            print(f"Error checking stop signal: {e}")

    def get_download_csv_flag(self):
        try:
            endpoint_url = f"{self.base_url}/download_csv"
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                return response.json().get("download_csv", False)
            return False
        except Exception as e:
            print(f"Error checking download CSV flag: {e}")
            return False

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
                    "latency_sent":              video_stats[0],
                    "jitter_sent":               video_stats[1],
                    "packet_loss_sent":          video_stats[2],
                    "resolution_sent":           video_stats[3],
                    "frames_per_second_sent":    video_stats[4],
                    "latency_received":          video_stats[5],
                    "jitter_received":           video_stats[6],
                    "packet_loss_received":      video_stats[7],
                    "resolution_received":       video_stats[8],
                    "frames_per_second_received": video_stats[9],
                },
            }
        }
        try:
            response = requests.post(endpoint_url, json=data)
            if response.status_code == 200:
                print("Stats sent successfully.")
            else:
                print(f"Failed to send stats. Status: {response.status_code}")
        except requests.RequestException as e:
            print(f"Request error: {e}")




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zoom Automation Script (Playwright)")
    parser.add_argument("--ip", required=True, help="Server endpoint IP")
    parser.add_argument("--env", action="extend", nargs="+", default=[])

    args = parser.parse_args()
    for argument in args.env:
        key, val = argument.split("=", 1)
        os.environ[key] = val
    print(os.environ)

    zoom_host = ZoomHost(server_ip=args.ip)

    zoom_host.start_zoom()
    wait_limit = datetime.now() + timedelta(seconds=120)
    zoom_host.get_stats_flags()

    # Wait for required participants to join
    while True:
        zoom_host.set_start_test()
        if (
            zoom_host.participants_required is not None
            and zoom_host.participants_required == zoom_host.participants
        ):
            print(zoom_host.participants_required)
            print("Required participants connected:", zoom_host.participants)
            break
        elif datetime.now() > wait_limit:
            print(
                "Wait limit reached. Starting with available clients.",
                zoom_host.participants_required,
                zoom_host.participants,
            )
            zoom_host.set_start_test(flag=True)
            break
        time.sleep(5)

    # Wait for start/end time from server
    count = 0
    while zoom_host.start_time is None or zoom_host.end_time is None:
        count += 1
        if count > 24:
            print("Start/end time not received after 2 minutes. Exiting.")
            zoom_host.browser.close()
            zoom_host._playwright.stop()
            sys.exit(1)
        print("Waiting for start and end time from server...")
        zoom_host.get_start_and_end_time()
        time.sleep(5)

    print("Start/end time received:", zoom_host.start_time, zoom_host.end_time)

    # Parse and localise times
    try:
        start_dt = datetime.fromisoformat(zoom_host.start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(zoom_host.end_time.replace("Z", "+00:00"))
        if start_dt.tzinfo is None:
            start_dt = zoom_host.tz.localize(start_dt)
        else:
            start_dt = start_dt.astimezone(zoom_host.tz)
        if end_dt.tzinfo is None:
            end_dt = zoom_host.tz.localize(end_dt)
        else:
            end_dt = end_dt.astimezone(zoom_host.tz)
    except Exception as e:
        print(f"Invalid start/end time format: {e}")
        zoom_host.browser.close()
        zoom_host._playwright.stop()
        sys.exit(1)

    # Wait for test start time
    while start_dt > datetime.now(zoom_host.tz):
        time.sleep(2)
        print("Waiting for start time...")

    # Run test monitoring loop
    while end_dt > datetime.now(zoom_host.tz):
        print("Monitoring the test...")
        if zoom_host.check_stop_signal():
            break
        stats = zoom_host.collecting_stats()  
        zoom_host.send_stats_to_api(zoom_host.audio_stats, zoom_host.video_stats)
        time.sleep(2)

    print("Test completed.")
    zoom_host.wait_for_exit()
    zoom_host.stop_zoom()
    zoom_host.send_client_disconnection()
