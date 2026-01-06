import logging
import os
import requests
from selenium import webdriver
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
import argparse
import random
import traceback
import socket
from datetime import datetime, timedelta, timezone
import platform

logging.basicConfig(
    filename="netflix_test.log",
    filemode="w",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


class Netflix:
    EMAIL_INPUT = (By.NAME, "userLoginId")  # Input with name="userLoginId"
    PASSWORD_INPUT = (By.NAME, "password")  # Input with name="password"
    LOGIN_SUBMIT_BTN = (By.CSS_SELECTOR, 'button[type="submit"]')
    PLAY_BTN = (
        By.CSS_SELECTOR,
        'button[data-uia="player-blocked-play"][aria-label="Play"]',
    )

    # Profile selection: targeting the first profile in the list
    FIRST_PROFILE = (By.CSS_SELECTOR, "ul.choose-profile li:nth-child(1) a")

    def __init__(self, duration, upstream_port):
        self.opt = Options()
        self.opt.add_argument("--disable-extensions")
        self.opt.add_argument("--disable-popup-blocking")
        self.opt.add_argument("--start-maximized")  # start window maximized
        # self.opt.add_argument("--start-fullscreen")  # request fullscreen on startup
        self.opt.add_argument("--no-sandbox")
        self.opt.add_argument("--disable-blink-features=AutomationControlled")
        self.opt.add_experimental_option("useAutomationExtension", False)
        self.opt.add_experimental_option(
            "excludeSwitches", ["enable-automation", "disable-component-update"]
        )
        # --- DYNAMIC OS DETECTION ---
        current_os = platform.system()
        logging.info(f"Detected OS: {current_os}")

        if current_os == "Windows":
            # Windows Binary
            self.opt.binary_location = (
                r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            )
            # Windows Profile Path
            user_data_dir = r"C:\ChromeProfile"

        elif current_os == "Linux":  # Ubuntu/Linux
            # Linux Binary (Common path for Ubuntu)
            self.opt.binary_location = "/usr/bin/google-chrome"
            # Linux Profile Path (Creates a folder 'chrome_profile' in your home directory)
            user_data_dir = os.path.expanduser("~/chrome_profile")

        elif current_os == "Darwin":  # macOS
            # macOS Binary
            self.opt.binary_location = (
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            )
            # macOS Profile Path (Creates a folder 'chrome_profile' in your home directory)
            user_data_dir = os.path.expanduser("~/chrome_profile")

        else:
            raise Exception(f"Unsupported Operating System: {current_os}")

        self.opt.add_argument(f"--user-data-dir={user_data_dir}")
        self.opt.add_argument("--profile-directory=Default")
        self.opt.add_argument("--no-first-run")
        self.opt.add_argument("--no-default-browser-check")

        prefs = {
            # commonly used keys (set both for safety)
            "profile.default_content_setting_values.notifications": 2,
            "profile.managed_default_content_settings.notifications": 2,
            "intl.accept_languages": "en-GB,en",
            "profile.default_content_setting_values.protected_media_identifier": 1,
            "profile.default_content_setting_values.geolocation": 1,
        }
        self.opt.add_experimental_option("prefs", prefs)
        self.opt.add_argument("--disable-notifications")

        self.driver = webdriver.Chrome(options=self.opt)
        self.wait = WebDriverWait(self.driver, 20)
        self.email = None
        self.passwd = None
        self.hostname = socket.gethostname()
        self.duration = duration
        self.upstream_port = upstream_port

    def simulate_human_movements(self):
        try:

            # Wait up to 10 seconds for the body tag to be present
            body = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            ActionChains(self.driver).move_to_element(body).perform()

            for _ in range(random.randint(2, 5)):
                ActionChains(self.driver).move_by_offset(
                    random.randint(-20, 20), random.randint(-20, 20)
                ).perform()
                time.sleep(random.uniform(0.1, 0.3))
        except Exception as e:
            logging.error(f"Error in simulate_human_movements(): {e}")
            traceback.print_exc()

    def get_credentials(self):
        # For demonstration, returning hardcoded credentials
        url = f"http://{self.upstream_port}:5010/get_credentials"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get("email"), data.get("password")
            else:
                logging.error(
                    f"Failed to get credentials | Status: {response.status_code}"
                )
        except Exception as e:
            logging.error(f"Error while getting credentials: {e}")
            traceback.print_exc()

    def login(self):
        try:
            self.driver.get("https://www.netflix.com/in/login")
            self.simulate_human_movements()
            # email = "candelatest773@gmail.com".strip()
            # passwd = "NetFlex@530045".strip()
            email, passwd = self.get_credentials()
            # Wait for Email input and send keys
            email_field = self.wait.until(
                EC.visibility_of_element_located(self.EMAIL_INPUT)
            )
            if platform.system() == "Darwin":
                email_field.send_keys(Keys.COMMAND, "a")
            else:
                email_field.send_keys(Keys.CONTROL, "a")
            email_field.send_keys(Keys.BACK_SPACE)
            email_field.send_keys(email)

            # Wait for Password input and send keys
            pass_field = self.driver.find_element(*self.PASSWORD_INPUT)
            # ROBUST CLEAR: Select All -> Backspace
            if platform.system() == "Darwin":
                pass_field.send_keys(Keys.COMMAND, "a")
            else:
                pass_field.send_keys(Keys.CONTROL, "a")

            pass_field.send_keys(Keys.BACK_SPACE)
            pass_field.send_keys(passwd)

            # Click Sign In
            self.driver.find_element(*self.LOGIN_SUBMIT_BTN).click()

            # Wait for the Profile Selection screen and click the first profile
            try:

                profile_icon = self.wait.until(
                    EC.element_to_be_clickable(self.FIRST_PROFILE)
                )
                profile_icon.click()
            except Exception as e:
                pass

            logging.info("Login and Profile selection successful.")

        except Exception as e:
            # logging.error(f"An error occurred: {e}")
            # traceback.print_exc()
            pass
            # Optional: Screenshot for debugging
            # self.driver.save_screenshot('error.png')

    def play(
        self,
    ):
        try:

            netflix_video_urls = [
                "https://www.netflix.com/watch/81776760?trackId=13212365&tctx=2%2C6%2Cc9ea1b81-62d6-4a53-8688-c68a09270524-104419064%2CNES_768BA76E15454089DC0700C2B358A8-994911DC4F528C-448F6C7696_p_1767341181732%2CNES_768BA76E15454089DC0700C2B358A8_p_1767341181732%2C%2C%2C%2C81223075%2CVideo%3A81776760%2CdetailsPageCollection"
            ]

            self.driver.get(netflix_video_urls[0])
            # play_button = self.wait.until(
            #     EC.element_to_be_clickable(self.PLAY_BTN)
            # )
            # play_button.click()
        except Exception as e:
            logging.error(f"An error occurred in play(): {e}")
            traceback.print_exc()

    def enable_stats(self):
        try:
            # Click body to ensure focus
            body = self.driver.find_element(By.TAG_NAME, "body")
            ActionChains(self.driver).move_to_element(body).click().perform()
            time.sleep(0.5)

            logging.info("Sending Ctrl + Shift + Alt + D...")

            actions = ActionChains(self.driver)
            actions.key_down(Keys.CONTROL)
            actions.key_down(Keys.SHIFT)
            actions.key_down(Keys.ALT)
            actions.send_keys("d")
            actions.key_up(Keys.ALT)
            actions.key_up(Keys.SHIFT)
            actions.key_up(Keys.CONTROL)
            actions.perform()

            logging.info("Shortcut sent successfully!")

        except Exception as e:
            logging.error(f"Error in enable_stats(): {e}")
            traceback.print_exc()

    def extract_stats(
        self,
    ):
        try:

            textarea = self.wait.until(
                EC.presence_of_element_located((By.TAG_NAME, "textarea"))
            )
            stats_text = textarea.get_attribute("value")
            self.stats = {}

            self.stats["timestamp"] = datetime.now(timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%SZ"
            )

            # Extract "Total Frames"
            m = re.search(r"Total Frames:\s*(\d+)", stats_text)
            self.stats["total_frames"] = int(m.group(1)) if m else None

            # Extract "Total Dropped Frames"
            m = re.search(r"Total Dropped Frames:\s*(\d+)", stats_text)
            self.stats["dropped_frames"] = int(m.group(1)) if m else None

            # Extract videoBuffered from VideoDiag line
            m = re.search(r"videoBuffered=([\d\.]+)", stats_text)
            self.stats["video_buffered"] = float(m.group(1)) if m else None

            # Extract audioBuffered from VideoDiag line
            m = re.search(r"audioBuffered=([\d\.]+)", stats_text)
            self.stats["audio_buffered"] = float(m.group(1)) if m else None

            m = re.search(
                r"Playing bitrate \(a\/v\):\s*(\d+)\s*/\s*(\d+)(?:\s*\(\s*(\d+)x(\d+)\s*\))?",
                stats_text,
                flags=re.IGNORECASE,
            )
            if m:
                self.stats["audio_bitrate_kbps"] = int(m.group(1))
                self.stats["video_bitrate_kbps"] = int(m.group(2))
                if m.group(3) and m.group(4):
                    w = int(m.group(3))
                    h = int(m.group(4))
                    self.stats["video_resolution"] = f"{w}x{h}"
                else:
                    self.stats["video_resolution"] = None
            else:
                self.stats["audio_bitrate_kbps"] = None
                self.stats["video_bitrate_kbps"] = None
                self.stats["video_resolution"] = None

            # --- New: Audio codec (full string + inner codec id/name) ---
            # Example line:
            # Audio Track: ... Codec: audio/mp4;codecs=mp4a.40.5 (he-aac)
            m = re.search(
                r"Audio Track:[^\n\r]*Codec:\s*([^\n\r]+)",
                stats_text,
                flags=re.IGNORECASE,
            )
            if m:
                audio_full = m.group(1).strip()
                # stats["audio_codec_full"] = audio_full
                # codec id like mp4a.40.5
                id_m = re.search(r"codecs=([^\s\);,]+)", audio_full)
                self.stats["audio_codec_id"] = id_m.group(1) if id_m else None
                # parenthetical name like (he-aac) or (he-aac, something)
                name_m = re.search(r"\(([^)]+)\)", audio_full)
                if name_m:
                    self.stats["audio_codec_name"] = (
                        name_m.group(1).split(",")[0].strip()
                    )
                else:
                    self.stats["audio_codec_name"] = None
            else:
                # stats["audio_codec_full"] = None
                self.stats["audio_codec_id"] = None
                self.stats["audio_codec_name"] = None

            # --- New: Video codec (full string + inner codec id/name) ---
            # Example line:
            # Video Track: Codec: video/mp4;codecs=av01.0.04M.08 (av1, prk)
            m = re.search(
                r"Video Track:[^\n\r]*Codec:\s*([^\n\r]+)",
                stats_text,
                flags=re.IGNORECASE,
            )
            if m:
                video_full = m.group(1).strip()
                # stats["video_codec_full"] = video_full
                id_m = re.search(r"codecs=([^\s\);,]+)", video_full)
                self.stats["video_codec_id"] = id_m.group(1) if id_m else None
                name_m = re.search(r"\(([^)]+)\)", video_full)
                if name_m:
                    self.stats["video_codec_name"] = (
                        name_m.group(1).split(",")[0].strip()
                    )
                else:
                    self.stats["video_codec_name"] = None
            else:
                # stats["video_codec_full"] = None
                self.stats["video_codec_id"] = None
                self.stats["video_codec_name"] = None

            self.stats = {self.hostname: self.stats}

            return self.stats
        except Exception as e:
            logging.error(f"An error occurred in extract_stats(): {e}")
            traceback.print_exc()
            return None

    def send_stats(self):
        url = f"http://{self.upstream_port}:5010/upload_stats"  # update this

        try:
            response = requests.post(url, json=self.stats, timeout=5)  # send JSON body

            if response.status_code == 200:
                logging.info(f"Stats uploaded successfully: {response.json()}")
            else:
                logging.error(
                    f"Failed to upload stats | "
                    f"Status: {response.status_code} | "
                    f"Response: {response.text}"
                )

        except requests.exceptions.RequestException as e:
            logging.error(f"Error while sending stats: {e}")

    def logout(self):
        try:
            self.driver.get("https://www.netflix.com/SignOut")
            logging.info("Logged out successfully.")
        except Exception as e:
            logging.error(f"An error occurred during logout: {e}")
            traceback.print_exc()


def main():
    try:
        parser = argparse.ArgumentParser(description="Netflix automation")
        parser.add_argument(
            "--duration", type=int, help="time duration for test", default=1
        )
        parser.add_argument(
            "--upstream_port", type=str, help="Upstream port for traffic"
        )
        args = parser.parse_args()
        netflix = Netflix(args.duration, args.upstream_port)
        netflix.login()
        netflix.play()
        netflix.enable_stats()
        time.sleep(5)  # Wait for stats overlay to appear
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=args.duration)

        while datetime.now() < end_time:
            netflix.extract_stats()
            netflix.send_stats()
            time.sleep(1)  # Interval between stats collection

        # netflix.logout()
    except Exception as e:
        logging.error(f"An error occurred in main: {e}")
        traceback.print_exc()
    finally:
        netflix.driver.quit()


if __name__ == "__main__":
    main()
