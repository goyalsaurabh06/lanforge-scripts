#!/usr/bin/env python3
"""NETGEAR Orbi gateway configuration and firmware update utility using Selenium and Firefox."""

from __future__ import annotations

import argparse
import configparser
import getpass
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

try:
    from selenium import webdriver
    from selenium.common.exceptions import NoAlertPresentException, WebDriverException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.firefox.options import Options
    from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
    from selenium.webdriver.support.ui import Select
except ImportError as exc:
    raise SystemExit(
        "Selenium is required. Install it with: python3 -m pip install selenium"
    ) from exc


# Supported wireless security normalization mapping
SECURITY_MAPPING: dict[str, str] = {
    "wpa2": "WPA2-PSK",
    "wpa3": "WPA3-Personal",
    "wpa2+wpa3": "WPA2-PSK + WPA3-Personal",
    "wpa2mixed": "WPA2-PSK + WPA3-Personal",
    "wpa3mixed": "WPA2-PSK + WPA3-Personal",
}


def normalize_security(security_input: str | None) -> str | None:
    """Normalize user security input to Orbi UI security label."""
    if not security_input:
        return None
    return SECURITY_MAPPING.get(security_input.strip().lower())


def positive_int(value: str) -> int:
    """Validate that CLI channel arguments are positive integers."""
    try:
        val = int(value)
        if val <= 0:
            raise ValueError
        return val
    except ValueError:
        raise argparse.ArgumentTypeError(f"Channel must be a positive integer, got: {value!r}")


def gateway_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise argparse.ArgumentTypeError("Gateway address cannot be empty.")
    if "://" not in value:
        value = f"http://{value}"
    if not urlsplit(value).hostname:
        raise argparse.ArgumentTypeError("Enter a gateway IP or URL, e.g. 192.168.1.1")
    return value.rstrip("/")


def default_firefox_profile() -> Path | None:
    """Find the default desktop Firefox profile on common Linux installs."""
    roots = (
        Path.home() / ".mozilla" / "firefox",
        Path.home() / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
    )
    for root in roots:
        ini = root / "profiles.ini"
        if not ini.is_file():
            continue
        config = configparser.ConfigParser()
        config.read(ini, encoding="utf-8")

        # Newer Firefox releases can record the selected profile in an Install section.
        for section in config.sections():
            if section.startswith("Install"):
                relative_path = config.get(section, "Default", fallback="")
                if relative_path:
                    candidate = root / relative_path
                    if candidate.is_dir():
                        return candidate

        profile_sections = [s for s in config.sections() if s.startswith("Profile")]
        profile_sections.sort(key=lambda s: not config.getboolean(s, "Default", fallback=False))
        for section in profile_sections:
            profile_path = config.get(section, "Path", fallback="")
            if not profile_path:
                continue
            is_relative = config.getboolean(section, "IsRelative", fallback=True)
            candidate = (root / profile_path) if is_relative else Path(profile_path)
            if candidate.is_dir():
                return candidate
    return None


def contexts(driver):
    """Yield the main document and each top-level frame for legacy Orbi pages."""
    driver.switch_to.default_content()
    yield None
    frames = driver.find_elements(By.CSS_SELECTOR, "iframe, frame")
    for frame in frames:
        driver.switch_to.default_content()
        try:
            driver.switch_to.frame(frame)
            yield frame
        except WebDriverException:
            continue
    driver.switch_to.default_content()


def first_visible(driver, selectors):
    for frame in contexts(driver):
        for by, selector in selectors:
            try:
                elements = driver.find_elements(by, selector)
                for element in elements:
                    if element.is_displayed():
                        return element, frame
            except WebDriverException:
                continue
    driver.switch_to.default_content()
    return None, None


def _clickable_ancestor(element):
    candidate = element
    for _ in range(5):
        try:
            tag = candidate.tag_name.lower()
            role = (candidate.get_attribute("role") or "").lower()
            onclick = candidate.get_attribute("onclick")
            if tag in {"a", "button", "input"} or role == "button" or onclick:
                return candidate
            candidate = candidate.find_element(By.XPATH, "..")
        except WebDriverException:
            break
    return element


def click_text(driver, pattern: str, timeout: int = 3) -> bool:
    regex = re.compile(pattern, re.IGNORECASE)
    for _frame in contexts(driver):
        try:
            # Direct text nodes avoid matching the whole page/container
            elements = driver.find_elements(By.XPATH, "//*[text()[normalize-space()]]")
            for element in elements:
                text = (element.text or "").strip()
                if text and regex.fullmatch(text) and element.is_displayed():
                    driver.execute_script("arguments[0].click();", _clickable_ancestor(element))
                    time.sleep(max(1, timeout / 2))
                    driver.switch_to.default_content()
                    return True
        except WebDriverException:
            continue
    driver.switch_to.default_content()
    return False


def find_file_input(driver):
    for frame in contexts(driver):
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
            if elements:
                return elements[0], frame
        except WebDriverException:
            continue
    driver.switch_to.default_content()
    return None, None


