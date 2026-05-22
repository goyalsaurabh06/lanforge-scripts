
import sys
import os
import threading
import time
import importlib
import logging
import argparse
from datetime import datetime, timedelta
import pandas as pd
import requests
from tabulate import tabulate
from flask import Flask, request, jsonify
import socket

if sys.version_info[0] != 3:
    print("This script requires Python3")
    exit()

sys.path.append(os.path.join(os.path.abspath(__file__ + "../../../")))
realm = importlib.import_module("py-json.realm")
Realm = realm.Realm

lf_report = importlib.import_module("py-scripts.lf_report")
lf_report = lf_report.lf_report


lf_graph = importlib.import_module("py-scripts.lf_graph")
lf_bar_graph_horizontal = lf_graph.lf_bar_graph_horizontal

class VLCStream(Realm):
    def __init__(self,
                 manager_ip=None,
                 port=8080,
                 mcast_addr="239.255.0.1",
                 mcast_port="1234",
                 host_res=None,
                 video_name=None,
                 duration=60,
                 fserver="localhost",
                 fport=5959,
                 _debug_on=False,
                 device_list=None):
        super().__init__(lfclient_host=manager_ip,
                         debug_=_debug_on)
        self.manager_ip = manager_ip
        self.manager_port = port
        self.devices_data = {}
        self.generic_endps_profile = self.new_generic_endp_profile()
        self.generic_endps_profile.type = 'generic'
        self.generic_endps_profile.cmd = ' ' 
        self.result_json = {}
        self.stop_time = None
        self.start_time = None
        self.mcast_addr = mcast_addr
        self.mcast_port = mcast_port
        self.host_res = host_res
        self.video_name = video_name
        self.duration = duration
        self.fserver = fserver
        self.fport = fport
        self.app = Flask(__name__)
        self.stats = {}
        self.device_list = device_list if device_list else []

    def get_port_data(self, resource_data):
        # Get ports
        # TODO: Add optional argument to function to allow the detection of down ports.
        # Currently only returns real device ports which are not phantom and are up
        resource_id = list(resource_data.keys())
        ports = self.json_get('/ports/all')['interfaces']
        for port_data_dict in ports:
            port_id = list(port_data_dict.keys())[0]
            port_id_parts = port_id.split('.')
            resource = port_id_parts[0] + '.' + port_id_parts[1]

            # Skip any non-real devices we have decided to not track
            if resource not in resource_id:
                continue

            # Need to unpack resource data dict of encapsulating dict that contains it
            port_data_dict = port_data_dict[port_id]

            if 'phantom' not in port_data_dict or 'down' not in port_data_dict or 'parent dev' not in port_data_dict:
                logging.error('Malformed json response for endpoint /ports/all')
                raise ValueError('Malformed json response for endpoint /ports/all')

            # Skip phantom or down ports
            if port_data_dict['phantom'] or port_data_dict['down']:
                continue

            # TODO: Support more than one station per real device
            # print(port_data_dict['parent dev'])
            if port_data_dict['parent dev'] != 'wiphy0':
                continue
            
            if resource in resource_data:
                self.devices_data[port_id] = {'device type': None, 'cmd': None, 'ip': None}
                self.devices_data[port_id]['device type'] = resource_data[resource]['device type']
                self.devices_data[port_id]['ip'] = resource_data[resource]['ctrl-ip']
                self.devices_data[port_id]['hostname'] = resource_data[resource]['hostname'] if resource_data[resource]['device type'] != 'Android' else resource_data[resource]['user']
                self.devices_data[port_id]['rssi'] = port_data_dict['signal']
                self.devices_data[port_id]['channel'] = port_data_dict['channel']
                self.devices_data[port_id]['mac'] = port_data_dict['mac']
                self.devices_data[port_id]['link rate'] = port_data_dict['rx-rate']
                self.devices_data[port_id]['adb_id'] = None if resource_data[resource]['device type'] != 'Android' else resource_data[resource].get('adb_id') 

        print(self.devices_data)

    def filter_devices(self, resources_list):
        resource_data = {}
        for resource_data_dict in resources_list:
            resource_id = list(resource_data_dict.keys())[0]
            resource_data_dict = resource_data_dict[resource_id]

            devices = ['Linux/Interop', 'Windows', 'Mac OS', 'Android']
            if resource_data_dict['device type'] in devices and resource_data_dict.get('phantom') is False:
                resource_data[resource_id] = resource_data_dict

        # Sort devices so Android appears last
        sorted_resource_data = dict(
            sorted(
                resource_data.items(),
                key=lambda item: item[1]['device type'].lower() == "android"
            )
        )

        return sorted_resource_data


    def get_resource_data(self):
        # Step 1: Get resource data
        resources_list = self.json_get("/resource/all")["resources"]
        adb_device_list = self.json_get("/adb/devices")["devices"]
        for adb_device in adb_device_list:
            adb_id = list(adb_device.keys())[0]
            adb_values = adb_device[adb_id]
            resource_id = adb_values["resource-id"]
            for resource_data_dict in resources_list:
                res_id = list(resource_data_dict.keys())[0]
                if res_id == resource_id and adb_values["phantom"] is False:
                    resource_data_dict[res_id]["adb_id"] = adb_id
                    break
        resource_data = self.filter_devices(resources_list)

        headers = ["Index", "Resource ID", "Hostname", "IP", "Device Type"]
        rows = []
        resource_keys = list(resource_data.keys())
        res_to_idx = {}
        for i, res_id in enumerate(resource_keys):
            print(i+1,res_id)
            res = resource_data[res_id]
            res_to_idx[res_id] = i+1
            rows.append([
                i + 1,
                res_id,
                res.get("hostname", "N/A"),
                res.get("ctrl-ip", "N/A"),
                res.get("device type", "N/A"),
            ])

        print("Available Devices:")
        print(tabulate(rows, headers=headers, tablefmt="fancy_grid"))
        # Step 3: User selection
        if self.device_list:
            temp_list = []
            dev_list = self.device_list.split(",")
            for dev in dev_list:
                if dev in res_to_idx:
                    temp_list.append(str(res_to_idx[dev]))
            selection = ",".join(temp_list)
        else:
            selection = input("Select devices (example: 1,3,5): ")
        selected_indices = [int(i.strip()) - 1 for i in selection.split(',') if i.strip().isdigit()]
        selected_ids = [resource_keys[i] for i in selected_indices if 0 <= i < len(resource_keys)]
        self.selected_devices_ordered = selected_ids
        selected_resources = {res_id: resource_data[res_id] for res_id in selected_ids}
        print(f"\n Selected Devices:\n{selected_resources}")

        # Step 4: Proceed with port collection
        self.get_port_data(selected_resources)
        # Select one device as host
        device_ids = list(self.devices_data.keys())
        host_id = None

        def is_android(device_id):
            return self.devices_data[device_id]['device type'].lower() == "android"

        def is_laptop(device_id):
            """Return True for Linux/Windows/Mac devices (non-Android)."""
            return not is_android(device_id)

        # ---------------------------------------------------------------
        # HOST SELECTION — no interactive prompts; always picks a laptop.
        # Priority:
        #   1. Use configured host_res if that device is in the configured
        #      list and is NOT Android.
        #   2. Fall back automatically to the first non-Android (laptop)
        #      device from the configured list.
        #   3. If no laptops exist at all, exit with a clear error.
        # ---------------------------------------------------------------
        if self.host_res:
            # Try to find the configured host_res in the configured device list
            for dev_id in device_ids:
                if dev_id.startswith(self.host_res + '.') or dev_id == self.host_res:
                    if is_android(dev_id):
                        print(f"[VLC] Configured host_res '{self.host_res}' is an Android device — "
                              "Android cannot be host. Will auto-select a laptop instead.")
                        self.host_res = None
                    else:
                        host_id = dev_id
                        self.host_res = host_id
                        print(f"[VLC] Using configured host_res device as host: {host_id}")
                    break
            else:
                # host_res was set but no matching device found in the configured list
                print(f"[VLC] Configured host_res '{self.host_res}' is NOT in the configured device list. "
                      "Will auto-select a laptop from the configured list instead.")
                self.host_res = None

        if host_id is None:
            # Auto-select: first non-Android (laptop) device from the configured list
            laptop_candidates = [d for d in device_ids if is_laptop(d)]
            if not laptop_candidates:
                print("[VLC] No non-Android (laptop) device found in the configured list. "
                      "Cannot proceed without a host. Exiting.")
                sys.exit(1)
            host_id = laptop_candidates[0]
            self.host_res = host_id
            print(f"[VLC] Auto-selected laptop as host: {host_id} "
                  f"({self.devices_data[host_id]['device type']})")

        # ---------------------------------------------------------------
        # Auto-set video_name path based on the selected host's OS so the
        # correct path is used regardless of what was configured.
        # ---------------------------------------------------------------
        host_os = self.devices_data[host_id]['device type'].lower()
        if "windows" in host_os:
            auto_video_name = r"C:\Program Files (x86)\LANforge-Server\testvideo.mp4"
        else:
            # Linux/Interop, Mac OS, or anything else → Linux path
            auto_video_name = "/home/lanforge/testvideo.mp4"

        if not self.video_name:
            self.video_name = auto_video_name
            print(f"[VLC] video_name not set; using OS-appropriate default: {self.video_name}")
        else:
            # Override with OS-correct path regardless of what was configured,
            # because the configured path might not match the actual host OS.
            self.video_name = auto_video_name
            print(f"[VLC] video_name overridden to OS-appropriate path for host "
                  f"({self.devices_data[host_id]['device type']}): {self.video_name}")


        # Step 5: Assign vlc streaming command by OS
        if self.devices_data:
            for device in self.devices_data:
                info = self.devices_data[device]
                ip = info['ip']
                os_type = info['device type'].lower()
                is_host = device == host_id
                if is_host:
                    if "linux" in os_type:
                        cmd = (
                            f'su -l lanforge ctvlc.bash {device.split(".")[2]} host "{self.video_name}" {self.mcast_addr} {self.mcast_port} {self.duration} {device} {self.fserver}:{self.fport}'
                        )
                    elif "windows" in os_type:
                        cmd = (
                            f'py ctvlc.py host --media "{self.video_name}" '
                            f'--mcast_ip "{self.mcast_addr}" --port {self.mcast_port} --duration {self.duration} --fserver {self.fserver}:{self.fport} --client_id {device}'
                        )
                    elif "mac" in os_type:
                        cmd = (
                            f'bash ctvlc.bash {device.split(".")[2]} host "{self.video_name}" "{self.mcast_addr}" {self.mcast_port} {self.duration} {device} {self.fserver}:{self.fport}'
                        )
                    elif "android" in os_type:
                        adb_id = info.get("adb_id")
                        if not adb_id:
                            print(f"No adb_id found for Android device {device}. Skipping command assignment.")
                            continue
                        cmd = (
                            f'python3 vlc_android.py --serial {adb_id.split(".")[-1]} --'
                            f'adb -s {adb_id} shell am start -n org.videolan.vlc/org.videolan.vlc.gui.video.VideoPlayerActivity '
                            f'-e vlc_args "--intf=rc --extraintf=rc --rc-host=localhost:{self.fport} --loop --sout=#duplicate{{dst=display,dst=std{{access=udp,mux=ts,dst={self.mcast_addr}:{self.mcast_port}}}}} --input-repeat=9999" '
                            f'-e input "{self.video_name}"'
                        )
                else:  # Client vlc udp://@239.255.0.1:1234 -vvv
                    if "linux" in os_type:
                        cmd = (
                            f'su -l lanforge ctvlc.bash {device.split(".")[2]} client - {self.mcast_addr} {self.mcast_port} {self.duration} {device} {self.fserver}:{self.fport}'
                        )
                    elif "windows" in os_type:
                        cmd = (
                            f'py ctvlc.py client '
                            f'--mcast_ip {self.mcast_addr} --port {self.mcast_port} --duration {self.duration} --fserver {self.fserver}:{self.fport} --client_id {device}'
                        )
                    elif "mac" in os_type:
                        cmd = (
                            f'bash ctvlc.bash {device.split(".")[2]} client - {self.mcast_addr} {self.mcast_port} {self.duration} {device} {self.fserver}:{self.fport}'
                        )
                    elif "android" in os_type:
                        adb_id = info.get("adb_id")
                        if not adb_id:
                            print(f"No adb_id found for Android device {device}. Skipping command assignment.")
                            continue
                        cmd = (
                            f'python3 vlc_android.py --serial {adb_id.split(".")[-1]} --mcast_ip {self.mcast_addr} --port {self.mcast_port} '
                            f'--duration {self.duration} --fserver {self.manager_ip}:{self.fport} --client_id {device}'
                        )
                print(self.devices_data[device])
                self.devices_data[device]['cmd'] = cmd
        else:
            print("No compatible devices found.")

        print("\nFinal Device Commands for vlc streaming:")
        for device, info in self.devices_data.items():
            print(f"{device} → {info['ip']} ({info['device type']}): {info['cmd']}")

    def start_generic(self):
        self.generic_endps_profile.start_cx()
        self.start_time = datetime.now()

    def stop_generic(self):
        self.generic_endps_profile.stop_cx()
        self.stop_time = datetime.now()

    def create_android(self, lanforge_res, ports=None, sleep_time=.5, debug_=False, suppress_related_commands_=None, real_client_os_types=None):
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

            gen_name_a = "%s-%s" % ('vlc', '_'.join(port_name.split('.')))
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
                "resource": lanforge_res,
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


    def create(self):
        print("devices data", self.devices_data)
        device_types = [device['device type'] for device in self.devices_data.values()]
        print(device_types)
        self.generic_endps_profile.name_prefix = "vlc"
        for device_id, device in self.devices_data.items():
            if device['device type'].lower() == "android":
                status, created_cx, created_endp = self.create_android(lanforge_res=device["adb_id"].split(".")[1], ports=[ device_id], real_client_os_types=['Linux'])
                print("return from android create",status, created_cx, created_endp)
                self.generic_endps_profile.created_endp.extend(created_endp)
                self.generic_endps_profile.created_cx.extend(created_cx)
                self.generic_endps_profile.set_cmd(created_endp[0], cmd=device["cmd"])
            else:
                new_cx_index = len(self.generic_endps_profile.created_cx)
                self.generic_endps_profile.create(ports=[device_id],real_client_os_types = device["device type"])
                self.generic_endps_profile.set_cmd(self.generic_endps_profile.created_endp[new_cx_index], cmd=device["cmd"])

        print(self.generic_endps_profile.created_endp)

    def cleanup(self):
        self.generic_endps_profile.cleanup()
        self.generic_endps_profile.created_cx = []
        self.generic_endps_profile.created_endp = []

    def start_flask_server(self):

        @self.app.route('/stats', methods=['POST'])
        def upload_stats():
            temp_data = request.get_json()
            for client_id, stats in temp_data.items():
                self.stats[client_id] = stats
            print(self.stats)
            return jsonify({"status": "success"}), 200

        # New route to check the health of the Flask server
        @self.app.route('/check_health', methods=['GET'])
        def check_health():
            return jsonify({"status": "healthy"}), 200

        @self.app.route('/check_stop', methods=['GET'])
        def check_stop():
            return jsonify({"stop": self.stop_signal})

        try:
            self.app.run(host='0.0.0.0', port=5959, debug=True, threaded=True, use_reloader=False)

        except Exception as e:
            logging.info(f"Error starting Flask server: {e}")
            sys.exit(0)

    def run_flask_server(self):
        flask_thread = threading.Thread(target=self.start_flask_server)
        flask_thread.daemon = True
        flask_thread.start()
        self.wait_for_flask()

    def wait_for_flask(self, url="http://127.0.0.1:5959/check_health", timeout=10):
            """Wait until the Flask server is up, but exit if it takes longer than `timeout` seconds."""
            start_time = time.time()  # Record the start time
            while time.time() - start_time < timeout:
                try:
                    response = requests.get(url, timeout=1)
                    if response.status_code == 200:
                        logging.info("✅ Flask server is up and running!")
                        return
                except requests.exceptions.ConnectionError:
                    time.sleep(1)
            logging.error(" Flask server did not start within 10 seconds. Exiting.")
            sys.exit(1)

    def generate_test_setup_info(self):
        """
        Generate a dictionary containing the test setup information
        Returns:
            dict: Test setup information.
        """
        mac = 0
        linux = 0
        win = 0
        android = 0
        device_list = []
        for devices in self.devices_data.values():
            if devices['device type'].lower() == "linux/interop":
                linux += 1
            elif devices['device type'].lower() == "windows":
                win += 1
            elif devices['device type'].lower() == "mac os":
                mac +=1
            elif devices['device type'].lower() == "android":
                android +=1
            device_list.append(devices["hostname"])
                
        test_setup_info = {
            'Test name' : "VLC Streaming Test",
            'Devies': device_list,
            'No of Devices': f'Total ({mac+linux+win+android}) Windows({win}),Linux({linux}),Mac({mac}),Android({android})',
            "Test Duration (min)": self.duration/60,
            "Host ID" : self.host_res,
            "Test Type" : "Video+Audio",
            "Multicast Port" : self.mcast_port,
            "Multicast Address" : self.mcast_addr
        }
        return test_setup_info
    
    def extract_data_for_reporting_for_laptop_clients(self):
         
        hostname, device_type, mac, channel, rssi, link = [], [], [], [], [], []
        video_decoded,  frames_displayed, frames_lost = [], [], []
        audio_decoded,buffer_played, buffer_lost = [], [], []
        print("start")
        print(self.devices_data)
        print("endddd")
        for eid,device in self.devices_data.items():
            if self.host_res and self.host_res == eid:
                # skipping host
                continue
            if device['device type'].lower() == "android":
                continue
            hostname.append(device.get("hostname", ""))
            device_type.append(device.get("device type", ""))
            mac.append(device.get("mac", ""))
            channel.append(device.get("channel", ""))
            rssi.append(device.get("rssi", ""))
            link.append(device.get("link rate", ""))

            stats = self.stats.get(eid)
            if stats:
                video_decoded.append(stats.get("video_decoded", "0"))
                audio_decoded.append(stats.get("audio_decoded", "0"))
                frames_displayed.append(stats.get("frames_displayed", "0"))
                frames_lost.append(stats.get("frames_lost", "0"))
                buffer_played.append(stats.get("buffers_played", "0"))
                buffer_lost.append(stats.get("buffers_lost", "0"))
            else:
                video_decoded.append("0")
                audio_decoded.append("0")
                frames_displayed.append("0")
                frames_lost.append("0")
                buffer_played.append("0")
                buffer_lost.append("0")
        return {
            "hostnames" : hostname,
            "device_types" : device_type,
            "mac": mac,
            "channel": channel,
            "rssi": rssi,
            "link" : link,
            "video_decoded": video_decoded,
            "frames_displayed": frames_displayed,
            "frames_lost" : frames_lost,
            "audio_decoded" : audio_decoded,
            "buffers_played": buffer_played,
            "buffers_lost" : buffer_lost
        }
    
    def extract_data_for_reporting_for_android_clients(self):
        hostname, device_type, mac, channel, rssi, link = [], [], [], [], [], []
        video_codec, audio_codec, audio_channels, audio_sample_rate = [], [], [], []
        demux_bitrate, input_bitrate = [], []
        for eid,device in self.devices_data.items():
            if device['device type'].lower() != "android":
                # skipping non-android clients
                continue
            hostname.append(device.get("hostname", ""))
            device_type.append(device.get("device type", ""))
            mac.append(device.get("mac", ""))
            channel.append(device.get("channel", ""))
            rssi.append(device.get("rssi", ""))
            link.append(device.get("link rate", ""))

            stats = self.stats.get(eid)
            """
            exmple stats curently received from vlc_android.py:
            {'timestamp': 1769581827.3940518, 
            'raw': ['Video', 'Codec', 'MPEG-1/2 Video', 'Audio', 'MPEG Audio layer 1/2', 'Language', 'English', 'Channels', '0', 'Sample rate', '0 Hz', 'Video information', 'Demux bitrate', '857 kb/s', 'Input bitrate', '1878 kb/s', '0:14', '0:00', 'udp://@239.255.0'], 
            'parsed': {'demux_bitrate_kbps': 857.0, 'input_bitrate_kbps': 1878.0, 'video_codec': 'MPEG-1/2 Video', 'audio_codec': None, 'channels': 0.0, 'sample_rate_hz': 0.0, 'framerate_fps': None}, 'device_type': 'Android'}
            """
            stats = stats.get("parsed") if stats else None
            if stats:
                video_codec.append(stats.get("video_codec", "N/A"))
                audio_codec.append(stats.get("audio_codec", "N/A"))
                audio_channels.append(stats.get("channels", "N/A"))
                audio_sample_rate.append(stats.get("sample_rate_hz", "N/A"))
                demux_bitrate.append(stats.get("demux_bitrate_kbps", "0"))
                input_bitrate.append(stats.get("input_bitrate_kbps", "0"))
            else:
                video_codec.append("N/A")
                audio_codec.append("N/A")
                audio_channels.append("N/A")
                audio_sample_rate.append("N/A")
                demux_bitrate.append("0")
                input_bitrate.append("0")
        return {
            "hostnames" : hostname,
            "device_types" : device_type,
            "mac": mac,
            "channel": channel,
            "rssi": rssi,
            "link" : link,
            "video_codec": video_codec,
            "audio_codec": audio_codec,
            "audio_channels": audio_channels,
            "audio_sample_rate": audio_sample_rate,
            "demux_bitrate": demux_bitrate,
            "input_bitrate": input_bitrate
        }
        
    def extract_data_for_reporting_for_host(self):
        hostname, device_type, mac, channel, rssi, link = [], [], [], [], [], []
        input_bytes_read = []
        input_bitrate = []
        demux_bytes_read = []
        demux_bitrate = []
        discontinuities = []

        for eid, device in self.devices_data.items():
            if(eid != self.host_res):
                #skipping client that is not host
                continue
            hostname.append(device.get("hostname", ""))
            device_type.append(device.get("device type", ""))
            mac.append(device.get("mac", ""))
            channel.append(device.get("channel", ""))
            rssi.append(device.get("rssi", ""))
            link.append(device.get("link rate", ""))

            stats = self.stats.get(eid)

            if stats:
                input_bytes_read.append(stats.get("input_bytes_read", "0 KiB"))

                input_bitrate.append(stats.get("input_bitrate", "0 kb/s"))

                demux_bytes_read.append(stats.get("demux_bytes_read", "0 KiB"))

                demux_bitrate.append(stats.get("demux_bitrate", "0 kb/s"))

                discontinuities.append(stats.get("discontinuities", "Constant"))
            else:
                input_bytes_read.append("0 KiB")
                input_bitrate.append("0 kb/s")
                demux_bytes_read.append("0 KiB")
                demux_bitrate.append("0 kb/s")
                discontinuities.append("0")

        return {
            "hostnames": hostname,
            "device_types": device_type,
            "mac": mac,
            "channel": channel,
            "rssi": rssi,
            "link": link,
            "input_bytes_read": input_bytes_read,
            "input_bitrate": input_bitrate,
            "demux_bytes_read": demux_bytes_read,
            "demux_bitrate": demux_bitrate,
            "discontinuities": discontinuities,
        }
    
    def build_device_metrics_table(self,report_obj, device_info, metrics):
        """
        device_info: dict with keys Device Name, Device Type, Mac Address, Channel, RSSI (dBm)
        metrics: list of tuples [(metric, start_value, end_value), ...]
        """
        rowspan_count = len(metrics)

        # first metric row with device info
        first_metric = metrics[0]
        html_rows = f"""
        <tr>
        <td rowspan="{rowspan_count}">{device_info.get('Device Name', '')}</td>
        <td rowspan="{rowspan_count}">{device_info.get('Device Type', '')}</td>
        <td rowspan="{rowspan_count}">{device_info.get('Mac Address', '')}</td>
        <td rowspan="{rowspan_count}">{device_info.get('Channel', '')}</td>
        <td rowspan="{rowspan_count}">{device_info.get('RSSI (dBm)', '')}</td>
        <td>{first_metric[0]}</td>
        <td>{first_metric[1]}</td>
        </tr>
        """

        # remaining metric rows without device info
        for metric in metrics[1:]:
            html_rows += f"""
        <tr>
        <td>{metric[0]}</td>
        <td>{metric[1]}</td>
        </tr>
        """

        # full table with headers
        table_html = f"""
        <table width='100%' border='1' cellpadding='4' cellspacing='0' style='border-collapse: collapse; border: 1px solid gray;'>
        <tr style='background-color: #f2f2f2;'>
            <th>Device Name</th>
            <th>Device Type</th>
            <th>Mac Address</th>
            <th>Channel</th>
            <th>RSSI (dBm)</th>
            <th>Metric</th>
            <th>Value</th>
        </tr>
        {html_rows}
        </table>
        <br>
        """

        report_obj.html += table_html

    def create_report(self):
        try:

            report = lf_report(_output_pdf='Vlc_Stremaing_Report',
                                _output_html='VLC_Streaming_Report.html',
                                _results_dir_name="VLC_Streaming_Report",
                                _path='')
            self.report_path_date_time = report.get_path_date_time()

            report.set_title("VLC Streaming Test")
            report.build_banner()

            report.set_table_title("Objective:")
            report.build_table_title()
            report.set_text("The Objective of the VLC media streaming test is to evaluate the performance and durability" +
                            " of video and audio streaming over Wi-Fi across multiple client platforms, including" +
                            "windows, Linux, macOS. By conducting this test, we aim to ensure successful stream" +
                            "initation, stable playback, and accurate collection of decoding statistics such as frames displayed, " +
                            "frames lost, buffer played and buffers lost. This helps assess the network's ability to support consistent and high-quality media streaming unser varying Wi-Fi consitions.")
            report.build_text_simple()

            report.set_table_title("Input Parameters:")
            report.build_table_title()


            test_setup_info = self.generate_test_setup_info()
            report.test_setup_table(test_setup_data=test_setup_info, value='Input Parameters')

            final_data = self.extract_data_for_reporting_for_laptop_clients()
            android_data = self.extract_data_for_reporting_for_android_clients()
            if len(final_data["hostnames"]) == 0:
                logging.info("No client data available for report generation.Continuing without client data.")
            else:
                report.set_graph_title("Video Frames per Device")
                report.build_graph_title()

                x_fig_size = 18
                y_fig_size = len(final_data["hostnames"]) * 1 + 4
                bar_graph_horizontal = lf_bar_graph_horizontal(
                    _data_set=[[int(float(x)) for x in final_data["frames_lost"]],[int(float(x)) for x in final_data["frames_displayed"]]],
                    _xaxis_name="No of Frames",
                    _yaxis_name="Device Name",
                    _yaxis_label=final_data["hostnames"],
                    _yaxis_categories=final_data["hostnames"],
                    _yaxis_step=1,
                    _yticks_font=8,
                    _bar_height=.20,
                    _show_bar_value=True,
                    _dpi=96,
                    _figsize=(x_fig_size, y_fig_size),
                    _graph_title="Video Frames Displayed/Lost per Device",
                    _graph_image_name=f"video_frames_per_device",
                    _label=["Frames Lost", "Frames Displayed"]
                )
                graph_image = bar_graph_horizontal.build_bar_graph_horizontal()
                report.set_graph_image(graph_image)
                report.move_graph_image()
                report.build_graph()

                report.set_graph_title("Audio Buffers Per Device")
                report.build_graph_title()

                x_fig_size = 18
                y_fig_size = len(final_data["hostnames"]) * 1 + 4
                bar_graph_horizontal = lf_bar_graph_horizontal(
                    _data_set=[[int(float(x)) for x in final_data["buffers_lost"]],[int(float(x)) for x in final_data["buffers_played"]]],
                    _xaxis_name="No of Buffers",
                    _yaxis_name="Device Name",
                    _yaxis_label=final_data["hostnames"],
                    _yaxis_categories=final_data["hostnames"],
                    _yaxis_step=1,
                    _yticks_font=8,
                    _bar_height=.20,
                    _show_bar_value=True,
                    _figsize=(x_fig_size, y_fig_size),
                    _graph_title="Audio Buffers Played/Lost Per Device",
                    _graph_image_name=f"audio_buffers_per_device",
                    _label=["Buffers Lost","Buffers Played",]
                )
                graph_image = bar_graph_horizontal.build_bar_graph_horizontal()
                report.set_graph_image(graph_image)
                report.move_graph_image()
                report.build_graph()

    
                report.set_table_title("Test Results For Clients(Laptops)")
                report.build_table_title()
                report.set_text("The table below provides detailed information of both the Audio and Video Playback statistics of laptop device acting as clients.")
                report.build_text_simple()
                final_test_results = {

                    "Device Name": final_data["hostnames"],
                    "Device Type": final_data["device_types"],
                    "MAC Address": final_data["mac"],
                    "Channel": final_data["channel"],
                    "RSSI": final_data["rssi"],
                    "Link Rate": final_data["link"],
                    "Video Decoded ": final_data["video_decoded"],
                    "Frames Displayed ": final_data["frames_displayed"],
                    "Frames Lost ": final_data["frames_lost"],
                    "Audio Decoded ": final_data["audio_decoded"],
                    "Buffers Played ": final_data["buffers_played"],
                    "Buffers Lost ": final_data["buffers_lost"],
                }

                test_results_df = pd.DataFrame(final_test_results)
                report.set_table_dataframe(test_results_df)
                report.build_table()
            if len(android_data["hostnames"]) == 0:
                logging.info("No Android client data available for report generation.Continuing without Android client data.")
            else:    
                report.set_table_title("Test Results For Clients(Androids)")
                report.build_table_title()
                
                android_test_results = {

                    "Device Name": android_data["hostnames"],
                    "Device Type": android_data["device_types"],
                    "MAC Address": android_data["mac"],
                    "Channel": android_data["channel"],
                    "RSSI": android_data["rssi"],
                    "Link Rate": android_data["link"],
                    "Video Codec": android_data["video_codec"],
                    "Audio Codec": android_data["audio_codec"],
                    "Audio Channels": android_data["audio_channels"],
                    "Audio Sample Rate (Hz)": android_data["audio_sample_rate"],
                    "Demux Bitrate (kb/s)": android_data["demux_bitrate"],
                    "Input Bitrate (kb/s)": android_data["input_bitrate"],
                }

                android_test_results_df = pd.DataFrame(android_test_results)
                android_test_results_df = android_test_results_df.fillna("None")

                report.set_table_dataframe(android_test_results_df)
                report.build_table()

                report.set_text("NOTE: VLC statistics on Android devices show audio parameters such as channel count and" +
                " sample rate as zero due to Media Codec limitations in Android. This behavior is application-specific and " +
                "does not indicate an issue with audio decoding or streaming quality.")
                report.build_text_simple()
            if self.host_res:
                report.set_table_title("Test Result For Host")
                report.build_table_title()
                report_data = self.extract_data_for_reporting_for_host()

                for i in range(len(report_data["hostnames"])):
                    device_info = {
                        "Device Name": report_data["hostnames"][i],
                        "Device Type": report_data["device_types"][i],
                        "Mac Address": report_data["mac"][i],
                        "Channel": report_data["channel"][i],
                        "RSSI (dBm)": report_data["rssi"][i],
                    }
                    metrics = [
                        ("Input bytes read", report_data["input_bytes_read"][i]),
                        ("Input bitrate", report_data["input_bitrate"][i]),
                        ("Demux bytes read", report_data["demux_bytes_read"][i]),
                        ("Demux bitrate", report_data["demux_bitrate"][i]),
                        ("Discontinuities", report_data["discontinuities"][i]),
                    ]
                    self.build_device_metrics_table(report,device_info, metrics)

            report.build_custom()
            report.build_footer()
            report.write_html()
            report.write_pdf()
        except Exception as e:
            logging.error(f"Error in create_report function {e}", exc_info=True)

