
import json
import sys
import os
import csv
import time
import shutil
import importlib
import logging
import paramiko
import argparse
import pandas as pd
from datetime import datetime
from tabulate import tabulate
import threading

logger = logging.getLogger(__name__)

if sys.version_info[0] != 3:
    print("This script requires Python3")
    exit()

if 'py-json' not in sys.path:
    sys.path.append(os.path.join(os.path.abspath('..'), 'py-json'))

from lf_graph import lf_bar_graph
from lf_report import lf_report
from lf_base_robo import RobotClass

realm = importlib.import_module("py-json.realm")
Realm = realm.Realm

class SpeedTest(Realm):
    def __init__(self, 
            manager_ip=None, 
            port=8080, 
            device_list=None,
            instance="Speed_Test_Report",
            iteration=1,
            do_interopability=False,
            dowebgui=False,
            type='ookla',
            result_dir='local',
            _debug_on=False,
            robot_test=False,
            robot_ip=None,
            coordinate=None,
            rotation=None):
        super().__init__(lfclient_host=manager_ip,
                        debug_=_debug_on)
        self.manager_ip = manager_ip
        self.manager_port = port
        self.device_list = device_list
        self.instance = instance
        self.iteration = iteration
        self.do_interopability = do_interopability
        self.dowebgui = dowebgui
        self.result_dir = result_dir
        self.type=type
        self.devices_data = {}
        self.android_data = {}
        self.laptop_data = {}
        self.generic_endps_profile = self.new_generic_endp_profile()
        self.generic_endps_profile.type = 'generic'
        self.generic_endps_profile.cmd = ' '
        self.result_json = {}
        self.stop_time = None
        self.start_time = None
        self.device_info = {}

        self._ingest_lock = threading.Lock()
        self._flask_thread = None
        self._post_url = None

        self.robot_test = robot_test
        self.robot_ip = robot_ip
        self.robot_port = 5000
        self.coordinate = coordinate
        self.rotation = rotation
        
        self.coordinate_list = coordinate.split(',') if coordinate else []
        self.rotation_list = rotation.split(',') if rotation else []
        
        self.current_coordinate = None
        self.current_rotation = None
        self.robot_iteration_count = 0
        self.total_robot_tests = 0
        
        if self.robot_test:
            if self.rotation_list and self.rotation_list[0] != "":
                self.total_robot_tests = len(self.coordinate_list) * len(self.rotation_list)
            else:
                self.total_robot_tests = len(self.coordinate_list)

        if  self.coordinate is not None: 
            base_dir = os.path.dirname(os.path.dirname(self.result_dir))
            nav_data = os.path.join(base_dir, 'nav_data.json') # To generate nav_data.json in webgui folder
            with open(nav_data, "w") as file:
                json.dump({}, file)

            self.robot_obj = RobotClass(robo_ip=self.robot_ip)
            self.robot_obj.robo_ip = f"{self.robot_ip}" # for Fake server testing use port :{self.robot_port}
            self.robot_obj.nav_data_path=nav_data
            self.robot_obj.runtime_dir=self.result_dir
            self.robot_obj.ip=self.robot_ip
            self.robot_obj.testname=self.instance
            # self.rotation_list = self.robot_obj.angles_to_radians(self.rotation_list)

        print('Initiating Server for WebGUI Ingest')
        self.change_port_to_ip()
        self._post_url = f"http://{self.manager_ip}:5050/api/speedtest"
        self._start_ingest_server() 

        #reporting variable
        self.selected_device_type = set()
        self.selected_resources = None
        self.ip_hostname = {}
        self.result_dict = {
                            'ip':[],
                            'hostname':[],
                            'download_speed':[],
                            'upload_speed':[],
                            'download_lat':[],
                            'upload_lat':[]
                        }
        self.iteration_dict = {}

    def get_expected_post_ips(self):
        """Get list of IPs expected to POST results"""
        want = []
        for info in self.devices_data.values():
            cmd = (info.get('cmd') or '')
            ip = (info.get('ip') or '')
            if ip and '--post_url' in cmd:
                want.append(ip)
        # de-dup (stable)
        seen, out = set(), []
        for ip in want:
            if ip not in seen:
                seen.add(ip)
                out.append(ip)
        return out

    def has_post_for(self, ip):
        """Check if we have received POST for given IP"""
        k = ip.replace('.', '_')
        return (k in self.result_json) or (ip in self.result_json)

    def write_robot_results_to_csv(self, test_number, csv_file):
        """Write results to CSV with robot-specific columns"""

        csv_exists = os.path.isfile(csv_file)
        csv_data = []
        table_data = []

        # Normalize keys we received this test
        received = {}
        for raw_ip, data in self.result_json.items():
            ip = raw_ip.replace('_', '.')
            received[ip] = {
                "download": data.get("download", "N/A"),
                "upload": data.get("upload", "N/A"),
                "Idle Latency": data.get("Idle Latency", "N/A"),
                "Download Latency": data.get("Download Latency", "N/A"),
                "Upload Latency": data.get("Upload Latency", "N/A"),
            }

        # Expected devices
        expected_ips = list(self.ip_hostname.keys()) or list(self.device_info.keys())

        # Emit rows for devices
        for ip, data in received.items():
            dev_type = self.device_info.get(ip, "N/A")
            hostname_safe = self.ip_hostname.get(ip, ip)

            download = data["download"]
            upload = data["upload"]
            idle_latency = data["Idle Latency"]
            down_latency = data["Download Latency"]
            up_latency = data["Upload Latency"]

            # Add robot-specific columns
            csv_data.append([
                test_number,
                self.total_robot_tests,  # Total robot tests
                self.current_coordinate,
                self.current_rotation,
                ip,
                dev_type,
                download,
                upload,
                idle_latency,
                down_latency,
                up_latency
            ])

            table_data.append([
                test_number,
                self.total_robot_tests,
                self.current_coordinate,
                self.current_rotation,
                ip,
                dev_type,
                download,
                upload,
                idle_latency,
                down_latency,
                up_latency
            ])

        # Handle missing devices
        missing_ips = [ip for ip in expected_ips if ip not in received]
        for ip in missing_ips:
            dev_type = self.device_info.get(ip, "N/A")
            hostname_safe = self.ip_hostname.get(ip, ip)
            
            csv_data.append([
                test_number,
                self.total_robot_tests,
                self.current_coordinate,
                self.current_rotation,
                ip,
                dev_type,
                "N/A", "N/A", "N/A", "N/A", "N/A"
            ])
            table_data.append([
                test_number,
                self.total_robot_tests,
                self.current_coordinate,
                self.current_rotation,
                ip,
                dev_type,
                "N/A", "N/A", "N/A", "N/A", "N/A"
            ])

        # Append to CSV
        with open(csv_file, "a", newline="") as csvfile:
            writer = csv.writer(csvfile)
            if not csv_exists:
                writer.writerow([
                    "Robot Test Number", "Total Robot Tests", "Coordinate", "Rotation",
                    "IP", "Device Type", "Download", "Upload", 
                    "Idle Latency", "Download Latency", "Upload Latency"
                ])
            writer.writerows(csv_data)

        # Print table
        print(f"\n Robot Speedtest Results for Test #{test_number}")
        try:
            from tabulate import tabulate
            print(tabulate(
                table_data,
                headers=[
                    "Test#", "Total", "Coordinate", "Rotation", "IP", "Device Type",
                    "Download", "Upload", "Idle Latency", "Download Latency", "Upload Latency"
                ],
                tablefmt="fancy_grid",
                disable_numparse=True
            ))
        except Exception:
            headers = [
                "Test#", "Total", "Coordinate", "Rotation", "IP", "Device Type",
                "Download", "Upload", "Idle Latency", "Download Latency", "Upload Latency"
            ]
            print("\t".join(headers))
            for row in table_data:
                print("\t".join(str(item) for item in row))

        if missing_ips:
            print(f"[NOTE] No data received for robot test {test_number} from: {', '.join(missing_ips)}")
        print("=" * 158)

    def store_robot_results_in_iteration_dict(self, test_number):
        """Store robot test results in iteration_dict for report generation"""

        # Initialize the result_dict for this test
        self.result_dict = {
            'ip': [],
            'hostname': [],
            'download_speed': [],
            'upload_speed': [],
            'download_lat': [],
            'upload_lat': []
        }

        # Process received results
        received = {}
        for raw_ip, data in self.result_json.items():
            ip = raw_ip.replace('_', '.')
            received[ip] = {
                "download": data.get("download", "N/A"),
                "upload": data.get("upload", "N/A"),
                "Idle Latency": data.get("Idle Latency", "N/A"),
                "Download Latency": data.get("Download Latency", "N/A"),
                "Upload Latency": data.get("Upload Latency", "N/A"),
            }

        # Expected devices
        expected_ips = list(self.ip_hostname.keys()) or list(self.device_info.keys())

        # Store data for devices that reported
        for ip, data in received.items():
            dev_type = self.device_info.get(ip, "N/A")
            hostname_safe = self.ip_hostname.get(ip, ip)

            download = data["download"]
            upload = data["upload"]
            idle_latency = data["Idle Latency"]
            down_latency = data["Download Latency"]
            up_latency = data["Upload Latency"]

            # Accumulate into per-iter dicts for graphs/tables
            self.result_dict['ip'].append(ip)
            self.result_dict['hostname'].append(hostname_safe)

            def _num(x):
                try:
                    # Handles values like "24.2 Mbps" or "114 ms" or "N/A"
                    return float(str(x).split()[0])
                except Exception:
                    return 0.0

            self.result_dict['download_speed'].append(_num(download))
            self.result_dict['upload_speed'].append(_num(upload))
            self.result_dict['download_lat'].append(_num(down_latency))
            self.result_dict['upload_lat'].append(_num(up_latency))

        # Handle missing devices
        missing_ips = [ip for ip in expected_ips if ip not in received]
        for ip in missing_ips:
            dev_type = self.device_info.get(ip, "N/A")
            hostname_safe = self.ip_hostname.get(ip, ip)

            # For graphs: use zeros so categories & lengths stay aligned
            self.result_dict['ip'].append(ip)
            self.result_dict['hostname'].append(hostname_safe)
            self.result_dict['download_speed'].append(0.0)
            self.result_dict['upload_speed'].append(0.0)
            self.result_dict['download_lat'].append(0.0)
            self.result_dict['upload_lat'].append(0.0)

        # Store in iteration_dict using test_number as key
        self.iteration_dict[test_number] = self.result_dict.copy()

        print(f"Stored robot test {test_number} data in iteration_dict")
        print(f"Data: {self.iteration_dict[test_number]}")

    def perform_single_robot_test(self, test_number, csv_file):
        """Execute a single speed test for robot testing"""

        print(f"Starting speed test for robot test #{test_number}")

        self.start_generic()
        print(f"Test started at {self.start_time}")
        time.sleep(50)  # Speedtest duration wait time
        self.stop_generic()
        time.sleep(20)

        # Wait for posts from all expected devices
        expected_ips = self.get_expected_post_ips()
        deadline = time.time() + 120
        while time.time() < deadline:
            got = [ip for ip in expected_ips if self.has_post_for(ip)]
            if len(got) >= len(expected_ips):
                break
            time.sleep(1)

        # Store results in iteration_dict for report generation
        self.store_robot_results_in_iteration_dict(test_number)

        # Write results with robot metadata
        self.write_robot_results_to_csv(test_number, csv_file)
        self.result_json = {}

    def perform_robot_testing(self, csv_file):
        """Execute robot tests based on coordinates and rotations"""
        test_count = 0
        # Condition 1: Both coordinates and rotations provided
        if self.rotation_list and self.rotation_list[0] != "":
            for coord in self.coordinate_list:
                coord = coord.strip()
                print(f"Moving to coordinate: {coord}")
                robo_moved, abort = self.robot_obj.move_to_coordinate(coord)

                if robo_moved:
                    for angle in self.rotation_list:
                        pause_coord,test_stopped_by_user=self.robot_obj.wait_for_battery(self.cleanup)
                        if pause_coord:
                            print("Robot battery low. Pausing at current location to charge.")
                            exit(0)

                        # angle = angle.strip()
                        print(f"Rotating to angle: {angle}")
                        robo_rotated = self.robot_obj.rotate_angle(angle)

                        if robo_rotated:
                            test_count += 1
                            self.current_coordinate = coord
                            self.current_rotation = angle
                            self.robot_iteration_count = test_count

                            print(f"Starting robot test {test_count}/{self.total_robot_tests}")
                            print(f"Coordinate: {coord}, Rotation: {angle}")

                            # Perform the speed test
                            self.perform_single_robot_test(test_count, csv_file)
                        else:
                            print(f"Failed to rotate to angle {angle}")
                else:
                    print(f"Failed to move to coordinate {coord}")

        # Condition 2: Only coordinates provided (no rotations)
        else:
            for coord in self.coordinate_list:
                pause_coord,test_stopped_by_user=self.robot_obj.wait_for_battery(self.cleanup)
                if pause_coord:
                    print("Robot battery low. Pausing at current location to charge.")
                    exit(0)

                coord = coord.strip()
                print(f"Moving to coordinate: {coord}")
                robo_moved = self.robot_obj.move_to_coordinate(coord)
                if robo_moved:
                    test_count += 1
                    self.current_coordinate = coord
                    self.current_rotation = "None"  # No rotation
                    self.robot_iteration_count = test_count

                    print(f"Starting robot test {test_count}/{self.total_robot_tests}")
                    print(f"Coordinate: {coord}, Rotation: None")

                    # Perform the speed test
                    self.perform_single_robot_test(test_count, csv_file)
                else:
                    print(f"Failed to move to coordinate {coord}")
        print(f"Completed {test_count} robot tests")

    def change_port_to_ip(self):
            if self.manager_ip.count('.') != 3:
                target_port_list = self.name_to_eid(self.manager_ip)
                shelf, resource, port, _ = target_port_list
                try:
                    target_port_ip = self.json_get(f'/port/{shelf}/{resource}/{port}?fields=ip')['interface']['ip']
                    self.manager_ip = target_port_ip
                except BaseException:
                    logging.warning(f'The Server port is not an ethernet port. Proceeding with the given {self.manager_ip}.')
                logging.info(f"Server port IP {self.manager_ip}")
            else:
                logging.info(f"Server port IP {self.manager_ip}")

            self.manager_ip = self.manager_ip

    def _start_ingest_server(self):
        try:
            from flask import Flask, request, jsonify
        except Exception:
            print("[WARN] Flask not installed; ingest disabled.")
            return

        app = Flask(__name__)
        parent = self

        @app.get("/api/health")
        def health():
            return jsonify({"ok": True, "ts": time.time()}), 200

        @app.route("/api/speedtest", methods=["POST"])
        def _ingest():
            try:
                payload = request.get_json(force=True) or {}
                ip  = (payload.get("ip") or "").strip()
                host = payload.get("hostname")
                key = ip.replace('.', '_') if ip else (payload.get("device_id") or payload.get("serial"))
                rec = {
                    "download":               f"{payload.get('download_mbps','0')} Mbps",
                    "upload":                 f"{payload.get('upload_mbps','0')} Mbps",
                    "Idle Latency":           f"{payload.get('idle_ms','0')} ms",
                    "Download Latency":       f"{payload.get('download_latency_ms','0')} ms",
                    "Upload Latency":         f"{payload.get('upload_latency_ms','0')} ms",
                    "source":                 "ingest"
                }

                print('[POST] got payload for key:', key, rec)
                with parent._ingest_lock:
                    parent.result_json[key] = rec
                    if ip and host:
                        parent.ip_hostname[ip] = host
                print("[INGEST] stored under key:", key)
                return jsonify({"stored": True}), 200
            except Exception as e:
                return jsonify({"stored": False, "error": str(e)}), 400

        @app.get("/api/data")
        def data():
            return jsonify(parent.result_json), 200

        def run():
            # IMPORTANT: bind to all interfaces so other machines clear
            #  POST
            app.run(host=self.manager_ip, port=5050, debug=True, use_reloader=False)

        import threading
        self._flask_thread = threading.Thread(target=run, daemon=True)
        self._flask_thread.start()

    def _ssh_connect(self, host, username, password):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=username, password=password)
        return ssh

    def get_device_data(self, resource_data):
        """
        get_devices_data:
        - /ports/all  ? ssid/channel/mac and the WLAN port key (e.g. '1.11.wlan0')
        - selected resource_data ? ctrl-ip, device type, box hostname
        - /adb/all    ? Android serial (name), user-name (friendly host), wifi mac
        """
        resource_ids = set(resource_data.keys())

        ports = self.json_get('/ports/all').get('interfaces', [])
        adb_devices_list = self.json_get('/adb/all')

        adb_by_resource = {}
        devices = adb_devices_list.get("devices", {})
        print(devices, ports)
        # {} [{'1.1.eth0': {'4way time (us)': '0', 'activity': 0.0, 'aid': '', 'alias': 'eth0', 'anqp time (us)': '0', 'ap': '', 'avg chain rssi': '', 'beacon': '0', 'bps rx': 187687, 'bps rx ll': 201480, 'bps tx': 597274, 'bps tx ll': 612370, 'bss color': '', 'bytes rx ll': 507391741, 'bytes tx ll': 225118890, 'center frequency': '', 'chain rssi': '', 'channel': '[channel: 0]', 'collisions': 0, 'connections': '0', 'crypt': '0', 'cx ago': '0', 'cx time (us)': '0', 'device': 'eth0', 'dhcp (ms)': 0, 'down': False, 'entity id': 'NA', 'gateway ip': '192.168.204.1', 'hardware': 'e1000e', 'ip': '192.168.204.75', 'ipv6 address': 'fe80::203:2dff:fe3f:7d02/64', 'ipv6 gateway': 'DELETED', 'key/phrase': '', 'login-fail': 0, 'login-ok': 0, 'logout-fail': 0, 'logout-ok': 0, 'mac': '00:03:2d:3f:7d:02', 'mask': '255.255.252.0', 'misc': '0', 'mode': '', 'mtu': '1500', 'no cx (us)': '0', 'noise': '', 'parent dev': '', 'phantom': False, 'port': '1.001.0', 'port type': 'Ethernet', 'pps rx': 71, 'pps tx': 78, 'qlen': '1000', 'reset': 'Complete', 'retry failed': '0', 'rf loss': '', 'rx bytes': 474663349, 'rx crc': 0, 'rx drop': 22137, 'rx errors': 0, 'rx fifo': 0, 'rx frame': 0, 'rx length': 0, 'rx miss': 0, 'rx over': 0, 'rx pkts': 1364810, 'rx-rate': '100 Mbps', 'sec': 0, 'security': '', 'signal': '', 'ssid': '', 'status': '', 'time-stamp': '2025-11-11 11:38:47.381', 'tx abort': 0, 'tx bytes': 212240658, 'tx crr': 0, 'tx errors': 0, 'tx fifo': 0, 'tx hb': 0, 'tx pkts': 537453, 'tx wind': 0, 'tx-failed %': '0', 'tx-rate': '100 Mbps', 'wifi retries': '0'}}, {'1.1.eth1': {'4way time (us)': '0', 'activity': 0.0, 'aid': '', 'alias': 'eth1', 'anqp time (us)': '0', 'ap': '', 'avg chain rssi': '', 'beacon': '0', 'bps rx': 3924, 'bps rx ll': 5326, 'bps tx': 0, 'bps tx ll': 0, 'bss color': '', 'bytes rx ll': 37788901, 'bytes tx ll': 2215434706, 'center frequency': '', 'chain rssi': '', 'channel': '[channel: 1]', 'collisions': 0, 'connections': '0', 'crypt': '0', 'cx ago': '0', 'cx time (us)': '0', 'device': 'eth1', 'dhcp (ms)': 33544, 'down': False, 'entity id': 'NA', 'gateway ip': '0.0.0.0', 'hardware': 'igb', 'ip': '192.168.204.53', 'ipv6 address': 'fe80::203:2dff:fe3f:7d03/64', 'ipv6 gateway': 'DELETED', 'key/phrase': '', 'login-fail': 0, 'login-ok': 0, 'logout-fail': 0, 'logout-ok': 0, 'mac': '00:03:2d:3f:7d:03', 'mask': '255.255.252.0', 'misc': '0', 'mode': '', 'mtu': '1500', 'no cx (us)': '0', 'noise': '', 'parent dev': '', 'phantom': False, 'port': '1.001.1', 'port type': 'Ethernet', 'pps rx': 7, 'pps tx': 0, 'qlen': '1000', 'reset': 'Complete', 'retry failed': '0', 'rf loss': '', 'rx bytes': 27848725, 'rx crc': 0, 'rx drop': 0, 'rx errors': 0, 'rx fifo': 0, 'rx frame': 0, 'rx length': 0, 'rx miss': 0, 'rx over': 0, 'rx pkts': 414178, 'rx-rate': '1 Gbps', 'sec': 0, 'security': '', 'signal': '', 'ssid': '', 'status': '', 'time-stamp': '2025-11-11 11:38:50.257', 'tx abort': 0, 'tx bytes': 2180857498, 'tx crr': 0, 'tx errors': 0, 'tx fifo': 0, 'tx hb': 0, 'tx pkts': 1440719, 'tx wind': 0, 'tx-failed %': '0', 'tx-rate': '1 Gbps', 'wifi retries': '0'}}, {'1.1.wiphy0': {'4way time (us)': 0, 'activity': 0, 'aid': 0, 'alias': 'wiphy0', 'anqp time (us)': 0, 'ap': '', 'avg chain rssi': '', 'beacon': 0, 'bps rx': 0, 'bps rx ll': 0, 'bps tx': 0, 'bps tx ll': 0, 'bss color': 0, 'bytes rx ll': 0, 'bytes tx ll': 0, 'center frequency': 0, 'chain rssi': '', 'channel': '-1', 'collisions': 0, 'connections': 0, 'crypt': 0, 'cx ago': '0', 'cx time (us)': 0, 'device': 'wiphy0', 'dhcp (ms)': 0, 'down': False, 'entity id': 'NA', 'gateway ip': '0.0.0.0', 'hardware': '988x', 'ip': '0.0.0.0', 'ipv6 address': 'DELETED', 'ipv6 gateway': 'DELETED', 'key/phrase': '', 'login-fail': 0, 'login-ok': 0, 'logout-fail': 0, 'logout-ok': 0, 'mac': '04:f0:21:89:cd:f4', 'mask': '0.0.0.0', 'misc': 0, 'mode': '802.11abgn-AC', 'mtu': '1500', 'no cx (us)': 0, 'noise': '', 'parent dev': '', 'phantom': False, 'port': '1.001.2', 'port type': 'WIFI-Radio', 'pps rx': 0, 'pps tx': 0, 'qlen': '0', 'reset': 'Complete', 'retry failed': 0, 'rf loss': '0', 'rx bytes': 0, 'rx crc': 0, 'rx drop': 0, 'rx errors': 0, 'rx fifo': 0, 'rx frame': 0, 'rx length': 0, 'rx miss': 0, 'rx over': 0, 'rx pkts': 0, 'rx-rate': '360 Kbps', 'sec': 0, 'security': '', 'signal': '', 'ssid': '', 'status': '', 'time-stamp': '2025-11-11 11:38:50.419', 'tx abort': 0, 'tx bytes': 0, 'tx crr': 0, 'tx errors': 0, 'tx fifo': 0, 'tx hb': 0, 'tx pkts': 0, 'tx wind': 0, 'tx-failed %': 0.0, 'tx-rate': '', 'wifi retries': 0}}, {'1.23.umts_dm0': {'4way time (us)': '0', 'activity': 0.0, 'aid': '', 'alias': 'umts_dm0', 'anqp time (us)': '0', 'ap': '', 'avg chain rssi': '', 'beacon': '0', 'bps rx': 0, 'bps rx ll': 0, 'bps tx': 0, 'bps tx ll': 0, 'bss color': '', 'bytes rx ll': 0, 'bytes tx ll': 0, 'center frequency': '', 'chain rssi': '', 'channel': '[channel: 2]', 'collisions': 0, 'connections': '0', 'crypt': '0', 'cx ago': '0', 'cx time (us)': '0', 'device': 'umts_dm0', 'dhcp (ms)': 0, 'down': True, 'entity id': 'NA', 'gateway ip': '0.0.0.0', 'hardware': 'Unknown', 'ip': '0.0.0.0', 'ipv6 address': 'DELETED', 'ipv6 gateway': 'DELETED', 'key/phrase': '', 'login-fail': 0, 'login-ok': 0, 'logout-fail': 0, 'logout-ok': 0, 'mac': '00:00:00:00:00:00', 'mask': '0.0.0.0', 'misc': '0', 'mode': '', 'mtu': '1500', 'no cx (us)': '0', 'noise': '', 'parent dev': '', 'phantom': False, 'port': '1.023.2', 'port type': 'Ethernet', 'pps rx': 0, 'pps tx': 0, 'qlen': '1000', 'reset': 'Complete', 'retry failed': '0', 'rf loss': '', 'rx bytes': 0, 'rx crc': 0, 'rx drop': 0, 'rx errors': 0, 'rx fifo': 0, 'rx frame': 0, 'rx length': 0, 'rx miss': 0, 'rx over': 0, 'rx pkts': 0, 'rx-rate': '0 bps', 'sec': 0, 'security': '', 'signal': '', 'ssid': '', 'status': '', 'time-stamp': '2025-11-11 11:38:44.891', 'tx abort': 0, 'tx bytes': 0, 'tx crr': 0, 'tx errors': 0, 'tx fifo': 0, 'tx hb': 0, 'tx pkts': 0, 'tx wind': 0, 'tx-failed %': '0', 'tx-rate': '0 bps', 'wifi retries': '0'}}, {'1.23.wiphy0': {'4way time (us)': 0, 'activity': 0, 'aid': 0, 'alias': 'wiphy0', 'anqp time (us)': 0, 'ap': '', 'avg chain rssi': '', 'beacon': 0, 'bps rx': 0, 'bps rx ll': 0, 'bps tx': 0, 'bps tx ll': 0, 'bss color': 0, 'bytes rx ll': 0, 'bytes tx ll': 0, 'center frequency': 0, 'chain rssi': '', 'channel': '0', 'collisions': 0, 'connections': 0, 'crypt': 0, 'cx ago': '0', 'cx time (us)': 0, 'device': 'wiphy0', 'dhcp (ms)': 0, 'down': False, 'entity id': 'NA', 'gateway ip': '0.0.0.0', 'hardware': 'Unknown', 'ip': '0.0.0.0', 'ipv6 address': 'DELETED', 'ipv6 gateway': 'DELETED', 'key/phrase': '', 'login-fail': 0, 'login-ok': 0, 'logout-fail': 0, 'logout-ok': 0, 'mac': '6e:ee:10:dd:e2:38', 'mask': '0.0.0.0', 'misc': 0, 'mode': '802.11bg', 'mtu': '1500', 'no cx (us)': 0, 'noise': '', 'parent dev': '', 'phantom': False, 'port': '1.023.1', 'port type': 'WIFI-Radio', 'pps rx': 0, 'pps tx': 0, 'qlen': '1000', 'reset': 'Complete', 'retry failed': 0, 'rf loss': '0', 'rx bytes': 0, 'rx crc': 0, 'rx drop': 0, 'rx errors': 0, 'rx fifo': 0, 'rx frame': 0, 'rx length': 0, 'rx miss': 0, 'rx over': 0, 'rx pkts': 0, 'rx-rate': '0 bps', 'sec': 0, 'security': '', 'signal': '', 'ssid': '', 'status': '', 'time-stamp': '2025-11-11 11:38:50.181', 'tx abort': 0, 'tx bytes': 0, 'tx crr': 0, 'tx errors': 0, 'tx fifo': 0, 'tx hb': 0, 'tx pkts': 0, 'tx wind': 0, 'tx-failed %': 0.0, 'tx-rate': '', 'wifi retries': 0}}, {'1.23.wlan0': {'4way time (us)': 0, 'activity': 0, 'aid': 0, 'alias': 'wlan0', 'anqp time (us)': 0, 'ap': '94:A6:7E:74:26:33', 'avg chain rssi': '', 'beacon': 0, 'bps rx': 15059, 'bps rx ll': 0, 'bps tx': 31636, 'bps tx ll': 0, 'bss color': 0, 'bytes rx ll': 0, 'bytes tx ll': 0, 'center frequency': 0, 'chain rssi': '', 'channel': '149', 'collisions': 0, 'connections': 0, 'crypt': 0, 'cx ago': '0', 'cx time (us)': 1684000, 'device': 'wlan0', 'dhcp (ms)': 0, 'down': False, 'entity id': 'NA', 'gateway ip': '192.168.204.1', 'hardware': 'Unknown', 'ip': '192.168.204.54', 'ipv6 address': 'fe80::6cee:10ff:fedd:e238/64', 'ipv6 gateway': 'DELETED', 'key/phrase': '', 'login-fail': 0, 'login-ok': 0, 'logout-fail': 0, 'logout-ok': 0, 'mac': '6e:ee:10:dd:e2:38', 'mask': '255.255.252.0', 'misc': 0, 'mode': 'AUTO 20 ', 'mtu': '1500', 'no cx (us)': 980000, 'noise': '', 'parent dev': 'wiphy0', 'phantom': False, 'port': '1.023.0', 'port type': 'WIFI-STA', 'pps rx': 11, 'pps tx': 3, 'qlen': '1000', 'reset': 'Complete', 'retry failed': 0, 'rf loss': '0', 'rx bytes': 4188260, 'rx crc': 0, 'rx drop': 0, 'rx errors': 0, 'rx fifo': 0, 'rx frame': 0, 'rx length': 0, 'rx miss': 0, 'rx over': 0, 'rx pkts': 22371, 'rx-rate': '263 Mbps', 'sec': 0, 'security': 'Open', 'signal': '-34', 'ssid': 'NETGEAR_5G_wpa2', 'status': 'Authorized', 'time-stamp': '2025-11-11 11:38:50.170', 'tx abort': 0, 'tx bytes': 5896305, 'tx crr': 0, 'tx errors': 0, 'tx fifo': 0, 'tx hb': 0, 'tx pkts': 5891, 'tx wind': 0, 'tx-failed %': 0.0, 'tx-rate': '263 Mbps', 'wifi retries': 0}}]
        if isinstance(devices, list):
            for dev in devices:
                if not isinstance(dev, dict):
                    continue
                key = next(iter(dev))
                info = dev[key]
                rid = info.get("resource-id")
                if rid:
                    adb_by_resource[rid] = {
                        'name': info.get('name'),
                        'serial': info.get('name') or '',
                        'shelf_resource': (info.get('name') or '').rsplit('.', 1)[0],
                        'user_name': info.get('user-name'),
                        'wifi_mac': info.get('wifi mac'),
                        'device_type': info.get('device-type', 'Android')
                    }
        elif isinstance(devices, dict):
            rid = devices.get("resource-id")
            if rid:
                adb_by_resource[rid] = {
                    'name': devices.get('name'),
                    'serial': devices.get('name') or '',
                    'shelf_resource': (devices.get('name') or '').rsplit('.', 1)[0],
                    'user_name': devices.get('user-name'),
                    'wifi_mac': devices.get('wifi mac'),
                    'device_type': devices.get('device-type', 'Android')
                }

        print(adb_by_resource)


        def merge_preferring_non_empty(dst: dict, src: dict) -> dict:
            for k, v in (src or {}).items():
                if v not in (None, ''):
                    if dst.get(k) in (None, ''):
                        dst[k] = v
            return dst

        devices_data = {}

        # From /ports/all: capture WLAN ports only, skip phantom/down
        for pd in ports:
            port_id = next(iter(pd))
            pdata = pd[port_id]

            parts = port_id.split('.')
            if len(parts) < 3:
                continue
            resource = '.'.join(parts[:2])

            if resource not in resource_ids:
                continue

            try:
                if pdata.get('phantom', True) or pdata.get('down', True):
                    continue
                if pdata.get('parent dev') != 'wiphy0':
                    continue
            except Exception:
                continue

            res = resource_data[resource]
            dev_type = res.get('device type')
            ctrl_ip = res.get('ctrl-ip')
            box_hostname = res.get('hostname')

            if not ctrl_ip:
                continue

            devices_data[port_id] = {
                'device type': dev_type,
                'cmd': None,
                'ip': ctrl_ip,
                'serial': None,
                'hostname': box_hostname,
                'ssid': pdata.get('ssid'),
                'channel': pdata.get('channel'),
                'mac': pdata.get('mac'),
                'port': resource,
            }

            # For reporting lookups
            if ctrl_ip and box_hostname:    
                self.ip_hostname[ctrl_ip] = box_hostname

        # ---- From /adb/all: move Android rows to a single row keyed by SERIAL
        for rid in resource_ids:
            res = resource_data[rid]
            if (res.get('device type') or '').lower() != 'android':
                continue

            ctrl_ip = res.get('ctrl-ip')
            adb = adb_by_resource.get(rid)
            if not adb:
                continue

            serial_key = adb.get('serial').split('.')[-1]  # e.g. R9ZW9098RMZ
            port_key = f"{rid}.wlan0"                      # e.g. 1.11.wlan0

            wlan_row = devices_data.pop(port_key, {})  # <? deletes 1.xx.wlan0 if present

            # Start the serial row with sane defaults
            serial_row = {
                'device type': 'Android',
                'cmd': None,
                'ip': ctrl_ip or wlan_row.get('ip'),
                'port': adb.get('shelf_resource'),
                'serial': serial_key,
                'hostname': adb.get('user_name') or res.get('hostname') or wlan_row.get('hostname') or res.get('user'),
                'ssid': wlan_row.get('ssid'),
                'channel': wlan_row.get('channel'),
                'mac': adb.get('wifi_mac') or wlan_row.get('mac'),
            }

            # If we had already created a serial row, merge non-empty fields into it
            if serial_key in devices_data:
                serial_row = merge_preferring_non_empty(devices_data[serial_key], serial_row)

            devices_data[serial_key] = serial_row

            # Prefer hostname for reporting
            if ctrl_ip and adb.get('user_name'):
                self.ip_hostname[ctrl_ip] = adb['user_name']

        self.devices_data = devices_data
        print(self.devices_data)

    def filter_devices(self, resources_list):
        resource_data = {}
        for resource_data_dict in resources_list:
            resource_id = list(resource_data_dict.keys())[0]
            resource_data_dict = resource_data_dict[resource_id]
            devices = ['Linux/Interop', 'Windows', 'Mac OS', 'Android']
            if resource_data_dict['device type'] in devices:
                resource_data[resource_id] = resource_data_dict
        print(resource_data)
        return resource_data

    def get_resource_data(self):

        resources_list = self.json_get("/resource/all")["resources"]
        resource_data = self.filter_devices(resources_list)

        headers = ["Index", "Resource ID", "Hostname", "IP", "Device Type"]
        rows = []
        resource_keys = list(resource_data.keys())

        for i, res_id in enumerate(resource_keys):
            res = resource_data[res_id]
            self.device_info[res.get("ctrl-ip", "N/A")] = res.get("device type", "N/A")
            rows.append([
                i,
                res_id,
                res.get("hostname", "N/A"),
                res.get("ctrl-ip", "N/A"),
                res.get("device type", "N/A"),
            ])

        if self.device_list:
            selected_ids = [x.strip() for x in self.device_list.split(',') if x.strip()]
            print(self.device_list, selected_ids)
            # 1.23 ['1.23']
        else:
            print("\n Available Devices:")
            try:
                print(tabulate(rows, headers=headers, tablefmt="fancy_grid"), disable_numparse=True)
            except:
                # Print table without using tabulate
                print("\t".join(headers))
                for row in rows:
                    print("\t".join(str(item) for item in row))

            selection = input("\n> Enter ports of devices to run speedtest on (comma-separated): ")
            selected_ids = [str(i.strip()) for i in selection.split(',')]

        print(resource_data)
        self.selected_resources = {res_id: resource_data[res_id] for res_id in selected_ids}
        print(f"\n Selected Devices:\n{self.selected_resources}")
        
        self.get_device_data(self.selected_resources)

        if self.devices_data:

            for device in self.devices_data:
                dev_type = self.devices_data[device]['device type']

                # For regular devices (Linux, Windows, Mac)
                if dev_type == 'Linux/Interop':
                    self.devices_data[device]['cmd'] = f"DISPLAY=:1 ./vrf_exec.bash {device.split('.')[2]} python3 ookla.py --type {self.type}{' --post_url ' + self._post_url if self._post_url else ''} --ip {self.devices_data[device]['ip']}"
                elif dev_type == 'Windows':
                    self.devices_data[device]['cmd'] = f"py ookla.py --type {self.type}{' --post_url ' + self._post_url if self._post_url else ''} --ip {self.devices_data[device]['ip']}"
                elif dev_type == 'Mac OS':
                    self.devices_data[device]['cmd'] = f"python3 ookla.py --type {self.type}{' --post_url ' + self._post_url if self._post_url else ''} --ip {self.devices_data[device]['ip']}"

                # For ADB devices (override previous command if serial exists)
                if self.devices_data[device].get("serial"):
                    self.devices_data[device]['cmd'] = f"python3 ookla.py --type adb --adb_devices {self.devices_data[device]['serial']}{' --post_url ' + self._post_url if self._post_url else ''} --ip {self.devices_data[device]['ip']}"

                # REMOVE THIS DUPLICATE SECTION:
                # if self.dowebgui and self._post_url:
                #     self.devices_data[device]['cmd'] += f' --post_url {self._post_url}'
        else:
            print(" No compatible devices found.")

        print("\n Final Device Commands for Speedtest")
        self.android_data = { #.split('.', 2)[-1]
            k: v
            for k, v in self.devices_data.items()
            if v.get('device type', '').lower() == 'android'
        }

        self.laptop_data = {
            k: v
            for k, v in self.devices_data.items()
            if v.get('device type', '').lower() != 'android'
        }

        print('android_data :=', self.android_data)
        print('laptop_data :=', self.laptop_data)

        if self.laptop_data:
            for device in self.laptop_data:
                print(f"{device}   ?  {self.laptop_data[device]['ip']} ({self.laptop_data[device]['device type']}): {self.laptop_data[device]['cmd']}")
        if self.android_data:
            for android in self.android_data:
                print(f"{android}   ?  {self.android_data[android]['ip']} ({self.android_data[android]['device type']}): {self.android_data[android]['cmd']}")

    def start_generic(self):
        self.generic_endps_profile.start_cx()
        self.start_time = datetime.now()

    def stop_generic(self):
        self.generic_endps_profile.stop_cx()
        self.stop_time = datetime.now()

    def get_results(self):
        logging.debug(self.generic_endps_profile.created_endp)
        results = self.json_get(
            "/generic/{}".format(','.join(self.generic_endps_profile.created_endp)))
        if (len(self.generic_endps_profile.created_endp) > 1):
            results = results['endpoints']
        else:
            results = results['endpoint']
        return (results)

    def create_cx_do_interop(self, csv_file):
        for iter in range(1, self.iteration + 1):
            print(f"\n Starting Interop Iteration {iter} of {self.iteration}")
            for cx_name in self.generic_endps_profile.created_cx:
                self.start_specific([cx_name])
                time.sleep(60)
                self.stop_specific([cx_name])

                for device in self.devices_data:
                    os_type = self.devices_data[device]['device type']
                    remote_path = self.get_remote_file_path_by_os(os_type)
                    result = self.fetch_remote_speedtest_file(
                        ip=self.devices_data[device]['ip'],
                        username="lanforge" if os_type.lower() != 'windows' else "Administrator",
                        password="lanforge",
                        remote_path=remote_path
                    )
                    print(result)

                self.write_results_to_csv(iter, csv_file)
                self.result_json = {}

    def start_specific(self, cx_list):
        logging.info("Test started at : {0} ".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        if len(cx_list) > 0:
            for cx in cx_list:
                req_url = "cli-json/set_cx_report_timer"
                data = {
                    "test_mgr": "all",
                    "cx_name": cx,
                    "milliseconds": 1000
                }
                self.json_post(req_url, data)
        for cx_name in cx_list:
            self.json_post("/cli-json/set_cx_state", {
                "test_mgr": "default_tm",
                "cx_name": cx_name,
                "cx_state": "RUNNING"
            }, debug_=True)

    def stop_specific(self, cx_list):
        logging.info("Stopping specific CXs...")
        for cx_name in cx_list:
            if self.debug:
                logging.debug("cx-name: {cx_name}".format(cx_name=cx_name))
            self.json_post("/cli-json/set_cx_state", {
                "test_mgr": "default_tm",
                "cx_name": cx_name,
                "cx_state": "STOPPED"
            }, debug_=self.debug)

    def create(self):
        device_types = [device['device type'] for device in self.laptop_data.values()]

        if self.laptop_data:
            self.generic_endps_profile.create(ports=list(self.laptop_data.keys()), real_client_os_types=device_types)
            
        for endp_name in self.generic_endps_profile.created_endp:
            self.generic_endps_profile.set_cmd(endp_name, cmd=self.laptop_data[endp_name.split('-')[1]]['cmd'])

        if self.android_data:
            self.android_data = {
                f"{v['port']}.{k}": v
                for k, v in self.android_data.items()
            }
            status, created_cx, created_endp = self.create_android(ports=list(self.android_data.keys()), real_client_os_types=device_types)
            self.generic_endps_profile.created_endp.extend(created_endp)
            self.generic_endps_profile.created_cx.extend(created_cx)

            for endp_name in created_endp:
                self.generic_endps_profile.set_cmd(endp_name, cmd=self.android_data[(endp_name.split('-')[1]).replace('_', '.')]['cmd'])
        
        print(self.generic_endps_profile.created_endp)
        print(self.generic_endps_profile.created_cx)

    def create_android(self, ports=None, sleep_time=.5, debug_=False, suppress_related_commands_=None, real_client_os_types=None):
        if ports and real_client_os_types and len(real_client_os_types) == 0:
            logging.error('Real client operating systems types is empty list')
            raise ValueError('Real client operating systems types is empty list')
        created_cx = []
        created_endp = []

        if not ports:
            ports = []

        if self.debug:
            debug_ = True

        post_data = []
        endp_tpls = []
        for port_name in ports:
            port_info = self.name_to_eid(port_name)
            resource = port_info[1]
            shelf = port_info[0]
            if real_client_os_types:
                name = port_name
            else:
                name = port_info[2]

            gen_name_a = "%s-%s" % ('generic', '_'.join(port_name.split('.')))
            endp_tpls.append((shelf, resource, name, gen_name_a))

        print('endp_tpls', endp_tpls)
        for endp_tpl in endp_tpls:
            shelf = endp_tpl[0]
            resource = endp_tpl[1]
            if real_client_os_types:
                name = endp_tpl[2].split('.')[2]
            else:
                name = endp_tpl[2]
            gen_name_a = endp_tpl[3]

            data = {
                "alias": gen_name_a,
                "shelf": shelf,
                "resource": resource,
                "port": 'eth0',
                "type": "gen_generic"
            }
            # print('Adding endpoint ', data)
            self.json_post("cli-json/add_gen_endp", data, debug_=self.debug)

        self.json_post("/cli-json/nc_show_endpoints", {"endpoint": "all"})
        if sleep_time:
            time.sleep(sleep_time)

        for endp_tpl in endp_tpls:
            gen_name_a = endp_tpl[3]
            self.generic_endps_profile.set_flags(gen_name_a, "ClearPortOnStart", 1)

        for endp_tpl in endp_tpls:
            name = endp_tpl[2]
            gen_name_a = endp_tpl[3]
            cx_name = "CX_%s-%s" % ("generic", gen_name_a)
            data = {
                "alias": cx_name,
                "test_mgr": "default_tm",
                "tx_endp": gen_name_a
            }
            post_data.append(data)
            created_cx.append(cx_name)
            created_endp.append(gen_name_a)

        for data in post_data:
            url = "/cli-json/add_cx"
            # print('Adding cx', data)
            self.json_post(url, data, debug_=debug_, suppress_related_commands_=suppress_related_commands_)
            # time.sleep(2)
        if sleep_time:
            time.sleep(sleep_time)

        for data in post_data:
            self.json_post("/cli-json/show_cx", {
                "test_mgr": "default_tm",
                "cross_connect": data["alias"]
            })
        return True, created_cx, created_endp

    def save_results(self):
        results = self.get_results()
        print(results, 'RESULTS')
        for device in self.generic_endps_profile.created_endp:
            if(device in list(results[0].keys())):
                self.result_json[device] = results[0][device]['last results']

    def fetch_remote_speedtest_file(self, ip, username, password, remote_path="/home/lanforge/speedtest.txt"):
        
        try:
            print(f"Connecting to {ip} to fetch speedtest.txt")
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=username, password=password)

            sftp = ssh.open_sftp()
            local_path = f"./{ip.replace('.', '_')}_speedtest.txt"
            sftp.get(remote_path, local_path)
            sftp.close()
            ssh.close()

            with open(local_path, "r") as f:
                content = f.read()

            # Parse download and upload
            download = upload = idle_latency = down_latency = up_latency = "N/A"
            for line in content.splitlines():
                if "Download speed" in line:
                    download = line.split(":")[1].strip()
                elif "Upload speed" in line:
                    upload = line.split(":")[1].strip()
                elif "Idle Latency" in line:
                    idle_latency = line.split(":")[1].strip()
                elif "Download Latency" in line:
                    down_latency = line.split(":")[1].strip()
                elif "Upload Latency" in line:
                    up_latency = line.split(":")[1].strip()

            # Store in result_json
            self.result_json[ip] = {"upload": upload,
                                    "download": download,
                                    "Idle Latency": idle_latency,
                                    "Download Latency": down_latency,
                                    "Upload Latency": up_latency
                                    }

            print(f"{ip} - Download: {download}, Upload: {upload}, Idle Latency: {idle_latency}, Download Latency: {down_latency}, Upload Latency: {up_latency}")
            return content

        except Exception as e:
            print(f" Failed to fetch file from {ip}: {e}")
            self.result_json[ip] = {"download": "Error", "upload": "Error"}
            return None

    def fetch_android_speedtest_from_lanforge(self, ip, username='lanforge', password='lanforge',
                                            remote_dir="/home/lanforge"):
        """
        Fetches <ip>_speedtest.txt from LANforge to local machine and parses it.
        If the file does not exist, sets all values to 0 for that IP.
        """
        print(ip, 'fetching speedtest file')
        remote_file = f"{remote_dir.rstrip('/')}/{ip}_speedtest.txt"
        local_path = f"./{ip}_speedtest.txt"

        try:
            print(f"Connecting to {self.manager_ip} to fetch {remote_file} and local path {local_path}")
            ssh = self._ssh_connect(self.manager_ip, username, password)
            sftp = ssh.open_sftp()
            sftp.get(remote_file, local_path)
            sftp.close()
            ssh.close()

            with open(local_path, "r") as f:
                content = f.read()

            download = upload = idle_latency = down_latency = up_latency = "N/A"
            for line in content.splitlines():
                if "Download speed" in line:
                    download = line.split(":", 1)[1].strip()
                elif "Upload speed" in line:
                    upload = line.split(":", 1)[1].strip()
                elif "Idle Latency" in line:
                    idle_latency = line.split(":", 1)[1].strip()
                elif "Download Latency" in line:
                    down_latency = line.split(":", 1)[1].strip()
                elif "Upload Latency" in line:
                    up_latency = line.split(":", 1)[1].strip()

            self.result_json[ip] = {
                "download": download,
                "upload": upload,
                "Idle Latency": idle_latency,
                "Download Latency": down_latency,
                "Upload Latency": up_latency,
                "local_file": local_path,
            }
            print(f"{ip} - D:{download} U:{upload} Idle:{idle_latency} DLat:{down_latency} ULat:{up_latency}")
            return self.result_json[ip]
        except Exception as e:
            print(f"Failed to fetch or parse Android speedtest result for {ip}: {e}")
            self.result_json[ip] = {
                "download": "0",
                "upload": "0",
                "Idle Latency": "0",
                "Download Latency": "0",
                "Upload Latency": "0",
                "local_file": None,
            }

            return self.result_json[ip]

    def write_results_to_csv(self, current_iter, csv_file,  per_iter_wait_seconds=120):

        csv_exists = os.path.isfile(csv_file)

        csv_data   = []
        table_data = []

        # 1) Normalize keys we received this iteration
        received = {}
        for raw_ip, data in self.result_json.items():
            ip = raw_ip.replace('_', '.')
            received[ip] = {
                "download":          data.get("download", "N/A"),
                "upload":            data.get("upload", "N/A"),
                "Idle Latency":      data.get("Idle Latency", "N/A"),
                "Download Latency":  data.get("Download Latency", "N/A"),
                "Upload Latency":    data.get("Upload Latency", "N/A"),
            }

        # 2) Figure out expected devices (from what you selected earlier)
        # Prefer the IPs you learned during device discovery; fall back to device_info keys.
        expected_ips = list(self.ip_hostname.keys()) or list(self.device_info.keys())

        # 3) Emit rows for devices that DID report
        for ip, data in received.items():
            dev_type      = self.device_info.get(ip, "N/A")
            hostname_safe = self.ip_hostname.get(ip, ip)

            download      = data["download"]
            upload        = data["upload"]
            idle_latency  = data["Idle Latency"]
            down_latency  = data["Download Latency"]
            up_latency    = data["Upload Latency"]

            csv_data.append([current_iter, self.iteration, ip, dev_type,
                            download, upload, idle_latency, down_latency, up_latency])
            table_data.append([current_iter, self.iteration, ip, dev_type,
                            download, upload, idle_latency, down_latency, up_latency])

            # Accumulate into per-iter dicts for graphs/tables
            self.result_dict['ip'].append(ip)
            self.result_dict['hostname'].append(hostname_safe)

            def _num(x):
                try:
                    # Handles values like "24.2 Mbps" or "114 ms" or "N/A"
                    return float(str(x).split()[0])
                except Exception:
                    return 0.0

            self.result_dict['download_speed'].append(_num(download))
            self.result_dict['upload_speed'].append(_num(upload))
            self.result_dict['download_lat'].append(_num(down_latency))
            self.result_dict['upload_lat'].append(_num(up_latency))

        # 4) Emit rows for devices that did NOT report in this iteration (N/A)
        missing_ips = [ip for ip in expected_ips if ip not in received]
        for ip in missing_ips:
            dev_type      = self.device_info.get(ip, "N/A")
            hostname_safe = self.ip_hostname.get(ip, ip)

            csv_data.append([current_iter, self.iteration, ip, dev_type,
                            "N/A", "N/A", "N/A", "N/A", "N/A"])
            table_data.append([current_iter, self.iteration, ip, dev_type,
                            "N/A", "N/A", "N/A", "N/A", "N/A"])

            # For graphs: use zeros so categories & lengths stay aligned
            self.result_dict['ip'].append(ip)
            self.result_dict['hostname'].append(hostname_safe)
            self.result_dict['download_speed'].append(0.0)
            self.result_dict['upload_speed'].append(0.0)
            self.result_dict['download_lat'].append(0.0)
            self.result_dict['upload_lat'].append(0.0)

        # 5) Freeze per-iteration snapshot, then reset the accumulator for the next iter
        self.iteration_dict[current_iter] = self.result_dict
        self.result_dict = {
            'ip': [],
            'hostname': [],
            'download_speed': [],
            'upload_speed': [],
            'download_lat': [],
            'upload_lat': []
        }

        # 6) Append to CSV
        with open(csv_file, "a", newline="") as csvfile:
            writer = csv.writer(csvfile)
            if not csv_exists:
                writer.writerow([
                    "Iteration", "Total Iterations", "IP", "Device Type",
                    "Download", "Upload", "Idle Latency", "Download Latency", "Upload Latency"
                ])
            writer.writerows(csv_data)

        # 7) Pretty print table for the console
        print(f"\n Speedtest Results for Iteration {current_iter}")
        try:
            from tabulate import tabulate
            print(tabulate(
                table_data,
                headers=["Iteration", "Total Iterations", "IP", "Device Type",
                        "Download", "Upload", "Idle Latency", "Download Latency", "Upload Latency"],
                tablefmt="fancy_grid",
                disable_numparse=True
            ))
        except Exception:
            headers = ["Iteration", "Total Iterations", "IP", "Device Type",
                    "Download", "Upload", "Idle Latency", "Download Latency", "Upload Latency"]
            print("\t".join(headers))
            for row in table_data:
                print("\t".join(str(item) for item in row))

        if missing_ips:
            print(f"[NOTE] No data received for iteration {current_iter} from: {', '.join(missing_ips)} (filled with N/A)")
        print("=" * 158)
        print(self.iteration_dict)

    def cleanup(self):
        self.generic_endps_profile.cleanup()
        self.generic_endps_profile.created_cx = []
        self.generic_endps_profile.created_endp = []

    @staticmethod
    def get_remote_file_path_by_os(os_type):
        if os_type.lower() == 'windows':
            return r"C:\Program Files (x86)\LANforge-Server\speedtest.txt"
        elif os_type.lower() == 'mac os':
            return "/Users/lanforge/speedtest.txt"
        else:
            return "/home/lanforge/speedtest.txt"

    def generate_report(self, result_dir_name, per_post_timeout=120, poll_interval=2):
        """
        Build report, guaranteeing per-iteration completeness:
        - For robot tests: uses robot test numbers as iterations
        - For regular tests: uses iteration numbers
        """

        # --- Build the canonical device roster (stable order) ---
        roster = []
        for key, info in self.devices_data.items():
            roster.append({
                "key": key,
                "hostname": info.get("hostname", "") or "",
                "ip": info.get("ip", "") or "",
                "mac": info.get("mac", "") or "",
                "ssid": info.get("ssid", "") or "",
                "channel": info.get("channel", "") or "",
                "device_type": info.get("device type", "") or ""
            })
        # sort by hostname, then ip for stable graphs/tables
        roster.sort(key=lambda r: (str(r["hostname"]), str(r["ip"])))
        device_count = len(roster)

        # --- Determine iteration range based on test type ---
        if self.robot_test:
            # Recreate iteration_dict in the correct order
            correct_iteration_dict = {}
            test_counter = 1
            
            if self.rotation_list and self.rotation_list[0] != "":
                # Correct order: coordinate1-rot1, coordinate1-rot2, coordinate2-rot1, coordinate2-rot2
                for coord_idx, coord in enumerate(self.coordinate_list):
                    for rot_idx, rotation in enumerate(self.rotation_list):
                        # Find the original test number for this coordinate-rotation combination
                        original_test_number = None
                        for test_num, test_data in self.iteration_dict.items():
                            expected_coord_idx = (test_num - 1) // len(self.rotation_list)
                            expected_rot_idx = (test_num - 1) % len(self.rotation_list)
                            if expected_coord_idx == coord_idx and expected_rot_idx == rot_idx:
                                original_test_number = test_num
                                break

                        if original_test_number and original_test_number in self.iteration_dict:
                            correct_iteration_dict[test_counter] = self.iteration_dict[original_test_number]
                            test_counter += 1
                
                # Replace the iteration_dict with the correctly ordered one
                self.iteration_dict = correct_iteration_dict
                iteration_range = sorted(self.iteration_dict.keys())
            else:
                # Only coordinates: use natural order
                iteration_range = sorted(self.iteration_dict.keys())
            
            total_iterations = len(iteration_range)
            print(f"Robot test mode: {total_iterations} tests in corrected order")
        else:
            # For regular tests, use the configured iteration range
            iteration_range = range(1, self.iteration + 1)
            total_iterations = self.iteration

        # Create report and make sure destination dirs exist
        report = lf_report(
            _output_pdf="speedtest.pdf",    
            _output_html="speedtest.html",
            _results_dir_name=result_dir_name,
            _path=self.result_dir if self.dowebgui else "/home/lanforge/html-reports"
        )
        report_path = report.get_path()
        report_path_date_time = report.get_path_date_time()
        os.makedirs(report_path, exist_ok=True)
        os.makedirs(report_path_date_time, exist_ok=True)

        # Move CSV files
        try:
            if self.robot_test:
                robot_csv = f'speedtest_results_{self.instance}.csv'
                if os.path.exists(robot_csv):
                    shutil.move(robot_csv, report_path_date_time)
                    print(f"Moved robot CSV: {robot_csv}")
                else:
                    print(f"Robot CSV not found: {robot_csv}")
            else:
                regular_csv = f'speedtest_results_{self.instance}.csv'
                if os.path.exists(regular_csv):
                    shutil.move(regular_csv, report_path_date_time)
                    print(f"Moved regular CSV: {regular_csv}")
                else:
                    print(f"Regular CSV not found: {regular_csv}")
        except Exception as e:
            print(f"[WARN] could not move CSV: {e}")

        logger.info("path: {}".format(report_path))
        logger.info("path_date_time: {}".format(report_path_date_time))

        # --- Title & objective ---
        report_title = "Robot Speed Test" if self.robot_test else "Speed Test"
        report.set_title(report_title)
        report.build_banner()

        report.set_obj_html(
            _obj_title="Objective",
            _obj=("The Candela Speed Test evaluates AP performance under real-world conditions by measuring latency, "
                "download speed, and upload speed. The goal is to reflect true end-user experience in typical deployments.")
        )
        report.build_objective()

        # --- Test configuration summary ---
        android_devices = windows_devices = linux_devices = mac_devices = 0
        for r in roster:
            dt = r["device_type"]
            if dt == 'Android':
                android_devices += 1
            elif dt == 'Windows':
                windows_devices += 1
            elif dt == 'Mac OS':
                mac_devices += 1
            elif dt == 'Linux/Interop':
                linux_devices += 1
        
        total_devices = ""
        if android_devices: total_devices += f" Android({android_devices})"
        if windows_devices: total_devices += f" Windows({windows_devices})"
        if linux_devices:   total_devices += f" Linux({linux_devices})"
        if mac_devices:     total_devices += f" Mac({mac_devices})"

        # Add robot-specific configuration if applicable
        config_data = {
            "Test name": "Robot Speed Test" if self.robot_test else "Speed Test",
            "Number of Iterations": total_iterations,
            "Number of Selected Devices": f"{device_count} {total_devices}".strip()
        }

        if self.robot_test:
            config_data["Robot Coordinates"] = ", ".join(str(c) for c in self.coordinate_list)

            if self.rotation_list and self.rotation_list[0] != "":
                config_data["Robot Rotations"] = ", ".join(str(r) for r in self.rotation_list)
            else:
                config_data["Robot Rotations"] = "None"

        report.test_setup_table(
            test_setup_data=config_data,
            value="Test Configuration"
        )

        # --- Per-iteration graphs and tables ---
        missing_notes_all = []
        self.rotation_graph_data = {
            str(rotation_value): {
                "coordinates": [],
                "download": [],
                "upload": [],
                "download_lat": [],
                "upload_lat": [],
            }
            for rotation_value in (self.rotation_list if self.rotation_list else ["0"])
        }

        for iter_idx in iteration_range:
            print(f'Processing iteration {iter_idx} from iteration_dict: {self.iteration_dict.get(iter_idx, {})}')

            iter_block = self.iteration_dict.get(iter_idx, {
                'ip': [], 'hostname': [], 'download_speed': [], 'upload_speed': [], 'download_lat': [], 'upload_lat': []
            })

            # Map from IP -> index in lists
            ip_to_idx = {ip: i for i, ip in enumerate(iter_block.get('ip', []))}

            hostnames = []
            dls = []
            uls = []
            dlat = []
            ulat = []

            t_hostname = []
            t_mac = []
            t_ssid = []
            t_channel = []
            t_type = []

            for dev in roster:
                ip = dev["ip"]
                host = dev["hostname"]
                t_hostname.append(host)
                t_mac.append(dev["mac"])
                t_ssid.append(dev["ssid"])
                t_channel.append(dev["channel"])
                t_type.append(dev["device_type"])

                if ip in ip_to_idx:
                    j = ip_to_idx[ip]
                    hostnames.append(host or ip)
                    dls.append(iter_block['download_speed'][j])
                    uls.append(iter_block['upload_speed'][j])
                    dlat.append(iter_block['download_lat'][j])
                    ulat.append(iter_block['upload_lat'][j])
                else:
                    host_label = host or ip or "(unknown)"
                    hostnames.append(host_label)
                    dls.append(0.0)
                    uls.append(0.0)
                    dlat.append(0.0)
                    ulat.append(0.0)
                    missing_notes_all.append(
                        f"Iteration {iter_idx}: no data received for device {host_label} (IP {ip or 'N/A'}); row filled with 0."
                    )

            # Skip if no data at all
            if not any(dls) and not any(uls):
                print(f"[WARN] iteration {iter_idx}: no speed data; skipping graphs/tables.")
                continue

            # Create descriptive label based on coordinate and rotation
            if self.robot_test:
                # Calculate coordinate and rotation based on CORRECT test order
                if self.rotation_list and self.rotation_list[0] != "":
                    # Both coordinates and rotations: calculate based on current position in sequence
                    # After reordering, iter_idx now represents the correct position
                    coord_idx = (iter_idx - 1) // len(self.rotation_list)
                    rot_idx = (iter_idx - 1) % len(self.rotation_list)
                    coord = self.coordinate_list[coord_idx] if coord_idx < len(self.coordinate_list) else 'Unknown'
                    rotation = self.rotation_list[rot_idx] if rot_idx < len(self.rotation_list) else 'Unknown'
                else:
                    # Only coordinates
                    coord_idx = (iter_idx - 1) % len(self.coordinate_list)
                    coord = self.coordinate_list[coord_idx] if coord_idx < len(self.coordinate_list) else 'Unknown'
                    rotation = 'None'
                # -------- Build Line Graph Dataset --------
                rot_key = str(rotation)  # rotation in degrees or "0"

                if rot_key not in self.rotation_graph_data:
                    self.rotation_graph_data[rot_key] = {"coordinates": [], "download": [], "upload": [], "download_lat": [], "upload_lat": []}

                self.rotation_graph_data[rot_key]["coordinates"].append(coord)
                self.rotation_graph_data[rot_key]["download"].append(sum(dls)/len(dls) if dls else 0)
                self.rotation_graph_data[rot_key]["upload"].append(sum(uls)/len(uls) if uls else 0)
                self.rotation_graph_data[rot_key]["download_lat"].append(sum(dlat)/len(dlat) if dlat else 0)
                self.rotation_graph_data[rot_key]["upload_lat"].append(sum(ulat)/len(ulat) if ulat else 0)

                iteration_label = f"Coordinate: {coord} | Rotation Angle: {rotation}°"
            else:
                iteration_label = f"Iteration {iter_idx}"

        if self.robot_test:

            print("\n[INFO] Generating rotation-based bar plots")
            print(self.rotation_graph_data)
            print("====================================")

            for rot, data in self.rotation_graph_data.items():
                coords = data["coordinates"]
                down = data["download"]
                up = data["upload"]
                dlat = data["download_lat"]
                ulat = data["upload_lat"]

                if not coords:
                    print(f"[WARN] No data for rotation {rot}, skipping")
                    continue

                report.set_table_title(f"<b>Rotation Angle: {rot}°</b>")
                report.build_table_title()

                report.set_table_title(f"Speed (Mbps) for Rotation {rot}°")
                report.build_table_title()

                bar_speed = lf_bar_graph(
                    _data_set=[down, up],
                    _xaxis_name="Coordinates",
                    _yaxis_name="Speed (Mbps)",
                    _xaxis_categories=coords,
                    _graph_image_name=f"rotation_{rot}_speed_barplot",
                    _label=["Download", "Upload"],
                    _color=None,
                    _color_edge="red",
                    _show_bar_value=True,
                    _text_font=7,
                    _enable_csv=True
                )

                speed_png = bar_speed.build_bar_graph()

                if speed_png:
                    report.set_graph_image(speed_png)
                    report.move_graph_image()
                    report.build_graph()

                # ----------------------------------------------
                # LATENCY PLOT (Download/Upload)
                # ----------------------------------------------
                report.set_table_title(f"Latency (ms) for Rotation {rot}°")
                report.build_table_title()

                bar_latency = lf_bar_graph(
                    _data_set=[dlat, ulat],
                    _xaxis_name="Coordinates",
                    _yaxis_name="Latency (ms)",
                    _xaxis_categories=coords,
                    _graph_image_name=f"rotation_{rot}_latency_barplot",
                    _label=["Download Latency", "Upload Latency"],
                    _color=None,
                    _color_edge="red",
                    _show_bar_value=True,
                    _text_font=7,
                    _enable_csv=True
                )

                latency_png = bar_latency.build_bar_graph()

                if latency_png:
                    report.set_graph_image(latency_png)
                    report.move_graph_image()
                    report.build_graph()

            report.set_table_title(f'{iteration_label} - Speed Test Results')
            report.build_table_title()

            report.set_table_title('Per-Client Speed')
            report.build_table_title()
            print('=============================')
            dls = [124.0, 85.0, 102.0]
            uls = [42.0, 39.0, 55.0]
            print('=============================')

            graph = lf_bar_graph(
                _data_set=[dls, uls],
                _xaxis_name="Device Name",
                _yaxis_name="Speed (in Mbps)",
                _xaxis_categories=hostnames,
                _graph_image_name=f"Download_upload_speed_{iter_idx}",
                _label=["Download", "Upload"],
                _color=None,
                _color_edge='red',
                _show_bar_value=True,
                _text_font=7,
                _text_rotation=None,
                _enable_csv=True
            )
            graph_png = graph.build_bar_graph()
            if graph_png:
                report.set_graph_image(graph_png)
                report.move_graph_image()
                report.build_graph()

            report.set_table_title('Per-Client Latency')
            report.build_table_title()
            graph2 = lf_bar_graph(
                _data_set=[dlat, ulat],
                _xaxis_name="Device Name",
                _yaxis_name="Latency (in ms)",
                _xaxis_categories=hostnames,
                _graph_image_name=f"Download_upload_Latency_{iter_idx}",
                _label=["Download", "Upload"],
                _color=None,
                _color_edge='red',
                _show_bar_value=True,
                _text_font=7,
                _text_rotation=None,
                _enable_csv=True
            )
            graph2_png = graph2.build_bar_graph()
            if graph2_png:
                report.set_graph_image(graph2_png)
                report.move_graph_image()
                report.build_graph()

            # ---- Per-iteration device table ----
            test_input_info = {
                "hostname": t_hostname,
                "MAC": t_mac,
                "Device Type": t_type,
                "SSID": t_ssid,
                "Channel": t_channel,
                "Download Speed (Mbps)": dls,
                "Upload Speed (Mbps)": uls,
                "Download Latency (ms)": dlat,
                "Upload Latency (ms)": ulat,
            }

            report.set_table_title('Device Data')
            report.build_table_title()

            report.set_table_dataframe(pd.DataFrame(test_input_info))
            report.build_table()

        else:
            print("\n[INFO] Generating CLI-based bar plots")
            for iter_idx in iteration_range:
                iter_block = self.iteration_dict.get(iter_idx, {})
                hostnames = iter_block.get("hostname", [])
                dls = iter_block.get("download_speed", [])
                uls = iter_block.get("upload_speed", [])
                dlat = iter_block.get("download_lat", [])
                ulat = iter_block.get("upload_lat", [])

                if not any(dls) and not any(uls):
                    print(f"[WARN] iteration {iter_idx}: no data; skipping.")
                    continue

                iteration_label = f"Iteration {iter_idx}"
                report.set_table_title(f"{iteration_label} - Speed Test Results")
                report.build_table_title()

                # ---- Speed (Mbps) ----
                report.set_table_title("Per-Client Speed (Mbps)")
                report.build_table_title()
                bar_speed = lf_bar_graph(
                    _data_set=[dls, uls],
                    _xaxis_name="Device Name",
                    _yaxis_name="Speed (Mbps)",
                    _xaxis_categories=hostnames,
                    _graph_image_name=f"iteration_{iter_idx}_speed_barplot",
                    _label=["Download", "Upload"],
                    _color=None,
                    _color_edge="red",
                    _show_bar_value=True,
                    _text_font=7,
                    _enable_csv=True,
                )
                speed_png = bar_speed.build_bar_graph()
                if speed_png:
                    report.set_graph_image(speed_png)
                    report.move_graph_image()
                    report.build_graph()

                # ---- Latency (ms) ----
                report.set_table_title("Per-Client Latency (ms)")
                report.build_table_title()
                bar_latency = lf_bar_graph(
                    _data_set=[dlat, ulat],
                    _xaxis_name="Device Name",
                    _yaxis_name="Latency (ms)",
                    _xaxis_categories=hostnames,
                    _graph_image_name=f"iteration_{iter_idx}_latency_barplot",
                    _label=["Download Latency", "Upload Latency"],
                    _color=None,
                    _color_edge="red",
                    _show_bar_value=True,
                    _text_font=7,
                    _enable_csv=True,
                )
                latency_png = bar_latency.build_bar_graph()
                if latency_png:
                    report.set_graph_image(latency_png)
                    report.move_graph_image()
                    report.build_graph()

                # ---- Per-iteration table ----
                test_input_info = {
                    "Hostname": hostnames,
                    "Download Speed (Mbps)": dls,
                    "Upload Speed (Mbps)": uls,
                    "Download Latency (ms)": dlat,
                    "Upload Latency (ms)": ulat,
                }
                report.set_table_title("Device Data")
                report.build_table_title()
                report.set_table_dataframe(pd.DataFrame(test_input_info))
                report.build_table()

        # If anything was missing, add a Notes block at the end
        if missing_notes_all:
            notes_html = "<br>".join(missing_notes_all)
            report.set_obj_html(_obj_title="Notes", _obj=notes_html)
            report.build_objective()

        # Footer + files
        report.build_footer()
        report.write_html()
        report.write_pdf(_orientation="Landscape")

        print(f"[REPORT] done, files in: {report_path_date_time}")


