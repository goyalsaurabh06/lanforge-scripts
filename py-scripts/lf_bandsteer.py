#!/usr/bin/env python3

import os
import re
import csv
import sys
import time
import shlex
import logging
import paramiko
import argparse
import threading
import importlib
import subprocess
import platform
from itertools import combinations
from datetime import datetime
# from lf_report import lf_report
import plotly.graph_objs as go
from lf_graph import lf_bar_graph_horizontal, lf_bar_graph

logger = logging.getLogger(__name__)
if sys.version_info[0] != 3:
    logger.critical("This script requires Python 3")
    exit(1)

sys.path.append(os.path.join(os.path.abspath(__file__ + "../../../")))
lfcli_base = importlib.import_module("py-json.LANforge.lfcli_base")
LFCliBase = lfcli_base.LFCliBase
realm = importlib.import_module("py-json.realm")
LFUtils = importlib.import_module("py-json.LANforge.LFUtils")
cv_test_manager = importlib.import_module("py-json.cv_test_manager")
sniff_radio = importlib.import_module("py-scripts.lf_sniff_radio")
sta_connect = importlib.import_module("py-scripts.sta_connect2")
create_qvlan = importlib.import_module("py-scripts.create_qvlan")
CreateQVlan = create_qvlan.CreateQVlan
Realm = realm.Realm
lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")

'''

python3 lf_bandsteer.py --set_max_attenuators "{'1.f1.3319':{(3,4)}}" --attenuators "{'1.1.3319':{(1,2)}}" --step 3 --max_attenuation 55 --iteration 1 --wait_time 4 --sniff_radio_1 1.1.wiphy5 --sniff_radio_2 1.1.wiphy6 --sniff_channel_1 11 --sniff_channel_2 36 --radios 'ssid==roam-5Ghz-air,passwd=="OpenWifi",security==wpa2,radio==1.1.wiphy4,num_sta==1,sta_flag==use-bss-transition' --upstream 1.1.eth2 --sniff_duration 20m  --mgr 10.28.3.43  --run_traffic upload --disable_restart_dhcp --steer_type steer_twog --custom_wifi_cmd 'bgscan="simple:15:-65:60:4"'

python3 lf_bandsteer.py --set_max_attenuators "{'1.1.3319':{(3,4)}}" --attenuators "{'1.1.3319':{(1,2)}}" --step 3 --max_attenuation 55 --iteration 1 --wait_time 10 --sniff_radio_1 1.1.wiphy5 --sniff_radio_2 1.1.wiphy6 --sniff_channel_1 11 --sniff_channel_2 36 --radios 'ssid==roam-5Ghz-air,passwd=="OpenWifi",security==wpa2,radio==1.1.wiphy4,num_sta==1,sta_flag==use-bss-transition' --upstream 1.1.eth2 --sniff_duration 20m  --mgr 10.28.3.43  --run_traffic upload --disable_restart_dhcp --steer_type steer_fiveg --custom_wifi_cmd 'bgscan="simple:15:-65:60:4"'


'''