def choose_checkbox_for_target(driver, model_tokens) -> bool:
    """Select a matching Orbi router/satellite row if the update dialog requires it."""
    for _frame in contexts(driver):
        try:
            checkboxes = driver.find_elements(By.CSS_SELECTOR, 'input[type="checkbox"]')
            for checkbox in checkboxes:
                if not checkbox.is_displayed():
                    continue
                row_text = driver.execute_script(
                    "let n=arguments[0], out=[]; for(let i=0;n && i<5;i++,n=n.parentElement)"
                    "{out.push(n.innerText || '');} return out.join(' ');",
                    checkbox,
                )
                normalized = re.sub(r"[^a-z0-9]", "", str(row_text).lower())
                if any(token and token in normalized for token in model_tokens):
                    if not checkbox.is_selected():
                        driver.execute_script("arguments[0].click();", checkbox)
                    driver.switch_to.default_content()
                    return True
        except WebDriverException:
            continue
    driver.switch_to.default_content()
    return False


def screen_text(driver) -> str:
    """Collect visible page text from the main document and its frames."""
    chunks = []
    for _frame in contexts(driver):
        try:
            body = driver.find_element(By.TAG_NAME, "body")
            text = body.text.strip()
            if text:
                chunks.append(text)
        except WebDriverException:
            continue
    driver.switch_to.default_content()
    return "\n\n".join(chunks)


def click_upload(driver) -> bool:
    selectors = (
        (By.XPATH, "//button[normalize-space()='Upload']"),
        (By.XPATH, "//input[(@type='submit' or @type='button') and normalize-space(@value)='Upload']"),
        (By.XPATH, "//a[normalize-space()='Upload']"),
    )
    button, _ = first_visible(driver, selectors)
    if not button:
        return False
    try:
        button.click()
    except WebDriverException:
        # A native JavaScript confirmation can interrupt the WebDriver click.
        try:
            driver.switch_to.alert
        except NoAlertPresentException:
            raise
    return True


def click_apply(driver) -> bool:
    """Locate and click the Apply button to save changes."""
    selectors = (
        (By.XPATH, "//button[normalize-space()='Apply']"),
        (By.XPATH, "//input[(@type='submit' or @type='button') and normalize-space(@value)='Apply']"),
        (By.XPATH, "//input[(@type='submit' or @type='button') and translate(normalize-space(@value), 'APPLY', 'apply')='apply']"),
        (By.XPATH, "//button[translate(normalize-space(), 'APPLY', 'apply')='apply']"),
        (By.XPATH, "//a[normalize-space()='Apply']"),
        (By.CSS_SELECTOR, 'input[name="Apply"], button[name="Apply"], input[id="apply"], button[id="apply"]'),
    )
    button, _frame = first_visible(driver, selectors)
    if not button:
        return False

    try:
        button.click()
    except WebDriverException:
        try:
            driver.execute_script("arguments[0].click();", button)
        except WebDriverException:
            return False

    # Handle any confirmation alert that appears after clicking Apply
    try:
        alert = driver.switch_to.alert
        alert.accept()
        driver.switch_to.default_content()
    except (NoAlertPresentException, WebDriverException):
        pass

    driver.switch_to.default_content()
    return True


def capture_and_accept_warning(driver) -> str:
    """Read and accept the upload confirmation, when one is shown."""
    try:
        alert = driver.switch_to.alert
        message = (alert.text or "").strip()
        alert.accept()
        driver.switch_to.default_content()
        return message
    except NoAlertPresentException:
        pass

    for _frame in contexts(driver):
        try:
            dialogs = driver.find_elements(By.CSS_SELECTOR, '[role="dialog"], .modal, .ui-dialog')
            for dialog in dialogs:
                if not dialog.is_displayed():
                    continue
                message = (dialog.text or "").strip()
                ok_button = None
                for selector in (
                    ".//button[normalize-space()='OK']",
                    ".//input[(@type='button' or @type='submit') and normalize-space(@value)='OK']",
                ):
                    buttons = dialog.find_elements(By.XPATH, selector)
                    ok_button = next((item for item in buttons if item.is_displayed()), None)
                    if ok_button:
                        break
                if ok_button:
                    ok_button.click()
                    driver.switch_to.default_content()
                    return message
        except WebDriverException:
            continue
    driver.switch_to.default_content()
    return ""


def update_report_lines(text: str) -> list[str]:
    keywords = re.compile(
        r"firmware|update|warning|error|success|failed|upload|restart|reboot|please wait|progress",
        re.IGNORECASE,
    )
    lines = []
    for line in text.splitlines():
        line = " ".join(line.split())
        if line and keywords.search(line) and line not in lines:
            lines.append(line)
    return lines


# ==============================================================================
# Argument Validation Helpers
# ==============================================================================

def validate_wireless_args(args: argparse.Namespace, parser: argparse.ArgumentParser | None = None) -> None:
    """Validate arguments required for wireless_config before launching browser."""
    errors: list[str] = []

    if not args.ssid or not args.ssid.strip():
        errors.append("--ssid is required and cannot be empty for wireless_config.")
    if not args.password or not args.password.strip():
        errors.append("--password is required and cannot be empty for wireless_config.")
    if not args.security or not args.security.strip():
        errors.append("--security is required and cannot be empty for wireless_config.")
    else:
        norm = normalize_security(args.security)
        if norm is None:
            supported = ", ".join(f"{k!r}" for k in sorted(SECURITY_MAPPING.keys()))
            errors.append(
                f"Unsupported --security value: {args.security!r}. "
                f"Supported options are: {supported}."
            )

    ch_2g = getattr(args, "2g_channel", 1)
    if ch_2g is None or ch_2g <= 0:
        errors.append("--2g_channel must be a positive integer.")

    ch_5g = getattr(args, "5g_channel", 36)
    if ch_5g is None or ch_5g <= 0:
        errors.append("--5g_channel must be a positive integer.")

    if errors:
        msg = "\n".join(errors)
        if parser:
            parser.error(msg)
        else:
            raise ValueError(msg)


