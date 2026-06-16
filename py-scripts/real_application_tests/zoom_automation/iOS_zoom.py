#!/usr/bin/env python3
import argparse
import atexit
import logging
import os
import re
import signal
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from appium import webdriver
    from appium.options.ios import XCUITestOptions
    from appium.webdriver.common.appiumby import AppiumBy
    from selenium.common.exceptions import (
        WebDriverException,
        NoSuchElementException,
        StaleElementReferenceException,
    )
    from selenium.webdriver.common.action_chains import ActionChains
except ImportError:
    print("Required packages not installed. Run: pip install Appium-Python-Client selenium")
    sys.exit(1)


ZOOM_BUNDLE_ID = "us.zoom.videomeetings"

# Tracks every live ZoomAutomator so signal handlers and atexit can
# terminate all Appium sessions regardless of which thread owns them.
_active_automations = []
_automations_lock = threading.Lock()


def _cleanup_all(sig=None, frame=None):
    """Terminate every active Appium session. Called on SIGINT, SIGTERM, or atexit."""
    with _automations_lock:
        instances = list(_active_automations)
    if not instances:
        if sig is not None:
            sys.exit(0)
        return
    print(f"\nSignal received — terminating {len(instances)} Appium session(s)...", flush=True)
    threads = [threading.Thread(target=inst._cleanup, daemon=True) for inst in instances]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=8)
    if sig is not None:
        sys.exit(0)