class BandSteer(Realm):

    def __init__(self,
                 lanforge_ip='localhost',
                 port=8080,
                 station_radio='1.1.wiphy2',
                 sniff_radio_1='1.1.wiphy0',
                 sniff_radio_2='1.1.wiphy1',
                 sniff_channel_1='6',
                 sniff_channel_2='36',
                 sniff_frequency_1=2437,
                 sniff_frequency_2=5180,
                 attenuators=[],
                 set_max_attenuators=None,
                 step=100,
                 test_type='standard',
                 max_attenuation=950,
                 upstream='1.1.eth1',
                 ssid=None,
                 security=None,
                 password=None,
                 num_sta=None,
                 station_flag=None,
                 option=None,
                 identity=None,
                 ttls_pass=None,
                 sta_type=None,
                 iteration_based=True,
                 duration=None,
                 wait_time=10,
                 sniff_duration=300,
                 iterations=1,
                 roam_timeout=50,
                 bg_scan='simple:10:-65:300:4',
                 traffic=False,
                 disable_restart_dhcp=False,
                 custom_wifi_cmd=None,
                 softroam=False,
                 steer_type=None,
                 initial_band_pref=None,
                 real_devices=True,
                 ):
        super().__init__(lanforge_ip, port)

        self.lanforge_ip = lanforge_ip
        self.port = port
        self.upstream = upstream

        self.attenuators = attenuators
        self.set_max_attenuators = set_max_attenuators
        self.step = step * 10
        self.max_attenuation = max_attenuation * 10

        self.ssid = ssid
        self.security = security
        self.password = password
        self.num_sta = num_sta
        self.station_flag = station_flag
        self.option = option
        self.identity = identity
        self.ttls_pass = ttls_pass
        self.sta_type = sta_type

        self.iteration_based = iteration_based
        self.duration = duration
        self.wait_time = wait_time
        self.sniff_channel_1 = sniff_channel_1
        self.sniff_frequency_1 = sniff_frequency_1
        self.sniff_channel_2 = sniff_channel_2
        self.sniff_frequency_2 = sniff_frequency_2
        self.iterations = iterations
        self.soft_roam = softroam

        self.real_devices = real_devices
        self.sniff_radio_1 = sniff_radio_1
        self.sniff_radio_2 = sniff_radio_2
        self.sniff_duration = sniff_duration
        self.station_radio = station_radio
        self.bg_scan = bg_scan
        self.traffic = traffic
        self.disable_restart_dhcp = disable_restart_dhcp
        self.custom_wifi_cmd = custom_wifi_cmd
        self.station_profile = self.new_station_profile()
        # self.stop_traffic_thread = threading.Event()
        # self.traffic_thread = None

        # Band Steering variables
        self.test_type = test_type
        self.steer_type = steer_type
        self.initial_band_pref = initial_band_pref
        # self.traffic_data = dict()
        self.station_ips = dict()
        self.ping_cx_profile = None
        self.traffic_cx_profile = None
        # initiating gen cx profile for Ping
        self.generic_endps_profile = self.new_generic_endp_profile()

        # reporting variable
        # self.band_steer_data = {}
        # self.bssid_based_totals = {}
        # self.channel_based_totals = {}
        # self.steer_bssid_info = {}
        # self.station_based_roam_count = {}
        # self.sta_steer_count = {}
        # self.final_data = {}
        self.sta_mac = {}
        # self.roam_timeout = roam_timeout
        # self.bssid_based_info = {}
        # self.ssid_based_info = {}
        # self.total_status = []

        # self.atten_serial_ = []
        # self.module_set = []
        # self.attenuator_combinations = []
        # self.unused_attenuator_combinations = []

        self.sniff_radio_resource_1, self.sniff_radio_shelf_1, self.sniff_radio_port_1, _ = self.name_to_eid(
            self.sniff_radio_1)
        self.sniff_radio_resource_2, self.sniff_radio_shelf_2, self.sniff_radio_port_2, _ = self.name_to_eid(
            self.sniff_radio_2)

        self.staConnect = sta_connect.StaConnect2(host=self.lanforge_ip, port=self.port, outfile="sta_connect2.csv")
        self.combined_sniff = bool(1 if (self.sniff_radio_1) and (self.sniff_radio_2) else 0)


    def create_specific_cx(self, station_list, traffic_type='lf_tcp', upstream=None, tos=None, pairs=0):

        self.traffic_cx_profile = self.new_l3_cx_profile()
        self.traffic_cx_profile.host = self.lanforge_ip
        self.traffic_cx_profile.port = self.port

        self.traffic_cx_profile.side_a_min_bps = 0
        self.traffic_cx_profile.side_a_max_bps = 0
        self.traffic_cx_profile.side_b_min_bps = 100_000_000
        self.traffic_cx_profile.side_b_max_bps = 0

        if pairs == 0:
            self.traffic_cx_profile.name_prefix = 'steer_DL_'
            self.traffic_cx_profile.create(endp_type=traffic_type,
                                   side_a=station_list,
                                   side_b=self.upstream if upstream is None else upstream,
                                   sleep_time=0,tos=tos)
        else:
            for pair in range(1, int(pairs)+1):
                self.traffic_cx_profile.name_prefix = f'steer_DL_{pair}_'
                self.traffic_cx_profile.create(endp_type=traffic_type,
                                       side_a=station_list,
                                       side_b=self.upstream if upstream is None else upstream,
                                   sleep_time=0,tos=tos)

    def _start_profile(self, profile):

        if not profile:
            return

        print(f"Starting profile: {profile.name_prefix}")

        # Attach monitoring state to profile
        profile.stop_event = threading.Event()
        profile.stop_event.clear()
        profile.traffic_data = {}

        profile.thread = threading.Thread(
            target=self._record_traffic_data,
            args=(profile,),
            daemon=True
        )
        profile.thread.start()

        profile.start_cx()

    def _stop_profile(self, profile):

        if not profile:
            return

        print(f"Stopping profile: {profile.name_prefix}")

        for name in profile.created_cx.keys():
            self.json_post("/cli-json/set_cx_state", {
                "test_mgr": "ALL",
                "cx_name": name,
                "cx_state": "STOPPED"
            }, debug_=self.debug)

        # Stop monitoring thread
        if hasattr(profile, "stop_event"):
            profile.stop_event.set()

        if hasattr(profile, "thread") and profile.thread.is_alive():
            profile.thread.join(timeout=5)

        print(f"{profile.name_prefix} monitoring stopped")
        time.sleep(2)

    def _record_traffic_data(self, profile):

        while not profile.stop_event.is_set():
            response_json = dict(self.json_get('/cx/all/'))

            for cx_name in profile.created_cx.keys():
                if cx_name not in response_json:
                    continue

                traffic_details = response_json[cx_name]
                dt = datetime.now()

                profile.traffic_data.setdefault(cx_name, []).append({
                    "timestamp": dt.strftime("%H:%M:%S"),
                    "bps_rx_a": traffic_details.get("bps rx a"),
                    "bps_rx_b": traffic_details.get("bps rx b"),
                    "rx_drop_a": traffic_details.get("rx drop % a"),
                    "rx_drop_b": traffic_details.get("rx drop % b"),
                })

            time.sleep(1)

    def create_ping_cx(self, station_list, traffic_type='lf_tcp'):
        self.ping_cx_profile = self.new_l3_cx_profile()
        self.ping_cx_profile.host = self.lanforge_ip
        self.ping_cx_profile.port = self.port

        self.ping_cx_profile.side_a_min_bps = 0
        self.ping_cx_profile.side_a_max_bps = 0
        self.ping_cx_profile.side_b_min_bps = 56000
        self.ping_cx_profile.side_b_max_bps = 0

        self.ping_cx_profile.name_prefix = 'ping_'

        # if len(station_list) > 1:
        #     for sta_a, sta_b in combinations(station_list, 2):
        #         self.ping_cx_profile.create(
        #             endp_type=traffic_type,
        #             side_a=[sta_a],
        #             side_b=sta_b
        #         )

        for sta in station_list:
            self.ping_cx_profile.create(
                endp_type=traffic_type,
                side_a=[sta],
                side_b=self.upstream
            )

    def check_connectivity(self, profile, min_bps=1):

        if not hasattr(profile, "traffic_data"):
            return False

        if not profile.traffic_data:
            return False

        for cx_name, samples in profile.traffic_data.items():

            if not samples:
                return False

            recent_samples = samples[-5:]

            traffic_ok = any(
                (sample.get("bps_rx_a", 0) or 0) > min_bps or
                (sample.get("bps_rx_b", 0) or 0) > min_bps
                for sample in recent_samples
            )

            if not traffic_ok:
                print(f"[DEBUG] No traffic detected for {cx_name}")
                return False

        return True

    def _expand_ping_lists(self, src_list, dst_list):
        """
        Returns aligned source and destination lists
        Skips self-ping
        """

        expanded_src = []
        expanded_dst = []

        for src in src_list:
            for dst in dst_list:
                if src == dst:
                    continue

                expanded_src.append(src)
                expanded_dst.append(self.change_port_to_ip(dst))

        return expanded_src, expanded_dst

    def run_generic_ping(
            self,
            src_list,
            dst_list,
            mode="once",
            count=5,
            interval=1,
            tag="ping"
    ):

        expanded_src, expanded_dst = self._expand_ping_lists(src_list, dst_list)

        if not expanded_src:
            raise ValueError("No valid ping combinations generated")

        # Configure profile
        self.generic_endps_profile.type = "lfping"
        self.generic_endps_profile.name_prefix = f"gen_{tag}"

        # Create endpoints only once
        self.generic_endps_profile.create(ports=expanded_src)

        # Assign proper ping command per endpoint
        print("Created Gen Endpoints", self.generic_endps_profile.created_endp)
        for idx, endp_name in enumerate(self.generic_endps_profile.created_endp):

            dst_ip = expanded_dst[idx]

            if mode == "once":
                cmd = f"ping -c {count} -i {interval} {dst_ip}"
            else:
                cmd = f"ping -i {interval} {dst_ip}"

            print("Command ping :", cmd)
            self.generic_endps_profile.set_cmd(
                endp_name,
                cmd=cmd
            )

        time.sleep(3)
        # Start CX
        self.generic_endps_profile.start_cx()

        if mode == "once":
            time.sleep(count * interval + 3)
            self.generic_endps_profile.stop_cx()

            status, data = self._evaluate_generic_ping()
            self.generic_endps_profile.cleanup()
            return status, data

        return True, {}

    def stop_generic_ping(self):

        if not hasattr(self, "generic_endps_profile"):
            return True, {}

        self.generic_endps_profile.stop_cx()
        time.sleep(2)

        status, data = self._evaluate_generic_ping()
        self.generic_endps_profile.cleanup()

        return status, data

    def _evaluate_generic_ping(self):
        """
        Returns:
            overall_status (bool)
            results (dict): key = "SRC -> DST", value = {
                endpoint,
                raw,
                status
            }
        """
        response = self.json_get(
            "generic/list?fields=name,last+results"
        )

        results = {}
        overall_status = True

        for ep in response.get("endpoints", []):
            for _, data in ep.items():
                endp_name = data.get("name", "")
                raw = data.get("last results", "")

                # Extract src / dst from endpoint name
                src = "unknown-src"
                dst = "unknown-dst"

                if "_to_" in endp_name:
                    try:
                        left, right = endp_name.split("_to_", 1)
                        src = left.split("_")[-1]
                        dst = right
                    except Exception:
                        pass

                key = f"{src}->{dst}"

                # Determine ping status
                status = not (
                        not raw
                        or "Unreachable" in raw
                        or "100%" in raw
                        or "0 received" in raw
                )

                if not status:
                    overall_status = False

                results[key] = {
                    "endpoint": endp_name,
                    "raw": raw,
                    "status": status
                }

        return overall_status, results

    def start_ping_cx(self):
        self._start_profile(self.ping_cx_profile)

    def stop_ping_cx(self):
        self._stop_profile(self.ping_cx_profile)

    def start_traffic_cx(self):
        self._start_profile(self.traffic_cx_profile)

    def stop_traffic_cx(self):
        self._stop_profile(self.traffic_cx_profile)

    def clean_ping_cx(self):
        self.ping_cx_profile.clean_cx_lists()
        self.ping_cx_profile.cleanup()

    def clean_traffic_cx(self):
        self.traffic_cx_profile.clean_cx_lists()
        self.traffic_cx_profile.cleanup()

    def stop_specific_cx(self, station_list, profile=None):
        profile = profile if profile is not None else self.traffic_cx_profile
        for name in profile.created_cx.keys():
            for station in station_list:
                sta_name = station.split('.')[-1]
                if sta_name in name:
                    print(f"Stopping CX: {name}")
                    self.json_post("/cli-json/set_cx_state", {
                        "test_mgr": "ALL",
                        "cx_name": name,
                        "cx_state": "STOPPED"
                    }, debug_=self.debug)
        time.sleep(2)

    def cleanup_stations(self):
        logger.info('Cleaning up the stations if exists')
        sta_list = self.get_station_list()
        self.station_profile.cleanup(sta_list, delay=1)
        self.wait_until_ports_disappear(sta_list=sta_list,
                                        debug_=True)
        logger.info('All stations got removed. Aborting...')
        exit(1)

    def set_atten_idx(self, eid, atten_ddb, atten_idx='all'):
        eid_toks = self.name_to_eid(eid, non_port=True)
        req_url = "cli-json/set_attenuator"
        data = {
            "shelf": eid_toks[0],
            "resource": eid_toks[1],
            "serno": eid_toks[2],
            "atten_idx": atten_idx,
            "val": atten_ddb,
        }
        self.json_post(req_url, data)

    def set_attenuators(self, atten1, atten2):
        """
        atten1 = [shelf,resource,serno,ch1,ch2]
        atten2 = [shelf,resource,serno,ch1,ch2]

        MODIFIED logic:
        - For steer_fiveg (5G -> 2G -> 5G):
            * Start: active=0, passive=0 (both on 5G)
            * Phase 1 (5G->2G): Increase active attenuation to steer to 2G
            * Phase 2 (2G->5G): Decrease passive attenuation to steer back to 5G

        - For steer_twog (5G -> 2G):
            * Original logic remains: Increase active, decrease passive
        """
        if self.steer_type == "steer_fiveg":
            # For steer_fiveg: atten1 controls 5G->2G, atten2 controls 2G->5G
            active = atten1  # Will increase to steer from 5G to 2G
            passive = atten2  # Will decrease to steer from 2G back to 5G

            # Start BOTH at 0 (connected to 5GHz)
            for idx in active[3:]:
                self.set_atten_idx(
                    f"{active[0]}.{active[1]}.{active[2]}",
                    0,
                    idx - 1
                )
            for idx in passive[3:]:
                self.set_atten_idx(
                    f"{passive[0]}.{passive[1]}.{passive[2]}",
                    0,
                    idx - 1
                )
        else:
            # steer_twog: original logic
            active = atten2
            passive = atten1

            for idx in active[3:]:
                self.set_atten_idx(
                    f"{active[0]}.{active[1]}.{active[2]}",
                    0,
                    idx - 1
                )
            # PASSIVE starts at MAX dB (2GHz weak)
            for idx in passive[3:]:
                self.set_atten_idx(
                    f"{passive[0]}.{passive[1]}.{passive[2]}",
                    self.max_attenuation,
                    idx - 1
                )

        self.active_attenuator = active
        self.passive_attenuator = passive

    def get_port_data(self, station, field):
        shelf, resource, port = station.split('.')
        data = self.json_get(
            '/port/{}/{}/{}?fields={}'.format(shelf, resource, port, field))
        if (data is not None and 'interface' in data.keys() and data['interface'] is not None):
            return data['interface'][field]
        else:
            logging.warning(
                'Station {} not found. Removing it from test.'.format(station))
            return None


    def cleanup(self):
        self.monitor.cleanup(desired_ports=['sniffer0'])

    def create_monitor(self):
        self.cleanup()
        channel = self.channel
        if channel != "AUTO":
            channel = int(channel)

        self.monitor.create(resource_=self.sniff_radio_resource,
                            radio_=self.sniff_radio_port, channel=channel, frequency=self.frequency,
                            name_='sniffer0')

    def start_sniff(self, capname='band_steer_test.pcap'):
        self.monitor.admin_up()
        self.monitor.start_sniff(capname=capname, duration_sec=self.sniff_duration)

    def stop_sniff(self):
        time.sleep(15)
        self.monitor.admin_down()

    def get_sta_list_before_creation(self,
                                     radio,
                                     start_id=0,
                                     num_sta=1):

        sta_list = LFUtils.port_name_series(prefix="sta",
                                            start_id=start_id,
                                            end_id=start_id + num_sta - 1,
                                            padding_number=10000,
                                            radio=radio)
        return sta_list

    def get_station_ips(self, station_list=None):
        self.station_ips = dict()
        if station_list is None:
            station_list = self.get_station_list()
        print('Station List for IP retrieval:', station_list)
        # if len(station_list) == 2:
        for station in station_list:
            ip_addr = self.get_port_data(station, 'ip')
            retry_count = 0
            while (ip_addr is None) or (ip_addr == 'NA') or (ip_addr == 'Not-Associated'):
                if retry_count >= 30:
                    break
                time.sleep(3)
                ip_addr = self.get_port_data(station, 'ip')
                retry_count += 1
            if ip_addr is not None:
                self.station_ips[station] = ip_addr
        return self.station_ips

    def _ssh_run_mgr(self, cmd, host=None, timeout=30):
        if not hasattr(self, "_mgr_ssh"):
            self._mgr_ssh = paramiko.SSHClient()
            self._mgr_ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._mgr_ssh.connect(
                hostname=self.lanforge_ip if host is None else host,
                username="lanforge",
                password="lanforge",
                look_for_keys=False,
                allow_agent=False,
                timeout=20
            )

        stdin, stdout, stderr = self._mgr_ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode(errors="ignore")
        err = stderr.read().decode(errors="ignore")
        rc = stdout.channel.recv_exit_status()
        return rc, out, err

    def is_pinging(self):
        logs = []
        logs.append("PINGING STATIONS TO VERIFY CONNECTIVITY")

        if not hasattr(self, "station_ips") or not self.station_ips:
            self.get_station_ips()

        logs.append(f"Retrieved Station IPs: {self.station_ips}")

        if not self.station_ips or len(self.station_ips) < 2:
            logs.append(f"Need at least 2 stations for ping test. Found: {len(self.station_ips)}")
            return False, "\n".join(logs)

        vrf_exec = "/home/lanforge/vrf_exec.bash"
        sudo_pass = "lanforge"

        # Get list of stations and their IPs
        stations = list(self.station_ips.items())

        # Test connectivity between stations (avoid self-ping)
        for i, (src_port, src_ip) in enumerate(stations):
            # Find a target station that's different from the source
            for j, (target_port, target_ip) in enumerate(stations):
                if i == j:  # Skip self-ping
                    continue

                rc = None
                out = ""
                err = ""

                try:
                    parts = src_port.split(".")
                    sta_name = parts[-1]  # sta0000, sta0001, etc.
                    resource = parts[1]  # 1 or 2

                    cmd = (
                        f"echo '{sudo_pass}' | "
                        f"sudo -S {vrf_exec} {sta_name} ping -c 3 {target_ip}"
                    )

                    # Choose correct manager
                    if resource == "1":
                        rc, out, err = self._ssh_run_mgr(cmd, host=None)
                    elif resource == "2":
                        continue
                        # resource_host = self.get_resource_host(resource=resource)
                        # rc, out, err = self._ssh_run_mgr(cmd, host=list(resource_host.values())[0])
                    else:
                        logs.append(f"Unknown resource for port {src_port}")
                        return False, "\n".join(logs)

                    logs.append(
                        f"Pinging {target_ip} (station {target_port}) from {sta_name} ({src_port}) -> rc={rc}"
                    )

                    if out.strip():
                        logs.append(f"STDOUT:\n{out.strip()}")
                    if err.strip():
                        logs.append(f"STDERR:\n{err.strip()}")

                    # Strong ping failure detection
                    if (
                            rc != 0
                            or "100% packet loss" in out
                            or "0 received" in out
                            or "Destination Host Unreachable" in out
                    ):
                        logs.append(f"Ping FAILED from {src_port} to {target_port}")
                        return False, "\n".join(logs)

                    logs.append(f"✓ Ping successful from {src_port} to {target_port}")
                    break  # Successful ping to at least one other station

                except Exception as e:
                    logs.append(f"Exception while pinging from {src_port} to {target_port}: {e}")
                    return False, "\n".join(logs)

        logs.append("PINGING SUCCESSFUL - All stations can reach each other")
        return True, "\n".join(logs)

    def run_ping(self, source, destination) -> bool:
        cmd = ["sudo", "./vrf_exec.bash", source, "ping", "1", destination]

        try:
            result = subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if result != 0:
                return False
        except Exception:
            return False

        return True

    def get_channel(self, as_dict=False, station_list=None):
        def parse_channel(value):
            if value is None:
                return None
            match = re.search(r"-?\d+", str(value))
            return int(match.group()) if match else None

        channel_info = []
        channel_map = {}
        removable_stations = []

        if station_list is None:
            station_list = self.get_station_list()

        for station in station_list:
            raw_value = self.get_port_data(station, 'channel')
            retry_count = 0

            while raw_value in (None, '-1', -1,  'NA', 'Not-Associated'):
                if retry_count >= 30:
                    break
                time.sleep(3)
                raw_value = self.get_port_data(station, 'channel')
                retry_count += 1

            if raw_value is not None:
                parsed = parse_channel(raw_value)
                if parsed is not None:
                    channel_info.append(parsed)
                    channel_map[station] = parsed
                else:
                    removable_stations.append(station)
            else:
                removable_stations.append(station)

        for station in removable_stations:
            if station in self.station_list:
                self.station_list.remove(station)

        return channel_map if as_dict else channel_info

    def get_bssids(self, as_dict=False, station_list=None):
        bssids = []
        bssid_map = {}
        removable_stations = []

        if station_list is None:
            station_list = self.get_station_list()

        for station in station_list:
            bssid = self.get_port_data(station, 'ap')
            retry_count = 0

            while bssid in (None, 'NA', 'Not-Associated', 'null'):
                if retry_count >= 30:
                    break
                time.sleep(3)
                bssid = self.get_port_data(station, 'ap')
                retry_count += 1

            if bssid is not None and bssid not in ('null', 'NA', 'Not-Associated'):
                bssids.append(bssid)
                bssid_map[station] = bssid
            else:
                removable_stations.append(station)

        for station in removable_stations:
            if station in self.station_list:
                self.station_list.remove(station)

        return bssid_map if as_dict else bssids

    def get_rssi(self, as_dict=False, station_list=None):
        rssi_lst = []
        rssi_map = {}
        removable_stations = []

        if station_list is None:
            station_list = self.get_station_list()

        for station in station_list:
            rssi = self.get_port_data(station, 'signal')
            retry_count = 0
            while rssi in (None, 'NA', "", 'null'):
                if retry_count >= 30:
                    break
                time.sleep(3)
                rssi = self.get_port_data(station, 'signal')
                retry_count += 1

            if rssi is not None and rssi not in ('null', 'NA', ""):
                rssi_lst.append(rssi)
                rssi_map[station] = rssi
            else:
                removable_stations.append(station)

        return rssi_map if as_dict else rssi_lst

    def get_ips(self, as_dict=False, station_list=None):
        ips_lst = []
        ips_map = {}
        removable_stations = []

        if station_list is None:
            station_list = self.get_station_list()

        for station in station_list:
            ips = self.get_port_data(station, 'ip')
            retry_count = 0
            while ips in (None, '0.0.0.0', ""):
                if retry_count >= 30:
                    break
                time.sleep(3)
                ips = self.get_port_data(station, 'ip')
                retry_count += 1

            if ips is not None and ips not in ('0.0.0.0', 'NA', ""):
                ips_lst.append(ips)
                ips_map[station] = ips
            else:
                removable_stations.append(station)

        return ips_map if as_dict else ips_lst

    def get_sta_bssids(self):
        sta_bssids = {}
        for station in self.get_station_list():
            bssid = self.get_port_data(station, 'ap')
            if bssid == 'NA':
                time.sleep(3)
                bssid = self.get_port_data(station, 'ap')
            if (bssid is not None):
                sta_bssids[f'{station}'] = bssid
        return sta_bssids

    def get_signal_strength(self, station):
        signal = self.get_port_data(station, 'signal')
        if signal == 'NA':
            time.sleep(3)
            signal = self.get_port_data(station, 'signal')
        if (signal is not None):
            return int(signal.split(' ')[0])

    def get_throughput_snapshot(self, label, profile=None):

        profile = profile if profile is not None else self.traffic_cx_profile
        lines = [f"Throughput Snapshot: {label}", "-" * 50]

        if not hasattr(profile, "traffic_data"):
            return "No traffic data"

        for cx_name, samples in profile.traffic_data.items():
            if not samples:
                continue

            last = samples[-1]

            lines.append(
                f"{cx_name} | "
                f"RX A: {last['bps_rx_a']} bps | "
                f"RX B: {last['bps_rx_b']} bps | "
                f"Drop A: {last['rx_drop_a']}% | "
                f"Drop B: {last['rx_drop_b']}%"
            )

        return "\n".join(lines)

    def monitor_sta_scan(self):
        for station_name in self.station_list:
            station = (station_name.split(".")[2])
            cmd_exec = False
            row_cnt = 0
            sta_bssids = self.get_sta_bssids()
            before_bssid = sta_bssids[f'{station_name}']
            target_strength = int(self.bg_scan.split(':')[2])
            while True:
                signal_strength = self.get_signal_strength(station=station_name)
                if signal_strength is not None:
                    if signal_strength <= target_strength:
                        result = subprocess.check_output(f"wpa_cli -i {station} scan_results", shell=True, text=True)
                        # Save to a file named after the station
                        with open(f"wpa_sta_scan_{station}.txt", "a") as file:
                            file.write(
                                f"_________________________________________________________________________________________________{station} with signal strength {signal_strength}\n")
                            file.write(result)
                            row_cnt += 1
                        time.sleep(2)
                        print(f"Saved scan results for {station}")
                        cmd_exec = True
                    elif (cmd_exec and signal_strength > target_strength):
                        while signal_strength > target_strength and signal_strength == 0:
                            continue
                        sta_bssids = self.get_sta_bssids()
                        after_bssid = sta_bssids[f'{station_name}']
                        result = subprocess.check_output(f"wpa_cli -i {station} scan_results", shell=True, text=True)
                        # Save to a file named after the station
                        with open(f"wpa_sta_scan_{station}.txt", "a") as file:
                            file.write(
                                f"_______________________________________________________________________________________{before_bssid} ------> {after_bssid}______________________{station} with signal strength {signal_strength}\n")
                            file.write(result)
                            row_cnt += 1
                        print(f"Signal strength for {station} is {signal_strength} dBm. Skipping scan...")
                        print(f"Number of Rows appended for wpa_sta_scan_{station} is {row_cnt}.")
                        break
                else:
                    print(f"Could not retrieve signal strength for {station}.")

    def get_station_list(self):
        sta = self.staConnect.station_list()
        if sta == "no response":
            return "no response"
        sta_list = []
        for group in sta:
            for port in group:
                # remove dummy stations
                if "dummy" in str(port).lower():
                    continue
                sta_list.append(port)

        return sta_list

    def set_unused_atten(self, attenuator, modules):
        for idx in modules:
            self.set_atten_idx(
                f"{attenuator}",
                "950",
                idx - 1
            )

    def create_build_qvlan(self, vlan_id, ipv4_addresses, ipv4_netmasks, ipv4_gateways):
        qvlan = CreateQVlan(mgr=self.lanforge_ip,
                            mgr_port=self.port,
                            parent_port=self.upstream,
                            qvlan_ids=[vlan_id],
                            dhcpv4=True,
                            ipv4_addresses=ipv4_addresses,
                            ipv4_netmasks=ipv4_netmasks,
                            ipv4_gateways=ipv4_gateways )
        qvlan.build()

    def steer_specific_client(self, attenuators, start_idx, end_idx, direction=None):
        """
        Simple version with direction parameter.
        attenuators: "1.1.3319" (serial number of the attenuator)
        direction: None (use self.steer_type), "inc", or "dec"
        """
        # Parse attenuators
        atten_list = []
        atten_list.append({
            'serial': attenuators.split(".")[-1],
            'modules': (start_idx, end_idx)
        })

        # Determine direction
        if direction is None:
            direction = 'inc' if self.steer_type == 'steer_twog' else 'dec'
        else:
            direction = direction.lower()
            if direction not in ['inc', 'dec']:
                direction = 'inc' if self.steer_type == 'steer_twog' else 'dec'

        # Generate attenuation sequence
        if direction == 'inc':
            atten_change = list(range(0, self.max_attenuation + 1, self.step))
            if self.max_attenuation not in atten_change:
                atten_change.append(self.max_attenuation)
        else:
            atten_change = list(range(self.max_attenuation, -1, -self.step))
            if 0 not in atten_change:
                atten_change.append(0)

        # Apply attenuation changes
        for atten in atten_change:
            for atten_info in atten_list:
                try:
                    shelf, resource, serno = map(int, atten_info['name'].split("."))
                    atten_serial = f"{shelf}.{resource}.{serno}"
                    start_port, end_port = atten_info['ports']

                    for port_idx in range(start_port, end_port + 1):
                        self.set_atten(atten_serial, atten, port_idx - 1)
                except ValueError:
                    print(f"Warning: Invalid attenuator: {atten_info['name']}")

            time.sleep(10)

    def pre_cleanup(self, sta_list):
        print("Available list of stations on lanforge-GUI :", sta_list)
        logging.info(str(sta_list))
        station_profile = self.new_station_profile()

        if not sta_list:
            print("No stations are available on lanforge-GUI")
            logging.info("No stations are available on lanforge-GUI")
        else:
            station_profile.cleanup(sta_list, delay=1)
            self.wait_until_ports_disappear(sta_list=sta_list,
                                            debug_=True)

    def create_clients(self,
                       radio,
                       ssid,
                       passwd,
                       security,
                       station_list,
                       station_flag,
                       sta_type,
                       dummy_client=False,
                       initial_band_pref=None,
                       option=None):

        print("Creating stations.")
        logging.info("Creating stations.")
        self.station_profile = self.new_station_profile()
        # self.set_unused_atten(self.max_attenuation)

        if station_flag is not None:
            _flags = station_flag.split(',')
            for flags in _flags:
                logger.info(f"Selected Flags: '{flags}'")
                self.station_profile.set_command_flag("add_sta", flags, 1)

        self.station_profile.use_security(security, ssid, passwd)
        self.station_profile.set_number_template("00")

        self.station_profile.set_command_flag("add_sta", "create_admin_down", 1)

        self.station_profile.set_command_param("set_port", "report_timer", 1000)
        self.station_profile.set_command_flag("add_sta", "80211u_enable", 0)

        self.station_profile.set_command_flag("set_port", "rpt_timer", 1)

        # Need to check based on requirement whether using band pref or NOT
        if initial_band_pref is not None:
            band_pref = {"2GHz": 2, "5GHz": 5}.get(initial_band_pref)
            self.station_profile.set_wifi_extra2(initial_band_pref=band_pref)

        if self.disable_restart_dhcp:
            self.station_profile.set_command_flag("set_port", "no_dhcp_restart", 1)
            self.station_profile.set_command_flag("set_port", "no_ifup_post", 1)
            self.station_profile.set_command_flag("set_port", "use_dhcp", 1)
            self.station_profile.set_command_flag("set_port", "current_flags", 1)
            self.station_profile.set_command_flag("set_port", "dhcp", 1)
            self.station_profile.set_command_flag("set_port", "dhcp_rls", 1)
            self.station_profile.set_command_flag("set_port", "no_dhcp_conn", 1)

        if sta_type == "normal":
            # self.station_profile.set_command_flag("add_sta", "power_save_enable", 1)
            if not self.soft_roam:
                self.station_profile.set_command_flag("add_sta", "disable_roam", 1)
            if self.soft_roam:
                print("Soft roam true")
                logging.info("Soft roam true")
                if option == "otds":
                    print("OTDS present")
                    self.station_profile.set_command_flag(
                        "add_sta", "ft-roam-over-ds", 1)
            # self.station_profile.set_command_flag("set_port", "skip_ifup_roam", 1)
        if sta_type == "enterprise":
            self.station_profile.set_command_flag("add_sta", "8021x_radius", 1)
            self.station_profile.set_wifi_extra(key_mgmt="WPA-EAP",
                                                identity = "testuser",
                                                eap="TTLS",
                                                passwd = "testpasswd",
                                                )
        if sta_type == "11r":
            # self.station_profile.set_command_flag("add_sta", "80211u_enable", 0)
            self.station_profile.set_command_flag("add_sta", "8021x_radius", 1)
            # if not self.soft_roam:
            #     self.station_profile.set_command_flag("add_sta", "disable_roam", 1)
            # if self.soft_roam:
            #     print("Soft roam true")
            #     logging.info("Soft roam true")
            #     if option == "otds":
            #         print("OTDS present")
            # 11kvr => k : neighboring AP so ds enabled 1
            self.station_profile.set_command_flag("add_sta", "ft-roam-over-ds", 1)
            # self.station_profile.set_command_flag("add_sta", "power_save_enable", 1)
            self.station_profile.set_wifi_extra(key_mgmt="FT-PSK",
                                                psk=passwd)

        if sta_type == "11r_enterprise":
            self.station_profile.set_command_flag("add_sta", "8021x_radius", 1)
            self.station_profile.set_command_flag("add_sta", "ft-roam-over-ds", 1)
            self.station_profile.set_wifi_extra(key_mgmt="FT-EAP",
                                                identity="testuser",
                                                eap="TTLS",
                                                passwd="testpasswd",
                                                )
        if sta_type == "11r-sae":
            self.station_profile.set_command_flag("add_sta", "ieee80211w", 2)
            self.station_profile.set_command_flag("add_sta", "80211u_enable", 0)
            self.station_profile.set_command_flag("add_sta", "8021x_radius", 1)
            if not self.soft_roam:
                self.station_profile.set_command_flag("add_sta", "disable_roam", 1)
            if self.soft_roam:
                if option == "otds":
                    self.station_profile.set_command_flag(
                        "add_sta", "ft-roam-over-ds", 1)
            self.station_profile.set_command_flag("add_sta", "power_save_enable", 1)
            self.station_profile.set_wifi_extra(key_mgmt="FT-SAE",
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
                                                anqp_3gpp_cell_net="NA")

        if sta_type == "11r-sae-802.1x":
            self.station_profile.set_command_flag("set_port", "rpt_timer", 1)
            self.station_profile.set_command_flag("add_sta", "ieee80211w", 2)
            self.station_profile.set_command_flag("add_sta", "80211u_enable", 0)
            self.station_profile.set_command_flag("add_sta", "8021x_radius", 1)
            if not self.soft_roam:
                self.station_profile.set_command_flag("add_sta", "disable_roam", 1)
            if self.soft_roam:
                if option == "otds":
                    self.station_profile.set_command_flag(
                        "add_sta", "ft-roam-over-ds", 1)
            self.station_profile.set_command_flag("add_sta", "power_save_enable", 1)
            self.station_profile.set_wifi_extra(key_mgmt="FT-EAP     ",
                                                pairwise="[BLANK]",
                                                group="[BLANK]",
                                                psk="[BLANK]",
                                                eap="TTLS",
                                                identity=self.identity,
                                                passwd=self.ttls_pass,
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
                                                anqp_3gpp_cell_net="NA")

        print('[DEBUG] lf_bandsteer.py Station list check', station_list)
        self.station_profile.create(radio=radio, sta_names_=station_list)
        print("Waiting for ports to appear")
        logging.info("Waiting for ports to appear")
        self.wait_until_ports_appear(sta_list=station_list)

        if self.custom_wifi_cmd:
            for sta in station_list:
                self.set_custom_wifi(resource=int(sta.split('.')[1]),
                                     station=str(sta.split('.')[2]),
                                     cmd=self.custom_wifi_cmd)

        self.station_profile.admin_up()
        if not dummy_client:
            print("Waiting for ports to admin up")
            logging.info("Waiting for ports to admin up")
            if self.wait_for_ip(station_list, timeout_sec=600):
                print("All stations got IPs")
                logging.info("All stations got IPs")
                self.station_list = station_list
                # self.set_unused_atten()
                return True
            else:
                print("Stations failed to get IPs")
                logging.info("Stations failed to get IPs")
                return False

    def record_steering_events(self, before_bssids, before_channels, current_bssids, current_channels,
                               iteration_data, iteration_num, phase=None):
        """
        Record steering events when BSSID or channel changes
        phase: 'phase1' for 5G->2G, 'phase2' for 2G->5G (for steer_fiveg)
        """
        print('------------------------------------------------------------------------')
        print(f'Phase: {phase}' if phase else '')
        print('BSSID before: ', before_bssids)
        print('BSSID after: ', current_bssids)
        print('Channel before: ', before_channels)
        print('Channel after: ', current_channels)
        print('------------------------------------------------------------------------')

        for bssid_index in range(min(len(current_bssids), len(self.station_list))):
            station = self.station_list[bssid_index]

            # For steer_fiveg, we want to record both steering events
            if self.steer_type == "steer_fiveg":
                if (before_bssids[bssid_index] != current_bssids[bssid_index]) \
                        and (before_channels[bssid_index] != current_channels[bssid_index]):
                    self._record_single_steering_event(station, before_bssids[bssid_index],
                                                       current_bssids[bssid_index], before_channels[bssid_index],
                                                       current_channels[bssid_index], iteration_data)
            else:
                # steer_twog logic (original)
                if (station not in iteration_data.keys()):
                    if (before_bssids[bssid_index] != current_bssids[bssid_index]) \
                            and (before_channels[bssid_index] != current_channels[bssid_index]):
                        self._record_single_steering_event(station, before_bssids[bssid_index],
                                                           current_bssids[bssid_index], before_channels[bssid_index],
                                                           current_channels[bssid_index], iteration_data)

    def _record_single_steering_event(self, station, before_bssid, after_bssid, before_channel, after_channel,
                                      iteration_data):
        """Helper method to record a single steering event"""
        if station in self.sta_steer_count:
            self.sta_steer_count[station] += 1
        else:
            self.sta_steer_count[station] = 1

        iteration_data[station] = {
            'BSSID before iteration': before_bssid,
            'BSSID after iteration': after_bssid,
            'Channel before iteration': before_channel,
            'Channel after iteration': after_channel,
            'Signal Strength': self.get_port_data(station, 'signal'),
            'Status': 'PASS' if before_bssid != after_bssid else 'FAIL'
        }

        if station not in self.steer_bssid_info:
            self.steer_bssid_info[station] = {
                'BSSID_before': [],
                'BSSID_after': [],
                'Channel_before': [],
                'Channel_after': [],
                'Signal': [],
                'Status': []
            }

        self.steer_bssid_info[station]['BSSID_before'].append(before_bssid)
        self.steer_bssid_info[station]['BSSID_after'].append(after_bssid)
        self.steer_bssid_info[station]['Channel_before'].append(before_channel)
        self.steer_bssid_info[station]['Channel_after'].append(after_channel)
        self.steer_bssid_info[station]['Signal'].append(iteration_data[station]['Signal Strength'])
        self.steer_bssid_info[station]['Status'].append(iteration_data[station]['Status'])

        if (after_bssid in self.bssid_based_totals):
            self.bssid_based_totals[after_bssid] += 1
        else:
            self.bssid_based_totals[after_bssid] = 1

        if (after_channel in self.channel_based_totals):
            self.channel_based_totals[after_channel] += 1
        else:
            self.channel_based_totals[after_channel] = 1

    def change_port_to_ip(self, upstream_port):
        if upstream_port.count('.') != 3:
            target_port_list = self.name_to_eid(upstream_port)
            shelf, resource, port, _ = target_port_list
            try:
                target_port_ip = self.json_get(f'/port/{shelf}/{resource}/{port}?fields=ip')['interface']['ip']
                upstream_port = target_port_ip
            except BaseException:
                logging.warning(
                    f'The upstream port is not an ethernet port. Proceeding with the given upstream_port {upstream_port}.')
            logging.info(f"Upstream port IP {upstream_port}")
        else:
            logging.info(f"Upstream port IP {upstream_port}")

        return upstream_port

    def roam_test_standard(self, attenuator=None, inc_modules=None, dec_modules=None):
        start_time = datetime.now()

        # Initialize values
        inc_value = 0
        dec_value = self.max_attenuation

        # If both None → nothing to do
        if not inc_modules and not dec_modules:
            logging.warning("No increment or decrement modules provided.")
            return start_time, start_time

        while True:
            stop_inc = True
            stop_dec = True

            if inc_modules and inc_value <= self.max_attenuation:
                for idx in inc_modules:
                    self.set_atten_idx(attenuator, inc_value, idx - 1)
                stop_inc = False

            if dec_modules and dec_value >= 0:
                for idx in dec_modules:
                    self.set_atten_idx(attenuator, dec_value, idx - 1)
                stop_dec = False

            logging.info(
                f"INC={inc_value if inc_modules else 'NA'} | "
                f"DEC={dec_value if dec_modules else 'NA'} | "
                f"Waiting {self.wait_time}s"
            )

            time.sleep(self.wait_time)

            # Update values
            if inc_modules:
                inc_value += self.step
            if dec_modules:
                dec_value -= self.step

            # Exit condition
            if stop_inc and stop_dec:
                break

        end_time = datetime.now()
        return start_time, end_time

    def start_band_steer_test_standard(self, attenuator=None, modules=None, steer='twog'):

        start_time = datetime.now()
        if steer == "fiveg":
            # Steer_fiveg logic (2G -> 5G)
            for attenuator_change_index in range(self.max_attenuation, -1, -self.step):
                for idx in modules:
                    self.set_atten_idx(
                        f"{attenuator}",
                        attenuator_change_index,
                        idx - 1
                    )

                logging.info(
                    'Waiting for {} seconds before monitoring the stations'.format(self.wait_time))
                time.sleep(self.wait_time)

        else:
            # Steer_twog logic (5G -> 2G)
            for attenuator_change_index in range(0, self.max_attenuation + 1, self.step):
                for idx in modules:
                    self.set_atten_idx(
                        f"{attenuator}",
                        attenuator_change_index,
                        idx - 1
                    )

                logging.info(
                    'Waiting for {} seconds before monitoring the stations'.format(self.wait_time))
                time.sleep(self.wait_time)

        end_time = datetime.now()
        data = [["Start Time", start_time.strftime("%Y-%m-%d %H:%M:%S")],
                ["End Time", end_time.strftime("%Y-%m-%d %H:%M:%S")]]

        print(data)
        return start_time, end_time

    def start_continues_ping(self, sta_list, target_list=None):
        if target_list is None:
            target_list = sta_list

        if not hasattr(self, "station_ips") or not self.station_ips:
            self.get_station_ips()

        if not hasattr(self, "cont_ping_procs") or not self.cont_ping_procs:
            self.cont_ping_procs = []

        for src_sta in sta_list:
            if src_sta not in self.station_ips:
                continue

            for dst_sta in target_list:

                # dst_ip = self.station_ips[dst_sta]
                # self.change_port_to_ip(upstream_port=target_list[0])
                target_ip = self.change_port_to_ip(upstream_port=self.upstream)
                cmd = ["./vrf_exec.bash", src_sta, "ping -c 3 ", target_ip]

                try:
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )

                    self.cont_ping_procs.append(proc)
                except Exception as e:
                    print(f"Failed to start ping from {src_sta} to {dst_sta}: {e}")

    def stop_continues_ping(self):
        if not hasattr(self, "cont_ping_procs"):
            return ""

        logs = []

        for idx, proc in enumerate(self.cont_ping_procs):
            try:
                proc.terminate()
                stdout, stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                    stdout, stderr = proc.communicate(timeout=5)
                except Exception as e:
                    logs.append(f"[PING {idx}] Failed to collect logs: {e}")
                    continue
            except Exception as e:
                logs.append(f"[PING {idx}] Termination error: {e}")
                continue

            if stdout:
                logs.append(f"[PING {idx} STDOUT]\n{stdout.strip()}")
            if stderr:
                logs.append(f"[PING {idx} STDERR]\n{stderr.strip()}")

        # Clear all after stopping
        self.cont_ping_procs = []

        return "\n".join(logs)

    def get_mac(self, station_list):
        self.sta_mac = {}

        response = super().json_get('/port/list?fields=_links,alias,mac,port+type')

        for sta in station_list:
            sta_alias = sta.split('.')[2]

            for interface in response.get('interfaces', []):
                for _, port_data in interface.items():

                    if port_data.get('alias') == sta_alias:
                        self.sta_mac[sta] = port_data.get('mac') or port_data.get('ap')

        return self.sta_mac

    def get_atten_info(self):
        atten_info = {}
        response = super().json_get('/atten/all')

        if not response:
            return atten_info

        # Case 1: Multiple attenuators
        if 'attenuators' in response:
            atten_list = response['attenuators']

        # Case 2: Single attenuator
        elif 'attenuator' in response:
            atten_list = [response['attenuator']]

        else:
            return atten_info

        for atten in atten_list:
            for serial, values in atten.items():

                modules = {}
                for i in range(1, 9):
                    modules[f"module_{i}"] = values.get(f"module {i}", "")

                atten_info[serial] = modules

        del response
        return atten_info

    def _ssh_run(self, cmd, timeout=30):
        """Run a command over SSH and return (rc, stdout, stderr)."""
        stdin, stdout, stderr = self.ssh.exec_command(cmd, timeout=timeout)
        out = stdout.read().decode(errors="ignore")
        err = stderr.read().decode(errors="ignore")
        rc = stdout.channel.recv_exit_status()
        return rc, out, err

    def get_resource_host(self, resource="3"):
        valid_ips = {}
        prefix = f"1.{resource}."

        data = self.json_get(
            '/port/all?fields={},{}'.format('ip','down','parent dev'))

        for interface in data.get("interfaces", []):
            for port_name, port_data in interface.items():

                # Match resource 1.2 ports only
                if not port_name.startswith(prefix):
                    continue

                ip = port_data.get("ip")
                down = port_data.get("down", True)
                parent_dev = port_data.get("parent dev", "")

                # Accept only active ports with real IPs and no parent device
                if ip and ip != "0.0.0.0" and not down and parent_dev == "":
                    valid_ips[port_name] = ip

        print(f'Resource ip for given resource {resource} : {valid_ips}')
        return valid_ips

    def start_sniffer(self, different_resource=False):
        self.local_tshark_process = None
        self.filter = "wlan type mgt"

        def get_band_cf(channel):
            try:
                ch = int(channel)
                if 1 <= ch <= 14:
                    return "2427"  # 2.4GHz Band
                elif 36 <= ch <= 177:
                    return "5180"  # 5GHz Band
                elif ch >= 180:
                    return "5955"  # 6GHz Band
            except (ValueError, TypeError):
                pass
            return "2427"

        if not self.combined_sniff and not different_resource:
            self.pcap_obj_2 = sniff_radio.SniffRadio(lfclient_host=self.lanforge_ip, lfclient_port=self.port,
                                                     center_freq="5180",
                                                     radio=self.sniff_radio, channel_freq="5180",
                                                     monitor_name="monitor")

            self.pcap_obj_2.setup(0, 0, 0)
            self.pcap_obj_2.monitor.admin_up()
            print("Waiting until ports appear...")
            x = LFUtils.wait_until_ports_appear(base_url=f"http://{self.lanforge_ip}:{self.port}", port_list="monitor",
                                                debug=True, timeout=300)
            if x is True:
                print("monitor is up ")
                print("start sniffing")
                monitor = "monitor1"
                self.filter = "wlan type mgt"
                # {self.report_path_date_time}/
                output_file = f'band_steer_test.pcap'
                c = f"tshark -q -i {monitor} -a duration:{self.sniff_duration} -f '{self.filter}' -w {output_file}"

                print("Execute the first command for scapy logic")

                self.tshark_process = subprocess.Popen(c, shell=True)

            else:
                print("some problem with monitor not being up")

        if different_resource:
            # Setup monitor1 (Local) and monitor2 (Remote)
            # Determine Center Frequencies dynamically
            cf1 = get_band_cf(self.sniff_channel_1)
            cf2 = get_band_cf(self.sniff_channel_2)

            # --- Setup monitor1 (Local) ---
            if self.sniff_channel_1 is not None:
                print(f"Configuring monitor1: Channel {self.sniff_channel_1} (CF: {cf1})")
                self.pcap_obj_1 = sniff_radio.SniffRadio(
                    lfclient_host=self.lanforge_ip,
                    lfclient_port=self.port,
                    center_freq=cf1,
                    radio=self.sniff_radio_1,
                    channel=self.sniff_channel_1,
                    monitor_name="monitor1"
                )
                self.pcap_obj_1.setup(0, 0, 0)
                self.pcap_obj_1.monitor.admin_up()

            # --- Setup monitor2 (Remote) ---
            if self.sniff_channel_2 is not None:
                print(f"Configuring monitor2: Channel {self.sniff_channel_2} (CF: {cf2})")
                self.pcap_obj_2 = sniff_radio.SniffRadio(
                    lfclient_host=self.lanforge_ip,
                    lfclient_port=self.port,
                    center_freq=cf2,
                    radio=self.sniff_radio_2,
                    channel=self.sniff_channel_2,
                    monitor_name="monitor2"
                )
                self.pcap_obj_2.setup(0, 0, 0)
                self.pcap_obj_2.monitor.admin_up()

            print("Waiting until ports appear...")
            # Wait logic for x (local) and y (remote)
            x = LFUtils.wait_until_ports_appear(base_url=f"http://{self.lanforge_ip}:{self.port}",
                                                port_list="monitor1", debug=True, timeout=300)
            y = LFUtils.wait_until_ports_appear(base_url=f"http://{self.lanforge_ip}:{self.port}",
                                                port_list=f"{self.sniff_radio_resource_2}.{self.sniff_radio_shelf_2}.monitor2",
                                                debug=True, timeout=300)

            if x and y:
                # --- START LOCAL SNIFFER ---
                self.local_output = os.path.abspath("sniffer_1.pcapng")
                local_cmd = f"tshark -q -i monitor1 -f '{self.filter}' -w {self.local_output}"
                self.local_tshark_process = subprocess.Popen(
                    local_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )

                # --- START REMOTE SNIFFER ---
                sniffer_host = self.get_resource_host()
                self.ssh = paramiko.SSHClient()
                self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.ssh.connect(hostname=list(sniffer_host.values())[0], username="root", password="lanforge")

                self.remote_output = "/tmp/sniffer_2.pcapng"
                self._ssh_run(f"rm -f {self.remote_output} /tmp/tshark2.log")

                # Use 'echo $!' to get the PID of the backgrounded tshark immediately
                remote_cmd = (f"nohup tshark -q -i monitor2 -f {shlex.quote(self.filter)} "
                              f"-w {shlex.quote(self.remote_output)} > /tmp/tshark2.log 2>&1 & echo $!")

                rc, out, err = self._ssh_run(remote_cmd)

                print("RC", rc)
                print("out", out)
                print("ERR", err)
                # Extract only the last line (the PID) in case nohup prints a warning
                self.remote_tshark_pid = out.strip().split('\n')[-1]

                print("PID: ", self.remote_tshark_pid, self.remote_tshark_pid.isdigit())
                if self.remote_tshark_pid.isdigit():
                    print(f"✅ Remote tshark started, PID: {self.remote_tshark_pid}")
                else:
                    print(f"❌ Failed to get PID. Output was: {out}")
                # Move the sleep here: give the remote process time to start writing
                time.sleep(2)
        else:
            self.pcap_obj_1 = sniff_radio.SniffRadio(lfclient_host=self.lanforge_ip, lfclient_port=self.port,
                                                     center_freq="2412",
                                                     radio=self.sniff_radio_1,
                                                     channel_freq="2412",
                                                     # channel=self.sniff_channel_1,
                                                     monitor_name="monitor1")

            self.pcap_obj_1.setup(0, 0, 0)
            self.pcap_obj_1.monitor.admin_up()

            self.pcap_obj_2 = sniff_radio.SniffRadio(lfclient_host=self.lanforge_ip, lfclient_port=self.port,
                                                     center_freq="5180",
                                                     radio=self.sniff_radio_2,
                                                     channel_freq="5180",
#                                                      channel=self.sniff_channel_2,
                                                     monitor_name="monitor2")
            self.pcap_obj_2.setup(0, 0, 0)
            self.pcap_obj_2.monitor.admin_up()

            print("Waiting until ports appear...")
            x = LFUtils.wait_until_ports_appear(base_url=f"http://{self.lanforge_ip}:{self.port}",
                                                port_list=f"{self.sniff_radio_resource_1}.{self.sniff_radio_shelf_1}.monitor1",
                                                debug=True, timeout=300)

            y = LFUtils.wait_until_ports_appear(base_url=f"http://{self.lanforge_ip}:{self.port}",
                                                port_list=f"{self.sniff_radio_resource_2}.{self.sniff_radio_shelf_2}.monitor2",
                                                debug=True, timeout=300)
            if x or y:
                sniffer_host = self.get_resource_host()
                self.ssh = paramiko.SSHClient()
                self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                self.ssh.connect(
                    hostname=list(sniffer_host.values())[0],
                    username="root",
                    password="lanforge",
                    look_for_keys=False,
                    allow_agent=False,
                    timeout=20
                )

                try:
                    self.ssh.get_transport().set_keepalive(30)
                except Exception:
                    pass

                self.filter = "wlan type mgt"
                self.output_file = "/tmp/combined_sniffer.pcapng"

                # Remove old artifacts
                self._ssh_run(
                    f"sudo -n rm -f {shlex.quote(self.output_file)} /tmp/tshark1.log"
                )

                cmd = (
                        "bash -lc " + shlex.quote(
                    f"nohup sudo -n tshark "
                    f"-i monitor1 -i monitor2 "
                    f"-f {shlex.quote(self.filter)} "
                    f"-w {shlex.quote(self.output_file)} "
                    f"> /tmp/tshark1.log 2>&1 & echo $!"
                )
                )

                print("COMMAND:", cmd)
                rc, out, err = self._ssh_run(cmd)
                self.tshark_pid = out.strip()

                if not self.tshark_pid.isdigit():
                    print("? Failed to start tshark. Output:", out)
                    print("stderr:", err)
                    # show log if exists
                    _, log_out, _ = self._ssh_run("tail -n 50 /tmp/tshark1.log || true")
                    print("tshark log:\n", log_out)
                    return

                print(f"Remote tshark started, PID = {self.tshark_pid}")

            # Creation of Dummy stations for mtk 7996 radios
            self.create_clients(radio=self.sniff_radio_1, ssid="Dummy_ssid", passwd="Dummy_passwd", security="wpa2", station_list=['1.3.dummy0'], station_flag=None, sta_type="normal", dummy_client=True)
            self.create_clients(radio=self.sniff_radio_2, ssid="Dummy_ssid", passwd="Dummy_passwd", security="wpa2", station_list=['1.3.dummy1'], station_flag=None, sta_type="normal", dummy_client=True)

    def download_pcap(self, remote_path, local_path, timeout=60):
        print(f"[DEBUG] PATH : {remote_path} --- {local_path}")
        host = list(self.get_resource_host().values())[0]
        transport = None
        sftp = None

        def progress(transferred, total):
            # prints occasionally so you know it's moving
            if total:
                pct = (transferred / total) * 100
                print(f"SFTP: {transferred}/{total} bytes ({pct:.1f}%)")
            else:
                print(f"SFTP: {transferred} bytes")

        try:
            # Create transport with timeout
            sock = None
            transport = paramiko.Transport((host, 22))
            transport.banner_timeout = 30
            transport.auth_timeout = 30
            transport.connect(username="root", password="lanforge")

            # Strongly recommended
            transport.set_keepalive(30)

            sftp = paramiko.SFTPClient.from_transport(transport)
            sftp.get_channel().settimeout(timeout)
            sftp.get(remote_path, local_path, callback=progress)

            print(f"PCAP downloaded: {local_path} ({os.path.getsize(local_path)} bytes)")
        finally:
            if sftp:
                sftp.close()
            if transport:
                transport.close()

    def stop_sniffer(self, different_resource=False):
        final_pcap = None
        local_pcap = None
        if different_resource:
            # 1. Stop Local
            if getattr(self, "local_tshark_process", None):
                print("Stopping Local Sniffer...")
                self.local_tshark_process.terminate()
                self.local_tshark_process.wait()

            # 2. Stop Remote
            if getattr(self, "ssh", None) and getattr(self, "remote_tshark_pid", None):
                print("Stopping Remote Sniffer...")
                # INTEGRATED PCAP.PY LOGIC: Use kill -2 (SIGINT) for clean pcap closure
                self._ssh_run(f"kill -2 {self.remote_tshark_pid}")
                time.sleep(3)  # Allow time for buffer flush

                # INTEGRATED PCAP.PY LOGIC: Verify file exists and has size > 0
                check_cmd = f"test -s {self.remote_output} && echo 'READY' || echo 'MISSING'"
                rc, out, _ = self._ssh_run(check_cmd)

                if "READY" in out:
                    local_sniffer_2 = os.path.abspath("sniffer_2.pcapng")
                    self.download_pcap(remote_path=self.remote_output, local_path=local_sniffer_2)

                    # 3. Merge
                    combined_pcap = os.path.abspath("combined_sniffer.pcapng")
                    local_1 = getattr(self, "local_output", "sniffer_1.pcapng")

                    merge_cmd = f"mergecap -w {combined_pcap} {local_1} {local_sniffer_2}"
                    print(f"Merging files: {merge_cmd}")

                    res = subprocess.run(merge_cmd, shell=True, capture_output=True, text=True)
                    if res.returncode == 0 and os.path.exists(combined_pcap):
                        print(f"Successfully created: {combined_pcap}")
                        local_pcap = combined_pcap
                    else:
                        print(f"❌ Merge failed: {res.stderr}")
                else:
                    print("❌ Remote file was not created or is empty.")

                self.ssh.close()
        else:
            if not getattr(self, "ssh", None) or not getattr(self, "tshark_pid", None):
                print("Sniffer not running")
                return None

            pid = self.tshark_pid

            # Graceful stop
            self._ssh_run(f"kill -INT {pid} || true")

            for _ in range(40):
                _, out, _ = self._ssh_run(
                    f"kill -0 {pid} >/dev/null 2>&1; echo $?"
                )
                if out.strip() != "0":
                    break
                time.sleep(0.5)

            # Flush filesystem
            time.sleep(2)
            self._ssh_run("sync")
            time.sleep(1)

            # Validate PCAP remotely
            _, out, _ = self._ssh_run(
                f"tshark -r {shlex.quote(self.output_file)} -c 1 >/dev/null 2>&1; echo $?"
            )
            if out.strip() != "0":
                print("PCAP validation failed on sniffer host")
                _, log_out, _ = self._ssh_run("tail -n 80 /tmp/tshark1.log || true")
                print("tshark log:\n", log_out)
                return

            print("Remote tshark stopped and PCAP looks valid")
            local_pcap = os.path.abspath(
                os.path.basename(self.output_file)
            )
            print(f"[DEBUG] PATH : {self.output_file} === {local_pcap}")
            self.download_pcap(
                remote_path=self.output_file,
                local_path=local_pcap
            )
            final_pcap = local_pcap
            # Close SSH
            self.ssh.close()

        # returning pcap path
        return local_pcap

    def calculate_steering_status(self, pcap_file, mac_list):
        steering_results = {}

        for mac in mac_list:
            if mac == '':
                continue

            print(f"Checking BTM steering for {mac}")

            tshark_cmd = (
                f'tshark -r {pcap_file} '
                f'-Y "wlan.fc.type == 0 && wlan.fc.type_subtype == 13 && wlan.action.category == 5" '
                f'-T fields '
                f'-e frame.time_epoch -e wlan.sa -e wlan.da -e wlan.action.wnm.btm '
                f'-E header=y -E separator=, -E quote=d '
                f'> btm_output.csv'
            )

            subprocess.run(tshark_cmd, shell=True, check=False)

            saw_btm_query = False
            saw_btm_response = False

            with open("btm_output.csv", "r") as csvfile:
                reader = csv.DictReader(csvfile)

                for row in reader:
                    source = row.get("wlan.sa", "")
                    dest = row.get("wlan.da", "")

                    # BTM Query / Request from AP ? sent TO STA
                    if dest.lower() == mac.lower():
                        saw_btm_query = True

                    # BTM Response from STA ? sent TO AP
                    if source.lower() == mac.lower():
                        saw_btm_response = True

            # Result classification
            if saw_btm_query and saw_btm_response:
                steering_results[mac] = "Steered"
            elif saw_btm_query and not saw_btm_response:
                steering_results[mac] = "Not Respond"
            else:
                steering_results[mac] = "Not Steered"

            self.final_data[mac] = steering_results[mac]

        # Save results into CSV
        out_csv = "band_steering_results.csv"
        with open(out_csv, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["MAC Address", "Steering Status"])
            for mac, status in steering_results.items():
                writer.writerow([mac, status])

        print(f"\nBand steering results saved to {out_csv}\n")
        print(''.join(f'{k}-{v}\n' for k, v in self.final_data.items()))
        return steering_results

    def build_line_plot(self, report_obj):

        logging.info(f"Current working directory: {os.getcwd()}")
        logging.info(f"Report directory: {report_obj.path_date_time}")

        timestamp_set = set()
        cx_names = list(self.traffic_data.keys())

        bps_rx_a_dict = {cx: {} for cx in cx_names}
        bps_rx_b_dict = {cx: {} for cx in cx_names}

        for cx, entries in self.traffic_data.items():
            for row in entries:
                if not isinstance(row, dict) or 'Time_Stamp' not in row:
                    continue  # skip malformed rows
                timestamp = row['Time_Stamp']
                timestamp_set.add(timestamp)
                bps_rx_a_dict[cx][timestamp] = round(row['Bps_Rx_A'] / 1_000_000, 3)  # Mbps
                bps_rx_b_dict[cx][timestamp] = round(row['Bps_Rx_B'] / 1_000_000, 3)  # Mbps

        timestamps = sorted(timestamp_set)
        fig = go.Figure()

        # 2. Add lines for each CX
        all_traces = []
        for cx in cx_names:
            y_a = [bps_rx_a_dict[cx].get(ts, 0) for ts in timestamps]
            y_b = [bps_rx_b_dict[cx].get(ts, 0) for ts in timestamps]

            trace_a = go.Scatter(x=timestamps, y=y_a, mode='lines', name=f'{cx} - Rx A')
            trace_b = go.Scatter(x=timestamps, y=y_b, mode='lines', name=f'{cx} - Rx B')
            fig.add_trace(trace_a)
            fig.add_trace(trace_b)
            all_traces.extend([trace_a, trace_b])

        # 3. Dropdown to toggle stations
        dropdown_buttons = [
            {
                "label": "All",
                "method": "update",
                "args": [{"visible": [True] * len(all_traces)}, {"showlegend": True}]
            },
            {
                "label": "None",
                "method": "update",
                "args": [{"visible": [False] * len(all_traces)}, {"showlegend": True}]
            }
        ]

        for i, cx in enumerate(cx_names):
            visibility = [False] * len(all_traces)
            visibility[i * 2] = True  # Rx A
            visibility[i * 2 + 1] = True  # Rx B
            dropdown_buttons.append({
                "label": cx,
                "method": "update",
                "args": [{"visible": visibility}, {"showlegend": True}]
            })

        fig.update_layout(
            title="Traffic per Station (in Mbps)",
            xaxis_title="Time",
            yaxis_title="Traffic (in Mbps)",
            xaxis=dict(
                tickangle=45,
                showline=True,
                linecolor='black',
                linewidth=2
            ),
            yaxis=dict(
                showline=True,
                linecolor='black',
                linewidth=2
            ),
            updatemenus=[{
                "buttons": dropdown_buttons,
                "direction": "down",
                "x": 1.05,
                "xanchor": "left",
                "y": 1.2,
                "yanchor": "top"
            }],
            height=600,
            plot_bgcolor="white",
            paper_bgcolor="white"
        )

        os.makedirs(report_obj.path_date_time, exist_ok=True)

        # Define paths using absolute paths
        html_path = os.path.abspath(f"{report_obj.path_date_time}/interactive_traffic_graph.html")
        png_path = os.path.abspath(f"{report_obj.path_date_time}/interactive_traffic_graph.png")

        try:
            # Save files directly to report directory
            fig.write_html(html_path, include_plotlyjs="inline")
            fig.write_image(png_path, format="png", width=1200, height=600, scale=2)

            # Verify files were created
            if not os.path.exists(png_path):
                logging.error(f"Graph image not created at {png_path}")
                return False

            # Tell report object about the file (using relative path)
            report_obj.set_graph_image("interactive_traffic_graph.png")
            return True

        except Exception as e:
            logging.error(f"Error saving interactive graph: {str(e)}")
            return False