def main():

    parser = argparse.ArgumentParser(
        prog='lf_interop_vlc.py',
        formatter_class=argparse.RawTextHelpFormatter,
        description=r'''
------------------------
LANforge VLC Interoperability Test
------------------------
This script sets up a VLC media streaming test using LANforge.
It allows you to stream video from a host device to multiple client devices over Wi-Fi.
1) python3 lf_interop_vlc.py --video_name 'C:\Users\Administrator\Downloads\sample.mp4' --duration 300 --mcast_port 1234 --mcast_addr 239.255.0.1 --host_res 1.13 --server_ip 192.168.0.57 //with host id and video path
2) python3 lf_interop_vlc.py --video_name 'C:\Users\Administrator\Downloads\sample.mp4' --duration 300 --mcast_port 1234 --mcast_addr 239.255.0.1 --server_ip 192.168.0.57 //takes first non android user selected devices as host
3) python3 lf_interop_vlc.py --duration 300 --mcast_port 1234 --mcast_addr 239.255.0.1 --server_ip 192.168.0.57 //all devices as client
        ''')
    # required = parser.add_argument_group('Required arguments')
    optional = parser.add_argument_group('Optional arguments')

    # optional arguments
    optional.add_argument('--mgr',
                          type=str,
                          help='hostname where LANforge GUI is running',
                          default='localhost')
    optional.add_argument('--mcast_addr',
                          type=str,
                          help='IP for streaming video on host',
                          default='239.255.0.1')
    optional.add_argument('--mcast_port',
                          type=str,
                          help='Port for streaming video on host',
                          default='1234')
    optional.add_argument('--host_res',
                          type=str,
                          help='host resource id to broadcast the video the video',
                          default=None)
    optional.add_argument('--video_name',
                          type=str,
                          help='Video file name to strema on host',
                          default=None)
    optional.add_argument('--duration',
                          type=int,
                          help='duration of test',
                          default=60)
    optional.add_argument('--server_ip',
                          type=str,
                          help='server ip on which client will request',
                          default="0.0.0.0")
    optional.add_argument('--server_port',
                          type=int,
                          help='port of flask server',
                          default=5959)           
    parser.add_argument('--help_summary', default=None, action="store_true", help='Show summary of what this script does')
    optional.add_argument('--device_list', help="Enter the devices on which the test should be run", default=[])

    args = parser.parse_args()

    if args.mgr is None:
        fetched_local_ip = socket.gethostbyname(socket.gethostname())
        print(f"No --mgr provided. Using local IP address: {fetched_local_ip}")
        args.mgr = fetched_local_ip

    vlc_stream_obj = VLCStream(manager_ip=args.mgr,mcast_addr=args.mcast_addr,mcast_port=args.mcast_port,video_name=args.video_name,host_res=args.host_res,duration=args.duration,fserver=args.server_ip,fport=args.server_port,device_list=args.device_list)
    vlc_stream_obj.run_flask_server()
    vlc_stream_obj.get_resource_data()
    vlc_stream_obj.create()
    vlc_stream_obj.start_generic()
    print("starting test")
    print(vlc_stream_obj.start_time)
    start = datetime.now()
    end = start + timedelta(seconds=args.duration)
    while datetime.now()<end:
        time.sleep(1)
    time.sleep(20)

    vlc_stream_obj.stop_generic()
    print(vlc_stream_obj.stats)
    vlc_stream_obj.create_report()
    # vlc_stream_obj.cleanup()

if __name__ == "__main__":
    main()