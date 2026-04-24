from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service


from datetime import datetime
import time
import re
import argparse
import csv
import requests
import sys
import os
import json   # --- NEW ---
import platform
import logging

sys.stdout.reconfigure(encoding="utf-8", errors="ignore")


class YouTubeShorts:

    def __init__(
        self,
        scroll_duration,
        entire_duration,
        url,
        host=None,
        device_name="device",
        stats_file=None
    ):
        self.scroll_duration = scroll_duration
        self.entire_duration = entire_duration
        self.device_name = device_name
        self.host = host
        self.url = url
        self.dataset = []
        self.short_index = 1

        # Linux VRF mode enabled ONLY when stats_file is provided
        self.stats_file = stats_file
        self.linux_vrf_mode = stats_file is not None

        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--autoplay-policy=no-user-gesture-required")
        options.add_argument("--disable-features=MediaSessionService")

        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        # --- DYNAMIC OS DETECTION ---
        current_os = platform.system()
        logging.info(f"Detected OS: {current_os}")

        self.driver = webdriver.Chrome(options=options)
        print("Chrome started successfully.")

        self.wait = WebDriverWait(self.driver, 35)
        self.video = None

    # ------------------------------------------------------------
    # OPEN SHORTS (LANforge / VNC SAFE)

    def open_shorts_home(self):
        if self.url:
            self.driver.get(self.url.split("?")[0])
        else:
            self.driver.get("https://www.youtube.com/shorts/")

        time.sleep(5)

        # FIX: JS-based focus + click (prevents element zero-size error)
        self.driver.execute_script("""
            document.body.focus();
            document.body.click();
        """)
        time.sleep(1)

        # User gesture for autoplay
        ActionChains(self.driver).send_keys(Keys.SPACE).perform()
        time.sleep(2)

        self.video = self.wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "video.video-stream.html5-main-video")
            )
        )

        print("First short started (JS focus + SPACE)")

    # ------------------------------------------------------------
    # FORCE PLAY (STABILITY FIX)

    def force_play_video(self):
        try:
            self.driver.execute_script("""
                const v = document.querySelector('video');
                if (v) {
                    v.muted = true;
                    v.play();
                }
            """)
            time.sleep(1)
        except Exception as e:
            print("Force play failed:", e)

    # ------------------------------------------------------------
    # STATS FOR NERDS

    def enable_stats(self):
        print("Enabling Stats for Nerds...")
        self.driver.execute_script("""
            const v = arguments[0];
            const r = v.getBoundingClientRect();
            v.dispatchEvent(new MouseEvent('contextmenu', {
                bubbles: true,
                cancelable: true,
                view: window,
                button: 2,
                buttons: 2,
                clientX: r.left + r.width / 2,
                clientY: r.top + r.height / 2
            }));
        """, self.video)

        items = self.wait.until(
            EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, ".ytp-menuitem-label")
            )
        )

        for item in items:
            if "stats for nerds" in item.text.lower():
                item.click()
                print("Stats enabled")
                return True

        print("Stats for Nerds not found")
        return False

    # ------------------------------------------------------------
    # GET STATS

    def get_stats(self):
        try:
            panel = self.driver.find_element(
                By.CSS_SELECTOR,
                ".html5-video-info-panel-content.ytp-sfn-content"
            )
            raw = panel.text.replace(" ", "")
        except:
            return None

        stats = {}

        vp = re.search(r"Viewport/Frames(\d+x\d+)", raw)
        stats["Viewport"] = vp.group(1) if vp else "-"

        drop = re.search(r"/(\d+)droppedof(\d+)", raw)
        stats["DroppedFrames"] = drop.group(1) if drop else "-"
        stats["TotalFrames"] = drop.group(2) if drop else "-"

        cr = re.search(r"Current/OptimalRes([\dx@]+)/([\dx@]+)", raw)
        stats["CurrentRes"] = cr.group(1) if cr else "-"
        stats["OptimalRes"] = cr.group(2) if cr else "-"

        bh = re.search(r"BufferHealth[:]?([\d\.]+)s", raw)
        stats["BufferHealth"] = bh.group(1) if bh else "0.0"

        lat = re.search(r"Live\s*Latency\s*([\d\.]+)s", raw)
        stats["LiveLatency"] = lat.group(1) if lat else "NA"

        lm = re.search(r"LiveMode([^A-Z]+)", raw)
        stats["LiveMode"] = lm.group(1) if lm else "NA"

        stats["Timestamp"] = datetime.now().strftime("%b %d %H:%M:%S")
        stats["Iterations"] = self.short_index
        return stats

    # ------------------------------------------------------------
    # NEXT SHORT (KEYBOARD SAFE)

    def next_short(self):
        try:
            ActionChains(self.driver).send_keys(Keys.ARROW_DOWN).perform()
            time.sleep(1)
            self.short_index += 1
            self.force_play_video()
        except Exception as e:
            print("Next short failed:", e)

    # ------------------------------------------------------------
    # PUBLISH STATS
    # Linux VRF → FILE
    # Others → HTTP

    def publish_stats(self, stats, stop=False):

        if self.linux_vrf_mode:
            try:
                with open(self.stats_file, "w") as f:
                    json.dump({"stats": stats, "stop": stop}, f)
            except Exception as e:
                print("Stats file write failed:", e)
            return

        if not self.host:
            return

        try:
            requests.post(
                f"http://{self.host}:5002/youtube_stats",
                json={self.device_name: stats, "stop": stop},
                timeout=5
            )
        except Exception as e:
            print("API send failed:", e)

    # ------------------------------------------------------------
    # RUN LOOP

    def run(self):
        self.open_shorts_home()
        self.force_play_video()

        if not self.enable_stats():
            self.driver.quit()
            return

        start_time = time.time()
        scroll_time = start_time
        next_sample_time = start_time
        sample_count = 0

        while sample_count < self.entire_duration:
            now = time.time()

            if now - scroll_time >= self.scroll_duration:
                self.next_short()
                scroll_time = now

            if now >= next_sample_time:
                stats = self.get_stats() or {
                    "Timestamp": datetime.now().strftime("%b %d %H:%M:%S"),
                    "Iterations": self.short_index,
                    "CurrentRes": "-",
                    "OptimalRes": "-",
                    "Viewport": "-",
                    "DroppedFrames": "0",
                    "TotalFrames": "0",
                    "BufferHealth": "0.0",
                    "LiveLatency": "0",
                    "LiveMode": "NA"
                }

                sample_count += 1
                self.dataset.append(stats)
                self.publish_stats(stats)
                next_sample_time += 1.0

        if self.dataset:
            self.publish_stats(self.dataset[-1], stop=True)

        self.driver.quit()
        print("Browser closed")

    # ------------------------------------------------------------
    # SAVE CSV

    def save_csv(self):
        filename = f"{self.device_name}_shorts_stats.csv"
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Iterations", "Timestamp", "CurrentRes", "OptimalRes",
                "Viewport", "DroppedFrames",
                "TotalFrames", "BufferHealth", "LiveLatency", "LiveMode"
            ])
            for s in self.dataset:
                writer.writerow([
                    s["Iterations"], s["Timestamp"], s["CurrentRes"], s["OptimalRes"],
                    s["Viewport"], s["DroppedFrames"],
                    s["TotalFrames"], s["BufferHealth"],
                    s["LiveLatency"], s["LiveMode"]
                ])

        print("CSV saved:", filename)


# ------------------------------------------------------------
# MAIN

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scroll", type=int, required=True)
    parser.add_argument("--duration", type=int, required=True)
    parser.add_argument("--host", type=str, default=None)
    parser.add_argument("--device_name", type=str, default="device")
    parser.add_argument("--url", type=str, default=None)
    parser.add_argument("--stats_file", type=str, default=None)

    args = parser.parse_args()

    yt = YouTubeShorts(
        scroll_duration=args.scroll,
        entire_duration=args.duration,
        url=args.url,
        host=args.host,
        device_name=args.device_name,
        stats_file=args.stats_file
    )

    yt.run()
    yt.save_csv()


if __name__ == "__main__":
    main()
