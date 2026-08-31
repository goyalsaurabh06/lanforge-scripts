#!/usr/bin/env python3
"""
NAME: lf_wifi_msgs.py

PURPOSE:
    Fetch LANforge Wi-Fi messages from the GUI REST API (/wifi-msgs): the last or
    first N messages, everything since a time-stamp, everything from the last
    <duration>, everything between two stamps, or keep printing new messages as
    they arrive.

EXAMPLE:
    python3 lf_wifi_msgs.py --mgr 192.168.1.31 --last 50
    python3 lf_wifi_msgs.py --mgr 192.168.1.31 --duration 5m --output json --outfile msgs.json
    python3 lf_wifi_msgs.py --mgr 192.168.1.31 --since 1699999999999 --output json
    python3 lf_wifi_msgs.py --mgr 192.168.1.31 --between 1788159332090 1788161286054
    python3 lf_wifi_msgs.py --mgr 192.168.1.31 --poll --interval 2s

    # importable
    from lf_wifi_msgs import WifiMessages
    wifi_msgs = WifiMessages(host="192.168.1.31")
    for entry in wifi_msgs.last(50):
        print(entry["time-stamp"], entry["resource"], entry["text"])
    for entry in wifi_msgs.poll(interval=2):   # stop with break / wifi_msgs.stop_polling()
        handle(entry)

NOTES:
    LANforge time-stamps are epoch milliseconds. --since / --between values are
    sent through unchanged; --duration is computed off the newest message.

SCRIPT_CLASSIFICATION: Reporting, Wi-Fi Messages

SCRIPT_CATEGORIES: Functional

STATUS: Functional

COPYRIGHT:
Copyright (C) 2020-2026 Candela Technologies Inc
License: Free to distribute and modify. LANforge systems must be licensed.

INCLUDE_IN_README: False
"""
import sys
import os
import importlib
import argparse
import json
import re
import time
import threading
import logging
from typing import Callable, Iterator, List, Optional

logger = logging.getLogger(__name__)
if sys.version_info[0] != 3:
    logger.critical("This script requires Python 3")
    exit(1)

sys.path.append(os.path.join(os.path.abspath(__file__ + "../../../")))

lfcli_base = importlib.import_module("py-json.LANforge.lfcli_base")
LFCliBase = lfcli_base.LFCliBase
realm = importlib.import_module("py-json.realm")
Realm = realm.Realm
lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")

RETRY_TIMEOUT = 40      # seconds to keep retrying a /wifi-msgs GET that returns nothing
RETRY_INTERVAL = 5      # seconds between those retries
POLL_INTERVAL = 5       # default seconds between polls in poll()


