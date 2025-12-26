#!/usr/bin/env python3
import argparse
import time
import sys
import os
import pandas as pd
import importlib
import logging
import matplotlib.pyplot as plt
import csv
import asyncio
import json
import shutil
import requests
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from threading import Thread
import traceback
import threading

logger = logging.getLogger(__name__)
log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)


sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))


# Import LANforge-related modules

# Set up logging
logger = logging.getLogger(__name__)

# Import LF logger configuration module
lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")

# Import realm module
realm = importlib.import_module("py-json.realm")
Realm = realm.Realm

# Import base interop profile module
base = importlib.import_module("py-scripts.lf_base_interop_profile")
base_RealDevice = base.RealDevice

DeviceConfig = importlib.import_module("py-scripts.DeviceConfig")

# Importing modules dynamically
lf_report = importlib.import_module("py-scripts.lf_report")
lf_graph = importlib.import_module("py-scripts.lf_graph")
lf_base_interop_profile = importlib.import_module("py-scripts.lf_base_interop_profile")

# Accessing specific classes
lf_report = lf_report.lf_report
lf_bar_graph_horizontal = lf_graph.lf_bar_graph_horizontal
RealDevice = lf_base_interop_profile.RealDevice


class Netflix(Realm):
    def __init__(
        self,
        host=None,
        port=None,
        duration=0,
        debug=False,
        upstream_port=None,
    ):
        """
        Initialize the YouTube streaming test parameters.
        Args:
            host (str): Hostname or IP address of the LANforge GUI.
            port (int): Port number for LANforge HTTP service.
            url (str): YouTube URL for streaming.
            duration (int): Duration of the test in seconds.
            lanforge_password (str): LANforge password for authentication.
            sta_list (list): List of station names or identifiers.
            do_webUI (bool): Flag indicating if triggered from LANforge webUI.
            ui_report_dir (str): Directory path to store webUI reports.
            debug (bool): Enable debugging output if True.
            stats_api_response (dict): Placeholder for API response statistics.
        """
        super().__init__(lfclient_host=host, lfclient_port=port)
        self.host = host
        self.port = port
        self.duration = duration
        self.debug = debug
        self.linux = 0
        self.windows = 0
        self.mac = 0
        self.generic_endps_profile = self.new_generic_endp_profile()
        self.generic_endps_profile.type = "netflix"
        self.generic_endps_profile.name_prefix = "nflx"
        self.device_names = []
        self.start_time = datetime.now()
        self.end_time = self.start_time + timedelta(minutes=self.duration)
        self.upstream_port = upstream_port
        self.stop_signal = False
        self.real_device_obj = None
        self.real_sta_os_types = None
        self.real_sta_hostname = None
        self.hostname_os_combination = None
        self.real_sta_data_dict = {}
        self.real_sta_list = []
        self.wifi_interface_list = []
        self.stop_signal = False
        self.header = [
            "timestamp",
            "total_frames",
            "dropped_frames",
            "video_buffered",
            "audio_buffered",
            "audio_bitrate_kbps",
            "video_bitrate_kbps",
            "video_resolution",
            "audio_codec_id",
            "audio_codec_name",
            "video_codec_id",
            "video_codec_name",
        ]
        self.credentials = []
        self.cred_index = 0

    def check_gen_cx(self):
        try:

            for gen_endp in self.generic_endps_profile.created_endp:
                generic_endpoint = self.json_get(f"/generic/{gen_endp}")

                if not generic_endpoint or "endpoint" not in generic_endpoint:
                    logging.info(f"Error fetching endpoint data for {gen_endp}")
                    return False

                endp_status = generic_endpoint["endpoint"].get("status", "")

                if endp_status not in [
                    "Stopped",
                    "WAITING",
                    "NO-CX",
                    "PHANTOM",
                    "FTM_WAIT",
                ]:
                    return False

            return True
        except Exception as e:
            logging.error(f"Error in check_gen_cx function {e}", exc_info=True)
            logging.info(f"generic endpoint data {generic_endpoint}")

    def generate_report(self):
        report = lf_report(
            _output_pdf="netflix_report.pdf",
            _output_html="netflix_report.html",
            _results_dir_name="netflix_report",
            _path="",
        )
        self.report_path_date_time = report.get_path_date_time()

    def move_csv_files(self):
        dest_dir = self.report_path_date_time
        os.makedirs(dest_dir, exist_ok=True)

        current_dir = os.getcwd()

        for filename in os.listdir(current_dir):
            # Only CSV files
            if not filename.lower().endswith(".csv"):
                continue

            # Skip netflix_cred.csv
            if filename == "netflix_cred.csv":
                continue

            src_path = os.path.join(current_dir, filename)
            dest_path = os.path.join(dest_dir, filename)

            # Move file
            shutil.move(src_path, dest_path)
            print(f"Moved {filename} → {dest_dir}")

    # Load the credentials on server startup
    def load_credentials(self):
        with open("netflix_cred.csv", newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            self.credentials = list(reader)
            print(self.credentials)

    def start_flask_server(self):
        """
        Starts a Flask server with API endpoints for YouTube statistics.
        """
        app = Flask(__name__)

        @app.route("/check_stop", methods=["GET"])
        def check_stop():
            return jsonify({"stop": self.stop_signal})

        @app.route("/get_credentials", methods=["GET"])
        def get_credentials():
            if self.cred_index < len(self.credentials):
                row = self.credentials[self.cred_index]
                self.cred_index += 1
                return jsonify({"email": row["email"], "password": row["password"]})
            else:
                logging.error("Not enough credentials for devices")
                return jsonify({"log": "Not enough credentials for devices"}), 404

        @app.route("/upload_stats", methods=["POST"])
        def upload_stats():
            data = request.json

            for hostname, stats in data.items():
                csv_file = f"{hostname}.csv"
                with open(csv_file, mode="a", newline="") as file:
                    writer = csv.writer(file)

                    if os.path.getsize(csv_file) == 0:
                        writer.writerow(self.header)
                    row = [
                        stats.get("timestamp", ""),
                        stats.get("total_frames", ""),
                        stats.get("dropped_frames", ""),
                        stats.get("video_buffered", ""),
                        stats.get("audio_buffered", ""),
                        stats.get("audio_bitrate_kbps", ""),
                        stats.get("video_bitrate_kbps", ""),
                        stats.get("video_resolution", ""),
                        stats.get("audio_codec_id", ""),
                        stats.get("audio_codec_name", ""),
                        stats.get("video_codec_id", ""),
                        stats.get("video_codec_name", ""),
                    ]
                    writer.writerow(row)
            return jsonify({"status": "success"})

        def run_flask():
            app.run(host="0.0.0.0", port=5010, debug=False, use_reloader=False)

        # Run the Flask server in a separate thread to avoid blocking
        flask_thread = Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()

    def create_generic_endp(self):
        self.wifi_interface_list = [item.split(".")[2] for item in self.real_sta_list]

        if self.generic_endps_profile.create(
            ports=self.real_sta_list,
            sleep_time=0.5,
            real_client_os_types=self.real_sta_os_types,
        ):
            logging.info("Real client generic endpoint creation completed.")
        else:
            logging.error("Real client generic endpoint creation failed.")
            exit(0)

        for i in range(0, len(self.real_sta_os_types)):
            if self.real_sta_os_types[i] == "windows":
                cmd = "py netflix.py --upstream_port %s --duration %s" % (
                    self.upstream_port,
                    self.duration,
                )
                self.generic_endps_profile.set_cmd(
                    self.generic_endps_profile.created_endp[i], cmd
                )
            elif self.real_sta_os_types[i] == "linux":
                cmd = "su -l lanforge  netflix.bash %s %s %s" % (
                    self.wifi_interface_list[i],
                    self.upstream_port,
                    self.duration,
                )
                self.generic_endps_profile.set_cmd(
                    self.generic_endps_profile.created_endp[i], cmd
                )

            elif self.real_sta_os_types[i] == "macos":
                cmd = "sudo bash netflix.bash %s %s %s" % (
                    "wlan0",
                    self.upstream_port,
                    self.duration,
                )
                self.generic_endps_profile.set_cmd(
                    self.generic_endps_profile.created_endp[i], cmd
                )

        self.generic_endps_profile.start_cx()

    def filter_ios_devices(self, device_list):
        """
        Filters out iOS devices from the given device list based on hardware and software identifiers.

        This method accepts a list or comma-separated string of device identifiers and removes
        devices identified as iOS (Apple) based on their hardware version, app ID, and kernel info
        fetched via the `/resource/{shelf}/{resource}` API endpoint.

        Supported input formats for each device:
        - "shelf.resource"
        - "shelf.resource.port"
        - "resource" (assumes shelf = 1)

        iOS devices are identified if:
        - 'Apple' is found in the hardware version, and
        - `app-id` is not empty and is either non-zero or the kernel is empty

        Args:
            device_list (Union[list[str], str]): A list or comma-separated string of devices to be filtered.

        Returns:
            Union[list[int], str]: A list of valid (non-iOS) device IDs as integers,
                                or a comma-separated string if the input was a string.

        Logs:
            - Warnings for invalid formats or missing device data.
            - Info when an iOS device is skipped.
            - Exceptions if errors occur during processing.

        """
        modified_device_list = device_list
        if isinstance(device_list, str):
            modified_device_list = device_list.split(",")

        filtered_list = []

        for device in modified_device_list:
            device = str(device).strip()
            try:
                if device.count(".") == 1:
                    shelf, resource = device.split(".")
                elif device.count(".") == 2:
                    shelf, resource, port = device.split(".")
                elif device.count(".") == 0:
                    shelf, resource = 1, device
                else:
                    logger.warning("Invalid device format: %s", device)
                    continue

                device_data_resp = self.json_get(f"/resource/{shelf}/{resource}")
                if not device_data_resp or "resource" not in device_data_resp:
                    logger.warning("Device data not found for %s", device)
                    continue

                device_data = device_data_resp["resource"]
                hw_version = device_data.get("hw version", "")
                app_id = device_data.get("app-id", "")
                kernel = device_data.get("kernel", "")

                if (
                    "Apple" in hw_version
                    and app_id != ""
                    and (app_id != "0" or kernel == "")
                ):
                    logger.info(
                        "%s is an iOS device. Currently, we do not support iOS devices.",
                        device,
                    )
                else:
                    filtered_list.append(device)

            except Exception as e:
                logger.exception(f"Error processing device {device}: {e}")
                continue

        if isinstance(device_list, str):
            filtered_list = ",".join(filtered_list)

        self.device_list = filtered_list
        return filtered_list

    def select_real_devices(self, real_sta_list=None):
        self.real_device_obj.get_devices()
        # Query and retrieve all user-defined real stations if `real_sta_list` is not provided
        if real_sta_list is None:
            self.real_sta_list, _, _ = self.real_device_obj.query_user()
        else:
            interface_data = self.json_get("/port/all")
            interfaces = interface_data["interfaces"]

            for device in real_sta_list:
                for interface_dict in interfaces:
                    for key, value in interface_dict.items():
                        key_parts = key.split(".")
                        extracted_key = ".".join(key_parts[:2])
                        if (
                            extracted_key == device
                            and not value["phantom"]
                            and not value["down"]
                            and value["parent dev"] != ""
                            and value["ip"] != "0.0.0.0"
                        ):
                            self.real_sta_list.append(key)
                            break

        # Log an error and exit if no real stations are selected for testing
        if len(self.real_sta_list) == 0:
            logger.error("There are no real devices in this testbed. Aborting test")
            exit(0)

        self.real_device_obj.get_devices()
        self.real_sta_list = self.filter_ios_devices(self.real_sta_list)

        if len(self.real_sta_list) == 0:
            logger.error("There are no real devices in this testbed. Aborting test")
            exit(0)

        for sta_name in self.real_sta_list:
            if sta_name not in self.real_device_obj.devices_data:
                logger.error(
                    f"Real station '{sta_name}' not in devices data, ignoring it from testing"
                )
                self.real_sta_list.remove(sta_name)

                continue

            self.real_sta_data_dict[sta_name] = self.real_device_obj.devices_data[
                sta_name
            ]

        # Retrieve OS types and hostnames
        self.real_sta_os_types = [
            self.real_sta_data_dict[real_sta_name]["ostype"]
            for real_sta_name in self.real_sta_data_dict
        ]
        self.real_sta_hostname = [
            self.real_sta_data_dict[real_sta_name]["hostname"]
            for real_sta_name in self.real_sta_data_dict
        ]

        self.hostname_os_combination = [
            f"{hostname} ({os_type})"
            for hostname, os_type in zip(self.real_sta_hostname, self.real_sta_os_types)
        ]

        for i in range(0, len(self.real_sta_os_types)):

            if self.real_sta_os_types[i] == "windows":
                self.windows = self.windows + 1
            elif self.real_sta_os_types[i] == "linux":
                self.linux = self.linux + 1
            elif self.real_sta_os_types[i] == "macos":
                self.mac = self.mac + 1

        return self.real_sta_list


def main():
    try:
        parser = argparse.ArgumentParser(description="LANforge Netflix Interop Test")
        parser.add_argument(
            "--mgr_ip", type=str, help="LANforge GUI host", default="localhost"
        )
        parser.add_argument("--port", type=int, help="LANforge HTTP port", default=8080)
        parser.add_argument(
            "--duration", type=int, help="Duration of the test in Minutes", default=1
        )
        parser.add_argument(
            "--upstream_port", type=str, help="Upstream port for traffic", default=None
        )
        parser.add_argument("--debug", action="store_true", help="Enable debug output")
        parser.add_argument(
            "--device_list",
            type=str,
            help="Comma-separated list of real devices to use",
            default=None,
        )

        args = parser.parse_args()

        netflix_obj = Netflix(
            host=args.mgr_ip,
            port=args.port,
            duration=args.duration,
            debug=args.debug,
            upstream_port=args.upstream_port,
        )

        netflix_obj.real_device_obj = RealDevice(
            manager_ip=args.mgr_ip,
            server_ip="192.168.1.61",
            ssid_2g="Test Configured",
            passwd_2g="",
            encryption_2g="",
            ssid_5g="Test Configured",
            passwd_5g="",
            encryption_5g="",
            ssid_6g="Test Configured",
            passwd_6g="",
            encryption_6g="",
            selected_bands=["5G"],
        )
        netflix_obj.load_credentials()
        netflix_obj.start_flask_server()
        netflix_obj.select_real_devices(
            real_sta_list=args.device_list.split(",") if args.device_list else None
        )
        netflix_obj.create_generic_endp()
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=args.duration)
        while datetime.now() < end_time or not netflix_obj.check_gen_cx():
            time.sleep(5)
        netflix_obj.generate_report()
        netflix_obj.move_csv_files()
    except Exception as e:
        logger.error("Exception occurred: %s", str(e))
        traceback.print_exc()
    finally:
        netflix_obj.stop_signal = True
        logger.info("Waiting for Client Devices to terminate the browser sessions...")
        time.sleep(10)
        logger.info("Test completed.")


if __name__ == "__main__":
    main()
