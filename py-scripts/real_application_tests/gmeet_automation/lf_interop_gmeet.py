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
import glob
import pytz
import dateutil.parser # pip install python-dateutil

flask_server_logger = logging.getLogger("werkzeug")
flask_server_logger.setLevel(logging.ERROR)


sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../.."))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))


# Set up logging
logger = logging.getLogger(__name__)

# Import realm module
realm = importlib.import_module("py-json.realm")
Realm = realm.Realm

# Import base interop profile module
base = importlib.import_module("py-scripts.lf_base_interop_profile")
base_RealDevice = base.RealDevice


# Importing modules dynamically
lf_report = importlib.import_module("py-scripts.lf_report")
lf_graph = importlib.import_module("py-scripts.lf_graph")
lf_base_interop_profile = importlib.import_module("py-scripts.lf_base_interop_profile")

# Accessing specific classes
lf_report = lf_report.lf_report
lf_bar_graph_horizontal = lf_graph.lf_bar_graph_horizontal
RealDevice = lf_base_interop_profile.RealDevice


class Gmeet(Realm):
    def __init__(self):
        self.stop_signal = False
        self.meeting_url = str()
        self.upstream_port = None
        self.real_devices_obj = None
        self.real_sta_list = list()
        self.real_sta_data_dict = dict()
        self.wifi_interface_list = list()
        self.lanforge_port_list = list()
        self.lanforge_os_type = list()
        self.serial_list_str = str()
        self.windows = 0
        self.linux = 0
        self.mac = 0
        self.android = 0
        self.hostname_os_combination = list()
        self.real_sta_os_types = list()
        self.real_sta_hostname = list()
        self.tz = pytz.timezone('Asia/Kolkata')
    

    def get_api_time(self, timezone_str="UTC"):
        try:
            # Request time for a specific timezone (e.g., "Europe/London" or "Etc/UTC")
            url = f"http://worldtimeapi.org/api/timezone/{timezone_str}"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            # Parse the standard ISO format string returned by the API
            return dateutil.parser.isoparse(data['datetime'])
        except Exception as e:
            print(f"API Time check failed: {e}")
            return datetime.now() # Fallback

    def set_start_time(self):
        # Fetch accurate time via HTTP
        current_true_time = self.get_api_time("UTC") 
        
        # If you need to convert it to self.tz manually:
        if self.tz:
            current_true_time = current_true_time.astimezone(self.tz)

        self.start_time = current_true_time + timedelta(seconds=30)
        self.end_time = self.start_time + timedelta(minutes=self.duration)

        logger.info(f"Start Time of the Test {self.start_time}")
        logger.info(f"End Time of the Test {self.end_time}")
        
        return [self.start_time, self.end_time]

    def change_port_to_ip(self, upstream_port):
        """
        Convert a given port name to its corresponding IP address if it's not already an IP.

        This function checks whether the provided `upstream_port` is a valid IPv4 address.
        If it's not, it attempts to extract the IP address of the port by resolving it
        via the internal `name_to_eid()` method and then querying the IP using `json_get()`.

        Args:
            upstream_port (str): The name or IP of the upstream port. This could be a
            LANforge port name like '1.1.eth1' or an IP address.

        Returns:
            str: The resolved IP address if the port name was converted successfully,
            otherwise returns the original input if it was already an IP or
            if resolution fails.

        Logs:
            - A warning if the port is not Ethernet or IP resolution fails.
            - Info logs for the resolved or passed IP.

        """
        if upstream_port.count(".") != 3:
            target_port_list = self.name_to_eid(upstream_port)
            shelf, resource, port, _ = target_port_list
            try:
                target_port_ip = self.json_get(
                    f"/port/{shelf}/{resource}/{port}?fields=ip"
                )["interface"]["ip"]
                upstream_port = target_port_ip
            except Exception as e:
                logging.warning(
                    f"Could not resolve IP for port {upstream_port}: {e}. Proceeding with the given upstream_port {upstream_port}."
                )
                logging.warning(
                    f"The upstream port is not an ethernet port. Proceeding with the given upstream_port {upstream_port}."
                )
            logging.info(f"Upstream port IP {upstream_port}")
        else:
            logging.info(f"Upstream port IP {upstream_port}")

        self.upstream_port = upstream_port

    def get_android_device_data(self):
        """
        Fetch and process Android device information from the ADB interop API.

        This method queries the '/adb' endpoint to retrieve connected Android
        device details, matches devices against the configured user list,
        and extracts relevant metadata for test execution.

        Behavior:
        - Supports both dictionary and list response formats from the API
        - Filters devices based on matching 'user-name' entries
        - Extracts device serial numbers and LANforge resource IDs
        - Builds LANforge port identifiers in the format: 1.<resource>.eth0
        - Populates internal lists used for endpoint and test setup

        Side Effects:
        - Updates self.serial_list with Android device serial numbers
        - Updates self.lanforge_port_list with LANforge port identifiers
        - Sets self.lanforge_os_type to 'Linux' for all discovered devices
        - Generates a comma-separated serial string in self.serial_list_str

        Returns:
            None
        """
        interop_data = self.json_get("/adb")
        interop_mobile_data = interop_data.get("devices", {})

        if isinstance(interop_mobile_data, dict):
            for user in self.user_list:
                if user != "":
                    if interop_mobile_data.get("user-name") == user:

                        serial = interop_mobile_data.get("name", "")
                        resource = serial.split(".")[1]
                        serial_no = serial.split(".")[2]
                        self.serial_list.append(serial_no)
                        lanforge_port = f"1.{resource}.eth0"
                        self.lanforge_port_list.add(lanforge_port)

        else:
            for user in self.user_list:
                if user != "":
                    for mobile_device in interop_mobile_data:
                        for serial, device_data in mobile_device.items():
                            if device_data.get("user-name") == user:
                                resource = serial.split(".")[1]
                                serial_no = serial.split(".")[2]
                                self.serial_list.append(serial_no)
                                lanforge_port = f"1.{resource}.eth0"
                                self.lanforge_port_list.add(lanforge_port)
                                break

        self.lanforge_port_list = list(self.lanforge_port_list)
        self.lanforge_os_type = ["Linux"] * len(self.lanforge_port_list)
        self.serial_list_str = ",".join(self.serial_list)

    def start_flask_server(self):
        """
        Starts a Flask server with API endpoints for YouTube statistics.
        """
        app = Flask(__name__)

        @app.route("/check_stop", methods=["GET"])
        def check_stop():
            return jsonify({"stop": self.stop_signal})

        @app.route("/meeting_url", methods=["GET", "POST"])
        def meeting_url():
            if request.method == "POST":
                data = request.json
                self.meeting_url = data.get("meeting_url")

                return jsonify({"message": "meeting url updated"}), 200

            elif request.method == "GET":
                return jsonify({"meeting_url": self.meeting_url})

        def run_flask():
            app.run(host="0.0.0.0", port=5020, debug=False, use_reloader=False)

        # Run the Flask server in a separate thread to avoid blocking
        flask_thread = Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()
    

    def create_host(self):

        if self.generic_endps_profile.create(ports=[self.real_sta_list[0]], real_client_os_types=[self.real_sta_os_types[0]]):
            logging.info('Real client generic endpoint creation completed.')
        else:
            logging.error('Real client generic endpoint creation failed.')
            exit(0)

        if self.real_sta_os_types[0] == "windows":
            cmd = f"py gmeet_host.py --ip {self.upstream_port}"
            self.generic_endps_profile.set_cmd(self.generic_endps_profile.created_endp[0], cmd)
        elif self.real_sta_os_types[0] == 'linux':

            cmd = "su -l lanforge ctteams.bash %s %s %s" % (self.wifi_interfaces[0], self.upstream_port, "host")

            self.generic_endps_profile.set_cmd(self.generic_endps_profile.created_endp[0], cmd)
        elif self.real_sta_os_types[0] == 'macos':
            cmd = "sudo bash ctteams.bash %s %s" % (self.upstream_port, "host")
            self.generic_endps_profile.set_cmd(self.generic_endps_profile.created_endp[0], cmd)
        self.generic_endps_profile.start_cx()
        time.sleep(5)


    def process_device_data(self):
        """
        Populate hostnames, OS types, and per-OS device counts for real stations.

        Android devices use serial numbers as hostnames (mapped sequentially),
        while other OS types use their reported hostnames. Also builds a combined
        hostname–OS list for display and updates OS counters.

        Returns:
            None
        """

        serial_idx = 0  # separate counter just for Android devices

        for _, sta_info in self.real_sta_data_dict.items():
            os_type = sta_info.get("ostype", "")
            self.real_sta_os_types.append(os_type)

            if os_type.lower() == "android":
                if serial_idx < len(self.serial_list):
                    self.real_sta_hostname.append(self.serial_list[serial_idx])
                    serial_idx += 1  # advance only for Androids
                else:
                    self.real_sta_hostname.append("NA")
            else:
                self.real_sta_hostname.append(sta_info.get("hostname", "NA"))

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
            elif self.real_sta_os_types[i] == "android":
                self.android = self.android + 1

    def get_device_data(self):
        """
        Collect and correlate device, resource, and port information for real stations.

        This method gathers metadata for devices listed in `self.real_sta_list` by:
        1. Extracting user-specified resource identifiers from real station entries.
        2. Querying the '/resource/all' API to map resources to device names,
        controller IPs, EIDs, and associated users.
        3. Querying the '/port/all' API to locate ports belonging to the matched
        resources, preserving the order defined by the real station list.
        4. Extracting wireless-specific attributes for ports associated with
        the 'wiphy0' parent device.

        The method builds several internal lists that are later used for endpoint
        creation, test execution, and result processing.

        Side Effects:
        - Populates self.device_names with matched device hostnames
        - Populates self.user_list with users associated with each resource
        - Populates self.mac_list with MAC addresses for wireless ports
        - Populates self.rssi_list with signal strength values
        - Populates self.link_rate_list with RX link rates
        - Populates self.ssid_list with SSID values

        Notes:
        - The method preserves the order of devices as specified in
        `self.real_sta_list`.
        - Only ports whose parent device is 'wiphy0' are considered wireless
        and used to collect RSSI, MAC, link rate, and SSID information.
        - This method does not return any value; all results are stored as
        instance attributes.

        Returns:
            None
        """

        ports_list = []
        user_resources = [".".join(item.split(".")[:2]) for item in self.real_sta_list]

        # Step 1: Retrieve information about all resources
        response = self.json_get("/resource/all")

        resource_data_list = response.get("resources", [])

        # Step 2. Loop through the user resources you want to find
        for user_resource in user_resources:

            # Look through the data to find that user
            for element in resource_data_list:

                # Check if the user_resource (e.g., "1.1") exists in this dictionary element
                if user_resource in element:
                    resource_values = element[user_resource]

                    # Extract the data
                    self.device_names.append(resource_values["hostname"])
                    self.user_list.append(resource_values["user"])
                    ports_list.append(
                        {
                            "eid": resource_values["eid"],
                            "ctrl-ip": resource_values["ctrl-ip"],
                        }
                    )

                    # Found it! Stop searching specifically for this user_resource
                    break
        self.mac_list = []
        self.rssi_list = []
        self.link_rate_list = []
        self.ssid_list = []

        # Step 3: Retrieve all port information
        all_ports_response = self.json_get("/port/all")
        interfaces_list = all_ports_response.get("interfaces", [])

        # Step 4: Find matching wifi ports for our target resources
        for target_resource in ports_list:
            target_eid = target_resource["eid"]

            # Search through all available interfaces
            for interface_entry in interfaces_list:
                for port_name, port_details in interface_entry.items():

                    # Logic: Extract EID from port name (e.g., "1.1.wlan0" -> "1.1")
                    current_eid = ".".join(port_name.split(".")[:2])

                    if (
                        current_eid == target_eid
                        and port_details.get("parent dev") == "wiphy0"
                    ):
                        self.mac_list.append(port_details.get("mac"))
                        self.rssi_list.append(port_details.get("signal"))
                        self.link_rate_list.append(port_details.get("rx-rate"))
                        self.ssid_list.append(port_details.get("ssid"))

        self.wifi_interface_list = [item.split(".")[2] for item in self.real_sta_list]

    def select_real_devices(self, real_sta_list=None):
        self.real_devices_obj.get_devices()
        # Query and retrieve all user-defined real stations if `real_sta_list` is not provided
        if real_sta_list is None:
            self.real_sta_list, _, _ = self.real_devices_obj.query_user()
        else:
            interface_data = self.json_get("/port/all")
            interfaces = interface_data["interfaces"]
            final_device_list = []  # Initialize the list

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
                            final_device_list.append(key)
                            break

            self.real_sta_list = final_device_list

        # Log an error and exit if no real stations are selected for testing
        if len(self.real_sta_list) == 0:
            logger.error("There are no real devices in this testbed. Aborting test")
            exit(0)

        self.real_devices_obj.get_devices()
        self.real_sta_list = self.filter_ios_devices(self.real_sta_list)

        if len(self.real_sta_list) == 0:
            logger.error("There are no real devices in this testbed. Aborting test")
            exit(0)

        for sta_name in self.real_sta_list:
            if sta_name not in self.real_devices_obj.devices_data:
                logger.error(
                    f"Real station '{sta_name}' not in devices data, ignoring it from testing"
                )
                self.real_sta_list.remove(sta_name)

                continue

            self.real_sta_data_dict[sta_name] = self.real_devices_obj.devices_data[
                sta_name
            ]

        return self.real_sta_list