def validate_firmware_args(args: argparse.Namespace, parser: argparse.ArgumentParser | None = None) -> None:
    """Validate arguments required for firmware_update before launching browser."""
    if not args.firmware:
        msg = "--firmware is required for action 'firmware_update'."
        if parser:
            parser.error(msg)
        else:
            raise ValueError(msg)

    firmware_path = args.firmware.expanduser().resolve()
    if not firmware_path.is_file():
        msg = f"Firmware file does not exist: {firmware_path}"
        if parser:
            parser.error(msg)
        else:
            raise FileNotFoundError(msg)


# ==============================================================================
# Wireless Configuration Workflow
# ==============================================================================

def navigate_to_wireless_page(driver) -> None:
    """Navigate to BASIC section and click Wireless from the left menu."""
    print("Navigating to BASIC -> Wireless")

    # 1. Navigate to BASIC section
    click_text(driver, r"^Basic$", timeout=2)
    time.sleep(1)

    # 2. Click Wireless from the menu
    if not click_text(driver, r"^Wireless(?:\s*Settings)?$", timeout=3):
        wireless_selectors = (
            (By.XPATH, "//a[translate(normalize-space(), 'WIRELESS', 'wireless')='wireless']"),
            (By.XPATH, "//span[translate(normalize-space(), 'WIRELESS', 'wireless')='wireless']"),
            (By.XPATH, "//a[contains(@href, 'WLG_wireless') or contains(@href, 'wireless')]"),
            (By.CSS_SELECTOR, '#wireless, [id*="wireless"]'),
        )
        element, _ = first_visible(driver, wireless_selectors)
        if element:
            try:
                element.click()
            except WebDriverException:
                driver.execute_script("arguments[0].click();", _clickable_ancestor(element))
        else:
            raise RuntimeError("Could not find or click 'Wireless' in the navigation menu.")

    time.sleep(2)
    driver.switch_to.default_content()


def configure_ssid(driver, ssid: str) -> None:
    """Locate the Name (SSID) input field and enter the provided SSID."""
    ssid_selectors = (
        (By.CSS_SELECTOR, 'input[name="ssid"]'),
        (By.CSS_SELECTOR, 'input[id="ssid"]'),
        (By.CSS_SELECTOR, 'input[name="wl_ssid"]'),
        (By.CSS_SELECTOR, 'input[id="wl_ssid"]'),
        (By.CSS_SELECTOR, 'input[name="ssid_2g"]'),
        (By.CSS_SELECTOR, 'input[name="wlg_ssid"]'),
        (By.XPATH, "//tr[contains(., 'SSID') or contains(., 'Name')]//input[@type='text']"),
        (By.XPATH, "//input[@type='text' and (contains(@name, 'ssid') or contains(@id, 'ssid'))]"),
    )

    deadline = time.monotonic() + 15
    ssid_field = None
    ssid_frame = None
    while time.monotonic() < deadline:
        ssid_field, ssid_frame = first_visible(driver, ssid_selectors)
        if ssid_field:
            break
        time.sleep(0.5)

    if not ssid_field:
        raise RuntimeError("Could not find the Name (SSID) input field on the Wireless page.")

    if ssid_frame is not None:
        driver.switch_to.default_content()
        driver.switch_to.frame(ssid_frame)

    ssid_field.clear()
    ssid_field.send_keys(ssid)

    current_val = ssid_field.get_attribute("value")
    if current_val != ssid:
        driver.execute_script(
            "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change'));",
            ssid_field,
            ssid,
        )
        current_val = ssid_field.get_attribute("value")
        if current_val != ssid:
            driver.switch_to.default_content()
            raise RuntimeError(f"Failed to set SSID to {ssid!r}; value is {current_val!r}.")

    driver.switch_to.default_content()


CHANNELS_5G = {
    36, 40, 44, 48, 52, 56, 60, 64,
    100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144,
    149, 153, 157, 161, 165,
}

CHANNELS_2G = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14}


def is_channel_select(select_elem, band: str) -> bool:
    """Determine if a select element is a valid Wi-Fi channel dropdown for the requested band."""
    try:
        name_id = (
            str(select_elem.get_attribute("name") or "")
            + " "
            + str(select_elem.get_attribute("id") or "")
        ).lower()

        # Reject language, region, or NTP time dropdowns
        if any(token in name_id for token in ("lang", "language", "region", "country", "timezone")):
            return False

        opts = (
            select_elem.options
            if hasattr(select_elem, "options")
            else select_elem.find_elements(By.TAG_NAME, "option")
        )
        if not opts:
            return False

        opt_texts = [(opt.text or "").strip() for opt in opts]
        opt_values = [(opt.get_attribute("value") or "").strip() for opt in opts]
        all_strings = " ".join(opt_texts + opt_values).lower()

        # Reject language selector by option content
        if any(
            lang in all_strings
            for lang in (
                "english",
                "deutsch",
                "german",
                "french",
                "spanish",
                "simplifiedchinese",
                "traditionalchinese",
                "italian",
                "russian",
                "japanese",
                "korean",
            )
        ):
            return False

        extracted_numbers = set()
        for s in opt_texts + opt_values:
            for num_str in re.findall(r"\b\d+\b", s):
                try:
                    extracted_numbers.add(int(num_str))
                except ValueError:
                    pass

        if band == "5":
            # Must have known 5 GHz channels
            if extracted_numbers & CHANNELS_5G:
                return True
            if any(t in name_id for t in ("5g", "wla", "channel_5")) and extracted_numbers:
                return True
            return False
        else:
            # 2.4 GHz channel dropdown must not contain 5 GHz channels
            if extracted_numbers & CHANNELS_5G:
                return False
            if extracted_numbers & CHANNELS_2G:
                return True
            if ("channel" in name_id or "w_channel" in name_id) and extracted_numbers:
                return True
            return False
    except Exception:
        return False


