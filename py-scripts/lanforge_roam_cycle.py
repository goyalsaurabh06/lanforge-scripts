#!/usr/bin/env python3
"""
LANforge attenuation-driven roaming capture runner.

Per cycle this script:
1. Configures monitor/sniffer radios on the requested channels.
2. Sets attenuator modules to their initial values.
3. Verifies station AP/BSSID state.
4. Starts packet capture for the cycle.
5. Performs attenuation sweeps to trigger roaming.
6. Saves local CSV/JSON metadata for the captures and BSSID transitions.
"""

import argparse
import csv
import importlib
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


logger = logging.getLogger(__name__)
MAC_RE = re.compile(r"(?i)\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b")
INVALID_BSSIDS = {"", "NA", "Not-Associated", "00:00:00:00:00:00"}
DEFAULT_REMOTE_CAPTURE_DIR = os.getcwd()


def add_lanforge_paths() -> None:
    here = Path(__file__).resolve()
    candidates = [
        here.parent,
        here.parent.parent,
        here.parent.parent.parent,
    ]
    for candidate in candidates:
        if candidate.exists():
            path_text = str(candidate)
            if path_text not in sys.path:
                sys.path.append(path_text)


add_lanforge_paths()

realm = importlib.import_module("py-json.realm")
LFUtils = importlib.import_module("py-json.LANforge.LFUtils")
add_monitor = importlib.import_module("py-json.LANforge.add_monitor")
set_wifi_radio = importlib.import_module("py-json.LANforge.set_wifi_radio")
sniff_radio = importlib.import_module("py-scripts.lf_sniff_radio")
sta_connect = importlib.import_module("py-scripts.sta_connect2")
Realm = realm.Realm
SET_RADIO_MODE = set_wifi_radio.set_radio_mode


@dataclass
class SnifferConfig:
    radio: str
    channel: str
    frequency: Optional[int] = None
    bandwidth: str = "20"
    center_freq: Optional[int] = None
    monitor_name: str = ""


@dataclass
class StationConfig:
    radio: str
    ssid: str
    security: str
    password: str
    num_sta: int
    station_flag: Optional[str] = None
    sta_type: str = "11r"
    option: str = "ota"
    identity: str = "testuser"
    ttls_pass: str = "testpasswd"


def split_multi_values(values: Optional[Iterable[str]]) -> List[str]:
    tokens: List[str] = []
    for value in values or []:
        for token in str(value).replace(",", " ").split():
            token = token.strip()
            if token:
                tokens.append(token)
    return tokens


def normalize_mac(value: str) -> str:
    match = MAC_RE.search(str(value or ""))
    return match.group(0).lower() if match else ""


def first_int(value: object) -> Optional[int]:
    match = re.search(r"-?\d+", str(value or ""))
    return int(match.group(0)) if match else None


def invalid_bssid(value: object) -> bool:
    text = str(value or "").strip()
    return text in INVALID_BSSIDS or text.lower() in {"na", "not-associated"}


def parse_duration_seconds(value: Optional[str], default: Optional[int] = None) -> Optional[int]:
    if value is None:
        return default
    text = str(value).strip().lower()
    match = re.fullmatch(r"(\d+)(ms|s|m|h)?", text)
    if not match:
        raise argparse.ArgumentTypeError(f"Invalid duration '{value}'. Use values like 30, 30s, 5m, or 1h.")
    amount = int(match.group(1))
    unit = match.group(2) or "s"
    if unit == "ms":
        return max(1, int(round(amount / 1000.0)))
    if unit == "s":
        return amount
    if unit == "m":
        return amount * 60
    if unit == "h":
        return amount * 3600
    raise argparse.ArgumentTypeError(f"Unsupported duration unit '{unit}'")


def parse_key_value_blob(value: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    clean = str(value).strip().strip("[]")
    clean = clean.replace("'", "").replace('"', "")
    for token in re.split(r"[,\s]+", clean):
        token = token.strip()
        if not token:
            continue
        if "==" in token:
            key, val = token.split("==", 1)
        elif "=" in token:
            key, val = token.split("=", 1)
        else:
            continue
        result[key.strip().replace("-", "_").lower()] = val.strip()
    return result


def attenuation_to_ddb(value: str, unit: str) -> int:
    text = str(value).strip().lower()
    if text.endswith("db"):
        text = text[:-2]
    number = float(text)
    if unit == "ddb":
        return int(round(number))
    return int(round(number * 10))


def ddb_to_db(value: int) -> float:
    return round(value / 10.0, 1)


def parse_modules(value: str) -> List[int]:
    """Parse a comma-separated module index string like '0,1,2' into a list of ints."""
    if not value or value.strip().lower() == "all":
        return []
    try:
        return [int(m.strip()) for m in value.split(",") if m.strip()]
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid module list '{value}'. Use comma-separated integers like 0,1,2 or 'all'."
        )


def parse_sniffer(value: str, index: int) -> SnifferConfig:
    data = parse_key_value_blob(value)
    if data:
        radio = data.get("radio") or data.get("sniffer") or data.get("sniff_radio")
        channel = data.get("channel")
        frequency = data.get("frequency") or data.get("freq")
        bandwidth = data.get("bandwidth") or data.get("bw") or "20"
        center_freq = data.get("center_freq") or data.get("center_frequency")
        monitor_name = data.get("monitor") or data.get("monitor_name") or f"roammon{index}"
        if not radio or not channel:
            raise argparse.ArgumentTypeError(
                "--sniffer requires at least radio and channel, for example radio=1.1.wiphy2,channel=36"
            )
        return SnifferConfig(
            radio=radio,
            channel=str(channel),
            frequency=int(frequency) if frequency else None,
            bandwidth=str(bandwidth),
            center_freq=int(center_freq) if center_freq else None,
            monitor_name=monitor_name,
        )

    parts = [part.strip() for part in re.split(r"[:,]", value) if part.strip()]
    if len(parts) < 2:
        raise argparse.ArgumentTypeError(
            "--sniffer must look like 1.1.wiphy2:36 or radio=1.1.wiphy2,channel=36"
        )
    return SnifferConfig(
        radio=parts[0],
        channel=parts[1],
        frequency=int(parts[2]) if len(parts) > 2 and parts[2] else None,
        bandwidth=parts[3] if len(parts) > 3 and parts[3] else "20",
        center_freq=int(parts[4]) if len(parts) > 4 and parts[4] else None,
        monitor_name=f"roammon{index}",
    )


def parse_station_config(value: str, defaults: argparse.Namespace) -> StationConfig:
    data = parse_key_value_blob(value)
    if not data:
        raise argparse.ArgumentTypeError(
            "--station-config must use key/value syntax like radio==1.1.wiphy0,ssid==ROAM,num_sta==2"
        )

    radio = data.get("radio") or data.get("sta_radio") or defaults.station_radio
    ssid = data.get("ssid") or defaults.ssid
    security = data.get("security") or defaults.security
    password = data.get("passwd") or data.get("password") or defaults.password
    num_sta = data.get("num_sta") or data.get("stations") or defaults.num_sta

    if not radio or not ssid or not security or num_sta is None:
        raise argparse.ArgumentTypeError(
            "Station config requires radio, ssid, security, and num_sta. Password is optional for open/owe."
        )
    if not password and str(security).lower() in {"open", "owe"}:
        password = "[BLANK]"
    if not password:
        raise argparse.ArgumentTypeError("Station config requires passwd/password unless security is open or owe.")

    return StationConfig(
        radio=radio,
        ssid=ssid,
        security=security,
        password=password,
        num_sta=int(num_sta),
        station_flag=data.get("sta_flag") or data.get("station_flag") or defaults.station_flag,
        sta_type=data.get("sta_type") or defaults.sta_type,
        option=data.get("option") or defaults.option,
        identity=data.get("identity") or defaults.identity,
        ttls_pass=data.get("ttls_pass") or defaults.ttls_pass,
    )