def validate_args(args):
    """Validate CLI arguments."""
    if args.parent_port is None:
        logger.critical("--parent or --parent_port or --macvlan_parent argument required")
        exit(0)

    if args.qvlan_ids is None:
        logger.critical("--qvlan_ids argument required")
        exit(0)

    if args.ipv4_addresses:
        num_addresses = len(args.ipv4_addresses)

        # If multiple static IPv4 addresses specified, then must match number
        # of QVLAN IDs specified
        if args.qvlan_ids and num_addresses != len(args.qvlan_ids):
            logger.error("Number of static IPv4 addresses does not match \'--qvlan_ids\'")
            exit(1)

        # IPv4 subnet mask required if static IPv4 configuration specified
        # If more than one subnet mask specified, must match number of IPv4 addresses
        # If only one, then apply that to all created ports
        if not args.ipv4_netmasks:
            logger.error("No IPv4 subnet mask specified")
            exit(1)
        elif len(args.ipv4_netmasks) != 1 and num_addresses != len(args.ipv4_netmasks):
            logger.error("Number of IPv4 subnet masks does not match number of IPv4 addresses.")
            exit(1)

        # IPv4 gateway required if static IPv4 configuration specified
        # If more than one gateway specified, must match number of IPv4 addresses
        # If only one, then apply that to all created ports
        if not args.ipv4_gateways:
            # TODO: Should we make this a warn and continue? Will need to fix
            # QVLANProfile code if so
            logger.error("No IPv4 gateway specified")
            exit(1)
        elif len(args.ipv4_gateways) != 1 and num_addresses != len(args.ipv4_gateways):
            logger.error("Number of IPv4 gateways does not match number of IPv4 addresses.")
            exit(1)