def find_channel_select(driver, band: str, timeout: int = 10):
    """Locate the channel dropdown element and its containing frame for the given band."""
    if band == "2.4":
        selectors = (
            (By.CSS_SELECTOR, 'select[name="w_channel"]'),
            (By.CSS_SELECTOR, 'select[id="w_channel"]'),
            (By.CSS_SELECTOR, 'select[name="channel_2g"]'),
            (By.CSS_SELECTOR, 'select[id="channel_2g"]'),
            (By.CSS_SELECTOR, 'select[name="channel"]'),
            (By.CSS_SELECTOR, 'select[id="channel"]'),
            (By.XPATH, "//tr[contains(., '2.4') and (contains(., 'Channel') or contains(., 'channel'))]//select"),
            (By.XPATH, "//div[contains(., '2.4') and (contains(., 'Channel') or contains(., 'channel'))]//select"),
            (By.XPATH, "//td[contains(., '2.4')]/following::select[1]"),
        )
    else:
        selectors = (
            (By.CSS_SELECTOR, 'select[name="w_channel_5g"]'),
            (By.CSS_SELECTOR, 'select[id="w_channel_5g"]'),
            (By.CSS_SELECTOR, 'select[name="w_channel_5G"]'),
            (By.CSS_SELECTOR, 'select[id="w_channel_5G"]'),
            (By.CSS_SELECTOR, 'select[name="wla_channel"]'),
            (By.CSS_SELECTOR, 'select[id="wla_channel"]'),
            (By.CSS_SELECTOR, 'select[name="wla1_channel"]'),
            (By.CSS_SELECTOR, 'select[id="wla1_channel"]'),
            (By.CSS_SELECTOR, 'select[name="wla2_channel"]'),
            (By.CSS_SELECTOR, 'select[id="wla2_channel"]'),
            (By.CSS_SELECTOR, 'select[name="channel_5g"]'),
            (By.CSS_SELECTOR, 'select[id="channel_5g"]'),
            (By.CSS_SELECTOR, 'select[name="channel5g"]'),
            (By.CSS_SELECTOR, 'select[id="channel5g"]'),
            (By.CSS_SELECTOR, 'select[name="w_channel5g"]'),
            (By.CSS_SELECTOR, 'select[id="w_channel5g"]'),
            (By.XPATH, "//tr[contains(., '5') and (contains(., 'Channel') or contains(., 'channel'))]//select"),
            (By.XPATH, "//div[contains(., '5') and (contains(., 'Channel') or contains(., 'channel'))]//select"),
            (By.XPATH, "//td[contains(., '5')]/following::select[1]"),
        )

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        # Phase 1: Try specific selectors across all contexts, filtering by is_channel_select
        for frame in contexts(driver):
            for by, selector in selectors:
                try:
                    elements = driver.find_elements(by, selector)
                    for el in elements:
                        if el.is_displayed() and is_channel_select(el, band):
                            return el, frame
                except WebDriverException:
                    continue

        # Phase 2: Scan all visible select elements across all frames
        for frame in contexts(driver):
            try:
                candidates = driver.find_elements(By.TAG_NAME, "select")
                for c in candidates:
                    if c.is_displayed() and is_channel_select(c, band):
                        return c, frame
            except WebDriverException:
                continue

        time.sleep(0.5)

    driver.switch_to.default_content()
    return None, None


def select_dropdown_channel(driver, band: str, target_channel: int) -> None:
    """Locate and select the requested channel in the 2.4 GHz or 5 GHz dropdown."""
    target_str = str(target_channel)
    element, frame = find_channel_select(driver, band)

    if not element:
        driver.switch_to.default_content()
        raise RuntimeError(f"Could not find the {band} GHz Channel dropdown in the gateway UI.")

    if frame is not None:
        driver.switch_to.default_content()
        driver.switch_to.frame(frame)

    select_obj = Select(element)
    available_options: list[str] = []
    matched_opt = None

    for opt in select_obj.options:
        val = (opt.get_attribute("value") or "").strip()
        txt = (opt.text or "").strip()
        available_options.append(f"{txt} (value={val})" if val != txt else txt)

        # Exact match on value or text
        if val == target_str or txt == target_str:
            matched_opt = opt
            break
        # Match channel formatted with leading zero or frequency (e.g. '01' or '44 (5.220 GHz)' or 'Channel 44')
        if re.search(rf"\b0*{target_channel}\b", txt) or re.search(rf"\b0*{target_channel}\b", val):
            matched_opt = opt
            break

    if not matched_opt:
        driver.switch_to.default_content()
        raise RuntimeError(
            f"Requested {band} GHz channel {target_channel} is not available in the gateway UI. "
            f"Available options: {available_options}"
        )

    try:
        select_obj.select_by_value(matched_opt.get_attribute("value"))
    except WebDriverException:
        select_obj.select_by_visible_text(matched_opt.text)

    # Verify that the channel was selected
    selected_option = select_obj.first_selected_option
    sel_val = (selected_option.get_attribute("value") or "").strip()
    sel_txt = (selected_option.text or "").strip()

    is_verified = (
        sel_val == target_str
        or sel_txt == target_str
        or bool(re.search(rf"\b0*{target_channel}\b", sel_txt))
        or bool(re.search(rf"\b0*{target_channel}\b", sel_val))
    )
    if not is_verified:
        driver.switch_to.default_content()
        raise RuntimeError(
            f"Failed to verify selection of {band} GHz channel {target_channel}. "
            f"Currently selected: {sel_txt!r} (value={sel_val!r})."
        )

    driver.switch_to.default_content()


