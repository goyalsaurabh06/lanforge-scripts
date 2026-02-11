from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import socket
import argparse
import requests
import time
from datetime import datetime
import sys
import pytz
import logging

# 1. Configure the logging system
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("gmeet_client.log", mode="w"),
        logging.StreamHandler(sys.stdout),
    ],
)

# 2. Create the logger instance
logger = logging.getLogger(__name__)


class GmeetClient:
    def __init__(self, upstream_port_ip):
        self.upstream_port_ip = upstream_port_ip
        self.meet_link = str()
        self.start_time = None
        self.end_time = None
        self.tz = pytz.timezone("Asia/Kolkata")
        self.stop_signal = False

        self.prefs = {
            "profile.default_content_setting_values.media_stream_mic": 1,  # Allow microphone access
            "profile.default_content_setting_values.media_stream_camera": 1,  # Allow camera access
            "profile.default_content_setting_values.notifications": 2,  # Block notifications
            "profile.default_content_setting_values.popups": 2,  # Block pop-ups
            "profile.default_content_setting_values.geolocation": 2,  # Block geolocation
            "profile.default_content_setting_values.automatic_downloads": 2,  # Block automatic downloads
        }

        self.opt = Options()
        self.opt.add_experimental_option("prefs", self.prefs)
        self.opt.add_argument("--disable-extensions")
        self.opt.add_argument("--disable-infobars")
        self.opt.add_argument("--disable-popup-blocking")
        self.opt.add_argument("--no-sandbox")
        self.opt.add_argument("--disable-blink-features=AutomationControlled")
        self.opt.add_experimental_option("useAutomationExtension", False)
        self.opt.add_experimental_option(
            "excludeSwitches", ["enable-automation", "disable-component-update"]
        )
        self.opt.add_argument("--disable-dev-shm-usage")
        self.opt.add_argument("--disable-gpu")
        self.opt.add_argument("--use-fake-ui-for-media-stream")
        self.driver = webdriver.Chrome(options=self.opt)
        self.driver.maximize_window()

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
            logger.error(f"Connection Error: Could not reach {url}.")
        except requests.exceptions.Timeout:
            logger.error(f"Timeout: {url} did not respond in {timeout}s.")
        except requests.exceptions.HTTPError as err:
            logger.error(f"HTTP Error {err.response.status_code}: {err}")
        except ValueError:
            logger.error(f"Data Error: Invalid JSON from {url}.")
        except Exception as e:
            logger.error(f"Unexpected error calling {url}: {e}")

        return None  # Return None on any failure

    def get_meet_link(self):
        """
        Fetches the meeting URL from the upstream server.
        Returns: str or None
        """
        # 1. Call the helper
        # This handles timeouts, connection errors, and bad JSON automatically.
        data = self.safe_request("GET", "meeting_url")

        # 2. Process the response
        if data:
            meet_link = data.get("meeting_url")

            if meet_link:
                self.meet_link = meet_link
                return self.meet_link
            else:
                # The server responded (200 OK), but the key 'meeting_url' was missing or empty
                logger.warning(
                    f"API returned 200 OK, but 'meeting_url' was missing. Response: {data}"
                )

        # Return None if request failed or link was missing
        return None

    def join_meet(self):
        self.driver.get(self.meet_link)
        # Wait up to 10 seconds for the input to be visible and interactive
        name_input = WebDriverWait(self.driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//input[@placeholder='Your name']"))
        )

        # Optional: Click to focus ensures the field is active
        name_input.click()
        name_input.clear()
        name_input.send_keys(socket.gethostname())

        # Wait for the "Join now" text to be visible and clickable
        join_button = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//span[contains(text(), 'Join now')]")
            )
        )
        join_button.click()

    def check_stop_signal(self):
        """
        Check the stop signal from the Flask server.
        Returns: bool (The current state of the stop signal)
        """
        # 1. Call the helper
        # Use a shorter timeout (e.g., 3s) for control signals to prevent loop freezing
        data = self.safe_request("GET", "check_stop", timeout=3)

        # 2. Process response
        # Only update if we received valid data and the 'stop' flag is explicitly True
        if data and data.get("stop") is True:
            self.stop_signal = True
            logger.warning("Stop signal received from server. Flag set to True.")

        # 3. Always return the current state
        # If the request failed (data is None), we simply return the existing state
        return self.stop_signal

    def update_participants(self):
        """
        Calls the upstream API to increment the participant count.
        Returns: (success: bool, current_count: int or None)
        """
        # 1. Call the helper
        # We pass timeout=10 to match the specific requirement in your snippet
        data = self.safe_request("GET", "update_participants", timeout=10)

        # 2. Verify application-level success
        if data and data.get("status") == "success":
            current_count = data.get("current_count")

            logger.info(
                f"Successfully updated participants. New count: {current_count}"
            )
            return True, current_count

        # 3. Handle specific application errors (e.g. server said "database full")
        elif data:
            logger.warning(
                f"API call completed but returned error status: {data.get('message')}"
            )

        # 4. Return failure (Covers network errors, timeouts, or application errors)
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
                f"Times updated successfully - Start: {self.start_time}, End: {self.end_time}"
            )
            return True

        # 3. Handle failure cases
        elif payload:
            # We got a response, but the server said "error"
            logger.error(
                f"Server returned application error: {payload.get('message')}"
            )
        else:
            # safe_request returned None (network error, timeout, etc.)
            # The specific error has already been logged by safe_request
            pass

        return False


def main():
    try:
        parser = argparse.ArgumentParser(description="Google Meet Client Automation")
        parser.add_argument(
            "--upstream_port_ip",
            type=str,
            help="Upstream port IP for data transfer",
            required=True,
        )
        args = parser.parse_args()

        client = GmeetClient(upstream_port_ip=args.upstream_port_ip)
        if client.get_meet_link():
            client.join_meet()
            client.update_participants()

            while client.start_time is None or client.end_time is None:
                client.get_start_and_end_time()
                time.sleep(5)

            while datetime.fromisoformat(client.start_time) > datetime.now(client.tz):
                time.sleep(2)
                logger.info("Waiting for the start time of The Test")

            while datetime.fromisoformat(client.end_time) > datetime.now(client.tz):
                logger.info("monitoring the test")
                client.check_stop_signal()
                if client.stop_signal:
                    logger.info("Stop signal received. Exiting the Test")
                    break

    except Exception as e:
        logger.error(f"Error Occured {e}")

    finally:
        client.driver.quit()


if __name__ == "__main__":
    main()
