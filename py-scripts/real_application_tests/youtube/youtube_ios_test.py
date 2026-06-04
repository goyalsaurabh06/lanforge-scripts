#!/usr/bin/env python3
"""
iOS YouTube automation wrapper for LANforge interop testing.

YouTubeAutomation (Appium/GADS-based) is embedded directly so no external
import of youtube_automation_optimized.py is required.

Posts Stats for Nerds data to the lf_interop_youtube Flask server
at /youtube_stats so that CSV / HTML / PDF report generation works
exactly like every other platform.

Usage:
    python3 youtube_ios_test.py \
        --udid <device_udid> \
        --url  <youtube_url> \
        --duration <minutes> \
        --host <lanforge_host_ip> \
        --device_name <hostname_for_report> \
        [--res <resolution>] \
        [--gads_hub <http://host:port/grid>] \
        [--stats_interval <seconds>]
"""

import argparse
import logging
import os
import re
import signal
import sys
import threading
import time
import csv as csv_mod
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

try:
    import requests
except ImportError:
    print("requests not installed. Run: pip install requests")
    sys.exit(1)

try:
    from appium import webdriver
    from appium.options.ios import XCUITestOptions
    from selenium.common.exceptions import (
        WebDriverException,
        NoSuchElementException,
        TimeoutException,
        StaleElementReferenceException,
    )
    from appium.webdriver.common.appiumby import AppiumBy
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError:
    print("Appium/Selenium packages not installed. "
          "Run: pip install Appium-Python-Client selenium")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
logging.getLogger("requests.packages.urllib3.connectionpool").setLevel(logging.ERROR)

_ACTIVE_AUTOMATIONS: set = set()
_ACTIVE_LOCK = threading.Lock()


# ===========================================================================
# YouTubeAutomation — embedded from youtube_automation_optimized.py
# ===========================================================================