def select_security_radio(driver, normalized_security: str) -> None:
    """Locate and select the radio button for the normalized security option."""
    matched_radio = None
    target_frame = None

    for frame in contexts(driver):
        try:
            radios = driver.find_elements(By.CSS_SELECTOR, 'input[type="radio"]')
            for r in radios:
                if not r.is_displayed():
                    continue
                label_text = driver.execute_script(
                    """
                    let r = arguments[0];
                    let text = '';
                    if (r.labels && r.labels.length > 0) {
                        for (let l of r.labels) text += ' ' + (l.innerText || '');
                    }
                    if (r.id) {
                        let lbl = document.querySelector('label[for="' + r.id + '"]');
                        if (lbl) text += ' ' + (lbl.innerText || '');
                    }
                    if (r.parentElement) {
                        text += ' ' + (r.parentElement.innerText || '');
                        if (r.parentElement.nextElementSibling) {
                            text += ' ' + (r.parentElement.nextElementSibling.innerText || '');
                        }
                    }
                    return text;
                    """,
                    r,
                )
                val = (r.get_attribute("value") or "").strip().lower()
                lbl = (label_text or "").strip().lower()
                combined = f"{val} {lbl}"

                # Strict matching based on normalized security to avoid accidental partial matches
                if normalized_security == "WPA2-PSK + WPA3-Personal":
                    if ("wpa2" in combined and "wpa3" in combined) or "mixed" in val or "wpa2+wpa3" in val:
                        matched_radio = r
                        target_frame = frame
                        break
                elif normalized_security == "WPA3-Personal":
                    if ("wpa3" in combined or "sae" in combined) and (
                        "wpa2" not in combined and "mixed" not in combined
                    ):
                        matched_radio = r
                        target_frame = frame
                        break
                elif normalized_security == "WPA2-PSK":
                    if (
                        "wpa2" in combined
                        and "wpa3" not in combined
                        and "mixed" not in combined
                        and "tkip" not in combined
                        and "enterprise" not in combined
                    ):
                        matched_radio = r
                        target_frame = frame
                        break
            if matched_radio:
                break
        except WebDriverException:
            continue

    if not matched_radio:
        driver.switch_to.default_content()
        raise RuntimeError(
            f"Could not locate radio button for security option: {normalized_security}."
        )

    if target_frame is not None:
        driver.switch_to.default_content()
        driver.switch_to.frame(target_frame)

    if not matched_radio.is_selected():
        driver.execute_script("arguments[0].click();", matched_radio)
        time.sleep(0.5)

    if not matched_radio.is_selected():
        try:
            matched_radio.click()
        except WebDriverException:
            pass

    if not matched_radio.is_selected():
        driver.switch_to.default_content()
        raise RuntimeError(
            f"Failed to select radio button for security option: {normalized_security}."
        )

    driver.switch_to.default_content()


def configure_password(driver, password: str) -> None:
    """Locate the Password (Network Key) input field and enter the provided password."""
    password_selectors = (
        (By.CSS_SELECTOR, 'input[name="passphrase"]'),
        (By.CSS_SELECTOR, 'input[id="passphrase"]'),
        (By.CSS_SELECTOR, 'input[name="network_key"]'),
        (By.CSS_SELECTOR, 'input[id="network_key"]'),
        (By.CSS_SELECTOR, 'input[name="passphrase_2g"]'),
        (By.CSS_SELECTOR, 'input[id="passphrase_2g"]'),
        (By.CSS_SELECTOR, 'input[name="sysPasswd"]'),
        (By.CSS_SELECTOR, 'input[name="sec_key"]'),
        (By.CSS_SELECTOR, 'input[name="wpa_key"]'),
        (By.XPATH, "//tr[contains(., 'Password') or contains(., 'Network Key') or contains(., 'Passphrase')]//input[@type='text' or @type='password']"),
        (By.XPATH, "//input[@type='password' or contains(@name, 'passphrase') or contains(@id, 'passphrase') or contains(@name, 'key')]"),
    )

    deadline = time.monotonic() + 10
    pw_field = None
    pw_frame = None
    while time.monotonic() < deadline:
        pw_field, pw_frame = first_visible(driver, password_selectors)
        if pw_field:
            break
        time.sleep(0.5)

    if not pw_field:
        raise RuntimeError("Could not find the Password (Network Key) input field on the Wireless page.")

    if pw_frame is not None:
        driver.switch_to.default_content()
        driver.switch_to.frame(pw_frame)

    pw_field.clear()
    pw_field.send_keys(password)

    current_pw = pw_field.get_attribute("value")
    if current_pw != password:
        driver.execute_script(
            "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change'));",
            pw_field,
            password,
        )
        current_pw = pw_field.get_attribute("value")
        if current_pw != password:
            driver.switch_to.default_content()
            raise RuntimeError("Failed to set wireless password in the input field.")

    driver.switch_to.default_content()


