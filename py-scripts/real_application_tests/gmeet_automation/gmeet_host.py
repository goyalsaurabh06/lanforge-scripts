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

# 1. Configure the logging system
logging.basicConfig(
    filename="gmeet_host.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    filemode="w",
)

# 2. Create the logger instance
logger = logging.getLogger(__name__)


class GoogleMeetHost:
    def __init__(self, email, password, duration, upstream_port_ip):
        self.email = email
        self.password = password
        self.duration = duration
        self.upstream_port_ip = upstream_port_ip
        self.meeting_url = str()

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

        time.sleep(300)

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

    def send_meeting_url(self):
        try:
            response = requests.post(
                f"http://{self.upstream_port_ip}:5020/meeting_url",
                json={"meeting_url": self.meeting_url},
            )
            if response.status_code == 200:
                logger.info("Meeting URL sent successfully.")
            else:
                logger.error(
                    f"Failed to send meeting URL. Status code: {response.status_code}"
                )
        except Exception as e:
            logger.error(f"Exception occurred while sending meeting URL: {e}")

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

    def login(self):
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


def main():
    try:
        parser = argparse.ArgumentParser(description="Google Meet Host Automation")
        parser.add_argument("--email", required=True, help="Email address for login")
        parser.add_argument("--password", required=True, help="Password for login")
        parser.add_argument(
            "--duration",
            type=int,
            help="Duration to run the meeting in minutes",
            required=True,
        )
        parser.add_argument(
            "--upstream_port_ip",
            type=str,
            help="Upstream port IP for data transfer",
            required=True,
        )
        args = parser.parse_args()

        host = GoogleMeetHost(
            email=args.email,
            password=args.password,
            duration=args.duration,
            upstream_port_ip=args.upstream_port_ip,
        )
        host.login()
        host.create_meeting()
        host.send_meeting_url()
    except Exception as e:
        logger.error(f"Exception occurred: {e}")
        logger.error(traceback.format_exc())
    finally:
        host.driver.quit()


if __name__ == "__main__":
    main()
