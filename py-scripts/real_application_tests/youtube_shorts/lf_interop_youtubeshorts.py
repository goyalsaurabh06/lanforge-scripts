import argparse
import time
import sys
import os
import pandas as pd
import importlib
import matplotlib.pyplot as plt
import csv
import asyncio
import json
import shutil
import requests
import logging
import threading
import traceback
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from flask import Flask, request, jsonify
from threading import Thread   

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Reduce noisy Flask internal logs
werk_log = logging.getLogger('werkzeug')
werk_log.setLevel(logging.ERROR)

# Pretty log format
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

if 'py-json' not in sys.path:
    sys.path.append('/home/lanforge/lanforge-scripts/py-json')

if 'py-scripts' not in sys.path:
    sys.path.append('/home/lanforge/lanforge-scripts/py-scripts')

# Add parent folder
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

# IMPORT LANFORGE MODULES
try:
    realm = importlib.import_module("py-json.realm")
    lf_report_mod = importlib.import_module("py-scripts.lf_report")
    lf_graph_mod = importlib.import_module("py-scripts.lf_graph")
    lf_base_mod = importlib.import_module("py-scripts.lf_base_interop_profile")
    DeviceConfig = importlib.import_module("py-scripts.DeviceConfig")
except Exception as e:
    logger.error("Unable to import LANforge helper modules. Check sys.path and installation.")
    traceback.print_exc()
    raise

# useful classes for easy access
Realm = realm.Realm
RealDevice = lf_base_mod.RealDevice
lf_report = lf_report_mod.lf_report
lf_bar_graph_horizontal = lf_graph_mod.lf_bar_graph_horizontal


