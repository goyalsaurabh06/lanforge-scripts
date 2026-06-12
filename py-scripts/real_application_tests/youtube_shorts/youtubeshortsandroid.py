from ppadb.client import Client as AdbClient
import uiautomator2 as u2
import xml.etree.ElementTree as ET
import time
import re
from datetime import datetime
import argparse
import os
import sys
import logging
import requests
import threading
import signal
import atexit

# ---------------- LOGGING ----------------
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(
    LOG_DIR, f"youtube_shorts_adb_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)

logger = logging.getLogger(__name__)


class YouTubeShortsADB:
    def __init__(self, host="127.0.0.1", port=5037, url=None):
        self.host = host
        self.port = port
        self.url = url

        self.adb_client = AdbClient(host=self.host, port=self.port)
        self.devices = {}
        self.u2_sessions = {}
        self._stop_event = threading.Event()
        self._cleanup_done = False
        self._cleanup_lock = threading.Lock()

    # ---------------- COMMAND ----------------
    def execute_cmd(self, serial, command):
        return self.devices[serial].shell(command)

    # ---------------- OPEN SHORTS ----------------
    def open_shorts_home(self, serial):
        url = self.url or "https://www.youtube.com/shorts"
        logger.info(f"[{serial}] Opening Shorts")

        self.execute_cmd(
            serial,
            f'am start -a android.intent.action.VIEW -d "{url}" com.google.android.youtube'
        )

        time.sleep(3)
        self.execute_cmd(serial, "input swipe 500 1500 500 500 200")
        time.sleep(1)

    # ---------------- WAIT FOR PLAYER ----------------
    def wait_for_player_ready(self, serial, timeout=30):
        d = self.u2_sessions[serial]
        start = time.time()

        while time.time() - start < timeout:
            if d(resourceId="com.google.android.youtube:id/player_container").exists:
                logger.info(f"[{serial}] Player ready")
                return True
            time.sleep(0.5)

        logger.warning(f"[{serial}] Player not ready (timeout)")
        return False

    # ---------------- ENABLE STATS ----------------
    def enable_stats_for_nerds(self, serial):
        d = self.u2_sessions[serial]

        logger.info(f"[{serial}] Enabling Stats for Nerds")

        for _ in range(12):
            try:
                if d(description="More").exists:
                    d(description="More").click()
                    time.sleep(1)

                    if d(text="Stats for nerds").exists:
                        d(text="Stats for nerds").click()
                        time.sleep(1)
                        logger.info(f"[{serial}] Stats for Nerds enabled")
                        return True

                time.sleep(1)
            except Exception:
                pass

        logger.warning(f"[{serial}] Failed to enable Stats for Nerds")
        return False

    # ---------------- SCROLL ----------------
    def scroll_to_next_short(self, serial):
        self.execute_cmd(serial, "input swipe 500 1500 500 500 200")
        time.sleep(0.01)

    # ---------------- FETCH STATS ----------------
    def fetch_stats_for_nerds(self, serial):
        d = self.u2_sessions[serial]

        try:
            root = ET.fromstring(d.dump_hierarchy(compressed=True))

            def get(res):
                n = root.find(f".//*[@resource-id='{res}']")
                return n.attrib.get("text") if n is not None else None

            raw_vf = get("com.google.android.youtube:id/video_format")
            vf = raw_vf
            if raw_vf:
                m = re.search(r"(\d+x\d+@\d+)", raw_vf)
                if m:
                    vf = m.group(1)

            stats = {
                "video_format": vf,
                "viewport": get("com.google.android.youtube:id/viewport"),
                "dropped_frames": get("com.google.android.youtube:id/dropped_frames"),
                "readahead": (get("com.google.android.youtube:id/readahead") or "0")
                                .replace("s", "").strip(),
            }

            if stats["dropped_frames"]:
                m = re.search(r"(\d+)\s*/\s*(\d+)", stats["dropped_frames"])
                if m:
                    stats["dropped_frames"] = int(m.group(1))
                    stats["total_frames"] = int(m.group(2))

            return stats
        except Exception:
            return {}

    # ---------------- POST STATS ----------------
    def post_stats(self, flask_ip, device_name, stats, iteration):
        payload = {
            device_name: {
                "Iterations": iteration,
                "Viewport": stats.get("viewport", "NA"),
                "DroppedFrames": stats.get("dropped_frames", "NA"),
                "TotalFrames": stats.get("total_frames", "NA"),
                "CurrentRes": stats.get("video_format", "NA"),
                "BufferHealth": stats.get("readahead", "0.0")
            }
        }

        try:
            requests.post(
                f"http://{flask_ip}:5002/youtube_stats",
                json=payload,
                timeout=1
            )
        except Exception:
            pass

    # ---------------- STOP CHECK ----------------
    def should_stop(self, flask_ip):
        if self._stop_event.is_set():
            return True
        try:
            r = requests.get(f"http://{flask_ip}:5002/check_stop", timeout=1)
            stop = r.json().get("stop", False)
            if stop:
                self._stop_event.set()
            return stop
        except Exception:
            return False

    # ---------------- FORCE STOP ALL DEVICES ----------------
    def force_stop_all(self):
        """Force-stop YouTube on ALL connected devices. Safe to call multiple times."""
        with self._cleanup_lock:
            if self._cleanup_done:
                return
            self._cleanup_done = True

        self._stop_event.set()  # signal all threads to exit

        for serial in list(self.devices.keys()):
            try:
                logger.info(f"[{serial}] Force-stopping YouTube (cleanup handler)")
                self.devices[serial].shell("am force-stop com.google.android.youtube")
                # Return to Candela interop app so device is ready for next test
                self.devices[serial].shell(
                    "am start -n com.candela.wecan/com.candela.wecan.StartupActivity"
                )
                logger.info(f"[{serial}] Returned to Candela interop app")
            except Exception as e:
                logger.warning(f"[{serial}] Cleanup force-stop failed: {e}")

    # ---------------- MAIN DEVICE LOOP ----------------
    def run_shorts_test(self, serial, duration, scroll_interval, flask_ip):
        try:
            self.open_shorts_home(serial)
            self.wait_for_player_ready(serial)
            self.enable_stats_for_nerds(serial)

            start = time.time()
            last_scroll = start
            iteration = 1


            while (time.time() - start < duration
                   and not self._stop_event.is_set()
                   and not self.should_stop(flask_ip)):
                stats = self.fetch_stats_for_nerds(serial)
                if stats:
                    self.post_stats(flask_ip, serial, stats, iteration)

                if time.time() - last_scroll >= scroll_interval:
                    self.scroll_to_next_short(serial)
                    iteration += 1
                    last_scroll = time.time()

                time.sleep(0.01)

        finally:
            logger.info(f"[{serial}] Stopping YouTube")
            try:
                self.execute_cmd(serial, "am force-stop com.google.android.youtube")
                # Return to Candela interop app so device is ready for next test
                self.execute_cmd(
                    serial,
                    "am start -n com.candela.wecan/com.candela.wecan.StartupActivity"
                )
                logger.info(f"[{serial}] Returned to Candela interop app")
            except Exception:
                pass

            logger.info(f"[{serial}] Thread exit")

    # ---------------- PARALLEL RUN ----------------
    def run_parallel(self, serials, duration, scroll, flask_ip):
        threads = []

        # Register signal + atexit handlers BEFORE starting threads
        def _signal_handler(signum, frame):
            logger.info(f"Received signal {signum} — force-stopping YouTube on all devices")
            self.force_stop_all()
            sys.exit(0)

        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)
        atexit.register(self.force_stop_all)

        for s in serials:
            self.devices[s] = self.adb_client.device(s)
            self.u2_sessions[s] = u2.connect(s)

            t = threading.Thread(
                target=self.run_shorts_test,
                args=(s, duration, scroll, flask_ip),
                daemon=True  # daemon so signal handler can exit quickly
            )
            threads.append(t)
            t.start()

        # Wait for threads, but allow signal interruption
        for t in threads:
            while t.is_alive():
                t.join(timeout=1.0)


# ---------------- MAIN ----------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--devices", required=True)
    parser.add_argument("--duration", type=int, required=True)
    parser.add_argument("--scroll", type=int, required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--url", default=None)
    args = parser.parse_args()

    yt = YouTubeShortsADB(url=args.url)
    serials = [s.strip() for s in args.devices.split(",")]

    logger.info(f"Running in parallel on: {serials}")
    yt.run_parallel(serials, args.duration, args.scroll, args.host)
    logger.info("Android Shorts script exiting cleanly")
    sys.exit(0)