def main():
    help_summary = '''\
The Candela's Speed Test is designed to evaluate the Access Point (AP) performance under real-world conditions by measuring key network metrics such as latency, download speed, upload speed.
This test aims to reflect the true end-user experience in typical deployment environments.

This test is currently supported only on laptop-based clients, including Linux, Windows, and Mac OS devices.

Key metrics collected include:
- Download Speed
- Upload Speed
- Idle Latency
- Download Latency
- Upload Latency
    '''

    parser = argparse.ArgumentParser(
        prog="lf_interop_speedtest.py",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog='''\
            Provides the list of available client devices and allows the user to perform speed testing
            on selected devices.
        ''',
        description='''\
            NAME: lf_interop_speedtest.py

            PURPOSE:
                The lf_interop_speedtest.py script enables users to perform real-world WiFi speed tests using laptop-based clients
                such as Linux, Windows, and macOS. This test does not support mobile platforms (e.g., Android, iOS).

                Instead, it focuses on measuring actual end-user experience by capturing metrics such as download/upload speed,
                latency (ping). The script uses the Speedtest.net service (via browser automation) to run the tests.

                TO PERFORM SPEED TEST:

                EXAMPLE-1:
                Run a default speed test using browser-based automation (Selenium)

                python3 lf_interop_speedtest.py --mgr 192.168.204.74

                EXAMPLE-2:
                Run a speed and interoperability test using browser automation

                python3 lf_interop_speedtest.py --mgr 192.168.204.74 --do_interopability
            '''
        )

    parser = argparse.ArgumentParser(
        prog='interop_speedtest.py',
        formatter_class=argparse.RawTextHelpFormatter)
    optional = parser.add_argument_group('Optional arguments')

    # optional arguments
    optional.add_argument(
                        '--mgr',
                        type=str,
                        help='hostname where LANforge GUI is running',
                        default='localhost')

    optional.add_argument(
                        '--device_list',
                        type=str,
                        help='Mention device list (comma seperated)',
                        )

    optional.add_argument(
                        '--instance_name',
                        type=str,
                        default='Speed_Test_report',
                        help='Mention Test Instance name (report folder name)',
                        )
    optional.add_argument(
                        '--iteration',
                        type=int,
                        default=1,
                        help='Mention number of iterations for the test.',
                        )

    optional.add_argument(
                        '--do_interopability',
                        action='store_true',
                        help='Ensures test on devices run sequentially')

    optional.add_argument(
                        '--result_dir',
                        type=str,
                        default='results',
                        help='Directory to store test results')

    optional.add_argument(
                        '--dowebgui',
                        action='store_true',
                        help='Generates a web GUI report for the test results')

    optional.add_argument(
                        '--type',
                        choices=['cli', 'ookla'],
                        default='ookla',
                        help='Type of speed test to perform (cli, ookla)')

    optional.add_argument(
                        '--cleanup',
                        action='store_true',
                        help='cleans up generic cx after completion of the test')

    optional.add_argument(
                        '--robot_test',
                        help='to trigger robot test',
                        action='store_true')

    optional.add_argument(
                        '--robot_ip',
                        type=str,
                        default='localhost',
                        help='hostname for where Robot server is running')

    optional.add_argument(
                        '--coordinate',
                        type=str,
                        default=None,
                        help="The coordinate contains list of coordinates to be ")

    optional.add_argument(
                        '--rotation',
                        type=str,
                        default=None,
                        help="The set of angles to rotate at a particular point")

    # TODO Commented lines are for implementation of incremental testing.
    # optional.add_argument(
    #               '--do_increment',
    #                       help='Specify the incremental values for speedtesting as a comma-separated list (e.g., 10,20,30).',
    #                       default=[])

    parser.add_argument('--help_summary', default=None, action="store_true", help='Show summary of what this script does')

    args = parser.parse_args()

    if args.help_summary:
        print(help_summary)
        exit(0)

    # TODO for folder creation purpose only
    # folder_name = f"{args.instance_name or 'SpeedTest'}"
    # os.makedirs(folder_name, exist_ok=True)
    # csv_file = os.path.join(folder_name, "speedtest_results.csv")

    csv_file = f"speedtest_results_{args.instance_name}.csv"
    # if not args.dowebgui else f"{args.result_dir}/speedtest_results_{args.instance_name}.csv"

    speedtest_obj = SpeedTest(
                            manager_ip=args.mgr,
                            device_list=args.device_list,
                            instance=args.instance_name,
                            iteration=args.iteration,
                            do_interopability=args.do_interopability,
                            result_dir=args.result_dir,
                            type=args.type,
                            dowebgui=args.dowebgui,
                            robot_test=args.robot_test,
                            robot_ip=args.robot_ip,
                            coordinate=args.coordinate,
                            rotation=args.rotation)

    speedtest_obj.get_resource_data()
    speedtest_obj.create()

    if args.do_interopability:
        speedtest_obj.create_cx_do_interop(csv_file)

    elif args.robot_test:
        # Use robot-specific CSV file
        csv_file = f"speedtest_results_{args.instance_name}.csv"
        print(f"Starting robot testing with {speedtest_obj.total_robot_tests} total tests")
        speedtest_obj.perform_robot_testing(csv_file)

    else:
        for iter in range(1, args.iteration + 1):
            print(f"\n Starting Iteration {iter} of {args.iteration}")

            speedtest_obj.start_generic()
            print(f"Test started at {speedtest_obj.start_time}")
            time.sleep(50)  # Speedtest duration wait time.
            speedtest_obj.stop_generic()
            time.sleep(20)

            # Wait until we have received posts from all expected devices (or timeout)
            def expected_post_ips(devices):
                want = []
                for info in devices.values():
                    cmd = (info.get('cmd') or '')
                    ip = (info.get('ip') or '')
                    if ip and '--post_url' in cmd:
                        want.append(ip)
                # de-dup (stable)
                seen, out = set(), []
                for ip in want:
                    if ip not in seen:
                        seen.add(ip)
                        out.append(ip)
                return out

            def has_post_for(ip):
                k = ip.replace('.', '_')
                # ookla.py posts using this exact key format
                return (k in speedtest_obj.result_json) or (ip in speedtest_obj.result_json)

            expected_ips = expected_post_ips(speedtest_obj.devices_data)
            deadline = time.time() + 120
            while time.time() < deadline:
                got = [ip for ip in expected_ips if has_post_for(ip)]
                if len(got) >= len(expected_ips):
                    break
                time.sleep(1)

            # Finally, write results for this iteration
            speedtest_obj.write_results_to_csv(iter, csv_file)
            # time.sleep() #TODO Hardcoded wait time to allow all devices to be ready for next iteration.
            speedtest_obj.result_json = {}

    if args.cleanup:
        speedtest_obj.cleanup()

    speedtest_obj.generate_report(result_dir_name=args.instance_name)


if __name__ == "__main__":
    main()