def load_ap_config(filepath: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Load per-band AP BSSIDs from a JSON file.

    Expected format::

        {
            "source": {"2g": "AA:BB:CC:DD:EE:FF", "5g": "AA:BB:CC:DD:EE:01"},
            "target": {"2g": "AA:BB:CC:DD:EE:10", "6g": "AA:BB:CC:DD:EE:11"}
        }

    Returns (source_by_band, target_by_band) dicts.
    """
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise argparse.ArgumentTypeError(f"Unable to load --ap-config '{filepath}': {exc}")

    if not isinstance(data, dict):
        raise argparse.ArgumentTypeError(f"--ap-config '{filepath}' must be a JSON object")

    source = data.get("source", {})
    target = data.get("target", {})

    if not isinstance(source, dict) or not isinstance(target, dict):
        raise argparse.ArgumentTypeError(
            f"--ap-config '{filepath}': 'source' and 'target' must be JSON objects "
            f"with band keys (2g, 5g, 6g)"
        )

    valid_bands = {"2g", "5g", "6g"}
    for role, bands in [("source", source), ("target", target)]:
        for band in bands:
            if band not in valid_bands:
                raise argparse.ArgumentTypeError(
                    f"--ap-config '{filepath}': unknown band '{band}' under '{role}'. "
                    f"Valid bands: {', '.join(sorted(valid_bands))}"
                )
            mac = normalize_mac(str(bands[band]))
            if not mac:
                raise argparse.ArgumentTypeError(
                    f"--ap-config '{filepath}': invalid BSSID '{bands[band]}' for {role}.{band}"
                )

    return source, target


def parse_expected_bssids(values: Optional[Iterable[str]]) -> List[str]:
    bssids: List[str] = []
    for token in split_multi_values(values):
        if "=" in token:
            token = token.split("=", 1)[1]
        mac = normalize_mac(token)
        if not mac:
            raise argparse.ArgumentTypeError(f"Invalid BSSID '{token}'")
        if mac not in bssids:
            bssids.append(mac)
    return bssids


def build_attenuator_initials(args: argparse.Namespace) -> Dict[str, int]:
    attenuators: Dict[str, int] = {}

    for token in split_multi_values(args.attenuator):
        if "=" in token:
            serial, value = token.split("=", 1)
        elif ":" in token:
            serial, value = token.split(":", 1)
        else:
            serial, value = token, args.initial_attenuation
        serial = serial.strip()
        if not serial:
            continue
        attenuators[serial] = attenuation_to_ddb(value, args.attenuation_unit)

    for token in split_multi_values(args.attenuators):
        if "=" in token:
            serial, value = token.split("=", 1)
        elif ":" in token:
            serial, value = token.split(":", 1)
        else:
            serial, value = token, args.initial_attenuation
        serial = serial.strip()
        if serial and serial not in attenuators:
            attenuators[serial] = attenuation_to_ddb(value, args.attenuation_unit)

    return attenuators


def build_step_values(max_ddb: int, step_ddb: int) -> Tuple[List[int], List[int]]:
    increments = list(range(0, max_ddb + 1, step_ddb))
    if increments[-1] != max_ddb:
        increments.append(max_ddb)
    decrements = list(range(max_ddb, -1, -step_ddb))
    if decrements[-1] != 0:
        decrements.append(0)
    length = min(len(increments), len(decrements))
    return increments[:length], decrements[:length]


def build_linear_steps(from_ddb: int, to_ddb: int, count: int) -> List[int]:
    """Return `count` values linearly interpolated from from_ddb to to_ddb."""
    if count <= 1:
        return [to_ddb]
    delta = (to_ddb - from_ddb) / (count - 1)
    values = [int(round(from_ddb + i * delta)) for i in range(count)]
    values[-1] = to_ddb
    return values


def build_steps_by_size(from_ddb: int, to_ddb: int, step_ddb: int) -> List[int]:
    """Return values stepping from from_ddb toward to_ddb in increments of step_ddb."""
    if step_ddb <= 0 or from_ddb == to_ddb:
        return [to_ddb]
    direction = 1 if to_ddb > from_ddb else -1
    steps: List[int] = []
    current = from_ddb
    while (direction > 0 and current < to_ddb) or (direction < 0 and current > to_ddb):
        steps.append(current)
        current += direction * step_ddb
    steps.append(to_ddb)
    return steps


class LanforgeRoamCycle(Realm):
    def __init__(
        self,
        host: str,
        port: int,
        sniffers: Sequence[SnifferConfig],
        attenuator_initials: Dict[str, int],
        max_attenuation_ddb: int,
        step_ddb: int,
        step_wait: int,
        settle_time: int,
        output_dir: str,
        remote_capture_dir: str,
        capture_filter: Optional[str],
        expected_bssids: Sequence[str],
        bssid_timeout: int,
        soft_roam: bool,
        bg_scan: str,
        disable_restart_dhcp: bool,
        cleanup_monitors: bool,
        isolate_unused: bool,
        maximize_unused_attenuators: bool,
    ):
        super().__init__(host, port)
        self.host = host
        self.port = port
        self.sniffer_configs = list(sniffers)
        self.attenuator_initials = dict(attenuator_initials)
        self.attenuator_order = list(attenuator_initials.keys())
        self.max_attenuation_ddb = max_attenuation_ddb
        self.step_ddb = step_ddb
        self.step_wait = step_wait
        self.settle_time = settle_time
        self.output_dir = os.path.abspath(output_dir)
        self.remote_capture_dir = remote_capture_dir.rstrip("/")
        self.remote_run_dir: str = ""
        self.capture_filter = capture_filter
        self.expected_bssids = {bssid.lower() for bssid in expected_bssids}
        self.bssid_timeout = bssid_timeout
        self.soft_roam = soft_roam
        self.bg_scan = bg_scan
        self.disable_restart_dhcp = disable_restart_dhcp
        self.cleanup_monitors = cleanup_monitors
        self.isolate_unused = isolate_unused
        self.maximize_unused_attenuators = maximize_unused_attenuators
        self.station_profile = self.new_station_profile()
        self.sta_connect = sta_connect.StaConnect2(host=self.host, port=self.port, outfile="sta_connect2.csv")
        self.sniffers = []
        self.station_list: List[str] = []
        self.increments, self.decrements = build_step_values(max_attenuation_ddb, step_ddb)
        self.capture_rows: List[Dict[str, object]] = []
        self.roam_rows: List[Dict[str, object]] = []

        if len(self.attenuator_order) < 2:
            raise ValueError("At least two attenuators are required for an attenuation-driven roam.")

    @property
    def attenuator_pairs(self) -> List[Tuple[str, str]]:
        order = self.attenuator_order
        return list(zip(order, order[1:] + order[:1]))

    def estimated_cycle_seconds(self) -> int:
        return len(self.attenuator_pairs) * (len(self.increments) * self.step_wait + self.settle_time) + 10

    def ensure_output_dir(self) -> None:
        os.makedirs(self.output_dir, exist_ok=True)

    def validate_attenuators(self) -> None:
        response = self.atten_list()
        if not response:
            raise RuntimeError(f"No attenuators were returned by LANforge manager {self.host}:{self.port}")

        available = {}
        for item in response:
            if not item:
                continue
            serial = list(item.keys())[0]
            available[serial] = list(item.values())[0]

        missing = [serial for serial in self.attenuator_order if serial not in available]
        if missing:
            raise RuntimeError(f"Missing requested attenuator(s): {', '.join(missing)}")

        phantom = [
            serial
            for serial in self.attenuator_order
            if str(available.get(serial, {}).get("state", "")).lower() == "phantom"
        ]
        if phantom:
            raise RuntimeError(f"Requested attenuator(s) are phantom: {', '.join(phantom)}")

        if self.maximize_unused_attenuators:
            for serial, info in available.items():
                if serial in self.attenuator_initials:
                    continue
                if str(info.get("state", "")).lower() == "phantom":
                    continue
                logger.info("Setting unused attenuator %s to %.1f dB", serial, ddb_to_db(self.max_attenuation_ddb))
                self.set_atten(serial, self.max_attenuation_ddb)

    def configure_initial_attenuators(self) -> None:
        for serial, value in self.attenuator_initials.items():
            logger.info("Initial attenuator %s = %.1f dB", serial, ddb_to_db(value))
            self.set_atten(serial, value)

    def set_pair_start(self, active: str, passive: str) -> None:
        logger.info("Preparing roam pair active=%s passive=%s", active, passive)
        for serial in self.attenuator_order:
            if serial == active:
                self.set_atten(serial, 0)
            elif serial == passive:
                self.set_atten(serial, self.max_attenuation_ddb)
            elif self.isolate_unused:
                self.set_atten(serial, self.max_attenuation_ddb)
        time.sleep(self.settle_time)

    def get_radio_status(self, shelf: int, resource: int, radio: str) -> Dict[str, object]:
        status = self.json_get(f"/radiostatus/{shelf}/{resource}/{radio}?fields=channel,frequency,country")
        if not status:
            raise RuntimeError(f"No radio status returned for {shelf}.{resource}.{radio}")
        if radio in status:
            return status[radio]
        if isinstance(status, dict):
            for value in status.values():
                if isinstance(value, dict):
                    return value
        raise RuntimeError(f"Unable to parse radio status for {shelf}.{resource}.{radio}: {status}")

    def radio_matches_channel(self, status: Dict[str, object], desired_channel: object, desired_frequency: Optional[int]) -> bool:
        current_frequency = first_int(status.get("frequency"))
        if desired_frequency is not None and current_frequency is not None:
            return current_frequency == int(desired_frequency)

        current_channel = first_int(status.get("channel"))
        desired_channel_int = first_int(desired_channel)
        if current_channel is not None and desired_channel_int is not None:
            return current_channel == desired_channel_int
        return str(status.get("channel") or "").strip() == str(desired_channel or "").strip()

    def configure_sniffer_radio_channel(self, cfg: SnifferConfig, sniffer) -> None:
        shelf, resource, radio, _ = self.name_to_eid(cfg.radio)
        desired_channel = getattr(sniffer, "channel", cfg.channel)
        desired_frequency = first_int(getattr(sniffer, "freq", None) or cfg.frequency)
        status = self.get_radio_status(shelf, resource, radio)

        if self.radio_matches_channel(status, desired_channel, desired_frequency):
            logger.info(
                "Sniffer radio %s is already on requested channel/frequency: channel=%s frequency=%s",
                cfg.radio,
                status.get("channel"),
                status.get("frequency"),
            )
            return

        country = status.get("country", 0)
        if desired_frequency is None:
            desired_frequency = self.channel_freq(channel_=desired_channel)

        logger.info(
            "Setting sniffer radio %s from channel=%s frequency=%s to channel=%s frequency=%s",
            cfg.radio,
            status.get("channel"),
            status.get("frequency"),
            desired_channel,
            desired_frequency,
        )
        self.json_post(
            "/cli-json/set_wifi_radio",
            _data={
                "shelf": shelf,
                "resource": resource,
                "radio": radio,
                "mode": SET_RADIO_MODE["AUTO"],
                "channel": desired_channel,
                "country": country,
                "frequency": desired_frequency,
            },
        )
        time.sleep(1)

    def add_sniffer_monitor(self, cfg: SnifferConfig, sniffer, monitor_name: str) -> None:
        shelf, resource, radio, _ = self.name_to_eid(cfg.radio)
        sniffer.monitor.resource = resource
        sniffer.monitor.monitor_name = monitor_name
        computed_flags = 0
        for flag_name in sniffer.monitor.flag_names:
            computed_flags += add_monitor.flags[flag_name]

        logger.info("Creating monitor %s on sniffer radio %s", monitor_name, cfg.radio)
        self.json_post(
            "/cli-json/add_monitor",
            {
                "shelf": shelf,
                "resource": resource,
                "radio": radio,
                "ap_name": monitor_name,
                "flags": computed_flags,
                "flags_mask": sniffer.monitor.flags_mask,
            },
        )

    def configure_sniffers(self) -> None:
        self.sniffers = []
        for index, cfg in enumerate(self.sniffer_configs, start=1):
            monitor_name = cfg.monitor_name or f"roammon{index}"
            logger.info(
                "Configuring sniffer radio=%s channel=%s frequency=%s monitor=%s",
                cfg.radio,
                cfg.channel,
                cfg.frequency if cfg.frequency is not None else "auto",
                monitor_name,
            )
            sniffer = sniff_radio.SniffRadio(
                lfclient_host=self.host,
                lfclient_port=self.port,
                radio=cfg.radio,
                channel=cfg.channel,
                channel_freq=cfg.frequency,
                channel_bw=cfg.bandwidth,
                center_freq=cfg.center_freq,
                monitor_name=monitor_name,
                sniff_filter=self.capture_filter,
            )
            radio_eid = self.name_to_eid(cfg.radio)
            sniffer.monitor.resource = radio_eid[1]
            sniffer.monitor.monitor_name = monitor_name
            try:
                sniffer.monitor.cleanup()
            except Exception as exc:
                logger.debug("Monitor cleanup for %s skipped/failed: %s", monitor_name, exc)
            self.configure_sniffer_radio_channel(cfg, sniffer)
            self.add_sniffer_monitor(cfg, sniffer, monitor_name)
            self.sniffers.append((cfg, sniffer))

    def cleanup_sniffers(self) -> None:
        for cfg, sniffer in self.sniffers:
            try:
                sniffer.monitor.admin_down()
            except Exception as exc:
                logger.debug("Unable to admin-down monitor %s: %s", cfg.monitor_name, exc)
            if self.cleanup_monitors:
                try:
                    sniffer.cleanup()
                except Exception as exc:
                    logger.warning("Unable to cleanup monitor %s: %s", cfg.monitor_name, exc)

    def discover_stations_on_radios(self, radios: Sequence[str]) -> List[str]:
        """Return EIDs of all existing station ports whose parent dev matches any of the given radios."""
        discovered: List[str] = []
        for radio in radios:
            shelf, resource, radio_port, _ = self.name_to_eid(radio)
            print("the radio is:",shelf,resource,radio_port,radio)
            response = self.json_get(f"/port/{shelf}/{resource}/?fields=port+type,parent+dev")
            if not response or ("interfaces" not in response and "interface" not in response):
                logger.warning("No port list returned for resource %s.%s (radio %s)", shelf, resource, radio)
                continue
            before = len(discovered)
            raw = response.get("interfaces") or response.get("interface")
            entries = raw if isinstance(raw, list) else [raw]
            for entry in entries:
                if not entry:
                    continue
                full_eid = list(entry.keys())[0]
                info = list(entry.values())[0]
                if str(info.get("parent dev") or "") == radio_port:
                    discovered.append(f"{shelf}.{resource}.{full_eid.split('.')[-1]}")
            found = len(discovered) - before
            logger.info("Found %s station(s) on radio %s", found, radio)
        return discovered

    def start_cycle_captures(self, cycle: int, duration_sec: int, label: str = "cycle") -> List[Dict[str, object]]:
        captures = []
        multi_sniffer = len(self.sniffers) > 1
        for cfg, sniffer in self.sniffers:
            monitor = sniffer.monitor.monitor_name
            monitor_suffix = f"_{monitor}" if multi_sniffer else ""
            remote_pcap = f"{self.remote_run_dir}/{label}_{cycle}{monitor_suffix}.pcap"
            logger.info("Starting capture cycle=%s monitor=%s output=%s", cycle, monitor, remote_pcap)
            sniffer.monitor.admin_down()
            time.sleep(1)
            sniffer.monitor.admin_up()
            monitor_eid = f"1.{sniffer.monitor.resource}.{monitor}"
            LFUtils.wait_until_ports_appear(
                base_url=f"http://{self.host}:{self.port}",
                port_list=monitor_eid,
                debug=False,
                timeout=120,
            )
            logger.info("Setting monitor %s frequency to %s MHz before capture", monitor, sniffer.freq)
            sniffer._set_freq(ssh_root=self.host, ssh_passwd="lanforge", freq=sniffer.freq)
            sniffer.monitor.start_sniff(
                capname=remote_pcap,
                duration_sec=duration_sec,
            )
            row = {
                "cycle": cycle,
                "radio": cfg.radio,
                "channel": cfg.channel,
                "frequency": cfg.frequency or "",
                "bandwidth": cfg.bandwidth,
                "center_freq": cfg.center_freq or "",
                "monitor": monitor,
                "remote_pcap": remote_pcap,
                "duration_sec": duration_sec,
            }
            captures.append(row)
            self.capture_rows.append(row)
        return captures

    def get_port_field(self, station: str, field: str) -> Optional[str]:
        shelf, resource, port, _ = self.name_to_eid(station)
        data = self.json_get(f"/port/{shelf}/{resource}/{port}?fields={field}")
        if data and "interface" in data and data["interface"] is not None:
            return data["interface"].get(field)
        return None

    def current_station_bssids(self, stations: Sequence[str]) -> Dict[str, str]:
        bssids: Dict[str, str] = {}
        for station in stations:
            value = self.get_port_field(station, "ap")
            bssids[station] = str(value or "")
        return bssids

    def wait_for_station_bssids(self, stations: Sequence[str], timeout: Optional[int] = None) -> Dict[str, str]:
        timeout = self.bssid_timeout if timeout is None else timeout
        deadline = time.time() + timeout
        latest = self.current_station_bssids(stations)
        while time.time() < deadline:
            pending = [
                station
                for station, bssid in latest.items()
                if invalid_bssid(bssid)
            ]
            if not pending:
                return latest
            time.sleep(3)
            latest = self.current_station_bssids(stations)
        missing = [station for station, bssid in latest.items() if invalid_bssid(bssid)]
        if missing:
            raise RuntimeError(f"Station(s) did not report a valid AP/BSSID: {', '.join(missing)}")
        return latest

    def get_signal(self, station: str) -> str:
        signal = self.get_port_field(station, "signal")
        return str(signal or "")

    def verify_ap_bssids(self, stations: Sequence[str], cycle: int) -> Dict[str, str]:
        bssids = self.wait_for_station_bssids(stations)
        logger.info("Cycle %s station BSSID map: %s", cycle, bssids)
        if self.expected_bssids:
            mismatches = {
                station: bssid
                for station, bssid in bssids.items()
                if str(bssid).lower() not in self.expected_bssids
            }
            if mismatches:
                pretty = ", ".join(f"{station}={bssid}" for station, bssid in mismatches.items())
                expected = ", ".join(sorted(self.expected_bssids))
                raise RuntimeError(f"Observed BSSID mismatch. Expected one of [{expected}], got {pretty}")
        return bssids

    def apply_bgscan_to_stations(self, station_names: Sequence[str]) -> None:
        if not self.soft_roam:
            return
        for station in station_names:
            shelf, resource, port, _ = self.name_to_eid(station)
            logger.info('Setting custom WiFi on %s: bgscan="%s"', station, self.bg_scan)
            self.json_post(
                "/cli-json/set_wifi_custom",
                {
                    "shelf": shelf,
                    "resource": resource,
                    "port": str(port),
                    "type": "NA",
                    "text": f'bgscan="{self.bg_scan}"',
                },
            )

    def reset_station_ports(self, station_names: Sequence[str], wait_seconds: int = 5) -> None:
        for station in station_names:
            logger.info("Resetting station port after custom WiFi update: %s", station)
            self.reset_port(station)
        if wait_seconds > 0:
            logger.info("Waiting %ss after station port reset", wait_seconds)
            time.sleep(wait_seconds)

    def pre_cleanup_stations(self, station_names: Sequence[str]) -> None:
        if not station_names:
            return
        profile = self.new_station_profile()
        logger.info("Cleaning existing station ports before create: %s", ", ".join(station_names))
        profile.cleanup(list(station_names), delay=1)
        self.wait_until_ports_disappear(sta_list=list(station_names), debug_=False)

    def create_clients(self, config: StationConfig, station_names: Sequence[str]) -> bool:
        logger.info("Creating stations on %s: %s", config.radio, ", ".join(station_names))
        self.station_profile = self.new_station_profile()

        if config.station_flag:
            for flag in config.station_flag.split(","):
                flag = flag.strip()
                if flag:
                    self.station_profile.set_command_flag("add_sta", flag, 1)

        sta_type = (config.sta_type or "normal").lower()
        if sta_type == "normal":
            self.station_profile.set_command_flag("add_sta", "power_save_enable", 1)
            if not self.soft_roam:
                self.station_profile.set_command_flag("add_sta", "disable_roam", 1)
            elif config.option == "otds":
                self.station_profile.set_command_flag("add_sta", "ft-roam-over-ds", 1)

        self.station_profile.use_security(config.security, config.ssid, config.password)
        self.station_profile.set_number_template("00")
        self.station_profile.set_command_flag("add_sta", "create_admin_down", 1)
        self.station_profile.set_command_param("set_port", "report_timer", 1500)
        self.station_profile.set_command_flag("set_port", "rpt_timer", 1)

        if self.disable_restart_dhcp:
            self.station_profile.set_command_flag("set_port", "no_dhcp_restart", 1)
            self.station_profile.set_command_flag("set_port", "no_ifup_post", 1)
            self.station_profile.set_command_flag("set_port", "use_dhcp", 1)
            self.station_profile.set_command_flag("set_port", "current_flags", 1)
            self.station_profile.set_command_flag("set_port", "dhcp", 1)
            self.station_profile.set_command_flag("set_port", "dhcp_rls", 1)
            self.station_profile.set_command_flag("set_port", "no_dhcp_conn", 1)

        if sta_type == "11r":
            self.station_profile.set_command_flag("add_sta", "80211u_enable", 0)
            if not self.soft_roam:
                self.station_profile.set_command_flag("add_sta", "disable_roam", 1)
            elif config.option == "otds":
                self.station_profile.set_command_flag("add_sta", "ft-roam-over-ds", 1)
            self.station_profile.set_wifi_extra(
                key_mgmt="FT-PSK",
                pairwise="",
                group="",
                psk="",
                eap="",
                identity="",
                passwd="",
                pin="",
                phase1="NA",
                phase2="NA",
                pac_file="NA",
                private_key="NA",
                pk_password="NA",
                client_cert="NA",
                imsi="NA",
                milenage="NA",
                roaming_consortium="NA",
                venue_group="NA",
                network_type="NA",
                ipaddr_type_avail="NA",
                network_auth_type="NA",
                anqp_3gpp_cell_net="NA",
            )

        if sta_type == "11r-sae":
            self.station_profile.set_command_flag("add_sta", "ieee80211w", 2)
            self.station_profile.set_command_flag("add_sta", "80211u_enable", 0)
            self.station_profile.set_command_flag("add_sta", "8021x_radius", 1)
            if not self.soft_roam:
                self.station_profile.set_command_flag("add_sta", "disable_roam", 1)
            elif config.option == "otds":
                self.station_profile.set_command_flag("add_sta", "ft-roam-over-ds", 1)
            self.station_profile.set_command_flag("add_sta", "power_save_enable", 1)
            self.station_profile.set_wifi_extra(
                key_mgmt="FT-SAE",
                pairwise="",
                group="",
                psk="",
                eap="",
                identity="",
                passwd="",
                pin="",
                phase1="NA",
                phase2="NA",
                pac_file="NA",
                private_key="NA",
                pk_password="NA",
                hessid="00:00:00:00:00:01",
                realm="localhost.localdomain",
                client_cert="NA",
                imsi="NA",
                milenage="NA",
                domain="localhost.localdomain",
                roaming_consortium="NA",
                venue_group="NA",
                network_type="NA",
                ipaddr_type_avail="NA",
                network_auth_type="NA",
                anqp_3gpp_cell_net="NA",
            )

        if sta_type == "11r-sae-802.1x":
            self.station_profile.set_command_flag("set_port", "rpt_timer", 1)
            self.station_profile.set_command_flag("add_sta", "ieee80211w", 2)
            self.station_profile.set_command_flag("add_sta", "80211u_enable", 0)
            self.station_profile.set_command_flag("add_sta", "8021x_radius", 1)
            if not self.soft_roam:
                self.station_profile.set_command_flag("add_sta", "disable_roam", 1)
            elif config.option == "otds":
                self.station_profile.set_command_flag("add_sta", "ft-roam-over-ds", 1)
            self.station_profile.set_command_flag("add_sta", "power_save_enable", 1)
            self.station_profile.set_wifi_extra(
                key_mgmt="FT-EAP",
                pairwise="[BLANK]",
                group="[BLANK]",
                psk="[BLANK]",
                eap="TTLS",
                identity=config.identity,
                passwd=config.ttls_pass,
                pin="",
                phase1="NA",
                phase2="NA",
                pac_file="NA",
                private_key="NA",
                pk_password="NA",
                hessid="00:00:00:00:00:01",
                realm="localhost.localdomain",
                client_cert="NA",
                imsi="NA",
                milenage="NA",
                domain="localhost.localdomain",
                roaming_consortium="NA",
                venue_group="NA",
                network_type="NA",
                ipaddr_type_avail="NA",
                network_auth_type="NA",
                anqp_3gpp_cell_net="NA",
            )

        self.station_profile.create(radio=config.radio, sta_names_=list(station_names))
        self.wait_until_ports_appear(sta_list=list(station_names), debug_=False)

        self.apply_bgscan_to_stations(station_names)

        self.station_profile.admin_up()
        if self.wait_for_ip(list(station_names), timeout_sec=600):
            logger.info("All created stations received IPs")
            return True
        logger.error("Created stations failed to receive IPs")
        return False

    def create_station_configs(
        self,
        station_configs: Sequence[StationConfig],
        start_id: int,
        replace_stations: bool,
    ) -> List[str]:
        station_names: List[str] = []
        next_id = start_id
        for config in station_configs:
            end_id = next_id + config.num_sta - 1
            names = LFUtils.port_name_series(
                prefix="sta",
                start_id=next_id,
                end_id=end_id,
                padding_number=10000,
                radio=config.radio,
            )
            if replace_stations:
                self.pre_cleanup_stations(names)
            if not self.create_clients(config, names):
                raise RuntimeError(f"Failed creating stations on {config.radio}")
            station_names.extend(names)
            next_id = end_id + 1
        self.station_list = station_names
        return station_names

    def record_roam_row(self, row: Dict[str, object]) -> None:
        self.roam_rows.append(row)

    def perform_pair_roam(self, cycle: int, pair_index: int, active: str, passive: str) -> None:
        self.set_pair_start(active, passive)
        before = self.wait_for_station_bssids(self.station_list)
        transitioned = set()

        for step_index, (active_val, passive_val) in enumerate(zip(self.increments, self.decrements), start=1):
            logger.info(
                "Cycle %s pair %s step %s: %s=%.1f dB, %s=%.1f dB",
                cycle,
                pair_index,
                step_index,
                active,
                ddb_to_db(active_val),
                passive,
                ddb_to_db(passive_val),
            )
            self.set_atten(active, active_val)
            self.set_atten(passive, passive_val)
            print(f"wait for {self.step_wait} seconds After setting attenuators {active} and {passive}")
            time.sleep(self.step_wait)
            current = self.current_station_bssids(self.station_list)

            for station in self.station_list:
                before_bssid = str(before.get(station, ""))
                current_bssid = str(current.get(station, ""))
                if station in transitioned:
                    continue
                if not invalid_bssid(current_bssid) and current_bssid != before_bssid:
                    transitioned.add(station)
                    self.record_roam_row(
                        {
                            "cycle": cycle,
                            "pair_index": pair_index,
                            "active_attenuator": active,
                            "passive_attenuator": passive,
                            "step_index": step_index,
                            "active_attenuation_db": ddb_to_db(active_val),
                            "passive_attenuation_db": ddb_to_db(passive_val),
                            "station": station,
                            "before_bssid": before_bssid,
                            "after_bssid": current_bssid,
                            "signal": self.get_signal(station),
                            "status": "PASS",
                            "timestamp": datetime.now().isoformat(timespec="seconds"),
                        }
                    )

        final = self.current_station_bssids(self.station_list)
        for station in self.station_list:
            if station in transitioned:
                continue
            self.record_roam_row(
                {
                    "cycle": cycle,
                    "pair_index": pair_index,
                    "active_attenuator": active,
                    "passive_attenuator": passive,
                    "step_index": "",
                    "active_attenuation_db": ddb_to_db(self.max_attenuation_ddb),
                    "passive_attenuation_db": 0.0,
                    "station": station,
                    "before_bssid": before.get(station, ""),
                    "after_bssid": final.get(station, ""),
                    "signal": self.get_signal(station),
                    "status": "FAIL",
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                }
            )

    def _set_atten_modules(self, serial: str, value: int, modules: List[int]) -> None:
        """Set attenuation; modules is 1-based user input converted to 0-based API index. Empty = all."""
        if not modules:
            self.set_atten(serial, value)
        else:
            for mod in modules:
                self.set_atten(serial, value, atten_idx=mod - 1)

    def perform_directed_roam(
        self,
        cycle: int,
        source_serial: str,
        target_serial: str,
        source_steps: List[int],
        target_steps: List[int],
        source_ap: str,
        target_ap: str,
        source_modules: Optional[List[int]] = None,
        target_modules: Optional[List[int]] = None,
        target_ap_macs: Optional[set] = None,
    ) -> None:
        before = self.wait_for_station_bssids(self.station_list)
        transitioned: set = set()
        if target_ap_macs:
            tgt_macs: set = target_ap_macs
        elif target_ap:
            m = normalize_mac(target_ap)
            tgt_macs = {m} if m else set()
        else:
            tgt_macs = set()

        for step_index, (src_val, tgt_val) in enumerate(zip(source_steps, target_steps), start=1):
            logger.info(
                "Cycle %s step %s/%s: source-AP(%s)=%.1f dB  target-AP(%s)=%.1f dB",
                cycle, step_index, len(source_steps),
                source_serial, ddb_to_db(src_val),
                target_serial, ddb_to_db(tgt_val),
            )
            self._set_atten_modules(source_serial, src_val, source_modules or [])
            self._set_atten_modules(target_serial, tgt_val, target_modules or [])
            time.sleep(self.step_wait)
            current = self.current_station_bssids(self.station_list)

            for station in self.station_list:
                if station in transitioned:
                    continue
                before_bssid = str(before.get(station, ""))
                current_bssid = str(current.get(station, ""))
                if not invalid_bssid(current_bssid) and current_bssid != before_bssid:
                    transitioned.add(station)
                    roamed_to_target = (normalize_mac(current_bssid) in tgt_macs) if tgt_macs else True
                    self.record_roam_row({
                        "cycle": cycle,
                        "step_index": step_index,
                        "source_ap": source_ap,
                        "target_ap": target_ap,
                        "source_attenuator": source_serial,
                        "target_attenuator": target_serial,
                        "source_attenuation_db": ddb_to_db(src_val),
                        "target_attenuation_db": ddb_to_db(tgt_val),
                        "station": station,
                        "before_bssid": before_bssid,
                        "after_bssid": current_bssid,
                        "signal": self.get_signal(station),
                        "status": "PASS" if roamed_to_target else "WRONG_AP",
                        "timestamp": datetime.now().isoformat(timespec="seconds"),
                    })

        final = self.current_station_bssids(self.station_list)
        for station in self.station_list:
            if station in transitioned:
                continue
            self.record_roam_row({
                "cycle": cycle,
                "step_index": "",
                "source_ap": source_ap,
                "target_ap": target_ap,
                "source_attenuator": source_serial,
                "target_attenuator": target_serial,
                "source_attenuation_db": ddb_to_db(source_steps[-1]),
                "target_attenuation_db": ddb_to_db(target_steps[-1]),
                "station": station,
                "before_bssid": before.get(station, ""),
                "after_bssid": final.get(station, ""),
                "signal": self.get_signal(station),
                "status": "FAIL",
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            })

    def run_cycles(
        self,
        cycles: int,
        capture_duration: Optional[int],
        source_serial: Optional[str] = None,
        target_serial: Optional[str] = None,
        source_steps: Optional[List[int]] = None,
        target_steps: Optional[List[int]] = None,
        source_ap: str = "",
        target_ap: str = "",
        source_ap_macs: Optional[set] = None,
        target_ap_macs: Optional[set] = None,
        source_modules: Optional[List[int]] = None,
        target_modules: Optional[List[int]] = None,
    ) -> None:
        directed = bool(source_serial and target_serial and source_steps and target_steps)

        self.ensure_output_dir()
        self.validate_attenuators()
        self.configure_sniffers()
        run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.remote_run_dir = f"{self.remote_capture_dir}/run_{run_ts}"
        os.makedirs(self.remote_run_dir, exist_ok=True)
        os.chmod(self.remote_run_dir, 0o777)
        logger.info("Capture run folder: %s", self.remote_run_dir)

        if directed:
            estimated = 2 * len(source_steps) * self.step_wait + self.settle_time + 10
        else:
            estimated = self.estimated_cycle_seconds()
        if capture_duration is not None and capture_duration < estimated:
            logger.warning(
                "Capture duration %ss is shorter than estimated cycle time %ss; captures may end before roam completes.",
                capture_duration,
                estimated,
            )
        duration = capture_duration or estimated

        try:
            for cycle in range(1, cycles + 1):
                logger.info("Starting cycle %s/%s", cycle, cycles)
                cycle_started = time.time()
                self.configure_initial_attenuators()

                if directed:
                    time.sleep(self.settle_time)
                    src_macs = source_ap_macs or ({normalize_mac(source_ap)} if source_ap else set())
                    if src_macs:
                        logger.info(
                            "Cycle %s: waiting for all stations to connect to source AP %s",
                            cycle, sorted(src_macs),
                        )
                        deadline = time.time() + self.bssid_timeout
                        wrong: Dict[str, str] = {}
                        while True:
                            bssids = self.wait_for_station_bssids(self.station_list)
                            wrong = {
                                sta: bssid
                                for sta, bssid in bssids.items()
                                if normalize_mac(bssid) not in src_macs
                            }
                            if not wrong:
                                logger.info("Cycle %s: all stations are on source AP", cycle)
                                break
                            if time.time() >= deadline:
                                pretty = ", ".join(f"{sta}={bssid}" for sta, bssid in wrong.items())
                                expected = ", ".join(sorted(src_macs))
                                raise RuntimeError(
                                    f"Cycle {cycle}: station(s) did not connect to source AP "
                                    f"within {self.bssid_timeout}s. "
                                    f"Expected one of [{expected}], got: {pretty}"
                                )
                            logger.info(
                                "Cycle %s: station(s) not yet on source AP, retrying: %s",
                                cycle, {sta: bssid for sta, bssid in wrong.items()},
                            )
                            time.sleep(5)

                self.verify_ap_bssids(self.station_list, cycle)
                label = "source_to_target" if directed else "cycle"
                self.start_cycle_captures(cycle, duration, label=label)

                if directed:
                    self.perform_directed_roam(
                        cycle, source_serial, target_serial,
                        source_steps, target_steps, source_ap, target_ap,
                        source_modules=source_modules,
                        target_modules=target_modules,
                        target_ap_macs=target_ap_macs,
                    )
                    print(f"wait for {self.step_wait} seconds before returning to source AP")
                    time.sleep(self.step_wait)
                    # Return leg: roam back from target AP to source AP
                    self.perform_directed_roam(
                        cycle, target_serial, source_serial,
                        list(reversed(target_steps)), list(reversed(source_steps)),
                        target_ap, source_ap,
                        source_modules=target_modules,
                        target_modules=source_modules,
                        target_ap_macs=source_ap_macs,
                    )
                    print(f"wait for {self.step_wait} seconds after returning to source AP")
                    time.sleep(self.step_wait)
                else:
                    for pair_index, (active, passive) in enumerate(self.attenuator_pairs, start=1):
                        self.perform_pair_roam(cycle, pair_index, active, passive)

                elapsed = time.time() - cycle_started
                remaining = duration - int(elapsed)
                if remaining > 0:
                    # logger.info("Waiting %ss for cycle capture(s) to finish", remaining)
                    time.sleep(remaining + 2)
                for fname in os.listdir(self.remote_run_dir):
                    if fname.endswith(".pcap"):
                        try:
                            os.chmod(os.path.join(self.remote_run_dir, fname), 0o644)
                        except OSError:
                            pass
                self.write_outputs()
                logger.info("Cycle %s complete", cycle)
        finally:
            self.cleanup_sniffers()

    def write_outputs(self) -> None:
        capture_csv = os.path.join(self.output_dir, "capture_files.csv")
        roam_csv = os.path.join(self.output_dir, "roam_events.csv")
        summary_json = os.path.join(self.output_dir, "roam_cycle_summary.json")

        if self.capture_rows:
            with open(capture_csv, "w", newline="", encoding="utf-8") as handle:
                fieldnames = list(self.capture_rows[0].keys())
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.capture_rows)

        if self.roam_rows:
            with open(roam_csv, "w", newline="", encoding="utf-8") as handle:
                fieldnames = list(self.roam_rows[0].keys())
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.roam_rows)

        pass_count = sum(1 for row in self.roam_rows if row.get("status") == "PASS")
        fail_count = sum(1 for row in self.roam_rows if row.get("status") == "FAIL")
        summary = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "lanforge": {"host": self.host, "port": self.port},
            "stations": self.station_list,
            "sniffers": [cfg.__dict__ for cfg in self.sniffer_configs],
            "attenuators": {
                serial: {"initial_db": ddb_to_db(value)}
                for serial, value in self.attenuator_initials.items()
            },
            "capture_files_csv": capture_csv,
            "roam_events_csv": roam_csv,
            "remote_capture_files": [row["remote_pcap"] for row in self.capture_rows],
            "roam_status": {"pass": pass_count, "fail": fail_count},
        }
        with open(summary_json, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)


def build_station_configs(args: argparse.Namespace) -> List[StationConfig]:
    if args.station_config:
        return [parse_station_config(value, args) for value in args.station_config]

    if args.station_list:
        return []

    missing = []
    for attr in ["ssid", "security", "num_sta"]:
        if getattr(args, attr) in (None, ""):
            missing.append(f"--{attr.replace('_', '-')}")
    password = args.password
    if args.security and str(args.security).lower() in {"open", "owe"} and not password:
        password = "[BLANK]"
    elif not password:
        missing.append("--password")
    if missing:
        raise argparse.ArgumentTypeError(
            "Creating stations requires " + ", ".join(missing) + " or use --station-list for existing stations."
        )

    return [
        StationConfig(
            radio=args.station_radio,
            ssid=args.ssid,
            security=args.security,
            password=password,
            num_sta=args.num_sta,
            station_flag=args.station_flag,
            sta_type=args.sta_type,
            option=args.option,
            identity=args.identity,
            ttls_pass=args.ttls_pass,
        )
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lanforge_roam_cycle.py",
        description="Configure LANforge sniffers/attenuators and run roaming capture cycles.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("--mgr", default="localhost", help="LANforge manager host/IP")
    parser.add_argument("--port", type=int, default=8080, help="LANforge manager HTTP port")

    parser.add_argument(
        "--sniffer",
        action="append",
        default=[],
        help=(
            "Sniffer config. Repeat for multiple radios. Formats: "
            "1.1.wiphy2:36[:5180[:20[:center_freq]]] or "
            "radio=1.1.wiphy2,channel=36,frequency=5180,bw=20,monitor=roammon0"
        ),
    )
    parser.add_argument("--sniff-radio", "--sniff_radio", default=None, help="Single sniffer radio, roam_Script.py style")
    parser.add_argument("--channel", default=None, help="Channel for --sniff-radio")
    parser.add_argument("--frequency", type=int, default=None, help="Frequency for --sniff-radio")
    parser.add_argument("--channel-bw", "--channel_bw", default="20", help="Channel width for --sniff-radio")
    parser.add_argument("--center-freq", "--center_freq", type=int, default=None, help="Center frequency for --sniff-radio")
    parser.add_argument("--monitor-name", "--monitor_name", default="roammon1", help="Monitor name for --sniff-radio")
    parser.add_argument(
        "--capture-duration",
        "--capture_duration",
        "--sniff-duration",
        "--sniff_duration",
        type=parse_duration_seconds,
        default=None,
        help="Packet capture duration per cycle. If omitted, script estimates it from roam steps.",
    )
    parser.add_argument("--capture-filter", default=None, help="Optional dumpcap capture filter for sniffer captures")
    parser.add_argument(
        "--remote-capture-dir",
        "--remote_capture_dir",
        default=DEFAULT_REMOTE_CAPTURE_DIR,
        help="Directory on the LANforge system where pcap files are written (default: %(default)s).",
    )
    parser.add_argument("--output-dir", "--output_dir", default="lanforge_roam_cycle_results", help="Local metadata output directory")
    parser.add_argument("--keep-monitors", action="store_true", help="Leave created monitor ports after the run")

    parser.add_argument(
        "--attenuator",
        action="append",
        default=[],
        help="Attenuator serial and initial attenuation, e.g. 1.1.84=0. Repeat or comma-separate.",
    )
    parser.add_argument(
        "--attenuators",
        nargs="*",
        default=[],
        help="Attenuator serials using --initial-attenuation for missing values. Compatible with roam_Script.py style.",
    )
    parser.add_argument("--initial-attenuation", default="0", help="Initial attenuation for serials without a value")
    parser.add_argument("--attenuation-unit", choices=["db", "ddb"], default="db", help="Input attenuation unit")
    parser.add_argument("--max-attenuation", "--max_attenuation", default="95", help="Maximum attenuation in selected unit")
    parser.add_argument("--step", default="10", help="Attenuation step in selected unit")
    parser.add_argument("--step-wait", "--step_wait", "--wait-time", "--wait_time", type=int, default=10, help="Seconds to wait after each attenuation step")
    parser.add_argument("--settle-time", "--settle_time", type=int, default=5, help="Seconds to wait after preparing each roam pair")
    parser.add_argument(
        "--no-isolate-unused",
        dest="isolate_unused",
        action="store_false",
        help="Do not set non-pair test attenuators to max during a pair roam",
    )
    parser.set_defaults(isolate_unused=True)
    parser.add_argument(
        "--maximize-unused-attenuators",
        action="store_true",
        help="Set LANforge attenuators not listed for the test to max attenuation",
    )

    parser.add_argument("--cycles", "--iterations", type=int, default=1, help="Number of full attenuator-pair roam cycles")
    parser.add_argument(
        "--expected-bssid",
        action="append",
        default=[],
        help="Expected AP BSSID. Repeat, comma-separate, or use label=mac.",
    )
    parser.add_argument("--bssid-timeout", type=int, default=90, help="Seconds to wait for station BSSID information")

    station_group = parser.add_argument_group("Station creation / selection")
    station_group.add_argument(
        "--station-list",
        "--station_list",
        default="",
        help="Comma-separated existing station EIDs. If provided, station creation is skipped.",
    )
    station_group.add_argument("--station-radio", "--sta-radio", default="1.1.wiphy0", help="Radio for created stations")
    station_group.add_argument("--num-sta", "--num_sta", type=int, default=1, help="Number of stations to create")
    station_group.add_argument("--start-id", "--start_id", type=int, default=0, help="First station index for generated names")
    station_group.add_argument("--ssid", default=None, help="SSID for created stations")
    station_group.add_argument("--security", default=None, help="Security for created stations")
    station_group.add_argument("--password", "--passwd", default=None, help="Password for created stations")
    station_group.add_argument("--station-flag", "--station_flag", default=None, help="Comma-separated add_sta flags")
    station_group.add_argument(
        "--station-config",
        action="append",
        default=[],
        help=(
            "Per-radio station config. Example: "
            "radio==1.1.wiphy0,ssid==ROAM,passwd==lanforge,security==wpa2,num_sta==3,sta_type==11r"
        ),
    )
    station_group.add_argument("--sta-type", "--sta_type", default="11r", help="Created station type: normal, 11r, 11r-sae, 11r-sae-802.1x")
    station_group.add_argument("--option", default="ota", help="Roam option used by created stations, e.g. ota or otds")
    station_group.add_argument("--identity", default="testuser", help="802.1x identity for FT-EAP")
    station_group.add_argument("--ttls-pass", "--ttls_pass", default="testpasswd", help="802.1x TTLS password for FT-EAP")
    station_group.add_argument("--bg-scan", "--bg_scan", default="simple:15:-60:500:4", help="bgscan string for soft roaming")
    station_group.add_argument("--no-soft-roam", dest="soft_roam", action="store_false", help="Disable soft roam/bgscan config")
    station_group.add_argument("--disable-restart-dhcp", action="store_true", help="Set no DHCP restart flags on stations")
    station_group.add_argument("--cleanup-stations", action="store_true", help="Cleanup test stations after the run")
    station_group.add_argument("--replace-stations", dest="replace_stations", action="store_true", help="Remove generated station ports before create")
    station_group.add_argument("--no-replace-stations", dest="replace_stations", action="store_false", help="Do not remove generated station ports before create")
    parser.set_defaults(soft_roam=True, replace_stations=True)

    directed_group = parser.add_argument_group(
        "Directed roam",
        "Use these options to drive roaming between a specific source AP and target AP using "
        "independent attenuation sweeps. Stations are discovered from --radios instead of being created.",
    )
    directed_group.add_argument(
        "--ap-config",
        "--ap_config",
        default=None,
        metavar="FILE",
        help=(
            "Path to a JSON file specifying per-band BSSIDs for source and target APs. "
            "Keys under 'source' and 'target' may be '2g', '5g', and/or '6g'. "
            "Example: {\"source\": {\"2g\": \"AA:BB:CC:DD:EE:FF\", \"5g\": \"AA:BB:CC:DD:EE:01\"}, "
            "\"target\": {\"5g\": \"AA:BB:CC:DD:EE:10\"}}. "
            "When provided, overrides --source-ap and --target-ap for BSSID verification."
        ),
    )
    directed_group.add_argument(
        "--radios",
        default=None,
        help="Comma-separated radio EIDs whose existing stations are used (e.g. 1.1.wiphy0,1.1.wiphy1). "
             "Skips station creation. Takes priority over --station-list.",
    )
    directed_group.add_argument(
        "--source-ap", "--from-ap",
        dest="source_ap",
        default=None,
        help="BSSID of the AP stations start on (source). Used for cycle-start validation and roam tracking.",
    )
    directed_group.add_argument(
        "--target-ap",
        default=None,
        help="BSSID of the AP stations should roam to (target).",
    )
    directed_group.add_argument(
        "--source-ap-attenuator",
        default=None,
        metavar="SERIAL",
        help="Attenuator serial controlling the source AP signal (e.g. 1.1.84).",
    )
    directed_group.add_argument(
        "--target-ap-attenuator",
        default=None,
        metavar="SERIAL",
        help="Attenuator serial controlling the target AP signal.",
    )
    directed_group.add_argument(
        "--source-ap-atten-from",
        default="0",
        metavar="VALUE",
        help="Starting attenuation for source AP attenuator (typically 0 = strong signal).",
    )
    directed_group.add_argument(
        "--source-ap-atten-to",
        default="95",
        metavar="VALUE",
        help="Ending attenuation for source AP attenuator (typically 95 = weak signal).",
    )
    directed_group.add_argument(
        "--target-ap-atten-from",
        default="95",
        metavar="VALUE",
        help="Starting attenuation for target AP attenuator (typically 95 = weak signal).",
    )
    directed_group.add_argument(
        "--target-ap-atten-to",
        default="0",
        metavar="VALUE",
        help="Ending attenuation for target AP attenuator (typically 0 = strong signal).",
    )
    directed_group.add_argument(
        "--source-ap-modules",
        default=None,
        metavar="MODULES",
        help="Comma-separated 1-based module indices on the source AP attenuator (e.g. 1,2). "
             "Omit to apply to all modules.",
    )
    directed_group.add_argument(
        "--target-ap-modules",
        default=None,
        metavar="MODULES",
        help="Comma-separated 1-based module indices on the target AP attenuator (e.g. 1,2). "
             "Omit to apply to all modules.",
    )

    parser.add_argument("--log-level", default="INFO", help="Logging level")
    return parser


def configure_logging(level_name: str) -> None:
    level = getattr(logging, str(level_name).upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    configure_logging(args.log_level)

    try:
        sniffers = [parse_sniffer(value, index) for index, value in enumerate(args.sniffer, start=1)]
        if args.sniff_radio:
            if not args.channel:
                parser.error("--sniff-radio requires --channel")
            sniffers.append(
                SnifferConfig(
                    radio=args.sniff_radio,
                    channel=str(args.channel),
                    frequency=args.frequency,
                    bandwidth=str(args.channel_bw),
                    center_freq=args.center_freq,
                    monitor_name=args.monitor_name,
                )
            )
        if not sniffers:
            parser.error("Provide --sniffer or --sniff-radio with --channel.")

        attenuator_initials = build_attenuator_initials(args)

        # Directed roam setup
        source_serial: Optional[str] = args.source_ap_attenuator
        target_serial: Optional[str] = args.target_ap_attenuator
        directed = bool(source_serial and target_serial)
        source_steps: Optional[List[int]] = None
        target_steps: Optional[List[int]] = None
        source_modules: List[int] = parse_modules(args.source_ap_modules) if args.source_ap_modules else []
        target_modules: List[int] = parse_modules(args.target_ap_modules) if args.target_ap_modules else []

        max_attenuation_ddb = attenuation_to_ddb(args.max_attenuation, args.attenuation_unit)
        step_ddb = attenuation_to_ddb(args.step, args.attenuation_unit)
        if step_ddb <= 0:
            parser.error("--step must be greater than zero")

        if directed:
            src_from = attenuation_to_ddb(args.source_ap_atten_from, args.attenuation_unit)
            src_to = attenuation_to_ddb(args.source_ap_atten_to, args.attenuation_unit)
            tgt_from = attenuation_to_ddb(args.target_ap_atten_from, args.attenuation_unit)
            tgt_to = attenuation_to_ddb(args.target_ap_atten_to, args.attenuation_unit)
            source_steps = build_steps_by_size(src_from, src_to, step_ddb)
            target_steps = build_steps_by_size(tgt_from, tgt_to, step_ddb)
            # Ensure source and target attenuators are registered with their initial values
            if source_serial not in attenuator_initials:
                attenuator_initials[source_serial] = src_from
            if target_serial not in attenuator_initials:
                attenuator_initials[target_serial] = tgt_from
        elif not attenuator_initials:
            parser.error(
                "Provide at least two attenuators with --attenuator or --attenuators, "
                "or use --source-ap-attenuator and --target-ap-attenuator for directed roam."
            )

        if args.cycles <= 0:
            parser.error("--cycles must be greater than zero")

        expected_bssids = parse_expected_bssids(args.expected_bssid)
        station_configs = [] if args.radios else build_station_configs(args)

        # Resolve per-band AP BSSIDs: JSON config takes priority over single --source-ap/--target-ap
        source_ap_macs: set = set()
        target_ap_macs: set = set()
        if args.ap_config:
            source_by_band, target_by_band = load_ap_config(args.ap_config)
            source_ap_macs = {normalize_mac(mac) for mac in source_by_band.values() if normalize_mac(mac)}
            target_ap_macs = {normalize_mac(mac) for mac in target_by_band.values() if normalize_mac(mac)}
            logger.info(
                "Loaded AP config from '%s': source bands=%s, target bands=%s",
                args.ap_config,
                {band: mac for band, mac in source_by_band.items()},
                {band: mac for band, mac in target_by_band.items()},
            )
        else:
            if args.source_ap:
                m = normalize_mac(args.source_ap)
                if m:
                    source_ap_macs = {m}
            if args.target_ap:
                m = normalize_mac(args.target_ap)
                if m:
                    target_ap_macs = {m}
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
        return 2

    runner = None
    created_station_ports: List[str] = []

    try:
        runner = LanforgeRoamCycle(
            host=args.mgr,
            port=args.port,
            sniffers=sniffers,
            attenuator_initials=attenuator_initials,
            max_attenuation_ddb=max_attenuation_ddb,
            step_ddb=step_ddb,
            step_wait=args.step_wait,
            settle_time=args.settle_time,
            output_dir=args.output_dir,
            remote_capture_dir=args.remote_capture_dir,
            capture_filter=args.capture_filter,
            expected_bssids=expected_bssids,
            bssid_timeout=args.bssid_timeout,
            soft_roam=args.soft_roam,
            bg_scan=args.bg_scan,
            disable_restart_dhcp=args.disable_restart_dhcp,
            cleanup_monitors=not args.keep_monitors,
            isolate_unused=args.isolate_unused,
            maximize_unused_attenuators=args.maximize_unused_attenuators,
        )

        runner.ensure_output_dir()
        runner.validate_attenuators()
        runner.configure_initial_attenuators()

        if args.radios:
            radios = [r.strip() for r in args.radios.split(",") if r.strip()]
            runner.station_list = runner.discover_stations_on_radios(radios)
            if not runner.station_list:
                logger.error("No stations found on radio(s): %s", args.radios)
                return 1
            logger.info(
                "Using %s discovered station(s): %s",
                len(runner.station_list), ", ".join(runner.station_list),
            )
            runner.apply_bgscan_to_stations(runner.station_list)
            runner.reset_station_ports(runner.station_list)
        elif args.station_list:
            runner.station_list = [station.strip() for station in args.station_list.split(",") if station.strip()]
            if not runner.station_list:
                parser.error("--station-list did not contain any station EIDs")
            logger.info("Using existing stations: %s", ", ".join(runner.station_list))
            runner.apply_bgscan_to_stations(runner.station_list)
            runner.reset_station_ports(runner.station_list)
        else:
            created_station_ports = runner.create_station_configs(
                station_configs=station_configs,
                start_id=args.start_id,
                replace_stations=args.replace_stations,
            )

        runner.run_cycles(
            cycles=args.cycles,
            capture_duration=args.capture_duration,
            source_serial=source_serial if directed else None,
            target_serial=target_serial if directed else None,
            source_steps=source_steps,
            target_steps=target_steps,
            source_ap=args.source_ap or "",
            target_ap=args.target_ap or "",
            source_ap_macs=source_ap_macs or None,
            target_ap_macs=target_ap_macs or None,
            source_modules=source_modules if directed else None,
            target_modules=target_modules if directed else None,
        )

        logger.info("Results written under %s", os.path.abspath(args.output_dir))
        return 0
    except Exception as exc:
        logger.exception("Roam cycle failed: %s", exc)
        return 1
    finally:
        if args.cleanup_stations and created_station_ports and runner is not None:
            try:
                runner.pre_cleanup_stations(created_station_ports)
            except Exception as exc:
                logger.warning("Station cleanup failed: %s", exc)


if __name__ == "__main__":
    sys.exit(main())
