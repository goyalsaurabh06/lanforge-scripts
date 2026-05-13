#!/usr/bin/env python3
"""
NAME:       lf_interop_qos.py

PURPOSE:    lf_interop_qos.py will provide the available devices and allows user to run the qos traffic
            with particular tos on particular devices in upload, download directions.

NOTES:      1. Use './lf_interop_qos.py --help' to see command line usage and options
            2. Please pass tos in CAPITALS as shown :"BK,VI,BE,VO"
            3. Please enter the download or upload rate in bps
            4. After passing cli, a list will be displayed on terminal which contains available resources to run test.
            5. specify client_type Real/Virtual/Both --> (New command flag used for Script Integration).
            The following sentence will be displayed
            Enter the desired resources to run the test:
            Please enter the port numbers seperated by commas ','.
            Example:
            Enter the desired resources to run the test:1.10,1.11,1.12,1.13,1.202,1.203,1.303

EXAMPLES:   # Command Line Interface to run download scenario with tos : Voice
            ./lf_interop_qos.py --ap_name Cisco --mgr 192.168.209.223 --mgr_port 8080 --ssid Cisco
                --passwd cisco@123 --security wpa2 --upstream eth1 --test_duration 1m --download 1000000 --upload 0
                --traffic_type lf_udp --tos "VO"

            # Command Line Interface to run download scenario with tos : Voice and Video
            ./lf_interop_qos.py --ap_name Cisco --mgr 192.168.209.223 --mgr_port 8080 --ssid Cisco
                --passwd cisco@123 --security wpa2 --upstream eth1 --test_duration 1m --download 1000000 --upload 0
                --traffic_type lf_udp --tos "VO,VI"

            # Load scenario with tos : Background, Besteffort, Video and Voice
            ./lf_interop_qos.py --ap_name Cisco --mgr 192.168.209.223 --mgr_port 8080 --ssid Cisco
                --passwd cisco@123 --security wpa2 --upstream eth1 --test_duration 1m --download 0 --upload 1000000
                --traffic_type lf_udp --tos "BK,BE,VI,VO"

            # Command Line Interface to run bi-directional scenario with tos : Video and Voice
            ./lf_interop_qos.py --ap_name Cisco --mgr 192.168.209.223 --mgr_port 8080 --ssid Cisco
                --passwd cisco@123 --security wpa2 --upstream eth1 --test_duration 1m --download 1000000 --upload 1000000
                --traffic_type lf_udp --tos "VI,VO"

            # Command Line Interface to run upload scenario by setting the same expected Pass/Fail value for all devices
            ./lf_interop_qos.py  --ap_name Cisco --mgr 192.168.244.97 --test_duration 1m --upstream_port eth1 --upload 1000000
                --mgr_port 8080 --traffic_type lf_udp --tos "VI,VO,BE,BK" --ssid DLI-LPC992 --passwd Password@123
                --security wpa2 --expected_passfail_value 0.3

            # Command Line Interface to run upload scenario by setting device specific Pass/Fail values in the csv file
            ./lf_interop_qos.py  --ap_name Cisco --mgr 192.168.244.97 --test_duration 1m --upstream_port eth1 --upload 1000000
                --mgr_port 8080 --traffic_type lf_udp --tos "VI,VO,BE,BK" --ssid DLI-LPC992 --passwd Password@123
                --security wpa2 --device_csv_name device_config.csv

            # Command Line Interface to run upload scenario by Configuring Real Devices with SSID, Password, and Security
            ./lf_interop_qos.py  --ap_name Cisco --mgr 192.168.244.97 --test_duration 1m --upstream_port eth1 --upload 1000000
                --mgr_port 8080 --traffic_type lf_udp --tos "VI,VO,BE,BK" --ssid DLI-LPC992 --passwd Password@123
                --security wpa2 --config

            # Command Line Interface to run upload scenario by setting the same expected Pass/Fail value for all devices with configuration
            ./lf_interop_qos.py  --ap_name Cisco --mgr 192.168.244.97 --test_duration 1m --upstream_port eth1 --upload 1000000
                --mgr_port 8080 --traffic_type lf_udp --tos "VI,VO,BE,BK" --ssid DLI-LPC992 --passwd Password@123
                --security wpa2 --config --expected_passfail_value 0.3

            # Command Line Interface to run upload scenario by Configuring Devices in Groups with Specific Profiles
            ./lf_interop_qos.py  --ap_name Cisco --mgr 192.168.244.97 --test_duration 1m --upstream_port eth1 --upload 1000000
                --mgr_port 8080 --traffic_type lf_udp --tos "VI,VO,BE,BK" --file_name g219 --group_name grp1 --profile_name Open3
            # Command Line Interface to run upload scenario by Configuring Devices in Groups with Specific Profiles for Real Devices
            ./lf_interop_qos.py  --ap_name Cisco --mgr 192.168.244.97 --test_duration 1m --upstream_port eth1 --upload 1000000
                --mgr_port 8080 --traffic_type lf_udp --tos "VI,VO,BE,BK" --file_name g219 --group_name grp1 --profile_name Open3 --bands 2.4G

            # Command Line Interface to run upload scenario by Configuring Devices in Groups with Specific Profiles with expected Pass/Fail values
            ./lf_interop_qos.py  --ap_name Cisco --mgr 192.168.244.97 --test_duration 1m --upstream_port eth1 --upload 1000000
                --mgr_port 8080 --traffic_type lf_udp --tos "VI,VO,BE,BK" --file_name g219 --group_name grp1 --profile_name Open3
                --expected_passfail_value 0.3 --wait_time 30

            # Command Line Interface to run the Test along with IOT without device list
            ./lf_interop_qos.py --mgr 192.168.207.78 --upstream_port eth1 --security None --ssid "NETGEAR_2G_wpa2" --passwd "" --traffic_type lf_tcp --download 10000000
                --upload 0 --test_duration 1m --tos VO,VI,BE,BK --device_list 1.5,1.13
                --iot_test --iot_testname "IotTest" --iot_delay 5

            # Command Line Interface to run the Test along with IOT with device list
            ./lf_interop_qos.py --mgr 192.168.207.78 --upstream_port eth1 --security None --ssid "NETGEAR_2G_wpa2" --passwd "" --traffic_type lf_tcp --download 10000000
                --upload 0 --test_duration 1m --tos VO,VI,BE,BK --device_list 1.13 --iot_test --iot_ip 127.0.0.1 --iot_port 8000 --iot_iterations 1
                --iot_delay 5 --iot_device_list "switch.smart_plug_1_socket_1" --iot_testname "QosWithIot" --iot_increment ""

            # Command Line Interface to run the QOS Test along with Robot by enabling rotation at the specified coordinates
            ./lf_interop_qos.py  --ap_name Cisco --mgr 192.168.207.78 --test_duration 1m --upstream_port eth1 --upload 1000000 --mgr_port 8080 --traffic_type lf_udp
                --tos "VI,VO,BE,BK" --ssid DLI-LPC992 --passwd Password@123 --security wpa2 --robot_ip 192.168.204.101 --rotation 30,90 --coordinate 3,4 --robot_test

            # Command Line Interface to run the QOS Test along with Robot at the specified coordinates without any rotation
            ./lf_interop_qos.py  --ap_name Cisco --mgr 192.168.207.78 --test_duration 1m --upstream_port eth1 --upload 1000000 --mgr_port 8080 --traffic_type lf_udp
                --tos "VI,VO,BE,BK" --ssid DLI-LPC992 --passwd Password@123 --security wpa2 --robot_ip 192.168.204.101 --coordinate 3,4 --robot_test

            # Command Line Interface to run the QOS Test along with Robot by enabling band steering at the specified coordinates.
            ./lf_interop_qos.py  --ap_name Cisco --mgr 192.168.207.78 --test_duration 1m --upstream_port eth1 --upload 1000000 --mgr_port 8080 --traffic_type lf_udp
                --tos "VI,VO,BE,BK" --ssid DLI-LPC992 --passwd Password@123 --security wpa2 --robot_ip 192.168.204.101 --coordinate 3,4 --robot_test --do_bandsteering
                --cycles 1 --bssids 7a:1d:35:c8:da:b9

            # Run download scenario with Voice TOS in 2.4GHz band for Virtual Stations
            ./lf_interop_qos.py --ap_name Cisco --mgr 192.168.209.223 --mgr_port 8080 --num_stations_2g 32 --radio_2g wiphy0
                --ssid_2g Cisco --passwd_2g cisco@123 --security_2g wpa2 --bands 2.4g --upstream eth1 --test_duration 1m
                --download 1000000 --upload 0 --traffic_type lf_udp --tos "VO" --create_sta --client_type Virtual

            # Run Bi-directional scenario with Voice and Video TOS in 5GHz band for Virtual Stations
            ./lf_interop_qos.py --ap_name Cisco --mgr 192.168.207.78 --mgr_port 8080 --num_stations_5g 3 --radio_5g wiphy1
                --ssid_5g NETGEAR_5G_wpa2 --passwd_5g Password@123 --security_5g wpa2 --bands 5g --upstream eth1 --test_duration 1m
                --download 1000000 --upload 2000000 --traffic_type lf_tcp --timebreak 5s --tos "VO,VI" --create_sta --client_type Virtual

            # Run download scenario with Voice and Video TOS in 6GHz band for Virtual Stations
            ./lf_interop_qos.py --ap_name Cisco --mgr 192.168.209.223 --mgr_port 8080 --num_stations_6g 32 --radio_6g wiphy1
                --ssid_6g Cisco --passwd_6g cisco@123 --security_6g wpa2 --bands 6g --upstream eth1 --test_duration 1m
                --download 1000000 --upload 0 --traffic_type lf_tcp --timebreak 5s --tos "VO,VI" --create_sta --client_type Virtual

            # Run upload scenario with Background, Best Effort, Video, and Voice TOS in 2.4GHz and 5GHz bands for Virtual Stations
            ./lf_interop_qos.py --ap_name Cisco --mgr 192.168.209.223 --mgr_port 8080 --num_stations_2g 32 --num_stations_5g 32 --radio_2g wiphy0
                --ssid_2g Cisco --passwd_2g cisco@123 --security_2g wpa2 --radio_5g wiphy1 --ssid_5g Cisco --passwd_5g cisco@123
                --security_5g wpa2 --bands dualband --upstream eth1 --test_duration 1m --timebreak 5s --download 0 --upload 1000000
                --traffic_type lf_udp --tos "BK,BE,VI,VO" --create_sta --client_type Virtual

            # Run upload scenario with Background, Best Effort, Video and Voice TOS in 2.4GHz and 5GHz bands with 'Open' security for Virtual Stations
            ./lf_interop_qos.py --ap_name Cisco --mgr 192.168.209.223 --mgr_port 8080 --num_stations_2g 32 --num_stations_5g 32 --radio_2g wiphy0
                --ssid_2g Cisco --passwd_2g [BLANK] --security_2g open --radio_5g wiphy1 --ssid_5g Cisco --passwd_5g [BLANK]
                --security_5g open --bands dualband --upstream eth1 --test_duration 1m --timebreak 5s --download 0 --upload 1000000
                --traffic_type lf_udp --tos "BK,BE,VI,VO" --create_sta --client_type Virtual

            # Run bi-directional scenario with Video and Voice TOS in 6GHz band for Virtual Stations
            ./lf_interop_qos.py --ap_name Cisco --mgr 192.168.209.223 --mgr_port 8080 --num_stations 32 --radio_6g wiphy1
                --ssid_6g Cisco --passwd_6g cisco@123 --security_6g wpa2 --bands 6g --upstream eth1 --test_duration 1m --timebreak 5s
                --download 1000000 --upload 10000000 --traffic_type lf_udp --tos "VO,VI" --create_sta --client_type Virtual

            # Run Bi_Directional Scenario for Both real and virtual stations in dual band scenario with all TOS values.
            ./lf_interop_qos.py --client_type Both --ap_name Cisco --mgr 192.168.207.78 --mgr_port 8080
            --ssid "NETGEAR_2G_wpa2" --passwd "Password@123" --security wpa2
            --num_stations_2g 4 --radio_2g wiphy0 --ssid_2g "NETGEAR_2G_wpa2" --passwd_2g Password@123 --security_2g wpa2
            --num_stations_5g 4 --radio_5g wiphy1 --ssid_5g "NETGEAR_5G_wpa2" --passwd_5g Password@123 --security_5g wpa2
            --bands dualband --upstream eth1 --test_duration 1m --download 1000000 --upload 1000000 --traffic_type lf_tcp --tos "BK,BE,VI,VO" --create_sta --timebreak 5s

            # Run Download Scenario By Configuring Both Real Devices and Virtual Stations in 5g band scenario with TOS values "VI,VO".
            ./lf_interop_qos.py --client_type Both --ap_name Cisco --mgr 192.168.207.78 --mgr_port 8080 --ssid "NETGEAR_2G_wpa2" --passwd "Password@123" --security wpa2
            --num_stations_5g 4 --radio_5g wiphy1 --ssid_5g "NETGEAR_5G_wpa2" --passwd_5g Password@123 --security_5g wpa2 --bands 5g
            --upstream eth1 --test_duration 1m --download 10000000 --traffic_type lf_tcp --tos "VI,VO" --create_sta --config --timebreak 5s --expected_passfail_value 5

            # Run Bi_Directional Scenario for both real and virtual stations in 5g band scenario with all TOS values.
            ./lf_interop_qos.py --client_type Both --ap_name Cisco --mgr 192.168.207.78 --mgr_port 8080
            --ssid "NETGEAR_2G_wpa2" --passwd "Password@123" --security wpa2
            --num_stations_5g 4 --radio_5g wiphy1 --ssid_5g "NETGEAR_5G_wpa2" --passwd_5g Password@123 --security_5g wpa2 --bands 5g --upstream eth1 --test_duration 1m --download 100000000 --upload 100000000 --traffic_type lf_tcp --tos "BK,BE,VI,VO" --create_sta --timebreak 5s

            # Run Bi_Directional Scenario for both real and virtual stations in tri band scenario with all TOS values.
            ./lf_interop_qos.py --client_type Both --ap_name Cisco --mgr 192.168.207.78 --mgr_port 8080
            --ssid "NETGEAR_2G_wpa2" --passwd "Password@123" --security wpa2
            --num_stations_2g 4 --radio_2g wiphy0 --ssid_2g "NETGEAR_2G_wpa2" --passwd_2g Password@123 --security_2g wpa2
            --num_stations_5g 4 --radio_5g wiphy1 --ssid_5g "NETGEAR_5G_wpa2" --passwd_5g Password@123 --security_5g wpa2
            --num_stations_6g 4 --radio_6g wiphy0 --ssid_6g "NETGEAR_2G_wpa2" --passwd_6g Password@123 --security_6g wpa2 --bands triband --upstream eth1 --test_duration 1m --download 100000000 --upload 100000000 --traffic_type lf_tcp --tos "BK,BE,VI,VO" --create_sta --timebreak 5s

            # Run Bi_Directional Scenario for both real and virtual stations in 2.4G band scenario with all TOS values along with Time Break.
            ./lf_interop_qos.py --client_type Both --ap_name Cisco --mgr 192.168.207.78 --mgr_port 8080
            --ssid "NETGEAR_2G_wpa2" --passwd "Password@123" --security wpa2
            --num_stations_2g 4 --radio_2g wiphy0 --ssid_2g "NETGEAR_2G_wpa2" --passwd_2g Password@123 --security_2g wpa2 --bands 5g --upstream eth1 --test_duration 1m --download 100000000 --upload 100000000 --traffic_type lf_tcp --tos "BK,BE,VI,VO" --create_sta --timebreak 5s

SCRIPT_CLASSIFICATION:
            Test

SCRIPT_CATEGORIES:
            Performance,  Functional, Report Generation

STATUS:     BETA RELEASE

VERIFIED_ON:
            Working date:   26/07/2023
            Build version:  5.4.8
            Kernel version: 6.2.16+

LICENSE:    Free to distribute and modify. LANforge systems must be licensed.
            Copyright (C) 2020-2026 Candela Technologies Inc
"""

from lf_base_robo import RobotClass
import time
import argparse
import sys
import os
import pandas as pd
import importlib
import copy
import logging
import json
import shutil
import asyncio
import csv
import re
from datetime import datetime, timedelta
from collections import defaultdict
import threading
from collections import OrderedDict, Counter

if sys.version_info[0] != 3:
    print("This script requires Python 3")
    exit(1)

if 'py-json' not in sys.path:
    sys.path.append(os.path.join(os.path.abspath('..'), 'py-json'))

# For whatever reason this import is required to run....but isn't directly used
from LANforge import LFUtils  # noqa: F401
realm = importlib.import_module("py-json.realm")
Realm = realm.Realm
from lf_report import lf_report  # noqa: E402
from lf_graph import lf_bar_graph, lf_bar_graph_horizontal  # noqa: E402

logger = logging.getLogger(__name__)
lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")
# Importing DeviceConfig to apply device configurations for ADB devices and laptops
DeviceConfig = importlib.import_module("py-scripts.DeviceConfig")

iot_scripts_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../local/interop-webGUI/IoT/scripts/"))
if os.path.exists(iot_scripts_path):
    sys.path.insert(0, iot_scripts_path)
    from test_automation import Automation  # noqa: E402