class YouTubeShorts(Realm):
    """
    Class for automating YouTube Shorts playback tests using LANforge.

    Responsibilities:
    - Connect to LANforge
    - Discover devices
    - Create and start generic endpoints
    - Receive stats from laptops through Flask
    - Track test duration and stop conditions
    - Generate final reports
    - Cleanup endpoints
    """

    def __init__(self,
                 host=None,
                 port=None,
                 duration=0,
                 scroll=0,
                 flask_ip=None,
                 do_webUI=False,
                 debug=False,
                 ui_report_dir=None):

        # Initialize LANforge Realm
        super().__init__(lfclient_host=host, lfclient_port=port)

        # Basic configuration
        self.host = host
        self.port = port
        self.duration = duration
        self.scroll = scroll
        self.flask_ip = flask_ip
        self.do_webUI = do_webUI
        self.ui_report_dir = ui_report_dir
        self.debug = debug
        self.stats_received = False
        self.cx_has_started = False
        self.cx_launch_time = None
        self.first_stat_time = None



        # Device discovery results
        self.real_sta_list = []
        self.real_sta_data_dict = {}
        self.real_sta_hostname = []
        self.real_sta_os_types = []

        # Stats storage
        self.stats_api_response = {}

        # CSV tracking for reporting
        self.devices_list = []

        # Generic endpoint profile
        self.generic_endps_profile = self.new_generic_endp_profile()
        self.generic_endps_profile.type = "youtube"
        self.generic_endps_profile.name_prefix = "ytshorts"

        # Android generic endpoint profile
        self.android_profiles = []




        # Execution tracking
        self.start_time = None
        self.est_end_time = None
        self.all_stop = False
        self.stop_signal = False

        # Aggregated data for final report
        self.device_names = []
        self.mydatajson = {}
        self.final_data = None

        # REQUIRED FIX ✔
        self.stats_lock = threading.Lock()

        # Track last written timestamp per device (DEDUP)
        self.last_written_timestamp = {}

        logger.info("YouTube Shorts Interop object initialized.")

    # Shutdown handler
    
    def shutdown(self):
        logger.info("shutting down YouTube Shorts...")
        self.stop_signal = True
        time.sleep(5)
        os._exit(1)

    # Start Flask server for receiving stats and stop signals

    def start_flask_server(self):
        """
        Flask server for:
        - Receiving stats from laptops (POST)
        - Allowing LANforge to read stats (GET)
        - Allowing WebUI to stop test
        - Allowing laptops to check stop flag
        """

        app = Flask(__name__)

        # Endpoint: devices poll everytime  to check stop condition
        @app.route('/check_stop', methods=['GET'])
        def check_stop():
            return jsonify({"stop": self.stop_signal})

        # Endpoint: LANforge/WebUI forces test stop
        @app.route('/stop_yt', methods=['GET'])
        def stop_yt():
            logger.info("Stopping YouTube Shorts test via /stop_yt")

            # respond immediately
            resp = jsonify({"message": "Stopping YouTube Shorts Test"})
            resp.status_code = 200

            # graceful shutdown
            shutdown_thread = threading.Thread(target=self.shutdown)
            shutdown_thread.start()

            return resp

        # Endpoint: device stats POST / LANforge stats GET
        @app.route('/youtube_stats', methods=['GET', 'POST'])
        def youtube_stats():

            # ------------ handle POST from laptops ------------
            if request.method == 'POST':
                data = request.json or {}

                # Ignore clear_data POSTs (do NOT start timer)
                if data.get("clear_data"):
                    with self.stats_lock:
                        self.stats_api_response = {}
                    return jsonify({"message": "Data cleared"}), 200

                # Start timer ONLY on first real device stats
                if (
                    not self.stats_received
                    and any(isinstance(v, dict) for v in data.values())
                ):
                    self.stats_received = True
                    self.first_stat_time = datetime.now()
                    logger.info("First Shorts stats received → starting test timer")


                # global stop flag
                global_stop_flag = data.get("stop", False)

                if global_stop_flag:
                    self.stop_signal = True

                # per-device stats
                for device, stats in data.items():

                    if device in ["stop", "clear_data"]:
                        continue

                    if not isinstance(stats, dict):
                        continue

                    if "Timestamp" not in stats:
                        stats["Timestamp"] = datetime.now().strftime("%H:%M:%S")

                    with self.stats_lock:
                        self.stats_api_response[device] = {
                            **stats,
                            "stop": global_stop_flag
                        }

                return jsonify({"message": "Stats updated"}), 200


            #  handle GET from LANforge 
            if request.method == 'GET':
                return jsonify({"result": self.stats_api_response}), 200

            return jsonify({"error": "Invalid request"}), 400

        # Endpoint: read final CSV row for UI/debugging
        @app.route('/read_youtube_data_from_csv', methods=['GET'])
        def read_youtube_data_from_csv():
            device_data = {}

            for csv_file_path in self.devices_list:
                if not os.path.isfile(csv_file_path):
                    continue

                df = pd.read_csv(csv_file_path)
                if df.empty:
                    continue

                last_row = df.iloc[-1].to_dict()
                name = os.path.basename(csv_file_path).replace("_shorts_stats.csv", "")
                device_data[name] = last_row

            return jsonify({"result": device_data}), 200

        # Run Flask server in background thread
        def run_flask():
            app.run(host="0.0.0.0", port=5002, debug=False, use_reloader=False)

        flask_thread = Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()

        logger.info("Flask server started on port 5002")


    def select_real_devices(self, real_devices, real_sta_list=None, base_interop_obj=None):
        """
        Selects real (non-Android) devices for testing.
        Android devices are FILTERED here and handled separately
        by create_android_generic_endp().
        """

        # --------------------------------------------------
        #  Resolve real-sta list
        if real_sta_list is None:
            self.real_sta_list, _, _ = real_devices.query_user()
        else:
            interface_data = self.json_get("/port/all")
            if not interface_data or "interfaces" not in interface_data:
                logger.error("LANforge /port/all error.")
                exit(1)

            interfaces = interface_data["interfaces"]
            final_device_list = []

            for device in real_sta_list:  # e.g. "1.11"
                for interface_dict in interfaces:
                    for key, value in interface_dict.items():  # "1.11.wlan0"
                        eid = ".".join(key.split(".")[:2])
                        if (
                            eid == device
                            and not value["phantom"]
                            and not value["down"]
                            and value["parent dev"]
                            and value["ip"] != "0.0.0.0"
                        ):
                            final_device_list.append(key)
                            break

            self.real_sta_list = final_device_list

        if base_interop_obj is not None:
            self.Devices = base_interop_obj

        if not self.real_sta_list:
            logger.error("No real stations found. Aborting test.")
            exit(0)

        # --------------------------------------------------
        #  Build real_sta_data_dict
        self.real_sta_data_dict = {}

        for sta in list(self.real_sta_list):
            if sta not in real_devices.devices_data:
                logger.error(f"Real station '{sta}' missing in devices_data → removing.")
                self.real_sta_list.remove(sta)
                continue
            self.real_sta_data_dict[sta] = real_devices.devices_data[sta]

        if not self.real_sta_list:
            logger.error("No valid real devices after validation.")
            exit(0)

        # --------------------------------------------------
        #  FILTER OUT ANDROID REAL-STAS 
        # Track Android real-stas 
        self.selected_android_realstas = []
        filtered_sta_list = []
        filtered_sta_data = {}

        for sta in self.real_sta_list:
            os_type = self.real_sta_data_dict[sta]["ostype"]
            if os_type == "android":
                eid = ".".join(sta.split(".")[:2])  # 1.12.wlan0 → 1.12
                logger.info(f"Selected Android real-sta {eid}")
                self.selected_android_realstas.append(eid)
                continue


            filtered_sta_list.append(sta)
            filtered_sta_data[sta] = self.real_sta_data_dict[sta]

        self.real_sta_list = filtered_sta_list
        self.real_sta_data_dict = filtered_sta_data

        if not self.real_sta_list:
            logger.info("No non-Android real stations selected.")
            return []

        # --------------------------------------------------
        #  Sort ports 
        def sort_key(port):
            try:
                return int(port.split(".")[1])
            except:
                return 9999

        self.real_sta_list = sorted(self.real_sta_list, key=sort_key)

        # --------------------------------------------------
        #  Extract hostname & OS 
        self.real_sta_os_types = [
            self.real_sta_data_dict[sta]["ostype"] for sta in self.real_sta_list
        ]
        self.real_sta_hostname = [
            self.real_sta_data_dict[sta]["hostname"] for sta in self.real_sta_list
        ]

        # --------------------------------------------------
        # Logging & counters
        self.hostname_os_combination = [
            f"{h} ({o})" for h, o in zip(self.real_sta_hostname, self.real_sta_os_types)
        ]

        self.windows = sum(1 for o in self.real_sta_os_types if o == "windows")
        self.linux = sum(1 for o in self.real_sta_os_types if o == "linux")
        self.mac = sum(1 for o in self.real_sta_os_types if o == "macos")

        logger.info("Selected Devices:")
        logger.info(f" Ports: {self.real_sta_list}")
        logger.info(f" Hostnames: {self.real_sta_hostname}")
        logger.info(f" OS Types: {self.real_sta_os_types}")

        return self.real_sta_list

    

    def create_generic_endp(self, query_resources):
        """
        Create LANforge generic endpoints for YouTube Shorts automation.

        Steps:
        1. Resolve ports/resources → get EID + hostname
        2. Fetch port info (/port/all) and extract WiFi interface details
        3. Create generic endpoints in LANforge
        4. Assign OS-specific command for Shorts automation
        """

        #   resource info (EID, ctrl-ip, hostname)

        ports_list = []
        user_resources = ['.'.join(item.split('.')[:2]) for item in self.real_sta_list]

        response = self.json_get("/resource/all")

        if user_resources:
            for user_resource in user_resources:
                for key, value in response.items():
                    if key == "resources":
                        for element in value:
                            for resource_key, resource_values in element.items():
                                if resource_key == user_resource:
                                    ports_list.append({
                                        "eid": resource_values["eid"],
                                        "ctrl-ip": resource_values["ctrl-ip"],
                                        "hostname": resource_values["hostname"]
                                    })
                                    self.device_names.append(resource_values["hostname"])
                                    break
                            else:
                                continue
                            break

        # Fetch WiFi interface details
        response_port = self.json_get("/port/all")

        self.mac_list = []
        self.rssi_list = []
        self.link_rate_list = []
        self.ssid_list = []
        self.new_port_list = []

        for port_entry in ports_list:
            expected_eid = port_entry["eid"]

            for interface in response_port["interfaces"]:
                for port_name, port_data in interface.items():

                    eid_prefix = ".".join(port_name.split(".")[:2])  # "1.5" from "1.5.wlan0"

                    # Match the device EID
                    if eid_prefix == expected_eid:

                        # Only pick the WiFi interface
                        if port_data["parent dev"] == "wiphy0":  
                            self.mac_list.append(port_data.get("mac", ""))
                            self.rssi_list.append(port_data.get("signal", ""))
                            self.link_rate_list.append(port_data.get("rx-rate", ""))
                            self.ssid_list.append(port_data.get("ssid", ""))
                            break
                else:
                    continue
                break

        # for Example: "1.5.wlan0" → "wlan0"
        self.new_port_list = [p.split(".")[2] for p in self.real_sta_list]

        #  Create LANforge generic endpoints
        created = self.generic_endps_profile.create(
            ports=self.real_sta_list,
            sleep_time=0.5,
            real_client_os_types=self.real_sta_os_types
        )

        if created:
            logging.info("==============================================")
            logging.info("Generic endpoint creation SUCCESS.")
        else:
            logging.error("Generic endpoint creation FAILED.")
            exit(0)

        # STEP 4: Assign OS-specific command to endpoints
        for i in range(len(self.real_sta_os_types)):
            os_type = self.real_sta_os_types[i]
            hostname = self.real_sta_hostname[i]

            # ---------------- WINDOWS ------------------
            if os_type == "windows":
                cmd = (
                  	r'"C:\Program Files (x86)\LANforge-Server\youtube_shorts_windows.bat" '
                    f"--scroll {self.scroll} "
                    f"--duration {self.duration} "
                    f"--host {self.flask_ip} "
                    f"--device_name {hostname}"
                )

            # ---------------- LINUX --------------------
            elif os_type == "linux":
                iface = self.real_sta_list[i].split(".")[2]  
                stats_file = f"/tmp/youtube_shorts_{hostname}_stats.json" 
                cmd = (
                    f"su -l lanforge -c "
                    f"\"bash youtube_shorts_linux.sh "
                    f"{iface} "
                    f"--scroll {self.scroll} "
                    f"--duration {self.duration} "
                    f"--host {self.flask_ip} "
                    f"--device_name {hostname} "
                    f"--stats_file {stats_file}\""
                )
                
            # ---------------- MAC OS -------------------
            elif os_type == "macos":
                    cmd = (
                        f"sudo bash yt_shorts_macos.sh "
                        f"--scroll {self.scroll} "
                        f"--duration {self.duration} "
                        f"--host {self.flask_ip} "
                        f"--device_name {hostname}"
                    )
            else:
                logging.error(f"Unknown OS type: {os_type}")
                continue

            # Attach command to correct endpoint
            self.generic_endps_profile.set_cmd(
                self.generic_endps_profile.created_endp[i], cmd
            )

        logging.info("All OS-specific endpoint commands assigned successfully.")
    

    def create_android_generic_endp(self):
        """
        - ONE generic endpoint
        - ONE anchor port
        - ADB handles multiple devices internally
        """

        if not self.mobile_devices:
            logger.info("No Android devices found. Skipping Android endpoints.")
            return

        #  anchor port (NOT device-mapped)
        anchor_port = "1.1.eth0"

        profile = self.new_generic_endp_profile()
        profile.type = "youtube"
        profile.name_prefix = "ytshorts_android"
        profile.no_preexec = True

        created = profile.create(
            ports=[anchor_port],
            sleep_time=0.5,
            real_client_os_types=["linux"]
        )

        if not created:
            logger.error("Failed to create Android Shorts generic endpoint")
            return

        # Pass ALL serials together
        serials = ",".join(self.mobile_devices)

        cmd = (
            "bash -lc '"
            "export PATH=/usr/local/bin:/usr/bin:/bin && "
            "export HOME=/home/lanforge && "
            f"python3 /home/lanforge/youtubeshortsandroid.py "
            f"--devices {serials} "
            f"--duration {self.duration} "
            f"--scroll {self.scroll} "
            f"--host {self.flask_ip} "
            "| tee /home/lanforge/youtube_shorts_android.log"
            "'"
        )

        endp = profile.created_endp[0]
        logger.info(f"[ANDROID] {cmd}")

        profile.set_cmd(endp, cmd)
        self.android_profiles.append(profile)

        logger.info("Android Shorts generic endpoint created (Instagram-style).")


    def get_android_serials_from_deviceconfig(self):
        """
        LANforge real-sta (1.xx) → correct ADB serial
        """

        cfg = DeviceConfig.DeviceConfig(lanforge_ip=self.host)
        adb_devices = cfg.adb_obj.get_devices()

        logger.info(f"DeviceConfig ADB devices: {adb_devices}")
        logger.info(f"Selected Android EIDs: {self.selected_android_realstas}")

        serials = []

        for sta in self.selected_android_realstas:
            eid = sta  # example: "1.22"

            for adb in adb_devices:
                if adb.get("eid") == eid:
                    if adb.get("phantom"):
                        logger.warning(f"Skipping phantom Android {adb['serial']}")
                        continue

                    serials.append(adb["serial"])
                    break

        return serials


    def start_generic(self):
        """
        Starts the generic endpoints' connections and sets the start time.

        Steps:
        1. Starts the connections of generic endpoints using `self.generic_endps_profile.start_cx()`.
        2. Sets the start time (`self.start_time`) to the current datetime.

        """
        # Start the connections of generic endpoints
        if self.generic_endps_profile.created_endp:
            self.generic_endps_profile.start_cx()

        # Start android CXs (if any)
        for profile in self.android_profiles:
            profile.start_cx()

        # Timestamp when LANforge launches client scripts
        self.cx_launch_time = datetime.now()
        # Set the start time to the current datetime
        self.start_time = datetime.now()

    def stop_generic_cx(self,):
        """
        Stops a specific generic connection (CX) and records the stop time.
        Args:
        - cx_name (str): The name of the specific connection to stop.

        Procedure followed:
        1. Stops the specific connection using `self.generic_endps_profile.stop_cx_specific(cx_name)`.
        2. Sets the stop time (`self.stop_time`) to the current datetime.
        """
        # Stop the specific connection (CX)
        # self.generic_endps_profile.stop_cx_specific(cx_name)
        self.generic_endps_profile.stop_cx()

        # stop android cxs if any
        for profile in self.android_profiles:
            if profile.created_endp:
                profile.stop_cx()

        # Set the stop time to the current datetime
        self.stop_time = datetime.now()


    def get_data_from_api(self):
        """
        Pull the latest YouTube Shorts stats from the Flask API.
        This function:
        - Gets JSON from /youtube_stats
        - Tracks max/min BufferHealth
        - Writes stats + min/max buffer health into CSV
        - Returns the parsed JSON data
        """

        api_url = f"http://{self.flask_ip}:5002/youtube_stats"

        
        # Make API request (get) to Flask

        try:
            response = requests.get(api_url)
        except Exception as e:
            logging.error(f"API request failed: {e}")
            return None

        if response.status_code != 200:
            logging.error(f"Bad API response: {response.status_code}")
            return None

        data = response.json()
        if "result" not in data:
            return None

        result_data = data["result"]
        if not result_data:
            return None

        # Process each device's stats as everythings stats stored in statsapiresponse list of dict
        for device_name, stats in result_data.items():

            # Timestamp (use current time if missing)
            timestamp = stats.get("Timestamp", datetime.now().strftime("%H:%M:%S"))

            last_ts = self.last_written_timestamp.get(device_name)

            if last_ts == timestamp:
                continue  # skip duplicate second

            self.last_written_timestamp[device_name] = timestamp

            # Convert BufferHealth to float (Android sends "x.xx s")
            raw_bh = stats.get("BufferHealth", "0.0")

            try:
                if isinstance(raw_bh, str):
                    # remove unit like " s"
                    raw_bh = raw_bh.replace("s", "").strip()
                bh = float(raw_bh)
            except Exception:
                bh = 0.0

            if device_name not in self.mydatajson:
                self.mydatajson[device_name] = {
                    "maxbufferhealth": "0.0",
                    "minbufferhealth": "9999.0"
                }

            # Update min/max buffer health
            current_max = float(self.mydatajson[device_name]["maxbufferhealth"])
            current_min = float(self.mydatajson[device_name]["minbufferhealth"])

            self.mydatajson[device_name]["maxbufferhealth"] = str(max(current_max, bh))
            self.mydatajson[device_name]["minbufferhealth"] = str(min(current_min, bh))

            max_bh = self.mydatajson[device_name]["maxbufferhealth"]
            min_bh = self.mydatajson[device_name]["minbufferhealth"]

            # CSV setup: one CSV per device

            csv_file = f"{device_name}_shorts_stats.csv"

            if self.do_webUI:
                csv_path = os.path.join(self.ui_report_dir, csv_file)
            else:
                csv_path = os.path.join(os.getcwd(), csv_file)

            file_exists = os.path.isfile(csv_path)

            headers = [
                "Instance Name",
                "Iteartions",
                "Timestamp",
                "Viewport",
                "DroppedFrames",
                "TotalFrames",
                "CurrentRes",
                "BufferHealth",
                "MaxBufferHealth",
                "MinBufferHealth"
            ]

        
            # Write row into CSV

            row = [
                device_name,
                stats.get("Iterations", "NA"),
                timestamp,
                stats.get("Viewport", "NA"),
                stats.get("DroppedFrames", "NA"),
                stats.get("TotalFrames", "NA"),
                stats.get("CurrentRes", "NA"),
                stats.get("BufferHealth", "0.0"),
                max_bh,
                min_bh
            ]
            with open(csv_path, "a", newline="") as f:
                writer = csv.writer(f)

                # Write headers only once
                if not file_exists:
                    writer.writerow(headers)

                writer.writerow(row)

            # Track this CSV file path
            if csv_path not in self.devices_list:
                self.devices_list.append(csv_path)

        return data
    

    def check_gen_cx(self):
        """
        Check if all generic endpoints have stopped on their own.

        IMPORTANT:
        - WAITING is NOT treated as stopped UNTIL
        the CX has been RUNNING at least once.
        """

        try:
            all_endps = []

            # desktop endpoints
            all_endps.extend(self.generic_endps_profile.created_endp)

            # android endpoints (multiple profiles)
            for profile in self.android_profiles:
                all_endps.extend(profile.created_endp)

            for gen_endp in all_endps:

                endpoint_data = self.json_get(f"/generic/{gen_endp}")

                if not endpoint_data or "endpoint" not in endpoint_data:
                    logging.error(f"Error fetching endpoint data for {gen_endp}")
                    return False

                status = endpoint_data["endpoint"].get("status", "")

                # detect first RUNNING
                if status == "RUNNING":
                    self.cx_has_started = True
                    return False

                # still active
                if status not in ["WAITING", "Stopped", "NO-CX"]:
                    return False

                # waiting but never ran
                if status in ["WAITING", "Stopped"] and not self.cx_has_started:
                    return False

            # all ran once and now stopped
            return self.cx_has_started

        except Exception as e:
            logging.error(f"Error in check_gen_cx: {e}")
            return False



    

    def check_tab_exists(self):
        """
        Check if the 'generic' LANforge tab exists.

        Returns True if:
        - LANforge returns valid JSON for /generic
        Returns False if:
        - No response or LANforge does not support generic endpoints
        """
        response = self.json_get("generic")
        return response is not None
    

    def clear_previous_data(self):
        """
        Clear previous YouTube Shorts stats stored in the Flask server.
        """
        try:
            url = f"http://{self.flask_ip}:5002/youtube_stats"

            payload = {"clear_data": True}

            response = requests.post(url, json=payload)

            if response.status_code == 200:
                logging.info("Successfully cleared previous Shorts stats from Flask.")
            else:
                logging.error(f"Failed to clear Shorts stats. Status code: {response.status_code}")

        except Exception as e:
            logging.error(f"Error clearing previous Shorts stats: {e}")


    def monitoring_loop(self):
        """
        Main test loop for YouTube Shorts automation.
        """

        logging.info("=== Monitoring YouTube Shorts Test ===")

        # FIX: timer starts only AFTER first stats
        test_start_time = None
        end_time = None

        while True:

            if not self.stats_received:
                logging.info("Waiting for first stats from client...")
                time.sleep(1)
                continue

            # FIX: initialize timer exactly at first stat
            if test_start_time is None:
                test_start_time = self.first_stat_time
                end_time = test_start_time + timedelta(seconds=self.duration)
                logging.info(
                    f"Test timer started at {test_start_time.strftime('%H:%M:%S')} "
                    f"for {self.duration} seconds"
                )

            if self.stop_signal:
                logging.info("Stop signal detected. Ending test.")
                break

            self.get_data_from_api()

            if self.check_gen_cx():
                logging.info("All generic endpoints stopped AFTER stats. Ending test.")
                break

            if datetime.now() >= end_time:
                logging.info("Test duration completed.")
                self.stop_signal = True
                break

            time.sleep(1)

        try:
            self.generic_endps_profile.stop_cx()
            logging.info("Stopped generic endpoints after monitoring.")
        except Exception as e:
            logging.error(f"Failed stopping CX at end: {e}")

        logging.info("YouTube Shorts monitoring loop ended.")


    """ def get_system_adb_devices(self):
        try:
            out = subprocess.check_output(["adb", "devices"], text=True)
            return [
                line.split()[0]
                for line in out.splitlines()
                if "\tdevice" in line and not line.startswith("List")
            ]
        except Exception as e:
            logger.error(f"ADB detection failed: {e}")
            return [] """


    def cleanup(self):
        """
        Cleanup all YouTube Shorts generic endpoints and connections.
        This removes:
        - Desktop CXs + endpoints
        - Android CXs + endpoints
        Ensures a clean state for the next test.
        """

        try:
            logger.info("Cleaning up YouTube Shorts generic endpoints...")

            # Stop Desktop CXs
            try:
                if self.generic_endps_profile.created_endp:
                    logger.info("Stopping desktop CXs...")
                    self.generic_endps_profile.stop_cx()
            except Exception as e:
                logger.warning(f"Desktop CX stop error (ignored): {e}")

            # Stop Android CXs
            try:
                for profile in getattr(self, "android_profiles", []):
                    if profile.created_endp:
                        logger.info(f"Stopping Android CXs for {profile.name_prefix}...")
                        profile.stop_cx()
            except Exception as e:
                logger.warning(f"Android CX stop error (ignored): {e}")

            # Cleanup Desktop endpoints
            try:
                if self.generic_endps_profile.created_endp:
                    logger.info("Cleaning up desktop endpoints...")
                    self.generic_endps_profile.cleanup()
            except Exception as e:
                logger.warning(f"Desktop cleanup error (ignored): {e}")

            # Cleanup Android endpoints
            try:
                for profile in getattr(self, "android_profiles", []):
                    if profile.created_endp:
                        logger.info(f"Cleaning up Android endpoints for {profile.name_prefix}...")
                        profile.cleanup()
            except Exception as e:
                logger.warning(f"Android cleanup error (ignored): {e}")

            # Clear internal tracking
            self.generic_endps_profile.created_cx = []
            self.generic_endps_profile.created_endp = []

            if hasattr(self, "android_profiles"):
                self.android_profiles.clear()

            logger.info("Cleanup completed successfully.")

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")




