import threading
import subprocess
import os
import logging
import argparse
import time
import json
from datetime import datetime, timezone
import jc


class PingMonitor:
    def __init__(self, participant_name):
        self.participant_name = participant_name
        self.process = None
        self.ping_logger = self._create_ping_logger()
        self.reader_thread = None
        self.stop_event = threading.Event()

        # JSONL output lives next to the existing .log
        log_dir = os.path.join(os.getcwd(), "zoom_mobile_logs")
        os.makedirs(log_dir, exist_ok=True)
        self.jsonl_path = os.path.join(log_dir, f"{participant_name}_ping.jsonl")

        self._jsonl_fp = None
        self._records = []  # jc records (replies/timeouts) collected for summary
        self._write_lock = threading.Lock()

    def _create_ping_logger(self):
        """Create a logger specifically for ping output"""
        log_dir = os.path.join(os.getcwd(), "zoom_mobile_logs")
        os.makedirs(log_dir, exist_ok=True)

        logger_name = f"ping.{self.participant_name}"
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        logger.propagate = False

        # Clear existing handlers to avoid duplicates
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        formatter = logging.Formatter("%(asctime)s - %(message)s")
        file_handler = logging.FileHandler(
            os.path.join(log_dir, f"{self.participant_name}_ping.log"), mode="w"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        return logger

    def start_ping(self, device_serial, target_host="8.8.8.8"):
        """Start ping subprocess in background"""
        if not device_serial:
            self.ping_logger.error(
                "Failed to start ping subprocess: missing device serial"
            )
            return

        try:
            self.stop_event.clear()
            self._records = []
            self._jsonl_fp = open(self.jsonl_path, "w", buffering=1)

            # `-tt` allocates a PTY on the device so ping line-buffers its
            # output. `-D` adds device-side epoch timestamps; `-O` reports
            # timeouts as they happen; `-n` skips reverse DNS.
            self.process = subprocess.Popen(
                [
                    "adb",
                    "-s",
                    device_serial,
                    "shell",
                    "-tt",
                    "ping",
                    "-D",
                    "-O",
                    "-n",
                    target_host,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered on the Python side
            )

            # Start thread to read ping output
            self.reader_thread = threading.Thread(
                target=self._read_ping_output, daemon=True
            )
            self.reader_thread.start()
            self.ping_logger.info(
                f"Ping monitor started on device {device_serial} for {target_host}"
            )
        except Exception as e:
            self.ping_logger.error(f"Failed to start ping subprocess: {e}")
            self._close_jsonl()

    def _close_jsonl(self):
        with self._write_lock:
            if self._jsonl_fp:
                try:
                    self._jsonl_fp.flush()
                    self._jsonl_fp.close()
                except Exception:
                    pass
                self._jsonl_fp = None

    def _write_record(self, record):
        host_ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        out = {"host_ts": host_ts, **record}
        with self._write_lock:
            self._records.append(record)
            if self._jsonl_fp:
                self._jsonl_fp.write(json.dumps(out) + "\n")

    def _line_iter(self):
        """Yield raw ping lines, mirroring each one to the .log file."""
        try:
            while not self.stop_event.is_set() and self.process:
                line = self.process.stdout.readline()
                if not line:
                    break
                # PTY converts \n to \r\n; strip both.
                clean = line.rstrip("\r\n")
                self.ping_logger.info(clean)
                yield clean
        except Exception as e:
            self.ping_logger.error(f"Error reading ping output: {e}")

    def _read_ping_output(self):
        """Stream ping output through `jc` and persist structured rows."""
        try:
            # jc.parse('ping_s', ...) yields one dict per reply / timeout.
            for record in jc.parse("ping_s", self._line_iter()):
                self._write_record(record)
        except Exception as e:
            self.ping_logger.error(f"Error parsing ping output via jc: {e}")

    def _emit_summary(self):
        """Compute a summary from collected jc records and append to JSONL."""
        if not self._records:
            return

        replies = [r for r in self._records if r.get("type") == "reply"]
        timeouts = [r for r in self._records if r.get("type") == "timeout"]
        rtts = [r["time_ms"] for r in replies if r.get("time_ms") is not None]
        seqs = [r["icmp_seq"] for r in self._records if r.get("icmp_seq") is not None]

        transmitted = max(seqs) if seqs else len(replies) + len(timeouts)
        received = len(replies)
        loss_count = max(transmitted - received, 0)
        loss_rate = (loss_count / transmitted * 100.0) if transmitted else 0.0

        if rtts:
            rtt_min = min(rtts)
            rtt_max = max(rtts)
            rtt_avg = sum(rtts) / len(rtts)
            # Mean absolute deviation (proxy for iputils 'mdev').
            rtt_mdev = sum(abs(x - rtt_avg) for x in rtts) / len(rtts)
        else:
            rtt_min = rtt_max = rtt_avg = rtt_mdev = None

        destination = next(
            (r.get("response_ip") for r in replies if r.get("response_ip")),
            None,
        )
        summary = {
            "type": "summary",
            "destination": destination,
            "packet_transmit": transmitted,
            "packet_receive": received,
            "packet_loss_count": loss_count,
            "packet_loss_rate": round(loss_rate, 3),
            "rtt_min_ms": rtt_min,
            "rtt_avg_ms": round(rtt_avg, 3) if rtt_avg is not None else None,
            "rtt_max_ms": rtt_max,
            "rtt_mdev_ms": round(rtt_mdev, 3) if rtt_mdev is not None else None,
        }

        try:
            host_ts = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
            with open(self.jsonl_path, "a") as fp:
                fp.write(json.dumps({"host_ts": host_ts, **summary}) + "\n")
        except Exception as e:
            self.ping_logger.error(f"Failed to write summary record: {e}")
        self.ping_logger.info(f"Summary: {summary}")

    def stop_ping(self):
        """Gracefully stop ping subprocess"""
        if self.process:
            self.stop_event.set()
            self.ping_logger.info("Stopping ping monitor...")

            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

            if self.reader_thread and self.reader_thread.is_alive():
                self.reader_thread.join(timeout=2)

            self.process = None
            self._close_jsonl()
            self._emit_summary()
            self.ping_logger.info("Ping monitor stopped")


def _main():
    """Standalone smoke test: run ping over adb for a fixed duration."""

    parser = argparse.ArgumentParser(
        description="Standalone test for PingMonitor (runs ping over adb for a fixed duration)."
    )
    parser.add_argument(
        "--device-serial",
        "-s",
        required=True,
        help="ADB device serial (e.g., 3C271FDJG0034L). Run `adb devices` to list.",
    )
    parser.add_argument(
        "--target",
        "-t",
        default="8.8.8.8",
        help="Ping target host (default: 8.8.8.8).",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=30,
        help="How long to run ping, in seconds (default: 30).",
    )
    parser.add_argument(
        "--name",
        "-n",
        default="test_device",
        help="Participant name used for the log file (default: test_device).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

    monitor = PingMonitor(args.name)
    log_path = os.path.join(os.getcwd(), "zoom_mobile_logs", f"{args.name}_ping.log")
    print(
        f"Starting ping on device={args.device_serial} target={args.target} "
        f"for {args.duration}s"
    )
    print(f"  log  : {log_path}")
    print(f"  jsonl: {monitor.jsonl_path}")

    monitor.start_ping(args.device_serial, target_host=args.target)
    try:
        time.sleep(args.duration)
    except KeyboardInterrupt:
        print("Interrupted - stopping early.")
    finally:
        monitor.stop_ping()

    print("Done.")


if __name__ == "__main__":
    _main()