class ThroughputQOS(Realm):
    def __init__(self,
                 tos,
                 ssid=None,
                 security=None,
                 password=None,
                 ssid_2g=None,
                 security_2g=None,
                 password_2g=None,
                 ssid_5g=None,
                 security_5g=None,
                 password_5g=None,
                 ssid_6g=None,
                 security_6g=None,
                 password_6g=None,
                 create_sta=True,
                 num_stations_2g=1,
                 num_stations_5g=0,
                 num_stations_6g=0,
                 radio_2g="wiphy0",
                 radio_5g="wiphy1",
                 radio_6g="wiphy2",
                 name_prefix=None,
                 upstream=None,
                 num_stations=10,
                 host="localhost",
                 file_name=None,
                 profile_name=None,
                 group_name=None,
                 port=8080,
                 mode=0,
                 test_name=None,
                 device_list=None,
                 result_dir=None,
                 ap_name="",
                 traffic_type=None,
                 direction="",
                 side_a_min_rate=0, side_a_max_rate=0,
                 side_b_min_rate=56, side_b_max_rate=0,
                 number_template="00000",
                 test_duration="2m",
                 bands="",
                 initial_band_pref=False,
                 test_case=None,
                 use_ht160=False,
                 _debug_on=False,
                 _exit_on_error=False,
                 _exit_on_fail=False,
                 dowebgui=False,
                 ip="localhost",
                 sta_list=None,
                 channel_list=None,
                 user_list=None,
                 real_client_list=None,
                 real_client_list1=None,
                 hw_list=None,
                 laptop_list=None,
                 android_list=None,
                 mac_list=None,
                 windows_list=None,
                 linux_list=None,
                 total_resources_list=None,
                 working_resources_list=None,
                 hostname_list=None,
                 username_list=None,
                 eid_list=None,
                 devices_available=None,
                 input_devices_list=None,
                 mac_id1_list=None,
                 mac_id_list=None,
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
                 config=False,
                 csv_direction=None,
                 expected_passfail_val=None,
                 csv_name=None,
                 wait_time=60,
                 get_live_view=False,
                 total_floors=0,
                 robot_test=False,
                 robot_ip=None,
                 coordinate=None,
                 rotation=None,
                 rotation_enabled=None,
                 angle_list=None,
                 client_type=None,
                 do_bandsteering=False,
                 cycles=None,
                 bssids=None,
                 duration_to_skip=None,
                 timebreak=0):
        super().__init__(lfclient_host=host,
                         lfclient_port=port)
        # For Virtual Stations
        if not sta_list:
            sta_list = []
        if not test_case:
            test_case = {}
        if not channel_list:
            channel_list = []
        if not mac_list:
            mac_list = []

        self.client_type = client_type
        self.ssid_list = []       # We will be using these for report generation.
        self.macid_list = []
        self.mode_list = []
        self.bssid_list = []
        self.channels_list = []
        self.rssi_list = []
        self.upstream = upstream
        self.host = host
        self.port = port
        self.test_name = test_name
        self.device_list = device_list if device_list else []
        self.result_dir = result_dir

        # SSID, Password, Security Fields for Real Devices.
        self.ssid = ssid
        self.security = security
        self.password = password

        self._explicit_ssid = (ssid is not None)  # to validate --real only scenario.

        self.test_case = test_case

        # SSID, Password, Security Fields for Virtual Stations
        self.ssid_2g = ssid_2g
        self.security_2g = security_2g
        self.password_2g = password_2g
        self.ssid_5g = ssid_5g
        self.security_5g = security_5g
        self.password_5g = password_5g
        self.ssid_6g = ssid_6g
        self.security_6g = security_6g
        self.password_6g = password_6g
        self.radio_2g = radio_2g
        self.radio_5g = radio_5g
        self.radio_6g = radio_6g
        self.num_stations_2g = num_stations_2g
        self.num_stations_5g = num_stations_5g
        self.num_stations_6g = num_stations_6g
        self.sta_list = sta_list
        self.channel_list = channel_list if channel_list else []
        self.test_case = test_case if test_case else {}
        # bands: always stored as a string; build_virtual_stations() will split it
        self.bands = bands if bands else ""
        self.create_sta = create_sta
        self.initial_band_pref = initial_band_pref
        self.mode = mode

        self.num_stations = num_stations  # These are default num_stations for real clients.
        self.ap_name = ap_name
        self.traffic_type = traffic_type
        self.direction = direction
        self.tos = tos.split(",")
        self.number_template = number_template
        self.debug = _debug_on
        self.name_prefix = name_prefix
        self.test_duration = test_duration
        self.station_profile = self.new_station_profile()
        self.cx_profile = self.new_l3_cx_profile()
        self.station_profile.lfclient_url = self.lfclient_url
        self.station_profile.ssid = self.ssid
        self.station_profile.ssid_pass = self.password
        self.station_profile.security = self.security
        self.station_profile.number_template_ = self.number_template
        self.station_profile.debug = self.debug
        self.station_profile.use_ht160 = use_ht160
        self.cx_profile.host = self.host
        self.cx_profile.port = self.port
        self.cx_profile.name_prefix = self.name_prefix
        self.cx_profile.side_a_min_bps = side_a_min_rate
        self.cx_profile.side_a_max_bps = side_a_max_rate
        self.cx_profile.side_b_min_bps = side_b_min_rate
        self.cx_profile.side_b_max_bps = side_b_max_rate
        self.hw_list = hw_list if hw_list else []
        self.laptop_list = laptop_list if laptop_list else []
        self.android_list = android_list if android_list else []
        self.mac_list = mac_list if mac_list else []
        self.windows_list = windows_list if windows_list else []
        self.linux_list = linux_list if linux_list else []
        self.total_resources_list = total_resources_list if total_resources_list else []
        self.working_resources_list = working_resources_list if working_resources_list else []
        self.hostname_list = hostname_list if hostname_list else []
        self.username_list = username_list if username_list else []
        self.eid_list = eid_list if eid_list else []
        self.devices_available = devices_available if devices_available else []
        self.input_devices_list = input_devices_list if input_devices_list else []
        self.real_client_list = real_client_list if real_client_list else []
        self.real_client_list1 = real_client_list1 if real_client_list1 else []
        self.user_list = user_list if user_list else []
        self.mac_id_list = mac_id_list if mac_id_list else []
        self.mac_id1_list = mac_id1_list if mac_id1_list else []
        self.dowebgui = dowebgui
        self.ip = ip
        self.device_found = False
        self.profile_name = profile_name
        self.file_name = file_name
        self.group_name = group_name
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
        self.csv_direction = csv_direction
        self.expected_passfail_val = expected_passfail_val
        self.csv_name = csv_name
        self.wait_time = wait_time
        self.group_device_map = {}
        self.config = config
        self.get_live_view = get_live_view
        self.total_floors = total_floors
        self.qos_data = {}
        self.timebreak = self.parse_timebreak(timebreak)
        self.throughput_data = []
        self.band_steering_df = []
        self.do_bandsteering = do_bandsteering
        self.bssids = bssids.split(",") if bssids else []
        # Normalise client_type — for real only and webgui scenarios user may pass None; treat as Real
        # Alert user can also specify --client_type Real
        if self.client_type is None:
            self.client_type = "Real"

        self.report_ssid_list = []
        self.report_mac_list = []
        self.report_channel_list = []
        self._existing_sta_list = []
        
        # Initializing robot test parameters
        self.robot_test = robot_test
        self.cycles = cycles
        if robot_test:
            if self.dowebgui:
                self.get_live_view = True if not self.do_bandsteering else False
            self.robot_ip = robot_ip
            self.coordinate = coordinate
            self.rotation = rotation
            self.test_stopped_by_user = False
            self.coordinate_list = coordinate.split(',')
            self.rotation_list = rotation.split(',')
            self.current_coordinate = None
            self.current_angle = None
            self.angle_list = angle_list
            self.rotation_enabled = rotation_enabled
            self.robot = RobotClass(robo_ip=self.robot_ip, angle_list=self.angle_list)
            self.last_rotated_angles = []
            self.charge_point_name = None
            self.robot.coordinate_list = self.coordinate_list
            self.robot.time_to_reach = duration_to_skip
            self.robot.total_cycles = cycles

    def os_type(self):
        response = self.json_get("/resource/all")
        for key, value in response.items():
            if key == "resources":
                for element in value:
                    for _a, b in element.items():
                        if "Apple" in b['hw version']:
                            if b['kernel'] == '':
                                self.hw_list.append('iOS')
                            else:
                                self.hw_list.append(b['hw version'])
                        else:
                            self.hw_list.append(b['hw version'])
        for hw_version in self.hw_list:
            if "Win" in hw_version:
                self.windows_list.append(hw_version)
            elif "Linux" in hw_version:
                self.linux_list.append(hw_version)
            elif "Apple" in hw_version:
                self.mac_list.append(hw_version)
            elif "iOS" in hw_version:
                self.mac_list.append(hw_version)
            else:
                if hw_version != "":
                    self.android_list.append(hw_version)
        self.laptop_list = self.windows_list + self.linux_list + self.mac_list

    def phantom_check(self):
        obj = DeviceConfig.DeviceConfig(lanforge_ip=self.host, file_name=self.file_name, wait_time=self.wait_time)
        config_devices = {}
        upstream = self.change_port_to_ip(self.upstream)
        config_dict = {
            'ssid': self.ssid,
            'passwd': self.password,
            'enc': self.security,
            'eap_method': self.eap_method,
            'eap_identity': self.eap_identity,
            'ieee80211': self.ieee80211,
            'ieee80211u': self.ieee80211u,
            'ieee80211w': self.ieee80211w,
            'enable_pkc': self.enable_pkc,
            'bss_transition': self.bss_transition,
            'power_save': self.power_save,
            'disable_ofdma': self.disable_ofdma,
            'roam_ft_ds': self.roam_ft_ds,
            'key_management': self.key_management,
            'pairwise': self.pairwise,
            'private_key': self.private_key,
            'ca_cert': self.ca_cert,
            'client_cert': self.client_cert,
            'pk_passwd': self.pk_passwd,
            'pac_file': self.pac_file,
            'server_ip': upstream,
        }
        # Case 1: Group name, file name, and profile name are provided
        if self.group_name and self.file_name and self.device_list == [] and self.profile_name:
            selected_groups = self.group_name.split(',')
            selected_profiles = self.profile_name.split(',')
            for i in range(len(selected_groups)):
                config_devices[selected_groups[i]] = selected_profiles[i]
            obj.initiate_group()
            self.group_device_map = obj.get_groups_devices(data=selected_groups, groupdevmap=True)
            # Configure devices in the selected group with the selected profile
            self.device_list = asyncio.run(obj.connectivity(config=config_devices, upstream=upstream))
        # Case 2: Device list is already provided
        elif self.device_list != []:
            all_devices = obj.get_all_devices()
            self.device_list = self.device_list.split(',')
            # If config is false, the test will exclude all inactive devices
            if self.config:
                # If config is True, attempt to bring up all devices in the list and perform tests on those that become active
                # Configure devices in the device list with the provided SSID, Password and Security
                self.device_list = asyncio.run(obj.connectivity(device_list=self.device_list, wifi_config=config_dict))
        # Case 3: Device list is empty but config flag is True — prompt the user to input device details for configuration
        elif self.device_list == [] and self.config:
            all_devices = obj.get_all_devices()
            device_list = []
            for device in all_devices:
                if device["type"] == 'laptop':
                    device_list.append(device["shelf"] + '.' + device["resource"] + " " + device["hostname"])
                else:
                    device_list.append(device["eid"] + " " + device["serial"])
            logger.info(f"Available devices: {device_list}")
            self.device_list = input("Enter the desired resources to run the test:").split(',')

            if self.config:
                # Configure devices entered by the user with the provided SSID, Password and Security
                self.device_list = asyncio.run(obj.connectivity(device_list=self.device_list, wifi_config=config_dict))
        port_eid_list, same_eid_list, original_port_list = [], [], []
        response = self.json_get("/resource/all")
        for key, value in response.items():
            if key == "resources":
                for element in value:
                    for _a, b in element.items():
                        if b['phantom'] is False:
                            self.working_resources_list.append(b["hw version"])
                            if "Win" in b['hw version']:
                                self.eid_list.append(b['eid'])
                                self.windows_list.append(b['hw version'])
                                self.devices_available.append(b['eid'] + " " + 'Win' + " " + b['hostname'])
                            elif "Linux" in b['hw version']:
                                if ('ct' not in b['hostname']):
                                    if ('lf' not in b['hostname']):
                                        self.eid_list.append(b['eid'])
                                        self.linux_list.append(b['hw version'])
                                        self.devices_available.append(b['eid'] + " " + 'Lin' + " " + b['hostname'])
                            elif "Apple" in b['hw version']:
                                if b['kernel'] == '':
                                    self.eid_list.append(b['eid'])
                                    self.mac_list.append(b['hw version'])
                                    self.devices_available.append(b['eid'] + " " + 'iOS' + " " + b['hostname'])
                                else:
                                    self.eid_list.append(b['eid'])
                                    self.mac_list.append(b['hw version'])
                                    self.devices_available.append(b['eid'] + " " + 'Mac' + " " + b['hostname'])
                            else:
                                self.eid_list.append(b['eid'])
                                self.android_list.append(b['hw version'])
                                self.devices_available.append(b['eid'] + " " + 'android' + " " + b['user'])

        # All the available resources are fetched from resource mgr tab ----

        response_port = self.json_get("/port/all")

        for interface in response_port['interfaces']:
            for port, port_data in interface.items():
                if (not port_data['phantom'] and not port_data['down'] and port_data['parent dev'] == "wiphy0" and port_data['alias'] != 'p2p0'):
                    for id in self.eid_list:
                        if (id + '.' in port):
                            original_port_list.append(port)
                            port_eid_list.append(str(self.name_to_eid(port)[0]) + '.' + str(self.name_to_eid(port)[1]))
                            self.mac_id1_list.append(str(self.name_to_eid(port)[0]) + '.' + str(self.name_to_eid(port)[1]) + ' ' + port_data['mac'])

        for i in range(len(self.eid_list)):
            for j in range(len(port_eid_list)):
                if self.eid_list[i] == port_eid_list[j]:
                    same_eid_list.append(self.eid_list[i])
        same_eid_list = [_eid + ' ' for _eid in same_eid_list]

        # All the available ports from port manager are fetched from port manager tab ---

        for eid in same_eid_list:
            for device in self.devices_available:
                if eid in device:
                    logger.info(f"{eid} : {device}")
                    if device not in self.user_list:
                        self.user_list.append(device)
        # checking for the availability of selected devices to run test
        obj.adb_obj.get_devices()
        logging.info(self.user_list)
        # Case 4: Config is False, no device list is provided, and no group is selected
        if self.config is False and len(self.device_list) == 0 and self.group_name is None:
            logger.info("AVAILABLE DEVICES TO RUN TEST : {}".format(self.user_list))
            # Prompt the user to manually input devices for running the test
            self.device_list = input("Enter the desired resources to run the test:").split(',')
        if len(self.device_list) == 0:
            devices_list = ""

        if len(self.device_list) != 0:
            devices_list = self.device_list
            available_list = []
            not_available = []
            for input_device in devices_list:
                found = False
                for device in self.devices_available:
                    if input_device + " " in device:
                        available_list.append(input_device)
                        found = True
                        break
                if found is False:
                    not_available.append(input_device)
                    logger.warning(input_device + " is not available to run test")

            if len(available_list) > 0:

                logger.info("Test is initiated on devices: {}".format(available_list))
                devices_list = ','.join(available_list)
                self.device_found = True
            else:
                devices_list = ""
                self.device_found = False
                logger.warning("Test can not be initiated on any selected devices")

        if devices_list == "" or devices_list == ",":
            logger.error("Selected Devices are not available in the lanforge. devices_list: '%s'", devices_list)
            exit(1)
        resource_eid_list = devices_list.split(',')
        logger.info(f"devices list {devices_list}")
        resource_eid_list2 = [eid + ' ' for eid in resource_eid_list]
        resource_eid_list1 = [resource + '.' for resource in resource_eid_list]
        logger.info(f"resource eid list : {resource_eid_list1} - {resource_eid_list2}")

        # User desired eids are fetched ---

        for eid in resource_eid_list1:
            logger.info(f"Original Port : {original_port_list}")
            for ports_m in original_port_list:
                if eid in ports_m:
                    self.input_devices_list.append(ports_m)
        logger.info("INPUT DEVICES LIST {}".format(self.input_devices_list))

        # user desired real client list 1.1 wlan0 ---

        for i in resource_eid_list2:
            for j in range(len(self.user_list)):
                if i in self.user_list[j]:
                    if self.user_list[j] not in self.real_client_list:
                        self.real_client_list.append(self.user_list[j])
                        self.real_client_list1.append((self.user_list[j])[:25])
        logger.info("REAL CLIENT LIST{}".format(self.real_client_list))

        self.num_stations = len(self.real_client_list)

        for eid in resource_eid_list2:
            for i in self.mac_id1_list:          # ['1.11 be:5d:07:76:c8:81', '1.20 30:35:ad:c5:e1:be', '1.23 ca:84:bc:fa:cb:7a']
                if eid in i:
                    self.mac_id_list.append(i.strip(eid + ' '))
        logger.info("MAC ID LIST {}" .format(self.mac_id_list))
        return self.input_devices_list, self.real_client_list, self.mac_id_list, config_devices
        # user desired real client list 1.1 OnePlus, 1.1 Apple for report generation ---

    def start(self, print_pass=False, print_fail=False):
        if len(self.cx_profile.created_cx) > 0:
            for cx in self.cx_profile.created_cx.keys():
                req_url = "cli-json/set_cx_report_timer"
                data = {
                    "test_mgr": "all",
                    "cx_name": cx,
                    "milliseconds": 1000
                }
                self.json_post(req_url, data)
        self.cx_profile.start_cx()

    def change_port_to_ip(self, upstream_port):
        if upstream_port.count('.') != 3:
            target_port_list = self.name_to_eid(upstream_port)
            shelf, resource, port, _ = target_port_list
            try:
                target_port_ip = self.json_get(f'/port/{shelf}/{resource}/{port}?fields=ip')['interface']['ip']
                upstream_port = target_port_ip
            except Exception:
                logging.warning(f'The upstream port is not an ethernet port. Proceeding with the given upstream_port {upstream_port}.')
            logging.info(f"Upstream port IP {upstream_port}")
        else:
            logging.info(f"Upstream port IP {upstream_port}")

        return upstream_port

    def updating_webui_runningjson(self, obj):
        data = {}
        with open(self.result_dir + "/../../Running_instances/{}_{}_running.json".format(self.host, self.test_name),
                  'r') as file:
            data = json.load(file)
            for key in obj:
                data[key] = obj[key]
        with open(self.result_dir + "/../../Running_instances/{}_{}_running.json".format(self.host, self.test_name),
                  'w') as file:
            json.dump(data, file, indent=4)

    def stop(self):
        self.cx_profile.stop_cx()
        self.station_profile.admin_down()

    def pre_cleanup(self):
        """Clean up CX profiles and virtual stations (if any).
        Stations listed in self._existing_sta_list are NOT deleted — they were
        pre-existing and should be left intact.
        """
        self.cx_profile.cleanup_prefix()
        self.cx_profile.cleanup()               # Added this to support throughput_qos script i.e for Virtual Station
        if self.create_sta and self.sta_list:
            existing = set(getattr(self, '_existing_sta_list', []))
            for sta in self.sta_list:
                if sta not in existing:
                    self.rm_port(sta, check_exists=True)

    def cleanup(self):
        self.cx_profile.cleanup()
        existing = set(getattr(self, '_existing_sta_list', []))
        # Only clean up stations that were freshly created by this run —
        # never delete pre-existing stations supplied via --existing_station_list.
        new_stas = [s for s in (self.sta_list or []) if s not in existing]
        if self.create_sta and new_stas:
            original_names = self.station_profile.station_names
            self.station_profile.station_names = new_stas
            self.station_profile.cleanup()
            LFUtils.wait_until_ports_disappear(    # Added this to support throughput_qos script i.e for Virtual Station
                base_url=self.lfclient_url,
                port_list=new_stas,
                debug=self.debug
            )
            self.station_profile.station_names = original_names

    #  build()  –  unified entry point for Real / Virtual / Both
    def create_cx(self):
        if self.client_type in ("Real", "Both"):
            self.create_cx_real()

        if self.client_type in ("Virtual", "Both"):
                self.create_cx_virtual()

    def build(self, client_type="Real"):
        """
        Build cross-connections.

        client_type:
            "Real"    : use real device ports discovered by phantom_check()
            "Virtual" : create virtual stations then build CX
            "Both"    : create virtual stations AND build CX for real devices and virtual stations.
        """

        if self.client_type in ("Virtual", "Both"):
            self.build_virtual_stations()

            # Merge existing stations into sta_list after build_virtual_stations
            existing_stas = getattr(self, '_existing_sta_list', [])
            for eid in existing_stas:
                if eid not in self.sta_list:
                    self.sta_list.append(eid)
            if existing_stas:
                logger.info(
                    f"Final sta_list after merging existing stations "
                    f"({len(existing_stas)} existing + {len(self.sta_list) - len(existing_stas)} new): "
                    f"{self.sta_list}")

        logger.info(f"We are Printing Virtual Stations after build from Station Profile : {self.station_profile.station_names}")

        self.create_cx()  # This method is used to create cross connections using L3CXProfile.

        logger.info(f"We are Printing CX List after the build Method : {list(self.cx_profile.created_cx.keys())}")
        print("cx build finished")

    #  Virtual station creation
    def build_virtual_stations(self):
        """
        Create virtual stations for each band in self.bands.
        """
        bands = self.bands if isinstance(self.bands, list) else self.bands.split(",")

        # This method is written inorder to overcome the band specific virtual station ssid, password and security config miss-match in --client_type Virtual or Both Scenario.
        def first_available():
            for s, p, e in [
                (self.ssid_2g, self.password_2g, self.security_2g),
                (self.ssid_5g, self.password_5g, self.security_5g),
                (self.ssid_6g, self.password_6g, self.security_6g),
            ]:
                if s is not None:
                    return s, p, e
            return self.ssid, self.password, self.security

        def resolve(band_ssid, band_passwd, band_sec):
            if band_ssid is not None:
                return band_ssid, band_passwd, band_sec

            if self.ssid is not None:
                return self.ssid, self.password, self.security

            return first_available()

        def station_count(specific):
            if specific and specific > 0:
                return specific
            for c in [self.num_stations_2g, self.num_stations_5g, self.num_stations_6g]:
                if c and c > 0:
                    return c
            return 0

        for key in bands:
            key = key.strip()
            if not self.create_sta:
                continue

            band_pref = 0

            if key in ("2.4G", "2.4g"):
                count = station_count(self.num_stations_2g)
                if count == 0:
                    logger.warning("2.4G band requested but num_stations_2g=0 - skipping")
                    continue
                ssid, passwd, sec = resolve(self.ssid_2g, self.password_2g, self.security_2g)
                logger.info(f"We are printing band specific ssid,passwd,sec from build() : {ssid} - {passwd} - {sec}")
                self.station_profile.mode = 13
                self.station_profile.use_security(sec, ssid, passwd)
                self.station_profile.set_number_template(self.number_template)
                self.station_profile.set_command_flag("add_sta", "create_admin_down", 1)
                self.station_profile.set_command_param("set_port", "report_timer", 1500)
                self.station_profile.set_command_flag("set_port", "rpt_timer", 1)
                if self.initial_band_pref:
                    band_pref = 2
                self.station_profile.set_wifi_extra2(initial_band_pref=band_pref)
                self.station_profile.create(radio=self.radio_2g, sta_names_=self.sta_list, debug=self.debug)

            elif key in ("5G", "5g"):
                count = station_count(self.num_stations_5g)
                if count == 0:
                    logger.warning("5G band requested but no station count found : skipping")
                    continue
                ssid, passwd, sec = resolve(self.ssid_5g, self.password_5g, self.security_5g)
                logger.info(f"We are printing band specific ssid,passwd,sec from build() : {ssid} - {passwd} - {sec}")
                self.station_profile.mode = 14
                self.station_profile.use_security(sec, ssid, passwd)
                self.station_profile.set_number_template(self.number_template)
                self.station_profile.set_command_flag("add_sta", "create_admin_down", 1)
                self.station_profile.set_command_param("set_port", "report_timer", 1500)
                self.station_profile.set_command_flag("set_port", "rpt_timer", 1)
                if self.initial_band_pref:
                    band_pref = 5
                self.station_profile.set_wifi_extra2(initial_band_pref=band_pref)
                self.station_profile.create(radio=self.radio_5g, sta_names_=self.sta_list, debug=self.debug)

            elif key in ("6G", "6g"):
                count = station_count(self.num_stations_6g)
                if count == 0:
                    logger.warning("6G band requested but no station count found : skipping")
                    continue
                ssid, passwd, sec = resolve(self.ssid_6g, self.password_6g, self.security_6g)
                logger.info(f"We are printing band specific ssid,passwd,sec from build() : {ssid} - {passwd} - {sec}")
                self.station_profile.mode = 15
                self.station_profile.use_security(sec, ssid, passwd)
                self.station_profile.set_number_template(self.number_template)
                self.station_profile.set_command_flag("add_sta", "create_admin_down", 1)
                self.station_profile.set_command_param("set_port", "report_timer", 1500)
                self.station_profile.set_command_flag("set_port", "rpt_timer", 1)
                if self.initial_band_pref:
                    band_pref = 6
                self.station_profile.set_wifi_extra2(initial_band_pref=band_pref)
                self.station_profile.create(radio=self.radio_6g, sta_names_=self.sta_list, debug=self.debug)

            elif key in ("dualband", "DUALBAND"):
                split = len(self.sta_list) // 2
                # 2.4 GHz half
                ssid, passwd, sec = resolve(self.ssid_2g, self.password_2g, self.security_2g)
                logger.info(f"We are printing band specific ssid,passwd,sec from build() : {ssid} - {passwd} - {sec}")
                self.station_profile.use_security(sec, ssid, passwd)
                self.station_profile.mode = 13
                self.station_profile.set_number_template(self.number_template)
                self.station_profile.set_command_flag("add_sta", "create_admin_down", 1)
                self.station_profile.set_command_param("set_port", "report_timer", 1500)
                self.station_profile.set_command_flag("set_port", "rpt_timer", 1)
                if self.initial_band_pref:
                    band_pref = 2
                self.station_profile.set_wifi_extra2(initial_band_pref=band_pref)
                self.station_profile.create(radio=self.radio_2g, sta_names_=self.sta_list[:split], debug=self.debug)
                # 5 GHz half
                ssid, passwd, sec = resolve(self.ssid_5g, self.password_5g, self.security_5g)
                logger.info(f"We are printing band specific ssid,passwd,sec from build() : {ssid} - {passwd} - {sec}")
                self.station_profile.use_security(sec, ssid, passwd)
                self.station_profile.mode = 14
                self.station_profile.set_number_template(self.number_template)
                self.station_profile.set_command_flag("add_sta", "create_admin_down", 1)
                self.station_profile.set_command_param("set_port", "report_timer", 1500)
                self.station_profile.set_command_flag("set_port", "rpt_timer", 1)
                if self.initial_band_pref:
                    band_pref = 5
                self.station_profile.set_wifi_extra2(initial_band_pref=band_pref)
                self.station_profile.create(radio=self.radio_5g, sta_names_=self.sta_list[split:], debug=self.debug)

            elif key in ("triband", "TRIBAND"):
                split_1 = len(self.sta_list) // 3
                split_2 = 2 * split_1
                # 2.4 GHz
                ssid, passwd, sec = resolve(self.ssid_2g, self.password_2g, self.security_2g)
                logger.info(f"We are printing band specific ssid,passwd,sec from build() : {ssid} - {passwd} - {sec}")
                self.station_profile.use_security(sec, ssid, passwd)
                self.station_profile.mode = 13
                self.station_profile.set_number_template(self.number_template)
                self.station_profile.set_command_flag("add_sta", "create_admin_down", 1)
                self.station_profile.set_command_param("set_port", "report_timer", 1500)
                self.station_profile.set_command_flag("set_port", "rpt_timer", 1)
                if self.initial_band_pref:
                    band_pref = 2
                self.station_profile.set_wifi_extra2(initial_band_pref=band_pref)
                self.station_profile.create(radio=self.radio_2g, sta_names_=self.sta_list[:split_1], debug=self.debug)
                # 5 GHz
                ssid, passwd, sec = resolve(self.ssid_5g, self.password_5g, self.security_5g)
                logger.info(f"We are printing band specific ssid,passwd,sec from build() : {ssid} - {passwd} - {sec}")
                self.station_profile.use_security(sec, ssid, passwd)
                self.station_profile.mode = 14
                self.station_profile.set_number_template(self.number_template)
                self.station_profile.set_command_flag("add_sta", "create_admin_down", 1)
                self.station_profile.set_command_param("set_port", "report_timer", 1500)
                self.station_profile.set_command_flag("set_port", "rpt_timer", 1)
                if self.initial_band_pref:
                    band_pref = 5
                self.station_profile.set_wifi_extra2(initial_band_pref=band_pref)
                self.station_profile.create(radio=self.radio_5g, sta_names_=self.sta_list[split_1:split_2], debug=self.debug)
                # 6 GHz
                ssid, passwd, sec = resolve(self.ssid_6g, self.password_6g, self.security_6g)
                logger.info(f"We are printing band specific ssid,passwd,sec from build() : {ssid} - {passwd} - {sec}")
                self.station_profile.use_security(sec, ssid, passwd)
                self.station_profile.mode = 15
                self.station_profile.set_number_template(self.number_template)
                self.station_profile.set_command_flag("add_sta", "create_admin_down", 1)
                self.station_profile.set_command_param("set_port", "report_timer", 1500)
                self.station_profile.set_command_flag("set_port", "rpt_timer", 1)
                if self.initial_band_pref:
                    band_pref = 6
                self.station_profile.set_wifi_extra2(initial_band_pref=band_pref)
                self.station_profile.create(radio=self.radio_6g, sta_names_=self.sta_list[split_2:], debug=self.debug)
            else:
                print(f"Band '{key}' not recognised : skipping station creation for this band.")
                continue

            # Bring all stations up and wait for IPs
            self.station_profile.admin_up()
            temp_stations = self.station_profile.station_names.copy()
            if self.wait_for_ip(temp_stations):
                self._pass("All virtual stations got IPs")
            else:
                self._fail("Virtual stations failed to get IPs")
                self.exit_fail()

        # Existing stations (--use_existing_station_list) have already been validated 
        # to exist and have IPs in validate_existing_stations(). We intentionally do 
        # NOT admin_up() them here to avoid altering their existing configuration.

        # Collect MAC and channel info for virtual stations
        response_port = self.json_get("/port/all")
        for sta in self.sta_list:
            found = False
            for interface in response_port['interfaces']:
                for port, port_data in interface.items():
                    if sta in port:
                        self.mac_list.append(port_data.get('mac', ''))
                        self.channel_list.append(port_data.get('channel', ''))
                        found = True
                        break
                if found:
                    break

    #  CX creation for Real device

    def create_cx_real(self):
        direction = ''
        if (int(self.cx_profile.side_b_min_bps)) != 0 and (int(self.cx_profile.side_a_min_bps)) != 0:
            self.direction = "Bi-direction"
            direction = 'Bi-di'
        elif int(self.cx_profile.side_b_min_bps) != 0:
            self.direction = "Download"
            direction = 'DL'
        else:
            if int(self.cx_profile.side_a_min_bps) != 0:
                self.direction = "Upload"
                direction = 'UL'

        logger.info(f"Direction : {self.direction}")
        print("Real_Client_List : ", self.real_client_list)
        traffic_type = (self.traffic_type.strip("lf_")).upper()
        traffic_direction_list, cx_list, traffic_type_list = [], [], []
        for _client in range(len(self.real_client_list)):
            traffic_direction_list.append(direction)
            traffic_type_list.append(traffic_type)
        logger.info("tos: {}".format(self.tos))

        for ip_tos in self.tos:
            for i in self.real_client_list1:
                for j in traffic_direction_list:
                    for k in traffic_type_list:
                        sta_name = i.split('.')[-1] if i.count('.') >= 2 else i
                        cxs = "%s_%s_%s_%s" % (sta_name, k, j, ip_tos)
                        cx_names = cxs.replace(" ", "")
                cx_list.append(cx_names)
        logger.info('cx_list {}'.format(cx_list))
        count = 0
        for ip_tos in range(len(self.tos)):
            for device in range(len(self.input_devices_list)):
                logger.info("## ip_tos: {}".format(ip_tos))
                logger.info("Creating connections for endpoint type: %s TOS: %s  cx-count: %s" % (
                    self.traffic_type, self.tos[ip_tos], self.cx_profile.get_cx_count()))
                print("Creating CX for real device port:", self.input_devices_list[device])
                self.cx_profile.create(
                    endp_type=self.traffic_type,
                    side_a=[self.input_devices_list[device]],
                    side_b=self.upstream,
                    sleep_time=0,
                    tos=self.tos[ip_tos],
                    cx_name="%s-%i" % (cx_list[count], len(self.cx_profile.created_cx))
                )
                count += 1
            logger.info("cross connections with TOS type created.")

    #  CX creation for Virtual stations

    def create_cx_virtual(self):
        """Build CX connections against virtual sta_list entries."""
        direction = ''
        if int(self.cx_profile.side_b_min_bps) != 0 and int(self.cx_profile.side_a_min_bps) != 0:
            self.direction = "Bi-direction"
            direction = 'Bi-di'
        elif int(self.cx_profile.side_b_min_bps) != 0:
            self.direction = "Download"
            direction = 'DL'
        else:
            if int(self.cx_profile.side_a_min_bps) != 0:
                self.direction = "Upload"
                direction = 'UL'

        print("Direction (virtual):", self.direction)
        traffic_type = (self.traffic_type.strip("lf_")).upper()
        traffic_direction_list = [direction] * len(self.sta_list)
        traffic_type_list = [traffic_type] * len(self.sta_list)
        cx_list = []
        for ip_tos in self.tos:
            for i in self.sta_list:
                for j in traffic_direction_list:
                    for k in traffic_type_list:
                        sta_name = i.split('.')[-1] if i.count('.') >= 2 else i
                        cx_names = ("%s_%s_%s_%s" % (sta_name, k, j, ip_tos)).replace(" ", "")
                cx_list.append(cx_names)
        print("Virtual cx_list:", cx_list)

        if len(cx_list) == 0:  # If no cross connects are created , then exit from the test.
            exit(1)
        count = 0
        for ip_tos in range(len(self.tos)):
            for sta in range(len(self.sta_list)):
                print("Creating virtual CX : TOS: %s, sta: %s" % (self.tos[ip_tos], self.sta_list[sta]))
                self.cx_profile.create(
                    endp_type=self.traffic_type,
                    side_a=[self.sta_list[sta]],
                    side_b=self.upstream,
                    sleep_time=0,
                    tos=self.tos[ip_tos],
                    cx_name="%s-%i" % (cx_list[count], len(self.cx_profile.created_cx))
                )
                count += 1
        print("Virtual cross connections with TOS type created.")

    def monitor_cx(self):
        """
        This function waits for up to 20 iterations to allow all CXs (connections) to be created.
        If some CXs are still not created after 20 iterations, then the CXs related to that device are removed,
        along with their associated client and MAC entries from all relevant lists.
        """

        max_retry = 20
        current_retry = 0
        while current_retry < max_retry:
            not_running_cx = []
            overallresponse = self.json_get('/cx/all')  # Get all current CXs from the layer-3 tab

            created_cx_list = list(self.cx_profile.created_cx.keys())
            l3_existing_cx = list(overallresponse.keys())
            count_of_cx = 0
            for created_cxs in created_cx_list:
                if created_cxs in l3_existing_cx:
                    count_of_cx += 1
                else:
                    # Extract base device name (e.g., from '1.16androidsamsunga7_UDP_UL_BE-8' to '1.16androidsamsunga7')
                    # to track the whole device if any TOS-based CX fails.
                    not_running_cx.append(created_cxs.split('_')[0])   # CX was not created
            if count_of_cx == len(created_cx_list):
                break
            logger.info(f"Try {current_retry + 1} out of 20: Waiting for the cross-connection to be created.")
            time.sleep(2)
            current_retry += 1
        cxs_to_remove = set()

        logger.info(f"Not running cx names : {not_running_cx}")
        for cx in self.cx_profile.created_cx:
            for not_created_cx in not_running_cx:
                if not_created_cx in cx:
                    cxs_to_remove.add(cx)

        # Remove each failed CX and delete it from the created CX tracking dictionary.
        for cx in cxs_to_remove:
            logger.info(f"Removing failed CX: {cx}")
            super().rm_cx(cx)
            self.cx_profile.created_cx.pop(cx, None)

        devices_to_be_removed = []
        for item in not_running_cx:
            match = re.match(r'^[0-9.]+', item)
            if match:
                devices_to_be_removed.append(match.group())

        # If there are devices to remove, filter them out from all related client and MAC lists
        # to keep the lists consistent with the currently considered devices.
        if len(devices_to_be_removed) != 0:
            self.real_client_list1 = [item for item in self.real_client_list1 if item.split()[0] not in devices_to_be_removed]
            self.input_devices_list = [item for item in self.input_devices_list if item.split('.')[0] + '.' + item.split('.')[1] not in devices_to_be_removed]
            filtered = [(dev, mac) for dev, mac in zip(self.real_client_list, self.mac_id_list) if dev.split()[0] not in devices_to_be_removed]
            self.real_client_list, self.mac_id_list = zip(*filtered) if filtered else ([], [])
            self.real_client_list = list(self.real_client_list)
            self.mac_id_list = list(self.mac_id_list)
            self.num_stations = len(self.real_client_list)

    def monitor(self, curr_coordinate=None, curr_rotation=None, monitor_charge_time=None,
                runtime_dir="per_client_csv"):
        client_type = getattr(self, "client_type", "Real")

        if (self.test_duration is None) or (int(self.test_duration) <= 1):
            raise ValueError("Monitor test duration should be > 1 second")
        if self.cx_profile.created_cx is None:
            raise ValueError("Monitor needs a list of Layer 3 connections")

        if self.robot_test:
            curr_coordinate = self.current_coordinate

        # ── Initialise overall / df_for_webui only at test start (not per-coord) ─ #
        if not hasattr(self, "overall"):
            self.overall = []
        if not hasattr(self, "df_for_webui"):
            self.df_for_webui = []
        if not hasattr(self, "generated_station_csv_files"):
            self.generated_station_csv_files = []

        cx_list = list(self.cx_profile.created_cx.keys())
        self.real_time_data = {
            cx: {
                t: {'time': [], 'bps rx a': [], 'bps rx b': [],
                    'rx drop % a': [], 'rx drop % b': []}
                for t in ["BE", "BK", "VI", "VO"]
            }
            for cx in cx_list
        }

        start_time = datetime.now()
        test_start_time = datetime.now().strftime("%Y %d %H:%M:%S")
        if not self.do_bandsteering:
            print("Test started at: ", test_start_time)
            print("Monitoring cx and endpoints")
        end_time = start_time + timedelta(seconds=int(self.test_duration))
        if not self.robot_test:
            self.overall = []
            self.df_for_webui = []
        index = -1

        connections_download = {cx: 0.0 for cx in cx_list}
        connections_upload = {cx: 0.0 for cx in cx_list}
        connections_download_avg = {cx: 0.0 for cx in cx_list}
        connections_upload_avg = {cx: 0.0 for cx in cx_list}
        dropa_connections = {cx: 0.0 for cx in cx_list}
        dropb_connections = {cx: 0.0 for cx in cx_list}
        drop_a_per = []
        drop_b_per = []

        avg_dl = defaultdict(list)   # per-CX download Mbps
        avg_ul = defaultdict(list)   # per-CX upload Mbps
        avg_da = defaultdict(list)   # per-CX drop-a %
        avg_db = defaultdict(list)   # per-CX drop-b %
        rates_data = defaultdict(list)   # port-level rx/tx/rssi

        per_client_rows = defaultdict(list)
        sta_rows = {sta: [] for sta in (self.sta_list or [])}
        all_station_rows = []

        individual_device_data = {cx: pd.DataFrame(columns=['bps rx a', 'bps rx b'])
                                  for cx in cx_list}

        webgui_mode = (self.dowebgui == "True")
        webgui_dir = self.result_dir if webgui_mode else ""
        previous_time = datetime.now()
        time_break = 0              # This is webgui incremental timebreak.
        timebreak = getattr(self, "timebreak", None)
        last_write = datetime.now()

        cx_list_endp = []
        for cx in cx_list:
            cx_list_endp.append(cx + '-A')
            cx_list_endp.append(cx + '-B')

        def map_tos(tos_val):
            _map = {
                "100": "BE", 100: "BE",
                "32": "BK", 32: "BK",
                "128": "VI", 128: "VI",
                "192": "VO", 192: "VO",
                "BE": "BE", "BK": "BK", "VI": "VI", "VO": "VO",
            }
            return _map.get(str(tos_val).strip().upper(), "BE")

        def resolve_client_key(cx_name):
            if self.sta_list:
                for sta in self.sta_list:
                    if sta in cx_name:
                        return sta
            m = re.match(r'^(\d+\.\d+)', cx_name)
            return m.group(1) if m else cx_name.split("_")[0]

        logger.info("monitor started (client_type=%s)", client_type)
        while datetime.now() < end_time or getattr(self, "background_run", None):
            if self.robot_test:
                if self.rotation_enabled:
                    if (datetime.now() - monitor_charge_time).total_seconds() >= 300:
                        logger.info("Checking battery status (5-minute interval)...")
                        pause_start = datetime.now()
                        pause = False
                        # Check battery level: if below 20% robot charges fully before resuming
                        pause, test_stopped_by_user = self.robot.wait_for_battery(stop=self.stop)
                        if test_stopped_by_user:
                            break
                        if pause:
                            # Return robot to the last saved coordinate after charging
                            reached = self.robot.move_to_coordinate(curr_coordinate)
                            if not reached:
                                test_stopped_by_user = True
                                break
                            if self.rotation_enabled:
                                # Restore robot's previous orientation before resuming the test
                                rotation_moni = self.robot.rotate_angle(curr_rotation)
                                if not rotation_moni:
                                    test_stopped_by_user = True
                                    break
                            self.start(False, False)
                            pause_end = datetime.now()
                            charge_pause = pause_end - pause_start
                            end_time += charge_pause
                            # overall_end_time += charge_pause
                            previous_time = datetime.now()
                        monitor_charge_time = datetime.now()
            index += 1
            now = datetime.now()
            current_time = now
            # This API Call to get All the running l3 endpoints data.
            try:
                raw_endp_data = self.json_get(
                    '/endp/{}/list?fields=name,rx rate (last),rx drop %25,tos'.format(
                        ','.join(cx_list_endp))
                )
                if raw_endp_data is None or 'endpoint' not in raw_endp_data:
                    logger.warning("Endpoint data query returned None or missing 'endpoint' key. Retrying...")
                    time.sleep(1)
                    continue
                endp_data = list(raw_endp_data['endpoint'])
            except Exception as e:
                logger.error(f"Failed to fetch endpoint data: {e}")
                time.sleep(1)
                continue

            # This API Call to calculate CLient Avg RTT.
            client_rtt = defaultdict(list)
            try:
                cx_resp = self.json_get("/cx/all")
                for cx_name, cx_val in cx_resp.items():
                    if cx_name in ("handler", "uri") or cx_name not in cx_list:
                        continue
                    client_rtt[resolve_client_key(cx_name)].append(
                        float(cx_val.get("avg rtt", 0)))
            except Exception:
                logger.warning("Failed /cx/all : skipping RTT this cycle")

            # This API Call to fetch Port Manager Stats for Run Time CSV'S
            port_stats = {}

            if client_type in ("Real", "Both"):
                try:
                    port_json = self.json_get("/port/all")["interfaces"]
                    for block in port_json:
                        for port, pdata in block.items():
                            if port not in (self.input_devices_list or []):
                                continue
                            eid = ".".join(port.split(".")[:2])
                            rx = pdata.get("rx-rate", 0)
                            tx = pdata.get("tx-rate", 0)
                            rssi = pdata.get("signal", "")
                            mode = pdata.get("mode", "-")
                            channel = pdata.get("channel", "-")
                            bssid = pdata.get("ap", "-")
                            ssid = pdata.get("ssid", "-")
                            port_stats[eid] = {
                                "rx": rx,
                                "tx": tx,
                                "rssi": rssi,
                                "mode": mode,
                                "channel": channel,
                                "bssid": bssid,
                                "ssid": ssid,
                            }
                            rates_data[f"{eid} rx_rate"].append(rx)
                            rates_data[f"{eid} tx_rate"].append(tx)
                            rates_data[f"{eid} RSSI"].append(rssi)
                            rates_data[f"{eid} BSSID"].append(bssid)
                            rates_data[f"{eid} Channel"].append(channel)
                            rates_data[f"{eid} Mode"].append(mode)
                except Exception:
                    logger.warning("Failed /ports/all/ for Real devices")

            if client_type in ("Virtual", "Both"):
                try:
                    port_resp = self.json_get("/port/all")
                    if "interfaces" in port_resp:
                        for iface in port_resp["interfaces"]:
                            for port, pdata in iface.items():
                                for sta in (self.sta_list or []):
                                    if sta in port:
                                        rx = round(pdata.get("bps rx", 0) / 1_000_000, 2)
                                        tx = round(pdata.get("bps tx", 0) / 1_000_000, 2)
                                        rssi = pdata.get("signal", "")
                                        mode = pdata.get("mode", "-")
                                        channel = pdata.get("channel", "-")
                                        bssid = pdata.get("ap", "-")
                                        ssid = pdata.get("ssid", "-")
                                        port_stats[sta] = {
                                            "rx": rx,
                                            "tx": tx,
                                            "rssi": rssi,
                                            "mode": mode,
                                            "channel": channel,
                                            "bssid": bssid,
                                            "ssid": ssid,
                                        }
                                        rates_data[f"{sta} rx_rate"].append(rx)
                                        rates_data[f"{sta} tx_rate"].append(tx)
                                        rates_data[f"{sta} RSSI"].append(rssi)
                                        rates_data[f"{sta} BSSID"].append(bssid)
                                        rates_data[f"{sta} Channel"].append(channel)
                                        rates_data[f"{sta} Mode"].append(mode)
                except Exception as e:
                    logger.warning(f"Failed /port/all for Virtual stations: {e}")

            # We will t_response for webgui monitoring.
            # t_response[cx] = [rx_a_bps, rx_b_bps, drop_a, drop_b]
            t_response = {cx: [0, 0, 0.0, 0.0] for cx in cx_list}

            qos_map = defaultdict(lambda: {
                "BE_dl": 0, "BE_ul": 0,
                "BK_dl": 0, "BK_ul": 0,
                "VI_dl": 0, "VI_ul": 0,
                "VO_dl": 0, "VO_ul": 0,
            })

            for ep in endp_data:
                ep_name, ep_val = list(ep.items())[0]
                side = ep_name[-1]       # "A" or "B"
                cx_name = ep_name[:-2]      # strip "-A" / "-B"

                if cx_name not in cx_list:
                    continue

                tos = map_tos(ep_val.get("tos", ""))
                rx = ep_val.get("rx rate (last)", 0)          # bps (raw)
                rx_mbps = rx / 1_000_000
                drop = ep_val.get("rx drop %", 0)
                t_now = now.strftime("%H:%M:%S")

                if side == "A":
                    avg_dl[cx_name].append(rx_mbps)
                    avg_da[cx_name].append(drop)
                    self.real_time_data[cx_name][tos]['bps rx a'].append(rx_mbps)
                    self.real_time_data[cx_name][tos]['rx drop % a'].append(drop)
                    self.real_time_data[cx_name][tos]['bps rx b'].append(0)
                    self.real_time_data[cx_name][tos]['rx drop % b'].append(0)
                    self.real_time_data[cx_name][tos]['time'].append(t_now)
                    t_response[cx_name][0] = rx    # raw bps for individual_device_data
                    t_response[cx_name][2] = drop
                else:
                    avg_ul[cx_name].append(rx_mbps)
                    avg_db[cx_name].append(drop)
                    self.real_time_data[cx_name][tos]['bps rx b'].append(rx_mbps)
                    self.real_time_data[cx_name][tos]['rx drop % b'].append(drop)
                    self.real_time_data[cx_name][tos]['bps rx a'].append(0)
                    self.real_time_data[cx_name][tos]['rx drop % a'].append(0)
                    self.real_time_data[cx_name][tos]['time'].append(t_now)
                    t_response[cx_name][1] = rx    # raw bps for individual_device_data
                    t_response[cx_name][3] = drop

                client_name = resolve_client_key(cx_name)
                col = f"{tos}_{'dl' if side == 'A' else 'ul'}"
                if col in qos_map[client_name]:
                    qos_map[client_name][col] = rx_mbps

            # Aggregate across all clients to get per-TOS totals
            client_avg_rtt = {
                cn: (sum(rtts) / len(rtts) if rtts else 0)
                for cn, rtts in client_rtt.items()
            }

            time_difference = abs(end_time - now)
            total_hours = time_difference.total_seconds() / 3600
            remaining_minutes = (total_hours % 1) * 60
            remaining_str = (
                str(int(total_hours)) + " hr and " + str(int(remaining_minutes)) + " min"
                if int(total_hours) != 0 or int(remaining_minutes) != 0 else '<1 min'
            )

            # Sum across all clients for the overall QoS row
            overall_row = {
                k: round(sum(v[k] for v in qos_map.values()), 2)
                for k in ["BE_dl", "BE_ul", "BK_dl", "BK_ul",
                          "VI_dl", "VI_ul", "VO_dl", "VO_ul"]
            }
            # Map to the direction-keyed names used by self.overall and dowebgui
            overall_entry = {
                "BE_dl": overall_row["BE_dl"],
                "BE_ul": overall_row["BE_ul"],
                "BK_dl": overall_row["BK_dl"],
                "BK_ul": overall_row["BK_ul"],
                "VI_dl": overall_row["VI_dl"],
                "VI_ul": overall_row["VI_ul"],
                "VO_dl": overall_row["VO_dl"],
                "VO_ul": overall_row["VO_ul"],
                "timestamp": now.strftime("%d/%m %I:%M:%S %p"),
                "start_time": start_time.strftime("%d/%m %I:%M:%S %p"),
                "end_time": end_time.strftime("%d/%m %I:%M:%S %p"),
                "remaining_time": remaining_str,
                "status": "Running",
            }

            # Appending current angle if rotation is enabled for the robot test
            if self.robot_test and self.rotation_enabled:
                overall_entry["angle"] = self.current_angle

            # Append latest port-level rates (rx_rate, tx_rate, RSSI, BSSID, Channel, Mode)
            for client_name, client_stats in rates_data.items():
                if client_stats:
                    overall_entry[client_name] = client_stats[-1]   # Upto here it supports overrall_csv for Real / Virtual / Both Scenario.

            if self.do_bandsteering:
                try:
                    robot_x, robot_y, prev_coord, nex_coord = self.robot.get_robot_pose()
                    overall_entry["robot_x"] = robot_x
                    overall_entry["robot_y"] = robot_y
                    overall_entry["from_coordinate"] = prev_coord
                    overall_entry["to_coordinate"] = nex_coord
                except Exception:
                    pass

            # Appending the data according to the time gap (for webgui)
            if not self.do_bandsteering and self.dowebgui and (current_time - previous_time).total_seconds() >= time_break:
                self.df_for_webui.append(overall_entry)
                previous_time = current_time

            # Append per-client RTT to the overall entry
            for client_name, avg_rtt in client_avg_rtt.items():
                overall_entry[f"{client_name} avg_rtt"] = round(avg_rtt, 2)

            self.overall.append(overall_entry)
            all_station_rows.append(overall_entry)

            # Bandsteering: accumulate band_steering_df and return after one iteration
            if getattr(self, "do_bandsteering", False):
                self.band_steering_df.append(overall_entry)
                df_bs = pd.DataFrame(self.band_steering_df)
                df_bs.to_csv('overall_throughput.csv', index=False)
                self.throughput_data.append({
                    cx: [t_response[cx][0], t_response[cx][1],
                         t_response[cx][2], t_response[cx][3]]
                    for cx in cx_list
                })
                return df_bs

            if webgui_mode and self.dowebgui:
                if not self.do_bandsteering:
                    for key, value in t_response.items():
                        row_data = [value[0], value[1]]
                        individual_device_data[key].loc[len(individual_device_data[key])] = row_data
                    for port, df in individual_device_data.items():
                        df.to_csv(f"{webgui_dir}/{port}.csv", index=False)
                    df1 = pd.DataFrame(self.df_for_webui)
                if not self.robot_test:
                    df1.to_csv('{}/overall_throughput.csv'.format(webgui_dir), index=False)
                else:
                    df1.to_csv('{}/overall_throughput_{}.csv'.format(webgui_dir, curr_coordinate), index=False)
                try:
                    with open(webgui_dir + "/../../Running_instances/{}_{}_running.json".format(self.ip, self.test_name), 'r') as file:
                        _run_data = json.load(file)
                        if _run_data.get("status") != "Running":
                            self.test_stopped_by_user = True
                            logger.warning('Test is stopped by the user')
                            if self.do_bandsteering:
                                df = pd.DataFrame(self.band_steering_df)
                                # *******
                                return df
                            break
                except Exception:
                    pass
                _elapsed = now - start_time
                if _elapsed <= timedelta(hours=1):
                    time_break = 5
                elif _elapsed <= timedelta(hours=6):
                    time_break = 5 if (end_time - now) < timedelta(seconds=10) else 10
                elif _elapsed <= timedelta(hours=12):
                    time_break = 5 if (end_time - now) < timedelta(seconds=30) else 30
                elif _elapsed <= timedelta(hours=24):
                    time_break = 5 if (end_time - now) < timedelta(seconds=60) else 60
                elif _elapsed <= timedelta(hours=48):
                    time_break = 5 if (end_time - now) < timedelta(seconds=60) else 90
                else:
                    time_break = 5 if (end_time - now) < timedelta(seconds=120) else 120
            else:
                if self.do_bandsteering:
                    df1 = pd.DataFrame(self.band_steering_df)
                    df1.to_csv('overall_throughput.csv', index=False)
                time_break = 1

            write_now = True
            if timebreak:
                try:
                    if (now - last_write).total_seconds() < int(timebreak):
                        write_now = False
                except Exception:
                    write_now = True

            if write_now:
                last_write = now
                for client_name, qrow in qos_map.items():
                    ps = port_stats.get(client_name)
                    if ps is None and self.sta_list:
                        for full_sta in self.sta_list:
                            if full_sta.endswith(client_name) or client_name in full_sta:
                                ps = port_stats.get(full_sta)
                                if ps is not None:
                                    break
                    if ps is None:
                        ps = {"rx": 0, "tx": 0, "rssi": 0,
                              "mode": "-", "channel": "-", "bssid": "-"}
                    row = {
                        **qrow,
                        f"{client_name} avg_rtt": round(client_avg_rtt.get(client_name, 0), 2),
                        "timestamp": now.strftime("%H:%M:%S"),
                        "start_time": start_time.strftime("%H:%M:%S"),
                        "end_time": end_time.strftime("%H:%M:%S"),
                        "remaining_time": str(end_time - now).split(".")[0],
                        "status": "Running",
                        f"{client_name} rx_rate": ps["rx"],
                        f"{client_name} tx_rate": ps["tx"],
                        f"{client_name} RSSI": ps["rssi"],
                        f"{client_name} Mode": ps["mode"],
                        f"{client_name} Channel": ps["channel"],
                        f"{client_name} BSSID": ps["bssid"],
                    }
                    per_client_rows[client_name].append(row)
                    if client_name in sta_rows:
                        sta_rows[client_name].append(row)

            time.sleep(1)
        # This is for Robo from WebGui
        if self.robot_test and webgui_mode and self.df_for_webui:
            last_e = self.df_for_webui[-1].copy()
            last_e["status"] = "Stopped"
            last_e["timestamp"] = datetime.now().strftime("%d/%m %I:%M:%S %p")
            last_e["remaining_time"] = "0"
            last_e["end_time"] = last_e["timestamp"]
            self.df_for_webui.append(last_e)
            df1 = pd.DataFrame(self.df_for_webui)
            df1.to_csv('{}/overall_throughput_{}.csv'.format(runtime_dir, curr_coordinate), index=False)

        # This is for Normal WebGui QOS Test.
        if not self.robot_test and webgui_mode and self.df_for_webui:
            last_e = self.df_for_webui[-1].copy()
            last_e["status"] = "Stopped"
            last_e["timestamp"] = datetime.now().strftime("%d/%m %I:%M:%S %p")
            last_e["remaining_time"] = "0"
            last_e["end_time"] = last_e["timestamp"]
            self.df_for_webui.append(last_e)
            pd.DataFrame(self.df_for_webui).to_csv(
                '{}/overall_throughput.csv'.format(webgui_dir), index=False)

        for cx in cx_list:
            if avg_dl[cx]:
                connections_download[cx] = sum(avg_dl[cx]) / len(avg_dl[cx])
                connections_download_avg[cx] = connections_download[cx]
            if avg_ul[cx]:
                connections_upload[cx] = sum(avg_ul[cx]) / len(avg_ul[cx])
                connections_upload_avg[cx] = connections_upload[cx]
            if avg_da[cx]:
                dropa_connections[cx] = sum(avg_da[cx]) / len(avg_da[cx])
            if avg_db[cx]:
                dropb_connections[cx] = sum(avg_db[cx]) / len(avg_db[cx])

        for cx in cx_list:
            drop_a_per.append(dropa_connections[cx])
            drop_b_per.append(dropb_connections[cx])

        # Generate individual client/station CSVs for all client types
        for client_name, rows in per_client_rows.items():
            if not rows:
                continue
            fname = os.path.abspath(f"{client_name}_overall_throughput.csv")
            with open(fname, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            print(f"Generated: {fname}")
            self.generated_station_csv_files.append(fname)

        logger.info("connections download {}".format(connections_download))
        logger.info("connections {}".format(connections_upload))
        self.connections_download = connections_download
        self.connections_upload = connections_upload
        self.drop_a_per = drop_a_per
        self.drop_b_per = drop_b_per

        return (
            connections_download,
            connections_upload,
            drop_a_per,
            drop_b_per,
            connections_download_avg,
            connections_upload_avg,
            dropa_connections,
            dropb_connections,
        )

    def evaluate_qos(self, connections_download, connections_upload, drop_a_per, drop_b_per):
        case_upload = ""
        case_download = ""

        tos_download = {'VI': [], 'VO': [], 'BK': [], 'BE': []}
        tx_b_download = {'BK': [], 'BE': [], 'VI': [], 'VO': []}
        rx_a_download = {'BK': [], 'BE': [], 'VI': [], 'VO': []}
        tx_endps_download = {}
        rx_endps_download = {}

        tos_upload = {'VI': [], 'VO': [], 'BK': [], 'BE': []}
        tx_b_upload = {'BK': [], 'BE': [], 'VI': [], 'VO': []}
        rx_a_upload = {'BK': [], 'BE': [], 'VI': [], 'VO': []}
        tx_endps_upload = {}
        rx_endps_upload = {}

        delay = {'BK': [], 'BE': [], 'VI': [], 'VO': []}

        tos_drop_dict = {'rx_drop_a': {'BK': [], 'BE': [], 'VI': [], 'VO': []},
                         'rx_drop_b': {'BK': [], 'BE': [], 'VI': [], 'VO': []}}

        if int(self.cx_profile.side_b_min_bps) != 0:
            case_download = str(int(self.cx_profile.side_b_min_bps) / 1000000)
        if int(self.cx_profile.side_a_min_bps) != 0:
            case_upload = str(int(self.cx_profile.side_a_min_bps) / 1000000)

        key_upload = case_upload + " Mbps"
        key_download = case_download + " Mbps"

        if len(self.cx_profile.created_cx) == 0:
            print("no RX values available to evaluate QOS")
            return {key_download: tos_download}, {key_upload: tos_upload}, {"drop_per": tos_drop_dict}

        endp_data = self.json_get('endp/all?fields=name,tx+pkts+ll,rx+pkts+ll,delay,tos')
        endp_data.pop("handler", None)
        endp_data.pop("uri", None)

        if 'endpoint' not in endp_data:
            logging.warning('evaluate_qos: malformed /endp/all response — returning empty QoS')
            return {key_download: tos_download}, {key_upload: tos_upload}, {"drop_per": tos_drop_dict}

        endps = endp_data['endpoint']
        for endp in endps:
            ename = list(endp.keys())[0]
            if ename.endswith('-A'):
                rx_endps_download.update(endp)   # side A receives download → rx_download
                rx_endps_upload.update(endp)      # also needed for upload loss calc
            elif ename.endswith('-B'):
                tx_endps_download.update(endp)   # side B transmits download → tx_download
                tx_endps_upload.update(endp)      # side B receives upload   → tx_upload

        # Per-CX accumulation loop
        counter = 0
        for sta in self.cx_profile.created_cx.keys():
            raw_tos = sta.rsplit('-', 1)[0].split('_')[-1]
            current_tos = raw_tos if raw_tos in ('BK', 'BE', 'VI', 'VO') else ''

            if int(self.cx_profile.side_b_min_bps) != 0:
                try:
                    tos_download[current_tos].append(connections_download.get(sta, 0.0))

                    tos_drop_dict['rx_drop_a'][current_tos].append(drop_a_per[counter] if counter < len(drop_a_per) else 0.0)

                    tx_b_download[current_tos].append(int(tx_endps_download.get('%s-B' % sta, {}).get('tx pkts ll', 0)))
                    rx_a_download[current_tos].append(int(rx_endps_download.get('%s-A' % sta, {}).get('rx pkts ll', 0)))

                    delay[current_tos].append(rx_endps_download.get('%s-A' % sta, {}).get('delay', 0))

                except Exception:
                    logger.info('%s: endpoint not found in download evaluation', sta)
                    tos_download[current_tos].append(0.0)
                    tos_drop_dict['rx_drop_a'][current_tos].append(0.0)
                    tx_b_download[current_tos].append(0)
                    rx_a_download[current_tos].append(0)
                    delay[current_tos].append(0)

            if int(self.cx_profile.side_a_min_bps) != 0:
                try:
                    tos_upload[current_tos].append(connections_upload.get(sta, 0.0))

                    tos_drop_dict['rx_drop_b'][current_tos].append(drop_b_per[counter] if counter < len(drop_b_per) else 0.0)

                    tx_b_upload[current_tos].append(int(tx_endps_upload.get('%s-B' % sta, {}).get('tx pkts ll', 0)))
                    rx_a_upload[current_tos].append(int(rx_endps_upload.get('%s-A' % sta, {}).get('rx pkts ll', 0)))

                except Exception:
                    logger.info('%s: endpoint not found in upload evaluation', sta)
                    tos_upload[current_tos].append(0.0)
                    tos_drop_dict['rx_drop_b'][current_tos].append(0.0)
                    tx_b_upload[current_tos].append(0)
                    rx_a_upload[current_tos].append(0)

            counter += 1

        # ── Packet-loss helper
        # Handles three cases: tx > rx (normal loss), tx < rx (reordering
        # counting artifact), and both zero (no traffic).
        def _loss_pct(tx_list, rx_list):
            tx_s = sum(tx_list)
            rx_s = sum(rx_list)
            if tx_s == 0 and rx_s == 0:
                return 0.0
            if tx_s > rx_s:
                return float(f"{((tx_s - rx_s) / tx_s) * 100:.2f}")
            else:
                return float(f"{((rx_s - tx_s) / rx_s) * 100:.2f}") if rx_s else 0.0

        if int(self.cx_profile.side_b_min_bps) != 0:
            tos_download.update({
                "bkQOS": float(f"{sum(tos_download['BK']):.2f}"),
                "beQOS": float(f"{sum(tos_download['BE']):.2f}"),
                "videoQOS": float(f"{sum(tos_download['VI']):.2f}"),
                "voiceQOS": float(f"{sum(tos_download['VO']):.2f}"),
                # Delay sums — per-TOS - similar to throughput.qos delay logic
                "bkDELAY": sum(delay['BK']),
                "beDELAY": sum(delay['BE']),
                "videoDELAY": sum(delay['VI']),
                "voiceDELAY": sum(delay['VO']),
                # Packet-level loss %
                "bkLOSS": _loss_pct(tx_b_download['BK'], rx_a_download['BK']),
                "beLOSS": _loss_pct(tx_b_download['BE'], rx_a_download['BE']),
                "videoLOSS": _loss_pct(tx_b_download['VI'], rx_a_download['VI']),
                "voiceLOSS": _loss_pct(tx_b_download['VO'], rx_a_download['VO']),
                # Raw packet lists (used by generate_individual_graph tables)
                'tx_b': tx_b_download,
                'rx_a': rx_a_download,
            })

        if int(self.cx_profile.side_a_min_bps) != 0:
            tos_upload.update({
                "bkQOS": float(f"{sum(tos_upload['BK']):.2f}"),
                "beQOS": float(f"{sum(tos_upload['BE']):.2f}"),
                "videoQOS": float(f"{sum(tos_upload['VI']):.2f}"),
                "voiceQOS": float(f"{sum(tos_upload['VO']):.2f}"),
                # Packet-level loss % for upload direction
                "bkLOSS": _loss_pct(tx_b_upload['BK'], rx_a_upload['BK']),
                "beLOSS": _loss_pct(tx_b_upload['BE'], rx_a_upload['BE']),
                "videoLOSS": _loss_pct(tx_b_upload['VI'], rx_a_upload['VI']),
                "voiceLOSS": _loss_pct(tx_b_upload['VO'], rx_a_upload['VO']),
                'tx_b': tx_b_upload,
                'rx_a': rx_a_upload,
            })

        return {key_download: tos_download}, {key_upload: tos_upload}, {"drop_per": tos_drop_dict}

    def set_report_data(self, data):
        client_type = getattr(self, 'client_type', 'Real')
        if client_type == 'Virtual':
            return self.set_report_data_virtual(data)
        rate_down = str(str(int(self.cx_profile.side_b_min_bps) / 1000000) + ' ' + 'Mbps')
        rate_up = str(str(int(self.cx_profile.side_a_min_bps) / 1000000) + ' ' + 'Mbps')
        res = {}
        if data is not None:
            res.update(data)
        else:
            print("No Data found to generate report!")
            exit(1)
        table_df = {}
        graph_df = {}
        download_throughput, upload_throughput = [], []
        upload_throughput_df, download_throughput_df = [[], [], [], []], [[], [], [], []]
        if int(self.cx_profile.side_a_min_bps) != 0:
            print(res['test_results'][0][1])
            upload_throughput.append(
                "BK : {}, BE : {}, VI: {}, VO: {}".format(res['test_results'][0][1][rate_up]["bkQOS"],
                                                          res['test_results'][0][1][rate_up]["beQOS"],
                                                          res['test_results'][0][1][rate_up]["videoQOS"],
                                                          res['test_results'][0][1][rate_up]["voiceQOS"]))
            upload_throughput_df[0].append(res['test_results'][0][1][rate_up]['bkQOS'])
            upload_throughput_df[1].append(res['test_results'][0][1][rate_up]['beQOS'])
            upload_throughput_df[2].append(res['test_results'][0][1][rate_up]['videoQOS'])
            upload_throughput_df[3].append(res['test_results'][0][1][rate_up]['voiceQOS'])
            table_df.update({"No of Stations": []})
            table_df.update({"Throughput for Load {}".format(rate_up + "-upload"): []})
            graph_df.update({rate_up: upload_throughput_df})
            n_both = (len(self.input_devices_list) + len(self.sta_list)) if client_type == 'Both' else len(self.input_devices_list)
            table_df.update({"No of Stations": str(n_both)})
            table_df["Throughput for Load {}".format(rate_up + "-upload")].append(upload_throughput[0])
            res_copy = copy.copy(res)
            res_copy.update({"throughput_table_df": table_df})
            res_copy.update({"graph_df": graph_df})
        if int(self.cx_profile.side_b_min_bps) != 0:
            print(res['test_results'][0][0])
            download_throughput.append(
                "BK : {}, BE : {}, VI: {}, VO: {}".format(res['test_results'][0][0][rate_down]["bkQOS"],
                                                          res['test_results'][0][0][rate_down]["beQOS"],
                                                          res['test_results'][0][0][rate_down]["videoQOS"],
                                                          res['test_results'][0][0][rate_down]["voiceQOS"]))
            download_throughput_df[0].append(res['test_results'][0][0][rate_down]['bkQOS'])
            download_throughput_df[1].append(res['test_results'][0][0][rate_down]['beQOS'])
            download_throughput_df[2].append(res['test_results'][0][0][rate_down]['videoQOS'])
            download_throughput_df[3].append(res['test_results'][0][0][rate_down]['voiceQOS'])
            table_df.update({"No of Stations": []})
            table_df.update({"Throughput for Load {}".format(rate_down + "-download"): []})
            graph_df.update({rate_down + "download": download_throughput_df})
            n_both = (len(self.input_devices_list) + len(self.sta_list)) if client_type == 'Both' else len(self.input_devices_list)
            table_df.update({"No of Stations": str(n_both)})
            table_df["Throughput for Load {}".format(rate_down + "-download")].append(download_throughput[0])
            res_copy = copy.copy(res)
            res_copy.update({"throughput_table_df": table_df})
            res_copy.update({"graph_df": graph_df})
        return res_copy

    def set_report_data_virtual(self, data):
        rate_down = str(str(int(self.cx_profile.side_b_min_bps) / 1000000) + ' ' + 'Mbps')
        rate_up = str(str(int(self.cx_profile.side_a_min_bps) / 1000000) + ' ' + 'Mbps')
        if data is None:
            print("No Data found to generate report!")
            exit(1)
        res = {}
        res.update(data)

        table_df = {}
        graph_df = {}
        upload_throughput_df = [[], [], [], []]
        download_throughput_df = [[], [], [], []]
        upload_throughput = []
        download_throughput = []
        num_stations = []
        res_copy = copy.copy(res)

        test_cases = list(self.test_case) if self.test_case else []

        for case in test_cases:
            case = case.strip()
            # Determine station count label for this band
            if case in ("2.4g", "2.4G"):
                num_stations.append(str(len(self.sta_list)))
            elif case in ("5g", "5G"):
                num_stations.append(str(len(self.sta_list)))
            elif case in ("6g", "6G"):
                num_stations.append(str(len(self.sta_list)))
            elif case in ("dualband", "DUALBAND"):
                half = len(self.sta_list) // 2
                num_stations.append("{} + {}".format(half, half))
            elif case in ("triband", "TRIBAND"):
                s = len(self.sta_list) // 3
                num_stations.append("{} + {} + {}".format(s, s, len(self.sta_list) - 2 * s))
            else:
                num_stations.append(str(len(self.sta_list)))

            if int(self.cx_profile.side_a_min_bps) != 0:
                for _ in res[case]['test_results'][0][1]:
                    upload_throughput.append(
                        "BK : {}, BE : {}, VI: {}, VO: {}".format(
                            res[case]['test_results'][0][1][rate_up]["bkQOS"],
                            res[case]['test_results'][0][1][rate_up]["beQOS"],
                            res[case]['test_results'][0][1][rate_up]["videoQOS"],
                            res[case]['test_results'][0][1][rate_up]["voiceQOS"]))
                    upload_throughput_df[0].append(res[case]['test_results'][0][1][rate_up]['bkQOS'])
                    upload_throughput_df[1].append(res[case]['test_results'][0][1][rate_up]['beQOS'])
                    upload_throughput_df[2].append(res[case]['test_results'][0][1][rate_up]['videoQOS'])
                    upload_throughput_df[3].append(res[case]['test_results'][0][1][rate_up]['voiceQOS'])
                    table_df.update({"No of Stations": num_stations})
                    table_df.update({"Throughput for Load {}".format(rate_up + "-upload"): [upload_throughput[0]]})
                    graph_df.update({rate_up + "-upload": upload_throughput_df})

            if int(self.cx_profile.side_b_min_bps) != 0:
                for _ in res[case]['test_results'][0][0]:
                    download_throughput.append(
                        "BK : {}, BE : {}, VI: {}, VO: {}".format(
                            res[case]['test_results'][0][0][rate_down]["bkQOS"],
                            res[case]['test_results'][0][0][rate_down]["beQOS"],
                            res[case]['test_results'][0][0][rate_down]["videoQOS"],
                            res[case]['test_results'][0][0][rate_down]["voiceQOS"]))
                    download_throughput_df[0].append(res[case]['test_results'][0][0][rate_down]['bkQOS'])
                    download_throughput_df[1].append(res[case]['test_results'][0][0][rate_down]['beQOS'])
                    download_throughput_df[2].append(res[case]['test_results'][0][0][rate_down]['videoQOS'])
                    download_throughput_df[3].append(res[case]['test_results'][0][0][rate_down]['voiceQOS'])
                    table_df.update({"No of Stations": num_stations})
                    table_df.update({"Throughput for Load {}".format(rate_down + "-download"): [download_throughput[0]]})
                    graph_df.update({rate_down + "-download": download_throughput_df})

            res_copy.update({"throughput_table_df": table_df, "graph_df": graph_df})

        return res_copy

    def generate_graph_data_set(self, data):
        client_type = getattr(self, 'client_type', 'Real')
        data_set, overall_list = [], []
        overall_throughput = [[], [], [], []]
        load = ''
        rate_down = str(str(int(self.cx_profile.side_b_min_bps) / 1000000) + ' ' + 'Mbps')
        rate_up = str(str(int(self.cx_profile.side_a_min_bps) / 1000000) + ' ' + 'Mbps')
        if self.direction == 'Upload':
            load = rate_up
        elif self.direction == "Download":
            load = rate_down

        res = self.set_report_data(data)

        if self.direction == "Bi-direction":
            load = 'Upload' + ':' + rate_up + ',' + 'Download' + ':' + rate_down
            for key in res["graph_df"]:
                for j in range(len(res['graph_df'][key])):
                    overall_list.append(res['graph_df'][key][j])
            if len(overall_list) >= 8:
                overall_throughput[0].append(round(sum(overall_list[0] + overall_list[4]), 2))
                overall_throughput[1].append(round(sum(overall_list[1] + overall_list[5]), 2))
                overall_throughput[2].append(round(sum(overall_list[2] + overall_list[6]), 2))
                overall_throughput[3].append(round(sum(overall_list[3] + overall_list[7]), 2))
            else:
                # Fallback: only one direction present in graph_df
                overall_throughput[0].append(round(sum(overall_list[0]), 2) if overall_list else 0)
                overall_throughput[1].append(round(sum(overall_list[1]), 2) if len(overall_list) > 1 else 0)
                overall_throughput[2].append(round(sum(overall_list[2]), 2) if len(overall_list) > 2 else 0)
                overall_throughput[3].append(round(sum(overall_list[3]), 2) if len(overall_list) > 3 else 0)
            data_set = overall_throughput
        else:
            data_set = list(res["graph_df"].values())[0]
        return data_set, load, res

    def get_ssid_list(self, station_names):
        ssid_list = []
        port_data = self.json_get('/ports/all/')['interfaces']
        interfaces_dict = dict()
        for port in port_data:
            interfaces_dict.update(port)
        for sta in station_names:
            ssid_found = False
            for key, val in interfaces_dict.items():
                if sta in key:
                    ssid_list.append(val.get('ssid', '-'))
                    ssid_found = True
                    break
            if not ssid_found:
                ssid_list.append('-')
        return ssid_list

    def get_portmgr_data(self, device_list):
        ssid_list, mac_list, mode_list, bssid_list, channel_list, rssi_list = [], [], [], [], [], []
        port_json = self.json_get('/port/all')['interfaces']

        # Flatten port_json to easily search
        interfaces_dict = dict()
        for block in port_json:
            interfaces_dict.update(block)

        for target_dev in device_list:
            found = False
            for dev, data in interfaces_dict.items():
                if target_dev in dev:
                    ssid_list.append(data.get("ssid", "-"))
                    mac_list.append(data.get("mac", "-"))
                    bssid_list.append(data.get("ap", "-"))
                    channel_list.append(data.get("channel", "-"))
                    mode_list.append(data.get("mode", "-"))
                    rssi_list.append(data.get("signal", "-"))
                    found = True
                    break
            if not found:
                # Add default padding so lengths always precisely match device_list
                ssid_list.append("-")
                mac_list.append("-")
                bssid_list.append("-")
                channel_list.append("-")
                mode_list.append("-")
                rssi_list.append("-")

        return ssid_list, mac_list, mode_list, bssid_list, channel_list, rssi_list

    def generate_report(self, data, input_setup_info,
                        connections_download_avg=None, connections_upload_avg=None,
                        avg_drop_a=None, avg_drop_b=None,
                        report_path='', result_dir_name='Qos_Test_report',
                        selected_real_clients_names=None, config_devices="", iot_summary=None):
        # Defaults for optional avg dicts
        if connections_download_avg is None:
            connections_download_avg = {}
        if connections_upload_avg is None:
            connections_upload_avg = {}
        if avg_drop_a is None:
            avg_drop_a = {}
        if avg_drop_b is None:
            avg_drop_b = {}

        client_type = getattr(self, 'client_type', 'Real')

        print("We are printing Port Manager Tab Data : ")
        print(f"{self.ssid_list}  --- {self.macid_list} --- {self.mode_list} --- {self.bssid_list} --- {self.channels_list} --- {self.rssi_list}")

        if selected_real_clients_names is not None:  # for real scenario only.
            self.num_stations = selected_real_clients_names

        data_set, load, res = self.generate_graph_data_set(data)

        # Report object: title and output file differ by client type
        if client_type == 'Virtual':
            report = lf_report(_output_pdf="throughput_qos.pdf",
                               _output_html="throughput_qos.html",
                               _path=report_path,
                               _results_dir_name=result_dir_name)
        elif client_type == "Real":
            report = lf_report(_output_pdf="interop_qos.pdf",
                               _output_html="interop_qos.html",
                               _path=report_path,
                               _results_dir_name=result_dir_name)
        else:
            report = lf_report(_output_pdf="interop_qos.pdf",
                               _output_html="interop_qos.html",
                               _path=report_path,
                               _results_dir_name=result_dir_name)

        report_path = report.get_path()
        report_path_date_time = report.get_path_date_time()

        # CSV file relocation — always move individual station/client CSVs to station_reports
        self.move_station_csv_to_report(report_path_date_time)

        print("path: {}".format(report_path))
        print("path_date_time: {}".format(report_path_date_time))

        # Banner / title
        if client_type == 'Virtual':
            report.set_title("Throughput QOS")
        elif client_type == "Real":
            report.set_title("Interop QOS")
        else:
            report.set_title("LF QOS")
        report.build_banner()

        # Objective paragraph
        if client_type == 'Virtual':
            report.set_obj_html(
                _obj_title="Objective",
                _obj="The objective of the QoS (Quality of Service) traffic throughput test is to measure the maximum"
                " achievable throughput of a network under specific QoS settings and conditions. By conducting"
                " this test, we aim to assess the capacity of the network to handle high volumes of traffic while"
                " maintaining acceptable performance levels, ensuring that the network meets the required QoS"
                " standards and can adequately support the expected user demands.")
        elif iot_summary:
            report.set_obj_html(
                _obj_title="Objective",
                _obj=(
                    "The Candela QoS (Quality of Service) Test Including IoT Devices is designed to evaluate an Access Point's "
                    "performance and stability under specific QoS settings while handling both Real clients (Android, Windows, "
                    "Linux, iOS) and IoT devices (controlled via Home Assistant). "
                    "For Real clients, the test measures maximum achievable throughput across different traffic types (voice, "
                    "video, best effort, background) to ensure airtime fairness and validate that the AP can sustain high "
                    "traffic volumes while meeting QoS standards. "
                    "For IoT clients, the test concurrently executes device-specific actions (e.g., camera streaming, switch "
                    "toggling, lock/unlock) and monitors task execution success rate, latency, and failure rate. The goal is to "
                    "confirm that the AP can maintain QoS prioritization for Real client traffic while reliably supporting "
                    "multiple IoT devices with consistent responsiveness and control."
                )
            )
        else:
            report.set_obj_html(
                _obj_title="Objective",
                _obj="The objective of the QoS (Quality of Service) traffic throughput test is to measure the maximum"
                " achievable throughput of a network under specific QoS settings and conditions. By conducting"
                " this test, we aim to assess the capacity of network to handle high volumes of traffic while"
                " maintaining acceptable performance levels, ensuring that the network meets the required QoS"
                " standards and can adequately support the expected user demands.")
        report.build_objective()

        # Test Configuration table —
        if client_type == 'Virtual':
            # Virtual: per-band SSID and Security exactly like throughput_qos.py
            _existing_stas = getattr(self, '_existing_sta_list', [])
            _new_stas = [s for s in self.sta_list if s not in set(_existing_stas)]
            _sta_count_label = str(len(self.sta_list))
            if _existing_stas:
                _sta_count_label += f" ({len(_new_stas)} new + {len(_existing_stas)} existing)"
            test_setup_info = {
                "Number of Virtual Stations": _sta_count_label,
                "Virtual Stations List": ", ".join(self.sta_list),
                "AP Model": self.ap_name,
                "SSID_2.4GHz": self.ssid_2g,
                "SSID_5GHz": self.ssid_5g,
                "SSID_6GHz": self.ssid_6g,
                "Traffic Duration in hours": round(int(self.test_duration) / 3600, 2),
                "Security_2.4GHz": self.security_2g,
                "Security_5GHz": self.security_5g,
                "Security_6GHz": self.security_6g,
                "Protocol": (self.traffic_type.strip("lf_")).upper(),
                "Traffic Direction": self.direction,
                "TOS": self.tos,
                "Per TOS Load in Mbps": load,
            }
            if _existing_stas:
                test_setup_info["Existing Stations Used"] = ", ".join(_existing_stas)
        elif client_type == "Real":
            # Real: device-type breakdown
            android_devices = windows_devices = linux_devices = ios_devices = ios_mob_devices = 0
            all_devices_names = []
            total_devices = ""
            for i in self.real_client_list:
                split_device_name = i.split(" ")
                if 'android' in split_device_name:
                    all_devices_names.append(split_device_name[2] + "(Android)")
                    android_devices += 1
                elif 'Win' in split_device_name:
                    all_devices_names.append(split_device_name[2] + "(Windows)")
                    windows_devices += 1
                elif 'Lin' in split_device_name:
                    all_devices_names.append(split_device_name[2] + "(Linux)")
                    linux_devices += 1
                elif 'Mac' in split_device_name:
                    all_devices_names.append(split_device_name[2] + "(Mac)")
                    ios_devices += 1
                elif 'iOS' in split_device_name:
                    all_devices_names.append(split_device_name[2] + "(iOS)")
                    ios_mob_devices += 1
            if android_devices > 0:
                total_devices += f" Android({android_devices})"
            if windows_devices > 0:
                total_devices += f" Windows({windows_devices})"
            if linux_devices > 0:
                total_devices += f" Linux({linux_devices})"
            if ios_devices > 0:
                total_devices += f" Mac({ios_devices})"
            if ios_mob_devices > 0:
                total_devices += f" iOS({ios_mob_devices})"

            if config_devices == "":
                # Real device list
                test_setup_info = {
                    "Device List": ", ".join(all_devices_names),
                    "Number of Devices": "Total" + f"({self.num_stations})" + total_devices,
                    "AP Model": self.ap_name,
                    "SSID": self.ssid,
                    "Traffic Duration in hours": round(int(self.test_duration) / 3600, 2),
                    "Security": self.security,
                    "Protocol": (self.traffic_type.strip("lf_")).upper(),
                    "Traffic Direction": self.direction,
                    "TOS": self.tos,
                    "Per TOS Load in Mbps": load,
                }
            else:
                # Real group / profile
                group_names = ', '.join(config_devices.keys())
                profile_names = ', '.join(config_devices.values())
                configmap = "Groups:" + group_names + " -> Profiles:" + profile_names
                test_setup_info = {
                    "AP Model": self.ap_name,
                    'Configuration': configmap,
                    "Traffic Duration in hours": round(int(self.test_duration) / 3600, 2),
                    "Security": self.security,
                    "Protocol": (self.traffic_type.strip("lf_")).upper(),
                    "Traffic Direction": self.direction,
                    "TOS": self.tos,
                    "Per TOS Load in Mbps": load,
                }
            if iot_summary:
                test_setup_info = with_iot_params_in_table(test_setup_info, iot_summary)
        elif client_type == "Both":
            # For Real Device Test SetUp Information
            android_devices = windows_devices = linux_devices = ios_devices = ios_mob_devices = 0
            all_devices_names = []
            total_devices = ""
            for i in self.real_client_list:
                split_device_name = i.split(" ")
                if 'android' in split_device_name:
                    all_devices_names.append(split_device_name[2] + "(Android)")
                    android_devices += 1
                elif 'Win' in split_device_name:
                    all_devices_names.append(split_device_name[2] + "(Windows)")
                    windows_devices += 1
                elif 'Lin' in split_device_name:
                    all_devices_names.append(split_device_name[2] + "(Linux)")
                    linux_devices += 1
                elif 'Mac' in split_device_name:
                    all_devices_names.append(split_device_name[2] + "(Mac)")
                    ios_devices += 1
                elif 'iOS' in split_device_name:
                    all_devices_names.append(split_device_name[2] + "(iOS)")
                    ios_mob_devices += 1
            if android_devices > 0:
                total_devices += f" Android({android_devices})"
            if windows_devices > 0:
                total_devices += f" Windows({windows_devices})"
            if linux_devices > 0:
                total_devices += f" Linux({linux_devices})"
            if ios_devices > 0:
                total_devices += f" Mac({ios_devices})"
            if ios_mob_devices > 0:
                total_devices += f" iOS({ios_mob_devices})"

            if config_devices == "":
                _existing_stas_both = getattr(self, '_existing_sta_list', [])
                _new_stas_both = [s for s in self.sta_list if s not in set(_existing_stas_both)]
                _vsta_label = "Total " + f"{len(self.sta_list)}"
                if _existing_stas_both:
                    _vsta_label += f" ({len(_new_stas_both)} new + {len(_existing_stas_both)} existing)"
                test_setup_info = {
                    "Number of Real Devices": "Total " + f"({self.num_stations})" + total_devices,
                    "Number of Virtual Stations": _vsta_label,
                    "Real Device List":        ", ".join(all_devices_names),
                    "Virtual Stations List": ", ".join(self.sta_list),
                    "AP Model": self.ap_name,
                    "SSID": self.ssid,
                    "SSID_2.4GHz": self.ssid_2g,
                    "SSID_5GHz": self.ssid_5g,
                    "SSID_6GHz": self.ssid_6g,
                    "Traffic Duration in hours": round(int(self.test_duration) / 3600, 2),
                    "Security_2.4GHz": self.security_2g,
                    "Security_5GHz": self.security_5g,
                    "Security_6GHz": self.security_6g,
                    "Security": self.security,
                    "Protocol": (self.traffic_type.strip("lf_")).upper(),
                    "Traffic Direction": self.direction,
                    "TOS": self.tos,
                    "Per TOS Load in Mbps": load,
                }
            else:
                # Real group / profile
                group_names = ', '.join(config_devices.keys())
                profile_names = ', '.join(config_devices.values())
                configmap = "Groups:" + group_names + " -> Profiles:" + profile_names
                test_setup_info = {
                    "AP Model": self.ap_name,
                    'Configuration': configmap,
                    "Security": self.security,
                    "Number of Virtual Stations": len(self.sta_list),
                    "Virtual Stations List": ", ".join(self.sta_list),
                    "AP Model": self.ap_name,
                    "SSID_2.4GHz": self.ssid_2g,
                    "SSID_5GHz": self.ssid_5g,
                    "SSID_6GHz": self.ssid_6g,
                    "Traffic Duration in hours": round(int(self.test_duration) / 3600, 2),
                    "Security_2.4GHz": self.security_2g,
                    "Security_5GHz": self.security_5g,
                    "Security_6GHz": self.security_6g,
                    "Protocol": (self.traffic_type.strip("lf_")).upper(),
                    "Traffic Direction": self.direction,
                    "TOS": self.tos,
                    "Per TOS Load in Mbps": load,
                }
            if iot_summary:
                test_setup_info = with_iot_params_in_table(test_setup_info, iot_summary)

        print(res["throughput_table_df"])
        report.test_setup_table(test_setup_data=test_setup_info, value="Test Configuration")  # Upto here i have built Test Setup Configuration Table.

        # Overall throughput table
        report.set_table_title(
            f"Overall {self.direction} Throughput for all TOS i.e BK | BE | Video (VI) | Voice (VO)")
        report.build_table_title()
        logger.info(f"We are printing throughput table df : ")
        print(res["throughput_table_df"])
        df_throughput = pd.DataFrame(res["throughput_table_df"])
        report.set_table_dataframe(df_throughput)
        report.build_table()

        # Objective for overall graph — client count varies by type
        n_total = 0
        if self.client_type == "Virtual":
            n_total = len(self.sta_list)
        elif self.client_type == "Real":
            n_total = len(self.input_devices_list)
        else:
            n_total = len(self.sta_list) + len(self.input_devices_list)

        for _key in res["graph_df"]:
            if client_type == 'Virtual':
                report.set_obj_html(
                    _obj_title=f"Overall {self.direction} throughput for {n_total} clients for {_key} with different TOS.",
                    _obj=f"The below graph represents overall {self.direction} throughput for all "
                    "connected stations running BK, BE, VO, VI traffic with different "
                    f"intended loads per station : {_key}")
            elif client_type in ('Real', 'Both'):
                report.set_obj_html(
                    _obj_title=f"Overall {self.direction} throughput for {n_total} clients with different TOS.",
                    _obj=f"The below graph represents overall {self.direction} throughput for all "
                    "connected stations running BK, BE, VO, VI traffic with different "
                    f"intended loads : {load} per tos")
        report.build_objective()

        # Overall bar graph
        _graph_img_name = f"tos_{self.direction}_{_key} Hz"
        graph = lf_bar_graph(_data_set=data_set,
                             _xaxis_name="Load per Type of Service",
                             _yaxis_name="Throughput (Mbps)",
                             _xaxis_categories=["BK,BE,VI,VO"],
                             _xaxis_label=['1 Mbps', '2 Mbps', '3 Mbps', '4 Mbps', '5 Mbps'],
                             _graph_image_name=_graph_img_name,
                             _label=["BK", "BE", "VI", "VO"],
                             _xaxis_step=1,
                             _graph_title=f"Overall {self.direction} throughput : BK,BE,VO,VI traffic streams",
                             _title_size=16,
                             _color=['orange', 'lightcoral', 'steelblue', 'lightgrey'],
                             _color_edge='black',
                             _bar_width=0.15,
                             _figsize=(18, 6),
                             _legend_loc="best",
                             _legend_box=(1.0, 1.0),
                             _dpi=96,
                             _show_bar_value=True,
                             _enable_csv=True,
                             _color_name=['orange', 'lightcoral', 'steelblue', 'lightgrey'])
        graph_png = graph.build_bar_graph()
        print("Overall Throughput Graph : {}".format(graph_png))
        report.set_graph_image(graph_png)
        # need to move the graph image to the results directory
        report.move_graph_image()
        report.set_csv_filename(graph_png)
        report.move_csv_file()
        report.build_graph()

        # Bandsteering stats section (only when do_bandsteering is enabled)
        if getattr(self, 'do_bandsteering', False):
            self.get_bandsteering_stats(report=report, data=self.band_steering_df)
        report.test_setup_table(test_setup_data=input_setup_info, value="Information")
        # To add charging timestamps of robot in report when bandsteering is enabled
        if self.do_bandsteering:
            if len(self.robot.charging_timestamps) != 0:
                report.set_obj_html(_obj_title="Charging Timestamps",
                                    _obj="")
                report.build_objective()
                df = pd.DataFrame(
                    self.robot.charging_timestamps,
                    columns=[
                        "charge_dock_arrival_timestamp",
                        "charging_completion_timestamp"
                    ]
                )
                # Add S.No column
                df.insert(0, "S.No", range(1, len(df) + 1))
                report.set_table_dataframe(df)
                report.build_table()
            else:
                report.set_obj_html(_obj_title="Charging Timestamps",
                                    _obj="Robot did not went to charge during this test")
                report.build_objective()

        # Individual per-TOS graphs and tables — dispatch by client type
        if client_type == 'Virtual':
            # Virtual: uses sta_list, mac_list, channel_list, test_case band loop
            self.generate_individual_graph_virtual(res, report)
        else:
            # Real/Both: uses real_client_list, mac_id_list, connections_avg dicts
            self.generate_individual_graph(
                res, report,
                connections_download_avg, connections_upload_avg,
                avg_drop_a, avg_drop_b)

        # Bandsteering stats section (only when do_bandsteering is enabled)
        if getattr(self, 'do_bandsteering', False):
            self.get_bandsteering_stats(report=report, data=self.band_steering_df)

        report.test_setup_table(test_setup_data=input_setup_info, value="Information")

        if client_type == 'Virtual':
            report.build_custom()
        elif iot_summary:
            self.build_iot_report_section(report, iot_summary)

        report.build_footer()
        report.write_html()
        report.write_pdf()

    # Generates a separate table in the report for each group, including its respective devices.
    def generate_dataframe(self, groupdevlist, clients_list, mac, ssid, tos, upload, download, individual_upload,
                           individual_download, test_input, individual_drop_b, individual_drop_a, pass_fail_list):
        clients = []
        macids = []
        ssids = []
        tos_a = []
        uploads = []
        downloads = []
        individual_uploads = []
        individual_downloads = []
        individual_b_drop = []
        individual_a_drop = []
        input_list = []
        status = []
        interop_tab_data = self.json_get('/adb/')["devices"]
        for i in range(len(clients_list)):
            for j in groupdevlist:
                # For a string like "1.360 Lin test3":
                # - clients_list[i].split(" ")[2] gives 'test3' (device name)
                # - clients_list[i].split(" ")[1] gives 'Lin' (OS type)
                # This condition filters out Android clients and matches device name with j
                if j == clients_list[i].split(" ")[2] and clients_list[i].split(" ")[1] != 'android':
                    clients.append(clients_list[i])
                    macids.append(mac[i])
                    ssids.append(ssid[i])
                    tos_a.append(tos[i])
                    uploads.append(upload[i])
                    downloads.append(download[i])
                    individual_uploads.append(individual_upload[i])
                    individual_downloads.append(individual_download[i])
                    if self.direction == "Bi-direction":
                        individual_b_drop.append(individual_drop_b[i])
                        individual_a_drop.append(individual_drop_a[i])
                    elif self.direction == "Download":
                        individual_a_drop.append(individual_drop_a[i])
                    else:
                        individual_b_drop.append(individual_drop_b[i])
                    if self.expected_passfail_val or self.csv_name:
                        input_list.append(test_input[i])
                        status.append(pass_fail_list[i])
                # For a string like 1.15 android samsungmob:
                # - clients_list[i].split(' ')[2] (e.g., 'samsungmob') matches item['user-name']
                # - The group name (e.g., 'RZCTA09CTXF') matches with item['name'].split('.')[2]
                else:
                    for dev in interop_tab_data:
                        for item in dev.values():
                            if item['user-name'] == clients_list[i].split(' ')[2] and j == item['name'].split('.')[2]:
                                clients.append(clients_list[i])
                                macids.append(mac[i])
                                ssids.append(ssid[i])
                                tos_a.append(tos[i])
                                uploads.append(upload[i])
                                downloads.append(download[i])
                                individual_uploads.append(individual_upload[i])
                                individual_downloads.append(individual_download[i])
                                if self.direction == "Bi-direction":
                                    individual_b_drop.append(individual_drop_b[i])
                                    individual_a_drop.append(individual_drop_a[i])
                                elif self.direction == "Download":
                                    individual_a_drop.append(individual_drop_a[i])
                                else:
                                    individual_b_drop.append(individual_drop_b[i])
                                if self.expected_passfail_val or self.csv_name:
                                    input_list.append(test_input[i])
                                    status.append(pass_fail_list[i])
        if len(clients) != 0:
            bk_dataframe = {
                " Client Name ": clients,
                " MAC ": self.macid_list,
                " SSID ": self.ssid_list,
                " BSSID ": self.bssid_list,
                " Channel ": self.channels_list,
                " RSSI ": self.rssi_list,
                " Type of traffic ": tos_a,
                " Offered upload rate(Mbps) ": uploads,
                " Offered download rate(Mbps) ": downloads,
                " Observed average upload rate(Mbps) ": individual_uploads,
                " Observed average download rate(Mbps)": individual_downloads,
            }
            if self.direction == "Bi-direction":
                bk_dataframe[" Observed Upload Drop (%)"] = individual_b_drop
                bk_dataframe[" Observed Download Drop (%)"] = individual_a_drop
            else:
                if self.direction == "Upload":
                    bk_dataframe[" Observed Upload Drop (%)"] = individual_b_drop
                    bk_dataframe[" Observed Download Drop (%)"] = [0.0] * len(individual_b_drop)
                elif self.direction == "Download":
                    bk_dataframe[" Observed Upload Drop (%)"] = [0.0] * len(individual_a_drop)
                    bk_dataframe[" Observed Download Drop (%)"] = individual_a_drop

            if self.expected_passfail_val or self.csv_name:
                bk_dataframe[" Expected " + self.direction + " rate(Mbps)"] = input_list
                bk_dataframe[" Status "] = status
            return bk_dataframe
        else:
            return None

    def get_live_view_images(self, multicast_exists=False):
        """
        This function looks for throughput and RSSI images for each floor
        in the 'live_view_images' folder within `self.result_dir`.
        It waits up to **60 seconds** for each image. If an image is found,then,
        their name/path will be stored for the report purposes,otherwise, it's skipped.

        Parameters:
        multicast_exists (bool): Indicates whether multicast traffic is present during the test.
        When running Testhouse with mixed traffic , such as both QoS and multicast,
        the overall report may show duplicate RSSI live view images, since the RSSI values are identical for both the tests.
        """
        image_paths_by_tos = {}      # { "BE": [img1, img2, ...], "VO": [...], ... }
        rssi_image_paths_by_floor = {} if not multicast_exists else {}  # Empty if skipping RSSI
        # Robot currently supports single-floor testing only, So setting the floors value to 1
        if self.robot_test:
            self.total_floors = 1
        for floor in range(int(self.total_floors)):
            for tos in self.tos:
                timeout = 200  # seconds

                throughput_image_path = os.path.join(self.result_dir, "live_view_images", f"{self.test_name}_throughput_{tos}_{floor + 1}.png")

                if not multicast_exists:
                    rssi_image_path = os.path.join(self.result_dir, "live_view_images", f"{self.test_name}_rssi_{floor + 1}.png")

                start_time = time.time()

                while True:
                    throughput_ready = os.path.exists(throughput_image_path)
                    rssi_ready = True if multicast_exists else os.path.exists(rssi_image_path)

                    if throughput_ready and rssi_ready:
                        break

                    if time.time() - start_time > timeout:
                        print(f"Timeout: Images for TOS '{tos}' on Floor {floor + 1} not found within 200 seconds.")
                        break
                    time.sleep(1)

                if throughput_ready:
                    image_paths_by_tos.setdefault(tos, []).append(throughput_image_path)

            # Only check and store RSSI if not multicast
            if not multicast_exists and os.path.exists(rssi_image_path):
                rssi_image_paths_by_floor[floor + 1] = rssi_image_path

        return image_paths_by_tos, rssi_image_paths_by_floor

    def generate_individual_graph(self, res, report, connections_download_avg, connections_upload_avg, avg_drop_a, avg_drop_b, totalfloors=None, multicast_exists=False, graph_no=''):
        client_type = getattr(self, 'client_type', 'Real')

        # Required when generate_individual_graph() called explicitly from mixed traffic
        if totalfloors is not None:
            self.total_floors = totalfloors

        # Client-list aliases — both Real and Both use real_client_list
        if client_type == "Real":
            client_list = self.real_client_list
            client_list_1 = self.real_client_list1
            macid_list = self.mac_id_list
            n_clients = len(self.real_client_list)
            n_ports = len(self.input_devices_list)

            print(f"{client_list} : {client_list_1} : {macid_list} : {n_clients} : {n_ports}")
        elif client_type == "Both":
            client_list = self.sta_list + self.real_client_list
            client_list_1 = self.sta_list + self.real_client_list1
            macid_list = self.mac_id_list
            n_clients = len(client_list)
            n_ports = len(self.input_devices_list) + len(self.sta_list)

            print(f"{client_list} : {client_list_1} : {macid_list} : {n_clients} : {n_ports}")

        load = ""
        upload_list, download_list, individual_upload_list, individual_download_list = [], [], [], []
        individual_set, colors, labels = [], [], []
        individual_drop_a_list, individual_drop_b_list = [], []
        list1 = [[], [], [], []]
        data_set = {}
        try:
            if (self.dowebgui and self.get_live_view) or multicast_exists:
                tos_images, rssi_images = self.get_live_view_images()
        except Exception:
            logger.error("Live View images not found")
        # Initialized dictionaries to store average upload ,download and drop values with respect to tos
        avg_res = {'Upload': {
            'VO': [],
            'VI': [],
            'BE': [],
            'BK': []
        },
            'Download': {
            'VO': [],
                'VI': [],
                'BE': [],
                'BK': []
        }
        }
        drop_res = {'drop_a': {
            'VO': [],
            'VI': [],
            'BE': [],
            'BK': []
        },
            'drop_b': {
            'VO': [],
                'VI': [],
                'BE': [],
                'BK': []
        }
        }
        rate_down = str(str(int(self.cx_profile.side_b_min_bps) / 1000000) + ' ' + 'Mbps')
        rate_up = str(str(int(self.cx_profile.side_a_min_bps) / 1000000) + ' ' + 'Mbps')
        # Updated the dictionaries with the respective average upload download and drop values for a particular tos
        # EXAMPLE DATA FOR UPLOAD:
        # {'1.10androidSamsung_M21_UDP_UL_VI-0': 1.0, '1.10androidSamsung_M21_UDP_UL_VO-1': 0.96,'1.10androidSamsung_M21_UDP_UL_BE- 2': 0.78,'1.10androidSamsung_M21_UDP_UL_BK-3': 1.0}
        if self.direction == 'Upload':
            load = rate_up
            data_set = res['test_results'][0][1]
            for _client in range(n_clients):
                individual_download_list.append('0.0')
                individual_drop_a_list.append('0.0')
            for key, val in connections_upload_avg.items():
                tos = key.split('_')[-1].split('-')[0]
                avg_res[self.direction][tos].append(val)
            for key, val in avg_drop_b.items():
                tos = key.split('_')[-1].split('-')[0]
                drop_res['drop_b'][tos].append(val)
        else:
            if self.direction == 'Download':
                load = rate_down
                data_set = res['test_results'][0][0]
                for _client in range(n_clients):
                    individual_upload_list.append('0.0')
                    individual_drop_b_list.append('0.0')
                for key, val in connections_download_avg.items():
                    tos = key.split('_')[-1].split('-')[0]
                    avg_res[self.direction][tos].append(val)
                for key, val in avg_drop_a.items():
                    tos = key.split('_')[-1].split('-')[0]
                    drop_res['drop_a'][tos].append(val)
        tos_type = ['Background', 'Besteffort', 'Video', 'Voice']
        load_list = []
        traffic_type_list = []
        traffic_direction_list = []
        bk_tos_list = []
        be_tos_list = []
        vi_tos_list = []
        vo_tos_list = []
        traffic_type = (self.traffic_type.strip("lf_")).upper()
        for _client in range(n_clients):
            upload_list.append(rate_up)
            download_list.append(rate_down)
            traffic_type_list.append(traffic_type.upper())
            bk_tos_list.append(tos_type[0])
            be_tos_list.append(tos_type[1])
            vi_tos_list.append(tos_type[2])
            vo_tos_list.append(tos_type[3])
            load_list.append(load)
            traffic_direction_list.append(self.direction)

        # print(traffic_type_list,traffic_direction_list,bk_tos_list,be_tos_list,vi_tos_list,vo_tos_list)
        if self.direction == "Bi-direction":
            load = 'Upload' + ':' + rate_up + ',' + 'Download' + ':' + rate_down
            for key in res['test_results'][0][0]:
                list1[0].append(res['test_results'][0][0][key]['VI'])
                list1[1].append(res['test_results'][0][0][key]['VO'])
                list1[2].append(res['test_results'][0][0][key]['BK'])
                list1[3].append(res['test_results'][0][0][key]['BE'])
            for key in res['test_results'][0][1]:
                list1[0].append(res['test_results'][0][1][key]['VI'])
                list1[1].append(res['test_results'][0][1][key]['VO'])
                list1[2].append(res['test_results'][0][1][key]['BK'])
                list1[3].append(res['test_results'][0][1][key]['BE'])
            for key, val in connections_upload_avg.items():
                tos = key.split('_')[-1].split('-')[0]
                avg_res['Upload'][tos].append(val)
            for key, val in connections_download_avg.items():
                tos = key.split('_')[-1].split('-')[0]
                avg_res['Download'][tos].append(val)
            for key, val in avg_drop_b.items():
                tos = key.split('_')[-1].split('-')[0]
                drop_res['drop_b'][tos].append(val)
            for key, val in avg_drop_a.items():
                tos = key.split('_')[-1].split('-')[0]
                drop_res['drop_a'][tos].append(val)

        x_fig_size = 15
        y_fig_size = n_clients * .5 + 4
        if len(res.keys()) > 0:
            if "throughput_table_df" in res:
                res.pop("throughput_table_df")
            if "graph_df" in res:
                res.pop("graph_df")
                logger.info(res)
                logger.info(load)
                logger.info(data_set)
                # If a CSV filename is provided, retrieve the expected values for each device from the CSV file
                if not self.expected_passfail_val and self.csv_name:
                    test_input_list = self.get_csv_expected_val()

                if "BK" in self.tos:
                    if self.direction == "Bi-direction":
                        individual_set = list1[2]
                        individual_download_list = avg_res['Download']['BK']
                        individual_upload_list = avg_res['Upload']['BK']
                        individual_drop_a_list = drop_res['drop_a']['BK']
                        individual_drop_b_list = drop_res['drop_b']['BK']
                        colors = ['orange', 'wheat']
                        labels = ["Download", "Upload"]
                    else:
                        individual_set = [data_set[load]['BK']]
                        colors = ['orange']
                        labels = ['BK']
                        if self.direction == "Upload":
                            individual_upload_list = avg_res['Upload']['BK']
                            individual_drop_b_list = drop_res['drop_b']['BK']
                        elif self.direction == "Download":
                            individual_download_list = avg_res['Download']['BK']
                            individual_drop_a_list = drop_res['drop_a']['BK']

                    report.set_obj_html(
                        _obj_title=f"Individual {self.direction} throughput with intended load {load}/station for traffic BK(WiFi).",
                        _obj=f"The below graph represents individual throughput for {n_ports} clients running BK "
                        f"(WiFi) traffic.  X- axis shows “Throughput in Mbps” and Y-axis shows “number of clients”.")
                    report.build_objective()
                    # print(upload_list, download_list, individual_download_list, individual_upload_list)
                    graph = lf_bar_graph_horizontal(_data_set=individual_set, _xaxis_name="Throughput in Mbps",
                                                    _yaxis_name="Client names",
                                                    _yaxis_categories=[i for i in client_list_1],
                                                    _yaxis_label=[i for i in client_list_1],
                                                    _label=labels,
                                                    _yaxis_step=1,
                                                    _yticks_font=8,
                                                    _yticks_rotation=None,
                                                    _graph_title=f"Individual {self.direction} throughput for BK(WIFI) traffic",
                                                    _title_size=16,
                                                    _figsize=(x_fig_size, y_fig_size),
                                                    _legend_loc="best",
                                                    _legend_box=(1.0, 1.0),
                                                    _color_name=colors,
                                                    _show_bar_value=True,
                                                    _enable_csv=True,
                                                    _graph_image_name="bk_{}{}".format(self.direction, graph_no), _color_edge=['black'],
                                                    _color=colors)
                    graph_png = graph.build_bar_graph_horizontal()
                    print("graph name {}".format(graph_png))
                    report.set_graph_image(graph_png)
                    # need to move the graph image to the results
                    report.move_graph_image()
                    report.set_csv_filename(graph_png)
                    report.move_csv_file()
                    report.build_graph()

                    if (self.dowebgui and self.get_live_view) or multicast_exists:
                        if not self.robot_test:
                            for image_path in tos_images['BK']:
                                report.set_custom_html('<div style="page-break-before: always;"></div>')
                                report.build_custom()
                                report.set_custom_html(f'<img src="file://{image_path}" style="width: 1200px; height: 800px;"></img>')
                                report.build_custom()
                    individual_avgupload_list = []
                    individual_avgdownload_list = []
                    for i in range(len(individual_upload_list)):
                        individual_avgupload_list.append(str(str(individual_upload_list[i]) + ' ' + 'Mbps'))
                    for j in range(len(individual_download_list)):
                        individual_avgdownload_list.append(str(str(individual_download_list[j]) + ' ' + 'Mbps'))
                    if self.expected_passfail_val:
                        test_input_list = [self.expected_passfail_val for val in range(n_clients)]
                    # Calculating the pass/fail criteria when either expected_passfail_val or csv_name is provided
                    if self.expected_passfail_val or self.csv_name:
                        pass_fail_list = self.get_pass_fail_list(test_input_list, individual_avgupload_list, individual_avgdownload_list)

                    if self.group_name:
                        for key, val in self.group_device_map.items():
                            if self.expected_passfail_val or self.csv_name:
                                dataframe = self.generate_dataframe(
                                    val,
                                    self.real_client_list,
                                    self.mac_id_list,
                                    self.ssid_list,
                                    bk_tos_list,
                                    upload_list,
                                    download_list,
                                    individual_avgupload_list,
                                    individual_avgdownload_list,
                                    test_input_list,
                                    individual_drop_b_list,
                                    individual_drop_a_list,
                                    pass_fail_list)
                            else:
                                dataframe = self.generate_dataframe(
                                    val,
                                    self.real_client_list,
                                    self.mac_id_list,
                                    self.ssid_list,
                                    bk_tos_list,
                                    upload_list,
                                    download_list,
                                    individual_avgupload_list,
                                    individual_avgdownload_list,
                                    [],
                                    individual_drop_b_list,
                                    individual_drop_a_list,
                                    [])
                            if dataframe:
                                report.set_obj_html("", "Group: {}".format(key))
                                report.build_objective()
                                print("dataframe", dataframe)
                                dataframe1 = pd.DataFrame(dataframe)
                                report.set_table_dataframe(dataframe1)
                                report.build_table()
                    else:
                        bk_dataframe = {
                            " Client Name ": client_list,
                            " MAC ": self.macid_list,
                            " SSID ": self.ssid_list,
                            " BSSID ": self.bssid_list,
                            " Channel ": self.channels_list,
                            " RSSI ": self.rssi_list,
                            " Type of traffic ": bk_tos_list,
                            " Offered upload rate ": upload_list,
                            " Offered download rate ": download_list,
                            " Observed average upload rate ": individual_avgupload_list,
                            " Observed average download rate": individual_avgdownload_list,
                        }
                        bk_dataframe[" Observed Upload Drop (%)"] = individual_drop_b_list
                        bk_dataframe[" Observed Download Drop (%)"] = individual_drop_a_list
                        if self.expected_passfail_val or self.csv_name:
                            bk_dataframe[" Expected " + self.direction + " rate(Mbps)"] = test_input_list
                            bk_dataframe[" Status "] = pass_fail_list
                        dataframe1 = pd.DataFrame(bk_dataframe)
                        report.set_table_dataframe(dataframe1)
                        report.build_table()
                logger.info("Graph and table for BK tos are built")

                if "BE" in self.tos:
                    if self.direction == "Bi-direction":
                        individual_set = list1[3]
                        individual_download_list = avg_res['Download']['BE']
                        individual_upload_list = avg_res['Upload']['BE']
                        individual_drop_a_list = drop_res['drop_a']['BE']
                        individual_drop_b_list = drop_res['drop_b']['BE']
                        colors = ['lightcoral', 'mistyrose']
                        labels = ['Download', 'Upload']
                    else:
                        individual_set = [data_set[load]['BE']]
                        colors = ['violet']
                        labels = ['BE']
                        if self.direction == "Upload":
                            individual_upload_list = avg_res['Upload']['BE']
                            individual_drop_b_list = drop_res['drop_b']['BE']
                        elif self.direction == "Download":
                            individual_download_list = avg_res['Download']['BE']
                            individual_drop_a_list = drop_res['drop_a']['BE']
                    report.set_obj_html(
                        _obj_title=f"Individual {self.direction} throughput with intended load {load}/station for traffic BE(WiFi).",
                        _obj=f"The below graph represents individual throughput for {n_ports} clients running BE "
                        f"(WiFi) traffic.  X- axis shows “number of clients” and Y-axis shows "
                        f"“Throughput in Mbps”.")
                    # print("individual set",individual_set)
                    report.build_objective()
                    graph = lf_bar_graph_horizontal(_data_set=individual_set, _yaxis_name="Client names",
                                                    _xaxis_name="Throughput in Mbps",
                                                    _yaxis_categories=[i for i in client_list_1],
                                                    _yaxis_label=[i for i in client_list_1],
                                                    _label=labels,
                                                    _yaxis_step=1,
                                                    _yticks_font=8,
                                                    _yticks_rotation=None,
                                                    _graph_title=f"Individual {self.direction} throughput for BE(WIFI) traffic",
                                                    _title_size=16,
                                                    _figsize=(x_fig_size, y_fig_size),
                                                    _legend_loc="best",
                                                    _legend_box=(1.0, 1.0),
                                                    _color_name=colors,
                                                    _show_bar_value=True,
                                                    _enable_csv=True,
                                                    _graph_image_name="be_{}{}".format(self.direction, graph_no), _color_edge=['black'],
                                                    _color=colors)
                    graph_png = graph.build_bar_graph_horizontal()
                    print("graph name {}".format(graph_png))
                    report.set_graph_image(graph_png)
                    # need to move the graph image to the results
                    report.move_graph_image()
                    report.set_csv_filename(graph_png)
                    report.move_csv_file()
                    report.build_graph()
                    if (self.dowebgui and self.get_live_view) or multicast_exists:
                        if not self.robot_test:
                            for image_path in tos_images['BE']:
                                report.set_custom_html('<div style="page-break-before: always;"></div>')
                                report.build_custom()
                                report.set_custom_html(f'<img src="file://{image_path}" style="width: 1200px; height: 800px;"></img>')
                                report.build_custom()
                    individual_avgupload_list = []
                    individual_avgdownload_list = []
                    for i in range(len(individual_upload_list)):
                        individual_avgupload_list.append(str(str(individual_upload_list[i]) + ' ' + 'Mbps'))
                    for j in range(len(individual_download_list)):
                        individual_avgdownload_list.append(str(str(individual_download_list[j]) + ' ' + 'Mbps'))
                    if self.expected_passfail_val:
                        test_input_list = [self.expected_passfail_val for val in range(n_clients)]
                    # Calculating the pass/fail criteria when either expected_passfail_val or csv_name is provided
                    if self.expected_passfail_val or self.csv_name:
                        pass_fail_list = self.get_pass_fail_list(test_input_list, individual_avgupload_list, individual_avgdownload_list)
                    if self.group_name:
                        for key, val in self.group_device_map.items():
                            if self.expected_passfail_val or self.csv_name:
                                dataframe = self.generate_dataframe(
                                    val,
                                    self.real_client_list,
                                    self.mac_id_list,
                                    self.ssid_list,
                                    be_tos_list,
                                    upload_list,
                                    download_list,
                                    individual_avgupload_list,
                                    individual_avgdownload_list,
                                    test_input_list,
                                    individual_drop_b_list,
                                    individual_drop_a_list,
                                    pass_fail_list)
                            else:
                                dataframe = self.generate_dataframe(
                                    val,
                                    self.real_client_list,
                                    self.mac_id_list,
                                    self.ssid_list,
                                    be_tos_list,
                                    upload_list,
                                    download_list,
                                    individual_avgupload_list,
                                    individual_avgdownload_list,
                                    [],
                                    individual_drop_b_list,
                                    individual_drop_a_list,
                                    [])
                            if dataframe:
                                report.set_obj_html("", "Group: {}".format(key))
                                report.build_objective()
                                dataframe1 = pd.DataFrame(dataframe)
                                report.set_table_dataframe(dataframe1)
                                report.build_table()
                    else:
                        be_dataframe = {
                            " Client Name ": client_list,
                            " MAC ": self.macid_list,
                            " SSID ": self.ssid_list,
                            " BSSID ": self.bssid_list,
                            " Channel ": self.channels_list,
                            " RSSI ": self.rssi_list,
                            " Type of traffic ": be_tos_list,
                            " Offered upload rate ": upload_list,
                            " Offered download rate ": download_list,
                            " Observed average upload rate ": individual_avgupload_list,
                            " Observed average download rate": individual_avgdownload_list,
                        }
                        be_dataframe[" Observed Upload Drop (%)"] = individual_drop_b_list
                        be_dataframe[" Observed Download Drop (%)"] = individual_drop_a_list
                        if self.expected_passfail_val or self.csv_name:
                            be_dataframe[" Expected " + self.direction + " rate(Mbps)"] = test_input_list
                            be_dataframe[" Status "] = pass_fail_list
                        dataframe2 = pd.DataFrame(be_dataframe)
                        report.set_table_dataframe(dataframe2)
                        report.build_table()
                logger.info("Graph and table for BE tos are built")
                if "VI" in self.tos:
                    if self.direction == "Bi-direction":
                        individual_set = list1[0]
                        individual_download_list = avg_res['Download']['VI']
                        individual_upload_list = avg_res['Upload']['VI']
                        individual_drop_a_list = drop_res['drop_a']['VI']
                        individual_drop_b_list = drop_res['drop_b']['VI']
                        colors = ['steelblue', 'lightskyblue']
                        labels = ['Download', 'Upload']
                    else:
                        individual_set = [data_set[load]['VI']]
                        colors = ['steelblue']
                        labels = ['VI']
                        if self.direction == "Upload":
                            individual_upload_list = avg_res['Upload']['VI']
                            individual_drop_b_list = drop_res['drop_b']['VI']
                        elif self.direction == "Download":
                            individual_download_list = avg_res['Download']['VI']
                            individual_drop_a_list = drop_res['drop_a']['VI']
                    report.set_obj_html(
                        _obj_title=f"Individual {self.direction} throughput with intended load {load}/station for traffic VI(WiFi).",
                        _obj=f"The below graph represents individual throughput for {n_ports} clients running VI "
                        f"(WiFi) traffic.  X- axis shows “number of clients” and Y-axis shows "
                        f"“Throughput in Mbps”.")
                    report.build_objective()
                    graph = lf_bar_graph_horizontal(_data_set=individual_set, _yaxis_name="Client names",
                                                    _xaxis_name="Throughput in Mbps",
                                                    _yaxis_categories=[i for i in client_list_1],
                                                    _yaxis_label=[i for i in client_list_1],
                                                    _label=labels,
                                                    _yaxis_step=1,
                                                    _yticks_font=8,
                                                    _yticks_rotation=None,
                                                    _graph_title=f"Individual {self.direction} throughput for VI(WIFI) traffic",
                                                    _title_size=16,
                                                    _figsize=(x_fig_size, y_fig_size),
                                                    _legend_loc="best",
                                                    _legend_box=(1.0, 1.0),
                                                    _show_bar_value=True,
                                                    _color_name=colors,
                                                    _enable_csv=True,
                                                    _graph_image_name="video_{}{}".format(self.direction, graph_no),
                                                    _color_edge=['black'],
                                                    _color=colors)
                    graph_png = graph.build_bar_graph_horizontal()
                    print("graph name {}".format(graph_png))
                    report.set_graph_image(graph_png)
                    # need to move the graph image to the results
                    report.move_graph_image()
                    report.set_csv_filename(graph_png)
                    report.move_csv_file()
                    report.build_graph()
                    if (self.dowebgui and self.get_live_view) or multicast_exists:
                        if not self.robot_test:
                            for image_path in tos_images['VI']:
                                report.set_custom_html('<div style="page-break-before: always;"></div>')
                                report.build_custom()
                                report.set_custom_html(f'<img src="file://{image_path}" style="width: 1200px; height: 800px;"></img>')
                                report.build_custom()
                    individual_avgupload_list = []
                    individual_avgdownload_list = []
                    for i in range(len(individual_upload_list)):
                        individual_avgupload_list.append(str(str(individual_upload_list[i]) + ' ' + 'Mbps'))
                    for j in range(len(individual_download_list)):
                        individual_avgdownload_list.append(str(str(individual_download_list[j]) + ' ' + 'Mbps'))
                    if self.expected_passfail_val:
                        test_input_list = [self.expected_passfail_val for val in range(n_clients)]
                    # Calculating the pass/fail criteria when either expected_passfail_val or csv_name is provided
                    if self.expected_passfail_val or self.csv_name:
                        pass_fail_list = self.get_pass_fail_list(test_input_list, individual_avgupload_list, individual_avgdownload_list)
                    if self.group_name:
                        for key, val in self.group_device_map.items():
                            if self.expected_passfail_val or self.csv_name:
                                dataframe = self.generate_dataframe(
                                    val,
                                    self.real_client_list,
                                    self.mac_id_list,
                                    self.ssid_list,
                                    vi_tos_list,
                                    upload_list,
                                    download_list,
                                    individual_avgupload_list,
                                    individual_avgdownload_list,
                                    test_input_list,
                                    individual_drop_b_list,
                                    individual_drop_a_list,
                                    pass_fail_list)
                            else:
                                dataframe = self.generate_dataframe(
                                    val,
                                    self.real_client_list,
                                    self.mac_id_list,
                                    self.ssid_list,
                                    vi_tos_list,
                                    upload_list,
                                    download_list,
                                    individual_avgupload_list,
                                    individual_avgdownload_list,
                                    [],
                                    individual_drop_b_list,
                                    individual_drop_a_list,
                                    [])
                            if dataframe:
                                report.set_obj_html("", "Group: {}".format(key))
                                report.build_objective()
                                dataframe1 = pd.DataFrame(dataframe)
                                report.set_table_dataframe(dataframe1)
                                report.build_table()
                    else:
                        vi_dataframe = {
                            " Client Name ": client_list,
                            " MAC ": self.macid_list,
                            " SSID ": self.ssid_list,
                            " BSSID ": self.bssid_list,
                            " Channel ": self.channels_list,
                            " RSSI ": self.rssi_list,
                            " Type of traffic ": vi_tos_list,
                            " Offered upload rate ": upload_list,
                            " Offered download rate ": download_list,
                            " Observed average upload rate ": individual_avgupload_list,
                            " Observed average download rate": individual_avgdownload_list,
                        }
                        vi_dataframe[" Observed Upload Drop (%)"] = individual_drop_b_list
                        vi_dataframe[" Observed Download Drop (%)"] = individual_drop_a_list
                        if self.expected_passfail_val or self.csv_name:
                            vi_dataframe[" Expected " + self.direction + " rate(Mbps)"] = test_input_list
                            vi_dataframe[" Status "] = pass_fail_list
                        dataframe3 = pd.DataFrame(vi_dataframe)
                        report.set_table_dataframe(dataframe3)
                        report.build_table()
                logger.info("Graph and table for VI tos are built")

                if "VO" in self.tos:
                    if self.direction == "Bi-direction":
                        individual_set = list1[1]
                        individual_download_list = avg_res['Download']['VO']
                        individual_upload_list = avg_res['Upload']['VO']
                        individual_drop_a_list = drop_res['drop_a']['VO']
                        individual_drop_b_list = drop_res['drop_b']['VO']
                        colors = ['grey', 'lightgrey']
                        labels = ['Download', 'Upload']
                    else:
                        individual_set = [data_set[load]['VO']]
                        colors = ['grey']
                        labels = ['VO']
                        if self.direction == "Upload":
                            individual_upload_list = avg_res['Upload']['VO']
                            individual_drop_b_list = drop_res['drop_b']['VO']
                        elif self.direction == "Download":
                            individual_download_list = avg_res['Download']['VO']
                            individual_drop_a_list = drop_res['drop_a']['VO']
                    report.set_obj_html(
                        _obj_title=f"Individual {self.direction} throughput with intended load {load}/station for traffic VO(WiFi).",
                        _obj=f"The below graph represents individual throughput for {n_ports} clients running VO "
                        f"(WiFi) traffic.  X- axis shows “number of clients” and Y-axis shows "
                        f"“Throughput in Mbps”.")
                    report.build_objective()
                    graph = lf_bar_graph_horizontal(_data_set=individual_set, _yaxis_name="Client names",
                                                    _xaxis_name="Throughput in Mbps",
                                                    _yaxis_categories=[i for i in client_list_1],
                                                    _yaxis_label=[i for i in client_list_1],
                                                    _label=labels,
                                                    _yaxis_step=1,
                                                    _yticks_font=8,
                                                    _graph_title=f"Individual {self.direction} throughput for VO(WIFI) traffic",
                                                    _title_size=16,
                                                    _figsize=(x_fig_size, y_fig_size),
                                                    _yticks_rotation=None,
                                                    _legend_loc="best",
                                                    _legend_box=(1.0, 1.0),
                                                    _show_bar_value=True,
                                                    _color_name=colors,
                                                    _enable_csv=True,
                                                    _graph_image_name="voice_{}{}".format(self.direction, graph_no),
                                                    _color_edge=['black'],
                                                    _color=colors)
                    graph_png = graph.build_bar_graph_horizontal()
                    print("graph name {}".format(graph_png))
                    report.set_graph_image(graph_png)
                    # need to move the graph image to the results
                    report.move_graph_image()
                    report.set_csv_filename(graph_png)
                    report.move_csv_file()
                    report.build_graph()
                    if (self.dowebgui and self.get_live_view) or multicast_exists:
                        if not self.robot_test:
                            for image_path in tos_images['VO']:
                                report.set_custom_html('<div style="page-break-before: always;"></div>')
                                report.build_custom()
                                report.set_custom_html(f'<img src="file://{image_path}" style="width: 1200px; height: 800px;"></img>')
                                report.build_custom()
                    individual_avgupload_list = []
                    individual_avgdownload_list = []
                    for i in range(len(individual_upload_list)):
                        individual_avgupload_list.append(str(str(individual_upload_list[i]) + ' ' + 'Mbps'))
                    for j in range(len(individual_download_list)):
                        individual_avgdownload_list.append(str(str(individual_download_list[j]) + ' ' + 'Mbps'))
                    if self.expected_passfail_val:
                        pass_fail_list = []
                        test_input_list = [self.expected_passfail_val for val in range(n_clients)]
                    # Calculating the pass/fail criteria when either expected_passfail_val or csv_name is provided
                    if self.expected_passfail_val or self.csv_name:
                        pass_fail_list = self.get_pass_fail_list(test_input_list, individual_avgupload_list, individual_avgdownload_list)
                    if self.group_name:
                        for key, val in self.group_device_map.items():
                            if self.expected_passfail_val or self.csv_name:
                                dataframe = self.generate_dataframe(
                                    val,
                                    self.real_client_list,
                                    self.mac_id_list,
                                    self.ssid_list,
                                    vo_tos_list,
                                    upload_list,
                                    download_list,
                                    individual_avgupload_list,
                                    individual_avgdownload_list,
                                    test_input_list,
                                    individual_drop_b_list,
                                    individual_drop_a_list,
                                    pass_fail_list)
                            else:
                                dataframe = self.generate_dataframe(
                                    val,
                                    self.real_client_list,
                                    self.mac_id_list,
                                    self.ssid_list,
                                    vo_tos_list,
                                    upload_list,
                                    download_list,
                                    individual_avgupload_list,
                                    individual_avgdownload_list,
                                    [],
                                    individual_drop_b_list,
                                    individual_drop_a_list,
                                    [])
                            if dataframe:
                                report.set_obj_html("", "Group: {}".format(key))
                                report.build_objective()
                                dataframe1 = pd.DataFrame(dataframe)
                                report.set_table_dataframe(dataframe1)
                                report.build_table()
                    else:
                        vo_dataframe = {
                            " Client Name ": client_list,
                            " MAC ": self.macid_list,
                            " SSID ": self.ssid_list,
                            " BSSID ": self.bssid_list,
                            " Channel ": self.channels_list,
                            " RSSI ": self.rssi_list,
                            " Type of traffic ": vo_tos_list,
                            " Offered upload rate ": upload_list,
                            " Offered download rate ": download_list,
                            " Observed average upload rate ": individual_avgupload_list,
                            " Observed average download rate": individual_avgdownload_list
                        }
                        vo_dataframe[" Observed Upload Drop (%)"] = individual_drop_b_list
                        vo_dataframe[" Observed Download Drop (%)"] = individual_drop_a_list
                        if self.expected_passfail_val or self.csv_name:
                            vo_dataframe[" Expected " + self.direction + " rate(Mbps)"] = test_input_list
                            vo_dataframe[" Status "] = pass_fail_list
                        dataframe4 = pd.DataFrame(vo_dataframe)
                        report.set_table_dataframe(dataframe4)
                        report.build_table()
                logger.info("Graph and table for VO tos are built")

            if self.dowebgui and self.get_live_view and not multicast_exists:
                if not self.robot_test:
                    for _floor, rssi_image_path in rssi_images.items():
                        if os.path.exists(rssi_image_path):
                            report.set_custom_html('<div style="page-break-before: always;"></div>')
                            report.build_custom()
                            report.set_custom_html(f'<img src="file://{rssi_image_path}" style="width: 1000px; height: 800px;"></img>')
                            report.build_custom()
        else:
            print("No individual graph to generate.")
        # storing overall throughput CSV in the report directory
        logger.info('Storing real time values in a CSV')
        df1 = pd.DataFrame(self.overall)
        df1.to_csv('{}/overall_throughput{}.csv'.format(report.path_date_time, graph_no))

        # create CX CSV folder path
        cx_csv_dir = os.path.join(report.path_date_time, "RealTime CX CSV'S")
        # create directory if not exists
        os.makedirs(cx_csv_dir, exist_ok=True)
        # storing real time data for CXs in separate CSVs
        for cx in self.real_time_data:
            for tos in self.real_time_data[cx]:
                if tos in self.tos and len(self.real_time_data[cx][tos]['time']) != 0:
                    try:
                        cx_df = pd.DataFrame(self.real_time_data[cx][tos])
                        cx_df.to_csv(
                            os.path.join(cx_csv_dir, f"{cx}_{tos}_realtime_data{graph_no}.csv"),
                            index=False
                        )
                    except Exception:
                        logger.info(f'failed cx {cx} tos {tos}')
                        logger.info(f"Overall Data : {self.real_time_data}")

    def generate_individual_graph_virtual(self, res, report):
        rate_down = str(str(int(self.cx_profile.side_b_min_bps) / 1000000) + ' ' + 'Mbps')
        rate_up = str(str(int(self.cx_profile.side_a_min_bps) / 1000000) + ' ' + 'Mbps')
        n = len(self.sta_list)
        x_fig_size = 15
        y_fig_size = n * 0.5 + 4
        traffic_type = (self.traffic_type.strip("lf_")).upper()
        tos_labels = ['Background', 'Besteffort', 'Video', 'Voice']

        # All fixed lists are sized to n once — never appended to
        upload_list = [rate_up] * n
        download_list = [rate_down] * n
        traffic_type_list = [traffic_type] * n
        traffic_direction_list = [self.direction] * n
        bk_tos_list = [tos_labels[0]] * n
        be_tos_list = [tos_labels[1]] * n
        vi_tos_list = [tos_labels[2]] * n
        vo_tos_list = [tos_labels[3]] * n

        # Pad / truncate any auxiliary list to exactly n items
        def _safe(lst, fill='-'):
            lst = list(lst) if lst else []
            return (lst + [fill] * n)[:n]

        mac_list_n = _safe(self.macid_list)
        channel_list_n = _safe(self.channels_list)
        ssid_list_n = _safe(self.ssid_list)
        rssi_list_n = _safe(self.rssi_list)
        mode_list_n = _safe(self.mode_list)
        bssid_list_n = _safe(self.bssid_list)

        # Bi-direction running totals — flat lists: [dl_total, ul_total]
        # Matches throughput_qos.py list[0..3] exactly
        list_vi = []
        list_vo = []
        list_bk = []
        list_be = []
        load = ""
        data_set = {}

        # Per-TOS per-station values for Upload / Download table column
        tos_dl = {}
        tos_ul = {}
        drop_dl = {'BK': [], 'BE': [], 'VI': [], 'VO': []}
        drop_ul = {'BK': [], 'BE': [], 'VI': [], 'VO': []}

        # Virtual Scenario Only: data is band-keyed → res[case]['test_results']
        # Both scenario:      data is flat       → res['test_results']
        # _get_case_res() returns the inner dict that holds 'test_results'
        # for whichever structure is present, making the loop below work
        # identically for both.

        def _get_case_res(res, case):
            if 'test_results' in res:
                return res           # flat path (Both)
            if case in res and 'test_results' in res[case]:
                return res[case]     # band-keyed path (Virtual standalone)
            # fallback: search for any key containing test_results
            for v in res.values():
                if isinstance(v, dict) and 'test_results' in v:
                    return v
            return res               # last resort — will raise naturally

        test_cases = list(self.test_case) if self.test_case else ['default']

        for case in test_cases:
            case = case.strip()
            cr = _get_case_res(res, case)   # resolved inner dict

            if self.direction == 'Upload':
                load = rate_up
                tos_ul = cr['test_results'][0][1]   # {rate_up: {...}}
                data_set = tos_ul
                for tk in ['BK', 'BE', 'VI', 'VO']:
                    drop_ul[tk] = cr['test_results'][0][2]['drop_per']['rx_drop_b'].get(tk, [])

            elif self.direction == 'Download':
                load = rate_down
                tos_dl = cr['test_results'][0][0]   # {rate_down: {...}}
                data_set = tos_dl
                for tk in ['BK', 'BE', 'VI', 'VO']:
                    drop_dl[tk] = cr['test_results'][0][2]['drop_per']['rx_drop_a'].get(tk, [])

            elif self.direction == 'Bi-direction':
                load = 'Upload' + ':' + rate_up + ',' + 'Download' + ':' + rate_down
                dl_dict = cr['test_results'][0][0]   # {rate_down: {...}}
                ul_dict = cr['test_results'][0][1]   # {rate_up:   {...}}
                data_set = dl_dict
                # Accumulate totals: first from download keys, then upload keys
                for key in dl_dict:
                    list_vi.append(dl_dict[key]['VI'])
                    list_vo.append(dl_dict[key]['VO'])
                    list_bk.append(dl_dict[key]['BK'])
                    list_be.append(dl_dict[key]['BE'])
                for key in ul_dict:
                    list_vi.append(ul_dict[key]['VI'])
                    list_vo.append(ul_dict[key]['VO'])
                    list_bk.append(ul_dict[key]['BK'])
                    list_be.append(ul_dict[key]['BE'])
                for tk in ['BK', 'BE', 'VI', 'VO']:
                    drop_dl[tk] = cr['test_results'][0][2]['drop_per']['rx_drop_a'].get(tk, [])
                    drop_ul[tk] = cr['test_results'][0][2]['drop_per']['rx_drop_b'].get(tk, [])

        # Remove throughput_table_df / graph_df so iteration keys are clean
        res.pop("throughput_table_df", None)
        res.pop("graph_df", None)

        # Convert a value to a per-station Mbps string list of length n
        def _mbps_list(vals):
            if isinstance(vals, list):
                return _safe([str(round(float(v), 2)) + ' Mbps' for v in vals], '0.0 Mbps')
            # scalar — replicate for all stations
            return [str(round(float(vals), 2)) + ' Mbps'] * n

        # ── Per-TOS section builder — mirrors throughput_qos.py exactly ── #
        def _tos_section(tos_key, tos_list):
            if tos_key not in self.tos:
                return

            bidi_map = {'VI': list_vi, 'VO': list_vo, 'BK': list_bk, 'BE': list_be}

            if self.direction == 'Bi-direction':
                # throughput_qos.py: individual_set = list[2]  (the raw flat list)
                # NOT [list[2]] — the flat list itself is passed as _data_set
                individual_set = bidi_map[tos_key]
                individual_download_list = individual_set[0] if individual_set else 0.0
                individual_upload_list = individual_set[1] if len(individual_set) > 1 else 0.0
                colors = {'BK': ['orange', 'wheat'], 'BE': ['lightcoral', 'mistyrose'],
                          'VI': ['steelblue', 'lightskyblue'], 'VO': ['grey', 'lightgrey']}[tos_key]
                labels = ['Download', 'Upload']
                ind_drop_a = _safe([str(round(v, 2)) for v in drop_dl[tos_key]], '0.0')
                ind_drop_b = _safe([str(round(v, 2)) for v in drop_ul[tos_key]], '0.0')

            else:
                # throughput_qos.py: individual_set = [data_set[load][tos_key]]
                # data_set[load] is the inner tos dict; data_set[load][tos_key] is a list
                val = data_set.get(load, {}).get(tos_key, [])
                individual_set = [val]
                colors = {'BK': ['orange'], 'BE': ['violet'],
                          'VI': ['steelblue'], 'VO': ['grey']}[tos_key]
                labels = [tos_key]

                if self.direction == 'Upload':
                    individual_upload_list = val
                    individual_download_list = []
                    ind_drop_a = ['0.0'] * n
                    ind_drop_b = _safe([str(round(v, 2)) for v in drop_ul[tos_key]], '0.0')
                else:
                    individual_download_list = val
                    individual_upload_list = []
                    ind_drop_a = _safe([str(round(v, 2)) for v in drop_dl[tos_key]], '0.0')
                    ind_drop_b = ['0.0'] * n

            # Objective text
            report.set_obj_html(
                _obj_title=f"Individual {self.direction} throughput with intended load {load}/station for traffic {tos_key}(WiFi).",
                _obj=f"The below graph represents individual throughput for {n} clients running {tos_key} "
                f"(WiFi) traffic.  Y-axis shows \u201cClient names\u201d and X-axis shows "
                f"\u201cThroughput in Mbps\u201d.")
            report.build_objective()

            graph = lf_bar_graph_horizontal(
                _data_set=individual_set,
                _xaxis_name="Throughput in Mbps",
                _yaxis_name="Client names",
                _yaxis_categories=list(self.sta_list),
                _yaxis_label=list(self.sta_list),
                _label=labels,
                _yaxis_step=1,
                _yticks_font=8,
                _yticks_rotation=None,
                _graph_title=f"Individual {self.direction} throughput for {tos_key}(WIFI) traffic",
                _title_size=16,
                _figsize=(x_fig_size, y_fig_size),
                _legend_loc="best",
                _legend_box=(1.0, 1.0),
                _color_name=colors,
                _show_bar_value=True,
                _enable_csv=True,
                _graph_image_name=f"{tos_key.lower()}_{self.direction}",
                _color_edge=['black'],
                _color=colors)
            graph_png = graph.build_bar_graph_horizontal()
            print("graph name {}".format(graph_png))
            report.set_graph_image(graph_png)
            report.move_graph_image()
            report.set_csv_filename(graph_png)
            report.move_csv_file()
            report.build_graph()

            # Table observed rate strings
            avg_ul_str = _mbps_list(individual_upload_list) if individual_upload_list else ['0.0 Mbps'] * n
            avg_dl_str = _mbps_list(individual_download_list) if individual_download_list else ['0.0 Mbps'] * n

            report.set_table_title(f" TOS : {tos_labels[['BK', 'BE', 'VI', 'VO'].index(tos_key)]} ")
            report.build_table_title()

            df_data = {
                " Client Name ": list(self.sta_list),
                " Mac ": mac_list_n,
                " SSID ": ssid_list_n,
                " BSSID ": bssid_list_n,
                " Mode ": mode_list_n,
                " Channel": channel_list_n,
                " RSSI ": rssi_list_n,
                " Type of traffic ": tos_list,
                " Traffic Direction ": traffic_direction_list,
                " Traffic Protocol ": traffic_type_list,
                " Offered upload rate(Mbps) ": upload_list,
                " Offered download rate(Mbps) ": download_list,
                " Observed upload rate(Mbps) ": avg_ul_str,
                " Observed download rate(Mbps)": avg_dl_str,
            }
            if self.direction == "Bi-direction":
                df_data[" Observed Upload Drop (%)"] = ind_drop_b
                df_data[" Observed Download Drop (%)"] = ind_drop_a
            elif self.direction == "Upload":
                df_data[" Observed Upload Drop (%)"] = ind_drop_b
                df_data[" Observed Download Drop (%)"] = ['0.0'] * n
            elif self.direction == "Download":
                df_data[" Observed Upload Drop (%)"] = ['0.0'] * n
                df_data[" Observed Download Drop (%)"] = ind_drop_a

            dataframe = pd.DataFrame(df_data)
            report.set_table_dataframe(dataframe)
            report.build_table()

        _tos_section("BK", bk_tos_list)
        _tos_section("BE", be_tos_list)
        _tos_section("VI", vi_tos_list)
        _tos_section("VO", vo_tos_list)

        # create CX CSV folder path
        cx_csv_dir = os.path.join(report.path_date_time, "RealTime CX CSV'S")
        # create directory if not exists
        os.makedirs(cx_csv_dir, exist_ok=True)
        # storing real time data for CXs in separate CSVs
        for cx in self.real_time_data:
            for tos in self.real_time_data[cx]:
                if tos in self.tos and len(self.real_time_data[cx][tos]['time']) != 0:
                    try:
                        cx_df = pd.DataFrame(self.real_time_data[cx][tos])
                        cx_df.to_csv(
                            os.path.join(cx_csv_dir, f"{cx}_{tos}_realtime_data.csv"),
                            index=False
                        )
                    except Exception:
                        logger.info(f'failed cx {cx} tos {tos}')

        # Store overall throughput CSV in report directory
        logger.info('Storing real time values in a CSV (virtual)')
        df1 = pd.DataFrame(self.overall)
        if hasattr(report, 'path_date_time') and report.path_date_time:
            df1.to_csv('{}/overall_throughput.csv'.format(report.path_date_time))

    def get_pass_fail_list(self, test_input_list, individual_avgupload_list, individual_avgdownload_list):
        pass_fail_list = []
        for i in range(len(test_input_list)):
            if self.csv_direction.split('_')[2] == 'BiDi':
                if float(test_input_list[i]) <= float(individual_avgupload_list[i].split(' ')[0]) + float(individual_avgdownload_list[i].split(' ')[0]):
                    pass_fail_list.append('PASS')
                else:
                    pass_fail_list.append('FAIL')
            elif self.csv_direction.split('_')[2] == 'UL':
                if float(test_input_list[i]) <= float(individual_avgupload_list[i].split(' ')[0]):
                    pass_fail_list.append('PASS')
                else:
                    pass_fail_list.append('FAIL')
            else:
                if float(test_input_list[i]) <= float(individual_avgdownload_list[i].split(' ')[0]):
                    pass_fail_list.append('PASS')
                else:
                    pass_fail_list.append('FAIL')
        return pass_fail_list

    def get_csv_expected_val(self):
        res_list = []
        test_input_list = []
        interop_tab_data = self.json_get('/adb/')["devices"]
        for client in self.real_client_list:
            if client.split(' ')[1] != 'android':
                res_list.append(client.split(' ')[2])
            else:
                for dev in interop_tab_data:
                    for item in dev.values():
                        if item['user-name'] == client.split(' ')[2]:
                            res_list.append(item['name'].split('.')[2])

        with open(self.csv_name, mode='r') as file:
            reader = csv.DictReader(file)
            rows = list(reader)
        for device in res_list:
            found = False
            for row in rows:
                if row['DeviceList'] == device and row[self.csv_direction + ' Mbps'].strip() != '':
                    test_input_list.append(row[self.csv_direction + ' Mbps'])
                    found = True
                    break
            if not found:
                logging.error(f"{self.csv_direction} value for Device {device} not found in CSV. Using default value 0.3")
                test_input_list.append(0.3)
        return test_input_list

    def copy_reports_to_home_dir(self):
        curr_path = self.result_dir
        home_dir = os.path.expanduser("~")
        out_folder_name = "WebGui_Reports"
        new_path = os.path.join(home_dir, out_folder_name)
        # webgui directory creation
        if not os.path.exists(new_path):
            os.makedirs(new_path)
        test_name = self.test_name
        test_name_dir = os.path.join(new_path, test_name)
        # in webgui-reports DIR creating a directory with test name
        if not os.path.exists(test_name_dir):
            os.makedirs(test_name_dir)
        shutil.copytree(curr_path, test_name_dir, dirs_exist_ok=True)

    def generate_individual_coordinate(self, report, data, connections_download_avg, connections_upload_avg, avg_drop_a, avg_drop_b, coordinate, angle):
        """
        Processes QoS data and generates a report (table and bar graph) for a
        specific robot coordinate and rotation angle.
        """
        res = self.set_report_data(data)
        data_set, load, res = self.generate_graph_data_set(data)
        report.set_table_title(
            f"Overall {self.direction} Throughput for all TOS i.e BK | BE | Video (VI) | Voice (VO)")
        report.build_table_title()
        df_throughput = pd.DataFrame(res["throughput_table_df"])
        report.set_table_dataframe(df_throughput)
        report.build_table()
        for _key in res["graph_df"]:
            report.set_obj_html(
                _obj_title=f"Overall {self.direction} throughput for {len(self.input_devices_list)} clients with different TOS.",
                _obj=f"The below graph represents overall {self.direction} throughput for all "
                "connected stations running BK, BE, VO, VI traffic with different "
                f"intended loads{load} per tos")
        report.build_objective()
        if self.rotation_enabled:
            graph_image_name = f"tos_{_key}_coord{self.coordinate_list[coordinate]}_angle{self.rotation_list[angle]}Hz"
            graph_title = f"Overall {self.direction} throughput – BK,BE,VO,VI traffic streams at Coordinate: {self.coordinate_list[coordinate]} | Rotation Angle: {self.rotation_list[angle]}°"
            graph_no = "_{}_{}".format(self.coordinate_list[coordinate], self.rotation_list[angle])
        else:
            graph_image_name = f"tos_{_key}_coord{self.coordinate_list[coordinate]}Hz"
            graph_title = f"Overall {self.direction} throughput – BK,BE,VO,VI traffic streams at Coordinate: {self.coordinate_list[coordinate]}"
            graph_no = "_{}".format(self.coordinate_list[coordinate])
        graph = lf_bar_graph(_data_set=data_set,
                             _xaxis_name="Load per Type of Service",
                             _yaxis_name="Throughput (Mbps)",
                             _xaxis_categories=["BK,BE,VI,VO"],
                             _xaxis_label=['1 Mbps', '2 Mbps', '3 Mbps', '4 Mbps', '5 Mbps'],
                             _graph_image_name=graph_image_name,
                             _label=["BK", "BE", "VI", "VO"],
                             _xaxis_step=1,
                             _graph_title=graph_title,
                             _title_size=16,
                             _color=['orange', 'lightcoral', 'steelblue', 'lightgrey'],
                             _color_edge='black',
                             _bar_width=0.15,
                             _figsize=(18, 6),
                             _legend_loc="best",
                             _legend_box=(1.0, 1.0),
                             _dpi=96,
                             _show_bar_value=True,
                             _enable_csv=True,
                             _color_name=['orange', 'lightcoral', 'steelblue', 'lightgrey'])
        graph_png = graph.build_bar_graph()
        print("graph name {}".format(graph_png))
        report.set_graph_image(graph_png)
        # need to move the graph image to the results directory
        report.move_graph_image()
        report.set_csv_filename(graph_png)
        report.move_csv_file()
        report.build_graph()
        self.generate_individual_graph(res, report, connections_download_avg, connections_upload_avg, avg_drop_a, avg_drop_b, graph_no=graph_no)

    def generate_report_for_robo(self, coordinate_list=None, angle_list=None, passed_coordinates=None):
        """
        Creates the final PDF and HTML report. It combines the results from every robot
        coordinate into one document.
        """
        self.ssid_list = self.get_ssid_list(self.input_devices_list)
        load = ''
        rate_down = str(str(int(self.cx_profile.side_b_min_bps) / 1000000) + ' ' + 'Mbps')
        rate_up = str(str(int(self.cx_profile.side_a_min_bps) / 1000000) + ' ' + 'Mbps')
        if self.direction == 'Upload':
            load = rate_up
        else:
            if self.direction == "Download":
                load = rate_down
        # res = self.set_report_data(data)
        if self.direction == "Bi-direction":
            load = 'Upload' + ':' + rate_up + ',' + 'Download' + ':' + rate_down
        # if selected_real_clients_names is not None:
        #     self.num_stations = selected_real_clients_names
        # data_set, load, res = self.generate_graph_data_set(data)
        report = lf_report(_output_pdf="interop_qos.pdf", _output_html="interop_qos.html", _path=self.result_dir,
                           _results_dir_name="Qos_Test_report")
        report_path = report.get_path()
        report_path_date_time = report.get_path_date_time()
        print("path: {}".format(report_path))
        print("path_date_time: {}".format(report_path_date_time))
        report.set_title("Interop QOS")
        report.build_banner()
        # objective title and description
        report.set_obj_html(_obj_title="Objective",
                            _obj="The objective of the QoS (Quality of Service) traffic throughput test is to measure the maximum"
                            " achievable throughput of a network under specific QoS settings and conditions.By conducting"
                            " this test, we aim to assess the capacity of network to handle high volumes of traffic while"
                            " maintaining acceptable performance levels,ensuring that the network meets the required QoS"
                            " standards and can adequately support the expected user demands.")
        report.build_objective()
        # Initialize counts and lists for device types
        android_devices, windows_devices, linux_devices, ios_devices, ios_mob_devices = 0, 0, 0, 0, 0
        all_devices_names = []
        device_type = []
        total_devices = ""
        for i in self.real_client_list:
            split_device_name = i.split(" ")
            if 'android' in split_device_name:
                all_devices_names.append(split_device_name[2] + ("(Android)"))
                device_type.append("Android")
                android_devices += 1
            elif 'Win' in split_device_name:
                all_devices_names.append(split_device_name[2] + ("(Windows)"))
                device_type.append("Windows")
                windows_devices += 1
            elif 'Lin' in split_device_name:
                all_devices_names.append(split_device_name[2] + ("(Linux)"))
                device_type.append("Linux")
                linux_devices += 1
            elif 'Mac' in split_device_name:
                all_devices_names.append(split_device_name[2] + ("(Mac)"))
                device_type.append("Mac")
                ios_devices += 1
            elif 'iOS' in split_device_name:
                all_devices_names.append(split_device_name[2] + ("(iOS)"))
                device_type.append("iOS")
                ios_mob_devices += 1

        # Build total_devices string based on counts
        if android_devices > 0:
            total_devices += f" Android({android_devices})"
        if windows_devices > 0:
            total_devices += f" Windows({windows_devices})"
        if linux_devices > 0:
            total_devices += f" Linux({linux_devices})"
        if ios_devices > 0:
            total_devices += f" Mac({ios_devices})"
        if ios_mob_devices > 0:
            total_devices += f" iOS({ios_mob_devices})"

        # Test setup information table for devices in device list
        if self.qos_data["configuration"] == "" or self.qos_data["configuration"] == {}:
            test_setup_info = {
                "Device List": ", ".join(all_devices_names),
                "Number of Stations": "Total" + f"({self.num_stations})" + total_devices,
                "AP Model": self.ap_name,
                "SSID": self.ssid,
                "Traffic Duration in hours": round(int(self.test_duration) / 3600, 2),
                "Security": self.security,
                "Protocol": (self.traffic_type.strip("lf_")).upper(),
                "Traffic Direction": self.direction,
                "TOS": self.tos,
                "Per TOS Load in Mbps": load,
                "Coordinates": self.coordinate_list
            }
            if self.rotation_enabled:
                test_setup_info["Rotations"] = self.rotation_list
        # Test setup information table for devices in groups
        else:
            group_names = ', '.join(self.qos_data["configuration"].keys())
            profile_names = ', '.join(self.qos_data["configuration"].values())
            configmap = "Groups:" + group_names + " -> Profiles:" + profile_names
            test_setup_info = {
                "AP Model": self.ap_name,
                'Configuration': configmap,
                "Traffic Duration in hours": round(int(self.test_duration) / 3600, 2),
                "Security": self.security,
                "Protocol": (self.traffic_type.strip("lf_")).upper(),
                "Traffic Direction": self.direction,
                "TOS": self.tos,
                "Per TOS Load in Mbps": load
            }
        report.test_setup_table(test_setup_data=test_setup_info, value="Test Configuration")
        if self.dowebgui:
            tos_for_report = self.tos
            tos_images, rssi_images = self.get_live_view_images()
            for tos_val in tos_for_report:
                for image_path in tos_images[tos_val]:
                    report.set_custom_html('<div style="page-break-before: always;"></div>')
                    report.build_custom()
                    report.set_custom_html(f'<img src="file://{image_path}" style="width: 1200px; height: 800px;"></img>')
                    report.build_custom()
            for _floor, rssi_image_path in rssi_images.items():
                if os.path.exists(rssi_image_path):
                    report.set_custom_html('<div style="page-break-before: always;"></div>')
                    report.build_custom()
                    report.set_custom_html(f'<img src="file://{rssi_image_path}" style="width: 1000px; height: 800px;"></img>')
                    report.build_custom()

        for coordinate in range(len(passed_coordinates)):
            if self.rotation_enabled:
                for angle in range(len(self.rotation_list)):
                    report.set_obj_html(_obj_title=f"Coordinate: {self.coordinate_list[coordinate]} | Rotation Angle: {self.rotation_list[angle]}°",
                                        _obj="")
                    report.build_objective()
                    data = self.qos_data[self.coordinate_list[coordinate]][self.rotation_list[angle]]["data"]
                    connections_download_avg = self.qos_data[self.coordinate_list[coordinate]][self.rotation_list[angle]]["connections_download_avg"]
                    connections_upload_avg = self.qos_data[self.coordinate_list[coordinate]][self.rotation_list[angle]]["connections_upload_avg"]
                    avg_drop_a = self.qos_data[self.coordinate_list[coordinate]][self.rotation_list[angle]]["avg_drop_a"]
                    avg_drop_b = self.qos_data[self.coordinate_list[coordinate]][self.rotation_list[angle]]["avg_drop_b"]
                    self.generate_individual_coordinate(report, data, connections_download_avg, connections_upload_avg, avg_drop_a, avg_drop_b, coordinate, angle)
            else:
                report.set_obj_html(_obj_title=f"Coordinate: {self.coordinate_list[coordinate]}",
                                    _obj="")
                report.build_objective()
                data = self.qos_data[self.coordinate_list[coordinate]]["data"]
                connections_download_avg = self.qos_data[self.coordinate_list[coordinate]]["connections_download_avg"]
                connections_upload_avg = self.qos_data[self.coordinate_list[coordinate]]["connections_upload_avg"]
                avg_drop_a = self.qos_data[self.coordinate_list[coordinate]]["avg_drop_a"]
                avg_drop_b = self.qos_data[self.coordinate_list[coordinate]]["avg_drop_b"]
                self.generate_individual_coordinate(report, data, connections_download_avg, connections_upload_avg, avg_drop_a, avg_drop_b, coordinate, None)
        input_setup_info = {
            "contact": "support@candelatech.com"
        }
        report.test_setup_table(test_setup_data=input_setup_info, value="Information")
        report.build_footer()
        report.write_html()
        report.write_pdf()

    def get_bandsteering_stats(self, report=None, data=None):
        """
        Generate Band Steering statistics and reports for each device.

        This function processes per-device connection data to:
        - Detect BSSID transitions (band steering events)
        - Count occurrences of each configured BSSID
        - Generate a bar graph showing BSSID change counts
        - Create a detailed table of band steering events (if any)

        Args:
            data (dict): {
                dev_name: pandas.DataFrame,
                ...
            }

            report (lf_report object)

        Expected DataFrame Columns:
            - timestamp
            - BSSID
            - Channel
            - from_coordinate
            - to_coordinate

        Behavior:
            - Considers only BSSID changes within the configured list (self.bssids)
            - Ignores consecutive duplicate BSSID entries
            - Skips table generation if no valid band steering events are found
            - Always generates a graph (even if counts are zero)

        Output:
            Adds band steering statistics to the report for each device, including:
            - Bar graph of BSSID change counts per device
            - Table of band steering transitions)
        """

        df = pd.DataFrame(data)

        rename_map = {
            "timestamp": "TIMESTAMP",
            "from_coordinate": "From Coordinate",
            "to_coordinate": "To Coordinate",
        }
        df.rename(columns=rename_map, inplace=True)

        bssid_cols = [c for c in df.columns if "BSSID" in c]
        channel_cols = [c for c in df.columns if "Channel" in c]

        for col in bssid_cols:
            # Create a mask to detect valid BSSID transitions:
            # - BSSID changes compared to previous row
            # - BSSID belongs to configured list
            allowed_bssids = set(self.bssids)

            mask = (
                (df[col] != df[col].shift()) &
                (df[col].isin(allowed_bssids))
            )

            skip_table = not mask.any()

            if skip_table:
                # Initialize all BSSID counts to zero if no events found
                bssid_counts = {bssid: 0 for bssid in self.bssids}
            else:
                bssid_list = df.loc[mask, col].tolist()
                timestamp_list = df.loc[mask, "TIMESTAMP"].tolist()
                from_coordinate_list = df.loc[mask, "From Coordinate"].tolist()
                to_coordinate_list = df.loc[mask, "To Coordinate"].tolist()
                bssid_counts = Counter(bssid_list)
            # Ensure all configured BSSIDs are present in final count (default = 0
            final_bssid_counts = {
                bssid: bssid_counts.get(bssid, 0)
                for bssid in self.bssids
            }

            x_axis = list(final_bssid_counts.keys())
            y_axis = [[float(v)] for v in final_bssid_counts.values()]

            device_name = col.replace("BSSID", "").strip()
            channel_col = next(
                (c for c in channel_cols if device_name in c), None
            )

            channel_list = (
                df.loc[mask, channel_col].tolist()
                if channel_col and not skip_table else []
            )

            report.set_obj_html(
                _obj_title=f"BSSID Change Count Of The Client {device_name}",
                _obj=" "
            )
            report.build_objective()

            graph = lf_bar_graph(
                _data_set=y_axis,
                _xaxis_name="BSSID",
                _yaxis_name="Number of Changes",
                _xaxis_categories=[""],
                _xaxis_label=x_axis,
                _graph_image_name=f"bssid_change_count_{device_name}",
                _label=x_axis,
                _xaxis_step=1,
                _graph_title=f"BSSID change count for device :  {device_name}",
                _title_size=16,
                _bar_width=0.15,
                _figsize=(18, 6),
                _dpi=96,
                _show_bar_value=True,
                _enable_csv=True,
            )

            graph_png = graph.build_bar_graph()
            report.set_graph_image(graph_png)
            report.move_graph_image()
            report.set_csv_filename(graph_png)
            report.move_csv_file()
            report.build_graph()

            # If no band steering events, show informational message
            if skip_table:
                report.set_obj_html(
                    _obj_title=f"Band Steering Results for {device_name}",
                    _obj="No band steering events observed for the configured BSSID list."
                )
                report.build_objective()
                continue

            report.set_obj_html(
                _obj_title=f"Band Steering Results for {device_name}",
                _obj=" "
            )
            report.build_objective()

            table_df = pd.DataFrame({
                "BSSID": bssid_list,
                "Channel": channel_list,
                "Timestamp": timestamp_list,
                "From Coordinate": from_coordinate_list,
                "To Coordinate": to_coordinate_list
            })

            report.set_table_dataframe(table_df)
            report.build_table()

    def perform_robo(self):
        """
        It handles moving the robot to each coordinate,
        checking battery levels, rotating at each spot, and collecting Wi-Fi
        performance data to build the final report.
        """
        if (self.rotation_list[0] != ""):
            self.rotation_enabled = True
        # coordinate list to track coordinates where the test needs to be triggered
        coord_list = []
        test_stopped_by_user = False
        if self.coordinate:
            coord_list = self.coordinate_list
            if self.dowebgui:
                base_dir = os.path.dirname(os.path.dirname(self.result_dir))
                nav_data = os.path.join(base_dir, 'nav_data.json')
                with open(nav_data, "w") as file:
                    json.dump({}, file)
                self.robot.nav_data_path = nav_data
                self.robot.runtime_dir = self.result_dir
                self.robot.ip = self.host
                self.robot.testname = self.test_name
            passed_coord_list = []
            abort = False
        if self.do_bandsteering:
            self.overall = []
            self.df_for_webui = []
            cycle_coords = self.robot.get_coordinates_list()
            self.start(False, False)
            if (len(cycle_coords) == 0):
                logger.info("Test aborted")
                exit(0)
            self.robot.do_bandsteering = True
            cycles = self.cycles
            curr_cycle = 1
            logger.info("Current Cycle {}".format(curr_cycle))
            for coordinate in cycle_coords:
                if self.test_stopped_by_user:
                    break
                # Before moving to next coordinate, check if battery is sufficient
                pause_coord, test_stopped_by_user, band_steering_data = self.robot.wait_for_battery(monitor_function=lambda: self.monitor())
                if test_stopped_by_user:
                    break
                matched, abort, band_steering_data = self.robot.move_to_coordinate(
                    coordinate,
                    monitor_function=lambda: self.monitor()
                )
                if matched:
                    logger.info("Reached the coordinate {}".format(coordinate))
                    if coordinate == coord_list[0]:
                        curr_cycle += 1
                        if curr_cycle > cycles:
                            logger.info("Completed all {} cycles".format(self.cycles))
                        else:
                            logger.info("current cycle {}".format(curr_cycle))
                if abort:
                    break
            self.stop()
            upload = []
            download = []
            drop_a = []
            drop_b = []
            avg_upload = []
            avg_download = []
            avg_drop_a = []
            avg_drop_b = []
            [(upload.append([]), download.append([]), drop_a.append([]), drop_b.append([]), avg_upload.append([]), avg_download.append([]), avg_drop_a.append([]), avg_drop_b.append([])) for i in
             range(len(self.cx_profile.created_cx))]
            dropa_connections = dict.fromkeys(list(self.cx_profile.created_cx.keys()), float(0))
            dropb_connections = dict.fromkeys(list(self.cx_profile.created_cx.keys()), float(0))
            connections_upload = dict.fromkeys(list(self.cx_profile.created_cx.keys()), float(0))
            connections_download = dict.fromkeys(list(self.cx_profile.created_cx.keys()), float(0))
            connections_upload_avg = dict.fromkeys(list(self.cx_profile.created_cx.keys()), float(0))
            connections_download_avg = dict.fromkeys(list(self.cx_profile.created_cx.keys()), float(0))
            # # rx_rate list is calculated
            for thpt in self.throughput_data:
                for ind, _k in enumerate(thpt):
                    avg_upload[ind].append(thpt[ind][1])
                    avg_download[ind].append(thpt[ind][0])
                    avg_drop_a[ind].append(thpt[ind][2])
                    avg_drop_b[ind].append(thpt[ind][3])
                    upload[ind].append(thpt[ind][1])
                    download[ind].append(thpt[ind][0])
                    drop_a[ind].append(thpt[ind][2])
                    drop_b[ind].append(thpt[ind][3])

            # Rounding of the results upto 2 decimals
            upload_throughput = [float(f"{(sum(i) / 1000000) / len(i): .2f}") for i in upload]
            download_throughput = [float(f"{(sum(i) / 1000000) / len(i): .2f}") for i in download]
            drop_a_per = [float(round(sum(i) / len(i), 2)) for i in drop_a]
            drop_b_per = [float(round(sum(i) / len(i), 2)) for i in drop_b]
            avg_upload_throughput = [float(f"{(sum(i) / 1000000) / len(i): .2f}") for i in avg_upload]
            avg_download_throughput = [float(f"{(sum(i) / 1000000) / len(i): .2f}") for i in avg_download]
            avg_drop_a_per = [float(round(sum(i) / len(i), 2)) for i in avg_drop_a]
            avg_drop_b_per = [float(round(sum(i) / len(i), 2)) for i in avg_drop_b]
            keys = list(connections_download.keys())
            # Updated the calculated values to the respective connections in dictionary
            for i in range(len(download_throughput)):
                connections_download.update({keys[i]: download_throughput[i]})
            for i in range(len(upload_throughput)):
                connections_upload.update({keys[i]: upload_throughput[i]})
            for i in range(len(avg_download_throughput)):
                connections_download_avg.update({keys[i]: avg_download_throughput[i]})
            for i in range(len(avg_upload_throughput)):
                connections_upload_avg.update({keys[i]: avg_upload_throughput[i]})
            for i in range(len(avg_drop_a_per)):
                dropa_connections.update({keys[i]: avg_drop_a_per[i]})
            for i in range(len(avg_drop_b_per)):
                dropb_connections.update({keys[i]: avg_drop_b_per[i]})
            logger.info("connections download {}".format(connections_download))
            logger.info("connections {}".format(connections_upload))
            test_results = {'test_results': []}
            data = {}
            test_results['test_results'].append(self.evaluate_qos(connections_download, connections_upload, drop_a_per, drop_b_per))
            data.update(test_results)
            input_setup_info = {
                "contact": "support@candelatech.com"
            }
            if self.dowebgui == "True":
                last_entry = self.overall[len(self.overall) - 1]
                last_entry["status"] = "Stopped"
                last_entry["timestamp"] = datetime.now().strftime("%d/%m %I:%M:%S %p")
                last_entry["remaining_time"] = "0"
                last_entry["end_time"] = last_entry["timestamp"]
                self.band_steering_df.append(
                    last_entry
                )
                df1 = pd.DataFrame(self.band_steering_df)
                df1.to_csv('{}/overall_throughput.csv'.format(self.result_dir, ), index=False)
            self.generate_report(
                data=data,
                input_setup_info=input_setup_info,
                report_path=self.result_dir,
                connections_upload_avg=connections_upload_avg,
                connections_download_avg=connections_download_avg,
                avg_drop_a=dropa_connections,
                avg_drop_b=dropb_connections)
            return
        for coordinate in coord_list:
            if self.robot_ip:
                if self.test_stopped_by_user:
                    break
                # Before moving to next coordinate, check if battery is sufficient
                pause_coord, test_stopped_by_user = self.robot.wait_for_battery()
                if test_stopped_by_user:
                    break
                matched, abort = self.robot.move_to_coordinate(coordinate)

                if matched:
                    logger.info("Reached the coordinate {}".format(coordinate))
                if abort:
                    break
                passed_coord_list.append(coordinate)

                if matched:
                    self.overall = []
                    self.df_for_webui = []
                    # If rotations are not allowed
                    if not self.rotation_enabled:
                        test_results = {'test_results': []}
                        data = {}
                        input_setup_info = {
                            "contact": "support@candelatech.com"
                        }
                        self.current_coordinate = coordinate
                        self.start(False, False)
                        time.sleep(10)
                        connections_download, connections_upload, drop_a_per, drop_b_per, connections_download_avg, connections_upload_avg, avg_drop_a, avg_drop_b = self.monitor(
                            curr_coordinate=coordinate)
                        logger.info("connections download {}".format(connections_download))
                        logger.info("connections upload {}".format(connections_upload))
                        self.stop()
                        time.sleep(5)
                        test_results['test_results'].append(self.evaluate_qos(connections_download, connections_upload, drop_a_per, drop_b_per))
                        data.update(test_results)
                        params = {
                            "data": None,
                            "input_setup_info": None,
                            "connections_download_avg": None,
                            "connections_upload_avg": None,
                            "avg_drop_a": None,
                            "avg_drop_b": None,
                            "report_path": "",
                            "result_dir_name": "Qos_Test_report",
                            "selected_real_clients_names": None,
                            "config_devices": ""
                        }

                        params.update({
                            "data": data,
                            "input_setup_info": input_setup_info,
                            "report_path": (
                                self.result_dir
                                if self.dowebgui else ""
                            ),
                            "connections_upload_avg": connections_upload_avg,
                            "connections_download_avg": connections_download_avg,
                            "avg_drop_a": avg_drop_a,
                            "avg_drop_b": avg_drop_b
                        })
                        self.qos_data[coordinate] = params

                    # If rotations are enabled
                    else:
                        exit_from_monitor = False
                        for angle in range(len(self.rotation_list)):
                            test_results = {'test_results': []}
                            data = {}
                            input_setup_info = {
                                "contact": "support@candelatech.com"
                            }
                            self.last_rotated_angles = []
                            self.current_coordinate = coordinate
                            self.current_angle = self.angle_list[angle]
                            pause_angle, test_stopped_by_user = self.robot.wait_for_battery(stop=self.stop)
                            if test_stopped_by_user:
                                break
                            if pause_angle:
                                reached = self.robot.move_to_coordinate(coordinate)
                                if not reached:
                                    test_stopped_by_user = True
                                    break
                            final_angle = self.robot.angle_list[angle]
                            rotation = self.robot.rotate_angle(self.current_angle)
                            if not rotation:
                                exit_from_monitor = True
                            if exit_from_monitor:
                                break
                            if final_angle not in self.last_rotated_angles:
                                self.last_rotated_angles.append(final_angle)
                            self.start(False, False)
                            monitor_charge_time = datetime.now()
                            connections_download, connections_upload, drop_a_per, drop_b_per, connections_download_avg, connections_upload_avg, avg_drop_a, avg_drop_b = self.monitor(
                                curr_coordinate=coordinate, curr_rotation=self.current_angle, monitor_charge_time=monitor_charge_time)
                            logger.info("connections download {}".format(connections_download))
                            logger.info("connections upload {}".format(connections_upload))
                            self.stop()
                            time.sleep(5)
                            test_results['test_results'].append(self.evaluate_qos(connections_download, connections_upload, drop_a_per, drop_b_per))
                            data.update(test_results)
                            params = {
                                "data": None,
                                "input_setup_info": None,
                                "connections_download_avg": None,
                                "connections_upload_avg": None,
                                "avg_drop_a": None,
                                "avg_drop_b": None,
                                "report_path": "",
                                "result_dir_name": "Qos_Test_report",
                                "selected_real_clients_names": None,
                                "config_devices": ""
                            }

                            params.update({
                                "data": data,
                                "input_setup_info": input_setup_info,
                                "report_path": (
                                    self.result_dir
                                    if self.dowebgui else ""
                                ),
                                "connections_upload_avg": connections_upload_avg,
                                "connections_download_avg": connections_download_avg,
                                "avg_drop_a": avg_drop_a,
                                "avg_drop_b": avg_drop_b
                            })
                            if coordinate not in self.qos_data:
                                self.qos_data[coordinate] = {}
                            self.qos_data[coordinate][self.rotation_list[angle]] = params

        self.generate_report_for_robo(coordinate_list=coord_list, angle_list=self.rotation_list, passed_coordinates=passed_coord_list)

    def build_iot_report_section(self, report, iot_summary):
        """
        Handles all IoT-related charts, tables, and increment-wise reports.
        """
        outdir = report.path_date_time
        os.makedirs(outdir, exist_ok=True)

        def copy_into_report(raw_path, new_name):
            """Resolve and copy image into report dir."""
            if not raw_path:
                return None

            abs_src = os.path.abspath(raw_path)
            if not os.path.exists(abs_src):
                # Search recursively under 'results' if absolute path missing
                for root, _, files in os.walk(os.path.join(os.getcwd(), "results")):
                    if os.path.basename(raw_path) in files:
                        abs_src = os.path.join(root, os.path.basename(raw_path))
                        break
                else:
                    return None

            dst = os.path.join(outdir, new_name)
            if os.path.abspath(abs_src) != os.path.abspath(dst):
                shutil.copy2(abs_src, dst)
            return new_name

        # section header
        report.set_custom_html('<div style="page-break-before: always;"></div>')
        report.build_custom()
        report.set_custom_html('<h2><u>IoT Results</u></h2>')
        report.build_custom()

        # Statistics
        stats_png = copy_into_report(iot_summary.get("statistics_img"), "iot_statistics.png")
        if stats_png:
            report.build_chart_title("Test Statistics")
            report.set_custom_html(f'<img src="{stats_png}" style="width:100%; height:auto;">')
            report.build_custom()

        # Request vs Latency
        rvl_png = copy_into_report(iot_summary.get("req_vs_latency_img"), "iot_request_vs_latency.png")
        if rvl_png:
            report.build_chart_title("Request vs Average Latency")
            report.set_custom_html(f'<img src="{rvl_png}" style="width:100%;">')
            report.build_custom()

        # Overall results table
        ort = iot_summary.get("overall_result_table") or {}
        if ort:
            rows = [{
                "Device": dev,
                "Min Latency (ms)": stats.get("min_latency"),
                "Avg Latency (ms)": stats.get("avg_latency"),
                "Max Latency (ms)": stats.get("max_latency"),
                "Total Iterations": stats.get("total_iterations"),
                "Success Iters": stats.get("success_iterations"),
                "Failed Iters": stats.get("failed_iterations"),
                "No-Response Iters": stats.get("no_response_iterations"),
            } for dev, stats in ort.items()]

            df_overall = pd.DataFrame(rows).round(2)

            report.set_custom_html('<div style="page-break-inside: avoid;">')
            report.build_custom()
            report.set_obj_html(_obj_title="Overall IoT Result Table", _obj=" ")
            report.build_objective()
            report.set_table_dataframe(df_overall)
            report.build_table()
            report.set_custom_html('</div>')
            report.build_custom()

        # Increment reports
        inc = iot_summary.get("increment_reports") or {}
        if inc:
            report.set_custom_html('<h3>Reports by Increment Steps</h3>')
            report.build_custom()

            for step_name, rep in inc.items():

                report.set_custom_html(f'<h4><u>{step_name.replace("_", " ")}</u></h4>')
                report.build_custom()

                # Latency graph
                lat_png = copy_into_report(rep.get("latency_graph"), f"iot_{step_name}_latency.png")
                if lat_png:
                    report.build_chart_title("Average Latency")
                    report.set_custom_html(f'<img src="{lat_png}" style="width:100%; height:auto;">')
                    report.build_custom()

                # Success count graph
                res_png = copy_into_report(rep.get("result_graph"), f"iot_{step_name}_results.png")
                if res_png:
                    report.build_chart_title("Success Count")
                    report.set_custom_html(f'<img src="{res_png}" style="width:100%; height:auto;">')
                    report.build_custom()

                # Tabular data for detailed iteration-level results
                data_rows = rep.get("data") or []
                if data_rows:
                    df = pd.DataFrame(data_rows).rename(
                        columns={"latency__ms": "Latency_ms", "latency_ms": "Latency_ms"}
                    )
                    if "Latency_ms" in df.columns:
                        df["Latency_ms"] = pd.to_numeric(df["Latency_ms"], errors="coerce").round(3)
                    if "Result" in df.columns:
                        df["Result"] = df["Result"].map(lambda x: "Success" if bool(x) else "Failure")

                    desired_cols = ["Iteration", "Device", "Current State", "Latency_ms", "Result"]
                    df = df[[c for c in desired_cols if c in df.columns]]

                    report.set_table_dataframe(df)
                    report.build_table()

                report.set_custom_html('<hr>')
                report.build_custom()

    def move_station_csv_to_report(self, report_path):
        """Move per-station CSV files generated during monitor2() into the report directory."""
        print("Report Path:", report_path)
        if not hasattr(self, "generated_station_csv_files"):
            print("No station CSV files to move.")
            return
        station_reports_dir = os.path.join(report_path, "station_reports")
        os.makedirs(station_reports_dir, exist_ok=True)
        for file_name in self.generated_station_csv_files:
            if os.path.exists(file_name):
                dest_path = os.path.join(station_reports_dir, os.path.basename(file_name))
                try:
                    shutil.move(file_name, dest_path)
                    print(f"Moved {file_name} → {dest_path}")
                except Exception as e:
                    print(f"Error moving {file_name}: {e}")
            else:
                print(f"{file_name} does not exist.")

    def validate_existing_stations(self, raw_existing_list):
        """
        Validate each EID in raw_existing_list against LANforge port manager.
        """
        # Normalise whatever argparse hands us into a flat list of strings
        if not raw_existing_list:
            return []

        flat = []
        if isinstance(raw_existing_list, str):
            flat = [s.strip() for s in raw_existing_list.split(',') if s.strip()]
        elif isinstance(raw_existing_list, list):
            for item in raw_existing_list:
                if isinstance(item, list):
                    for sub in item:
                        flat.extend([s.strip() for s in sub.split(',') if s.strip()])
                else:
                    flat.extend([s.strip() for s in item.split(',') if s.strip()])

        if not flat:
            logger.warning("validate_existing_stations: no EIDs found after parsing.")
            return []

        validated = []
        seen = set()
        
        # Fetch port/all to check IPs
        port_data = {}
        try:
            port_resp = self.json_get("/port/all")
            if port_resp and "interfaces" in port_resp:
                for iface in port_resp["interfaces"]:
                    for port_name, pdata in iface.items():
                        port_data[port_name] = pdata
        except Exception as e:
            logger.warning(f"Failed to fetch /port/all for IP validation: {e}")

        for eid in flat:
            if eid in seen:
                continue
            seen.add(eid)
            # port_exists() from Realm accepts shelf.resource.port or short name 
            if self.port_exists(eid):
                # Check if it has an IP address
                has_ip = False
                for p_name, p_info in port_data.items():
                    if eid in p_name:
                        ip = p_info.get("ip", "0.0.0.0")
                        if ip and ip != "0.0.0.0":
                            has_ip = True
                        break
                
                if has_ip:
                    validated.append(eid)
                    logger.info(f"validate_existing_stations: confirmed port '{eid}' with IP")
                else:
                    logger.warning(f"validate_existing_stations: port '{eid}' found but has no IP — skipping.")
            else:
                logger.warning(
                    f"validate_existing_stations: port '{eid}' NOT found in LANforge — skipping.")

        if not validated:
            logger.error(
                "validate_existing_stations: none of the supplied existing stations "
                "exist in LANforge.  Aborting.")
            exit(1)

        logger.info(f"validate_existing_stations: {len(validated)} valid port(s): {validated}")
        return validated

    def parse_timebreak(self, tb_str):
        if not tb_str:
            return None
        tb_str = tb_str.strip().lower()
        if tb_str.endswith("s"):
            return int(tb_str[:-1])
        elif tb_str.endswith("m"):
            return int(tb_str[:-1]) * 60
        elif tb_str.endswith("h"):
            return int(tb_str[:-1]) * 3600
        else:
            raise ValueError("Invalid timebreak format. Use 5s, 5m or 1h")


def validate_args(args):
    if args.group_name:
        selected_groups = args.group_name.split(',')
    else:
        selected_groups = []
    if args.profile_name:
        selected_profiles = args.profile_name.split(',')
    else:
        selected_profiles = []

    # Calculate total new virtual stations and check for custom stations
    total_new_stations = args.num_stations_2g + args.num_stations_5g + args.num_stations_6g
    has_custom_stations = bool(getattr(args, 'sta_names', None))
    has_existing_stations = bool(getattr(args, 'use_existing_station_list', False))

    # Real-device specific validation
    if hasattr(args, 'client_type') and args.client_type in ("Real", "Both"):
        if args.config and args.group_name is None:
            if args.ssid is None:
                logger.error('Specify SSID for configuration, Password(Optional for "open" type security) , Security')
                exit(1)
            elif args.ssid and args.passwd == '[BLANK]' and args.security.lower() != 'open':
                logger.error('Please provide valid passwd and security configuration')
                exit(1)
            elif args.ssid and args.passwd:
                if args.security is None:
                    logger.error('Security must be provided when SSID and Password specified')
                    exit(1)
    elif not hasattr(args, 'client_type'):
        # Backward compat: original Real-only validate logic
        if args.config and args.group_name is None:
            if args.ssid is None:
                logger.error('Specify SSID for configuration, Password(Optional for "open" type security) , Security')
                exit(1)
            elif args.ssid and args.passwd == '[BLANK]' and args.security.lower() != 'open':
                logger.error('Please provide valid passwd and security configuration')
                exit(1)
            elif args.ssid and args.passwd:
                if args.security is None:
                    logger.error('Security must be provided when SSID and Password specified')
                    exit(1)

    # Validate --existing_station_list requires --use_existing_station_list flag
    if getattr(args, 'existing_station_list', None) and not has_existing_stations:
        logger.error("Error: --existing_station_list provided but --use_existing_station_list flag is missing.")
        exit(1)

    # Virtual device validation for station counts
    # Any of: create_sta, sta_names, use_existing_station_list satisfies the requirement
    if args.client_type in ("Virtual", "Both"):
        if not getattr(args, 'create_sta', False) and not has_custom_stations and not has_existing_stations:
            logger.error("Error: No stations specified for the test.\n"
                  "You must either create new stations with '--create_sta',\n"
                  "OR provide custom station names (e.g., '--sta_names sta000,sta001'),\n"
                  "OR use existing stations (e.g., '--use_existing_station_list --existing_station_list 1.1.sta00000').")
            exit(1)
        if getattr(args, 'create_sta', False) and total_new_stations == 0 and not has_custom_stations and not has_existing_stations:
            logger.error("Error: --create_sta was passed but station counts are 0 and no station names provided.")
            exit(1)
    if args.device_csv_name and args.expected_passfail_value:
        logger.error("Enter either --device_csv_name or --expected_passfail_value")
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

    if len(selected_groups) != len(selected_profiles):
        logger.error("Number of groups should match number of profiles")
    elif args.group_name and args.profile_name and args.file_name and args.device_list != []:
        logger.error("Either group name or device list should be entered, not both")
    elif args.ssid and args.profile_name:
        logger.error("Either SSID or profile name should be given")
    elif args.device_list != [] and (args.ssid is None or args.passwd is None or args.security is None):
        logger.error("Please provide ssid password and security when device list is given")
    elif args.file_name and (args.group_name is None or args.profile_name is None):
        logger.error("Please enter the correct set of arguments")
        exit(1)
    elif args.config and args.group_name is None and (args.ssid is None or (args.passwd is None and args.security is None) or (args.passwd is None and args.security.lower() != 'open')):
        logger.error("Please provide ssid password and security for configuring devices")
        exit(1)


def with_iot_params_in_table(base: dict, iot_summary) -> dict:
    """
    Append IoT params into the existing Throughput Input Parameters table.
    Adds: IoT Test name, IoT Iterations, IoT Delay (s), IoT Increment.
    Accepts dict or JSON string.
    """
    try:
        if not iot_summary:
            return base
        if isinstance(iot_summary, str):
            try:
                iot_summary = json.loads(iot_summary)
            except Exception:
                start = iot_summary.find("{")
                end = iot_summary.rfind("}")
                if start == -1 or end == -1 or end <= start:
                    return base
                try:
                    iot_summary = json.loads(iot_summary[start:end + 1])
                except Exception:
                    return base

        ti = (iot_summary.get("test_input_table") or {})
        out = OrderedDict(base)
        out["Iot Device List"] = ti.get("Device List", "")
        out["IoT Iterations"] = ti.get("Iterations", "")
        out["IoT Delay (s)"] = ti.get("Delay (seconds)", "")
        out["IoT Increment"] = ti.get("Increment Pattern", "")
        return out
    except Exception:
        return base


def trigger_iot(ip, port, iterations, delay, device_list, testname, increment):
    """
    Entry point to start the IoT test in a separate thread.
    This function is called from the throughput test script when IoT testing
    is enabled. It wraps the asynchronous `run_iot()`.
    """
    asyncio.run(run_iot(ip, port, iterations, delay, device_list, testname, increment))


async def run_iot(ip: str = '127.0.0.1',
                  port: str = '8000',
                  iterations: int = 1,
                  delay: int = 5,
                  device_list: str = '',
                  testname: str = '',
                  increment: str = ''):
    try:

        if delay < 5:
            logger.error('The minimum delay should be 5 seconds.')
            exit(1)

        if device_list != '':
            device_list = device_list.split(',')
        else:
            device_list = None
        # Parse and validate increment pattern if provided
        if increment:
            print("the increment is : ", increment)
            try:
                increment = list(map(int, increment.split(',')))
                if any(i < 1 for i in increment):
                    logger.error('Increment values must be positive integers')
                    exit(1)
            except ValueError:
                logger.error('Invalid increment format. Please provide comma-separated integers (e.g., "1,3,5")')
                exit(1)

        testname = testname

        # Ensure test name is unique (avoid overwriting previous results)
        if testname in os.listdir('../../local/interop-webGUI/IoT/scripts/results/'):
            logger.error('Test with same name already existing. Please give a different testname.')
            exit(1)
        automation = Automation(ip=ip,
                                port=port,
                                iterations=iterations,
                                delay=delay,
                                device_list=device_list,
                                testname=testname,
                                increment=increment)

        # fetch the available iot devices
        automation.devices = await automation.fetch_iot_devices()

        # select the iot devices for testing
        automation.select_iot_devices()

        # run the iot test on selected devices
        automation.run_test()

        # generate the iot report
        automation.generate_report()

    except Exception as e:
        logger.error(f"Iot Test failed: {str(e)}")
        raise

    await automation.session.close()

    logger.info('Iot Test Completed.')


def main():
    help_summary = '''\
    The Interop QoS test is designed to measure performance of an Access Point
    while running traffic with different types of services like voice, video, best effort, background.
    The test allows the user to run layer3 traffic for different ToS in upload, download and bi-direction scenarios between AP and real devices.
    Throughputs for all the ToS are reported for individual devices along with the overall throughput for each ToS.
    The expected behavior is for the AP to be able to prioritize the ToS in an order of voice,video,best effort and background.

    The test will create stations, create CX traffic between upstream port and stations, run traffic and generate a report.
    '''
    parser = argparse.ArgumentParser(
        prog='throughput_QOS.py',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog='''\
            Provides the available devices list and allows user to run the qos traffic
            with particular tos on particular devices in upload, download directions.
            ''',
        description=r'''\
NAME:       lf_interop_qos.py

PURPOSE:    lf_interop_qos.py will provide the available devices and allows user to run the qos traffic
            with particular tos on particular devices in upload, download directions.

NOTES:      1. Use './lf_interop_qos.py --help' to see command line usage and options
            2. Please pass tos in CAPITALS as shown :"BK,VI,BE,VO"
            3. Please enter the download or upload rate in bps
            4. After passing cli, a list will be displayed on terminal which contains available resources to run test.
            The following sentence will be displayed
            Enter the desired resources to run the test:
            Please enter the port numbers seperated by commas ','.
            Example:
            Enter the desired resources to run the test:1.10,1.11,1.12,1.13,1.202,1.203,1.303

EXAMPLES:   # Command Line Interface to run download scenario with tos : Voice
            ./lf_interop_qos.py --ap_name Cisco --mgr 192.168.209.223 --mgr_port 8080 --ssid Cisco
                --passwd cisco@123 --security wpa2 --upstream eth1 --test_duration 1m --download 1000000 --upload 0
                --traffic_type lf_udp --tos "VO"

            # Command Line Interface to run download scenario with tos : Voice and Video
            ./lf_interop_qos.py --ap_name Cisco --mgr 192.168.209.223 --mgr_port 8080 --ssid Cisco
                --passwd cisco@123 --security wpa2 --upstream eth1 --test_duration 1m --download 1000000 --upload 0
                --traffic_type lf_udp --tos "VO,VI"

            # Load scenario with tos : Background, Besteffort, Video and Voice
            ./lf_interop_qos.py --ap_name Cisco --mgr 192.168.209.223 --mgr_port 8080 --ssid Cisco
                --passwd cisco@123 --security wpa2 --upstream eth1 --test_duration 1m --download 0 --upload 1000000
                --traffic_type lf_udp --tos "BK,BE,VI,VO"

            # Command Line Interface to run bi-directional scenario with tos : Video and Voice
            ./lf_interop_qos.py --ap_name Cisco --mgr 192.168.209.223 --mgr_port 8080 --ssid Cisco
                --passwd cisco@123 --security wpa2 --upstream eth1 --test_duration 1m --download 1000000 --upload 1000000
                --traffic_type lf_udp --tos "VI,VO"

            # Command Line Interface to run upload scenario by setting the same expected Pass/Fail value for all devices
            ./lf_interop_qos.py  --ap_name Cisco --mgr 192.168.244.97 --test_duration 1m --upstream_port eth1 --upload 1000000
                --mgr_port 8080 --traffic_type lf_udp --tos "VI,VO,BE,BK" --ssid DLI-LPC992 --passwd Password@123
                --security wpa2 --expected_passfail_value 0.3

            # Command Line Interface to run upload scenario by setting device specific Pass/Fail values in the csv file
            ./lf_interop_qos.py  --ap_name Cisco --mgr 192.168.244.97 --test_duration 1m --upstream_port eth1 --upload 1000000
                --mgr_port 8080 --traffic_type lf_udp --tos "VI,VO,BE,BK" --ssid DLI-LPC992 --passwd Password@123
                --security wpa2 --device_csv_name device_config.csv

            # Command Line Interface to run upload scenario by Configuring Real Devices with SSID, Password, and Security
            ./lf_interop_qos.py  --ap_name Cisco --mgr 192.168.244.97 --test_duration 1m --upstream_port eth1 --upload 1000000
                --mgr_port 8080 --traffic_type lf_udp --tos "VI,VO,BE,BK" --ssid DLI-LPC992 --passwd Password@123
                --security wpa2 --config

            # Command Line Interface to run upload scenario by setting the same expected Pass/Fail value for all devices with configuration
            ./lf_interop_qos.py  --ap_name Cisco --mgr 192.168.244.97 --test_duration 1m --upstream_port eth1 --upload 1000000
                --mgr_port 8080 --traffic_type lf_udp --tos "VI,VO,BE,BK" --ssid DLI-LPC992 --passwd Password@123
                --security wpa2 --config --expected_passfail_value 0.3

            # Command Line Interface to run upload scenario by Configuring Devices in Groups with Specific Profiles
            ./lf_interop_qos.py  --ap_name Cisco --mgr 192.168.244.97 --test_duration 1m --upstream_port eth1 --upload 1000000
                --mgr_port 8080 --traffic_type lf_udp --tos "VI,VO,BE,BK" --file_name g219 --group_name grp1 --profile_name Open3

            # Command Line Interface to run upload scenario by Configuring Devices in Groups with Specific Profiles with expected Pass/Fail values
            ./lf_interop_qos.py  --ap_name Cisco --mgr 192.168.244.97 --test_duration 1m --upstream_port eth1 --upload 1000000
                --mgr_port 8080 --traffic_type lf_udp --tos "VI,VO,BE,BK" --file_name g219 --group_name grp1 --profile_name Open3
                --expected_passfail_value 0.3 --wait_time 30

SCRIPT_CLASSIFICATION:
            Test

SCRIPT_CATEGORIES:
            Performance,  Functional, Report Generation

STATUS:     BETA RELEASE

VERIFIED_ON:
            Working date:   26/07/2023
            Build version:  5.4.8
            Kernel version: 6.2.16+

LICENSE:    Free to distribute and modify. LANforge systems must be licensed.
            Copyright (C) 2020-2026 Candela Technologies Inc
''')

    required = parser.add_argument_group('Required arguments to run lf_interop_qos.py')
    optional = parser.add_argument_group('Optional arguments to run lf_interop_qos.py')
    optional.add_argument('--device_list',
                          help='Enter the devices on which the test should be run', default=[])
    optional.add_argument('--test_name',
                          help='Specify test name to store the runtime csv results', default="QOS Test")
    optional.add_argument('--result_dir',
                          help='Specify the result dir to store the runtime logs', default='')
    optional.add_argument('--mode', help='Force specific station mode.', default="0")
    required.add_argument('--mgr',
                          '--lfmgr',
                          default='localhost',
                          help='hostname for where LANforge GUI is running')
    required.add_argument('--mgr_port',
                          '--port',
                          default=8080,
                          help='port LANforge GUI HTTP service is running on')
    required.add_argument('--upstream_port',
                          '-u',
                          default='eth1',
                          help='non-station port that generates traffic: <resource>.<port>, e.g: 1.eth1')
    optional.add_argument('--security',
                          default="Open",
                          help='WiFi Security protocol: < open | wep | wpa | wpa2 | wpa3 >')
    optional.add_argument('--ssid',
                          help='WiFi SSID for script objects to associate to')
    optional.add_argument('--passwd',
                          '--password',
                          '--key',
                          default="[BLANK]",
                          help='WiFi passphrase/password/key')
    optional.add_argument('--use_existing_station_list', help='--use_station_list ,full eid must be given,'
                                'the script will use stations from the list, no configuration on the list, also prevents pre_cleanup',
                                action='store_true')
    # TODO pass in the existing station list
    optional.add_argument('--existing_station_list',action='append',nargs=1,
                                help='--station_list [list of stations] , use the stations in the list , multiple station lists may be entered')
    optional.add_argument('--ssid_2g',help='WiFi SSID for script objects to associate with Virtual Clients',default=None)
    optional.add_argument('--password_2g', '--passwd_2g', default="[BLANK]", help='WiFi passphrase/password/key for 2.4GHz', dest='password_2g')
    optional.add_argument('--security_2g', default='Open', help='WiFi Security Protocol : < open | wep | wpa | wpa2 | wpa3>')
    optional.add_argument('--ssid_5g', help='WiFi SSID for script objects to associate with Virtual Clients', default=None)
    optional.add_argument('--password_5g', '--passwd_5g', default="[BLANK]", help='WiFi passphrase/password/key for 5GHz', dest='password_5g')
    optional.add_argument('--security_5g', default='Open', help='WiFi Security Protocol : < open | wep | wpa | wpa2 | wpa3>')
    optional.add_argument('--ssid_6g', help='WiFi SSID for script objects to associate with Virtual Clients', default=None)
    optional.add_argument('--password_6g', '--passwd_6g', default="[BLANK]", help='WiFi passphrase/password/key for 6GHz', dest='password_6g')
    optional.add_argument('--security_6g', default='Open', help='WiFi Security Protocol : < open | wep | wpa | wpa2 | wpa3>')
    optional.add_argument('--bands', default='2.4G', help='Comma-seperated list of bands for test.')
    optional.add_argument('--create_sta', help='Create virtual stations for use in test', action='store_true', default=False)
    optional.add_argument('--sta_names', help='Comma-separated station names when not creating stations', default="")
    optional.add_argument('--num_stations_2g', help="Number of 2GHz band stations", type=int, default=1, required=False)
    optional.add_argument('--num_stations_5g', help="Number of 5GHz band stations", type=int, default=0, required=False)
    optional.add_argument('--num_stations_6g', help="Number of 6GHz band stations", type=int, default=0, required=False)
    optional.add_argument('--radio_2g', help="Radio used for 2.4GHz station creation", default="wiphy0")
    optional.add_argument('--radio_5g', help="Radio used for 5GHz station creation", default="wiphy1")
    optional.add_argument('--radio_6g', help="Radio used for 6GHz station creation", default="wiphy2")
    optional.add_argument('--initial_band_pref',
                          help="If specified, set a band preference for stations created for specific band",
                          required=False, action='store_true', default=False)
    required.add_argument('--traffic_type', help='Select the Traffic Type [lf_udp, lf_tcp]', required=False)
    required.add_argument('--upload', help='--upload traffic load per connection (upload rate)')
    required.add_argument('--download', help='--download traffic load per connection (download rate)')
    required.add_argument('--test_duration', help='--test_duration sets the duration of the test', default="2m")
    required.add_argument('--ap_name', help="AP Model Name", default="Test-AP")
    required.add_argument('--tos', help='Enter the tos. Example1 : "BK,BE,VI,VO" , Example2 : "BK,VO", Example3 : "VI" ')
    required.add_argument('--dowebgui', help="If true will execute script for webgui", default=False)
    required.add_argument('--client_type', help="It is used to specify the type of test. Example : Real/Virtual/Both. ")
    optional.add_argument('-d',
                          '--debug',
                          action="store_true",
                          help='Enable debugging')
    parser.add_argument('--help_summary', help='Show summary of what this script does', default=None,
                        action="store_true")
    required.add_argument('--group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    required.add_argument('--profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')
    required.add_argument('--file_name', type=str, help='Specify the file name containing group details. Example:file1')
    optional.add_argument("--eap_method", type=str, default='DEFAULT', help="Specify the EAP method for authentication.")
    optional.add_argument("--eap_identity", type=str, default='', help="Specify the EAP identity for authentication.")
    optional.add_argument("--ieee8021x", action="store_true", help='Enables 802.1X enterprise authentication for test stations.')
    optional.add_argument("--ieee80211u", action="store_true", help='Enables IEEE 802.11u (Hotspot 2.0) support.')
    optional.add_argument("--ieee80211w", type=int, default=1, help='Enables IEEE 802.11w (Management Frame Protection) support.')
    optional.add_argument("--enable_pkc", action="store_true", help='Enables pkc support.')
    optional.add_argument("--bss_transition", action="store_true", help='Enables BSS transition support.')
    optional.add_argument("--power_save", action="store_true", help='Enables power-saving features.')
    optional.add_argument("--disable_ofdma", action="store_true", help='Disables OFDMA support.')
    optional.add_argument("--roam_ft_ds", action="store_true", help='Enables fast BSS transition (FT) support')
    optional.add_argument("--key_management", type=str, default='DEFAULT', help='Specify the key management method (e.g., WPA-PSK, WPA-EAP')
    optional.add_argument("--pairwise", type=str, default='NA')
    optional.add_argument("--private_key", type=str, default='NA', help='Specify EAP private key certificate file.')
    optional.add_argument("--ca_cert", type=str, default='NA', help='Specifiy the CA certificate file name')
    optional.add_argument("--client_cert", type=str, default='NA', help='Specify the client certificate file name')
    optional.add_argument("--pk_passwd", type=str, default='NA', help='Specify the password for the private key')
    optional.add_argument("--pac_file", type=str, default='NA', help='Specify the pac file name')
    optional.add_argument('--expected_passfail_value', help='Enter the expected throughput ', default=None)
    optional.add_argument('--device_csv_name', type=str, help='Enter the csv name to store expected values', default=None)
    optional.add_argument("--wait_time", type=int, help="Enter the maximum wait time for configurations to apply", default=60)
    optional.add_argument("--config", action="store_true", help="Specify for configuring the devices")
    optional.add_argument('--get_live_view', help="If true will heatmap will be generated from testhouse automation WebGui ", action='store_true')
    optional.add_argument('--total_floors', help="Total floors from testhouse automation WebGui ", default="0")
    # Args for robot testing
    optional.add_argument("--robot_test", help='to trigger robot test', action='store_true')
    optional.add_argument('--robot_ip', type=str, default='localhost', help='hostname for where Robot server is running')
    optional.add_argument('--coordinate', type=str, default='', help="The coordinate contains list of coordinates to be ")
    optional.add_argument('--rotation', type=str, default='', help="The set of angles to rotate at a particular point")
    optional.add_argument('--do_bandsteering', help='Enable bandsteering', action='store_true')
    optional.add_argument('--cycles', type=int, default=1, help='No of cycles to perform band steering')
    optional.add_argument('--bssids', type=str, default='', help='Comma separated list of BSSIDs to be used for the test')
    optional.add_argument("--duration_to_skip", type=int, help='Specify the maximum time in seconds to skip a point if there is an obstacle', default=60)
    # IOT ARGS
    parser.add_argument('--iot_test', help="If true will execute script for iot", action='store_true')
    optional.add_argument('--iot_ip',
                          default='127.0.0.1',
                          help='IP of the server')

    optional.add_argument('--iot_port',
                          default='8000',
                          help='Port of the server')
    optional.add_argument('--iot_iterations',
                          type=int,
                          default=1,
                          help='Iterations to run the test')

    optional.add_argument('--iot_delay',
                          type=int,
                          default=5,
                          help='Delay in seconds between iterations (min. 5 seconds)')

    optional.add_argument('--iot_device_list',
                          type=str,
                          default='',
                          help='Entity IDs of the devices to include in testing (comma separated)')

    optional.add_argument('--iot_testname',
                          type=str,
                          default='',
                          help='Testname for reporting')

    optional.add_argument('--iot_increment',
                          type=str,
                          default='',
                          help='Comma-separated list of device counts to incrementally test (e.g., "1,3,5")')
    optional.add_argument('--timebreak', type=str, default=None, help="CSV aggregation interval like 5s, 5m, 1h")
    args = parser.parse_args()

    # help summary
    if args.help_summary:
        print(help_summary)
        exit(0)
    print("--------------------------------------------")
    print(args)
    print("--------------------------------------------")
    # TODO: set up logger
    # logger_config = lf_logger_config.lf_logger_config()

    # Normalise client_type — webgui may omit --client_type; treat as Real
    if not getattr(args, 'client_type', None):
        args.client_type = "Real"

    test_results = {'test_results': []}

    loads = {}
    data = {}
    rotation_enabled = False
    angle_list = []

    # For Virtual Clients
    bands = []
    station_list = []

    if args.rotation:
        angle_list = args.rotation.split(',')
        rotation_enabled = True

    if args.download and args.upload:
        loads = {'upload': str(args.upload).split(","), 'download': str(args.download).split(",")}
        loads_data = loads["download"]
        print("Loads Data BiDirectional: ", loads_data)
    elif args.download:
        loads = {'upload': [], 'download': str(args.download).split(",")}
        for _i in range(len(args.download)):
            loads['upload'].append(0)
        loads_data = loads["download"]
        print("Loads Data Download : ", loads_data)
    else:
        if args.upload:
            loads = {'upload': str(args.upload).split(","), 'download': []}
            for _i in range(len(args.upload)):
                loads['download'].append(0)
            loads_data = loads["upload"]
            print("Loads Data Upload : ", loads_data)
    if args.download and args.upload:
        direction = 'L3_' + args.traffic_type.split('_')[1].upper() + '_BiDi'
    elif args.upload:
        direction = 'L3_' + args.traffic_type.split('_')[1].upper() + '_UL'
    else:
        direction = 'L3_' + args.traffic_type.split('_')[1].upper() + '_DL'

    validate_args(args)
    if args.test_duration.endswith('s') or args.test_duration.endswith('S'):
        args.test_duration = int(args.test_duration[0:-1])
    elif args.test_duration.endswith('m') or args.test_duration.endswith('M'):
        args.test_duration = int(args.test_duration[0:-1]) * 60
    elif args.test_duration.endswith('h') or args.test_duration.endswith('H'):
        args.test_duration = int(args.test_duration[0:-1]) * 60 * 60
    elif args.test_duration.endswith(''):
        args.test_duration = int(args.test_duration)
    if args.iot_test:
        iot_ip = args.iot_ip
        iot_port = args.iot_port
        iot_iterations = args.iot_iterations
        iot_delay = args.iot_delay
        iot_device_list = args.iot_device_list
        iot_testname = args.iot_testname
        iot_increment = args.iot_increment

    ssid = ""
    password = ""
    security = ""

    bands_list = [b.strip() for b in args.bands.split(',')] if args.bands else ["2.4G"]
    station_list = []

    # If the enduser didn't provided correct band specific num_stations then method will come into action.
    def any_sta_count():
        for c in [args.num_stations_2g, args.num_stations_5g, args.num_stations_6g]:
            if c and c > 0:
                return c
        return 0

    # For Real Clients we consider 2.4G as default band - to support --client_type "Both" scenario
    if args.client_type in ("Virtual", "Both"):
        for band in bands_list:
            band = band.strip()  # This is extra validation inorder to remove leading and trailing white spaces before band word, inorder to reduce errors.

            # Use append logic to combine newly created stations and existing custom stations
            if getattr(args, 'create_sta', False):
                if band in ("2.4G", "2.4g"):
                    count = args.num_stations_2g or any_sta_count()
                    args.mode = 13
                    if count > 0:
                        station_list.extend(LFUtils.portNameSeries(
                            prefix_="sta", start_id_=0,
                            end_id_=count - 1,
                            padding_number_=10000, radio=args.radio_2g))
                elif band in ("5G", "5g"):
                    count = args.num_stations_5g or any_sta_count()
                    args.mode = 14
                    if count > 0:
                        station_list.extend(LFUtils.portNameSeries(
                            prefix_="sta", start_id_=0,
                            end_id_=count - 1,
                            padding_number_=10000, radio=args.radio_5g))
                elif band in ("6G", "6g"):
                    count = args.num_stations_6g or any_sta_count()
                    args.mode = 15
                    if count > 0:
                        station_list.extend(LFUtils.portNameSeries(
                            prefix_="sta", start_id_=0,
                            end_id_=count - 1,
                            padding_number_=10000, radio=args.radio_6g))
                elif band in ("dualband", "DUALBAND"):
                    args.mode = 0
                    if int(args.num_stations_2g) > 0:
                        station_list.extend(LFUtils.portNameSeries(
                            prefix_="sta", start_id_=0,
                            end_id_=int(args.num_stations_2g) - 1,
                            padding_number_=10000, radio=args.radio_2g))
                    if int(args.num_stations_5g) > 0:
                        station_list.extend(LFUtils.portNameSeries(
                            prefix_="sta",
                            start_id_=int(args.num_stations_2g),
                            end_id_=int(args.num_stations_2g) + int(args.num_stations_5g) - 1,
                            padding_number_=10000, radio=args.radio_5g))
                elif band in ("triband", "TRIBAND"):
                    args.mode = 0
                    if int(args.num_stations_2g) > 0:
                        station_list.extend(LFUtils.portNameSeries(
                            prefix_="sta", start_id_=0,
                            end_id_=int(args.num_stations_2g) - 1,
                            padding_number_=10000, radio=args.radio_2g))
                    if int(args.num_stations_5g) > 0:
                        station_list.extend(LFUtils.portNameSeries(
                            prefix_="sta",
                            start_id_=int(args.num_stations_2g),
                            end_id_=int(args.num_stations_2g) + int(args.num_stations_5g) - 1,
                            padding_number_=10000, radio=args.radio_5g))
                    if int(args.num_stations_6g) > 0:
                        station_list.extend(LFUtils.portNameSeries(
                            prefix_="sta",
                            start_id_=int(args.num_stations_2g) + int(args.num_stations_5g),
                            end_id_=int(args.num_stations_2g) + int(args.num_stations_5g) + int(args.num_stations_6g) - 1,
                            padding_number_=10000, radio=args.radio_6g))
                else:
                    print(f"Band '{band}' not recognised : skipping station list generation.")

        # --sta_names: append custom-named stations (new or pre-existing by name)
        # If a sta_name already exists in LANforge it will be skipped by station_profile.create()
        # (LANforge ignores add_sta for a port that already exists).
        if getattr(args, 'sta_names', None):
            station_list.extend([s.strip() for s in args.sta_names.split(",") if s.strip() not in station_list])

        print("Virtual station_list (before existing validation):", station_list)

    if args.client_type == "Real":
        ssid = args.ssid
        password = args.passwd
        security = args.security
    else:
        # Virtual / Both — only use the generic slot for a true override
        ssid = args.ssid   # None unless --ssid was explicitly supplied
        password = args.passwd if args.ssid is not None else None
        security = args.security if args.ssid is not None else None

    for index in range(len(loads_data)):
        throughput_qos = ThroughputQOS(host=args.mgr,
                                       ip=args.mgr,
                                       port=args.mgr_port,
                                       number_template="0000",
                                       ap_name=args.ap_name,
                                       name_prefix="TOS-",
                                       upstream=args.upstream_port,
                                       # Generic SSID / security (used by Real and as fallback)
                                       ssid=ssid,
                                       password=password,
                                       security=security,
                                       # Band-specific SSID / security (used by Virtual/Both)
                                       ssid_2g=args.ssid_2g,
                                       security_2g=args.security_2g,
                                       password_2g=args.password_2g,
                                       ssid_5g=args.ssid_5g,
                                       security_5g=args.security_5g,
                                       password_5g=args.password_5g,
                                       ssid_6g=args.ssid_6g,
                                       security_6g=args.security_6g,
                                       password_6g=args.password_6g,
                                       # Virtual station params
                                       create_sta=getattr(args, 'create_sta', False),
                                       sta_list=station_list,
                                       num_stations_2g=args.num_stations_2g,
                                       num_stations_5g=args.num_stations_5g,
                                       num_stations_6g=args.num_stations_6g,
                                       radio_2g=args.radio_2g,
                                       radio_5g=args.radio_5g,
                                       radio_6g=args.radio_6g,
                                       bands=args.bands,
                                       mode=int(args.mode),
                                       initial_band_pref=getattr(args, 'initial_band_pref', False),
                                       test_duration=args.test_duration,
                                       use_ht160=False,
                                       side_a_min_rate=int(loads['upload'][index]),
                                       side_b_min_rate=int(loads['download'][index]),
                                       traffic_type=args.traffic_type,
                                       tos=args.tos,
                                       csv_direction=direction,
                                       dowebgui=args.dowebgui,
                                       test_name=args.test_name,
                                       result_dir=args.result_dir,
                                       device_list=args.device_list,
                                       _debug_on=args.debug,
                                       group_name=args.group_name,
                                       profile_name=args.profile_name,
                                       file_name=args.file_name,
                                       eap_method=args.eap_method,
                                       eap_identity=args.eap_identity,
                                       ieee80211=args.ieee8021x,
                                       ieee80211u=args.ieee80211u,
                                       ieee80211w=args.ieee80211w,
                                       enable_pkc=args.enable_pkc,
                                       bss_transition=args.bss_transition,
                                       power_save=args.power_save,
                                       disable_ofdma=args.disable_ofdma,
                                       roam_ft_ds=args.roam_ft_ds,
                                       key_management=args.key_management,
                                       pairwise=args.pairwise,
                                       private_key=args.private_key,
                                       ca_cert=args.ca_cert,
                                       client_cert=args.client_cert,
                                       pk_passwd=args.pk_passwd,
                                       pac_file=args.pac_file,
                                       expected_passfail_val=args.expected_passfail_value,
                                       csv_name=args.device_csv_name,
                                       wait_time=args.wait_time,
                                       config=args.config,
                                       get_live_view=args.get_live_view,
                                       total_floors=args.total_floors,
                                       robot_test=args.robot_test,
                                       robot_ip=args.robot_ip,
                                       coordinate=args.coordinate,
                                       rotation=args.rotation,
                                       rotation_enabled=rotation_enabled,
                                       angle_list=angle_list,
                                       do_bandsteering=args.do_bandsteering,
                                       cycles=args.cycles,
                                       bssids=args.bssids,
                                       duration_to_skip=args.duration_to_skip,
                                       timebreak=args.timebreak,
                                       client_type=args.client_type
                                       )
        throughput_qos.do_bandsteering = getattr(args, 'do_bandsteering', False)
        throughput_qos.cycles = getattr(args, 'cycles', 1)
        throughput_qos.bssids = getattr(args, 'bssids', '').split(',') if getattr(args, 'bssids', '') else []
        if throughput_qos.robot_test and throughput_qos.do_bandsteering:
            throughput_qos.get_live_view = False

        # Existing-station validation (--use_existing_station_list) - here we use port_exists() method of realm class inorder to validate.
        existing_sta_list = []
        if args.client_type in ("Virtual", "Both") and getattr(args, 'use_existing_station_list', False):
            raw = getattr(args, 'existing_station_list', None)
            if raw:
                existing_sta_list = throughput_qos.validate_existing_stations(raw)
                logger.info(f"Existing stations after validation: {existing_sta_list}")
            else:
                logger.warning("--use_existing_station_list set but --existing_station_list is empty — ignoring.")

        throughput_qos._existing_sta_list = existing_sta_list

        # Inorder to run the test on Real Devices in --client_type 'Real and Both' Scenarios.
        if args.client_type in ("Real", "Both"):
            throughput_qos.os_type()
            _, configured_device, _, configuration = throughput_qos.phantom_check()
            throughput_qos.qos_data["configuration"] = configuration
            if args.dowebgui and args.group_name:
                if len(configured_device) == 0:
                    logger.warning("No device is available to run the test")
                    obj1 = {
                        "status": "Stopped",
                        "configuration_status": "configured"
                    }
                    throughput_qos.updating_webui_runningjson(obj1)
                    return
                else:
                    obj1 = {
                        "configured_devices": configured_device,
                        "configuration_status": "configured"
                    }
                    throughput_qos.updating_webui_runningjson(obj1)
        else:
            # Virtual-only: no real device discovery needed
            throughput_qos.qos_data["configuration"] = {}
            configuration = {}

        if args.iot_test:
            if args.iot_iterations > 1:
                thread = threading.Thread(target=trigger_iot, args=(iot_ip, iot_port, iot_iterations, iot_delay, iot_device_list, iot_testname, iot_increment))
                thread.start()
            else:
                total_secs = int(args.test_duration)
                iot_iterations = max(1, total_secs // args.iot_delay)
                iot_thread = threading.Thread(
                    target=trigger_iot,
                    args=(
                        args.iot_ip,
                        args.iot_port,
                        iot_iterations,
                        args.iot_delay,
                        args.iot_device_list,
                        args.iot_testname,
                        args.iot_increment
                    ),
                    daemon=True
                )
                iot_thread.start()

        # checking if we have atleast one device available for running test
        if args.client_type in ("Real", "Both") and throughput_qos.dowebgui == "True":
            if throughput_qos.device_found is False:
                logger.warning("No Device is available to run the test hence aborting the test")
                df1 = pd.DataFrame([{
                    "BE_dl": 0,
                    "BE_ul": 0,
                    "BK_dl": 0,
                    "BK_ul": 0,
                    "VI_dl": 0,
                    "VI_ul": 0,
                    "VO_dl": 0,
                    "VO_ul": 0,
                    "timestamp": datetime.now().strftime('%H:%M:%S'),
                    'status': 'Stopped'
                }])
                df1.to_csv('{}/overall_throughput.csv'.format(throughput_qos.result_dir), index=False)
                raise ValueError("Aborting the test....")

        # Virtual pre-cleanup (remove Old Stations / CX prefixes)
        if args.client_type in ("Virtual", "Both"):
            throughput_qos.pre_cleanup()

        # Build CX (creates stations for Real, Virtual and Both Scenario)
        throughput_qos.build(client_type=args.client_type)

        # Remove's not working cx's from the test.
        if args.client_type in ("Real", "Virtual", "Both"):
            throughput_qos.monitor_cx()

        if args.robot_test:
            throughput_qos.perform_robo()
            exit(1)
        throughput_qos.start(False, False)
        time.sleep(10)

        connections_download, connections_upload, drop_a_per, drop_b_per, connections_download_avg, connections_upload_avg, avg_drop_a, avg_drop_b = throughput_qos.monitor(
            runtime_dir="per_client_csv")

        logger.info("connections download {}".format(connections_download))
        logger.info("connections upload {}".format(connections_upload))

        ssid_list = []
        mac_list = []
        mode_list = []
        bssid_list = []
        channel_list = []
        rssi_list = []

        if args.client_type == "Both":
            total_devices_list = throughput_qos.sta_list + throughput_qos.input_devices_list
            ssid_list, mac_list, mode_list, bssid_list, channel_list, rssi_list = throughput_qos.get_portmgr_data(total_devices_list)
            throughput_qos.ssid_list, throughput_qos.macid_list, throughput_qos.mode_list, throughput_qos.bssid_list, throughput_qos.channels_list, throughput_qos.rssi_list = ssid_list, mac_list, mode_list, bssid_list, channel_list, rssi_list
            print("We are printing Total Test Devices : ", total_devices_list)
        elif args.client_type == 'Virtual':
            print("Station List : ", throughput_qos.sta_list)
            ssid_list, mac_list, mode_list, bssid_list, channel_list, rssi_list = throughput_qos.get_portmgr_data(throughput_qos.sta_list)
            throughput_qos.ssid_list, throughput_qos.macid_list, throughput_qos.mode_list, throughput_qos.bssid_list, throughput_qos.channels_list, throughput_qos.rssi_list = ssid_list, mac_list, mode_list, bssid_list, channel_list, rssi_list
        else:
            print("Input Real Device List : ", throughput_qos.input_devices_list)
            ssid_list, mac_list, mode_list, bssid_list, channel_list, rssi_list = throughput_qos.get_portmgr_data(throughput_qos.input_devices_list)
            throughput_qos.ssid_list, throughput_qos.macid_list, throughput_qos.mode_list, throughput_qos.bssid_list, throughput_qos.channels_list, throughput_qos.rssi_list = ssid_list, mac_list, mode_list, bssid_list, channel_list, rssi_list

        throughput_qos.stop()
        time.sleep(5)

        test_results['test_results'].append(throughput_qos.evaluate_qos(
            connections_download, connections_upload, drop_a_per, drop_b_per))

        if args.client_type == 'Virtual':
            # Virtual: band-keyed structure for set_report_data_virtual
            _primary_band = bands_list[0] if bands_list else "2.4G"
            data.update({_primary_band: test_results})
            throughput_qos.test_case = bands_list
        else:
            # Real and Both
            # test_case is still set so generate_individual_graph_virtual
            data.update(test_results)
            throughput_qos.test_case = bands_list

    test_end_time = datetime.now().strftime("%Y %d %H:%M:%S")
    print("Test ended at: ", test_end_time)

    input_setup_info = {
        "contact": "support@candelatech.com"
    }

    iot_summary = None
    if args.iot_test and args.iot_testname:
        base = os.path.join("results", args.iot_testname)
        p = os.path.join(base, "iot_summary.json")
        if os.path.exists(p):
            with open(p) as f:
                iot_summary = json.load(f)

    # Update webgui running json with latest entry and test status completed
    if throughput_qos.dowebgui == "True":
        last_entry = throughput_qos.overall[len(throughput_qos.overall) - 1]
        last_entry["status"] = "Stopped"
        last_entry["timestamp"] = datetime.now().strftime("%d/%m %I:%M:%S %p")
        last_entry["remaining_time"] = "0"
        last_entry["end_time"] = last_entry["timestamp"]
        throughput_qos.df_for_webui.append(last_entry)
        df1 = pd.DataFrame(throughput_qos.df_for_webui)
        df1.to_csv('{}/overall_throughput.csv'.format(args.result_dir), index=False)

    # generate_report: all three paths pass the same kwargs; Virtual ignores
    # connections_avg (they default to {} in the method signature)
    if args.client_type == "Both":
        if args.group_name:
            throughput_qos.generate_report(
                data=data,
                input_setup_info=input_setup_info,
                report_path=throughput_qos.result_dir,
                connections_upload_avg=connections_upload_avg,
                connections_download_avg=connections_download_avg,
                avg_drop_a=avg_drop_a,
                avg_drop_b=avg_drop_b,
                config_devices=configuration,
                iot_summary=iot_summary)
        else:
            throughput_qos.generate_report(
                data=data,
                input_setup_info=input_setup_info,
                report_path=throughput_qos.result_dir,
                connections_upload_avg=connections_upload_avg,
                connections_download_avg=connections_download_avg,
                avg_drop_a=avg_drop_a,
                avg_drop_b=avg_drop_b,
                iot_summary=iot_summary)

    if args.client_type == 'Virtual':
        throughput_qos.generate_report(
            data=data,
            input_setup_info=input_setup_info,
            report_path=throughput_qos.result_dir,
            connections_upload_avg=connections_upload_avg,
            connections_download_avg=connections_download_avg,
            avg_drop_a=avg_drop_a,
            avg_drop_b=avg_drop_b,
            iot_summary=iot_summary)

    if args.client_type == "Real":
        if args.group_name:
            throughput_qos.generate_report(
                data=data,
                input_setup_info=input_setup_info,
                report_path=throughput_qos.result_dir,
                connections_upload_avg=connections_upload_avg,
                connections_download_avg=connections_download_avg,
                avg_drop_a=avg_drop_a,
                avg_drop_b=avg_drop_b,
                config_devices=configuration,
                iot_summary=iot_summary)
        else:
            throughput_qos.generate_report(
                data=data,
                input_setup_info=input_setup_info,
                report_path=throughput_qos.result_dir,
                connections_upload_avg=connections_upload_avg,
                connections_download_avg=connections_download_avg,
                avg_drop_a=avg_drop_a,
                avg_drop_b=avg_drop_b,
                iot_summary=iot_summary)

    if args.create_sta:
        if not throughput_qos.passes():
            print(throughput_qos.get_fail_message())
            throughput_qos.exit_fail()
        # LFUtils.wait_until_ports_admin_up(port_list=station_list)
        if throughput_qos.passes():
            throughput_qos.success()
            throughput_qos.cleanup()

    throughput_qos.cleanup()  # After Test Cleanup()

    # Update webgui running json with latest entry and test status completed
    if throughput_qos.dowebgui == "True":
        # copying to home directory i.e home/user_name
        throughput_qos.copy_reports_to_home_dir()


if __name__ == "__main__":
    main()