def configure_wireless(driver, args: argparse.Namespace) -> int:
    """Perform wireless configuration workflow on the Orbi gateway."""
    channel_2g = getattr(args, "2g_channel", 1) or 1
    channel_5g = getattr(args, "5g_channel", 36) or 36
    normalized_security = normalize_security(args.security)
    if not normalized_security:
        raise ValueError(f"Invalid security option: {args.security!r}")

    navigate_to_wireless_page(driver)

    configure_ssid(driver, args.ssid)
    print(f"SSID configured: {args.ssid}")

    select_dropdown_channel(driver, "2.4", channel_2g)
    print(f"2.4 GHz Channel: {channel_2g}")

    select_dropdown_channel(driver, "5", channel_5g)
    print(f"5 GHz Channel: {channel_5g}")

    select_security_radio(driver, normalized_security)
    print(f"Security: {normalized_security}")

    configure_password(driver, args.password)
    # Never expose the actual wireless password in logs
    print("Password: ********")

    print("Clicking Apply")
    if not click_apply(driver):
        raise RuntimeError("The wireless settings were entered, but the Apply button could not be clicked.")

    print("Waiting 15 seconds to update the wireless settings")
    time.sleep(15)

    print("Wireless configuration submitted successfully")
    return 0


# ==============================================================================
# Firmware Update Workflow
# ==============================================================================