class WifiMessages(Realm):
    """Query the LANforge ``/wifi-msgs`` REST endpoints."""

    def __init__(self, host: Optional[str] = None, port: int = 8080, debug: bool = False,
                 retry_timeout: int = RETRY_TIMEOUT, retry_interval: int = RETRY_INTERVAL) -> None:
        super().__init__(host, port, debug_=debug)
        self.debug = debug
        self.retry_timeout = retry_timeout
        self.retry_interval = retry_interval
        self._poll_stop = threading.Event()   # set by stop_polling(), watched by poll()

    # helpers
    @staticmethod
    def flatten(response: Optional[dict]) -> List[dict]:
        """Flatten a /wifi-msgs response body into a list of entry dicts.

        LANforge returns ``wifi-messages`` as a bare entry, a ``{'<key>': {entry}}``
        wrapper, or a list of either; this returns a plain list of the entry dicts
        (each has ``resource``, ``text``, ``time-stamp``). Missing/empty -> [].
        """
        messages = (response or {}).get("wifi-messages")
        if messages is None:
            return []
        items = messages if isinstance(messages, list) else [messages]
        out = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if "text" in item or "time-stamp" in item:
                out.append(item)
            else:
                out.extend(v for v in item.values() if isinstance(v, dict))
        return out

    @staticmethod
    def timestamp_ms(entry: dict) -> Optional[int]:
        """The entry's ``time-stamp`` as an int, or None if missing/non-numeric."""
        try:
            return int(str(entry.get("time-stamp") or entry.get("timestamp")).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def to_seconds(text: str) -> float:
        """'30s' / '5m' / '2h' / '500ms' / bare number -> float seconds."""
        match = re.match(r"^\s*(\d+(?:\.\d+)?)\s*(ms|s|m|h|d)?\s*$", str(text), re.IGNORECASE)
        if not match:
            raise ValueError("invalid duration {!r}; use e.g. 30s, 5m, 2h, 500ms".format(text))
        units = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400}
        return float(match.group(1)) * units[(match.group(2) or "s").lower()]

    def get_wifi_messages(self, uri: str) -> List[dict]:
        """GET ``uri`` (retrying while the response is empty), return the flattened entries."""
        start = time.time()
        response = self.json_get(uri, debug_=self.debug)
        while response is None and (time.time() - start) < self.retry_timeout:
            logger.warning("GET %s returned nothing from LANforge; retrying", uri)
            time.sleep(self.retry_interval)
            response = self.json_get(uri, debug_=self.debug)
        if response is None:
            logger.error("GET %s returned nothing after %ss", uri, self.retry_timeout)
        return self.flatten(response)

    # ---- queries ----------------------------------------------------------
    def last(self, count: int = 1) -> List[dict]:
        return self.get_wifi_messages("/wifi-msgs/last/{}".format(int(count)))

    def first(self, count: int = 1) -> List[dict]:
        return self.get_wifi_messages("/wifi-msgs/first/{}".format(int(count)))

    def since(self, timestamp: int) -> List[dict]:
        return self.get_wifi_messages("/wifi-msgs/since=time/{}".format(timestamp))

    def between(self, start: int, end: int) -> List[dict]:
        return self.get_wifi_messages("/wifi-msgs/between=time/{}/{}".format(start, end))

    def duration(self, seconds: float) -> List[dict]:
        """Messages from the last ``seconds``: newest message's stamp minus the
        window, via since=time. Falls back to last=time with no baseline."""
        window_ms = int(float(seconds) * 1000)
        latest = self.last(1)
        base_ms = self.timestamp_ms(latest[-1]) if latest else None
        if base_ms is None:
            logger.warning("No epoch-ms wifi-msg baseline available; using /wifi-msgs/last=time")
            return self.get_wifi_messages("/wifi-msgs/last=time/{}".format(window_ms))
        return self.since(base_ms - window_ms)

    # ---- poll -----------------------------------------------------------
    def stop_polling(self) -> None:
        """Ask a running `poll()` to stop; safe from another thread, the loop
        body, or a signal handler. Cleared on the next `poll()` entry."""
        self._poll_stop.set()

    def poll(self, interval: float = POLL_INTERVAL, since_ts: Optional[int] = None,
             stop: Optional[Callable[[], bool]] = None) -> Iterator[dict]:
        """Yield each new /wifi-msgs entry as it appears.

        Open-ended generator; never prints. Stop it with ``break``,
        `stop_polling()`, or a ``stop`` predicate. ``since_ts`` is the
        epoch-ms cursor (default: the newest message at entry, so only new
        traffic is yielded; 0 if the buffer is empty).
        """
        self._poll_stop.clear()
        if since_ts is None:
            latest = self.last(1)
            since_ts = self.timestamp_ms(latest[-1]) if latest else 0
        cursor = int(since_ts)
        while not self._poll_stop.is_set() and not (stop and stop()):
            batch = self.since(cursor + 1)   # +1: since=time is inclusive
            for entry in sorted(batch, key=lambda e: self.timestamp_ms(e) or 0):
                yield entry
                ts = self.timestamp_ms(entry)
                if ts:
                    cursor = max(cursor, ts)
            if self._poll_stop.wait(interval):
                return

    # output
    @staticmethod
    def render(entries: List[dict], output: str, stream) -> None:
        """Write ``entries`` to ``stream`` as 'raw' text lines or a 'json' array."""
        if output == "json":
            json.dump(entries, stream, indent=2)
            stream.write("\n")
            return
        for entry in entries:
            text = entry.get("text", [])
            for line in (text if isinstance(text, list) else [text]):
                stream.write("{}\n".format(line))


