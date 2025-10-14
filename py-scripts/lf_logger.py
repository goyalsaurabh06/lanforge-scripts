#!/usr/bin/env python3
"""
lf_logger.py — Dual-output logger
---------------------------------
Captures all stdout/stderr/logging to a file,
while still mirroring live output to the console.
"""

import sys
import os
import logging
import datetime
import signal
import atexit
import threading
import time

log_file = None
log_fh = None
_stop_flush_thread = False


class TeeStream:
    """Writes output to both terminal and log file."""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            try:
                s.write(data)
                s.flush()
            except Exception:
                pass

    def flush(self):
        for s in self.streams:
            try:
                s.flush()
            except Exception:
                pass


def _auto_flush():
    """Periodically flush log file to disk."""
    while not _stop_flush_thread:
        try:
            if log_fh and not log_fh.closed:
                log_fh.flush()
                os.fsync(log_fh.fileno())
        except Exception:
            pass
        time.sleep(5)


def start(log_dir="test_logs", level=logging.INFO, rotate_daily=True):
    """Start logging to file + console."""
    global log_file, log_fh, _stop_flush_thread

    os.makedirs(log_dir, exist_ok=True)
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    log_name = f"log_{date_str}.log" if rotate_daily else f"log_{date_str}_{int(time.time())}.log"
    log_file = os.path.join(log_dir, log_name)

    log_fh = open(log_file, "a", buffering=1)

    # Save original stdout/stderr
    original_stdout = sys.__stdout__
    original_stderr = sys.__stderr__

    # Tee stdout/stderr -> both console and log
    sys.stdout = TeeStream(original_stdout, log_fh)
    sys.stderr = TeeStream(original_stderr, log_fh)

    # Configure logging
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    atexit.register(stop)
    signal.signal(signal.SIGINT, handle_interrupt)
    signal.signal(signal.SIGTERM, handle_interrupt)

    print(f"[lf_logger] Logging started: {log_file}\n")

    # Background flusher
    _stop_flush_thread = False
    threading.Thread(target=_auto_flush, daemon=True).start()


def stop():
    """Stop and flush safely."""
    global _stop_flush_thread
    _stop_flush_thread = True
    flush()
    if log_fh and not log_fh.closed:
        log_fh.close()
    print("[lf_logger] Logging stopped.")


def flush():
    """Force flush to disk."""
    try:
        if log_fh and not log_fh.closed:
            log_fh.flush()
            os.fsync(log_fh.fileno())
    except Exception:
        pass


def handle_interrupt(sig, frame):
    print("\n[lf_logger] Interrupted. Flushing logs before exit...")
    stop()
    sys.exit(1)


def get_log_file():
    return log_file
