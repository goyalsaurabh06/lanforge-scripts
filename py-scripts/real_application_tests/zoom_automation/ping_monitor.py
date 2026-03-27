import threading
import subprocess
import os
import logging


class PingMonitor:
    def __init__(self, participant_name):
        self.participant_name = participant_name
        self.process = None
        self.ping_logger = self._create_ping_logger()
        self.reader_thread = None
        self.stop_event = threading.Event()

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
            self.process = subprocess.Popen(
                ["adb", "-s", device_serial, "shell", "ping", target_host],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True,
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

    def _read_ping_output(self):
        """Read ping output line by line and log it"""
        try:
            while not self.stop_event.is_set() and self.process:
                line = self.process.stdout.readline()
                if not line:
                    break
                self.ping_logger.info(line.strip())
        except Exception as e:
            self.ping_logger.error(f"Error reading ping output: {e}")

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
                self.reader_thread.join(timeout=1)

            self.process = None
            self.ping_logger.info("Ping monitor stopped")