def main() -> None:
    help_summary = ("Fetch LANforge Wi-Fi messages from the /wifi-msgs REST API: last/first N, since a "
                    "time-stamp, from the last <duration>, between two stamps, or poll for new ones. "
                    "Importable as WifiMessages.")

    parser = LFCliBase.create_basic_argparse(
        prog='lf_wifi_msgs.py',
        formatter_class=argparse.RawTextHelpFormatter,
        description=__doc__)

    wifi_msgs_args = parser.add_argument_group('wifi-msgs arguments')
    mode = wifi_msgs_args.add_mutually_exclusive_group()
    mode.add_argument('--last', type=int, metavar='N', help='the most recent N messages (default: 25)')
    mode.add_argument('--first', type=int, metavar='N', help='the oldest N messages still buffered')
    mode.add_argument('--since', metavar='TIMESTAMP', help='every message since a LANforge epoch-ms time-stamp')
    mode.add_argument('--duration', metavar='WINDOW', help='every message from the last WINDOW (e.g. 30s, 5m, 2h)')
    mode.add_argument('--between', nargs=2, type=int, metavar=('START', 'END'),
                      help='every message between two epoch-ms stamps')
    mode.add_argument('--poll', '-p', action='store_true',
                      help='print new messages as they arrive (Ctrl-C to stop)')
    wifi_msgs_args.add_argument('--interval', default='5s', metavar='WINDOW',
                                help='--poll interval (e.g. 2s, 500ms; default: 5s)')
    wifi_msgs_args.add_argument('--output', choices=['raw', 'json'], default='raw',
                                help='raw message text lines or json (default: raw)')
    wifi_msgs_args.add_argument('--outfile', metavar='PATH', help='write output to PATH instead of stdout')

    args = parser.parse_args()
    if args.help_summary:
        print(help_summary)
        exit(0)

    try:
        interval = WifiMessages.to_seconds(args.interval)
        duration = WifiMessages.to_seconds(args.duration) if args.duration is not None else None
    except Exception as error:
        parser.error(f"Failed to parse the CLI arguments: {str(error)}")

    logger_config = lf_logger_config.lf_logger_config()
    logger_config.set_level(level=args.log_level)
    logger_config.set_json(json_file=args.lf_logger_config_json)

    wifi_msgs = WifiMessages(host=args.mgr, port=args.mgr_port, debug=args.debug)
    out_stream = open(args.outfile, 'w') if args.outfile else sys.stdout
    try:
        if args.poll:
            print("Polling /wifi-msgs (Ctrl-C to stop)", file=sys.stderr)
            try:
                for entry in wifi_msgs.poll(interval=interval):
                    wifi_msgs.render([entry], args.output, out_stream)
                    out_stream.flush()
            except KeyboardInterrupt:
                wifi_msgs.stop_polling()
                print("Polling stopped", file=sys.stderr)
        else:
            if args.since is not None:
                entries = wifi_msgs.since(args.since)
            elif duration is not None:
                entries = wifi_msgs.duration(duration)
            elif args.between is not None:
                entries = wifi_msgs.between(*sorted(args.between))
            elif args.first is not None:
                entries = wifi_msgs.first(args.first)
            else:
                entries = wifi_msgs.last(args.last if args.last is not None else 25)
            logger.debug("Fetched %d wifi message(s)", len(entries))
            wifi_msgs.render(entries, args.output, out_stream)
    finally:
        if out_stream is not sys.stdout:
            out_stream.close()
    exit(0)


if __name__ == "__main__":
    main()
