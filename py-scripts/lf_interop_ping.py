#!/usr/bin/env python3

'''
    NAME: lf_interop_ping.py

    PURPOSE: lf_interop_ping.py will let the user select real devices, virtual devices or both and then allows them to run
    ping test for user given duration and packet interval on the given target IP or domain name.

    EXAMPLE-1:
    Command Line Interface to run ping test with only virtual clients
    python3 lf_interop_ping.py --mgr 192.168.200.103  --target 192.168.1.3 --virtual --num_sta 1 --radio 1.1.wiphy2 --ssid RDT_wpa2 --security wpa2
    --passwd OpenWifi --ping_interval 1 --ping_duration 1 --server_ip 192.168.1.61 --debug

    EXAMPLE-2:
    Command Line Interface to run ping test with only real clients
    python3 lf_interop_ping.py --mgr 192.168.200.103 --real --target 192.168.1.3 --ping_interval 1 --ping_duration 1 --server_ip 192.168.1.61 --ssid RDT_wpa2 --security wpa2_personal
    --passwd OpenWifi

    EXAMPLE-3:
    Command Line Interface to run ping test with both real and virtual clients
    python3 lf_interop_ping.py --mgr 192.168.200.103 --target 192.168.1.3 --real --virtual --num_sta 1 --radio 1.1.wiphy2 --ssid RDT_wpa2 --security wpa2
    --passwd OpenWifi --ping_interval 1 --ping_duration 1 --server_ip 192.168.1.61

    EXAMPLE-4:
    Command Line Interface to run ping test with existing Wi-Fi configuration on the real devices
    python3 lf_interop_ping.py --mgr 192.168.200.63 --real --target 192.168.1.61 --ping_interval 5 --ping_duration 1 --passwd OpenWifi --use_default_config

    EXAMPLE-5:
    Command Line Interface to run ping test by setting device specific Pass/Fail values in the csv file
    python3 lf_interop_ping.py --mgr 192.168.244.97 --real --target 192.168.1.3 --ping_interval 1 --ping_duration 1 --device_csv_name device.csv
     --use_default_config

    EXAMPLE-6:
    Command Line Interface to run ping test by setting the same expected Pass/Fail value for all devices
    python3 lf_interop_ping.py --mgr 192.168.244.97 --real --target 192.168.1.3 --ping_interval 1 --ping_duration 1 --expected_passfail_value 3
     --use_default_config

    EXAMPLE-7:
    Command Line Interface to run ping test by configuring Real Devices with SSID, Password, and Security
    python3 lf_interop_ping.py --mgr 192.168.244.97 --real --target 192.168.1.3 --ping_interval 1 --ping_duration 1  --ssid RDT_wpa2 --security wpa2
    --passwd OpenWifi --server_ip 192.168.244.97 --wait_time 30

    EXAMPLE-8:
    Command Line Interface to run ping test by Configuring Devices in Groups with Specific Profiles
    python3 lf_interop_ping.py --mgr 192.168.244.97 --real --target 192.168.1.3 --ping_interval 1 --ping_duration 1   --group_name grp3 --file_name g219 --profile_name Open5
     --server_ip 192.168.204.60

    EXAMPLE-9:
    Command Line Interface to run ping test by Configuring Devices in Groups with Specific Profiles with expected Pass/Fail values
    python3 lf_interop_ping.py --mgr 192.168.244.97 --real --target 192.168.1.3 --ping_interval 1 --ping_duration 1   --group_name grp3 --file_name g219 --profile_name Open5
     --expected_passfail_value 3 --server_ip 192.168.204.60

    EXAMPLE-10:
    Command Line Interface for Configuring Devices in Groups with Specific Profiles with device_csv_name
    python3 lf_interop_ping.py --mgr 192.168.244.97 --real --target 192.168.1.3 --ping_interval 1 --ping_duration 1   --group_name grp3 --file_name g219 --profile_name Open5
     --device_csv_name device.csv --server_ip 192.168.204.60

    SCRIPT_CLASSIFICATION : Test

    SCRIPT_CATEGORIES: Performance, Functional, Report Generation

    NOTES:
    1.Use './lf_interop_ping.py --help' to see command line usage and options
    2.Please pass ping_duration in minutes
    3.Please pass ping_interval in seconds
    4.After passing the cli, if --real flag is selected, then a list of available real devices will be displayed on the terminal.
    5.Enter the real device resource numbers seperated by commas (,)

    STATUS: BETA RELEASE

    VERIFIED_ON:
    Working date    - 20/09/2023
    Build version   - 5.4.7
    kernel version  - 6.2.16+

    License: Free to distribute and modify. LANforge systems must be licensed.
    Copyright (C) 2020-2026 Candela Technologies Inc.
'''

import argparse
import time
import sys
import os
import datetime
import json
import pandas as pd
import importlib
import logging
import asyncio
import csv
import statistics
import matplotlib.pyplot as plt

if 'py-json' not in sys.path:
    sys.path.append(os.path.join(os.path.abspath('..'), 'py-json'))

if 'py-scripts' not in sys.path:
    sys.path.append('/home/lanforge/lanforge-scripts/py-scripts')

from lf_base_interop_profile import RealDevice
from lf_modern_report import lf_report
from station_profile import StationProfile
from typing import List
from LANforge import LFUtils
# Importing DeviceConfig to apply device configurations for ADB devices and laptops
DeviceConfig = importlib.import_module("py-scripts.DeviceConfig")

logger = logging.getLogger(__name__)
lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")

try:
    from lf_wifi_msgs import RealClientAnalysis
except ImportError:
    try:
        lf_wifi_msgs = importlib.import_module("py-scripts.lf_wifi_msgs")
        RealClientAnalysis = lf_wifi_msgs.RealClientAnalysis
    except Exception:
        RealClientAnalysis = None

if sys.version_info[0] != 3:
    print("This script requires Python 3")
    exit(1)

realm = importlib.import_module("py-json.realm")
Realm = realm.Realm