class YouTubeAutomation:
    """Coordinates Appium UI automation with optional network trace collection."""

    SKIP_AD_PREDICATE = (
        '(label BEGINSWITH "Skip" OR name == "ad.skip.button") '
        'AND visible == true'
    )
    PLAY_BUTTON_PREDICATE  = 'label == "Play" OR name == "Play" OR accessibilityIdentifier == "play-button"'
    PAUSE_BUTTON_PREDICATE = 'label == "Pause" OR name == "Pause" OR accessibilityIdentifier == "pause-button"'
    STATS_CONTAINER_PREDICATE = (
        'type == "XCUIElementTypeOther" AND name CONTAINS[c] "id.player.overlay" AND visible == true'
    )

    # Predicates for locating the Full Screen button in the YouTube player controls.
    # Tried in order — first match wins.
    FULLSCREEN_BUTTON_PREDICATES = [
        'type == "XCUIElementTypeButton" AND name == "id.player.fullscreen.button"',
        'type == "XCUIElementTypeButton" AND label == "Enter full screen"',
        'type == "XCUIElementTypeButton" AND label CONTAINS[c] "full screen"',
        'type == "XCUIElementTypeButton" AND label CONTAINS[c] "fullscreen"',
        'type == "XCUIElementTypeButton" AND name CONTAINS[c] "fullscreen"',
        'type == "XCUIElementTypeButton" AND accessibilityIdentifier CONTAINS[c] "fullscreen"',
    ]
    # Predicates to detect if already in fullscreen (exit-fullscreen button visible).
    EXIT_FULLSCREEN_PREDICATES = [
        'type == "XCUIElementTypeButton" AND label CONTAINS[c] "exit full screen"',
        'type == "XCUIElementTypeButton" AND label CONTAINS[c] "exit fullscreen"',
        'type == "XCUIElementTypeButton" AND name CONTAINS[c] "exit_fullscreen"',
    ]

    _STAT_PREDICATES = [
        (
            'elementType == XCUIElementTypeStaticText AND ('
            'label CONTAINS[c] "conn speed" OR '
            'label CONTAINS[c] "framedrop" OR '
            'label CONTAINS[c] "readahead" OR '
            'label CONTAINS[c] "view" OR '
            'label CONTAINS[c] "net activity" OR '
            'label CONTAINS[c] "video" OR '
            'label CONTAINS[c] "audio" OR '
            'label CONTAINS[c] "cpn:"'
            ')'
        ),
        (
            'type == "XCUIElementTypeStaticText" AND ('
            'label CONTAINS[c] "conn speed" OR '
            'label CONTAINS[c] "framedrop" OR '
            'label CONTAINS[c] "readahead" OR '
            'label CONTAINS[c] "view" OR '
            'label CONTAINS[c] "net activity" OR '
            'label CONTAINS[c] "video" OR '
            'label CONTAINS[c] "audio" OR '
            'label CONTAINS[c] "cpn:"'
            ')'
        ),
        (
            'type == "XCUIElementTypeStaticText" AND ('
            'name CONTAINS[c] "conn speed" OR '
            'name CONTAINS[c] "framedrop" OR '
            'name CONTAINS[c] "readahead" OR '
            'name CONTAINS[c] "view" OR '
            'name CONTAINS[c] "net activity" OR '
            'name CONTAINS[c] "video" OR '
            'name CONTAINS[c] "audio" OR '
            'name CONTAINS[c] "cpn"'
            ')'
        ),
    ]

    STAT_TEXT_PREDICATE = _STAT_PREDICATES[0]

    _STAT_KEYS = [
        ("conn_speed",   "conn speed"),
        ("readahead",    "readahead"),
        ("viewport",     "view"),
        ("framedrop",    "framedrop"),
        ("video",        "video"),
        ("audio",        "audio"),
        ("net_activity", "net activity"),
        ("cpn",          "cpn:"),
    ]

    def __init__(
        self,
        device_udid: str,
        output_dir: str = "automation_results",
        video_url: str = "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        bundle_id: str = "com.google.ios.youtube",
        process_name: str = "YouTube",
        duration: int = 60,
        app_launch_timeout: int = 15,
        ad_skip_timeout: int = 30,
        playback_check_timeout: int = 10,
        stats_poll_interval: int = 1,
        enable_network_trace: bool = False,
        client_secret: Optional[str] = None,
        session_retries: int = 3,
        session_retry_delay: float = 2.0,
        keepalive_interval: int = 20,
        stats_miss_threshold: int = 8,
        stats_recovery_cooldown: int = 30,
    ):
        self.device_udid = device_udid
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.enable_network_trace = enable_network_trace

        self.video_url = video_url
        self.bundle_id = bundle_id
        self.process_name = process_name
        self.duration = duration
        self.app_launch_timeout = app_launch_timeout
        self.ad_skip_timeout = ad_skip_timeout
        self.playback_check_timeout = playback_check_timeout
        self.stats_poll_interval = stats_poll_interval

        self.hub_url = os.getenv("GADS_HUB_URL", "http://192.168.207.75:10000/grid")
        self.client_secret = client_secret or os.getenv("GADS_CLIENT_SECRET", "9UX71PpZCQoK6ijNYm-Unnsd0rD-5_d4FPftk0c_Rqc=")
        self.session_retries = max(1, int(session_retries or 10))
        self.session_retry_delay = max(0.0, float(session_retry_delay or 5.0))
        self.keepalive_interval = max(10, int(keepalive_interval or 30))
        self.stats_miss_threshold = max(1, int(stats_miss_threshold))
        self.stats_recovery_cooldown = max(10, int(stats_recovery_cooldown))
        self._reconnect_count_without_stats = 0

        self.recorder = None
        self.driver = None
        self._driver_lock = threading.RLock()
        self._reconnect_lock = threading.Lock()
        self._shutdown = threading.Event()
        self._video_started_event = threading.Event()
        self._stats_polling_stop = threading.Event()
        self._ad_monitor_stop = threading.Event()
        self._stats_missing_dumped = False
        self.stats_csv_file: Optional[Path] = None

    def _setup_signal_handlers(self):
        def signal_handler(sig, frame):
            logger.warning("Shutdown signal received, cleaning up...")
            self._shutdown.set()
            self._cleanup()
            sys.exit(0)
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _cleanup(self):
        self._stats_polling_stop.set()
        self._ad_monitor_stop.set()
        for attr in ("stats_polling_thread", "ad_monitor_thread"):
            t = getattr(self, attr, None)
            if t and t.is_alive():
                t.join(timeout=3)
        if self.driver:
            try:
                with self._driver_lock:
                    try:
                        self.driver.terminate_app(self.bundle_id)
                    except Exception:
                        pass
                    self.driver.quit()
            except Exception as e:
                logger.error("Error closing Appium session: %s", e)
            finally:
                self.driver = None

    def request_shutdown(self):
        self._shutdown.set()
        self._cleanup()

    def _extract_video_id(self, url: str) -> Optional[str]:
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'youtu\.be\/([0-9A-Za-z_-]{11})',
            r'embed\/([0-9A-Za-z_-]{11})',
        ]
        for pattern in patterns:
            m = re.search(pattern, url)
            if m:
                return m.group(1)
        return None

    def _wait_for_element(self, predicate: str, timeout: int = 10, check_visible: bool = True):
        start = time.time()
        while time.time() - start < timeout and not self._shutdown.is_set():
            try:
                with self._driver_lock:
                    el = self.driver.find_element(AppiumBy.IOS_PREDICATE, predicate)
                    if not check_visible or el.is_displayed():
                        return el
            except (NoSuchElementException, TimeoutException, StaleElementReferenceException):
                pass
            time.sleep(0.5)
        return None

    def _keepalive(self) -> bool:
        try:
            with self._driver_lock:
                if self.driver is None:
                    return True
                _ = self.driver.current_context
            return True
        except Exception as e:
            logger.warning("[%s] Keepalive failed: %s", self.device_udid, e)
            return False

    def _is_session_alive(self) -> bool:
        try:
            with self._driver_lock:
                if self.driver is None:
                    return False
                self.driver.current_context
            return True
        except Exception:
            return False

    def _build_options(self) -> XCUITestOptions:
        options = XCUITestOptions()
        options.set_capability('udid', self.device_udid)
        options.set_capability('platformName', 'iOS')
        options.set_capability('automationName', 'XCUITest')
        options.set_capability('bundleId', self.bundle_id)
        options.set_capability('noReset', True)
        options.set_capability('shouldUseSingletonTestManager', False)
        options.set_capability('newCommandTimeout', max(self.duration + 600, 7200))
        options.set_capability('wdaConnectionTimeout', 240000)
        options.set_capability('wdaLaunchTimeout', 240000)
        options.set_capability('waitForIdleTimeout', 0)
        options.set_capability('maxTypingFrequency', 60)
        options.set_capability('mjpegServerPort', 0)
        if self.client_secret:
            options.set_capability('gads:clientSecret', self.client_secret)
        return options

    def _reconnect_session(self, force: bool = False, hard_reset: bool = False) -> bool:
        with self._reconnect_lock:
            if not force and not hard_reset and self._is_session_alive():
                return True
            mode = "HARD RESET" if hard_reset else "SOFT"
            logger.warning("[%s] Reconnecting Appium session (%s)...", self.device_udid, mode)
            with self._driver_lock:
                old_driver = self.driver
                self.driver = None
            if old_driver:
                session_id = None
                try:
                    session_id = old_driver.session_id
                    if hard_reset:
                        try:
                            old_driver.execute_script('mobile: terminateApp', {'bundleId': self.bundle_id})
                        except Exception:
                            pass
                    old_driver.quit()
                except Exception as e:
                    logger.debug("[%s] Quit failed: %s", self.device_udid, e)
                    try:
                        import requests as _req
                        _req.delete(self.hub_url.rstrip('/') + f"/session/{session_id}", timeout=5)
                    except Exception:
                        pass
                time.sleep(3.0)
            options = self._build_options()
            if hard_reset:
                options.set_capability('noReset', False)
                options.set_capability('shouldTerminateApp', True)
            else:
                options.set_capability('noReset', True)
                options.set_capability('shouldTerminateApp', False)
            for attempt in range(1, self.session_retries + 1):
                try:
                    new_driver = webdriver.Remote(self.hub_url, options=options)
                    if hard_reset:
                        video_id = self._extract_video_id(self.video_url)
                        new_driver.execute_script('mobile: deepLink', {
                            'url': f"youtube://watch?v={video_id}",
                            'bundleId': self.bundle_id,
                        })
                        time.sleep(5)
                    with self._driver_lock:
                        self.driver = new_driver
                    logger.info("[%s] Session reconnected (%s, attempt %d/%d)",
                                self.device_udid, mode, attempt, self.session_retries)
                    return True
                except Exception as e:
                    logger.warning("[%s] Reconnect attempt %d/%d failed: %s",
                                   self.device_udid, attempt, self.session_retries, e)
                    if attempt < self.session_retries:
                        time.sleep(self.session_retry_delay)
            logger.error("[%s] All reconnect attempts failed", self.device_udid)
            return False

    def _click_element(self, element) -> bool:
        try:
            with self._driver_lock:
                element.click()
            return True
        except Exception:
            return False

    def _safe_window_size(self) -> dict:
        try:
            with self._driver_lock:
                size = self.driver.get_window_size()
            if isinstance(size, dict):
                value = size.get("value") or {}
                w = int(size.get("width") or value.get("width") or 0)
                h = int(size.get("height") or value.get("height") or 0)
                if w > 0 and h > 0:
                    return {"width": w, "height": h}
        except Exception:
            pass
        return {"width": 390, "height": 844}

    def _dump_page_source_once(self, reason: str, source: Optional[str] = None):
        if self._stats_missing_dumped:
            return
        self._stats_missing_dumped = True
        safe_r = re.sub(r"[^0-9A-Za-z_-]+", "_", reason).strip("_") or "dump"
        safe_u = re.sub(r"[^0-9A-Za-z_-]+", "_", self.device_udid)
        dump_path = self.output_dir / f"page_source_{safe_r}_{safe_u}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xml"
        try:
            if source is None:
                with self._driver_lock:
                    source = self.driver.page_source
            dump_path.write_text(source or "", encoding="utf-8")
            logger.warning("[%s] Saved UI dump: %s", self.device_udid, dump_path)
        except Exception as e:
            logger.warning("[%s] Failed to save UI dump: %s", self.device_udid, e)

    def _parse_stat_elements(self, elements: list) -> Dict[str, str]:
        stats: Dict[str, str] = {}
        for el in elements:
            try:
                text = ""
                for attr in ("label", "name", "value"):
                    try:
                        val = (el.get_attribute(attr) or "").strip()
                        if val:
                            text = val
                            break
                    except Exception:
                        pass
                if not text:
                    continue
                lower = text.lower()
                for key, kw in self._STAT_KEYS:
                    if kw in lower and key not in stats:
                        stats[key] = text
                        break
            except Exception:
                pass
        return stats

    def _extract_stats_lightweight(self) -> Dict[str, str]:
        for predicate in self._STAT_PREDICATES:
            try:
                with self._driver_lock:
                    elements = self.driver.find_elements(AppiumBy.IOS_PREDICATE, predicate)
                if not elements:
                    continue
                stats = self._parse_stat_elements(elements)
                if stats:
                    return stats
            except Exception as e:
                logger.debug("[%s] Stats predicate failed: %s", self.device_udid, e)
        return {}

    def _poll_stats_for_nerds(self, interval: float = 3.0, duration: int = 60):
        """Default stats poller — writes raw CSV only. Overridden by subclass."""
        logger.info("[%s] Stats polling started (interval=%.1fs duration=%ds)",
                    self.device_udid, interval, duration)
        safe_udid = re.sub(r"[^0-9A-Za-z_-]+", "_", self.device_udid)
        csv_path = (
            self.output_dir
            / f"youtube_stats_{safe_udid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        self.stats_csv_file = csv_path
        headers = ["timestamp", "elapsed_sec", "conn_speed", "readahead", "viewport",
                   "framedrop", "video", "audio", "net_activity", "cpn"]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            csv_mod.DictWriter(f, fieldnames=headers).writeheader()

        self._video_started_event.wait()
        start_time = time.time()
        consecutive_errors = 0
        consecutive_misses = 0
        poll_count = 0

        while (not self._stats_polling_stop.is_set()
               and (time.time() - start_time) < duration):
            try:
                if not self._is_session_alive():
                    if not self._reconnect_session(force=True):
                        self._shutdown.set()
                        break
                    consecutive_errors = 0
                    consecutive_misses = 0
                    time.sleep(interval)
                    continue

                elapsed = time.time() - start_time
                stats = self._extract_stats_lightweight()

                if stats:
                    consecutive_misses = 0
                    self._reconnect_count_without_stats = 0
                    row = {"timestamp": datetime.now().isoformat(),
                           "elapsed_sec": f"{elapsed:.1f}",
                           **{k: stats.get(k, "") for k in
                              ["conn_speed", "readahead", "viewport", "framedrop",
                               "video", "audio", "net_activity", "cpn"]}}
                    with open(csv_path, "a", newline="", encoding="utf-8") as f:
                        csv_mod.DictWriter(f, fieldnames=headers).writerow(row)
                    poll_count += 1
                else:
                    consecutive_misses += 1
                    if consecutive_misses >= self.stats_miss_threshold:
                        self._reconnect_count_without_stats += 1
                        if self._reconnect_count_without_stats >= 2:
                            if self._reconnect_session(force=True, hard_reset=True):
                                consecutive_misses = 0
                                self._enable_stats_for_nerds()
                            else:
                                self._shutdown.set()
                                break
                        else:
                            if self._reconnect_session(force=True):
                                consecutive_misses = 0
                            else:
                                self._shutdown.set()
                                break
                        time.sleep(interval)
                        continue

                time.sleep(interval)
            except Exception as e:
                consecutive_errors += 1
                msg = str(e).lower()
                is_sess = ("404" in msg or "invalid session id" in msg
                           or "session does not exist" in msg)
                if is_sess or consecutive_errors >= 3:
                    if self._reconnect_session(force=True):
                        consecutive_errors = 0
                        consecutive_misses = 0
                    else:
                        self._shutdown.set()
                        break
                time.sleep(interval)

        logger.info("[%s] Stats polling stopped. %d rows -> %s",
                    self.device_udid, poll_count, csv_path)

    def _tap_point(self, x: int, y: int):
        with self._driver_lock:
            self.driver.tap([(x, y)])

    def _tap_first_element(self, predicates, timeout: int = 3) -> bool:
        end = time.time() + timeout
        while time.time() < end and not self._shutdown.is_set():
            for pred in predicates:
                try:
                    with self._driver_lock:
                        els = self.driver.find_elements(AppiumBy.IOS_PREDICATE, pred)
                        if els:
                            els[0].click()
                            return True
                except Exception:
                    pass
            time.sleep(0.25)
        return False

    def _tap_horizontal_scrollbar(self) -> bool:
        preds = [
            'type == "XCUIElementTypeOther" AND name BEGINSWITH "Horizontal scroll bar"',
            'type == "XCUIElementTypeOther" AND label BEGINSWITH "Horizontal scroll bar"',
        ]
        for pred in preds:
            try:
                with self._driver_lock:
                    els = self.driver.find_elements(AppiumBy.IOS_PREDICATE, pred)
                    if els:
                        rect = els[0].rect
                cx = int(rect["x"] + rect["width"] / 2)
                cy = int(rect["y"] + rect["height"] / 2)
                self._tap_point(cx, cy)
                return True
            except Exception:
                pass
        try:
            size = self._safe_window_size()
            self._tap_point(max(8, int(size["width"] * 0.02)),
                            int(size["height"] * 0.96))
            return True
        except Exception:
            return False

    def _get_player_rect(self) -> dict:
        predicates = [
            'name == "player_view"',
            'name == "YTPlayerView"',
            'type == "XCUIElementTypeOther" AND name CONTAINS[c] "player"',
            'type == "XCUIElementTypeOther" AND label CONTAINS[c] "player"',
        ]
        for pred in predicates:
            try:
                with self._driver_lock:
                    el = self.driver.find_element(AppiumBy.IOS_PREDICATE, pred)
                    rect = el.rect
                if rect['width'] > 100 and rect['height'] > 50:
                    return rect
            except Exception:
                pass
        size = self._safe_window_size()
        w = size['width']
        return {'x': 0, 'y': 88, 'width': w, 'height': int(w * 9 / 16)}

    # ── Full Screen activation ────────────────────────────────────────────
    def _enter_fullscreen(self) -> bool:
        """
        Switch the YouTube player to Full Screen mode.

        Strategy:
          1. Check if already in fullscreen (exit-fullscreen button visible).
          2. Tap the player center to surface overlay controls.
          3. Locate the fullscreen button via accessibility predicates.
          4. Fallback: tap the bottom-right corner of the player (where the
             fullscreen icon appears on all supported iPhone models).
          5. Verify fullscreen by checking for the exit-fullscreen button.

        Returns True if fullscreen was entered (or was already active),
        False otherwise.  Failure is non-fatal — the caller may proceed
        with Stats for Nerds in the current player mode.
        """
        logger.info("[%s] Entering fullscreen...", self.device_udid)

        try:
            # ── Already in fullscreen? ──────────────────────────────────
            for pred in self.EXIT_FULLSCREEN_PREDICATES:
                try:
                    with self._driver_lock:
                        els = self.driver.find_elements(AppiumBy.IOS_PREDICATE, pred)
                        if els and els[0].is_displayed():
                            logger.info("[%s] Already in fullscreen mode", self.device_udid)
                            return True
                except Exception:
                    pass

            # ── Step 1: Tap the player to make controls visible ────────
            rect = self._get_player_rect()
            player_cx = rect['x'] + rect['width'] // 2
            player_cy = rect['y'] + rect['height'] // 2
            self._tap_point(player_cx, player_cy)
            time.sleep(0.6)

            # ── Step 2: Try accessibility-based fullscreen button tap ──
            if self._tap_first_element(self.FULLSCREEN_BUTTON_PREDICATES, timeout=5):
                logger.info("[%s] Fullscreen button tapped via accessibility predicate", self.device_udid)
                time.sleep(1.5)  # allow rotation / animation to settle
                logger.info("[%s] Fullscreen enabled successfully", self.device_udid)
                return True

            # ── Step 3: Coordinate fallback ────────────────────────────
            logger.warning(
                "[%s] Fullscreen button not found via accessibility, "
                "using coordinate fallback", self.device_udid,
            )

            # Re-tap player center to ensure controls are still visible
            self._tap_point(player_cx, player_cy)
            time.sleep(0.5)

            # The fullscreen icon sits in the bottom-right corner of the
            # player area on all supported iPhone sizes.  Use proportional
            # offsets from the player rect so it scales across models.
            fs_x = rect['x'] + rect['width'] - max(24, int(rect['width'] * 0.06))
            fs_y = rect['y'] + rect['height'] - max(14, int(rect['height'] * 0.07))
            logger.info("[%s] Coordinate fallback: tapping (%d, %d)", self.device_udid, fs_x, fs_y)
            self._tap_point(fs_x, fs_y)
            time.sleep(1.5)

            # ── Step 4: Verify fullscreen ──────────────────────────────
            for pred in self.EXIT_FULLSCREEN_PREDICATES:
                try:
                    with self._driver_lock:
                        els = self.driver.find_elements(AppiumBy.IOS_PREDICATE, pred)
                        if els:
                            logger.info(
                                "[%s] Fullscreen enabled successfully (coordinate fallback)",
                                self.device_udid,
                            )
                            return True
                except Exception:
                    pass

            # Secondary coordinate attempt — some models place the button
            # slightly differently; use a fixed pixel offset as a last resort.
            logger.warning(
                "[%s] First coordinate attempt may have missed, "
                "trying alternative position", self.device_udid,
            )
            self._tap_point(player_cx, player_cy)
            time.sleep(0.5)
            alt_fs_x = rect['x'] + rect['width'] - 30
            alt_fs_y = rect['y'] + rect['height'] - 15
            logger.info("[%s] Alternative coordinate fallback: tapping (%d, %d)", self.device_udid, alt_fs_x, alt_fs_y)
            self._tap_point(alt_fs_x, alt_fs_y)
            time.sleep(1.5)

            logger.info(
                "[%s] Fullscreen enabled successfully (alternative coordinate fallback)",
                self.device_udid,
            )
            return True

        except Exception as e:
            logger.error("[%s] Failed to enter fullscreen: %s", self.device_udid, e)
            return False

    def _enable_stats_for_nerds(self) -> bool:
        try:
            if self._extract_stats_lightweight():
                logger.info("[%s] Stats for Nerds already visible", self.device_udid)
                return True
        except Exception:
            pass
        logger.info("[%s] Enabling Stats for Nerds...", self.device_udid)
        try:
            rect = self._get_player_rect()
            player_cx = rect['x'] + rect['width'] // 2
            player_cy = rect['y'] + rect['height'] // 2
            gear_x, gear_y = 358, 77
            self._tap_point(player_cx, player_cy)
            time.sleep(0.4)
            settings_preds = [
                'type == "XCUIElementTypeButton" AND name == "id.player.overflow.button"',
                'type == "XCUIElementTypeButton" AND label == "Player settings"',
                'type == "XCUIElementTypeButton" AND name == "Player settings"',
            ]
            if not self._tap_first_element(settings_preds, timeout=3):
                self._tap_point(gear_x, gear_y)
            time.sleep(0.5)
            if not self._tap_horizontal_scrollbar():
                raise RuntimeError("Could not tap horizontal scroll bar (1/2)")
            time.sleep(0.25)
            if not self._tap_horizontal_scrollbar():
                raise RuntimeError("Could not tap horizontal scroll bar (2/2)")
            time.sleep(0.8)
            logger.info("[%s] Stats for Nerds activation complete", self.device_udid)
            return True
        except Exception as e:
            logger.error("[%s] Error enabling Stats for Nerds: %s", self.device_udid, e)
            return False

    def _check_video_playing(self) -> bool:
        try:
            if self._wait_for_element(self.PAUSE_BUTTON_PREDICATE, timeout=2):
                if not self._wait_for_element(self.PLAY_BUTTON_PREDICATE, timeout=1):
                    return True
            return False
        except Exception:
            return False

    def _handle_skip_ad(self) -> bool:
        logger.info("[%s] Monitoring for Skip Ad button...", self.device_udid)
        start = time.time()
        while time.time() - start < self.ad_skip_timeout and not self._shutdown.is_set():
            try:
                skip_btn = self._wait_for_element(self.SKIP_AD_PREDICATE, timeout=2)
                if skip_btn:
                    self._click_element(skip_btn)
                    time.sleep(1)
                    return True
            except Exception:
                pass
            if self._check_video_playing():
                return True
            time.sleep(1)
        return self._check_video_playing()

    def _monitor_skip_ads_continuous(self, interval: float = 1.0):
        while not self._ad_monitor_stop.is_set() and not self._shutdown.is_set():
            try:
                skip_btn = self._wait_for_element(self.SKIP_AD_PREDICATE, timeout=1)
                if skip_btn:
                    if self._click_element(skip_btn):
                        time.sleep(0.6)
                time.sleep(interval)
            except Exception:
                time.sleep(interval)

    def _wait_for_video_playback(self) -> bool:
        start = time.time()
        while time.time() - start < self.playback_check_timeout and not self._shutdown.is_set():
            if self._check_video_playing():
                return True
            time.sleep(0.5)
        return True

    def run_appium_task(self) -> bool:
        logger.info("[%s] Connecting to GADS Hub at %s", self.device_udid, self.hub_url)
        options = self._build_options()
        try:
            last_error = None
            for attempt in range(1, self.session_retries + 1):
                try:
                    self.driver = webdriver.Remote(self.hub_url, options=options)
                    logger.info("[%s] Appium session established", self.device_udid)
                    break
                except Exception as e:
                    last_error = e
                    logger.warning("[%s] Session attempt %d/%d failed: %s",
                                   self.device_udid, attempt, self.session_retries, e)
                    if attempt < self.session_retries:
                        time.sleep(self.session_retry_delay)
            if not self.driver:
                raise WebDriverException(f"Unable to create Appium session: {last_error}")

            for _ in range(self.app_launch_timeout):
                if self._shutdown.is_set():
                    return False
                if self._keepalive():
                    break
                time.sleep(1)

            video_id = self._extract_video_id(self.video_url)
            if not video_id:
                logger.error("[%s] Cannot extract video ID from: %s", self.device_udid, self.video_url)
                return False

            youtube_deep_link = f"youtube://watch?v={video_id}"
            try:
                with self._driver_lock:
                    self.driver.execute_script('mobile: deepLink', {
                        'url': youtube_deep_link, 'bundleId': self.bundle_id,
                    })
            except Exception as e:
                logger.warning("[%s] Deep link failed (%s), trying openUrl...", self.device_udid, e)
                with self._driver_lock:
                    self.driver.execute_script('mobile: openUrl', {'url': youtube_deep_link})

            time.sleep(5)
            self._ad_monitor_stop.clear()
            self.ad_monitor_thread = threading.Thread(
                target=self._monitor_skip_ads_continuous, args=(3.0,), daemon=True, name="AdMonitor"
            )
            self.ad_monitor_thread.start()
            self._handle_skip_ad()
            if not self._wait_for_video_playback():
                logger.error("[%s] Video never started", self.device_udid)
                return False

            # ── Enter Full Screen before enabling Stats for Nerds ──
            fullscreen_ok = self._enter_fullscreen()
            if not fullscreen_ok:
                logger.warning(
                    "[%s] Could not enter fullscreen — continuing with Stats for Nerds in current mode",
                    self.device_udid,
                )

            stats_ok = self._enable_stats_for_nerds()
            if stats_ok:
                self._stats_polling_stop.clear()
                self.stats_polling_thread = threading.Thread(
                    target=self._poll_stats_for_nerds,
                    args=(self.stats_poll_interval, self.duration),
                    daemon=True, name="StatsPoller"
                )
                self.stats_polling_thread.start()

            # ── Duration timer starts HERE — only after fullscreen +
            #    Stats for Nerds are ready.  The _video_started_event
            #    also unblocks the stats poller's internal duration
            #    countdown, so both timers are synchronised.  ──
            self._video_started_event.set()
            logger.info(
                "[%s] Fullscreen=%s | StatsForNerds=%s — starting %ds duration timer NOW",
                self.device_udid, fullscreen_ok, stats_ok, self.duration,
            )
            elapsed = 0
            last_keepalive = time.time()
            while elapsed < self.duration and not self._shutdown.is_set():
                time.sleep(1)
                elapsed += 1
                if time.time() - last_keepalive >= self.keepalive_interval:
                    if not self._keepalive():
                        if not self._reconnect_session(force=True):
                            self._shutdown.set()
                            return False
                    last_keepalive = time.time()
            return not self._shutdown.is_set()

        except WebDriverException as e:
            logger.error("[%s] WebDriver error: %s", self.device_udid, e)
            return False
        except Exception as e:
            logger.error("[%s] Unexpected error: %s", self.device_udid, e, exc_info=True)
            return False
        finally:
            self._cleanup()

    def run(self) -> bool:
        if threading.current_thread() is threading.main_thread():
            self._setup_signal_handlers()
        logger.info("[%s] Starting YouTube automation | video=%s | duration=%ds",
                    self.device_udid, self.video_url, self.duration)
        results = {"appium": False}

        if not self.enable_network_trace:
            results["appium"] = self.run_appium_task()
            return results["appium"]

        appium_thread = threading.Thread(target=lambda: results.update({"appium": self.run_appium_task()}))
        try:
            appium_thread.start()
            appium_thread.join()
            return results["appium"]
        except KeyboardInterrupt:
            return False
        except Exception as e:
            logger.error("Unexpected error: %s", e)
            return False
        finally:
            self._shutdown.set()
            self._cleanup()


# ===========================================================================
# Stat string parsers
# ===========================================================================

def _first_number(text: str) -> Optional[str]:
    """Return the first numeric token found in text."""
    m = re.search(r"[\d,]+(?:\.\d+)?", text)
    return m.group(0).replace(",", "") if m else None


def parse_ios_stats(raw: Dict[str, str]) -> Dict[str, str]:
    """
    Convert raw YouTube Stats for Nerds label strings (iOS accessibility tree)
    into the Flask /youtube_stats dict format.

    raw key      sample label text
    ─────────────────────────────────────────────────────────────
    conn_speed   "Conn Speed: 2,345 Kbps"
    readahead    "Readahead: 25.3 s"
    framedrop    "Framedrop: 0/1234"
    video        "Video: h264 @ 1080p30 | 8000Kbps"
    audio        "Audio: mp4a.40.2"
    net_activity "Net Activity: 1,234 KB"
    """
    result: Dict[str, str] = {
        "Viewport": "NA",
        "DroppedFrames": "0",
        "TotalFrames": "0",
        "CurrentRes": "NA",
        "OptimalRes": "NA",
        "BufferHealth": "0.0",
        "VideoCodec": "NA",
        "AudioCodec": "NA",
        "ConnectionSpeedKbps": "NA",
        "NetworkActivityKB": "NA",
        "LiveLatency(sec)": "NA",
        "Timestamp": datetime.now().strftime("%H:%M:%S"),
    }

    conn = raw.get("conn_speed", "")
    if conn:
        val = _first_number(conn)
        if val:
            result["ConnectionSpeedKbps"] = val

    readahead = raw.get("readahead", "")
    if readahead:
        val = _first_number(readahead)
        if val:
            result["BufferHealth"] = val

    viewport = raw.get("viewport", "")
    if viewport:
        value = re.sub(r"^\s*View(?:port)?:\s*", "", viewport, flags=re.IGNORECASE).strip()
        value = re.sub(r"\bSBDL\b", "", value, flags=re.IGNORECASE).strip()
        value = re.sub(r"\s*/\s*$", "", value).strip()
        if value:
            result["Viewport"] = value

    framedrop = raw.get("framedrop", "")
    if framedrop:
        m = re.search(r"(\d+)\s*/\s*(\d+)", framedrop)
        if m:
            result["DroppedFrames"] = m.group(1)
            result["TotalFrames"] = m.group(2)
        else:
            val = _first_number(framedrop)
            if val:
                result["DroppedFrames"] = val

    video = raw.get("video", "")
    if video:
        codec_m = re.search(r"(?:Video:\s*)?([\w.]+)", video, re.IGNORECASE)
        if codec_m:
            result["VideoCodec"] = codec_m.group(1)
        res_m = re.search(r"(\d{3,4}p\d*)", video, re.IGNORECASE)
        if res_m:
            result["CurrentRes"] = res_m.group(1)
            result["OptimalRes"] = res_m.group(1)

    audio = raw.get("audio", "")
    if audio:
        codec_m = re.search(r"(?:Audio:\s*)?([\w.]+)", audio, re.IGNORECASE)
        if codec_m:
            result["AudioCodec"] = codec_m.group(1)

    net = raw.get("net_activity", "")
    if net:
        m = re.search(r"([\d,]+(?:\.\d+)?)\s*(KB|MB|GB)", net, re.IGNORECASE)
        if m:
            try:
                val = float(m.group(1).replace(",", ""))
                unit = m.group(2).upper()
                if unit == "MB":
                    val *= 1024.0
                elif unit == "GB":
                    val *= 1024.0 * 1024.0
                result["NetworkActivityKB"] = str(int(val))
            except ValueError:
                pass

    return result


# ===========================================================================
# Extended automation — posts stats to Flask
# ===========================================================================

class iOSYouTubeAutomation(YouTubeAutomation):
    """
    YouTubeAutomation subclass that additionally POSTs parsed stats to the
    LANforge Flask server (/youtube_stats) so that CSV / HTML / PDF report
    generation in lf_interop_youtube.py works automatically.
    """

    def __init__(self, flask_host: str, device_name: str, **kwargs):
        super().__init__(**kwargs)
        self.flask_host = flask_host
        self.device_name = device_name
        self._flask_stats_url = f"http://{flask_host}:5002/youtube_stats"
        self._flask_stop_url  = f"http://{flask_host}:5002/check_stop"

    def _post_to_flask(self, parsed: Dict[str, str]):
        try:
            requests.post(self._flask_stats_url, json={self.device_name: parsed}, timeout=5)
        except Exception as exc:
            logger.debug("[%s] Flask POST failed: %s", self.device_udid, exc)

    def _check_stop_signal(self) -> bool:
        try:
            resp = requests.get(self._flask_stop_url, timeout=3)
            return resp.json().get("stop", False)
        except Exception:
            return False

    def _signal_stop_to_flask(self):
        try:
            requests.post(self._flask_stats_url,
                          json={self.device_name: {"stop": True}}, timeout=5)
        except Exception:
            pass

    def _poll_stats_for_nerds(self, interval: float = 3.0, duration: int = 60):
        """Override: parse stats and POST to Flask on every poll cycle."""
        logger.info("[%s] Stats polling started → Flask %s (interval=%.1fs duration=%ds)",
                    self.device_udid, self._flask_stats_url, interval, duration)

        safe_udid = re.sub(r"[^0-9A-Za-z_-]+", "_", self.device_udid)
        csv_path = (
            self.output_dir
            / f"youtube_stats_{safe_udid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        self.stats_csv_file = csv_path
        raw_headers = ["timestamp", "elapsed_sec", "conn_speed", "readahead", "viewport",
                       "framedrop", "video", "audio", "net_activity", "cpn"]
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            csv_mod.DictWriter(fh, fieldnames=raw_headers).writeheader()

        self._video_started_event.wait()
        start_time = time.time()
        consecutive_errors = 0
        consecutive_misses = 0
        poll_count = 0

        while (not self._stats_polling_stop.is_set()
               and (time.time() - start_time) < duration):

            if self._check_stop_signal():
                logger.info("[%s] Flask stop signal — ending stats polling.", self.device_udid)
                self._shutdown.set()
                break

            try:
                if not self._is_session_alive():
                    if not self._reconnect_session(force=True):
                        self._shutdown.set()
                        break
                    consecutive_errors = 0
                    consecutive_misses = 0
                    time.sleep(interval)
                    continue

                elapsed = time.time() - start_time
                raw_stats = self._extract_stats_lightweight()

                if raw_stats:
                    consecutive_misses = 0
                    self._reconnect_count_without_stats = 0

                    self._post_to_flask(parse_ios_stats(raw_stats))

                    row = {"timestamp": datetime.now().isoformat(),
                           "elapsed_sec": f"{elapsed:.1f}",
                           **{k: raw_stats.get(k, "") for k in
                              ["conn_speed", "readahead", "viewport", "framedrop",
                               "video", "audio", "net_activity", "cpn"]}}
                    with open(csv_path, "a", newline="", encoding="utf-8") as fh:
                        csv_mod.DictWriter(fh, fieldnames=raw_headers).writerow(row)
                    poll_count += 1

                else:
                    consecutive_misses += 1
                    logger.warning("[%s] Stats not found (%d/%d)",
                                   self.device_udid, consecutive_misses, self.stats_miss_threshold)
                    if consecutive_misses >= self.stats_miss_threshold:
                        self._reconnect_count_without_stats += 1
                        if self._reconnect_count_without_stats >= 2:
                            logger.error("[%s] Hard reset triggered", self.device_udid)
                            if self._reconnect_session(force=True, hard_reset=True):
                                consecutive_misses = 0
                                consecutive_errors = 0
                                self._enable_stats_for_nerds()
                            else:
                                self._shutdown.set()
                                break
                        else:
                            if self._reconnect_session(force=True):
                                consecutive_misses = 0
                                consecutive_errors = 0
                            else:
                                self._shutdown.set()
                                break
                        time.sleep(interval)
                        continue

                time.sleep(interval)

            except Exception as exc:
                consecutive_errors += 1
                msg = str(exc).lower()
                is_sess = ("404" in msg or "invalid session id" in msg
                           or "session does not exist" in msg)
                if is_sess or consecutive_errors >= 3:
                    if self._reconnect_session(force=True):
                        consecutive_errors = 0
                        consecutive_misses = 0
                    else:
                        self._shutdown.set()
                        break
                time.sleep(interval)

        self._signal_stop_to_flask()
        logger.info("[%s] Stats polling done — %d rows -> %s",
                    self.device_udid, poll_count, csv_path)


# ===========================================================================
# Candela interop app flow — tap testroom button after YouTube test
# ===========================================================================

def _candela_connect(udid: str, hub_url: str, bundle_id: str, secret: str):
    options = XCUITestOptions()
    options.set_capability("udid", udid)
    options.set_capability("platformName", "iOS")
    options.set_capability("automationName", "XCUITest")
    options.set_capability("bundleId", bundle_id)
    options.set_capability("noReset", True)
    options.set_capability("shouldUseSingletonTestManager", False)
    options.set_capability("newCommandTimeout", 600)
    if secret:
        options.set_capability("gads:clientSecret", secret)
    logger.info("[%s] Connecting to Candela interop app at %s", udid, hub_url)
    return webdriver.Remote(hub_url, options=options)


def _candela_find_testroom_button(driver, timeout: int):
    wait = WebDriverWait(driver, timeout)
    predicate = (
        "type == 'XCUIElementTypeButton' AND visible == 1 AND enabled == 1 "
        "AND (name == 'testroom' OR label == 'testroom')"
    )
    return wait.until(EC.element_to_be_clickable((AppiumBy.IOS_PREDICATE, predicate)))


def _candela_handle_post_join_popups(driver, timeout: int):
    join_labels = {"Join", "Join Network"}
    location_labels = {"Always Allow"}
    deadline = time.time() + max(8, timeout)
    handled_join = False
    handled_location = False
    while time.time() < deadline:
        try:
            _ = driver.switch_to.alert
        except Exception:
            time.sleep(0.4)
            continue
        try:
            buttons = driver.execute_script("mobile: alert", {"action": "getButtons"}) or []
        except Exception:
            time.sleep(0.4)
            continue
        if not isinstance(buttons, list) or not buttons:
            time.sleep(0.4)
            continue
        button_set = set(buttons)
        target = None
        if not handled_location:
            for lbl in location_labels:
                if lbl in button_set:
                    target = lbl
                    break
        if target is None and not handled_join:
            for lbl in join_labels:
                if lbl in button_set:
                    target = lbl
                    break
        if target is None:
            time.sleep(0.4)
            continue
        try:
            driver.execute_script("mobile: alert", {"action": "accept", "buttonLabel": target})
            if target in location_labels:
                handled_location = True
                logger.info("Handled location permission popup (Always Allow)")
            if target in join_labels:
                handled_join = True
                logger.info("Handled network join popup (Join)")
            time.sleep(0.5)
        except Exception:
            time.sleep(0.4)
        if handled_join and handled_location:
            break


def run_candela_interop_flow(udid: str, hub_url: str, bundle_id: str, secret: str,
                              timeout: int = 20) -> bool:
    """Connect to Candela interop app and tap testroom (forms are already pre-filled)."""
    driver = None
    try:
        driver = _candela_connect(udid, hub_url, bundle_id, secret)
        button = _candela_find_testroom_button(driver, timeout)
        button.click()
        _candela_handle_post_join_popups(driver, timeout)
        logger.info("[%s] Candela interop: tapped testroom button", udid)
        return True
    except TimeoutException as e:
        logger.error("[%s] Candela interop timeout — element not found: %s", udid, e)
        return False
    except WebDriverException as e:
        logger.error("[%s] Candela interop WebDriver error: %s", udid, e)
        return False
    except Exception as e:
        logger.error("[%s] Candela interop unexpected error: %s", udid, e)
        return False
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


# ===========================================================================
# Entry point
# ===========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="iOS YouTube automation for LANforge interop testing"
    )
    parser.add_argument("--udid", required=True, help="iOS device UDID")
    parser.add_argument("--url", required=True, help="YouTube video URL")
    parser.add_argument(
        "--duration", type=int, required=True,
        help="Test duration in minutes (matches lf_interop_youtube convention)",
    )
    parser.add_argument("--host", required=True, help="LANforge host IP (Flask server)")
    parser.add_argument("--device_name", required=True, help="Device hostname for reporting")
    parser.add_argument("--res", default="Auto", help="Target video resolution")
    parser.add_argument(
        "--gads_hub", default=None,
        help="GADS hub URL (overrides GADS_HUB_URL env var)",
    )
    parser.add_argument("--stats_interval", type=int, default=3,
                        help="Stats polling interval in seconds (default: 3)")
    parser.add_argument("--session_retries", type=int, default=3,
                        help="Appium session retry attempts (default: 3)")
    parser.add_argument("--candela_bundle_id", default="com.candela.wecan.interop-ios",
                        help="Candela interop app bundle ID (default: com.candela.wecan.interop-ios)")
    parser.add_argument("--candela_timeout", type=int, default=20,
                        help="Element wait timeout in seconds for Candela flow (default: 20)")
    args = parser.parse_args()

    if args.gads_hub:
        os.environ["GADS_HUB_URL"] = args.gads_hub

    automation = iOSYouTubeAutomation(
        flask_host=args.host,
        device_name=args.device_name,
        device_udid=args.udid,
        video_url=args.url,
        duration=args.duration * 60,   # minutes → seconds
        stats_poll_interval=args.stats_interval,
        enable_network_trace=False,
        session_retries=args.session_retries,
    )

    success = automation.run()

    hub = args.gads_hub or os.getenv("GADS_HUB_URL", "http://192.168.207.75:10000/grid")
    secret = os.getenv("GADS_CLIENT_SECRET", "9UX71PpZCQoK6ijNYm-Unnsd0rD-5_d4FPftk0c_Rqc=")
    run_candela_interop_flow(
        udid=args.udid,
        hub_url=hub,
        bundle_id=args.candela_bundle_id,
        secret=secret,
        timeout=args.candela_timeout,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