def main():
    try:
        parser = argparse.ArgumentParser(
            prog="lf_interop_youtubeshorts.py",
            formatter_class=argparse.RawTextHelpFormatter,
            description="LANforge YouTube Shorts Automation"
        )

        # Required arguments
        parser.add_argument("--mgr", required=True, help="LANforge manager IP")
        parser.add_argument("--mgr_port", default=8080, help="LANforge HTTP port")
        parser.add_argument("--duration", type=int, required=True,
                            help="Total test duration in seconds")
        parser.add_argument("--scroll", type=int, required=True,
                            help="Scroll interval in seconds (time between moving to next Short)")
        parser.add_argument("--flask_ip", required=True,
                            help="IP where Flask server will run")

        # Optional
        parser.add_argument("--resources", help="Comma-separated device EIDs like 1.5,1.15")
        parser.add_argument("--debug", action="store_true", help="Enable debugging")

        # Cleanup toggles
        parser.add_argument("--no_pre_cleanup", action="store_true",
                            help="Skip cleanup BEFORE test")
        parser.add_argument("--no_post_cleanup", action="store_true",
                            help="Skip cleanup AFTER test")

        args = parser.parse_args()


        # Enable debug logs
        if args.debug:
            logger.setLevel(logging.DEBUG)

        # Load LANforge device info
        Devices = RealDevice(manager_ip=args.mgr, selected_bands=[])
        Devices.get_devices()

        # Create Shorts automation object
        yt = YouTubeShorts(
            host=args.mgr,
            port=args.mgr_port,
            duration=args.duration,
            scroll=args.scroll,
            flask_ip=args.flask_ip,
            debug=args.debug
        )

       
        # Start Flask server
        yt.start_flask_server()
        time.sleep(1)

        # Clear previous test stats
        yt.clear_previous_data()

        # PRE-CLEANUP (optional)
       
        if not args.no_pre_cleanup:
            logging.info("Running pre-test cleanup...")
            yt.cleanup()
        else:
            logging.info("Skipping pre-test cleanup.")

        # SELECT DEVICES
      
        if args.resources:
            # User provided device list
            real_sta_list = [r.strip() for r in args.resources.split(",")]
            yt.select_real_devices(
                real_devices=Devices,
                real_sta_list=real_sta_list,
                base_interop_obj=Devices
            )
        else:
            # No resources mentioned →  call query_user() in selectrealdevice function
            yt.select_real_devices(
                real_devices=Devices,
                real_sta_list=None,
                base_interop_obj=Devices
            )
        
        # ---------------- ANDROID SELECTION (FIXED)

        yt.mobile_devices = []

        if getattr(yt, "selected_android_realstas", []):
            yt.mobile_devices = yt.get_android_serials_from_deviceconfig()

        logger.info(f"FINAL Android devices selected (mapped): {yt.mobile_devices}")


        logger.info(
        f"RUN SUMMARY → desktops={yt.real_sta_list}, androids={yt.mobile_devices}"
        )
       
        logger.info(f"Desktop devices selected: {yt.real_sta_list}")
        logger.info(f"Android devices selected: {yt.mobile_devices}")
        # Create desktop endpoints (if any)
        if yt.real_sta_list:
            yt.create_generic_endp(yt.real_sta_list)

        # Create android endpoints (if any)
        if yt.mobile_devices:
            yt.create_android_generic_endp()

        # Check if generic tab exists in LANforge
        if not yt.check_tab_exists():
            logging.error("LANforge generic tab missing. Aborting.")
            return

        # Start LANforge connections (scripts launch on devices)
        yt.start_generic()

        logging.info("=== YouTube Shorts Test Started ===")
        logging.info(f"Duration: {args.duration} seconds")
        logging.info(f"Scroll count: {args.scroll}")
        logging.info(f"Devices: {yt.real_sta_hostname}")
        logging.info(f"Android devices: {yt.mobile_devices}")

        # Monitoring loop (heart of the test)
        yt.monitoring_loop()

        logging.info("=== Test Completed ===")

        # Stop connections after monitoring loop ends
        yt.stop_generic_cx()

        
        # POST-CLEANUP (optional)

        if not args.no_post_cleanup:
            logging.info("Running post-test cleanup...")
            yt.cleanup()
        else:
            logging.info("Skipping post-test cleanup.")

        # Final shutdown
        yt.shutdown()

    except Exception as e:
        logging.error(f"Fatal error in main(): {e}")
        traceback.print_exc()

        try:
            yt.shutdown()
        except:
            os._exit(1)
if __name__ == "__main__":
    main()






