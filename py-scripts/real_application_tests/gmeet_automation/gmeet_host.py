"""
NAME : googleMeetHost.py
PURPOSE :
        This script automates the process of opening and running Google Meet for a user-specified duration.
        It collects statistics from WebRTC-internals and stores these stats in CSV files.
        Additionally, the script calls a reporting function that generates a live report and saves both HTML and PDF reports upon test completion (reports are generated on each system).
"""

# import required modules
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
import traceback
import requests
import sys
import pytz
from datetime import datetime

# 1. Configure the logging system
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("gmeet_host.log", mode="w"),
        logging.StreamHandler(sys.stdout),
    ],
)

# 2. Create the logger instance
logger = logging.getLogger(__name__)


class GoogleMeetHost:
    def __init__(self, upstream_port_ip):
        self.email = None
        self.password = None
        self.upstream_port_ip = upstream_port_ip
        self.meeting_url = str()
        self.start_time = None
        self.end_time = None
        self.tz = pytz.timezone("Asia/Kolkata")
        self.stop_signal = False

        # configure chrome options
        self.opt = Options()

        self.opt.add_argument("--disable-blink-features=AutomationControlled")
        self.opt.add_argument("--start-maximized")

        self.opt.add_experimental_option(
            "prefs",
            {
                "profile.default_content_setting_values.media_stream_mic": 1,
                "profile.default_content_setting_values.media_stream_camera": 1,
                "profile.default_content_setting_values.geolocation": 0,
                "profile.default_content_setting_values.notifications": 1,
            },
        )
        # create chrome instance
        self.driver = webdriver.Chrome(options=self.opt)

    def dynamic_wait(self, waittime):
        return WebDriverWait(self.driver, waittime)

    def allow_all(self):
        host_controls = self.dynamic_wait(15).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[@aria-label='Host controls']")
            )
        )

        host_controls.click()

        open_option = self.dynamic_wait(10).until(
            EC.element_to_be_clickable((By.XPATH, "//label[normalize-space()='Open']"))
        )

        open_option.click()

    def create_meeting(self):
        target_element = self.dynamic_wait(10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//button[descendant::span[@class='UywwFc-RLmnJb']]")
            )
        )
        target_element.click()

        start_meeting_btn = self.dynamic_wait(10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//li[@aria-label='Start an instant meeting']")
            )
        )

        start_meeting_btn.click()
        self.allow_all()
        self.meeting_url = self.driver.current_url

    def safe_request(self, method, endpoint, payload=None, timeout=5):
        """
        Generic wrapper to handle requests with consistent error logging.
        """
        url = f"http://{self.upstream_port_ip}:5020/{endpoint}"

        try:
            if method.upper() == "GET":
                response = requests.get(url, timeout=timeout)
            else:
                response = requests.post(url, json=payload, timeout=timeout)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.ConnectionError:
            logger.error(f"❌ Connection Error: Could not reach {url}.")
        except requests.exceptions.Timeout:
            logger.error(f"❌ Timeout: {url} did not respond in {timeout}s.")
        except requests.exceptions.HTTPError as err:
            logger.error(f"❌ HTTP Error {err.response.status_code}: {err}")
        except ValueError:
            logger.error(f"❌ Data Error: Invalid JSON from {url}.")
        except Exception as e:
            logger.error(f"❌ Unexpected error calling {url}: {e}")

        return None  # Return None on any failure

    def send_meeting_url(self):
        """
        Sends the current meeting URL to the upstream server.
        Returns: bool (True if successful)
        """
        # 1. Validation
        if not self.meeting_url:
            logger.warning("⚠️ Attempted to send meeting URL, but it is empty.")
            return False

        # 2. Call the helper
        # The helper handles crashes/timeouts and returns None if they happen.
        response_data = self.safe_request(
            method="POST",
            endpoint="meeting_url",
            payload={"meeting_url": self.meeting_url},
        )

        # 3. Verify application success
        # We check if response_data exists AND if the 'status' key is 'success'
        if response_data and response_data.get("status") == "success":
            logger.info("✅ Meeting URL sent successfully.")
            return True
        else:
            # If we got a response but the server said "error" (e.g. invalid data)
            if response_data:
                logger.error(
                    f"❌ Server rejected update: {response_data.get('message')}"
                )
            return False

    def inform_host_failed(self):
        """
        Notifies the upstream server that the host has failed.
        Returns: bool (True if notification was successful)
        """
        logger.info("Attempting to report host failure...")

        # 1. Call the helper
        # The helper handles crashes/timeouts and returns None if they happen.
        response_data = self.safe_request(method="GET", endpoint="host_failed")

        # 2. Check the response
        if response_data and response_data.get("status") == "success":
            logger.info("✅ Successfully notified server of host failure.")
            return True

        # 3. Handle specific failure messages if needed
        if response_data:
            logger.error(
                f"❌ Server received request but returned error: {response_data.get('message')}"
            )

        return False

    def dismiss_popup(self):
        try:

            got_it_button = self.dynamic_wait(10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//span[contains(text(), 'Got it')]")
                )
            )
            got_it_button.click()
        except Exception as e:
            logger.info("No popup to dismiss.")

    def get_email(self):
        """
        Fetches the login email from the upstream server.
        """
        # 1. Call helper
        data = self.safe_request("GET", "get_email")

        # 2. Validate
        if data and data.get("email"):
            self.email = data.get("email")
            logger.info(f"✅ Fetched Email: {self.email}")
            return True

        # 3. Handle Failure
        logger.error("❌ Unable to Fetch Email ID for login.")
        sys.exit(1)

    def get_password(self):
        """
        Fetches the login password from the upstream server.
        """
        # 1. Call helper
        data = self.safe_request("GET", "get_passwd")

        # 2. Validate
        if data and data.get("password"):
            self.password = data.get("password")
            logger.info("✅ Fetched Password.")
            return True

        # 3. Handle Failure
        logger.error("❌ Unable to Fetch Password for login.")
        sys.exit(1)

    def login(self):
        self.get_email()
        self.driver.get("https://meet.google.com/landing?pli=1")

        email_input = self.dynamic_wait(10).until(
            EC.visibility_of_element_located((By.ID, "identifierId"))
        )

        email_input.send_keys(self.email)

        next_button = self.dynamic_wait(10).until(
            EC.visibility_of_element_located((By.ID, "identifierNext"))
        )

        next_button.click()

        password_input = self.dynamic_wait(10).until(
            EC.visibility_of_element_located((By.NAME, "Passwd"))
        )

        password_input.send_keys(self.password)

        password_next = self.dynamic_wait(10).until(
            EC.visibility_of_element_located((By.ID, "passwordNext"))
        )
        password_next.click()

        self.dismiss_popup()

    def update_participants(self):
        """
        Calls the upstream API to increment the participant count.
        Returns: (success: bool, current_count: int or None)
        """
        # 1. Call the helper
        # This handles timeouts, connection errors, and bad JSON automatically.
        data = self.safe_request("GET", "update_participants")

        # 2. Verify application-level success
        if data and data.get("status") == "success":
            current_count = data.get("current_count")

            logger.info(
                f"✅ Successfully updated participants. New count: {current_count}"
            )
            return True, current_count

        # 3. Handle failure cases
        elif data:
            # Request worked, but server returned an error (e.g. database full)
            logger.warning(
                f"⚠️ API call completed but returned error status while updating participants: {data.get('message')}"
            )
        else:
            # safe_request returned None (network error/timeout).
            # The specific error has already been logged by safe_request.
            pass

        return False, None

    def get_start_and_end_time(self):
        """
        Fetches start and end times from the upstream server.
        Updates self.start_time and self.end_time.
        Returns: bool (True if update succeeded, False otherwise)
        """
        # 1. Call the helper
        # This handles timeouts, connection errors, and bad JSON automatically.
        payload = self.safe_request("GET", "get_start_end_time")

        # 2. Verify application-level success
        if payload and payload.get("status") == "success":
            data = payload.get("data", {})

            self.start_time = data.get("start_time")
            self.end_time = data.get("end_time")

            logger.info(
                f"✅ Times updated successfully - Start: {self.start_time}, End: {self.end_time}"
            )
            return True

        # 3. Handle failure cases
        elif payload:
            # We got a response, but the server said "error"
            logger.error(
                f"❌ Server returned application error: {payload.get('message')}"
            )
        else:
            # safe_request returned None (network error, timeout, etc.)
            # The specific error has already been logged by safe_request
            pass

        return False

    def check_stop_signal(self):
        """
        Check the stop signal from the Flask server.
        Returns: bool (The current state of the stop signal)
        """
        # 1. Call the helper
        # We use a shorter timeout (3s) so the main loop doesn't freeze if the server hangs.
        data = self.safe_request("GET", "check_stop", timeout=3)

        # 2. Process the response
        # We only update if we got valid data AND the 'stop' flag is explicitly True.
        if data and data.get("stop") is True:
            self.stop_signal = True
            logger.warning("🛑 Stop signal received from server. Flag set to True.")

        # 3. Always return the current state
        # (If the request failed/returned None, we simply return the existing state)
        return self.stop_signal


def main():
    try:
        parser = argparse.ArgumentParser(description="Google Meet Host Automation")
        parser.add_argument(
            "--upstream_port_ip",
            type=str,
            help="Upstream port IP for data transfer",
            required=True,
        )
        args = parser.parse_args()

        host = GoogleMeetHost(upstream_port_ip=args.upstream_port_ip)
        host.login()
        host.create_meeting()
        host.send_meeting_url()
        host.update_participants()
        while host.start_time is None or host.end_time is None:
            host.get_start_and_end_time()
            time.sleep(5)

        while datetime.fromisoformat(host.start_time) > datetime.now(host.tz):
            time.sleep(2)
            logger.info("Waiting for the start time of The Test")

        while datetime.fromisoformat(host.end_time) > datetime.now(host.tz):
            logger.info("monitoring the test")
            host.check_stop_signal()
            if host.stop_signal:
                logger.info("Stop signal received. Exiting the Test")
                break

    except Exception as e:
        logger.error(f"Exception occurred: {e}")
        logger.error(traceback.format_exc())
        host.inform_host_failed()
    finally:
        host.driver.quit()


if __name__ == "__main__":
    main()