def main():
    parser = argparse.ArgumentParser("Google Meet Automation")

    # Define required arguments group
    required = parser.add_argument_group("Required arguments")
    # Define optional arguments group
    optional = parser.add_argument_group("Optional arguments")

    # Add parser arguments
    required.add_argument(
        "--mgr", type=str, help="hostname where LANforge GUI is running", parser=True
    )
    required.add_argument(
        "--duration", type=int, help="duration to run the test", parser=True
    )

    required.add_argument(
        "--upstream_port",
        type=str,
        help="Upstream port ip or EID for data transfer and communcation with clients",
    )

    optional.add_argument(
        "--resources", help="Specify the real device ports seperated by comma"
    )
    optional.add_argument(
        "--no_pre_cleanup",
        action="store_true",
        help="specify this flag to stop cleaning up generic cxs before the test",
    )
    optional.add_argument(
        "--no_post_cleanup",
        action="store_true",
        help="specify this flag to stop cleaning up generic cxs after the test",
    )

    args = parser.parse_args()

    gmeet = Gmeet()
    gmeet.change_port_to_ip(args.upstream_port)

    gmeet.real_devices_obj = RealDevice(
        manager_ip=args.mgr, server_ip=gmeet.upstream_port
    )

    gmeet.real_devices_obj.get_devices()

    if args.resources:
        resources = [r.strip() for r in args.resources.split(",")]
        resources = [r for r in resources if len(r.split(".")) > 1]

        gmeet.select_real_devices(real_sta_list=resources)

    else:
        gmeet.select_real_devices()

    gmeet.get_device_data()
    gmeet.get_android_device_data()
    gmeet.process_device_data()
    gmeet.create_host()

