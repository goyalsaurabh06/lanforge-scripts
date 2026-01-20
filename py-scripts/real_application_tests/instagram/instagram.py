#!/usr/bin/env python3
"""
Instagram Reels Automation
Works on Linux / macOS / Windows
Requires:
  - Python 3.9+
  - pip install selenium>=4.17
  - Google Chrome installed
"""

import os
import time
import argparse
import pickle
import platform
from pathlib import Path
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# OS NORMALIZATION
SYSTEM = platform.system().lower()

if SYSTEM == "linux":
    if os.environ.get("XDG_SESSION_TYPE") == "wayland":
        print("[env] Wayland detected ? switching to X11 compatibility")
        os.environ["XDG_SESSION_TYPE"] = "x11"

# PROFILE / COOKIE PATH 
BASE_DIR = Path.home() / ".insta_automation"
PROFILE_DIR = BASE_DIR / "chrome_profile"
COOKIE_FILE = BASE_DIR / "cookies.pkl"
BASE_DIR.mkdir(exist_ok=True)
PROFILE_DIR.mkdir(exist_ok=True)


class Instagram:
    def __init__(self, username, password, duration, driver):
        self.username = username
        self.password = password
        self.duration = duration
        self.driver = driver
        self.wait = WebDriverWait(driver, 30)

    #  COOKIE HANDLING 
    def load_cookies(self):
        if COOKIE_FILE.exists():
            with open(COOKIE_FILE, "rb") as f:
                for cookie in pickle.load(f):
                    try:
                        self.driver.add_cookie(cookie)
                    except:
                        pass
            print("[cookie] Loaded saved cookies")

    def save_cookies(self):
        with open(COOKIE_FILE, "wb") as f:
            pickle.dump(self.driver.get_cookies(), f)
        print("[cookie] Cookies saved")

    #  LOGIN LOGIC 
    def is_logged_in(self):
        try:
            self.wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//img[contains(@alt,'profile')]")
                )
            )
            return True
        except:
            return False

    def login(self):
        print("[login] Opening Instagram")
        self.driver.get("https://www.instagram.com/")
        time.sleep(3)

        self.load_cookies()
        self.driver.refresh()

        if self.is_logged_in():
            print("[login] Already logged in")
            return

        print("[login] Performing login")
        self.driver.get("https://www.instagram.com/accounts/login/")

        user = self.wait.until(EC.presence_of_element_located((By.NAME, "username")))
        pwd = self.wait.until(EC.presence_of_element_located((By.NAME, "password")))

        user.clear()
        pwd.clear()
        user.send_keys(self.username)
        pwd.send_keys(self.password)
        pwd.send_keys(Keys.RETURN)

        time.sleep(10)

        if not self.is_logged_in():
            raise RuntimeError(
                "Login failed. Possible 2FA / captcha / challenge."
            )

        self.save_cookies()
        print("[login] Login successful")

    #  REELS PLAYBACK 
    def open_reels(self):
        print("[reels] Opening reels page")
        self.driver.get("https://www.instagram.com/reels/")
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "video")))

    def wait_on_reel(self, watch_seconds=10):
        start = time.time()
        current_src = self.get_video_src()

        while True:
            time.sleep(0.5)

            new_src = self.get_video_src()

            # If Instagram auto-scrolled, reset timer
            if new_src and new_src != current_src:
                current_src = new_src
                start = time.time()

            # If we watched this reel long enough, exit
            if time.time() - start >= watch_seconds:
                break


    def next_reel(self):
        try:
            body = self.driver.find_element(By.TAG_NAME, "body")
            body.click()
            time.sleep(0.2)
            body.send_keys(Keys.ARROW_DOWN)
        except Exception as e:
            print("[scroll] Error:", e)

    def get_video_src(self):
        try:
            video = self.driver.find_element(By.TAG_NAME, "video")
            return video.get_attribute("src")
        except:
            return None



    def play(self):
        self.login()
        self.open_reels()

        end_time = datetime.now() + timedelta(minutes=self.duration)
        reel_num = 1
        last_src = self.get_video_src()

        while datetime.now() <= end_time:
            print(f"Watching reel #{reel_num}")

            self.wait_on_reel(watch_seconds=10)
            self.next_reel()

            reel_num += 1

        print("Done.")
        self.driver.quit()



# DRIVER FACTORY 
def create_driver():
    options = webdriver.ChromeOptions()

    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")

    # ? REQUIRED for Linux stability
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    options.add_argument(f"--user-data-dir={PROFILE_DIR}")

    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)

    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        }
    )

    return driver

# MAIN 
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--duration", type=int, required=True, help="Minutes")
    args = parser.parse_args()

    driver = create_driver()
    insta = Instagram(args.username, args.password, args.duration, driver)
    insta.play()


if __name__ == "__main__":
    main()