class ZoomAutomator:
    # Zoom iOS: labels for the 'Join Audio' dialog
    AUDIO_JOIN_LABELS = [
        "Join with Internet Audio",
        "Call via Device Audio",
        "Call using Internet Audio",
        "Join Audio by Internet",
        "Internet Audio",
        "Join Audio",
    ]

    # iOS system permission sheet allow-buttons
    PERMISSION_ALLOW_LABELS = [
        "Allow",
        "Allow While Using App",
        "Allow Once",
        "OK",
    ]

    def __init__(
        self,
        device_udid,
        invite_link,
        meeting_password=None,
        display_name="Test User",
        bundle_id=ZOOM_BUNDLE_ID,
        hub_url=None,
        client_secret=None,
        element_timeout=20,
        launch_timeout=15,
        enable_screen_share=False,
        duration_minutes=None,
        enable_audio=False,
        enable_video=False,
    ):
        self.device_udid = device_udid
        self.bundle_id = bundle_id
        self.display_name = display_name
        self.element_timeout = element_timeout
        self.launch_timeout = launch_timeout
        self.enable_screen_share = enable_screen_share
        self.duration_minutes = duration_minutes
        self.enable_audio = enable_audio
        self.enable_video = enable_video
        self.hub_url = hub_url or os.getenv("GADS_HUB_URL", "http://localhost:10000/grid")
        self.client_secret = client_secret or os.getenv("GADS_CLIENT_SECRET", "")
        self.driver = None
        self.logger = self._create_logger()

        # Parse meeting ID and URL-encoded pwd from the invite link
        self.meeting_id, self.url_pwd = self._parse_invite_link(invite_link)

        # --password flag overrides the raw passcode typed into the UI password screen.
        # The url_pwd (extracted from the link) is used only in the deep link construction.
        self.meeting_password = meeting_password

        if not self.meeting_id:
            self.logger.error(f"[{self.device_udid}] Could not extract meeting ID from: {invite_link}")
            sys.exit(1)

        self.logger.info(f"[{self.device_udid}] Meeting ID  : {self.meeting_id}")
        self.logger.info(f"[{self.device_udid}] URL pwd     : {'present' if self.url_pwd else 'not in URL'}")
        self.logger.info(f"[{self.device_udid}] Raw password: {'****' if self.meeting_password else '(none)'}")
        self.logger.info(f"[{self.device_udid}] Display name: {self.display_name}")
        if self.duration_minutes is not None:
            self.logger.info(f"[{self.device_udid}] Duration    : {self.duration_minutes} minute(s)")
        if self.enable_audio:
            self.logger.info(f"[{self.device_udid}] Audio flag enabled — will unmute after joining.")
        if self.enable_video:
            self.logger.info(f"[{self.device_udid}] Video flag enabled — will start camera after joining.")

    def _create_logger(self):
        log_dir = os.path.join(os.getcwd(), "zoom_mobile_logs")
        os.makedirs(log_dir, exist_ok=True)

        logger_name = f"{__name__}.{self.device_udid}"
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        if not logger.handlers:
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

            file_handler = logging.FileHandler(
                os.path.join(log_dir, f"{self.device_udid}.log"), mode="w"
            )
            file_handler.setFormatter(formatter)

            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setFormatter(formatter)

            logger.addHandler(file_handler)
            logger.addHandler(stream_handler)

        return logger

    def _parse_invite_link(self, url):
        """Return (meeting_id, url_pwd) parsed from a Zoom invite URL."""
        id_match = re.search(r"/j/(\d+)|/wc/join/(\d+)", url)
        meeting_id = (id_match.group(1) or id_match.group(2)) if id_match else None

        pwd_match = re.search(r"[?&]pwd=([^&\s#]+)", url)
        url_pwd = pwd_match.group(1) if pwd_match else None

        return meeting_id, url_pwd

    def _connect(self):
        options = XCUITestOptions()
        options.set_capability("udid", self.device_udid)
        options.set_capability("platformName", "iOS")
        options.set_capability("automationName", "XCUITest")
        # ZOOM-ANCHORED SESSION: target Zoom for the main flow, but use deep-scan capabilities
        # to ensure system overlays are visible.
        options.set_capability("bundleId", self.bundle_id)
        options.set_capability("noReset", True)
        options.set_capability("shouldUseSingletonTestManager", False)
        options.set_capability("newCommandTimeout", 300)

        # Allows seeing elements outside the app (like ReplayKit / Start Broadcast)
        options.set_capability("appium:includeUnifiedUISchedule", True)
        # Don't wait for animations to stop (fixes ReplayKit "ghosting")
        options.set_capability("appium:waitForQuiescence", False)

        if self.client_secret:
            options.set_capability("gads:clientSecret", self.client_secret)

        self.logger.info(f"[{self.device_udid}] Connecting to GADS hub at {self.hub_url} ...")
        self.driver = webdriver.Remote(self.hub_url, options=options)
        self.logger.info(f"[{self.device_udid}] Appium session established")

    def _cleanup(self):
        if self.driver:
            self.logger.info(f"[{self.device_udid}] Stopping Zoom and terminating Appium session...")
            try:
                self.driver.terminate_app(self.bundle_id)
                self.logger.info(f"[{self.device_udid}] Zoom app stopped on device")
            except Exception as e:
                self.logger.warning(f"[{self.device_udid}] Could not stop Zoom app: {e}")
            try:
                self.driver.quit()
                self.logger.info(f"[{self.device_udid}] Appium session terminated")
            except Exception as e:
                self.logger.warning(
                    f"[{self.device_udid}] Session quit failed (may still be active on server): {e}"
                )
            self.driver = None

    def _find(self, predicate, timeout=None):
        """Poll until first visible element matching predicate is found."""
        deadline = time.time() + (timeout or self.element_timeout)
        while time.time() < deadline:
            try:
                el = self.driver.find_element(AppiumBy.IOS_PREDICATE, predicate)
                if el.is_displayed():
                    return el
            except (NoSuchElementException, StaleElementReferenceException):
                pass
            time.sleep(0.4)
        return None

    def _find_any(self, predicates, timeout=None):
        """Return the first visible element matching any predicate in the list."""
        deadline = time.time() + (timeout or self.element_timeout)
        while time.time() < deadline:
            for pred in predicates:
                try:
                    el = self.driver.find_element(AppiumBy.IOS_PREDICATE, pred)
                    if el.is_displayed():
                        return el
                except (NoSuchElementException, StaleElementReferenceException):
                    pass
            time.sleep(0.4)
        return None

    def _tap_button(self, labels, timeout=10):
        """Tap the first visible button whose label or name matches any entry in labels."""
        predicates = [
            f'type == "XCUIElementTypeButton" AND visible == true '
            f'AND (label == "{l}" OR name == "{l}")'
            for l in labels
        ]
        el = self._find_any(predicates, timeout=timeout)
        if el:
            label_str = el.get_attribute("label") or el.get_attribute("name") or "?"
            self.logger.info(f"[{self.device_udid}]    Tapping button: '{label_str}'")
            el.click()
            return True
        return False

    def _enter_field(self, predicate, text, timeout=10):
        """Find a text or secure field and type text into it."""
        el = self._find(predicate, timeout=timeout)
        if not el:
            return False
        el.click()
        time.sleep(0.3)
        try:
            el.clear()
        except Exception:
            pass
        el.send_keys(text)
        return True

    def _hide_keyboard(self):
        try:
            self.driver.execute_script("mobile: hideKeyboard")
        except Exception:
            pass

    def _launch_via_deep_link(self):
        """
        Open the Zoom app directly into the join flow via zoomus:// deep link.
        Embeds meeting ID and URL-encoded pwd so Zoom skips the manual entry screen.
        """
        pwd_param = f"&pwd={self.url_pwd}" if self.url_pwd else ""
        deep_link = f"zoomus://zoom.us/join?confno={self.meeting_id}{pwd_param}"
        self.logger.info(
            f"[{self.device_udid}] Deep link: zoomus://zoom.us/join?confno={self.meeting_id}"
            + ("&pwd=***" if self.url_pwd else "")
        )

        for method, script, payload in [
            ("deepLink", "mobile: deepLink", {"url": deep_link, "bundleId": self.bundle_id}),
            ("openUrl",  "mobile: openUrl",  {"url": deep_link}),
        ]:
            try:
                self.driver.execute_script(script, payload)
                self.logger.info(f"[{self.device_udid}]    Launched via {method}")
                return True
            except Exception as e:
                self.logger.warning(f"[{self.device_udid}]    {method} failed: {e}")

        self.logger.error(f"[{self.device_udid}] Both deep link launch methods failed")
        return False

    def _handle_display_name(self):
        """Fill in display name if Zoom prompts for it."""
        name_pred = (
            'type == "XCUIElementTypeTextField" AND visible == true AND enabled == true '
            'AND (label CONTAINS[c] "name" OR name CONTAINS[c] "name" '
            'OR value CONTAINS[c] "name" OR placeholder CONTAINS[c] "name")'
        )
        el = self._find(name_pred, timeout=5)
        if not el:
            return
        self.logger.info(
            f"[{self.device_udid}] Display name prompt detected — entering: {self.display_name}"
        )
        el.click()
        time.sleep(0.2)
        try:
            el.clear()
        except Exception:
            pass
        el.send_keys(self.display_name)
        self._hide_keyboard()
        time.sleep(0.3)

    def _handle_join_button(self):
        """
        Tap the Join / Join Meeting button.
        After a deep link, Zoom typically shows a confirmation screen where you
        still need to tap Join to actually connect to the meeting.
        """
        tapped = self._tap_button(
            ["Join", "Join Meeting", "Tap to Join", "Join a Meeting"],
            timeout=8,
        )
        if tapped:
            self.logger.info(f"[{self.device_udid}]    Join button tapped")
        return tapped

    def _handle_password_prompt(self):
        """
        Enter the raw meeting password/passcode if Zoom's password screen appears.
        This happens when the password was not embedded in the deep link, or when
        the URL pwd parameter is invalid.
        """
        if not self.meeting_password:
            return True

        # Zoom password screen: usually a single SecureTextField
        for pred in [
            'type == "XCUIElementTypeSecureTextField" AND visible == true AND enabled == true',
            (
                'type == "XCUIElementTypeTextField" AND visible == true AND enabled == true '
                'AND (label CONTAINS[c] "pass" OR name CONTAINS[c] "pass" '
                'OR label CONTAINS[c] "passcode" OR name CONTAINS[c] "passcode")'
            ),
        ]:
            el = self._find(pred, timeout=6)
            if el:
                self.logger.info(f"[{self.device_udid}] Password prompt detected — entering passcode")
                el.click()
                time.sleep(0.2)
                try:
                    el.clear()
                except Exception:
                    pass
                el.send_keys(self.meeting_password)
                self._hide_keyboard()
                time.sleep(0.3)
                self._tap_button(["OK", "Join", "Continue", "Submit"], timeout=5)
                time.sleep(1)
                return True

        return True  # no prompt found — not an error

    def _handle_wrong_password_alert(self):
        """Dismiss 'incorrect password' alert and re-enter if possible."""
        alert_pred = (
            'type == "XCUIElementTypeStaticText" AND visible == true '
            'AND (label CONTAINS[c] "incorrect" OR label CONTAINS[c] "wrong" '
            'OR label CONTAINS[c] "invalid")'
        )
        el = self._find(alert_pred, timeout=3)
        if el:
            self.logger.warning(f"[{self.device_udid}] Wrong password alert detected")
            self._tap_button(["OK", "Try Again", "Close"], timeout=5)
            return True
        return False

    def _handle_audio_join(self):
        """
        Dismiss the 'Join Audio' / 'Call via Internet' dialog that Zoom shows
        every time you enter a meeting.
        """
        self.logger.info(f"[{self.device_udid}] Waiting for audio join dialog...")
        predicates = [
            f'type == "XCUIElementTypeButton" AND visible == true '
            f'AND (label == "{l}" OR name == "{l}")'
            for l in self.AUDIO_JOIN_LABELS
        ]
        el = self._find_any(predicates, timeout=20)
        if el:
            label_str = el.get_attribute("label") or el.get_attribute("name")
            self.logger.info(f"[{self.device_udid}]    Tapping audio button: '{label_str}'")
            el.click()
            return True
        self.logger.warning(
            f"[{self.device_udid}]    Audio dialog not found — Zoom may have auto-joined audio"
        )
        return False

    def _handle_permissions(self, max_rounds=3):
        """Tap Allow/OK on any iOS system permission sheets (microphone, camera, etc.)."""
        for _ in range(max_rounds):
            if self._tap_button(self.PERMISSION_ALLOW_LABELS, timeout=4):
                self.logger.info(f"[{self.device_udid}]    Dismissed system permission dialog")
                time.sleep(0.5)
            else:
                break

    def _handle_misc_dialogs(self):
        """Dismiss any remaining one-off dialogs: 'Got it', 'Continue', 'OK'."""
        self._tap_button(["Got it", "Continue", "OK", "Dismiss"], timeout=3)

    def _is_on_home_or_join_screen(self):
        """Detect if we landed on Zoom home/login screen instead of the join flow."""
        indicators = [
            'type == "XCUIElementTypeButton" AND visible == true '
            'AND (label == "Join a Meeting" OR name == "Join a Meeting")',
            'type == "XCUIElementTypeTextField" AND visible == true '
            'AND (label CONTAINS[c] "meeting id" OR name CONTAINS[c] "meeting id" '
            'OR placeholder CONTAINS[c] "meeting")',
        ]
        for pred in indicators:
            try:
                els = self.driver.find_elements(AppiumBy.IOS_PREDICATE, pred)
                if els:
                    return True
            except Exception:
                pass
        return False

    def _join_via_ui(self):
        """
        Full UI navigation fallback: tap 'Join a Meeting' → enter ID → tap Join.
        Used when the deep link opens the app but lands on the home screen.
        """
        self.logger.info(
            f"[{self.device_udid}] UI navigation fallback: Join a Meeting -> enter ID -> Join"
        )

        if not self._tap_button(["Join a Meeting", "Join Meeting"], timeout=10):
            self.logger.error(
                f"[{self.device_udid}]    'Join a Meeting' button not found on home screen"
            )
            return False
        time.sleep(1)

        # Meeting ID field (Zoom labels it "Meeting ID or Personal Link Name")
        id_pred = (
            'type == "XCUIElementTypeTextField" AND visible == true AND enabled == true '
            'AND (label CONTAINS[c] "meeting" OR name CONTAINS[c] "meeting" '
            'OR label CONTAINS[c] "id" OR name CONTAINS[c] "id")'
        )
        # Broadest fallback: first available text field
        any_field_pred = (
            'type == "XCUIElementTypeTextField" AND visible == true AND enabled == true'
        )

        if not self._enter_field(id_pred, self.meeting_id, timeout=10):
            self.logger.info(
                f"[{self.device_udid}]    Trying first visible text field for meeting ID..."
            )
            if not self._enter_field(any_field_pred, self.meeting_id, timeout=5):
                self.logger.error(f"[{self.device_udid}]    Could not find meeting ID text field")
                return False

        self.logger.info(f"[{self.device_udid}]    Entered meeting ID: {self.meeting_id}")
        self._hide_keyboard()
        time.sleep(0.4)

        if not self._tap_button(["Join", "Join Meeting"], timeout=10):
            self.logger.error(
                f"[{self.device_udid}]    Join button not found after entering meeting ID"
            )
            return False

        return True

    def _is_in_meeting(self):
        """
        Return True if in-meeting controls are visible (Mute/Unmute/Leave).
        These elements are always present once you are inside a Zoom meeting.
        """
        predicates = [
            'type == "XCUIElementTypeButton" AND visible == true '
            'AND (label == "Mute" OR label == "Unmute" OR name == "Mute" OR name == "Unmute")',
            'type == "XCUIElementTypeButton" AND visible == true '
            'AND (label == "Leave" OR name == "Leave" OR label == "End" OR name == "End")',
        ]
        for pred in predicates:
            try:
                els = self.driver.find_elements(AppiumBy.IOS_PREDICATE, pred)
                if els and els[0].is_displayed():
                    return True
            except Exception:
                pass
        return False

    def _ensure_controls_visible(self):
        """Best-effort: tap center a few times so Zoom bottom controls appear."""
        for _ in range(3):
            self._tap_meeting_center()
            time.sleep(0.8)
            more_pred = (
                'type == "XCUIElementTypeButton" AND visible == true '
                'AND (label == "More" OR name == "More")'
            )
            if self._find(more_pred, timeout=1):
                return

    def _tap_meeting_center(self):
        """Tap the middle of the screen to reveal hidden in-meeting controls."""
        if not self.driver:
            return False
        try:
            size = self.driver.get_window_size()
            x = int(size["width"] * 0.5)
            y = int(size["height"] * 0.5)
        except Exception as e:
            self.logger.warning(
                f"[{self.device_udid}]    Could not get window size for center tap: {e}"
            )
            return False

        if self._tap_at(x, y):
            self.logger.info(
                f"[{self.device_udid}]    Center tap via W3C actions at ({x}, {y})"
            )
            return True
        return False

    def _tap_at(self, x, y):
        """Tap absolute screen coordinates using W3C actions."""
        try:
            actions = ActionChains(self.driver)
            actions.w3c_actions.pointer_action.move_to_location(x, y)
            actions.w3c_actions.pointer_action.click()
            actions.perform()
            return True
        except Exception as e:
            self.logger.warning(
                f"[{self.device_udid}]    Coordinate tap failed at ({x}, {y}): {e}"
            )
            return False

    def _start_screen_share(self):
        """
        Start Zoom screen share:
          1) Tap meeting surface to show toolbar (if hidden)
          2) Tap 'More'
          3) Tap 'Start share'
          4) Tap final 'Share screen' confirmation
        """
        self.logger.info(f"[{self.device_udid}] Starting screen share flow")

        more_pred = (
            'type == "XCUIElementTypeButton" AND visible == true '
            'AND (label == "More" OR name == "More")'
        )
        start_share_predicates = [
            'type == "XCUIElementTypeButton" AND visible == true '
            'AND (label == "Start share" OR name == "Start share" '
            'OR label == "Start Share" OR name == "Start Share")',
            'type == "XCUIElementTypeStaticText" AND visible == true '
            'AND (label == "Start share" OR name == "Start share" '
            'OR label == "Start Share" OR name == "Start Share")',
        ]

        # Retry because toolbar auto-hides in meeting.
        for attempt in range(1, 5):
            self.logger.info(
                f"[{self.device_udid}]    Attempt {attempt}: revealing in-meeting toolbar"
            )
            self._tap_meeting_center()
            time.sleep(0.9)

            more_btn = self._find(more_pred, timeout=2)
            if not more_btn:
                self.logger.info(
                    f"[{self.device_udid}]    Attempt {attempt}: 'More' button not visible yet"
                )
                continue

            self.logger.info(f"[{self.device_udid}]    Tapping 'More'")
            more_btn.click()
            time.sleep(1.0)

            target = self._find_any(start_share_predicates, timeout=4)
            if target:
                self.logger.info(f"[{self.device_udid}]    Tapping 'Start share'")
                target.click()
                time.sleep(1.0)

                # Final confirmation sheet/button.
                share_screen_preds = [
                    'type == "XCUIElementTypeButton" AND visible == true '
                    'AND (label == "Share screen" OR name == "Share screen" '
                    'OR label == "Share Screen" OR name == "Share Screen")',
                    'type == "XCUIElementTypeStaticText" AND visible == true '
                    'AND (label == "Share screen" OR name == "Share screen" '
                    'OR label == "Share Screen" OR name == "Share Screen")',
                ]
                confirm = self._find_any(share_screen_preds, timeout=6)
                if confirm:
                    self.logger.info(f"[{self.device_udid}]    Tapping final 'Share screen'")
                    confirm.click()
                    time.sleep(1.0)

                    # ReplayKit overlay often requires one more tap: "Start Broadcast".
                    if self._handle_start_broadcast():
                        self.logger.info(f"[{self.device_udid}] Screen share flow completed")
                        return True
                    self.logger.warning(
                        f"[{self.device_udid}]    Could not confirm 'Start Broadcast' tap"
                    )
                    return False

                self.logger.warning(
                    f"[{self.device_udid}]    'Share screen' confirmation not found after 'Start share'"
                )
                continue

            # If menu closed or changed, retry from toolbar reveal.
            self.logger.info(
                f"[{self.device_udid}]    Attempt {attempt}: 'Start share' not found after tapping More"
            )
            time.sleep(0.8)

        self.logger.warning(
            f"[{self.device_udid}] Could not complete screen share flow (More -> Start share)"
        )
        return False

    def _handle_start_broadcast(self):
        """
        Handle ReplayKit "Start Broadcast" confirmation.
        Calculates coordinates dynamically based on current window size
        to ensure compatibility across different iOS device models.
        """
        self.logger.info(f"[{self.device_udid}] Handling ReplayKit 'Start Broadcast' overlay...")

        try:
            size = self.driver.get_window_size()
            width, height = size["width"], size["height"]

            # The 'Start Broadcast' button center is typically:
            # Width: Exactly middle (50%)
            # Height: Approximately 58-60% from the top (based on x=195, y=496 on 390x844 screen)

            points = [
                (int(width * 0.5), int(height * 0.585)),  # Primary target (calculated from scan)
                (int(width * 0.5), int(height * 0.600)),  # Slight variation fallback
            ]

            for i, (px, py) in enumerate(points):
                self.logger.info(
                    f"[{self.device_udid}]    Dynamic tap attempt {i + 1} at ({px}, {py})"
                    f" [Size: {width}x{height}]"
                )
                if self._tap_at(px, py):
                    time.sleep(2.0)
                    # If meeting controls appear, we succeeded
                    if self._is_in_meeting():
                        self.logger.info(f"[{self.device_udid}]    Broadcast started successfully")
                        return True
        except Exception as e:
            self.logger.warning(
                f"[{self.device_udid}]    Dynamic coordinate calculation failed: {e}"
            )

        # Fallback to broad system-level search (requires includeUnifiedUISchedule)
        start_broadcast_preds = [
            'label == "Start Broadcast" OR name == "Start Broadcast"',
            'type == "XCUIElementTypeButton" AND (label CONTAINS "Start" OR name CONTAINS "Start")',
        ]
        target = self._find_any(start_broadcast_preds, timeout=5)
        if target:
            self.logger.info(
                f"[{self.device_udid}]    Tapping 'Start Broadcast' via broad predicate"
            )
            try:
                target.click()
                time.sleep(1.5)
                return True
            except Exception:
                pass

        return False

    def _enable_audio(self):
        """Unmute or join audio so the participant's microphone is active."""
        self.logger.info(f"[{self.device_udid}] Enabling audio...")
        try:
            self._ensure_controls_visible()

            # Already unmuted — audio is active, nothing to do
            mute_pred = (
                'type == "XCUIElementTypeButton" AND visible == true '
                'AND (label == "Mute" OR name == "Mute")'
            )
            if self._find(mute_pred, timeout=3):
                self.logger.info(f"[{self.device_udid}] Audio already enabled (microphone active).")
                return True

            # Muted — tap Unmute to enable
            if self._tap_button(["Unmute"], timeout=5):
                self.logger.info(f"[{self.device_udid}] Audio enabled successfully.")
                return True

            # Audio not joined at all — tap one of the join-audio dialog buttons
            if self._tap_button(self.AUDIO_JOIN_LABELS, timeout=5):
                self.logger.info(f"[{self.device_udid}] Audio enabled successfully (joined audio).")
                return True

            self.logger.warning(f"[{self.device_udid}] Could not enable audio — button not found.")
            return False
        except Exception as e:
            self.logger.error(f"[{self.device_udid}] Error while enabling audio: {e}")
            return False

    def _enable_video(self):
        """Start the camera so the participant's video is active."""
        self.logger.info(f"[{self.device_udid}] Enabling video...")
        try:
            self._ensure_controls_visible()

            # Already on — video is active, nothing to do
            stop_pred = (
                'type == "XCUIElementTypeButton" AND visible == true '
                'AND (label == "Stop Video" OR name == "Stop Video")'
            )
            if self._find(stop_pred, timeout=3):
                self.logger.info(f"[{self.device_udid}] Video already enabled (camera active).")
                return True

            # Video off — tap Start Video to enable
            if self._tap_button(["Start Video"], timeout=5):
                self.logger.info(f"[{self.device_udid}] Video enabled successfully.")
                return True

            self.logger.warning(f"[{self.device_udid}] Could not enable video — button not found.")
            return False
        except Exception as e:
            self.logger.error(f"[{self.device_udid}] Error while enabling video: {e}")
            return False

    def _wait_for_duration(self):
        """Hold in the meeting for self.duration_minutes, logging remaining time every minute."""
        total_seconds = self.duration_minutes * 60
        end_time = time.time() + total_seconds

        self.logger.info(
            f"[{self.device_udid}] Duration timer started — staying in meeting for"
            f" {self.duration_minutes} minute(s)."
        )

        while True:
            remaining = end_time - time.time()
            if remaining <= 0:
                break
            self.logger.info(
                f"[{self.device_udid}]    Time remaining: {int(remaining // 60)}m {int(remaining % 60)}s"
            )
            time.sleep(min(60, remaining))

        self.logger.info(f"[{self.device_udid}] Duration completed — leaving meeting.")

    def run(self):
        with _automations_lock:
            _active_automations.append(self)
        try:
            self._connect()

            # 1. Launch Zoom via deep link
            self.logger.info(f"[{self.device_udid}] Launching Zoom via deep link...")
            if not self._launch_via_deep_link():
                return False

            self.logger.info(
                f"[{self.device_udid}] Waiting {self.launch_timeout}s for Zoom to initialize..."
            )
            time.sleep(self.launch_timeout)

            # 2. Handle display name prompt
            self.logger.info(f"[{self.device_udid}] Handling display name prompt...")
            self._handle_display_name()

            # 3. Handle password prompt
            self.logger.info(f"[{self.device_udid}] Handling password prompt...")
            self._handle_password_prompt()
            self._handle_wrong_password_alert()
            time.sleep(0.5)

            # 4. Tap Join confirmation button
            self.logger.info(f"[{self.device_udid}] Tapping Join confirmation button...")
            self._handle_join_button()
            time.sleep(1.5)

            # 5. UI fallback if deep link landed on home screen
            self.logger.info(f"[{self.device_udid}] Checking for UI fallback...")
            if self._is_on_home_or_join_screen():
                self.logger.info(
                    f"[{self.device_udid}] Deep link did not trigger join flow — switching to UI navigation"
                )
                if not self._join_via_ui():
                    self.logger.error(f"[{self.device_udid}] UI navigation fallback failed")
                    return False
                time.sleep(2)
                self._handle_display_name()
                self._handle_password_prompt()
                time.sleep(1)
            else:
                self.logger.info(
                    f"[{self.device_udid}] Deep link join flow is active — no UI fallback needed"
                )

            # 6. OS permissions (mic may appear before audio dialog)
            self.logger.info(f"[{self.device_udid}] Handling OS permission dialogs (round 1)...")
            self._handle_permissions()

            # 7. Audio join dialog
            self.logger.info(f"[{self.device_udid}] Handling audio join dialog...")
            self._handle_audio_join()
            time.sleep(1)

            # 8. OS permissions again (camera appears after audio)
            self.logger.info(f"[{self.device_udid}] Handling OS permission dialogs (round 2)...")
            self._handle_permissions()

            # 9. Any remaining misc dialogs
            self.logger.info(f"[{self.device_udid}] Handling misc dialogs...")
            self._handle_misc_dialogs()
            time.sleep(1.5)

            # 10. Verify in meeting
            self.logger.info(f"[{self.device_udid}] Verifying in-meeting state...")
            self._ensure_controls_visible()
            if self._is_in_meeting():
                self.logger.info(f"[{self.device_udid}] In meeting! (Mute/Leave controls visible)")
            else:
                # Give Zoom a few extra seconds to connect
                self.logger.info(
                    f"[{self.device_udid}] Meeting controls not yet visible — waiting 5s more..."
                )
                time.sleep(5)
                self._ensure_controls_visible()
                if self._is_in_meeting():
                    self.logger.info(f"[{self.device_udid}] In meeting!")
                else:
                    self.logger.warning(
                        f"[{self.device_udid}] Could not confirm in-meeting state after all steps.\n"
                        "   The meeting may still be loading, or the UI changed.\n"
                        "   Proceeding to screen-share attempt anyway."
                    )

            # 10a. Enable audio if requested
            if self.enable_audio:
                self._enable_audio()

            # 10b. Enable video if requested
            if self.enable_video:
                self._enable_video()

            # 11. Start screen share
            if self.enable_screen_share:
                self.logger.info(f"[{self.device_udid}] Starting screen share...")
                if self._start_screen_share():
                    self.logger.info(
                        f"[{self.device_udid}] SUCCESS — Joined meeting and started screen share"
                    )
                else:
                    self.logger.warning(
                        f"[{self.device_udid}] Screen share failed — meeting join was still successful"
                    )

            # 12. Hold meeting for configured duration
            if self.duration_minutes is not None:
                self._wait_for_duration()
                self.logger.info(f"[{self.device_udid}] Leaving meeting after duration...")

            return True

        except WebDriverException as e:
            self.logger.error(f"[{self.device_udid}] Appium WebDriver error: {e}")
            return False
        except KeyboardInterrupt:
            self.logger.info(f"[{self.device_udid}] Interrupted — session will be cleaned up")
            raise
        except Exception as e:
            self.logger.error(f"[{self.device_udid}] Unexpected error: {e}", exc_info=True)
            return False
        finally:
            self._cleanup()
            with _automations_lock:
                try:
                    _active_automations.remove(self)
                except ValueError:
                    pass