class Ping(Realm):
    def __init__(self,
                 host=None,
                 port=None,
                 ssid=None,
                 security=None,
                 password=None,
                 radio=None,
                 target=None,
                 interval=None,
                 lanforge_password='lanforge',
                 sta_list=None,
                 virtual=None,
                 duration=1,
                 real=None,
                 debug=False, file_name=None,
                 profile_name=None,
                 group_name=None,
                 eap_method=None,
                 eap_identity=None,
                 ieee80211=None,
                 ieee80211u=None,
                 ieee80211w=None,
                 enable_pkc=None,
                 bss_transition=None,
                 power_save=None,
                 disable_ofdma=None,
                 roam_ft_ds=None,
                 key_management=None,
                 pairwise=None,
                 private_key=None,
                 ca_cert=None,
                 client_cert=None,
                 pk_passwd=None,
                 pac_file=None,
                 server_ip=None,
                 expected_passfail_val=None,
                 csv_name=None,
                 wait_time=60,
                 total_floors: int = None,
                 get_live_view: bool = None,
                 result_dir: str = None,
                 dowebgui: bool = False,
                 test_name: str = None):
        super().__init__(lfclient_host=host,
                         lfclient_port=port)
        self.ssid_list = []
        self.host = host
        self.lanforge_password = lanforge_password
        self.port = port
        self.lfclient_host = host
        self.lfclient_port = port
        self.ssid = ssid
        self.security = security
        self.password = password
        self.radio = radio
        self.target = target
        self.interval = interval
        self.debug = debug
        self.sta_list = sta_list
        self.real_sta_list = []
        self.real_sta_data_dict = {}
        self.enable_virtual = virtual
        self.enable_real = real
        self.duration = duration
        self.android = 0
        self.virtual = 0
        self.linux = 0
        self.windows = 0
        self.mac = 0
        self.result_json = {}
        self.generic_endps_profile = self.new_generic_endp_profile()
        self.generic_endps_profile.type = 'lfping'
        self.generic_endps_profile.dest = self.target
        self.generic_endps_profile.interval = self.interval
        self.Devices = None
        self.total_floors = total_floors
        self.get_live_view = get_live_view
        self.result_dir = result_dir
        self.dowebgui = dowebgui
        self.test_name = test_name
        self.missing_endp_logged = set()
        self.not_running_endp_logged = set()
        self.client_issue_csv_name = "client_issue.csv"
        self.client_issue_data = []
        self.latest_results = {}
        self.eap_method = eap_method
        self.eap_identity = eap_identity
        self.ieee80211 = ieee80211
        self.ieee80211u = ieee80211u
        self.ieee80211w = ieee80211w
        self.enable_pkc = enable_pkc
        self.bss_transition = bss_transition
        self.power_save = power_save
        self.disable_ofdma = disable_ofdma
        self.roam_ft_ds = roam_ft_ds
        self.key_management = key_management
        self.pairwise = pairwise
        self.private_key = private_key
        self.ca_cert = ca_cert
        self.client_cert = client_cert
        self.pk_passwd = pk_passwd
        self.pac_file = pac_file
        self.profile_name = profile_name
        self.file_name = file_name
        self.group_name = group_name
        self.server_ip = server_ip
        self.real = real
        self.expected_passfail_val = expected_passfail_val
        self.csv_name = csv_name
        self.pass_fail_list = []
        self.test_input_list = []
        self.percent_pac_loss = []
        self.wait_time = wait_time
        self.timeline_start = None
        self.timeline_samples = {}
        self.wifi_analysis = None
        self.wifi_analysis_stats = {}
        self.wifi_analysis_start_time = None

    def change_target_to_ip(self):

        # checking if target is an IP or a port
        if (self.target.count('.') != 3 and self.target.split('.')[-2].isnumeric()):
            # checking if target is eth1 or 1.1.eth1
            target_port_list = self.name_to_eid(self.target)
            shelf, resource, port, _ = target_port_list
            port_url = '/port/{}/{}/{}?fields=ip'.format(shelf, resource, port)
            response = self.json_get(port_url)
            if not response:
                logger.error("Failed to fetch port info. Received empty response.\nRequested URL: '{}'\nResponse: {}".format(port_url, response))
                raise RuntimeError('The target port {} not found on the LANforge. Please change the target.'.format(self.target))
            if 'interface' not in response:
                logger.error("'interface' key not found in response.\nRequested URL: '{}'\nResponse: {}".format(port_url, response))
                raise RuntimeError('The target port {} not found on the LANforge. Please change the target.'.format(self.target))
            if 'ip' not in response['interface']:
                logger.error("'ip' key not found in response.\nRequested URL: '{}'\nResponse: {}".format(port_url, response))
                raise RuntimeError('The target port {} not found on the LANforge. Please change the target.'.format(self.target))
            self.target = response['interface']['ip']
            logger.info(self.target)
        else:
            logger.info(self.target)

    def cleanup(self):
        expected_endp_names = []
        # setting the created_cx and created_endp to empty list and adding the existing endpoints to the list for cleanup
        self.generic_endps_profile.created_cx = []
        self.generic_endps_profile.created_endp = []
        if (self.enable_virtual):
            for station in self.sta_list:
                expected_endp_names.append('generic-{}'.format(station.split('.')[2]))
        if (self.enable_real):
            for station in self.real_sta_list:
                expected_endp_names.append('generic-{}'.format(station))

        if expected_endp_names:
            endp_url = "/generic/{}".format(','.join(expected_endp_names))
            response = self.json_get(endp_url)
            if not response:
                logger.error("Failed to fetch endpoints for cleanup.\nRequested URL: '{}'\nResponse: {}".format(endp_url, response))
                endpoint = []
            else:
                endpoint = response.get('endpoints', response.get('endpoint', []))
                if isinstance(endpoint, dict):
                    endpoint = [{endpoint['name']: endpoint}]

            present_endp_names = set()
            for endp_entry in endpoint:
                present_endp_names.update(endp_entry.keys())

            for endp_name in expected_endp_names:
                if endp_name in present_endp_names:
                    self.generic_endps_profile.created_endp.append(endp_name)
                    self.generic_endps_profile.created_cx.append('CX_{}'.format(endp_name))

        if (self.enable_virtual):
            # removing virtual stations if existing
            for station in self.sta_list:
                logger.info('Removing the station {} if exists'.format(station))
                self.rm_port(station, check_exists=True)

            if (not LFUtils.wait_until_ports_disappear(base_url=self.host, port_list=self.sta_list, debug=self.debug)):
                logger.info('All stations are not removed or a timeout occured.')
                logger.error('Aborting the test.')
                exit(0)

        logger.info("Cleaning up generic endpoints if exists: cx={}, endp={}".format(self.generic_endps_profile.created_cx, self.generic_endps_profile.created_endp))
        self.generic_endps_profile.cleanup()
        self.generic_endps_profile.created_cx = []
        self.generic_endps_profile.created_endp = []
        logger.info('Cleanup Successful')

    # Args:
    #   devices: Connected RealDevice object which has already populated tracked real device
    #            resources through call to get_devices()
    def select_real_devices(self, real_devices, real_sta_list=None, base_interop_obj=None, device_list=None):
        if real_sta_list is None:
            self.real_sta_list, _, _ = real_devices.query_user(device_list=device_list)
        else:
            self.real_sta_list = real_sta_list
        if base_interop_obj is not None:
            self.Devices = base_interop_obj

        # Need real stations to run interop test
        if (len(self.real_sta_list) == 0):
            raise RuntimeError('There are no real devices in this testbed. Aborting test')

        logger.info(self.real_sta_list)

        for sta_name in self.real_sta_list:
            if sta_name not in real_devices.devices_data:
                logger.error('Real station {} not in devices data, ignoring it from testing'.format(sta_name))
                continue
                # raise ValueError('Real station not in devices data')

            self.real_sta_data_dict[sta_name] = real_devices.devices_data[sta_name]

        # Track number of selected devices
        self.android = self.Devices.android
        self.windows = self.Devices.windows
        self.mac = self.Devices.mac
        self.linux = self.Devices.linux
        d_list = []
        for i in self.real_sta_list:
            device = i.split('.')
            d_list.append(device[0] + '.' + device[1])
        return d_list

    def buildstation(self):
        logger.info('Creating Stations {}'.format(self.sta_list))
        for station_index in range(len(self.sta_list)):
            shelf, resource, port = self.sta_list[station_index].split('.')
            logger.info('{} {} {}'.format(shelf, resource, port))
            station_object = StationProfile(lfclient_url='http://{}:{}'.format(self.host, self.port), local_realm=self, ssid=self.ssid,
                                            ssid_pass=self.password, security=self.security, number_template_='00', up=True, resource=resource, shelf=shelf)
            station_object.use_security(
                security_type=self.security, ssid=self.ssid, passwd=self.password)

            station_object.create(radio=self.radio, sta_names_=[
                self.sta_list[station_index]])
        station_object.admin_up()
        if self.wait_for_ip([self.sta_list[station_index]]):
            self._pass("All stations got IPs", print_=True)
        else:
            self._fail(
                "Stations failed to get IPs", print_=True)

    def check_tab_exists(self):
        generic_url = "generic"
        response = self.json_get(generic_url)
        if not response:
            logger.error("Failed to fetch generic tab data.\nRequested URL: '{}'\nResponse: {}".format(generic_url, response))
            return False
        return True

    def create_generic_endp(self):
        # Virtual stations are tracked in same list as real stations, so need to separate them
        # in order to create generic endpoints for just the virtual stations
        virtual_stations = list(set(self.sta_list).difference(set(self.real_sta_list)))

        if (self.enable_virtual):
            if (self.generic_endps_profile.create(ports=virtual_stations, sleep_time=.5)):
                logger.info('Virtual client generic endpoint creation completed.')
            else:
                raise RuntimeError('Virtual client generic endpoint creation failed.')

        if (self.enable_real):
            real_sta_os_types = [self.real_sta_data_dict[real_sta_name]['ostype'] for real_sta_name in self.real_sta_data_dict]

            if (self.generic_endps_profile.create(ports=self.real_sta_list, sleep_time=.5, real_client_os_types=real_sta_os_types)):
                logger.info('Real client generic endpoint creation completed.')
            else:
                raise RuntimeError('Real client generic endpoint creation failed.')

    def start_generic(self):
        self.generic_endps_profile.start_cx()
        self.timeline_start = time.time()

    def stop_generic(self):
        if self.missing_endp_logged:
            missing_cx_names = {'CX_{}'.format(endp) for endp in self.missing_endp_logged}
            self.generic_endps_profile.created_endp = [
                endp for endp in self.generic_endps_profile.created_endp
                if endp not in self.missing_endp_logged
            ]
            self.generic_endps_profile.created_cx = [
                cx for cx in self.generic_endps_profile.created_cx
                if cx not in missing_cx_names
            ]
        self.generic_endps_profile.stop_cx()

    def get_results(self):
        logger.debug(self.generic_endps_profile.created_endp)
        endp_url = "/generic/{}".format(','.join(self.generic_endps_profile.created_endp))
        response = self.json_get(endp_url)
        if not response:
            logger.error("Failed to fetch endpoint results.\nRequested URL: '{}'\nResponse: {}".format(endp_url, response))
        else:
            endpoint = response.get('endpoints', response.get('endpoint', []))
            if isinstance(endpoint, dict):
                endpoint = [{endpoint['name']: endpoint}]
            present_endps = {}
            for endp_entry in endpoint:
                for endp_name, endp_response in endp_entry.items():
                    # Use the second-last result when more than one is available.
                    last_results = endp_response.get('last results')
                    if last_results:
                        result_lines = last_results.split('\n')
                        if len(result_lines) > 1:
                            endp_response['last results'] = result_lines[-2]
                    present_endps[endp_name] = endp_response
            self.latest_results.update(present_endps)

        if not self.latest_results:
            logger.error('No ping results were collected for any endpoint during the entire test.')
            return []

        return [{name: data} for name, data in self.latest_results.items()]

    def append_endp_data(self, name, state, response):
        """Save an endpoint state change for the report."""
        self.client_issue_data.append([
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            name,
            state,
            response
        ])

    def write_client_issue_csv(self, report_path):
        """Create the endpoint issue CSV in the report folder."""
        if not self.client_issue_data:
            return

        csv_path = os.path.join(report_path, self.client_issue_csv_name)
        with open(csv_path, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["TIMESTAMP", "ENDP_NAME", "STATE", "API RESPONSE"])
            writer.writerows(self.client_issue_data)

    def check_endpoint_availability(self, expected_endps, present_endps):
        """Log endpoint missing/not-running/recovered transitions and update the tracking sets."""
        endp_url = "/generic/{}".format(','.join(expected_endps))
        for endp_name in expected_endps:
            if endp_name not in present_endps.keys():
                if endp_name not in self.missing_endp_logged:
                    present_endp_names = list(present_endps)
                    logger.warning(
                        "Endpoint '{}' is missing from the monitoring data.\n"
                        "Requested URL: '{}'\n"
                        "Response: {}".format(endp_name, endp_url, present_endp_names))
                    self.append_endp_data(name=endp_name, state="MISSING", response=present_endp_names)
                    self.missing_endp_logged.add(endp_name)
                self.not_running_endp_logged.discard(endp_name)
            elif present_endps[endp_name].get('status').lower() != "run":
                if endp_name not in self.not_running_endp_logged:
                    logger.warning(
                        "Endpoint '{}' is not running in the monitoring data.\n"
                        "Requested URL: '{}'\n"
                        "Response: {}".format(endp_name, endp_url, present_endps[endp_name]))
                    self.append_endp_data(name=endp_name, state=present_endps[endp_name].get('status'), response=present_endps[endp_name])
                    self.not_running_endp_logged.add(endp_name)
                self.missing_endp_logged.discard(endp_name)
            else:
                if endp_name in self.missing_endp_logged or endp_name in self.not_running_endp_logged:
                    logger.info(
                        "Endpoint '{}' is running in the monitoring data\n"
                        "Requested URL: '{}'\n"
                        "Response: {}".format(endp_name, endp_url, present_endps[endp_name]))
                    self.append_endp_data(name=endp_name, state=present_endps[endp_name].get('status'), response=present_endps[endp_name])
                self.missing_endp_logged.discard(endp_name)
                self.not_running_endp_logged.discard(endp_name)

    def is_test_stopped_by_webgui(self):
        """Check the webgui running-instance file to see if the user stopped the test."""
        if not self.dowebgui:
            return False
        running_file = f"{self.result_dir}/../../Running_instances/{self.host}_{self.test_name}_running.json"
        try:
            with open(running_file, "r") as file:
                data = json.load(file)
            if data.get("status") != "Running":
                logger.warning("Test is stopped by the user")
                return True
        except FileNotFoundError:
            logger.warning(f"Running instance file not found: {running_file}")
            return True
        except json.JSONDecodeError:
            logger.warning(f"Running instance file corrupted or empty: {running_file}")
            return True
        except Exception as e:
            logger.error(f"Unexpected error reading running.json: {e}")
            return True
        return False

    def monitor_endp_availability(self, expected_endps, duration=40, interval=5):
        """Retry for up to duration seconds until at least one expected endpoint is present and running."""
        start_time = time.time()
        end_time = start_time + duration
        no_of_attempts = duration // interval
        count = 0
        while (start_time <= end_time):
            count += 1
            if self.is_test_stopped_by_webgui():
                logger.info("Test stopped by user via WebGUI. Exiting monitoring.")
                return False
            if count > 1:
                logger.info("Attempt {} of {} to check endpoints availability".format(count, no_of_attempts))
            endp_url = "/generic/{}".format(','.join(expected_endps))
            response = self.json_get(endp_url)
            if not response:
                logger.error(
                    "Failed to fetch endpoints. Received empty response.\n"
                    f"Requested URL: '{endp_url}'\n"
                    f"Response: {response}")
                response = {}
            endpoint = response.get('endpoints', response.get('endpoint', []))
            if isinstance(endpoint, dict):
                endpoint = [{endpoint['name']: endpoint}]
            present_endps = {}
            for endp_entry in endpoint:
                for endp_name, endp_response in endp_entry.items():
                    # Use the second-last result when more than one is available.
                    last_results = endp_response.get('last results')
                    if last_results:
                        result_lines = last_results.split('\n')
                        if len(result_lines) > 1:
                            endp_response['last results'] = result_lines[-2]
                    present_endps[endp_name] = endp_response
            self.latest_results.update(present_endps)
            self.record_timeline_samples(present_endps)
            self.check_endpoint_availability(expected_endps, present_endps)
            missed = len(self.missing_endp_logged)
            not_run = len(self.not_running_endp_logged)
            if missed == len(expected_endps):
                logger.error("All expected endpoints ({}) are missing from the monitoring data. Retrying... Before giving up and stopping test".format(
                    ", ".join(self.missing_endp_logged)))
            elif not_run == len(expected_endps):
                logger.error("All expected endpoints ({}) are present but not running. Retrying... Before giving up and stopping test".format(
                    ", ".join(self.not_running_endp_logged)))
            elif missed + not_run == len(expected_endps):
                logger.error("Some expected endpoints ({}) are missing and some endpoints ({}) are not running. Retrying... Before giving up and stopping test".format(
                    ", ".join(self.missing_endp_logged), ", ".join(self.not_running_endp_logged)))
            else:
                return True
            time.sleep(interval)
            start_time = time.time()
        return False

    @staticmethod
    def validate_rtt(min_rtt, avg_rtt, max_rtt):
        """Check whether min/avg/max RTT values represent a real ping result.

        A ping that never got a reply shows up differently per OS: Linux/Mac
        report a negative min and/or max (e.g. min=1000000, max=-1000000,
        avg=0), while Windows reports a flat 0.000/0.000/0.000. Either
        signature means the ping did not succeed, so all three values are
        normalized to 'NA'.
        """
        try:
            min_val = float(str(min_rtt).replace(',', ''))
            avg_val = float(str(avg_rtt).replace(',', ''))
            max_val = float(str(max_rtt).replace(',', ''))
        except (TypeError, ValueError):
            return 'NA', 'NA', 'NA'
        if min_val < 0 or avg_val < 0 or max_val < 0 or (min_val == 0 and avg_val == 0 and max_val == 0):
            return 'NA', 'NA', 'NA'
        return min_rtt, avg_rtt, max_rtt

    def generate_remarks(self, station_ping_data):
        remarks = []

        # NOTE if there are any more ping failure cases that are missed, add them here.

        # checking if ping output is not empty
        if (station_ping_data['last_result'] == ""):
            remarks.append('No output for ping')

        # illegal division by zero error. Issue with arguments.
        if ('Illegal division by zero' in station_ping_data['last_result']):
            remarks.append('Illegal division by zero error. Please re-check the arguments passed.')

        # unknown host
        if ('Totals:  *** dropped: 0  received: 0  failed: 0  bytes: 0' in station_ping_data['last_result'] or 'unknown host' in station_ping_data['last_result']):
            remarks.append('Unknown host. Please re-check the target')

        # checking if IP is existing in the ping command or not for Windows device
        if (station_ping_data['os'] == 'Windows'):
            if ('None' in station_ping_data['command'] or station_ping_data['command'].split('-n')[0].split('-S')[-1] == "  "):
                remarks.append('Station has no IP')

        # network buffer overflow
        if ('ping: sendmsg: No buffer space available' in station_ping_data['last_result']):
            remarks.append('Network buffer overlow')

        # checking for no ping states (min/avg/max were normalized to 'NA' by validate_rtt)
        if (station_ping_data['min_rtt'] == 'NA'):

            # Destination Host Unreachable state
            if ('Destination Host Unreachable' in station_ping_data['last_result']):
                remarks.append('Destination Host Unrechable')

            # Destination Net Unreachable state
            if ('Destination Net Unreachable' in station_ping_data['last_result']):
                remarks.append('Destination Net Unreachable')

            # Name or service not known state
            if ('Name or service not known' in station_ping_data['last_result']):
                remarks.append('Name or service not known')

            # Temporary failure in name resolution (e.g. no network/DNS reachable)
            if ('Temporary failure in name resolution' in station_ping_data['last_result']):
                remarks.append('Temporary failure in name resolution')

            # fall back so an invalid/NA ping result is never left unexplained
            if (not remarks):
                remarks.append('Ping failed - invalid RTT statistics (min/avg/max: NA)')

        return (remarks)

    # Converts an upstream port name to its corresponding IP address if it's not already in IP format.
    def change_port_to_ip(self, upstream_port):
        if upstream_port.count('.') != 3:
            target_port_list = self.name_to_eid(upstream_port)
            shelf, resource, port, _ = target_port_list
            try:
                target_port_ip = self.json_get(f'/port/{shelf}/{resource}/{port}?fields=ip')['interface']['ip']
                upstream_port = target_port_ip
            except Exception:
                logger.warning(f'The upstream port is not an ethernet port. Proceeding with the given upstream_port {upstream_port}.')
            logger.info(f"Upstream port IP {upstream_port}")
        else:
            logger.info(f"Upstream port IP {upstream_port}")
        return upstream_port

    # Calculates pass/fail status for each client based on their result compared to the expected value.
    def get_pass_fail_list(self, os_type):
        # When csv_name is provided, for pass/fail criteria, respective values for each client will be used
        if not self.expected_passfail_val:
            res_list = []
            test_input_list = []
            pass_fail_list = []
            adb_url = '/adb/'
            response = self.json_get(adb_url)
            if not response:
                logger.error("Failed to fetch adb data.\nRequested URL: '{}'\nResponse: {}".format(adb_url, response))
                interop_tab_data = None
            else:
                interop_tab_data = response['devices']
                if isinstance(interop_tab_data, dict):
                    interop_tab_data = [{interop_tab_data['name']: interop_tab_data}]
            for client in range(len(os_type)):
                device_name = self.device_names[client].split(' ')[0:-1][0]
                if os_type[client] != 'Android':
                    res_list.append(device_name)
                else:
                    matched_name = None
                    if interop_tab_data is not None:
                        for dev in interop_tab_data:
                            for item in dev.values():
                                if item['user-name'] == device_name:
                                    matched_name = item['name'].split('.')[2]
                                    break
                            if matched_name is not None:
                                break
                    # Always append one entry so res_list stays aligned with os_type/packets_sent.
                    res_list.append(matched_name if matched_name is not None else device_name)
            with open(self.csv_name, mode='r') as file:
                reader = csv.DictReader(file)
                rows = list(reader)
                # fieldnames = reader.fieldnames
            for device in res_list:
                found = False
                for row in rows:
                    if row['DeviceList'] == device and row['PingPacketLoss %'].strip() != '':
                        test_input_list.append(row['PingPacketLoss %'])
                        found = True
                        break
                if not found:
                    logger.info(f"Ping result for device {device} not found in CSV. Using default packet loss = 10%")
                    test_input_list.append(10)
            self.percent_pac_loss = []
            for i in range(len(self.packets_sent)):
                if self.packets_sent[i] != 0:
                    self.percent_pac_loss.append(((self.packets_sent[i] - self.packets_received[i]) / self.packets_sent[i]) * 100)
                else:
                    self.percent_pac_loss.append(0)
            for i in range(len(test_input_list)):
                if self.packets_sent[i] == 0:
                    pass_fail_list.append('FAIL')
                elif float(test_input_list[i]) >= self.percent_pac_loss[i]:
                    pass_fail_list.append('PASS')
                else:
                    pass_fail_list.append('FAIL')
            self.pass_fail_list = pass_fail_list
            self.test_input_list = test_input_list
        # When expected_passfail_val is provided, for pass/fail criteria, the same value will be used for all clients
        else:
            self.test_input_list = [self.expected_passfail_val for val in range(len(self.device_names))]
            self.percent_pac_loss = []
            for i in range(len(self.packets_sent)):
                if self.packets_sent[i] != 0:
                    self.percent_pac_loss.append(((self.packets_sent[i] - self.packets_received[i]) / self.packets_sent[i]) * 100)
                else:
                    self.percent_pac_loss.append(0)
            pass_fail_list = []
            for i in range(len(self.test_input_list)):
                if self.packets_sent[i] == 0:
                    pass_fail_list.append('FAIL')
                elif float(self.expected_passfail_val) >= self.percent_pac_loss[i]:
                    pass_fail_list.append("PASS")
                else:
                    pass_fail_list.append("FAIL")
            self.pass_fail_list = pass_fail_list

    def add_live_view_images_to_report(self, report: lf_report, report_path: str):
        """
        This function looks for throughput and RSSI images for each floor
        in the 'live_view_images' folder within `self.result_dir`.
        It waits up to **60 seconds** for each image. If an image is found,
        it's added to the `report` on a new page; otherwise, it's skipped.
        """
        test_name = os.path.basename(report_path)
        for floor in range(int(self.total_floors)):
            # Construct expected image paths
            packet_sent_image = os.path.join(self.result_dir, "heatmap_images", f"{test_name}_ping_packet_sent_{floor + 1}.png")
            packet_recv_image = os.path.join(self.result_dir, "heatmap_images", f"{test_name}_ping_packet_recv_{floor + 1}.png")
            packet_loss_image = os.path.join(self.result_dir, "heatmap_images", f"{test_name}_ping_packet_loss_{floor + 1}.png")

            # Wait for all required images to be generated (up to timeout)
            timeout = 60  # seconds
            start_time = time.time()

            while not (os.path.exists(packet_sent_image) and os.path.exists(packet_recv_image) and os.path.exists(packet_loss_image)):
                if time.time() - start_time > timeout:
                    print(f"Timeout: Heatmap images for floor {floor + 1} not found within {timeout} seconds.")
                    break
                time.sleep(1)

            report.set_custom_html("<h2>Ping Packet Sent vs Recevied vs Lost: </h2>")
            report.build_custom()

            # Generate report sections for each image if it exists
            for image_path in [packet_sent_image, packet_recv_image, packet_loss_image]:
                if os.path.exists(image_path):
                    report.set_custom_html(f'<img src="file://{image_path}"  style="width:1200px; height:800px;"></img>')
                    report.build_custom()

    # (minimum ping score, rating, badge colour), highest first
    PING_RATING_BANDS = [
        (90, 'Excellent', '#1e7e34'),
        (70, 'Good', '#1d9a8a'),
        (50, 'Average', '#d48b1f'),
        (0, 'Poor', '#d95f5f')
    ]
    # Average RTT (ms) up to which the latency score is 100, and from which it is 0
    LATENCY_FULL_SCORE_MS = 100
    LATENCY_ZERO_SCORE_MS = 300
    # Clients per static graph in the PDF, so each graph fits on one page
    PDF_CLIENTS_PER_GRAPH = 8
    DELIVERY_WEIGHT = 0.7
    LATENCY_WEIGHT = 0.3
    # Colours of the wifi connectivity event categories, in the order they are drawn
    WIFI_EVENT_COLORS = {
        'Disconnected': '#e8742a',
        'Scans': '#1e6b2a',
        'Association Attempts': '#1ba1e2',
        'Association Rejected': '#a2289a',
        'Connected': '#4ea72e'
    }

    @staticmethod
    def _as_int(value):
        try:
            return int(float(str(value).replace(',', '')))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _plural(count, word):
        return '{} {}{}'.format(count, word, '' if count == 1 else 's')

    @staticmethod
    def format_channel(channel):
        return 'N/A' if str(channel).strip() in ('', '0', '-1', 'NA', 'None') else channel

    @classmethod
    def classify_ping_rating(cls, score):
        for threshold, label, color in cls.PING_RATING_BANDS:
            if score >= threshold:
                return label, color
        return cls.PING_RATING_BANDS[-1][1], cls.PING_RATING_BANDS[-1][2]

    def record_timeline_samples(self, present_endps):
        """Record the endpoint packet counters used to build the connectivity timeline."""
        sample_time = time.time()
        for endp_name, endp_data in present_endps.items():
            self.timeline_samples.setdefault(endp_name, []).append((
                sample_time, self._as_int(endp_data.get('tx pkts')), self._as_int(endp_data.get('rx pkts')), self._as_int(endp_data.get('dropped'))))

    @staticmethod
    def append_timeline_segment(segments, client_index, status, start, end):
        """Add a span to a client's connectivity timeline."""
        if end <= start:
            return
        if segments and segments[-1]['clientIndex'] == client_index and segments[-1]['status'] == status:
            segments[-1]['end'] = round(end, 3)
        else:
            segments.append({'clientIndex': client_index, 'start': round(start, 3), 'end': round(end, 3), 'status': status})

    def connectivity_timeline_payload(self):
        """Up/drop spans of every client over the test, built from the packet counters polled while it ran."""
        if not self.timeline_samples:
            return None
        start = self.timeline_start or min(samples[0][0] for samples in self.timeline_samples.values())
        duration = max(samples[-1][0] for samples in self.timeline_samples.values()) - start
        if duration <= 0:
            return None
        try:
            ping_interval = max(float(self.interval), 0.001)
        except (TypeError, ValueError):
            ping_interval = 1.0
        clients, stations, segments = [], [], []
        for station, device_data in self.result_json.items():
            endp_name = 'generic-{}'.format(station.split('.')[2] if device_data['os'] == 'Virtual' else station)
            samples = self.timeline_samples.get(endp_name)
            if not samples:
                continue
            client_index = len(clients)
            clients.append(device_data['name'])
            stations.append(station)
            if self._as_int(device_data['sent']) == 0:
                # nothing was ever sent (for example, the client has no IP), so it never had connectivity
                self.append_timeline_segment(segments, client_index, 'drop', 0.0, duration)
                continue
            previous_time, previous_sent, previous_received, previous_dropped = 0.0, 0, 0, 0
            status = 'up'
            for sample_time, sent, received, dropped in samples:
                elapsed = min(duration, max(0.0, sample_time - start))
                window = elapsed - previous_time
                # pings lost since the previous poll, counting pings that were sent without any reply
                lost = max(dropped - previous_dropped, 0)
                if sent > previous_sent and received <= previous_received:
                    lost = max(lost, sent - previous_sent)
                if lost:
                    # each lost ping is one ping interval of no connectivity; where in the window it happened is unknown, so it is shown at the end
                    down = min(window, lost * ping_interval)
                    self.append_timeline_segment(segments, client_index, 'up', previous_time, elapsed - down)
                    self.append_timeline_segment(segments, client_index, 'drop', max(previous_time, elapsed - down), elapsed)
                    status = 'drop' if down >= window else 'up'
                else:
                    if received > previous_received:
                        status = 'up'
                    self.append_timeline_segment(segments, client_index, status, previous_time, elapsed)
                previous_time, previous_sent, previous_received, previous_dropped = elapsed, sent, received, dropped
        if not clients:
            return None
        return {'clients': clients, 'stations': stations, 'segments': segments, 'duration': round(duration, 3),
                'emptyMessage': 'No time-series ping samples were collected'}

    def start_wifi_analysis(self, host, port, device_list, ssid):
        """Start a RealClientAnalysis window covering the devices under test."""
        self.wifi_analysis = None
        self.wifi_analysis_stats = {}
        if not device_list or RealClientAnalysis is None:
            return
        try:
            self.wifi_analysis = RealClientAnalysis(host=host, port=port, device_list=list(device_list),
                                                    ssid=ssid or "", debug=self.debug)
            self.wifi_analysis_start_time = int(time.time() * 1000)
            logger.info("Wi-Fi connectivity analysis started for devices: %s", device_list)
        except Exception as e:
            logger.warning("Wifi connectivity analysis could not be started: %s", e)
            self.wifi_analysis = None

    def stop_wifi_analysis(self):
        """Analyze '/wifi-msgs' since start_wifi_analysis() into self.wifi_analysis_stats."""
        if not self.wifi_analysis:
            return
        try:
            self.wifi_analysis.query_devices_1()
            local_dict = self.wifi_analysis.create_local_dict()
            if not local_dict:
                logger.warning("None of the wifi connectivity analysis devices resolved to a device LANforge knows about")
                return
            self.wifi_analysis_stats = self.wifi_analysis.get_client_connectivity_stats_from_timestamp(
                self.wifi_analysis_start_time, None, local_dict)
            logger.info("Wi-Fi connectivity analysis completed: %s", self.wifi_analysis_stats)
        except Exception as e:
            logger.warning("Wifi connectivity analysis results could not be collected: %s", e)

    @staticmethod
    def add_page_break(report):
        report.set_custom_html('<div style="page-break-before: always;"></div>')
        report.build_custom()

    def add_interactive_chart(self, report, chart_id, chart_type, payload, title, png_names, x_name='', y_name=''):
        """Adds a chart that is interactive in the HTML report and static images in the PDF."""
        report.set_custom_html('<div class="hideFromPrint">')
        report.build_custom()
        report.build_echarts_chart(chart_id=chart_id, chart_type=chart_type, payload=payload, title=title, y_name=y_name, x_name=x_name)
        report.set_custom_html('</div>')
        report.build_custom()
        for index, png_name in enumerate(png_names):
            report.set_custom_html('<div class="hideFromScreen chart-card"{}><img src="{}" alt="{}" /></div>'.format(
                ' style="page-break-before: always;"' if index else '', png_name, title))
            report.build_custom()

    def add_client_bar_chart(self, report, report_path_date_time, chart_id, title, description, categories, series, x_name):
        """Adds a per client horizontal bar graph with one bar per series, preceded by its description."""
        self.add_page_break(report)
        report.set_obj_html(_obj_title=title, _obj=description)
        report.build_objective()
        bar_height = 0.8 / len(series)
        png_names = []
        for first in range(0, len(categories), self.PDF_CLIENTS_PER_GRAPH):
            names = categories[first:first + self.PDF_CLIENTS_PER_GRAPH]
            fig, ax = plt.subplots(figsize=(14, max(2.6, 0.3 * len(names) + 1.4)))
            for index, item in enumerate(series):
                positions = [position + index * bar_height for position in range(len(names))]
                bars = ax.barh(positions, item['data'][first:first + len(names)], height=bar_height, color=item['color'], label=item['name'])
                ax.bar_label(bars, fmt='%g', fontsize=8, padding=2)
            ax.set_yticks([position + bar_height * (len(series) - 1) / 2 for position in range(len(names))])
            ax.set_yticklabels(names, fontsize=9)
            ax.invert_yaxis()
            ax.set_xlabel(x_name, fontweight='bold', fontsize=11)
            ax.set_ylabel('Wireless Clients', fontweight='bold', fontsize=11)
            ax.set_title(title if not first else '{} (continued)'.format(title), fontsize=14)
            if len(series) > 1:
                ax.legend(loc='best')
            ax.grid(axis='x', linestyle=':', alpha=0.5)
            ax.set_axisbelow(True)
            fig.tight_layout()
            png_names.append('{}_{}.png'.format(chart_id, len(png_names) + 1))
            fig.savefig(os.path.join(report_path_date_time, png_names[-1]), dpi=96)
            plt.close(fig)
        self.add_interactive_chart(report, chart_id, 'horizontal_bar', {'categories': categories, 'series': series}, title, png_names, x_name=x_name)

    def add_wifi_analysis_to_report(self, report, report_path_date_time):
        """Append the wifi connectivity event summary graph and stats table to the report."""
        if not self.wifi_analysis_stats or not self.wifi_analysis:
            return
        try:
            devices, connect_attempt, disconnected, scanning, association_rejection, connected, remarks, cx_time = \
                self.wifi_analysis.dicttolist(self.wifi_analysis_stats)
            port_to_name = {port: data['name'] for port, data in self.result_json.items()}
            devices = [port_to_name.get(port, port) for port in devices]

            categories = list(self.WIFI_EVENT_COLORS)
            totals = [sum(disconnected), sum(scanning), sum(connect_attempt), sum(association_rejection), sum(connected)]
            colors = list(self.WIFI_EVENT_COLORS.values())
            title = 'Client Connectivity Status'

            self.add_page_break(report)
            report.set_obj_html(
                _obj_title='Client Connectivity Event Summary',
                _obj='This graph summarizes connection-related events observed during the ping test. '
                     'These metrics provide insight into client stability and wireless connectivity performance.')
            report.build_objective()
            png_name = 'wifi_connectivity_status.png'
            fig, ax = plt.subplots(figsize=(12, 3.4))
            bars = ax.bar(categories, totals, color=colors, width=0.5, edgecolor='black')
            ax.bar_label(bars, fontweight='bold')
            ax.set_ylim(0, max(totals) * 1.15 if max(totals) > 0 else 1)
            ax.set_ylabel('Count')
            ax.set_title(title, fontsize=16)
            fig.savefig(os.path.join(report_path_date_time, png_name), dpi=96, bbox_inches='tight')
            plt.close(fig)
            # One series per category, stacked, so every category gets its own colour and legend entry
            series = [{'name': category, 'data': [total if position == index else 0 for position, total in enumerate(totals)], 'color': color}
                      for index, (category, color) in enumerate(zip(categories, colors))]
            self.add_interactive_chart(report, 'wifi_connectivity_status', 'bar', {'categories': categories, 'series': series, 'stacked': True},
                                       title, [png_name], y_name='Count')

            report.set_table_title('Wifi Connectivity Analysis')
            report.build_table_title()
            report.set_table_dataframe(pd.DataFrame({
                'Device': devices,
                'Association Attempts': connect_attempt,
                'Disconnected': disconnected,
                'Scanning': scanning,
                'Association Rejection': association_rejection,
                'Connected': connected,
            }))
            report.build_table()
        except Exception as e:
            logger.warning("Wifi connectivity analysis could not be added to the report: %s", e)

    def add_connectivity_timeline_to_report(self, report, report_path_date_time):
        """Append the per client connectivity timeline of the test."""
        timeline = self.connectivity_timeline_payload()
        if not timeline or not timeline['segments']:
            return
        title = 'Wireless Client Connectivity Status vs Time'
        self.add_page_break(report)
        report.set_obj_html(
            _obj_title='Client Connectivity Results Throughout the Test Duration',
            _obj='The graph illustrates the connectivity status of all wireless clients during the test based on connectivity monitoring '
                 'during the test execution. Green segments represent successful responses, while red segments indicate packet loss '
                 'or connectivity drops observed during the test.')
        report.build_objective()
        png_names = []
        for first in range(0, len(timeline['clients']), self.PDF_CLIENTS_PER_GRAPH):
            names = timeline['clients'][first:first + self.PDF_CLIENTS_PER_GRAPH]
            fig, ax = plt.subplots(figsize=(14, 0.28 * len(names) + 1.0))
            for segment in timeline['segments']:
                if first <= segment['clientIndex'] < first + len(names):
                    ax.barh(segment['clientIndex'] - first, segment['end'] - segment['start'], left=segment['start'], height=0.6,
                            color='#1e7e34' if segment['status'] == 'up' else '#e53935')
            ax.set_yticks(range(len(names)))
            ax.set_yticklabels(names)
            ax.invert_yaxis()
            ax.set_xlim(0, timeline['duration'])
            ax.set_xlabel('Time (s)')
            ax.set_title(title if not first else '{} (continued)'.format(title), fontsize=14)
            ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color='#1e7e34'), plt.Rectangle((0, 0), 1, 1, color='#e53935')],
                      labels=['Up (reply received)', 'Drop (packet lost)'], loc='upper center',
                      bbox_to_anchor=(0.5, -0.15), ncol=2, frameon=False)
            png_names.append('ping_connectivity_timeline_{}.png'.format(len(png_names) + 1))
            fig.savefig(os.path.join(report_path_date_time, png_names[-1]), dpi=96, bbox_inches='tight')
            plt.close(fig)
        self.add_interactive_chart(report, 'ping-connectivity-timeline', 'connectivity_timeline', timeline, title, png_names)

    def build_client_scores(self):
        """Packet loss, delivery, latency and ping score and the rating of every client."""
        scores = {'loss': [], 'delivery': [], 'latency': [], 'ping': [], 'rating': []}
        for sent, received, avg_rtt in zip(self.packets_sent, self.packets_received, self.device_avg):
            delivery = min(100.0, received / sent * 100) if sent > 0 else 0.0
            if received <= 0 or avg_rtt == 'NA':
                latency = 0.0
            else:
                latency_span = self.LATENCY_ZERO_SCORE_MS - self.LATENCY_FULL_SCORE_MS
                latency = max(0.0, min(100.0, (self.LATENCY_ZERO_SCORE_MS - avg_rtt) / latency_span * 100))
            ping_score = round(self.DELIVERY_WEIGHT * delivery + self.LATENCY_WEIGHT * latency, 2)
            scores['loss'].append(round(100.0 - delivery, 2))
            scores['delivery'].append(round(delivery, 2))
            scores['latency'].append(round(latency, 2))
            scores['ping'].append(ping_score)
            scores['rating'].append(self.classify_ping_rating(ping_score)[0])
        return scores

    def add_key_findings_to_report(self, report, scores, overall_score, overall_rating):
        """Adds a short plain-English summary of the test results to the report."""
        total = len(self.packets_sent)
        responding = [i for i in range(total) if self.packets_received[i] > 0]
        no_reply = total - len(responding)
        if total == 0:
            findings = ['No ping results were collected for any client during the test.']
        else:
            if no_reply == 0:
                findings = ['All {} received ping replies from the target during the test.'.format(self._plural(total, 'client'))]
            elif not responding:
                findings = ['None of the {} received ping replies from the target; all recorded 100% packet loss.'.format(self._plural(total, 'client'))]
            else:
                findings = ['{} of {} clients ({:.1f}%) received ping replies from the target during the test; {} received no replies and recorded 100% packet loss.'.format(
                    len(responding), total, len(responding) / total * 100, self._plural(no_reply, 'client'))]
            if responding:
                avg_loss = sum(scores['loss'][i] for i in responding) / len(responding)
                if avg_loss <= 1:
                    findings.append('Packet loss was minimal for responding clients, averaging {:.2f}% across the {}, indicating reliable communication for connected clients.'.format(
                        avg_loss, self._plural(len(responding), 'client')))
                elif avg_loss <= 5:
                    findings.append('Packet loss was moderate for responding clients, averaging {:.2f}% across the {}.'.format(
                        avg_loss, self._plural(len(responding), 'client')))
                else:
                    findings.append('Packet loss was high for responding clients, averaging {:.2f}% across the {}, indicating unstable communication.'.format(
                        avg_loss, self._plural(len(responding), 'client')))
            rtts = [self.device_avg[i] for i in responding if self.device_avg[i] != 'NA']
            if rtts:
                slow = sum(1 for rtt in rtts if rtt > self.LATENCY_FULL_SCORE_MS)
                if slow == 0:
                    findings.append('Latency was low for all responding clients, with an average RTT of {:.1f} ms.'.format(sum(rtts) / len(rtts)))
                else:
                    findings.append('Latency {} for most clients, with an average RTT of {:.1f} ms across responding clients; {} exceeded {} ms.'.format(
                        'remained stable' if slow * 2 <= len(rtts) else 'was high', sum(rtts) / len(rtts), self._plural(slow, 'client'), self.LATENCY_FULL_SCORE_MS))
            findings.append('Overall, the network achieved a ping score of {:.2f} out of 100, giving an overall rating of {}.'.format(overall_score, overall_rating))
        items = ''.join("<li style='font-size:14px; color:var(--ink); line-height:1.5;'>{}</li>".format(point) for point in findings)
        report.set_custom_html("<div class='info-card'><div class='info-card-header'>Key Findings</div>"
                               "<ul style='margin:0; padding-left:20px; display:flex; flex-direction:column; gap:10px;'>{}</ul></div>".format(items))
        report.build_custom()

    def add_client_graphs_to_report(self, report, report_path_date_time, client_names, scores):
        """Adds the per client average RTT, packet loss and packets sent vs received graphs."""
        responding = sorted((self.device_avg[i], client_names[i]) for i in range(len(client_names))
                            if self.device_avg[i] != 'NA' and self.packets_received[i] > 0)
        if responding:
            rtts = [rtt for rtt, _ in responding]
            no_reply = len(client_names) - len(responding)
            self.add_client_bar_chart(
                report, report_path_date_time, 'per_client_rtt', 'Per Client Average RTT',
                'The graph below illustrates the average round-trip time observed by each Wi-Fi client during the test. The X-axis represents '
                'the average RTT in milliseconds, while the Y-axis lists the individual wireless client identifiers.{}<br>'
                'Average RTT: {:.2f} ms | Median RTT: {:.2f} ms | RTT Range: {:.2f} – {:.2f} ms'.format(
                    ' The {} that received no replies are not plotted.'.format(self._plural(no_reply, 'client')) if no_reply else '',
                    sum(rtts) / len(rtts), statistics.median(rtts), min(rtts), max(rtts)),
                [name for _, name in responding], [{'name': 'Average RTT (ms)', 'data': rtts, 'color': '#2f80ed'}], 'Average RTT (ms)')

        lossy = sorted((scores['loss'][i], client_names[i]) for i in range(len(client_names)) if scores['loss'][i] > 0)
        if lossy:
            self.add_client_bar_chart(
                report, report_path_date_time, 'per_client_loss', 'Per Client Packet Loss',
                'The graph below illustrates the packet loss percentage observed by each Wi-Fi client during the test. The X-axis represents '
                'the percentage of sent packets that were not received, while the Y-axis lists the wireless clients that experienced packet loss. '
                'All other clients recorded 0% packet loss.',
                [name for _, name in lossy], [{'name': 'Packet Loss %', 'data': [loss for loss, _ in lossy], 'color': '#d95f5f'}], 'Packet Loss (%)')
        elif client_names:
            report.set_obj_html(_obj_title='Per Client Packet Loss', _obj='All clients recorded 0% packet loss.')
            report.build_objective()

        if client_names:
            self.add_client_bar_chart(
                report, report_path_date_time, 'per_client_packets', 'Per Client Packets Sent vs Received',
                'The graph below compares the number of ICMP packets sent and received by each Wi-Fi client during the test. The X-axis represents '
                'the packet count, while the Y-axis lists the individual wireless client identifiers. A gap between the two bars indicates lost packets.',
                client_names, [{'name': 'Packets Sent', 'data': self.packets_sent, 'color': '#2f80ed'},
                               {'name': 'Packets Received', 'data': self.packets_received, 'color': '#1f6f58'}], 'Packets')

    def get_group_indices(self, groupdevlist: List[str]) -> List[int]:
        """Positions, in the report's device lists, of the devices that belong to a group."""
        indices = []
        adb_url = '/adb/'
        response = self.json_get(adb_url)
        if not response:
            logger.error("Failed to fetch adb data.\nRequested URL: '{}'\nResponse: {}".format(adb_url, response))
            interop_tab_data = None
        else:
            interop_tab_data = response['devices']
            if isinstance(interop_tab_data, dict):
                interop_tab_data = [{interop_tab_data['name']: interop_tab_data}]
        for i in range(len(self.device_names)):
            for j in groupdevlist:
                # For a string like "test3 Linux":
                # - device_names[i].split(" ")[0:-1][0] gives 'test3' (device name)
                # - device_names[i].split(" ")[-1] gives 'Linux' (OS type)
                # This condition filters out Android clients and matches device name with j
                if j == self.device_names[i].split(" ")[0:-1][0] and self.device_names[i].split(" ")[-1] != 'Android':
                    indices.append(i)
                elif interop_tab_data is not None:
                    for dev in interop_tab_data:
                        for item in dev.values():
                            # For a string like "samsungmob Android":
                            # - device_names[i].split(' ')[0:-1][0] (e.g., 'samsungmob') matches item['user-name']
                            # - The group name (e.g., 'RZCTA09CTXF') matches with item['name'].split('.')[-1]
                            if item['user-name'] == self.device_names[i].split(' ')[0:-1][0] and j == item['name'].split('.')[-1]:
                                indices.append(i)
        return sorted(set(indices))

    def generate_report(self, result_json=None, result_dir='Ping_Test_Report', report_path='', config_devices='', group_device_map=None):
        if result_json is not None:
            self.result_json = result_json
        logger.info('Generating Report')

        report = lf_report(_output_pdf='interop_ping.pdf',
                           _output_html='interop_ping.html',
                           _results_dir_name=result_dir,
                           _path=report_path)
        report_path = report.get_path()
        report_path_date_time = report.get_path_date_time()

        self.write_client_issue_csv(report_path_date_time)

        logger.info('path: {}'.format(report_path))
        logger.info('path_date_time: {}'.format(report_path_date_time))

        # setting report title
        client_kind = 'Real' if self.real and not self.enable_virtual else 'Virtual' if self.enable_virtual and not self.real else 'Real and Virtual'
        report.set_title("LANforge Interop<br>Ping Test<br>"
                         "<span style='font-size:0.45em; font-weight:400;'>({} Client Connectivity Validation)</span>".format(client_kind))
        report.build_banner()
        report.set_custom_html('<style>@media print { .chart-card, .info-card { page-break-inside: avoid; } '
                               'table.data-table { font-size: 9px; } table.data-table th, table.data-table td { padding: 3px 4px; } '
                               '.ping-results td { white-space: nowrap; } }</style>')
        report.build_custom()

        self.packets_sent = []
        self.packets_received = []
        self.packets_dropped = []
        self.device_names = []
        self.device_modes = []
        self.device_channels = []
        self.device_min = []
        self.device_max = []
        self.device_avg = []
        self.device_mac = []
        self.device_ip = []
        self.device_bssid = []
        self.device_names_with_errors = []
        self.devices_with_errors = []
        self.report_names = []
        self.remarks = []
        self.device_ssid = []
        os_type = []
        for device, device_data in self.result_json.items():
            logger.debug('Device data: {} {}'.format(device, device_data))
            os_type.append(device_data['os'])
            self.packets_sent.append(int(device_data['sent']))
            self.packets_received.append(int(device_data['recv']))
            self.packets_dropped.append(int(device_data['dropped']))
            self.device_names.append(device_data['name'] + ' ' + device_data['os'])
            self.device_modes.append(device_data['mode'])
            self.device_channels.append(device_data['channel'])
            self.device_mac.append(device_data['mac'])
            self.device_ip.append(device_data.get('ip') or 'N/A')
            self.device_bssid.append(device_data.get('bssid') or 'N/A')
            self.device_ssid.append(device_data['ssid'])
            # NA (failed ping) is kept as text for the tables and skipped by the graphs
            self.device_min.append(device_data['min_rtt'] if device_data['min_rtt'] == 'NA' else float(device_data['min_rtt'].replace(',', '')))
            self.device_max.append(device_data['max_rtt'] if device_data['max_rtt'] == 'NA' else float(device_data['max_rtt'].replace(',', '')))
            self.device_avg.append(device_data['avg_rtt'] if device_data['avg_rtt'] == 'NA' else float(device_data['avg_rtt'].replace(',', '')))
            if (device_data['os'] == 'Virtual'):
                self.report_names.append('{} {}'.format(device, device_data['os'])[0:25])
            else:
                self.report_names.append('{} {} {}'.format(device, device_data['os'], device_data['name']))
            if (device_data['remarks'] != []):
                self.device_names_with_errors.append(device_data['name'])
                self.devices_with_errors.append(device)
                self.remarks.append(','.join(device_data['remarks']))

        ports = list(self.result_json)
        client_names = [device_data['name'] for device_data in self.result_json.values()]
        scores = self.build_client_scores()
        overall_score = round(sum(scores['ping']) / len(scores['ping']), 2) if scores['ping'] else 0.0
        overall_rating, overall_color = self.classify_ping_rating(overall_score)
        rating_colors = {label: color for _, label, color in self.PING_RATING_BANDS}

        # objective and description
        report.set_obj_html(_obj_title='Test Overview',
                            _obj='''The Candela Ping test assesses network connectivity for wireless clients, such as Android, Linux, Windows, and macOS
                            devices and virtual stations, by sending ICMP echo requests from each client to a target host and measuring the round-trip
                            time (RTT) of every reply. The test detects packet loss, delays, and response-time variations across clients, ensuring
                            effective device communication and helping identify connectivity problems. The expected behavior is for every associated
                            client to receive replies consistently, with low packet loss and stable RTT for the duration of the test. A healthy network
                            should show all clients responding, with RTT clustered in a narrow band and no clients losing connectivity.
                            ''')
        report.build_objective()

        report.build_info_card(
            title='Overall Test Verdict',
            items=[
                {'label': 'Total Devices Tested', 'value': str(len(ports))},
                {'label': 'Ping Target', 'value': str(self.target)},
                {'label': 'Overall Ping Score', 'value': '{:.2f} / 100'.format(overall_score)},
                {'label': 'Overall Rating', 'value': "<span style='color:{}; font-weight:800;'>{}</span>".format(overall_color, overall_rating)},
            ])
        self.add_key_findings_to_report(report, scores, overall_score, overall_rating)
        self.add_client_graphs_to_report(report, report_path_date_time, client_names, scores)
        self.add_wifi_analysis_to_report(report, report_path_date_time)
        self.add_connectivity_timeline_to_report(report, report_path_date_time)

        self.add_page_break(report)
        report.set_obj_html(
            _obj_title='Overall Tabular Results for all Wi-Fi Clients',
            _obj='The below table provides detailed per-client ping results -- IP and MAC address, BSSID, channel, packets sent and received, '
                 'packet loss, average RTT, delivery and latency scores, ping score, and rating -- for all Wi-Fi clients. '
                 'Channel is shown as N/A when the client does not report it.')
        report.build_objective()
        dataframe = pd.DataFrame({
            'Port': ports,
            'Device Type': os_type,
            'Wireless Client': client_names,
            'IP Address': self.device_ip,
            'MAC': self.device_mac,
            'BSSID': self.device_bssid,
            'Channel': [self.format_channel(channel) for channel in self.device_channels],
            'Packets Sent': self.packets_sent,
            'Packets Received': self.packets_received,
            'Packet Loss %': ['{:.2f}'.format(loss) for loss in scores['loss']],
            'Average RTT (ms)': [rtt if rtt == 'NA' else '{:.2f}'.format(rtt) for rtt in self.device_avg],
            'Delivery Score': ['{:.2f}'.format(delivery) for delivery in scores['delivery']],
            'Latency Score': ['{:.2f}'.format(latency) for latency in scores['latency']],
            'Ping Score': ['{:.2f}'.format(ping_score) for ping_score in scores['ping']],
            'Rating': scores['rating'],
        })
        report.set_custom_html('<div class="ping-results">')
        report.build_custom()
        if self.real:
            # Calculating the pass/fail criteria when either expected_passfail_val or csv_name is provided
            if self.expected_passfail_val or self.csv_name:
                self.get_pass_fail_list(os_type)
                dataframe['Expected Packet Loss %'] = self.test_input_list
                dataframe['Status'] = self.pass_fail_list
            # When groups are provided a seperate table will be generated for each group
            if self.group_name and group_device_map:
                for key, val in group_device_map.items():
                    indices = self.get_group_indices(val)
                    if indices:
                        report.set_obj_html("", "Group: {}".format(key))
                        report.build_objective()
                        report.set_table_dataframe(dataframe.iloc[indices].reset_index(drop=True))
                        report.rating_build_table('Rating', rating_colors)
            else:
                report.set_table_dataframe(dataframe)
                report.rating_build_table('Rating', rating_colors)
            if self.get_live_view:
                self.add_live_view_images_to_report(report=report, report_path=report_path)
        else:
            report.set_table_dataframe(dataframe)
            report.rating_build_table('Rating', rating_colors)

        report.set_custom_html('</div>')
        report.build_custom()

        # only show the NA caveat when at least one device actually has NA latency
        if ('NA' in self.device_min):
            report.set_text("Note: Stations which are not reachable to the internet, and the ping failed to receive any packets, "
                            "resulting in 100% packet loss. Hence, the latency is reported as NA.")
            report.build_text_simple()

        # check if there are remarks for any device. If there are remarks, build table else don't
        if (self.remarks != []):
            report.set_table_title('Notes')
            report.build_table_title()
            dataframe3 = pd.DataFrame({
                'Wireless Client': self.device_names_with_errors,
                'Port': self.devices_with_errors,
                'Remarks': self.remarks
            })
            report.set_table_dataframe(dataframe3)
            report.build_table()

        report.build_device_summary_card([{'name': name, 'platform': platform} for name, platform in zip(client_names, os_type)])

        # Test configuration for devices in device list
        device_counts = ', '.join('{}: {}'.format(platform, os_type.count(platform))
                                  for platform in ('Android', 'Windows', 'Linux', 'Mac', 'Virtual') if platform in os_type)
        duration_sec = int(round(float(self.duration) * 60))
        config_items = []
        if config_devices == '':
            config_items.append({'label': 'SSID', 'value': self.ssid or ', '.join(sorted(set(self.device_ssid)))})
            config_items.append({'label': 'Security', 'value': self.security if self.ssid else 'N/A'})
        # Test configuration for devices in groups
        else:
            config_items.append({'label': 'Configuration', 'value': 'Groups:{} -> Profiles:{}'.format(', '.join(config_devices.keys()), ', '.join(config_devices.values()))})
        config_items += [
            {'label': 'Website / IP', 'value': str(self.target)},
            {'label': 'No. of Devices', 'value': '{} ({})'.format(len(ports), device_counts) if device_counts else str(len(ports))},
            {'label': 'Test Duration', 'value': '{:02d}:{:02d}:{:02d}'.format(duration_sec // 3600, (duration_sec % 3600) // 60, duration_sec % 60)},
            {'label': 'Test Date', 'value': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')},
        ]
        report.build_info_card(title='Test Configuration', items=config_items)

        report.build_footer()
        report.write_html()
        report.write_pdf(_orientation='Landscape')


def validate_args(args):
    # input sanity
    if args.virtual is False and args.real is False:
        logger.error('Atleast one of --real or --virtual is required')
        exit(1)
    if args.virtual is True and args.radio is None:
        logger.error('--radio required')
        exit(1)
    if args.virtual is True and args.ssid is None:
        logger.error('--ssid required for virtual stations')
        exit(1)
    if args.ssid and args.passwd and args.group_name and args.profile_name:
        logger.error('either --ssid,--password,--security or --profile_name,--group_name should be given')
        exit(1)
    if args.use_default_config is False and args.group_name is None and args.file_name is None and args.profile_name is None:
        if args.ssid is None:
            logger.error('--ssid required for Wi-Fi configuration')
            exit(1)

        if args.security.lower() != 'open' and args.passwd == '[BLANK]':
            logger.error('--passwd required for Wi-Fi configuration')
            exit(1)

        if args.server_ip is None:
            logger.error('--server_ip or upstream ip required for Wi-fi configuration')
            exit(1)
        if args.group_name and (args.file_name is None or args.profile_name is None):
            logger.error("Please provide file name and profile name for group configuration")
            exit(1)
        elif args.file_name and (args.group_name is None or args.profile_name is None):
            logger.error("Please provide group name and profile name for file configuration")
            exit(1)
        elif args.profile_name and (args.group_name is None or args.file_name is None):
            logger.error("Please provide group name and file name for profile configuration")
            exit(1)
    # Get group and profile values from arguments and convert comma-separated strings into lists
    if args.group_name:
        selected_groups = args.group_name.split(',')
    else:
        selected_groups = []  # Default to empty list if group name is not provided
    if args.profile_name:
        selected_profiles = args.profile_name.split(',')
    else:
        selected_profiles = []  # Default to empty list if profile name is not provided
    if len(selected_groups) != len(selected_profiles):
        logger.error("Number of groups should match number of profiles")
        exit(1)
    if args.device_csv_name and args.expected_passfail_value:
        logger.error("Enter either --device_csv_name or --expected_passfail_value")
        exit(1)


def main():

    help_summary = '''\
The Candela Tech ping test is to evaluate network connectivity and measure the round-trip time taken for
data packets to travel from the source to the destination and back. It helps assess the reliability and latency of the network,
identifying any packet loss, delays, or variations in response times. The test aims to ensure that devices can communicate
effectively over the network and pinpoint potential issues affecting connectivity.
    '''

    parser = argparse.ArgumentParser(
        prog='interop_ping.py',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog='''
            Allows user to run the ping test on a target IP or port for the given duration and packet interval
            with either selected number of virtual stations or provides the list of available real devices
            and allows the user to select the real devices and run ping test on them.
        ''',
        description='''
        NAME: lf_interop_ping.py

        PURPOSE: lf_interop_ping.py will let the user select real devices, virtual devices or both and then allows them to run
        ping test for user given duration and packet interval on the given target IP or domain name.

        EXAMPLE-1:
        Command Line Interface to run ping test with only virtual clients
        python3 lf_interop_ping.py --mgr 192.168.200.103  --target 192.168.1.3 --virtual --num_sta 1 --radio 1.1.wiphy2 --ssid RDT_wpa2 --security wpa2
        --passwd OpenWifi --ping_interval 1 --ping_duration 1 --server_ip 192.168.1.61 --debug

        EXAMPLE-2:
        Command Line Interface to run ping test with only real clients
        python3 lf_interop_ping.py --mgr 192.168.200.103 --real --target 192.168.1.3 --ping_interval 1 --ping_duration 1 --server_ip 192.168.1.61 --ssid RDT_wpa2
        --security wpa2_personal --passwd OpenWifi

        EXAMPLE-3:
        Command Line Interface to run ping test with both real and virtual clients
        python3 lf_interop_ping.py --mgr 192.168.200.103 --target 192.168.1.3 --real --virtual --num_sta 1 --radio 1.1.wiphy2 --ssid RDT_wpa2 --security wpa2
        --passwd OpenWifi --ping_interval 1 --ping_duration 1 --server_ip 192.168.1.61

        EXAMPLE-4:
        Command Line Interface to run ping test with existing Wi-Fi configuration on the real devices
        python3 lf_interop_ping.py --mgr 192.168.200.63 --real --target 192.168.1.61 --ping_interval 5 --ping_duration 1 --passwd OpenWifi --use_default_config

        EXAMPLE-5:
        Command Line Interface to run ping test by setting device specific Pass/Fail values in the csv file
        python3 lf_interop_ping.py --mgr 192.168.244.97 --real --target 192.168.1.3 --ping_interval 1 --ping_duration 1 --device_csv_name device.csv
        --use_default_config

        EXAMPLE-6:
        Command Line Interface to run ping test by setting the same expected Pass/Fail value for all devices
        python3 lf_interop_ping.py --mgr 192.168.244.97 --real --target 192.168.1.3 --ping_interval 1 --ping_duration 1 --expected_passfail_value 3
        --use_default_config

        EXAMPLE-7:
        Command Line Interface to run ping test by configuring Real Devices with SSID, Password, and Security
        python3 lf_interop_ping.py --mgr 192.168.244.97 --real --target 192.168.1.3 --ping_interval 1 --ping_duration 1  --ssid RDT_wpa2 --security wpa2
        --passwd OpenWifi --server_ip 192.168.244.97 --wait_time 30

        EXAMPLE-8:
        Command Line Interface to run ping test by Configuring Devices in Groups with Specific Profiles
        python3 lf_interop_ping.py --mgr 192.168.244.97 --real --target 192.168.1.3 --ping_interval 1 --ping_duration 1   --group_name grp3 --file_name g219 --profile_name Open5
        --server_ip 192.168.204.60

        EXAMPLE-9:
        Command Line Interface to run ping test by Configuring Devices in Groups with Specific Profiles with expected Pass/Fail values
        python3 lf_interop_ping.py --mgr 192.168.244.97 --real --target 192.168.1.3 --ping_interval 1 --ping_duration 1   --group_name grp3 --file_name g219 --profile_name Open5
        --expected_passfail_value 3 --server_ip 192.168.204.60

        EXAMPLE-10:
        Command Line Interface for Configuring Devices in Groups with Specific Profiles with device_csv_name
        python3 lf_interop_ping.py --mgr 192.168.244.97 --real --target 192.168.1.3 --ping_interval 1 --ping_duration 1   --group_name grp3 --file_name g219 --profile_name Open5
        --device_csv_name device.csv --server_ip 192.168.204.60

        SCRIPT_CLASSIFICATION : Test

        SCRIPT_CATEGORIES: Performance, Functional, Report Generation

        NOTES:
        1.Use './lf_interop_ping.py --help' to see command line usage and options
        2.Please pass ping_duration in minutes
        3.Please pass ping_interval in seconds
        4.After passing the cli, if --real flag is selected, then a list of available real devices will be displayed on the terminal.
        5.Enter the real device resource numbers seperated by commas (,)

        STATUS: BETA RELEASE

        VERIFIED_ON:
        Working date    - 20/09/2023
        Build version   - 5.4.7
        kernel version  - 6.2.16+

        License: Free to distribute and modify. LANforge systems must be licensed.
        Copyright (C) 2020-2026 Candela Technologies Inc.
        '''
    )
    # required = parser.add_argument_group('Required arguments')
    optional = parser.add_argument_group('Optional arguments')

    # optional arguments
    optional.add_argument('--mgr',
                          type=str,
                          help='hostname where LANforge GUI is running',
                          default='localhost')

    optional.add_argument('--target',
                          type=str,
                          help='Target URL or port for ping test',
                          default='1.1.eth1')

    optional.add_argument('--ping_interval',
                          type=str,
                          help='Interval (in seconds) between the echo requests',
                          default='1')

    optional.add_argument('--ping_duration',
                          type=float,
                          help='Duration (in minutes) to run the ping test',
                          default=1)

    optional.add_argument('--ssid',
                          type=str,
                          help='SSID for connecting the stations')

    optional.add_argument('--mgr_port',
                          type=str,
                          default=8080,
                          help='port on which LANforge HTTP service is running'
                          )

    optional.add_argument('--mgr_passwd',
                          type=str,
                          default='lanforge',
                          help='Password to connect to LANforge GUI')

    optional.add_argument('--server_ip',
                          type=str,
                          help='Upstream for configuring the Interop App')

    optional.add_argument('--security',
                          type=str,
                          default='open',
                          help='Security protocol for the specified SSID: <open | wep | wpa | wpa2 | wpa3>')

    optional.add_argument('--passwd',
                          type=str,
                          default='[BLANK]',
                          help='passphrase for the specified SSID')

    optional.add_argument('--virtual',
                          action="store_true",
                          help='specify this flag if the test should run on virtual clients')

    optional.add_argument('--num_sta',
                          type=int,
                          default=1,
                          help='specify the number of virtual stations to be created.')

    optional.add_argument('--radio',
                          type=str,
                          help='specify the radio to create the virtual stations')

    optional.add_argument('--real',
                          action="store_true",
                          help='specify this flag if the test should run on real clients')

    optional.add_argument('--use_default_config',
                          action='store_true',
                          help='specify this flag if wanted to proceed with existing Wi-Fi configuration of the devices')

    optional.add_argument('--debug',
                          action="store_true",
                          help='Enable debugging')

    # local report directory used by lf_report
    parser.add_argument('--local_lf_report_dir',
                        help='--local_lf_report_dir override the report path (lanforge/html-reports), primary used when making another directory lanforge/html-report/<test_rig>',
                        default="")

    # logging configuration:
    parser.add_argument('--log_level', default=None,
                        help='Set logging level: debug | info | warning | error | critical')

    parser.add_argument("--lf_logger_config_json",
                        help="--lf_logger_config_json <json file> , json configuration of logger")
    parser.add_argument('--help_summary', default=None, action="store_true", help='Show summary of what this script does')
    parser.add_argument('--group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    parser.add_argument('--profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')
    parser.add_argument('--file_name', type=str, help='Specify the file name containing group details. Example:file1')
    parser.add_argument("--eap_method", type=str, default='DEFAULT', help="Specify the EAP method for authentication.")
    parser.add_argument("--eap_identity", type=str, default='', help="Specify the EAP identity for authentication.")
    parser.add_argument("--ieee8021x", action="store_true", help='Enables 802.1X enterprise authentication for test stations.')
    parser.add_argument("--ieee80211u", action="store_true", help='Enables IEEE 802.11u (Hotspot 2.0) support.')
    parser.add_argument("--ieee80211w", type=int, default=1, help='Enables IEEE 802.11w (Management Frame Protection) support.')
    parser.add_argument("--enable_pkc", action="store_true", help='Enables pkc support.')
    parser.add_argument("--bss_transition", action="store_true", help='Enables BSS transition support.')
    parser.add_argument("--power_save", action="store_true", help='Enables power-saving features.')
    parser.add_argument("--disable_ofdma", action="store_true", help='Disables OFDMA support.')
    parser.add_argument("--roam_ft_ds", action="store_true", help='Enables fast BSS transition (FT) support')
    parser.add_argument("--key_management", type=str, default='DEFAULT', help='Specify the key management method (e.g., WPA-PSK, WPA-EAP')
    parser.add_argument("--pairwise", type=str, default='[BLANK]')
    parser.add_argument("--private_key", type=str, default='[BLANK]', help='Specify EAP private key certificate file.')
    parser.add_argument("--ca_cert", type=str, default='[BLANK]', help='Specifiy the CA certificate file name')
    parser.add_argument("--client_cert", type=str, default='[BLANK]', help='Specify the client certificate file name')
    parser.add_argument("--pk_passwd", type=str, default='[BLANK]', help='Specify the password for the private key')
    parser.add_argument("--pac_file", type=str, default='[BLANK]', help='Specify the pac file name')
    parser.add_argument('--expected_passfail_value', help='Enter the expected packet loss', default=None)
    parser.add_argument('--device_csv_name', type=str, help='Enter the csv name to store expected values', default=None)
    parser.add_argument('--wait_time', type=int, help="Enter the maximum wait time for configurations to apply", default=60)
    parser.add_argument('--wifi_analysis', '--wifi-analysis',
                        dest='wifi_analysis',
                        action='store_true',
                        help='Analyze real-client wifi-msgs (connects/disconnects/scans/association rejections) '
                             'for the duration of the test and include the results in the report')

    args = parser.parse_args()

    if args.help_summary:
        print(help_summary)
        exit(0)

    # set the logger level to debug
    logger_config = lf_logger_config.lf_logger_config()

    if args.log_level:
        logger_config.set_level(level=args.log_level)

    if args.lf_logger_config_json:
        # logger_config.lf_logger_config_json = "lf_logger_config.json"
        logger_config.lf_logger_config_json = args.lf_logger_config_json
        logger_config.load_lf_logger_config()
    validate_args(args)

    mgr_ip = args.mgr
    mgr_password = args.mgr_passwd
    mgr_port = args.mgr_port
    server_ip = args.server_ip
    ssid = args.ssid
    security = args.security
    password = args.passwd
    num_sta = args.num_sta
    radio = args.radio
    target = args.target
    interval = args.ping_interval
    duration = args.ping_duration
    configure = not args.use_default_config
    debug = args.debug
    group_name = args.group_name
    file_name = args.file_name
    profile_name = args.profile_name
    eap_method = args.eap_method
    eap_identity = args.eap_identity
    ieee80211 = args.ieee8021x
    ieee80211u = args.ieee80211u
    ieee80211w = args.ieee80211w
    enable_pkc = args.enable_pkc
    bss_transition = args.bss_transition
    power_save = args.power_save
    disable_ofdma = args.disable_ofdma
    roam_ft_ds = args.roam_ft_ds
    key_management = args.key_management
    pairwise = args.pairwise
    private_key = args.private_key
    ca_cert = args.ca_cert
    client_cert = args.client_cert
    pk_passwd = args.pk_passwd
    pac_file = args.pac_file

    if (debug):
        print('''Specified configuration:
              ip:                       {}
              port:                     {}
              ssid:                     {}
              security:                 {}
              password:                 {}
              target:                   {}
              Ping interval:            {}
              Packet Duration (in min): {}
              virtual:                  {}
              num of virtual stations:  {}
              radio:                    {}
              real:                     {}
              debug:                    {}
              '''.format(mgr_ip, mgr_port, ssid, security, password, target, interval, duration, args.virtual, num_sta, radio, args.real, debug))

    # ping object creation
    ping = Ping(host=mgr_ip, port=mgr_port, ssid=ssid, security=security, password=password, radio=radio,
                lanforge_password=mgr_password, target=target, interval=interval, sta_list=[], virtual=args.virtual, real=args.real, duration=duration, debug=debug, csv_name=args.device_csv_name,
                expected_passfail_val=args.expected_passfail_value, wait_time=args.wait_time, group_name=group_name)

    # changing the target from port to IP
    ping.change_target_to_ip()

    # creating virtual stations if --virtual flag is specified
    if (args.virtual):

        logger.info('Proceeding to create {} virtual stations on {}'.format(num_sta, radio))
        station_list = LFUtils.portNameSeries(
            prefix_='sta', start_id_=0, end_id_=num_sta - 1, padding_number_=100000, radio=radio)
        ping.sta_list = station_list
        if (debug):
            logger.info('Virtual Stations: {}'.format(station_list).replace(
                '[', '').replace(']', '').replace('\'', ''))

    # selecting real clients if --real flag is specified
    if (args.real):
        Devices = RealDevice(manager_ip=mgr_ip, selected_bands=[])
        Devices.get_devices()
        ping.Devices = Devices
        # ping.select_real_devices(real_devices=Devices)
        # If config is True, attempt to bring up all devices in the list and perform tests on those that become active
        if (configure):
            config_devices = {}
            obj = DeviceConfig.DeviceConfig(lanforge_ip=mgr_ip, file_name=file_name, wait_time=args.wait_time)
            # Case 1: Group name, file name, and profile name are provided
            if group_name and file_name and profile_name:
                selected_groups = group_name.split(',')
                selected_profiles = profile_name.split(',')
                for i in range(len(selected_groups)):
                    config_devices[selected_groups[i]] = selected_profiles[i]
                obj.initiate_group()
                group_device_map = obj.get_groups_devices(data=selected_groups, groupdevmap=True)
                # Configure devices in the selected group with the selected profile
                eid_list = asyncio.run(obj.connectivity(config=config_devices, upstream=server_ip))
                Devices.get_devices()
                ping.select_real_devices(real_devices=Devices, device_list=eid_list)
            # Case 2: Device list is empty but config flag is True — prompt the user to input device details for configuration
            else:
                all_devices = obj.get_all_devices()
                device_list = []
                config_dict = {
                    'ssid': ssid,
                    'passwd': password,
                    'enc': security,
                    'eap_method': eap_method,
                    'eap_identity': eap_identity,
                    'ieee80211': ieee80211,
                    'ieee80211u': ieee80211u,
                    'ieee80211w': ieee80211w,
                    'enable_pkc': enable_pkc,
                    'bss_transition': bss_transition,
                    'power_save': power_save,
                    'disable_ofdma': disable_ofdma,
                    'roam_ft_ds': roam_ft_ds,
                    'key_management': key_management,
                    'pairwise': pairwise,
                    'private_key': private_key,
                    'ca_cert': ca_cert,
                    'client_cert': client_cert,
                    'pk_passwd': pk_passwd,
                    'pac_file': pac_file,
                    'server_ip': server_ip,
                }
                for device in all_devices:
                    if device["type"] == 'laptop':
                        device_list.append(device["shelf"] + '.' + device["resource"] + " " + device["hostname"])
                    else:
                        device_list.append(device["eid"] + " " + device["serial"])
                logger.info(f"Available devices: {device_list}")
                dev_list = input("Enter the desired resources to run the test:").split(',')
                dev_list = asyncio.run(obj.connectivity(device_list=dev_list, wifi_config=config_dict))
                Devices.get_devices()
                ping.select_real_devices(real_devices=Devices, device_list=dev_list)
        # Case 3: Config is False, no device list is provided, and no group is selected
        # Prompt the user to manually input devices for running the test
        else:
            device_list = ping.Devices.get_devices()
            logger.info(f"Available devices: {device_list}")
            dev_list = input("Enter the desired resources to run the test:").split(',')
            ping.select_real_devices(real_devices=Devices, device_list=dev_list)

    # station precleanup
    ping.cleanup()

    # building station if virtual
    if (args.virtual):
        ping.buildstation()

    # check if generic tab is enabled or not
    if (not ping.check_tab_exists()):
        raise RuntimeError('Generic Tab is not available.\nAborting the test.')

    ping.sta_list += ping.real_sta_list

    # creating generic endpoints
    ping.create_generic_endp()

    # run the test for the given duration
    logger.info('Running the ping test for {} minutes'.format(duration))

    if args.wifi_analysis:
        ping.start_wifi_analysis(host=mgr_ip, port=mgr_port, device_list=ping.real_sta_list, ssid=ssid)

    # start generate endpoint
    ping.start_generic()
    start_time = time.time()
    end_time = start_time + (duration * 60)
    while time.time() < end_time:
        success = ping.monitor_endp_availability(ping.generic_endps_profile.created_endp)
        if not success:
            logger.error('All endpoints are not available. So exiting the monitor early.')
            break
        time.sleep(3)
    logger.info('Stopping the test')
    ping.stop_generic()
    ping.stop_wifi_analysis()

    result_data = ping.get_results()
    logger.info("Endpoint results after stopping the test: {}".format(result_data))
    if (args.virtual):
        ports_url = '/ports/all/'
        response = ping.json_get(ports_url)
        if not response:
            logger.error("Failed to fetch ports. Received empty response.\nRequested URL: '{}'\nResponse: {}".format(ports_url, response))
            raise RuntimeError('Failed to fetch port data from the LANforge.')
        if 'interfaces' not in response:
            logger.error("'interfaces' key not found in response.\nRequested URL: '{}'\nResponse: {}".format(ports_url, response))
            raise RuntimeError('Failed to fetch port data from the LANforge.')
        ports_data_dict = response['interfaces']
        ports_data = {}
        for ports in ports_data_dict:
            port, port_data = list(ports.keys())[0], list(ports.values())[0]
            ports_data[port] = port_data
        for station in ping.sta_list:
            if (station not in ping.real_sta_list):
                current_device_data = ports_data[station]
                for ping_device in result_data:
                    ping_endp, ping_data = list(ping_device.keys())[
                        0], list(ping_device.values())[0]
                    if (station.split('.')[2] in ping_endp):
                        last_result_lines = []
                        try:
                            last_result_lines = ping_data['last results'].split('\n') if ping_data['last results'] else []
                            if len(last_result_lines) > 1:
                                last_result = last_result_lines[-2]
                            elif last_result_lines:
                                last_result = last_result_lines[-1]
                            else:
                                last_result = ""

                            if 'min/avg/max' in last_result:
                                rtt_values = last_result.split('min/avg/max:', 1)[1].strip().split()[0].split('/')
                                min_rtt, avg_rtt, max_rtt = ping.validate_rtt(rtt_values[0], rtt_values[1], rtt_values[2])
                            else:
                                min_rtt, avg_rtt, max_rtt = 'NA', 'NA', 'NA'

                            ping.result_json[station] = {
                                'command': ping_data['command'],
                                'sent': ping_data['tx pkts'],
                                'recv': ping_data['rx pkts'],
                                'dropped': ping_data['dropped'],
                                'min_rtt': min_rtt,
                                'avg_rtt': avg_rtt,
                                'max_rtt': max_rtt,
                                'mac': current_device_data['mac'],
                                'ip': current_device_data.get('ip'),
                                'bssid': current_device_data.get('ap'),
                                'ssid': current_device_data['ssid'],
                                'channel': current_device_data['channel'],
                                'mode': current_device_data['mode'],
                                'name': station,
                                'os': 'Virtual',
                                'remarks': [],
                                'last_result': last_result
                            }
                            ping.result_json[station]['remarks'] = ping.generate_remarks(ping.result_json[station])
                        except Exception as error:
                            logger.error(
                                "Failed parsing the result for station %s. Error: %s\nLast result lines: %s",
                                station, error, last_result_lines)

    if (args.real):
        for station in ping.real_sta_list:
            current_device_data = Devices.devices_data[station]
            for ping_device in result_data:
                ping_endp, ping_data = list(ping_device.keys())[
                    0], list(ping_device.values())[0]
                if (station in ping_endp):
                    last_result_lines = []
                    try:
                        last_result_lines = ping_data['last results'].split('\n') if ping_data['last results'] else []
                        if len(last_result_lines) > 1:
                            last_result = last_result_lines[-2]
                        elif last_result_lines:
                            last_result = last_result_lines[-1]
                        else:
                            last_result = ""

                        if 'min/avg/max' in last_result:
                            rtt_values = last_result.split('min/avg/max:', 1)[1].strip().split()[0].split('/')
                            min_rtt, avg_rtt, max_rtt = ping.validate_rtt(rtt_values[0], rtt_values[1], rtt_values[2])
                        else:
                            min_rtt, avg_rtt, max_rtt = 'NA', 'NA', 'NA'

                        ping.result_json[station] = {
                            'command': ping_data['command'],
                            'sent': ping_data['tx pkts'],
                            'recv': ping_data['rx pkts'],
                            'dropped': ping_data['dropped'],
                            'min_rtt': min_rtt,
                            'avg_rtt': avg_rtt,
                            'max_rtt': max_rtt,
                            'mac': current_device_data['mac'],
                            'ip': current_device_data.get('ip'),
                            'bssid': current_device_data.get('ap'),
                            'ssid': current_device_data['ssid'],
                            'channel': current_device_data['channel'],
                            'mode': current_device_data['mode'],
                            'name': [current_device_data['user'] if current_device_data['user'] != '' else current_device_data['hostname']][0],
                            'os': ['Windows' if 'Win' in current_device_data['hw version'] else 'Linux' if 'Linux' in current_device_data['hw version'] else 'Mac' if 'Apple' in current_device_data['hw version'] else 'Android'][0],  # noqa E501
                            'remarks': [],
                            'last_result': last_result
                        }
                        ping.result_json[station]['remarks'] = ping.generate_remarks(ping.result_json[station])
                    except Exception as error:
                        logger.error(
                            "Failed parsing the result for station %s. Error: %s\nLast result lines: %s",
                            station, error, last_result_lines)

    logger.info("Final parsed per-station results: {}".format(ping.result_json))

    # station post cleanup
    ping.cleanup()

    if args.local_lf_report_dir == "":
        # Report generation when groups are specified but no custom report path is provided
        if args.group_name:
            ping.generate_report(config_devices=config_devices, group_device_map=group_device_map)
        # Report generation when no group is specified and no custom report path is provided
        else:
            ping.generate_report()
    else:
        # Report generation when groups are specified and a custom report path is provided
        if args.group_name:
            ping.generate_report(config_devices=config_devices, group_device_map=group_device_map, report_path=args.local_lf_report_dir)
        # Report generation when no group is specified but a custom report path is provided
        else:
            ping.generate_report(report_path=args.local_lf_report_dir)


if __name__ == "__main__":
    main()