def main():
    help_summary = '''

    EXAMPLE 1:
    python3 lf_bandsteer.py --attenuators 1.1.84 1.1.1030 --step 20 --max_attenuation 60 --iteration 1 --wait_time 12 --sniff_radio 1.1.wiphy2 --channel 36 --frequency 5180 --radios 'ssid==ROAM,passwd==lanforge,security==wpa2,sta_type==11r,option==ota,radio==1.1.wiphy2,num_sta==3' --upstream 1.1.eth2 --sniff_duration 3000  --mgr localhost  --bg_scan "simple:30:-65:300:4" --roam_timeout 3s --cleanup --run_traffic bidirectional
    python3 lf_bandsteer.py --set_max_attenuators "{'1.1.3002':{(1,2)}}" --attenuators "{'1.1.3002':{(3,4)}}" --step 5 --max_attenuation 75 --iteration 1 --wait_time 5 --sniff_radio_1 1.2.wiphy0 --sniff_radio_2 1.2.wiphy1 --sniff_channel_1 6 --sniff_channel_2 36 --radios 'ssid==jitu123,passwd==123456789,security==wpa2,radio==1.1.wiphy0,num_sta==1' --upstream 1.1.eth2 --sniff_duration 20m  --mgr 192.168.245.117  --run_traffic upload --disable_restart_dhcp --steer_type steer_twog --initial_band_pref 5GHz

'''

    parser = argparse.ArgumentParser(
        prog='band_steer_test.py',
    )

    required = parser.add_argument_group('Required Arguments')

    required.add_argument('--ssid',
                          help='SSID of the APs',
                          required=False)
    required.add_argument('--security',
                          help='Encryption type for the SSID',
                          required=False)
    required.add_argument('--password',
                          help='Key/Password for the SSID',
                          required=False)
    required.add_argument('--sta_radio',
                          help='Station Radio',
                          default='1.1.wiphy0',
                          required=False)
    required.add_argument('--band',
                          help='eg. --band "2G", "5G" or "6G"',
                          default="5G")
    required.add_argument('--num_sta',
                          help='Number of Stations',
                          type=int,
                          default=1,
                          required=False)
    required.add_argument('--option',
                          help='eg. --option "ota',
                          type=str,
                          default="ota",
                          required=False)
    required.add_argument('--identity',
                          help='Radius server identity',
                          type=str,
                          default="testuser",
                          required=False)
    required.add_argument('--ttls_pass',
                          help='Radius Server passwd',
                          type=str,
                          default="testpasswd",
                          required=False)
    required.add_argument('--sta_type',
                          type=str,
                          help="provide the type of"
                               " client you want to create i.e 11r,11r-sae,"
                               " 11r-sae-802.1x or simple as none")

    optional = parser.add_argument_group('Optional Arguments')

    optional.add_argument('--mgr',
                          help='LANforge IP',
                          default='localhost')
    optional.add_argument('--port',
                          help='LANforge port',
                          type=int,
                          default=8080)
    optional.add_argument('--upstream',
                          help='Upstream Port',
                          default='1.1.eth1')
    optional.add_argument('--step',
                          help='Attenuation increment/decrement step size eg: 10',
                          type=int,
                          default=10)
    optional.add_argument('--max_attenuation',
                          help='Maximum attenuation value (dBm) for the attenuators eg: 95',
                          type=int,
                          default=95)
    optional.add_argument('--set_max_attenuators',
                          nargs='+',
                          help='Attenuator serials',
                          required=False)
    optional.add_argument('--attenuators',
                          nargs='+',
                          help='''Attenuator serials e.g "{'1.1.3008':{(1,2),(3,4)}}" or "{'1.1.3319':{(1,2)}}" "{'1.1.3000':{(1,2)}}" ''',
                          default=[],
                          required=False)
    optional.add_argument('-r', '--radios',
                          action='append',
                          nargs=1,
                          help=(' --radios'
                                ' radio==<wiphy_radios> num_sta==<number of stations>'
                                ' ssid==<ssid> passwd==<ssid password> security==<security> '
                                )
                          )
    optional.add_argument('--iterations',
                          help='Number of iterations to perform steer test',
                          type=int,
                          default=1)
    optional.add_argument('--wait_time',
                          help='Waiting time (seconds) between iterations',
                          type=int,
                          default=15)
    optional.add_argument('--roam_timeout',
                          help='Threshold time in milli seconds(ms)/in seconds(s)/in minutes (min) to determine if the roam attempt succeeds or fails',
                          type=str,
                          default="50ms")
    optional.add_argument('--station_list',
                          help='List of stations to perform roam test (comma seperated)')
    optional.add_argument('--station_flag',
                          help='station flags to add. eg: --station_flag use-bss-transition',
                          required=False,
                          default=None)
    optional.add_argument('--bg_scan',
                          help='Background scan filter',
                          required=False,
                          default='simple:10:-65:300:4')
    optional.add_argument('--sniff_frequency_1',
                          help='Frequency',
                          type=int,
                          default=None)
    optional.add_argument('--sniff_frequency_2',
                          help='Frequency',
                          type=int,
                          default=None)
    optional.add_argument('--sniff_radio_1',
                          help='Sniffer Radio',
                          default='1.1.wiphy0')
    optional.add_argument('--sniff_radio_2',
                          help='Sniffer Radio',
                          default='1.1.wiphy1')
    optional.add_argument('--sniff_channel_1',
                          help='Channel',
                          type=str,
                          default='6')
    optional.add_argument('--sniff_channel_2',
                          help='Channel',
                          type=str,
                          default='36')
    optional.add_argument('--sniff_duration',
                          help='Sniff duration',
                          type=str,
                          default=300)
    optional.add_argument('--traffic_type',
                          help='Specify Traffci Type',
                          choices=["lf_tcp", "lf_udp"],
                          default="lf_tcp")
    optional.add_argument('--steer_type',
                          help='Type of steering to perform for bandsteering',
                          choices=['steer_fiveg', 'steer_twog'],
                          )
    optional.add_argument('--initial_band_pref',
                          help='Initial Band Preference for the stations before bandsteering',
                          choices=['5GHz'])
    optional.add_argument('--cleanup',
                          help='Cleanup the stations after the roam test',
                          action='store_true')
    optional.add_argument('--run_traffic',
                          help='Run traffic: upload, download, or bidirectional. Omit to skip traffic.',
                          choices=['upload', 'download', 'bidirectional'],
                          default=None)
    optional.add_argument('--disable_restart_dhcp',
                          help='This disables Restart Dhcp on connect flag in Station Misc config',
                          action='store_true')
    optional.add_argument("--custom_wifi_cmd",
                          help="Mention the custom wifi command.")
    optional.add_argument('--test_type',
                          choices=['standard',
                                   'pre_assoc',
                                   'post_assoc',
                                   'no_pre_no_post',
                                   'stickiness',
                                   'success_rate',
                                   'performance',
                                   'qvlan',
                                   'client_isolation_qvlan'],
                          default='standard',
                          help='Type of Bandsteering test scenario to perform')
    optional.add_argument('--attenuate_speicific',
                          help='Attenuate specific client {"1.1.3319":{(1,2)}}',
                          default=None)

    # QVLAN related arguments
    optional.add_argument('--scenario',
                          type=str,
                          help='Provide the Scenario name of the Chamber view for building.')
    optional.add_argument('--qvln',
                          action='store_true',
                          help='Create QVLAN ports')
    optional.add_argument('--parent', '--parent_port', '--qvlan_parent',
                          dest='parent_port',
                          help='Parent port used by created QVLAN port(s)',
                          default=None)
    optional.add_argument('--qvlan_ids',
                          dest='qvlan_ids',
                          nargs='+',
                          help='QVLAN ID(s) used in creation. '
                               'One QVLAN port is created per ID. For static IP configuration, '
                               'the number of IDs specified in this argument must match the number '
                               'of static IP addresses specified in the \'--ipv4_addresses\'.',
                          default=None)

    ipv4_cfg = parser.add_mutually_exclusive_group(required=False)
    ipv4_cfg.add_argument('--dhcp', '--dhcpv4', '--use_dhcp',
                          dest='dhcpv4',
                          help='Enable DHCPv4 on created QVLAN ports',
                          action='store_true')
    ipv4_cfg.add_argument('--ip', '--ips', '--ipv4_address', '--ipv4_addresses',
                          dest='ipv4_addresses',
                          type=str,
                          nargs='+',
                          help='List of static IPv4 addresses. The number of IPv4 addresses '
                               'specified must match the number of QVLAN ports specified in '
                               '\'--num_ports\'',
                          default=None)

    # Only checked when static configuration specified
    optional.add_argument('--netmask', '--netmasks', '--ipv4_netmask', '--ipv4_netmasks',
                          dest='ipv4_netmasks',
                          type=str,
                          nargs='+',
                          help='IPv4 subnet mask to apply to all created QVLAN ports '
                               'when static IPv4 configuration requested',
                          default=None)
    optional.add_argument('--gateway', '--gateways', '--ipv4_gateway', '--ipv4_gateways',
                          dest='ipv4_gateways',
                          type=str,
                          nargs='+',
                          help='IPv4 gateway to apply to all created QVLAN ports '
                               'when static IPv4 configuration requested',
                          default=None)

    parser.add_argument('--help_summary',
                        help='Show summary of what this script does',
                        default=None,
                        action="store_true")
    parser.add_argument('--log_level', default=None,
                        help='Set logging level: debug | info | warning | error | critical')
    parser.add_argument("--lf_logger_config_json",
                        help="--lf_logger_config_json <json file> , json configuration of logger")

    args = parser.parse_args()
    if (args.help_summary):
        print(help_summary)
        exit(0)

    logger_config = lf_logger_config.lf_logger_config()

    if args.log_level:
        logger_config.set_level(level=args.log_level)

    if args.lf_logger_config_json:
        # logger_config.lf_logger_config_json = "lf_logger_config.json"
        logger_config.lf_logger_config_json = args.lf_logger_config_json
        logger_config.load_lf_logger_config()

    if args.run_traffic is None:
        logging.info("Traffic will not be run (no --run_traffic specified).")
    else:
        logging.info(f"Running traffic: {args.run_traffic}")

    if 'm' in args.sniff_duration:
        args.sniff_duration = int(args.sniff_duration.replace('m', '')) * 60
    elif 'h' in args.sniff_duration:
        args.sniff_duration = int(args.sniff_duration.replace('h', '')) * 360
    else:
        args.sniff_duration = int(300)

    if args.disable_restart_dhcp:
        disable_restart_dhcp = True
    else:
        disable_restart_dhcp = False

    if args.radios:
        radios = args.radios
    else:
        radios = None

    if (args.station_list is None):
        band_steer_test = BandSteer(
            lanforge_ip=args.mgr,
            port=args.port,
            station_radio=args.sta_radio,
            sniff_radio_1=args.sniff_radio_1,
            sniff_channel_1=args.sniff_channel_1,
            sniff_frequency_1=args.sniff_frequency_1,
            sniff_radio_2=args.sniff_radio_2,
            sniff_channel_2=args.sniff_channel_2,
            sniff_frequency_2=args.sniff_frequency_2,
            attenuators=args.attenuators[0],
            set_max_attenuators=args.set_max_attenuators,
            step=args.step,
            test_type=args.test_type,
            max_attenuation=args.max_attenuation,
            sniff_duration=args.sniff_duration,
            upstream=args.upstream,
            option=args.option,
            identity=args.identity,
            ttls_pass=args.ttls_pass,
            wait_time=args.wait_time,
            iterations=args.iterations,
            roam_timeout=args.roam_timeout,
            bg_scan=args.bg_scan,
            traffic=args.run_traffic,
            steer_type=args.steer_type,
            initial_band_pref=args.initial_band_pref,
            disable_restart_dhcp=disable_restart_dhcp,
            custom_wifi_cmd=args.custom_wifi_cmd
        )

        if args.steer_type == 'steer_twog':
            logger.info("Steering type selected: Steer to 2.4GHz")
            for idx in range(1, 7):
                band_steer_test.set_atten_idx(args.attenuators[0], 0, idx - 1)

        else:
            logger.info("Steering type selected: Steer to 5GHz")
            for idx in range(1, 7):
                band_steer_test.set_atten_idx(args.attenuators[0], band_steer_test.max_attenuation, idx - 1)

        station_list = []
        radio_list, num_sta_list, ssid_list, password_list, security_list = [], [], [], [], []
        station_flag_list = []
        sta_type_list = []
        option_list = []
        initial_band_pref_list = []

        for radio_ in radios:
            radio_keys = ['radio', 'security', 'ssid', 'passwd', 'num_sta', 'sta_flag', 'sta_type', 'option']
            logger.info("radio_dict before format {}".format(radio_))
            radio_info_dict = dict(
                map(
                    lambda x: x.split('=='),
                    str(radio_).replace(
                        '"',
                        '').replace(
                        '[',
                        '').replace(
                        ']',
                        '').replace(
                        "'",
                        "").replace(
                        ",",
                        " ").split()))
            logger.info("radio_dict after format {}".format(radio_info_dict))
            for key in radio_keys:
                if key not in radio_info_dict:
                    if hasattr(args, f'{key}'):
                        radio_info_dict[f'{key}'] = getattr(args, f'{key}')
                    else:
                        continue
                        # logger.critical(
                        #     "missing argument, for the {}, all of the following need to be present {} ".format(
                        #         key, radio_info_dict))
                        # exit(1)
            radio_list.append(radio_info_dict['radio'])
            num_sta_list.append(int(radio_info_dict['num_sta']))
            ssid_list.append(radio_info_dict.get('ssid', None))
            password_list.append(radio_info_dict.get('passwd', None))
            security_list.append(radio_info_dict.get('security', None))

            if 'sta_flag' in radio_info_dict:
                station_flag_list.append(",".join(flag.strip() for flag in radio_info_dict['sta_flag'].split('&')))
            else:
                station_flag_list.append(None)

            if "sta_type" in radio_info_dict:
                sta_type_list.append(radio_info_dict['sta_type'])
            else:
                sta_type_list.append(None)

            if "option" in radio_info_dict:
                option_list.append(radio_info_dict['option'])
            else:
                option_list.append(None)

            if "initial_band_pref" in radio_info_dict:
                initial_band_pref_list = radio_info_dict['initial_band_pref']
            else:
                initial_band_pref_list.append("5GHz")

            logger.debug("radio_dict {}".format(radio_info_dict))

        # staring sniffer
        band_steer_test.start_sniffer(ssid_list[0], password_list[0], security_list[0])

        start_time = datetime.now()
        # data = [["Start Time", start_time.strftime("%Y-%m-%d %H:%M:%S")],
        #         ["Estimated Roam Time", f' ~ {BandSteer.estimate_roam_time(args.iterations, sum(num_sta_list))}'],]
        # print(tabulate(data, headers=[], tablefmt="grid"))
        start_id = 0
        # if args.start_id != 0:
        #     start_id = int(args.start_id)

        # band_steer_test.set_unused_atten(band_steer_test.max_attenuation)
        # band_steer_test.pre_cleanup()
        if args.test_type == 'standard':
            band_steer_test.set_unused_atten(attenuator=args.attenuators[0], modules=[1, 2])

        for (radio,
             num_sta,
             ssid,
             passwd,
             security,
             station_flag,
             sta_type,
             band_pref,
             option) in zip(radio_list,
                            num_sta_list,
                            ssid_list,
                            password_list,
                            security_list,
                            station_flag_list,
                            sta_type_list,
                            initial_band_pref_list,
                            option_list):
            end_id = start_id + num_sta - 1
            sta_list = LFUtils.port_name_series(prefix="sta",
                                                start_id=start_id,
                                                end_id=end_id,
                                                padding_number=10000,
                                                radio=radio)

            print("station_list {}".format(sta_list))
            station_list.extend(sta_list)

            band_steer_test.pre_cleanup(sta_list)

            band_steer_test.create_clients(radio,
                                           ssid,
                                           passwd,
                                           security,
                                           sta_list,
                                           station_flag,
                                           sta_type,
                                           band_pref,
                                           option)
            start_id = end_id + 1

        band_steer_test.station_list = station_list
        logging.info('Selected stations\t{}'.format(station_list))

    else:
        stations = args.station_list.split(',')
        band_steer_test = BandSteer(
            lanforge_ip=args.mgr,
            port=args.port,
            sniff_radio_1=args.sniff_radio_1,
            sniff_channel_1=args.sniff_channel_1,
            sniff_frequency_1=args.sniff_frequency_1,
            sniff_radio_2=args.sniff_radio_2,
            sniff_channel_2=args.sniff_channel_2,
            sniff_frequency_2=args.sniff_frequency_2,
            attenuators=args.attenuators[0],
            set_max_attenuators=args.set_max_attenuators,
            step=args.step,
            max_attenuation=args.max_attenuation,
            sniff_duration=args.sniff_duration,
            upstream=args.upstream,
            wait_time=args.wait_time,
            iterations=args.iterations,
            roam_timeout=args.roam_timeout,
            bg_scan=args.bg_scan,
            traffic=args.run_traffic
        )
        band_steer_test.station_list = stations
        logging.info('Selected stations\t{}'.format(stations))

    if args.test_type == 'standard':
        # python3 lf_bandsteer.py  --attenuators "{'1.1.3002':{(1,2)}}"  --step 2  --max_attenuation 52 --it
        # eration 1 --wait_time 5 --sniff_radio_1 1.1.wiphy0 --sniff_radio_2 1.1.wiphy1 --sniff_
        # channel_1 36 --sniff_channel_2 6 --radios 'ssid==Test123,passwd==Password@123,security
        # ==wpa2,radio==1.2.wiphy1,num_sta==1,sta_flag==use-bss-transition' --upstream 1.1.eth2
        # --sniff_duration 20m  --mgr 192.168.245.117 --run_traffic upload --disable_restart_dhcp --steer_type  steer_fiveg --test_type standard --run_traffic download

        band_steer_test.test_type = 'standard'
        if args.run_traffic:
            band_steer_test.create_cx(traffic_type=args.traffic_type)
            band_steer_test.start_cx()

        logging.info('Initiating band steering')
        print(f"\nStarting band steering test...")

        before_bssid = band_steer_test.get_bssids(as_dict=True)
        before_chan = band_steer_test.get_channel(as_dict=True)

        start_time, end_time = band_steer_test.start_band_steer_test_standard(attenuator=args.attenuators[0],
                                                                              modules=[3, 4])
        # temporarly waiting for 2mins
        time.sleep(140)

        after_bssid = band_steer_test.get_bssids(as_dict=True)
        after_chan = band_steer_test.get_channel(as_dict=True)

        logging.info(f'Start Time :{start_time}')
        logging.info(f'End Time :{end_time}')
        logging.info('Stopping sniffer')
        band_steer_test.stop_sniffer()

        stations = set(before_bssid) | set(before_chan) | set(after_bssid) | set(after_chan)

        test_results = {}
        for sta in sorted(stations):
            test_results[sta] = {
                "before_bssid": before_bssid.get(sta),
                "before_channel": before_chan.get(sta),
                "after_bssid": after_bssid.get(sta),
                "after_channel": after_chan.get(sta),
            }

        print(f"\n{'=' * 60}")
        print("Evaluating test results...")
        print(test_results, "Station wise bssid logs")

        if args.run_traffic:
            band_steer_test.stop_cx()
            band_steer_test.clean_cxs()

        return test_results

    elif args.test_type == 'pre_assoc':
        band_steer_test.test_type = 'pre_assoc'
        logging.info('Initiating pre-association band steer test')
        # args.attenuate_speicific
        start_time = band_steer_test.start_band_steer_test_pre_assoc()

    elif args.test_type == 'post_assoc':
        band_steer_test.test_type = 'post_assoc'
        logging.info('Initiating post-association band steer test')
        start_time, end_time = band_steer_test.start_band_steer_test_post_assoc()

    elif args.test_type == 'no_pre_no_post':
        band_steer_test.test_type = 'no_pre_no_post'
        logging.info('Initiating no pre and no post band steer test')
        start_time, end_time = band_steer_test.start_band_steer_test_no_pre_no_post()

    elif args.test_type == 'stickiness':
        band_steer_test.test_type = 'stickiness'
        logging.info('Initiating stickiness band steer test')
        start_time, end_time = band_steer_test.start_band_steer_test_stickiness()

    elif args.test_type == 'success_rate':
        band_steer_test.test_type = 'success_rate'
        logging.info('Initiating success rate band steer test')
        start_time, end_time = band_steer_test.start_band_steer_test_success_rate()

    elif args.test_type == 'performance':
        band_steer_test.test_type = 'performance'
        logging.info('Initiating performance band steer test')
        start_time, end_time = band_steer_test.start_band_steer_test_performance()

    elif args.test_type == 'qvlan':
        band_steer_test.test_type = 'qvlan'
        # validate qvlan creation args
        if args.qvln:
            validate_args(args)
            create_qvlan = CreateQVlan(**vars(args))
            create_qvlan.build()

        cv_test_obj = cv_test_manager.cv_test(lfclient_host=args.mgr)
        cv_test_obj.apply_cv_scenario(args.scenario)
        cv_test_obj.build_cv_scenario()
        cv_test_obj.create_test(test_name='Scenario Test', instance=args.scenario, load_old_cfg=False)

        logger.info("Stations Initiated and waits until adminup and gets IP")

        start_time, end_time = band_steer_test.start_band_steer_test_standard()

    elif args.test_type == 'client_isolation_qvlan':
        band_steer_test.test_type = 'client_isolation_qvlan'
        # validate qvlan creation args
        if args.qvln:
            validate_args(args)
            create_qvlan = CreateQVlan(**vars(args))
            create_qvlan.build()

        cv_test_obj = cv_test_manager.cv_test(lfclient_host=args.mgr)
        cv_test_obj.apply_cv_scenario(args.scenario)
        cv_test_obj.build_cv_scenario()
        cv_test_obj.create_test(test_name='Scenario Test', instance=args.scenario, load_old_cfg=False)

        logger.info("Stations Initiated and waits until adminup and gets IP")

        start_time, end_time = band_steer_test.start_band_steer_test_client_isolation_qvlan()

    if args.cleanup:
        logging.info('Cleaning up the stations after the roam test')
        band_steer_test.cleanup_stations()


if __name__ == '__main__':
    main()