def parse_udids(values):
    udids = []
    for item in values:
        for part in str(item).split(","):
            part = part.strip()
            if part:
                udids.append(part)
    return udids


def run_for_device(udid, args):
    automation = ZoomAutomator(
        device_udid=udid,
        invite_link=args.link,
        meeting_password=args.password,
        display_name=args.name,
        bundle_id=args.bundle_id,
        hub_url=args.hub,
        client_secret=args.secret,
        element_timeout=args.timeout,
        launch_timeout=args.launch_timeout,
        enable_screen_share=args.share,
        duration_minutes=args.duration,
        enable_audio=args.audio,
        enable_video=args.video,
    )
    return automation.run()


def main():
    signal.signal(signal.SIGINT, _cleanup_all)
    signal.signal(signal.SIGTERM, _cleanup_all)
    atexit.register(_cleanup_all)

    parser = argparse.ArgumentParser(
        description="Join a Zoom meeting on iOS via GADS/Appium",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Password embedded in invite URL (most common case)
  %(prog)s --udid 00008110-001155242680A01E \\
           --link "https://zoom.us/j/99271832693?pwd=abc123XYZ"

  # Meeting ID in URL, passcode provided separately
  %(prog)s --udid 00008110-001155242680A01E \\
           --link "https://zoom.us/j/99271832693" --password 123456

  # Subdomain invite link (us02web.zoom.us, company.zoom.us, etc.)
  %(prog)s --udid ABC123 \\
           --link "https://us02web.zoom.us/j/88012345678?pwd=XYZ" --name "Test Device"

  # GADS hub on a different host
  GADS_HUB_URL=http://myserver:10000/grid %(prog)s --udid ABC123 --link "..."
        """,
    )
    parser.add_argument(
        "--udid", "-u", required=True, nargs="+",
        help="iOS device UDID(s), comma or space separated",
    )
    parser.add_argument(
        "--link", "-l", required=True,
        help="Zoom invite link (https://zoom.us/j/...)",
    )
    parser.add_argument(
        "--password", "-p", default=None,
        help="Raw meeting passcode (overrides / supplements URL pwd)",
    )
    parser.add_argument(
        "--name", "-n", default="Test User",
        help="Display name shown inside the meeting (default: 'Test User')",
    )
    parser.add_argument(
        "--bundle-id", "-b", default=ZOOM_BUNDLE_ID,
        help=f"Zoom app bundle ID (default: {ZOOM_BUNDLE_ID})",
    )
    parser.add_argument(
        "--hub", default=None,
        help="GADS hub URL (default: GADS_HUB_URL env or http://localhost:10000/grid)",
    )
    parser.add_argument(
        "--secret", "-s", default=None,
        help="GADS client secret (default: GADS_CLIENT_SECRET env)",
    )
    parser.add_argument(
        "--timeout", "-t", type=int, default=20,
        help="Per-element wait timeout in seconds (default: 20)",
    )
    parser.add_argument(
        "--launch-timeout", type=int, default=15,
        help="Seconds to wait after launching Zoom (default: 15)",
    )
    parser.add_argument(
        "--share", action="store_true", default=False,
        help="Start screen share after joining the meeting",
    )
    parser.add_argument(
        "--duration", "-d", type=int, default=None,
        help="How long to stay in the meeting after joining, in minutes (default: exit immediately)",
    )
    parser.add_argument(
        "--audio", action="store_true", default=False,
        help="Unmute / join computer audio after successfully joining the meeting",
    )
    parser.add_argument(
        "--video", action="store_true", default=False,
        help="Start camera (enable video) after successfully joining the meeting",
    )

    args = parser.parse_args()
    udids = parse_udids(args.udid)
    if not udids:
        print("No valid UDID provided")
        sys.exit(1)

    if len(udids) == 1:
        success = run_for_device(udids[0], args)
        sys.exit(0 if success else 1)

    results = []
    try:
        with ThreadPoolExecutor(max_workers=len(udids)) as ex:
            futures = {ex.submit(run_for_device, u, args): u for u in udids}
            for f in as_completed(futures):
                udid = futures[f]
                try:
                    ok = f.result()
                    print(f"[{udid}] {'SUCCESS' if ok else 'FAILED'}")
                    results.append(ok)
                except Exception as e:
                    print(f"[{udid}] FAILED: {e}")
                    results.append(False)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt — waiting for all sessions to terminate...")
        sys.exit(1)

    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