def update_firmware(driver, args: argparse.Namespace, firmware: Path, model_label: str) -> int:
    """Execute the existing Orbi manual firmware update flow."""
    report_path = Path.cwd() / (
        f"orbi_firmware_update_{re.sub(r'[^A-Za-z0-9_.-]+', '_', model_label)}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    def write_report(status: str, details: str) -> None:
        report_path.write_text(
            "\n".join((
                f"Timestamp: {datetime.now().astimezone().isoformat(timespec='seconds')}",
                f"Model: {model_label}",
                f"Gateway: {args.gateway_ip}",
                f"Firmware: {firmware}",
                f"Status: {status}",
                f"Details: {details}",
                "",
            )),
            encoding="utf-8",
        )

    try:
        menu_results = []
        for label, click_action in (
            ("Advanced", lambda: click_text(driver, r"^Advanced$")),
            ("Administration", lambda: click_text(driver, r"^Administration(?:\s*\+)?$")),
            ("Firmware Update", lambda: click_text(driver, r"^Firmware\s*Update$|^Firmware$")),
            ("Manual Update", lambda: click_text(driver, r"^Manual\s*Update$")),
        ):
            clicked = click_action()
            menu_results.append(f"{label}={'clicked' if clicked else 'not found'}")
            print(f"Navigation: {menu_results[-1]}; page={driver.current_url}")

        file_input, _ = find_file_input(driver)
        firmware_model = firmware.name.split("-V", 1)[0]
        model_tokens = {
            re.sub(r"[^a-z0-9]", "", token.lower())
            for token in (args.model or "", firmware_model)
            if token
        }
        if not file_input and choose_checkbox_for_target(driver, model_tokens):
            print(f"Selected update row matching model: {firmware_model}")
            if click_text(driver, r"^Update$"):
                time.sleep(2)
                file_input, _ = find_file_input(driver)

        if not file_input:
            raise RuntimeError(
                "Could not find a firmware file input after navigation. "
                f"Current page: {driver.current_url!r}; title: {driver.title!r}; "
                f"menu steps: {menu_results!r}. "
                "Check whether the selected model row needs its Update dialog opened."
            )
        file_input.send_keys(str(firmware))
        selected_value = (file_input.get_attribute("value") or "").replace("\\", "/")
        driver.switch_to.default_content()
        print(f"Firmware selected: {firmware.name}")
        if Path(selected_value).name != firmware.name:
            raise RuntimeError(
                f"The file chooser does not show the expected file. Found {selected_value!r}."
            )

        before_url = driver.current_url
        before_text = screen_text(driver)
        before_lines = set(update_report_lines(before_text))
        time.sleep(10)
        if not click_upload(driver):
            raise RuntimeError("The firmware file is selected, but the Upload button was not found.")
        print("Clicked Upload.")

        warning_text = capture_and_accept_warning(driver)
        if warning_text:
            print(f"Warning/confirmation: {warning_text}")
        else:
            print("No warning dialog was shown after clicking Upload.")

        print("Waiting for the Firmware Update page or status message...")
        deadline = time.monotonic() + 60
        final_url = driver.current_url
        final_text = ""
        final_lines = []
        redirected = False
        while time.monotonic() < deadline:
            try:
                final_url = driver.current_url
                final_text = screen_text(driver)
                current_lines = update_report_lines(final_text)
                new_lines = [line for line in current_lines if line not in before_lines]
                if final_url != before_url or new_lines:
                    redirected = True
                    final_lines = new_lines or current_lines
                    break
            except WebDriverException:
                pass
            time.sleep(1)

        if not final_lines:
            final_lines = update_report_lines(final_text)
        print("\n=== Firmware Update Details ===")
        print(f"Page: {final_url}")
        if final_lines:
            for line in final_lines:
                print(line)
        elif warning_text:
            print("No additional firmware status text was found on the next page.")
        else:
            print("No firmware update details or warnings were found on the page.")
        if not redirected:
            print("No redirect or new status message was detected within 60 seconds.")

        write_report(
            "upload_submitted_warning_accepted",
            "\n".join((f"Warning: {warning_text}", f"Page: {final_url}", *final_lines)),
        )
        print(f"\nReport: {report_path}")
        print("Waiting 30 seconds to finish firmware update process...")
        time.sleep(30)
        return 0
    except Exception as exc:
        write_report("error", str(exc))
        raise


# ==============================================================================
# Common Firefox & Gateway Login Helpers
# ==============================================================================

def init_driver(firefox_profile_arg: Path | None) -> webdriver.Firefox:
    """Initialize system Firefox webdriver with optimal Orbi automation options."""
    options = Options()
    options.page_load_strategy = "none"
    options.set_capability("unhandledPromptBehavior", "ignore")
    firefox_executable = shutil.which("firefox")
    if firefox_executable:
        options.binary_location = firefox_executable
        print(f"Firefox executable: {firefox_executable}")

    profile_path = (
        firefox_profile_arg.expanduser().resolve()
        if firefox_profile_arg
        else default_firefox_profile()
    )
    if profile_path and profile_path.is_dir():
        options.profile = FirefoxProfile(str(profile_path))
        print(f"Using a copy of Firefox profile: {profile_path}")
    else:
        print("No desktop Firefox profile was found; using a fresh Firefox profile.")

    driver = webdriver.Firefox(options=options)
    driver.set_page_load_timeout(45)
    return driver


def login_gateway(driver: webdriver.Firefox, gateway_ip: str, login_user: str, password: str) -> None:
    """Navigate to gateway and perform admin login."""
    driver.switch_to.new_window("tab")
    target_host = urlsplit(gateway_ip).hostname
    driver.get(gateway_ip)

    navigation_deadline = time.monotonic() + 15
    while time.monotonic() < navigation_deadline:
        try:
            if urlsplit(driver.current_url).hostname == target_host:
                break
        except WebDriverException:
            pass
        time.sleep(0.25)

    if urlsplit(driver.current_url).hostname != target_host:
        driver.execute_script("window.location.assign(arguments[0]);", gateway_ip)
        navigation_deadline = time.monotonic() + 15
        while time.monotonic() < navigation_deadline:
            try:
                if urlsplit(driver.current_url).hostname == target_host:
                    break
            except WebDriverException:
                pass
            time.sleep(0.25)

    if urlsplit(driver.current_url).hostname != target_host:
        tab_urls = []
        for handle in driver.window_handles:
            try:
                driver.switch_to.window(handle)
                tab_urls.append(driver.current_url)
            except WebDriverException:
                continue
        raise RuntimeError(
            f"Firefox did not navigate to {gateway_ip}. Browser tab URLs: {tab_urls!r}."
        )

    password_field, _ = first_visible(driver, (
        (By.CSS_SELECTOR, 'input[name="password"]'),
        (By.CSS_SELECTOR, 'input[id="password"]'),
        (By.CSS_SELECTOR, 'input[type="password"]'),
    ))
    login_deadline = time.monotonic() + 20
    while not password_field and time.monotonic() < login_deadline:
        time.sleep(0.5)
        password_field, _ = first_visible(driver, (
            (By.CSS_SELECTOR, 'input[name="password"]'),
            (By.CSS_SELECTOR, 'input[id="password"]'),
            (By.CSS_SELECTOR, 'input[type="password"]'),
        ))
    if not password_field:
        raise RuntimeError("Could not find the Orbi password field on the login page.")

    user_field, _ = first_visible(driver, (
        (By.CSS_SELECTOR, 'input[name="username"]'),
        (By.CSS_SELECTOR, 'input[id="username"]'),
        (By.CSS_SELECTOR, 'input[name="userName"]'),
        (By.CSS_SELECTOR, 'input[autocomplete="username"]'),
        (By.CSS_SELECTOR, 'input[type="text"]'),
    ))
    if user_field:
        user_field.clear()
        user_field.send_keys(login_user)

    password_field.clear()
    password_field.send_keys(password)

    submit, _ = first_visible(driver, (
        (By.CSS_SELECTOR, 'button[type="submit"]'),
        (By.CSS_SELECTOR, 'input[type="submit"]'),
        (By.XPATH, "//button[contains(translate(., 'LOGIN', 'login'), 'login')]"),
        (By.XPATH, "//input[contains(translate(@value, 'LOGIN', 'login'), 'login')]"),
    ))
    if submit:
        submit.click()
    else:
        password_field.send_keys("\n")
    # Allow the gateway time to authenticate instead of checking after only 3 seconds.
    login_deadline = time.monotonic() + 30
    while time.monotonic() < login_deadline:
        time.sleep(1)
        driver.switch_to.default_content()
        password_after_login, _ = first_visible(driver, (
            (By.CSS_SELECTOR, 'input[name="password"]'),
            (By.CSS_SELECTOR, 'input[id="password"]'),
            (By.CSS_SELECTOR, 'input[type="password"]'),
        ))
        if not password_after_login:
            break
    else:
        raise RuntimeError(
            f"Login did not complete within 30 seconds at {driver.current_url!r}; "
            "check the gateway credentials or login button selector."
        )

    print("Login successful")


# Dispatcher dictionary for action-based execution
ACTIONS = {
    "firmware_update": update_firmware,
    "wireless_config": configure_wireless,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="""Sign in to an Orbi gateway to perform actions (firmware upload, wireless config) using Firefox.

Examples:
  # Wireless configuration with specified channels
  python3 ap_firmware_update.py \\
    --action wireless_config \\
    --ssid "Test_WiFi" \\
    --password "Test@12345" \\
    --security "wpa2mixed" \\
    --2g_channel 6 \\
    --5g_channel 40

  # Wireless configuration with default channels
  python3 ap_firmware_update.py \\
    --action wireless_config \\
    --ssid "Test_WiFi" \\
    --password "Test@12345" \\
    --security "wpa3"

  # Firmware update
  python3 ap_firmware_update.py \\
    --action firmware_update \\
    --firmware "/home/lanforge/Tarun/RBE781-V12.1.12.31_5.5.32-beta-signed.chk"

  # Backward-compatible firmware update (default action)
  python3 ap_firmware_update.py \\
    --gateway_ip 10.168.168.1 \\
    --login_user admin \\
    --login_pw "Password@123" \\
    --firmware "/home/lanforge/Tarun/RBE781-V12.1.12.31_5.5.32-beta-signed.chk" \\
    --model Orbi781
""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Common CLI arguments
    parser.add_argument(
        "--action",
        choices=["firmware_update", "wireless_config"],
        default="firmware_update",
        help="Action to perform: 'firmware_update' or 'wireless_config' (default: firmware_update)",
    )
    parser.add_argument(
        "--gateway_ip",
        default="10.168.168.1",
        type=gateway_url,
        help="Gateway IP or URL, e.g. 192.168.1.1 (default: 10.168.168.1)",
    )
    parser.add_argument(
        "--login_user",
        default="admin",
        help="Gateway login name (default: admin)",
    )
    parser.add_argument(
        "--login_pw",
        default=None,
        help="Gateway password; ORBI_LOGIN_PW env var or default 'Password@123' used if omitted",
    )
    parser.add_argument(
        "--firefox-profile",
        type=Path,
        help="Optional Firefox profile directory; by default the script detects the desktop profile",
    )

    # Arguments for firmware_update
    parser.add_argument(
        "--firmware",
        type=Path,
        default=None,
        help="Path to the router or satellite firmware image (required for firmware_update)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Orbi model identifier to include in the update report (optional)",
    )

    # Arguments for wireless_config
    parser.add_argument(
        "--ssid",
        default=None,
        help="Wireless network name / SSID (required for wireless_config)",
    )
    parser.add_argument(
        "--password",
        default=None,
        help="Wireless network key / password (required for wireless_config)",
    )
    parser.add_argument(
        "--security",
        default=None,
        help="Wireless security mode: wpa2, wpa3, wpa2+wpa3, wpa2mixed, wpa3mixed (required for wireless_config)",
    )
    parser.add_argument(
        "--2g_channel",
        type=positive_int,
        default=1,
        help="2.4 GHz channel positive integer (default: 1)",
    )
    parser.add_argument(
        "--5g_channel",
        type=positive_int,
        default=36,
        help="5 GHz channel positive integer (default: 36)",
    )

    args = parser.parse_args()

    # Determine password: CLI argument > ORBI_LOGIN_PW env var > default "Password@123"
    password = args.login_pw
    if password is None:
        password = os.environ.get("ORBI_LOGIN_PW", "Password@123")
    if not password:
        password = getpass.getpass("Orbi admin password (input is hidden): ")
    if not password:
        parser.error("Password cannot be empty.")

    # Validate action-specific arguments before launching browser
    if args.action == "wireless_config":
        validate_wireless_args(args, parser)
    elif args.action == "firmware_update":
        validate_firmware_args(args, parser)
    else:
        parser.error(f"Unsupported action: {args.action}")

    # Action-specific setup and console announcement
    firmware: Path | None = None
    model_label: str = "Unknown_Model"

    if args.action == "wireless_config":
        gateway_host = urlsplit(args.gateway_ip).hostname or args.gateway_ip
        print(f"Action: {args.action}")
        print(f"Gateway: {gateway_host}")
    elif args.action == "firmware_update":
        firmware = args.firmware.expanduser().resolve()
        firmware_model = firmware.name.split("-V", 1)[0]
        model_label = args.model or firmware_model or "Unknown_Model"
        print(f"\nModel: {model_label}")
        print(f"Gateway: {args.gateway_ip}")
        print(f"Firmware: {firmware}")
        print("Opening the system-installed Firefox.\n")

    driver = None
    try:
        driver = init_driver(args.firefox_profile)
        login_gateway(driver, args.gateway_ip, args.login_user, password)

        if args.action == "wireless_config":
            return configure_wireless(driver, args)
        elif args.action == "firmware_update":
            assert firmware is not None
            return update_firmware(driver, args, firmware, model_label)
        else:
            raise RuntimeError(f"Action {args.action} is not implemented.")
    except Exception as exc:
        print(f"\nStopped safely: {exc}", file=sys.stderr)
        if args.action == "firmware_update":
            print("No further update action was taken. Check the gateway page before retrying.")
        return 1
    finally:
        if driver is not None:
            driver.quit()


if __name__ == "__main__":
    raise SystemExit(main())
