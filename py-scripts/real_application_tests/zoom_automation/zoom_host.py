import time
import csv
import sys
import re
import pytz
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import os
import requests
import socket
import argparse
import json
import pickle
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_log_fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_log_fmt)
logger.addHandler(_console_handler)

_file_handler = logging.FileHandler(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "zoom_host.log"),
    mode="w",
)
_file_handler.setFormatter(_log_fmt)
logger.addHandler(_file_handler)


class ZoomHost:
    def __init__(self, server_ip=None):
        self.server_ip = server_ip
        self.base_url = f"http://{self.server_ip}:5000"
        # self.base_url = "http://10.253.8.108:5000"
        self.meeting_id = None
        self.meeting_passwd = None
        self.login_email = None
        self.login_passwd = None
        self.meeting_link = None
        self.wait = None
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

    def setupdriver(self):
        chrome_options = Options()

        prefs = {
            "profile.managed_default_content_settings.notifications": 1,
            "profile.managed_default_content_settings.geolocation": 1,
            "profile.managed_default_content_settings.media_stream": 1,
            "download.default_directory": os.getcwd(),  # Change default directory
            "download.prompt_for_download": False,  # Disable download prompt
            "download.directory_upgrade": True,
        }

        # Performance-related options
        chrome_options.add_argument("--process-per-site")
        chrome_options.add_argument("--renderer-process-limit=4")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--enable-low-res-tiling")
        chrome_options.add_argument("--force-gpu-mem-available-mb=4096")
        chrome_options.add_argument("--memory-pressure-thresholds-mb=2048")
        # chrome_options.add_argument("--enable-quic")

        # chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_argument("--use-fake-ui-for-media-stream")
        chrome_options.add_argument(
            "--auto-select-desktop-capture-source=Entire screen"
        )

        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.maximize_window()
        self.wait = WebDriverWait(self.driver, 90)

    def share_screen(self):
        logger.info("sharing screen now")
        try:
            # Wait for the Zoom share button to be present in the DOM
            self.wait.until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        ".footer-button-base__button.sharing-entry-button-container",
                    )
                )
            )

            # Click the Zoom share button
            self.driver.execute_script(
                "document.querySelector('.footer-button-base__button.sharing-entry-button-container').click()"
            )
            logger.info("Share Screen clicked in Zoom UI.")

            # Give the WebRTC connection a moment to establish
            time.sleep(2)

            logger.info("Entire Screen shared successfully via Chrome flags")

            # We use a short wait here because if it's not there, we don't want to wait 90 seconds
            pause_audio_btn = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button[aria-label='Pause Audio Share']")
                )
            )

            # Click it to pause the audio sharing
            self.driver.execute_script("arguments[0].click();", pause_audio_btn)
            logger.info("Screen share audio has been muted/paused.")

        except Exception as e:
            logger.error(f"Error in sharing screen: {e}")

    def saveCookies(self):
        # Save cookies to a file
        cookies = self.driver.get_cookies()
        with open("cookies.pkl", "wb") as file:
            pickle.dump(cookies, file)
        logger.info("Cookies saved.")

    def loadCookies(self):
        # Load cookies from a file
        try:
            with open("cookies.pkl", "rb") as file:
                if os.path.getsize("cookies.pkl") > 0:  # Ensure the file is not empty
                    cookies = pickle.load(file)
                    for cookie in cookies:
                        self.driver.add_cookie(cookie)
                    logger.info("Cookies loaded.")
                else:
                    logger.warning("Cookies file is empty. Proceeding with new login.")
        except FileNotFoundError:
            logger.warning("No cookies file found. Proceeding with new login.")
        except EOFError:
            logger.warning(
                "Cookies file is corrupted or empty. Proceeding with new login."
            )

    def dynamic_wait(self, waittime):
        return WebDriverWait(self.driver, waittime)

    def start_zoom(self):
        self.setupdriver()
        self.participants_required = self.get_required_participants()
        self.zoom_login()
        # After starting Zoom, retrieve meeting ID and meeting password
        self.update_login_completed()
        time.sleep(1)

    def keep_footer_visible(self):
        logger.info("Disabling Zoom's auto-hide footer...")
        try:
            # Injects a background script that fires a fake mouse movement every 2 seconds
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
            self.driver.execute_script(js_script)
            logger.info("Footer is now locked to visible.")
        except Exception as e:
            logger.error(f"Failed to lock footer visibility: {e}")

    def zoom_login(self):
        logger.info("getting host email and password")
        self.login_email = self.get_host_email()
        self.login_passwd = self.get_host_password()
        self.login_email = self.login_email.strip()
        self.login_passwd = self.login_passwd.strip()

        if not self.login_email or not self.login_passwd:
            logger.error("Failed to Fetch login credentials from the server.")
            self.driver.quit()
            sys.exit(1)

        # Create a dictionary with the login details
        login_data = {
            "login_email": self.login_email,
            "login_passwd": self.login_passwd,
        }

        # Variable to store whether the credentials match
        credentials_match = False

        # Path to the JSON file
        file_path = "login_data.json"

        # Check if the file exists
        if os.path.exists(file_path):
            # Read the existing JSON data
            with open(file_path, "r") as json_file:
                try:
                    existing_data = json.load(json_file)
                except json.JSONDecodeError:
                    existing_data = {}

            # Compare the existing data with the new login data
            if existing_data == login_data:
                credentials_match = True
        else:
            # If the file doesn't exist, treat it as new data
            existing_data = {}

        if not credentials_match:
            with open(file_path, "w") as json_file:
                json.dump(login_data, json_file, indent=4)
                credentials_match = False

        self.driver.get("https://app.zoom.us/wc")
        if credentials_match:

            self.loadCookies()
            self.driver.refresh()
        try:
            element = self.dynamic_wait(5).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "button[aria-label='Sign In']")
                )
            )
            self.driver.execute_script("arguments[0].click();", element)
            logger.info("clicked sign in button")
        except Exception:
            logger.info("Loaded session through cookies")

        if "signin" in self.driver.current_url:

            # if sys.platform.lower()=="linux":
            #     email_field=self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#email")))
            #     for char in self.login_email:
            #         email_field.send_keys(char)
            #     pass_field=self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#password")))
            #     for char in self.login_passwd:
            #         pass_field.send_keys(char)

            # pyautogui.write(self.login_email)
            # time.sleep(2)
            # # password_field = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#password")))
            # self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input#password"))).click()

            # #self.driver.execute_script("arguments[0].click();", password_field)
            # pyautogui.write(self.login_passwd)

            # else:
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input#email"))
            ).send_keys(self.login_email)
            time.sleep(1)
            self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "#signin_btn_next > span"))
            ).click()
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input#password"))
            ).send_keys(self.login_passwd)
            time.sleep(5)
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button#js_btn_login"))
            ).click()
            self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "button.main__action-btn")
                )
            )
            time.sleep(5)
            self.saveCookies()

        else:
            logger.info("previous session loaded")

        self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "button.main__action-btn"))
        ).click()

        try:

            iframe = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "webclient"))
            )
            self.driver.switch_to.frame(iframe)

            try:
                element = self.dynamic_wait(5).until(
                    EC.presence_of_element_located((By.ID, "btn_end_meeting"))
                )
                element.click()

                logger.info(
                    "User was already in the meeting and has been removed to start a new session."
                )
            except Exception:
                logger.info("new user login")

            self.driver.switch_to.default_content()
            logger.info("Clicked the element inside the iframe.")
        except Exception as e:
            logger.error(f"Error clicking the element inside the iframe: {str(e)}")

        time.sleep(2)
        vel = self.wait.until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="webclient"]'))
        )
        self.driver.switch_to.frame(vel)
        time.sleep(2)
        action = webdriver.ActionChains(self.driver)

        action.move_by_offset(10, 20).perform()

        self.meeting_link = self.driver.current_url
        action.move_by_offset(10, 20).perform()
        time.sleep(1)
        audio_join_btn = self.wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    ".footer-button-base__button.join-audio-container__btn",
                )
            )
        )

        self.driver.execute_script(
            "document.querySelector('button.footer-button-base__button.join-audio-container__btn').click()"
        )
        time.sleep(1)
        if audio_join_btn.text.lower() == "join audio":
            logger.info("audio not joined")
            self.driver.execute_script(
                "document.querySelector('button.footer-button-base__button.join-audio-container__btn').click()"
            )

        elif audio_join_btn.text.lower() == "unmute":
            logger.info("it is muted")
            self.driver.execute_script(
                "document.querySelector('button.footer-button-base__button.join-audio-container__btn').click()"
            )

        elif audio_join_btn.text.lower() == "mute":
            logger.info("already unmuted")
        self.wait.until(
            EC.presence_of_element_located((By.XPATH, "//*[@id='audioOptionMenu']"))
        )
        self.driver.execute_script(
            "document.querySelector('#audioOptionMenu button').click()"
        )
        time.sleep(2)

        setting_options = self.driver.find_elements(
            By.CSS_SELECTOR, "#audioOptionMenu a"
        )
        for el in setting_options:
            logger.info(el.text)
            if el.text == "Audio Settings":
                logger.info(el.text)
                el.click()
                break
        time.sleep(1)
        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#video")))
        self.driver.execute_script("document.querySelector('#video').click()")
        time.sleep(1)
        video_join_btn = self.wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    ".footer-button-base__button.send-video-container__btn",
                )
            )
        )

        self.driver.execute_script(
            "document.querySelector('button.footer-button-base__button.send-video-container__btn').click()"
        )
        if (
            video_join_btn.text.lower() == "join video"
            or video_join_btn.text.lower() == "start video"
        ):
            logger.info("video not Turned on")
            self.driver.execute_script(
                "document.querySelector('button.footer-button-base__button.send-video-container__btn').click()"
            )

        elif video_join_btn.text.lower() == "stop video":
            logger.info("already video on")

        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#stats")))
        self.driver.execute_script("document.querySelector('#stats').click()")
        time.sleep(1)
        self.send_meeting_link_and_password()

    def wait_for_exit(self):
        logger.info("waiting for clients to left the meeting...")
        tries = 0
        count = self.monitor_client_count()
        while count > 1:
            logger.info(f"{count} Devices in the Meeting")
            time.sleep(2)
            tries += 1
            if tries > 20:
                logger.warning("max tries reached for clients to leave the meeting.")
                break
            count = self.monitor_client_count()

    # To download the csv
    def download_csv(self):
        # redirecting to dashboard
        self.driver.get(
            "https://www.zoom.us/account/metrics/dashboard/home/#/pastMeetings"
        )

        # get meeting id formated
        cleaned_id = (
            self.meeting_id[:3] + " " + self.meeting_id[3:7] + " " + self.meeting_id[7:]
        )

        xpath = (
            f"//p[contains(@class, 'ellipsis') and contains(text(), '{cleaned_id}')]"
        )

        # element containing id and link to meeting dashboard
        current_elem = self.wait.until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        parent = current_elem.find_element(By.XPATH, "..")
        try:
            anchor = parent.find_element(By.TAG_NAME, "a")
        except BaseException:
            logger.warning("coudlnt find anchor tag refreshing in 15 seconds..")
            time.sleep(15)
            try:
                self.driver.refresh()
                current_elem = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                parent = current_elem.find_element(By.XPATH, "..")
                anchor = parent.find_element(By.TAG_NAME, "a")
            except BaseException:
                logger.warning("still link Does not appear...on last refresh")
                time.sleep(60)
                self.driver.refresh()
                current_elem = self.wait.until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                parent = current_elem.find_element(By.XPATH, "..")
        anchor = parent.find_element(By.TAG_NAME, "a")

        # redirecting to meeting dashboard
        self.driver.get(anchor.get_attribute("href"))

        # path for export button
        export_xpath = "//div[contains(@class, 'detail-operation') and contains(@class, 'detial-operation')]//button[.//span[contains(translate(., 'EXPORT', 'export'), 'export')]]"
        export_btn = self.wait.until(
            EC.element_to_be_clickable((By.XPATH, export_xpath))
        )
        export_btn.click()
        logger.info("Clicked Export button.")
        try:
            # Wait for modal and click "Go to Downloads Page"
            modal_btn = self.dynamic_wait(25).until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//button[.//span[contains(text(), 'Go to Downloads Page')]]",
                    )
                )
            )
            modal_btn.click()
            logger.info("Clicked 'Go to Downloads Page'.")
        except BaseException:
            # did not get the download popup refresh here"
            self.driver.refresh()
            export_xpath = "//div[contains(@class, 'detail-operation') and contains(@class, 'detial-operation')]//button[.//span[contains(translate(., 'EXPORT', 'export'), 'export')]]"
            export_btn = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, export_xpath))
            )
            export_btn.click()
            logger.info("Clicked Export button.")
            modal_btn = self.wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//button[.//span[contains(text(), 'Go to Downloads Page')]]",
                    )
                )
            )
            modal_btn.click()
            logger.info("Clicked 'Go to Downloads Page'.")

        # Wait for download to start
        logger.info("Waiting for download to complete...")
        time.sleep(15)
        all_handles = self.driver.window_handles
        self.driver.switch_to.window(all_handles[-1])
        # refreshing to get the updated tables
        self.driver.refresh()
        filename = self.wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    "table#download_queue_list tbody tr:nth-of-type(1) td.col1",
                )
            )
        ).text
        logger.info(f"download file is {filename}")
        button__dd = self.wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    "table#download_queue_list tbody tr:nth-of-type(1) button",
                )
            )
        )
        self.driver.execute_script("arguments[0].click();", button__dd)
        logger.info("Clicked 'Download' button")
        self.wait_for_download(filename, download_dir=os.getcwd(), timeout=45)

    def wait_for_download(self, dlname, download_dir, timeout=60):
        seconds = 0
        dl_wait = True
        final_file_path = None
        logger.info(f"{dlname} {download_dir} {timeout} <====directories")
        while dl_wait and seconds < timeout:
            time.sleep(1)
            dl_wait = False
            for fname in os.listdir(download_dir):
                if fname.startswith(dlname):
                    if fname.endswith(".crdownload"):
                        dl_wait = True  # still downloading
                    else:
                        final_file_path = os.path.join(download_dir, fname)
            seconds += 1

        if final_file_path and os.path.isfile(final_file_path):
            logger.info(f"File downloaded: {final_file_path}")
            try:
                with open(final_file_path, newline="") as csvfile:
                    reader = csv.reader(csvfile)
                    rows = list(reader)
                    endpoint_url = f"{self.base_url}/upload_csv"
                    logger.info(endpoint_url)

                    dd = {"filename": os.path.basename(final_file_path), "rows": rows}
                    logger.info(dd)
                    requests.post(
                        endpoint_url,
                        json={
                            "filename": os.path.basename(final_file_path),
                            "rows": rows,
                        },
                    )
            except Exception as e:
                logger.error(f"Error reading file: {e}")
        else:
            logger.warning("File was not downloaded in time or not found.")

    def stop_zoom(self):
        self.wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".footer__leave-btn-container button")
            )
        )
        self.driver.execute_script(
            "document.querySelector('.footer__leave-btn-container button').click()"
        )
        time.sleep(1)
        self.wait.until(
            EC.presence_of_element_located(
                (
                    By.CSS_SELECTOR,
                    ".leave-meeting-options__btn.leave-meeting-options__btn--default",
                )
            )
        )
        self.driver.execute_script(
            "document.querySelector('.leave-meeting-options__btn.leave-meeting-options__btn--default').click()"
        )
        download_csv = self.get_download_csv_flag()
        if download_csv:
            time.sleep(100)
            self.download_csv()
        self.driver.quit()

    def monitor_client_count(self):
        try:
            counter_text = self.wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, ".footer-button__number-counter")
                )
            ).text.strip()

            if not counter_text:
                return 1

            if not counter_text.isdigit():
                logger.warning(
                    f"Unexpected participant counter value: {counter_text!r}"
                )
                return 1

            return int(counter_text)
        except Exception as e:
            logger.error(f"Error reading participant count: {e}")
            return 1

    def set_start_test(self, flag=False):
        try:
            self.participants = self.monitor_client_count()
            self.set_participants()
            logger.info(
                f"{self.participants_required} is the participants required and {self.participants} are currently in the meeting"
            )
            if self.participants_required == self.participants:
                self.update_start_test()

            elif flag:
                self.update_start_test()

        except Exception as e:
            logger.error(f"error in setting start test {e}")

    def get_download_csv_flag(self):
        try:
            endpoint_url = f"{self.base_url}/download_csv"

            response = requests.get(endpoint_url)
            if response.status_code == 200:

                download_csv_flag = response.json().get("download_csv", False)
                return download_csv_flag

            return False
        except Exception as e:
            logger.error(f"Error checking get download csv flag: {e}")
            return False

    def check_stop_signal(self):
        """Check the stop signal from the Flask server."""
        try:
            endpoint_url = f"{self.base_url}/check_stop"

            response = requests.get(endpoint_url)  # Replace with your Flask server URL
            if response.status_code == 200:

                stop_signal_from_server = response.json().get("stop", False)

                # Only update if the server's stop signal is True
                if stop_signal_from_server:
                    self.stop_signal = True
                    logger.info(
                        "Stop signal received from the Flask Server. Exiting the test."
                    )
            return self.stop_signal
        except Exception as e:
            logger.error(f"Error checking stop signal from the Flask Server: {e}")

    def send_meeting_link_and_password(self):
        pattern = r"https://\S+?\.zoom\.us/(?:j|wc)/(?P<meeting_id>\d+)\S*?pwd=(?P<password>[^\s&]+)"

        match = re.search(pattern, self.meeting_link)
        if match:
            self.meeting_id = match.group("meeting_id")
            self.meeting_passwd = match.group("password")
            logger.info(
                f"meeting id: {self.meeting_id} meeting password: {self.meeting_passwd}"
            )
            if self.meeting_id:
                self.update_meeting_id(self.meeting_id)
            if self.meeting_passwd:
                self.update_meeting_passwd(self.meeting_passwd)
            logger.info("Meeting ID and password updated successfully")

    def capture_audio_stats(self):
        self.wait.until(
            EC.presence_of_element_located((By.XPATH, "//*[@id='Audio']"))
        ).click()
        time.sleep(2)
        freq = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[@id='Audio-tab']/div/table/tbody/tr[1]/td[2]")
            )
        ).text
        freq = freq.replace(" khz", "")
        freq_rec = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[@id='Audio-tab']/div/table/tbody/tr[1]/td[3]")
            )
        ).text
        freq_rec = freq_rec.replace(" khz", "")
        lat = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[@id='Audio-tab']/div/table/tbody/tr[2]/td[2]")
            )
        ).text
        lat = lat.replace(" ms", "")
        lat_rec = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[@id='Audio-tab']/div/table/tbody/tr[2]/td[3]")
            )
        ).text
        lat_rec = lat_rec.replace(" ms", "")
        jitt = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[@id='Audio-tab']/div/table/tbody/tr[3]/td[2]")
            )
        ).text
        jitt = jitt.replace(" ms", "")
        jitt_rec = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[@id='Audio-tab']/div/table/tbody/tr[3]/td[3]")
            )
        ).text
        jitt_rec = jitt_rec.replace(" ms", "")
        pack = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[@id='Audio-tab']/div/table/tbody/tr[4]/td[2]")
            )
        ).text
        packet_loss = re.sub(r"\s*\(.*?\)", "", pack)
        packet_loss_ = packet_loss.replace("%", "")
        pack_rec = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[@id='Audio-tab']/div/table/tbody/tr[4]/td[3]")
            )
        ).text
        packet_rec = re.sub(r"\s*\(.*?\)", "", pack_rec)
        packet_rec_ = packet_rec.replace("%", "")
        return [
            freq if freq != "-" else "0",
            lat if lat != "-" else "0",
            jitt if jitt != "-" else "0",
            packet_loss_ if packet_loss_ != "-" else "0",
            freq_rec if freq_rec != "-" else "0",
            lat_rec if lat_rec != "-" else "0",
            jitt_rec if jitt_rec != "-" else "0",
            packet_rec_ if packet_rec_ != "-" else "0",
        ]

    def capture_video_stats(self):
        self.wait.until(
            EC.presence_of_element_located((By.XPATH, "//*[@id='Video']"))
        ).click()
        time.sleep(2)
        latency = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[@id='Video-tab']/div/table/tbody/tr[1]/td[2]")
            )
        ).text
        latency = latency.replace(" ms", "")
        latency_rec = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[@id='Video-tab']/div/table/tbody/tr[1]/td[3]")
            )
        ).text
        latency_rec = latency_rec.replace(" ms", "")
        jitter = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[@id='Video-tab']/div/table/tbody/tr[2]/td[2]")
            )
        ).text
        jitter = jitter.replace(" ms", "")
        jitter_rec = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[@id='Video-tab']/div/table/tbody/tr[2]/td[3]")
            )
        ).text
        jitter_rec = jitter_rec.replace(" ms", "")
        packet_loss = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[@id='Video-tab']/div/table/tbody/tr[3]/td[2]")
            )
        ).text
        packet_loss_vi = re.sub(r"\s*\(.*?\)", "", packet_loss)
        packet_loss_vi = packet_loss_vi.replace("%", "")
        packet_loss_rec = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[@id='Video-tab']/div/table/tbody/tr[3]/td[3]")
            )
        ).text
        packet_loss_vi_rec = re.sub(r"\s*\(.*?\)", "", packet_loss_rec)
        packet_loss_vi_rec = packet_loss_vi_rec.replace("%", "")
        resolution = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[@id='Video-tab']/div/table/tbody/tr[4]/td[2]")
            )
        ).text
        resolution_rec = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[@id='Video-tab']/div/table/tbody/tr[4]/td[3]")
            )
        ).text
        frames_per_second = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[@id='Video-tab']/div/table/tbody/tr[5]/td[2]")
            )
        ).text
        frames_per_second = frames_per_second.replace(" fps", "")
        frames_per_second_rec = self.wait.until(
            EC.presence_of_element_located(
                (By.XPATH, "//*[@id='Video-tab']/div/table/tbody/tr[5]/td[3]")
            )
        ).text
        frames_per_second_rec = frames_per_second_rec.replace(" fps", "")
        return [
            latency if latency != "-" else "0",
            jitter if jitter != "-" else "0",
            packet_loss_vi if packet_loss_vi != "-" else "0",
            resolution if resolution != "-" else "0",
            frames_per_second if frames_per_second != "-" else "0",
            latency_rec if latency_rec != "-" else "0",
            jitter_rec if jitter_rec != "-" else "0",
            packet_loss_vi_rec if packet_loss_vi_rec != "-" else "0",
            resolution_rec if resolution_rec != "-" else "0",
            frames_per_second_rec if frames_per_second_rec != "-" else "0",
        ]

    def get_host_email(self):
        # Call Flask endpoint to get host email
        endpoint_url = f"{self.base_url}/get_host_email"
        try:
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                return response.json().get("host_email", None)
            else:
                logger.warning(
                    f"Failed to fetch Login Email. Status code: {response.status_code}"
                )
        except requests.RequestException as e:
            logger.error(f"Request error while getting login email: {e}")
        return None

    def get_host_password(self):
        # Call Flask endpoint to get new_password
        endpoint_url = f"{self.base_url}/get_host_passwd"
        try:
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                return response.json().get("host_passwd", None)
            else:
                logger.warning(
                    f"Failed to fetch login Password. Status code: {response.status_code}"
                )
        except requests.RequestException as e:
            logger.error(f"Request error while getting login password: {e}")
        return None

    def update_meeting_id(self, meeting_id):
        endpoint_url = f"{self.base_url}/login_url"
        data = {"login_url": meeting_id}

        try:
            response = requests.post(endpoint_url, json=data)
            if response.status_code == 200:
                logger.info("Meeting ID updated successfully to Flask Server.")
            else:
                logger.warning(
                    f"Failed to update meeting ID to Flask Server. Status code: {response.status_code}"
                )
        except requests.RequestException as e:
            logger.error(f"Request error: {e}")

    def update_meeting_passwd(self, meeting_passwd):
        endpoint_url = f"{self.base_url}/login_passwd"
        data = {"login_passwd": meeting_passwd}

        try:
            response = requests.post(endpoint_url, json=data)
            if response.status_code == 200:
                logger.info("Meeting password updated successfully to Flask Server.")
            else:
                logger.warning(
                    f"Failed to update meeting password to Flask Server. Status code: {response.status_code}"
                )
        except requests.RequestException as e:
            logger.error(f"Request error: {e}")

    def update_login_completed(self):
        endpoint_url = f"{self.base_url}/login_completed"

        try:
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                logger.info(
                    "Login completed status updated successfully to Flask Server."
                )
            else:
                logger.warning(
                    f"Failed to update login completed status to Flask Server. Status code: {response.status_code}"
                )
        except requests.RequestException as e:
            logger.error(f"Request error while updating login completed status: {e}")

    def update_start_test(self):

        endpoint_url = f"{self.base_url}/test_started"
        data = {"test_started": True}
        try:
            response = requests.post(endpoint_url, json=data)
            if response.status_code == 200:
                logger.info("test started status updated successfully to Flask Server.")
            else:
                logger.warning(
                    f"Failed to update test started status to Flask Server. Status code: {response.status_code}"
                )
        except requests.RequestException as e:
            logger.error(
                f"Request error while updating test started status to Flask Server: {e}"
            )

    def set_participants(self):
        endpoint_url = f"{self.base_url}/set_participants_joined"
        data = {"participants_joined": self.participants}
        try:
            response = requests.post(endpoint_url, json=data)
            if response.status_code == 200:
                logger.info(
                    "test participants joined status updated successfully to Flask Server."
                )
            else:
                logger.warning(
                    f"Failed to update participants status to Flask Server. Status code: {response.status_code}"
                )
        except requests.RequestException as e:
            logger.error(
                f"Request error while updating participants status to Flask Server: {e}"
            )

    def get_required_participants(self):
        endpoint_url = f"{self.base_url}/get_participants_req"
        try:
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                return response.json().get("participants", None)
            else:
                logger.warning(
                    f"Failed to fetch required participants from the Flask Server. Status code: {response.status_code}"
                )
        except requests.RequestException as e:
            logger.error(
                f"Request error while getting required participants from the Flask Server: {e}"
            )
            return None
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
                logger.warning(
                    f"Failed to fetch start and end time from the Flask Server. Status code: {response.status_code}"
                )
        except requests.RequestException as e:
            logger.error(
                f"Request error while fetching start and end time from the Flask Server: {e}"
            )
        return None

    def send_client_disconnection(self):
        endpoint_url = f"{self.base_url}/clients_disconnected"
        data = {"clients_disconnected": True}
        try:
            response = requests.post(endpoint_url, json=data)
            if response.status_code == 200:
                logger.info(
                    "test participants disconnection updated successfully to Flask Server."
                )
            else:
                logger.warning(
                    f"Failed to update participants disconnection to Flask Server. Status code: {response.status_code}"
                )
        except requests.RequestException as e:
            logger.error(
                f"Request error while updating participants disconnection to Flask Server: {e}"
            )

    def get_stats_flags(self):
        endpoint_url = f"{self.base_url}/stats_opt"
        try:
            response = requests.get(endpoint_url)
            if response.status_code == 200:
                data = response.json()
                self.audio = data.get("audio_stats")
                self.video = data.get("video_stats")
            else:
                logger.warning(
                    f"Failed to fetch stats flag from the Flask Server. Status code: {response.status_code}"
                )
        except requests.RequestException as e:
            logger.error(
                f"Request error while fetching stats flag from the Flask Server: {e}"
            )
        return None

    def collecting_stats(self):
        if self.audio:
            self.audio_stats = self.capture_audio_stats()
        else:
            self.audio_stats = ["0", "0", "0", "0", "0", "0", "0", "0"]
        if self.video:
            self.video_stats = self.capture_video_stats()
        else:
            self.video_stats = ["0", "0", "0", "0", "0", "0", "0", "0", "0", "0"]
        return self.audio_stats + self.video_stats

    def get_formated_time(self, timestamp_str):
        timestamp = datetime.fromisoformat(timestamp_str)
        date = timestamp.date()
        hour = timestamp.hour
        minute = timestamp.minute
        second = timestamp.second
        return f"{date} {hour}:{minute:02}:{second:02}"

    def send_stats_to_api(self, audio_stats, video_stats):
        endpoint_url = f"{self.base_url}/upload_stats"
        data = {
            self.hostname: {
                "timestamp": self.get_formated_time(datetime.now(self.tz).isoformat()),
                "audio_stats": {
                    "frequency_sent": audio_stats[0],
                    "latency_sent": audio_stats[1],
                    "jitter_sent": audio_stats[2],
                    "packet_loss_sent": audio_stats[3],
                    "frequency_received": audio_stats[4],
                    "latency_received": audio_stats[5],
                    "jitter_received": audio_stats[6],
                    "packet_loss_received": audio_stats[7],
                },
                "video_stats": {
                    "latency_sent": video_stats[0],
                    "jitter_sent": video_stats[1],
                    "packet_loss_sent": video_stats[2],
                    "resolution_sent": video_stats[3],
                    "frames_per_second_sent": video_stats[4],
                    "latency_received": video_stats[5],
                    "jitter_received": video_stats[6],
                    "packet_loss_received": video_stats[7],
                    "resolution_received": video_stats[8],
                    "frames_per_second_received": video_stats[9],
                },
            }
        }

        try:
            response = requests.post(endpoint_url, json=data)
            if response.status_code == 200:
                logger.info("Stats sent successfully to Flask Server.")
            else:
                logger.warning(
                    f"Failed to send stats to Flask Server. Status code: {response.status_code}"
                )
        except requests.RequestException as e:
            logger.error(f"Request error while sending stats to Flask Server: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zoom Automation Script")
    parser.add_argument("--ip", required=True, help="Server endpoint ip")
    parser.add_argument("--env", action="extend", nargs="+", default=[])

    args = parser.parse_args()
    for argument in args.env:
        arg = argument.split("=")
        os.environ[arg[0]] = arg[1]

    zoom_host = ZoomHost(server_ip=args.ip)  # Replace with your actual server IP

    zoom_host.start_zoom()
    wait_limit = datetime.now() + timedelta(seconds=120)
    zoom_host.get_stats_flags()
    while True:
        zoom_host.set_start_test()
        if (
            zoom_host.participants_required is not None
            and zoom_host.participants_required == zoom_host.participants
        ):
            logger.info(
                f"participants required is {zoom_host.participants_required} and current participants in meeting is {zoom_host.participants}"
            )
            logger.info(
                f"required participants are Joined the meeting. Starting the test."
            )
            break
        elif datetime.now() > wait_limit:
            logger.warning(
                f"wait limit is reached. Starting the test with available clients "
                f"{zoom_host.participants_required} {zoom_host.participants}"
            )
            zoom_host.set_start_test(flag=True)
            break
        time.sleep(5)
    count = 0
    while zoom_host.start_time is None or zoom_host.end_time is None:
        count += 1
        if count > 24:
            logger.error(
                "start and end time is not set from server even after 2 minutes. Exiting the test"
            )
            zoom_host.driver.quit()
            sys.exit(1)
        logger.info("waiting for start and end time from server")
        zoom_host.get_start_and_end_time()
        time.sleep(5)
    logger.info(
        f"End time and Start time of the test is {zoom_host.start_time} {zoom_host.end_time}"
    )
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
        logger.error(f"Invalid start/end time format from server: {e}")
        zoom_host.driver.quit()
        sys.exit(1)

    while start_dt > datetime.now(zoom_host.tz):
        time.sleep(2)
        logger.info("Waiting until the Start time of the test reached")

    while end_dt > datetime.now(zoom_host.tz):
        logger.info("monitoring the test")
        if zoom_host.check_stop_signal():
            break
        zoom_host.send_stats_to_api(zoom_host.audio_stats, zoom_host.video_stats)
        time.sleep(2)
    logger.info("Test has been completed")
    zoom_host.wait_for_exit()
    zoom_host.stop_zoom()
    zoom_host.send_client_disconnection()
