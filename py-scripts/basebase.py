import asyncio
import importlib
import datetime
from datetime import datetime, timedelta
import time
import requests
import threading
import logging
import pandas as pd
from lf_base_interop_profile import RealDevice
from lf_ftp import FtpTest
import lf_webpage as http_test
import lf_interop_qos as qos_test
import lf_interop_ping as ping_test
from lf_interop_throughput import Throughput
from lf_interop_video_streaming import VideoStreamingTest
# from lf_interop_real_browser_test import RealBrowserTest
from test_l3 import L3VariableTime,change_port_to_ip,configure_reporting,query_real_clients
from lf_kpi_csv import lf_kpi_csv
import lf_cleanup
import os
import sys
import json
from types import SimpleNamespace
base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
print('base path',base_path)
sys.path.insert(0, os.path.join(base_path, 'py-json'))     # for interop_connectivity, LANforge
sys.path.insert(0, os.path.join(base_path, 'py-json', 'LANforge'))  # for LFUtils
sys.path.insert(0, os.path.join(base_path, 'py-scripts'))  # for lf_logger_config
througput_test=importlib.import_module("py-scripts.lf_interop_throughput")
video_streaming_test=importlib.import_module("py-scripts.lf_interop_video_streaming")
web_browser_test=importlib.import_module("py-scripts.real_application_tests.real_browser.lf_interop_real_browser_test")
yt_test=importlib.import_module("py-scripts.real_application_tests.youtube.lf_interop_youtube")
lf_report_pdf = importlib.import_module("py-scripts.lf_report")
lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")
logger = logging.getLogger(__name__)
RealBrowserTest = getattr(web_browser_test, "RealBrowserTest")
Youtube = getattr(yt_test, "Youtube")
DeviceConfig=importlib.import_module("py-scripts.DeviceConfig")
# from py_scripts import lf_logger_config, interop_connectivity
from lf_interop_ping import Ping
# from LANforge.LFUtils import LFUtils
import sys
import os

# BASE PATH: /home/sidartha/project/lanforge-scripts
# base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# # Add py-json and LANforge to sys.path
# sys.path.insert(0, os.path.join(base_path, 'py-json'))               # for interop_connectivity
# sys.path.insert(0, os.path.join(base_path, 'py-json', 'LANforge'))   # for LFUtils
# sys.path.insert(0, os.path.join(base_path, 'py-scripts'))            # for lf_logger_config

# import LFUtils
# import lf_logger_config
# import interop_connectivity
if 'py-json' not in sys.path:
    sys.path.append(os.path.join(os.path.abspath('..'), 'py-json'))

if 'py-scripts' not in sys.path:
    sys.path.append('/home/lanforge/lanforge-scripts/py-scripts')

from station_profile import StationProfile
import interop_connectivity
from LANforge import LFUtils
class Candela:
    """
    Candela Class file to invoke different scripts from py-scripts.
    """

    def __init__(self, ip='localhost', port=8080):
        """
        Constructor to initialize the LANforge IP and port
        Args:
            ip (str, optional): LANforge IP. Defaults to 'localhost'.
            port (int, optional): LANforge port. Defaults to 8080.
        """
        self.lanforge_ip = ip
        self.port = port
        self.api_url = 'http://{}:{}'.format(self.lanforge_ip, self.port)
        self.cleanup = lf_cleanup.lf_clean(host=self.lanforge_ip, port=self.port, resource='all')
        self.ftp_test = None
        self.http_test = None

        self.iterations_before_test_stopped_by_user=None
        self.incremental_capacity_list=None
        self.all_dataframes=None
        self.to_run_cxs_len=None
        self.date=None
        self.test_setup_info=None
        self.individual_df=None
        self.cx_order_list=None
        self.dataset2=None
        self.dataset = None
        self.lis = None
        self.bands = None
        self.total_urls = None
        self.uc_min_value = None
        self.cx_order_list = None
        self.gave_incremental=None

    def api_get(self, endp: str):
        """
        Sends a GET request to fetch data

        Args:
            endp (str): API endpoint

        Returns:
            response: response code for the request
            data: data returned in the response
        """
        if endp[0] != '/':
            endp = '/' + endp
        response = requests.get(url=self.api_url + endp)
        data = response.json()
        return response, data

    def api_post(self, endp: str, payload: dict):
        """
        Sends POST request

        Args:
            endp (str): API endpoint
            payload (dict): Endpoint data in JSON format

        Returns:
            response: response code for the request
                      None if endpoint is invalid
        """
        if endp == '' or endp is None:
            logger.info('Invalid endpoint specified.')
            return False
        if endp[0] != '/':
            endp = '/' + endp
        response = requests.post(url=self.api_url + endp, json=payload)
        return response

    def misc_clean_up(self,layer3=False,layer4=False):
        """
        Use for the cleanup of cross connections
        arguments:
        layer3: (Boolean : optional) Default : False To Delete all layer3 connections
        layer4: (Boolean : optional) Default : False To Delete all layer4 connections
        """
        if layer3:
            self.cleanup.cxs_clean()
            self.cleanup.layer3_endp_clean()
        if layer4:
            self.cleanup.layer4_endp_clean()

    def get_device_info(self):
        """
        Fetches all the real devices clustered to the LANforge

        Returns:
            interop_tab_response: if invalid response code. Response code other than 200.
            all_devices (dict): returns both the port data and resource mgr data with shelf.resource as the key
        """
        androids, linux, macbooks, windows, iOS = [], [], [], [], []
        all_devices = {}

        # querying resource manager tab for fetching laptops data
        resource_manager_tab_response, resource_manager_data = self.api_get(
            endp='/resource/all')
        if resource_manager_tab_response.status_code != 200:
            logger.info('Error fetching the data with the {}. Returned {}'.format(
                '/resources/all', resource_manager_tab_response))
            return resource_manager_tab_response
        resources_list = [resource_manager_data['resource']
                          if 'resource' in resource_manager_data else resource_manager_data['resources']][0]
        for resource in resources_list:
            resource_port, resource_data = list(resource.keys())[
                0], list(resource.values())[0]
            if resource_data['phantom']:
                continue
            if resource_data['ct-kernel'] is False:
                if resource_data['app-id'] == '0':
                    if 'Win' in resource_data['hw version']:
                        windows.append(resource_data)
                    elif 'Apple' in resource_data['hw version']:
                        macbooks.append(resource_data)
                    elif 'Linux' in resource_data['hw version']:
                        linux.append(resource_data)
                else:
                    if 'Apple' in resource_data['hw version']:
                        iOS.append(resource_data)
                    else:
                        androids.append(resource_data)
                all_devices[resource_port] = resource_data
                shelf, resource = resource_port.split('.')
                _, port_data = self.api_get(endp='/port/{}/{}'.format(shelf, resource))
                if 'interface' in port_data.keys():
                    port_data['interfaces'] = [port_data['interface']]
                for port_id in port_data['interfaces']:
                    port_id_values = list(port_id.values())[0]
                    _, all_columns = self.api_get(endp=port_id_values['_links'])
                    all_columns = all_columns['interface']
                    if all_columns['parent dev'] == 'wiphy0':
                        all_devices[resource_port].update(all_columns)
        return all_devices

    def get_client_connection_details(self, device_list: list):
        """
        Method to return SSID, BSSID and Signal Strength details of the ports mentioned in the device list argument.

        Args:
            device_list (list): List of all the ports. E.g., ['1.10.wlan0', '1.11.wlan0']

        Returns:
            connection_details (dict): Dictionary containing port number as the key and SSID, BSSID, Signal as the values for each device in the device_list.
        """
        connection_details = {}
        for device in device_list:
            shelf, resource, port_name = device.split('.')
            _, device_data = self.api_get('/port/{}/{}/{}?fields=phantom,down,ssid,ap,signal,mac'.format(shelf, resource, port_name))
            device_data = device_data['interface']
            if device_data['phantom'] or device_data['down']:
                print('{} is in phantom state or down state, data may not be accurate.'.format(device))
            connection_details[device] = device_data
        return connection_details

    def filter_iOS_devices(self, device_list):
        modified_device_list = device_list
        if type(device_list) is str:
            modified_device_list = device_list.split(',')
        filtered_list = []
        for device in modified_device_list:
            if device.count('.') == 1:
                shelf, resource = device.split('.')
            elif device.count('.') == 2:
                shelf, resource, port = device.split('.')
            elif device.count('.') == 0:
                shelf, resource = 1, device
            response_code, device_data = self.api_get('/resource/{}/{}'.format(shelf, resource))
            if 'status' in device_data and device_data['status'] == 'NOT_FOUND':
                print('Device {} is not found.'.format(device))
                continue
            device_data = device_data['resource']
            # print(device_data)
            if 'Apple' in device_data['hw version'] and (device_data['app-id'] != '') and (device_data['app-id'] != '0' or device_data['kernel'] == ''):
                print('{} is an iOS device. Currently we do not support iOS devices.'.format(device))
            else:
                filtered_list.append(device)
        if type(device_list) is str:
            filtered_list = ','.join(filtered_list)
        return filtered_list

    def http_parmeter_validate(self,http_val):
        if http_val["expected_passfail_value"] and http_val["device_csv_name"]:
            logger.error("Specify either --expected_passfail_value or --device_csv_name")
            exit(1)
        if http_val["group_name"]:
            selected_groups = http_val["group_name"].split(',')
        else:
            selected_groups = []
        if http_val["profile_name"]:
            selected_profiles = http_val["profile_name"].split(',')
        else:
            selected_profiles = []

        if len(selected_groups) != len(selected_profiles):
            logger.error("Number of groups should match number of profiles")
            exit(1)
        elif http_val["group_name"] and http_val["profile_name"] and http_val["file_name"] and http_val["device_list"] != []:
            logger.error("Either --group_name or --device_list should be entered not both")
            exit(1)
        elif http_val["ssid"] and http_val["profile_name"]:
            logger.error("Either --ssid or --profile_name should be given")
            exit(1)
        elif http_val["file_name"] and (http_val["group_name"] is None or http_val["profile_name"] is None):
            logger.error("Please enter the correct set of arguments for configuration")
            exit(1)
        if http_val["config"] and http_val["group_name"] is None:
            if http_val["ssid"] and http_val["security"] and http_val["security"].lower() == 'open' and (http_val["passwd"] is None or http_val["passwd"] == ''):
                http_val["passwd"] = '[BLANK]'
            if http_val["ssid"] is None or http_val["passwd"] is None or http_val["passwd"] == '':
                logger.error('For configuration need to Specify --ssid , --passwd (Optional for "open" type security) , --security')
                exit(1)
            elif http_val["ssid"] and http_val["passwd"] == '[BLANK]' and http_val["security"] and http_val["security"].lower() != 'open':
                logger.error('Please provide valid --passwd and --security configuration')
                exit(1)
            elif http_val["ssid"] and http_val["passwd"]:
                if http_val["security"] is None:
                    logger.error('Security must be provided when --ssid and --password specified')
                    exit(1)
                elif http_val["ssid"] and http_val["passwd"] == '[BLANK]' and http_val["security"] and http_val["security"].lower() != 'open':
                    logger.error('Please provide valid passwd and security configuration')
                    exit(1)
                elif http_val["security"].lower() == 'open' and http_val["passwd"] != '[BLANK]':
                    logger.error("For a open type security there will be no password or the password should be left blank (i.e., set to '' or [BLANK]).")
                    exit(1)

    def run_ping_test(self,
                  mgr_passwd='lanforge',
                  server_ip=None,
                  ssid=None,
                  security='open',
                  passwd='[BLANK]',
                  target='1.1.eth1',
                  ping_interval='1',
                  ping_duration=1.0,
                  virtual=False,
                  real=True,
                  radio=None,
                  num_sta=1,
                  use_default_config=False,
                  debug=False,
                  local_lf_report_dir="",
                  log_level=None,
                  lf_logger_config_json=None,
                  help_summary=None):

        if help_summary:
            print(help_summary)
            return

        # Logger setup
        logger_config = lf_logger_config.lf_logger_config()
        if log_level:
            logger_config.set_level(level=log_level)
        if lf_logger_config_json:
            logger_config.lf_logger_config_json = lf_logger_config_json
            logger_config.load_lf_logger_config()

        if not (virtual or real):
            print('At least one of --real or --virtual is required')
            return
        if virtual:
            if not radio:
                print('--radio required')
                return
            if not ssid:
                print('--ssid required for virtual stations')
                return
        if security != 'open' and passwd == '[BLANK]':
            print('--passwd required')
            return
        if not use_default_config:
            if not ssid:
                print('--ssid required for Wi-Fi configuration')
                return
            if security.lower() != 'open' and passwd == '[BLANK]':
                print('--passwd required for Wi-Fi configuration')
                return
            if server_ip is None:
                print('--server_ip or upstream ip required for Wi-Fi configuration')
                return

        if debug:
            print(f"""Specified configuration:
            ip:                       {self.lanforge_ip}
            port:                     {self.port}
            ssid:                     {ssid}
            security:                 {security}
            password:                 {passwd}
            target:                   {target}
            Ping interval:            {ping_interval}
            Packet Duration (min):    {ping_duration}
            virtual:                  {virtual}
            num virtual stations:     {num_sta}
            radio:                    {radio}
            real:                     {real}
            debug:                    {debug}
            """)

        ping = Ping(
            host=self.lanforge_ip,
            port=self.port,
            ssid=ssid,
            security=security,
            password=passwd,
            radio=radio,
            lanforge_password=mgr_passwd,
            target=target,
            interval=ping_interval,
            sta_list=[],
            virtual=virtual,
            real=real,
            duration=ping_duration,
            debug=debug
        )

        ping.change_target_to_ip()


        if real:
            Devices = RealDevice(manager_ip=self.lanforge_ip, selected_bands=[])
            Devices.get_devices()
            ping.Devices = Devices
            ping.select_real_devices(real_devices=Devices)

            if not use_default_config:
                if Devices.android_list:
                    androids = interop_connectivity.Android(self.lanforge_ip, self.port, server_ip, ssid, passwd, security)
                    androids_data = androids.get_serial_from_port(Devices.android_list)
                    androids.stop_app(androids_data)
                    androids.set_wifi_state(androids_data, state='enable')
                    androids.configure_wifi(androids_data)
                if Devices.windows_list or Devices.linux_list or Devices.mac_list:
                    laptops = interop_connectivity.Laptop(self.lanforge_ip, self.port, server_ip, ssid, passwd, security)
                    all_laptops = Devices.windows_list + Devices.linux_list + Devices.mac_list
                    laptops_data = laptops.get_laptop_from_port(all_laptops)
                    laptops.rm_station(laptops_data)
                    time.sleep(2)
                    laptops.add_station(laptops_data)
                    time.sleep(2)
                    laptops.set_port(laptops_data)
                time.sleep(20)

        ping.cleanup()
        if virtual:
            ping.buildstation()
        if not ping.check_tab_exists():
            logging.error("Generic Tab not available. Aborting test.")
            return

        ping.sta_list += ping.real_sta_list
        ping.create_generic_endp()
        ping.start_generic()
        time.sleep(ping_duration * 60)
        ping.stop_generic()

        result_data = ping.get_results()
        ports_data_dict = ping.json_get('/ports/all/')['interfaces']
        ports_data = {list(p.keys())[0]: list(p.values())[0] for p in ports_data_dict}

        # Initialize result storage
        ping.result_json = {}

        # Parsing Virtual Device Results
        if virtual:
            for station in ping.sta_list:
                if station not in ping.real_sta_list:
                    current_device_data = ports_data.get(station, {})
                    for ping_device in result_data if isinstance(result_data, list) else [result_data]:
                        key, data = (list(ping_device.items())[0] if isinstance(ping_device, dict) else (station, result_data))
                        if station.split('.')[-1] in key:
                            try:
                                last_line = data['last results'].split('\n')[-2] if 'last results' in data and len(data['last results'].split('\n')) > 1 else ""
                                parts = last_line.split()[-1].split('/')
                                ping.result_json[station] = {
                                    'command': data['command'],
                                    'sent': data['tx pkts'],
                                    'recv': data['rx pkts'],
                                    'dropped': data['dropped'],
                                    'min_rtt': parts[0] if len(parts) == 3 else '0',
                                    'avg_rtt': parts[1] if len(parts) == 3 else '0',
                                    'max_rtt': parts[2] if len(parts) == 3 else '0',
                                    'mac': current_device_data.get('mac', ''),
                                    'channel': current_device_data.get('channel', ''),
                                    'ssid': current_device_data.get('ssid', ''),
                                    'mode': current_device_data.get('mode', ''),
                                    'name': station,
                                    'os': 'Virtual',
                                    'remarks': [],
                                    'last_result': last_line
                                }
                                ping.result_json[station]['remarks'] = ping.generate_remarks(ping.result_json[station])
                            except Exception as e:
                                logging.error(f'Failed parsing virtual station {station}: {e}')

        # Parsing Real Device Results
        if real:
            for station in ping.real_sta_list:
                current_device_data = Devices.devices_data.get(station, {})
                for ping_device in result_data if isinstance(result_data, list) else [result_data]:
                    key, data = (list(ping_device.items())[0] if isinstance(ping_device, dict) else (station, result_data))
                    if station.split('.')[-1] in key:
                        try:
                            last_line = data['last results'].split('\n')[-2] if 'last results' in data and len(data['last results'].split('\n')) > 1 else ""
                            parts = last_line.split(':')[-1].split('/') if ':' in last_line else last_line.split('/')
                            ping.result_json[station] = {
                                'command': data['command'],
                                'sent': data['tx pkts'],
                                'recv': data['rx pkts'],
                                'dropped': data['dropped'],
                                'min_rtt': parts[0] if len(parts) == 3 else '0',
                                'avg_rtt': parts[1] if len(parts) == 3 else '0',
                                'max_rtt': parts[2] if len(parts) == 3 else '0',
                                'mac': current_device_data.get('mac', ''),
                                'channel': current_device_data.get('channel', ''),
                                'ssid': current_device_data.get('ssid', ''),
                                'mode': current_device_data.get('mode', ''),
                                'name': current_device_data.get('user', '') or current_device_data.get('hostname', ''),
                                'os': (
                                    'Windows' if 'Win' in current_device_data.get('hw version', '') else
                                    'Linux' if 'Linux' in current_device_data.get('hw version', '') else
                                    'Mac' if 'Apple' in current_device_data.get('hw version', '') else 'Android'
                                ),
                                'remarks': [],
                                'last_result': last_line
                            }
                            ping.result_json[station]['remarks'] = ping.generate_remarks(ping.result_json[station])
                        except Exception as e:
                            logging.error(f'Failed parsing real station {station}: {e}')

        logging.info(ping.result_json)

        if local_lf_report_dir:
            ping.generate_report(report_path=local_lf_report_dir)
        else:
            ping.generate_report()

    def run_http_test(
        self,
        upstream_port='eth2',
        num_stations=0,
        twog_radio='wiphy3',
        fiveg_radio='wiphy0',
        sixg_radio='wiphy2',
        twog_security=None,
        twog_ssid=None,
        twog_passwd=None,
        fiveg_security=None,
        fiveg_ssid=None,
        fiveg_passwd=None,
        sixg_security=None,
        sixg_ssid=None,
        sixg_passwd=None,
        target_per_ten=100,
        file_size='5MB',
        bands=["5G", "2.4G", "6G"],
        duration=None,
        client_type="Real",
        threshold_5g="60",
        threshold_2g="90",
        threshold_both="50",
        ap_name="TestAP",
        lf_username="lanforge",
        lf_password="lanforge",
        ssh_port=22,
        test_rig="",
        test_tag="",
        dut_hw_version="",
        dut_sw_version="",
        dut_model_num="",
        dut_serial_num="",
        test_priority="",
        test_id="lf_webpage",
        csv_outfile="",
        dowebgui=False,
        result_dir='',
        device_list=[],
        test_name=None,
        get_url_from_file=False,
        file_path=None,
        help_summary=False,
        ssid=None,
        passwd='',
        security=None,
        file_name=None,
        group_name=None,
        profile_name=None,
        eap_method='DEFAULT',
        eap_identity='',
        ieee8021x=False,
        ieee80211u=False,
        ieee80211w=1,
        enable_pkc=False,
        bss_transition=False,
        power_save=False,
        disable_ofdma=False,
        roam_ft_ds=False,
        key_management='DEFAULT',
        pairwise='NA',
        private_key='NA',
        ca_cert='NA',
        client_cert='NA',
        pk_passwd='NA',
        pac_file='NA',
        expected_passfail_value=None,
        device_csv_name=None,
        wait_time=60,
        config=False,
        get_live_view=False,
        total_floors="0"
    ):
            if help_summary:
                print(help_summary)
                exit(0)

            bands.sort()

            # Error checking to prevent case issues
            for band in range(len(bands)):
                bands[band] = bands[band].upper()
                if bands[band] == "BOTH":
                    bands[band] = "Both"

            # Error checking for non-existent bands
            valid_bands = ['2.4G', '5G', '6G', 'Both']
            for band in bands:
                if band not in valid_bands:
                    raise ValueError("Invalid band '%s' used in bands argument!" % band)

            # Check for Both being used independently
            if len(bands) > 1 and "Both" in bands:
                raise ValueError("'Both' test type must be used independently!")

            # validate_args(args)
            if duration.endswith('s') or duration.endswith('S'):
                duration = int(duration[0:-1])
            elif duration.endswith('m') or duration.endswith('M'):
                duration = int(duration[0:-1]) * 60
            elif duration.endswith('h') or duration.endswith('H'):
                duration = int(duration[0:-1]) * 60 * 60
            elif duration.endswith(''):
                duration = int(duration)

            list6G, list6G_bytes, list6G_speed, list6G_urltimes = [], [], [], []
            list5G, list5G_bytes, list5G_speed, list5G_urltimes = [], [], [], []
            list2G, list2G_bytes, list2G_speed, list2G_urltimes = [], [], [], []
            Both, Both_bytes, Both_speed, Both_urltimes = [], [], [], []
            listReal, listReal_bytes, listReal_speed, listReal_urltimes = [], [], [], []  # For real devices (not band specific)
            dict_keys = []
            dict_keys.extend(bands)
            # print(dict_keys)
            final_dict = dict.fromkeys(dict_keys)
            # print(final_dict)
            dict1_keys = ['dl_time', 'min', 'max', 'avg', 'bytes_rd', 'speed', 'url_times']
            for i in final_dict:
                final_dict[i] = dict.fromkeys(dict1_keys)
            print(final_dict)
            min6 = []
            min5 = []
            min2 = []
            min_both = []
            max6 = []
            max5 = []
            max2 = []
            max_both = []
            avg6 = []
            avg2 = []
            avg5 = []
            avg_both = []
            port_list, dev_list, macid_list = [], [], []
            for band in bands:
                # For real devices while ensuring no blocker for Virtual devices
                if client_type == 'Real':
                    ssid = ssid
                    passwd = passwd
                    security = security
                elif band == "2.4G":
                    security = [twog_security]
                    ssid = [twog_ssid]
                    passwd = [twog_passwd]
                elif band == "5G":
                    security = [fiveg_security]
                    ssid = [fiveg_ssid]
                    passwd = [fiveg_passwd]
                elif band == "6G":
                    security = [sixg_security]
                    ssid = [sixg_ssid]
                    passwd = [sixg_passwd]
                elif band == "Both":
                    security = [twog_security, fiveg_security]
                    ssid = [twog_ssid, fiveg_ssid]
                    passwd = [twog_passwd, fiveg_passwd]
                http = http_test.HttpDownload(lfclient_host=self.lanforge_ip, lfclient_port=self.port,
                                    upstream=upstream_port, num_sta=num_stations,
                                    security=security, ap_name=ap_name,
                                    ssid=ssid, password=passwd,
                                    target_per_ten=target_per_ten,
                                    file_size=file_size, bands=band,
                                    twog_radio=twog_radio,
                                    fiveg_radio=fiveg_radio,
                                    sixg_radio=sixg_radio,
                                    client_type=client_type,
                                    lf_username=lf_username, lf_password=lf_password,
                                    result_dir=result_dir,  # FOR WEBGUI
                                    dowebgui=dowebgui,  # FOR WEBGUI
                                    device_list=device_list,
                                    test_name=test_name,  # FOR WEBGUI
                                    get_url_from_file=get_url_from_file,
                                    file_path=file_path,
                                    file_name=file_name,
                                    group_name=group_name,
                                    profile_name=profile_name,
                                    eap_method=eap_method,
                                    eap_identity=eap_identity,
                                    ieee80211=ieee8021x,
                                    ieee80211u=ieee80211u,
                                    ieee80211w=ieee80211w,
                                    enable_pkc=enable_pkc,
                                    bss_transition=bss_transition,
                                    power_save=power_save,
                                    disable_ofdma=disable_ofdma,
                                    roam_ft_ds=roam_ft_ds,
                                    key_management=key_management,
                                    pairwise=pairwise,
                                    private_key=private_key,
                                    ca_cert=ca_cert,
                                    client_cert=client_cert,
                                    pk_passwd=pk_passwd,
                                    pac_file=pac_file,
                                    expected_passfail_value=expected_passfail_value,
                                    device_csv_name=device_csv_name,
                                    wait_time=wait_time,
                                    config=config,
                                    get_live_view= get_live_view,
                                    total_floors = total_floors
                                    )
                if client_type == "Real":
                    if not isinstance(device_list, list):
                        http.device_list = http.filter_iOS_devices(device_list)
                        if len(http.device_list) == 0:
                            logger.info("There are no devices available")
                            exit(1)
                    port_list, dev_list, macid_list, configuration = http.get_real_client_list()
                    if dowebgui and group_name:
                        if len(dev_list) == 0:
                            logger.info("No device is available to run the test")
                            obj = {
                                "status": "Stopped",
                                "configuration_status": "configured"
                            }
                            http.updating_webui_runningjson(obj)
                            return
                        else:
                            obj = {
                                "configured_devices": dev_list,
                                "configuration_status": "configured"
                            }
                            http.updating_webui_runningjson(obj)
                    num_stations = len(port_list)
                if not get_url_from_file:
                    http.file_create(ssh_port=ssh_port)
                else:
                    if file_path is None:
                        print("WARNING: Please Specify the path of the file, if you select the --get_url_from_file")
                        exit(0)
                http.set_values()
                http.precleanup()
                http.build()
                if client_type == 'Real':
                    http.monitor_cx()
                    logger.info(f'Test started on the devices : {http.port_list}')
                test_time = datetime.now()
                # Solution For Leap Year conflict changed it to %Y
                test_time = test_time.strftime("%Y %d %H:%M:%S")
                print("Test started at ", test_time)
                http.start()
                if dowebgui:
                    # FOR WEBGUI, -This fumction is called to fetch the runtime data from layer-4
                    http.monitor_for_runtime_csv(duration)
                elif client_type == 'Real':
                    # To fetch runtime csv during runtime
                    http.monitor_for_runtime_csv(duration)
                else:
                    time.sleep(duration)
                http.stop()
                # taking http.data, which got updated in the monitor_for_runtime_csv method
                if client_type == 'Real':
                    uc_avg_val = http.data['uc_avg']
                    url_times = http.data['url_data']
                    rx_bytes_val = http.data['bytes_rd']
                    print('rx_rate_Val',http.data['rx rate (1m)'])
                    rx_rate_val = list(http.data['rx rate (1m)'])
                else:
                    uc_avg_val = http.my_monitor('uc-avg')
                    url_times = http.my_monitor('total-urls')
                    rx_bytes_val = http.my_monitor('bytes-rd')
                    rx_rate_val = http.my_monitor('rx rate')
                if dowebgui:
                    http.data_for_webui["url_data"] = url_times  # storing the layer-4 url data at the end of test
                if client_type == 'Real':  # for real clients
                    listReal.extend(uc_avg_val)
                    listReal_bytes.extend(rx_bytes_val)
                    listReal_speed.extend(rx_rate_val)
                    listReal_urltimes.extend(url_times)
                    logger.info("%s %s %s", listReal, listReal_bytes, listReal_speed)
                    final_dict[band]['dl_time'] = listReal
                    min2.append(min(listReal))
                    final_dict[band]['min'] = min2
                    max2.append(max(listReal))
                    final_dict[band]['max'] = max2
                    avg2.append((sum(listReal) / num_stations))
                    final_dict[band]['avg'] = avg2
                    final_dict[band]['bytes_rd'] = listReal_bytes
                    final_dict[band]['speed'] = listReal_speed
                    final_dict[band]['url_times'] = listReal_urltimes
                else:
                    if band == "5G":
                        list5G.extend(uc_avg_val)
                        list5G_bytes.extend(rx_bytes_val)
                        list5G_speed.extend(rx_rate_val)
                        list5G_urltimes.extend(url_times)
                        logger.info("%s %s %s %s", list5G, list5G_bytes, list5G_speed, list5G_urltimes)
                        final_dict['5G']['dl_time'] = list5G
                        min5.append(min(list5G))
                        final_dict['5G']['min'] = min5
                        max5.append(max(list5G))
                        final_dict['5G']['max'] = max5
                        avg5.append((sum(list5G) / num_stations))
                        final_dict['5G']['avg'] = avg5
                        final_dict['5G']['bytes_rd'] = list5G_bytes
                        final_dict['5G']['speed'] = list5G_speed
                        final_dict['5G']['url_times'] = list5G_urltimes
                    elif band == "6G":
                        list6G.extend(uc_avg_val)
                        list6G_bytes.extend(rx_bytes_val)
                        list6G_speed.extend(rx_rate_val)
                        list6G_urltimes.extend(url_times)
                        final_dict['6G']['dl_time'] = list6G
                        min6.append(min(list6G))
                        final_dict['6G']['min'] = min6
                        max6.append(max(list6G))
                        final_dict['6G']['max'] = max6
                        avg6.append((sum(list6G) / num_stations))
                        final_dict['6G']['avg'] = avg6
                        final_dict['6G']['bytes_rd'] = list6G_bytes
                        final_dict['6G']['speed'] = list6G_speed
                        final_dict['6G']['url_times'] = list6G_urltimes
                    elif band == "2.4G":
                        list2G.extend(uc_avg_val)
                        list2G_bytes.extend(rx_bytes_val)
                        list2G_speed.extend(rx_rate_val)
                        list2G_urltimes.extend(url_times)
                        logger.info("%s %s %s", list2G, list2G_bytes, list2G_speed)
                        final_dict['2.4G']['dl_time'] = list2G
                        min2.append(min(list2G))
                        final_dict['2.4G']['min'] = min2
                        max2.append(max(list2G))
                        final_dict['2.4G']['max'] = max2
                        avg2.append((sum(list2G) / num_stations))
                        final_dict['2.4G']['avg'] = avg2
                        final_dict['2.4G']['bytes_rd'] = list2G_bytes
                        final_dict['2.4G']['speed'] = list2G_speed
                        final_dict['2.4G']['url_times'] = list2G_urltimes
                    elif bands == "Both":
                        Both.extend(uc_avg_val)
                        Both_bytes.extend(rx_bytes_val)
                        Both_speed.extend(rx_rate_val)
                        Both_urltimes.extend(url_times)
                        final_dict['Both']['dl_time'] = Both
                        min_both.append(min(Both))
                        final_dict['Both']['min'] = min_both
                        max_both.append(max(Both))
                        final_dict['Both']['max'] = max_both
                        avg_both.append((sum(Both) / num_stations))
                        final_dict['Both']['avg'] = avg_both
                        final_dict['Both']['bytes_rd'] = Both_bytes
                        final_dict['Both']['speed'] = Both_speed
                        final_dict['Both']['url_times'] = Both_urltimes

            result_data = final_dict
            print("result", result_data)
            print("Test Finished")
            test_end = datetime.now()
            test_end = test_end.strftime("%Y %d %H:%M:%S")
            print("Test ended at ", test_end)
            s1 = test_time
            s2 = test_end  # for example
            FMT = '%Y %d %H:%M:%S'
            test_duration = datetime.strptime(s2, FMT) - datetime.strptime(s1, FMT)

            info_ssid = []
            info_security = []
            # For real clients
            if client_type == 'Real':
                info_ssid.append(ssid)
                info_security.append(security)
            else:
                for band in bands:
                    if band == "2.4G":
                        info_ssid.append(twog_ssid)
                        info_security.append(twog_security)
                    elif band == "5G":
                        info_ssid.append(fiveg_ssid)
                        info_security.append(fiveg_security)
                    elif band == "6G":
                        info_ssid.append(sixg_ssid)
                        info_security.append(sixg_security)
                    elif band == "Both":
                        info_ssid.append(fiveg_ssid)
                        info_security.append(fiveg_security)
                        info_ssid.append(twog_ssid)
                        info_security.append(twog_security)

            print("total test duration ", test_duration)
            date = str(datetime.now()).split(",")[0].replace(" ", "-").split(".")[0]
            duration = duration
            if int(duration) < 60:
                duration = str(duration) + "s"
            elif int(duration == 60) or (int(duration) > 60 and int(duration) < 3600):
                duration = str(duration / 60) + "m"
            else:
                if int(duration == 3600) or (int(duration) > 3600):
                    duration = str(duration / 3600) + "h"

            android_devices, windows_devices, linux_devices, mac_devices = 0, 0, 0, 0
            all_devices_names = []
            device_type = []
            total_devices = ""
            for i in http.devices_list:
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
                    mac_devices += 1

            # Build total_devices string based on counts
            if android_devices > 0:
                total_devices += f" Android({android_devices})"
            if windows_devices > 0:
                total_devices += f" Windows({windows_devices})"
            if linux_devices > 0:
                total_devices += f" Linux({linux_devices})"
            if mac_devices > 0:
                total_devices += f" Mac({mac_devices})"
            if client_type == "Real":
                if group_name:
                    group_names = ', '.join(configuration.keys())
                    profile_names = ', '.join(configuration.values())
                    configmap = "Groups:" + group_names + " -> Profiles:" + profile_names
                    test_setup_info = {
                        "AP name": ap_name,
                        "Configuration": configmap,
                        "Configured Devices": ", ".join(all_devices_names),
                        "No of Devices": "Total" + f"({len(all_devices_names)})" + total_devices,
                        "Traffic Direction": "Download",
                        "Traffic Duration ": duration
                    }
                else:
                    test_setup_info = {
                        "AP Name": ap_name,
                        "SSID": ssid,
                        "Device List": ", ".join(all_devices_names),
                        "Security": security,
                        "No of Devices": "Total" + f"({len(all_devices_names)})" + total_devices,
                        "Traffic Direction": "Download",
                        "Traffic Duration ": duration
                    }
            else:
                test_setup_info = {
                    "AP Name": ap_name,
                    "SSID": ssid,
                    "Security": security,
                    "No of Devices": num_stations,
                    "Traffic Direction": "Download",
                    "Traffic Duration ": duration
                }
            test_input_infor = {
                "LANforge ip": self.lanforge_ip,
                "Bands": bands,
                "Upstream": upstream_port,
                "Stations": num_stations,
                "SSID": ','.join(filter(None, info_ssid)) if info_ssid else "",
                "Security": ', '.join(filter(None, info_security)) if info_security else "",
                "Duration": duration,
                "Contact": "support@candelatech.com"
            }
            if not file_path:
                test_setup_info["File size"] = file_size
                test_setup_info["File location"] = "/usr/local/lanforge/nginx/html"
                test_input_infor["File size"] = file_size
            else:
                test_setup_info["File location (URLs from the File)"] = file_path
            # dataset = http.download_time_in_sec(result_data=result_data)
            rx_rate = []
            for i in result_data:
                dataset = result_data[i]['dl_time']
                dataset2 = result_data[i]['url_times']
                bytes_rd = result_data[i]['bytes_rd']
                rx_rate = result_data[i]['speed']
            dataset1 = [round(x / 1000000, 4) for x in bytes_rd]
            rx_rate = [round(x / 1000000, 4) for x in rx_rate]  # converting bps to mbps

            lis = []
            if band == "Both":
                for i in range(1, num_stations * 2 + 1):
                    lis.append(i)
            else:
                for i in range(1, num_stations + 1):
                    lis.append(i)

            # dataset2 = http.speed_in_Mbps(result_data=result_data)

            # data = http.summary_calculation(
                # result_data=result_data,
                # bands=bands,
                # threshold_5g=threshold_5g,
                # threshold_2g=threshold_2g,
                # threshold_both=threshold_both)
            # summary_table_value = {
                # "": bands,
                # "PASS/FAIL": data
            # }
            if dowebgui:
                http.data_for_webui["status"] = ["STOPPED"] * len(http.devices_list)
                http.data_for_webui['rx rate (1m)'] = http.data['rx rate (1m)']
                http.data_for_webui['total_err'] = http.data['total_err']
                http.data_for_webui["start_time"] = http.data["start_time"]
                http.data_for_webui["end_time"] = http.data["end_time"]
                http.data_for_webui["remaining_time"] = http.data["remaining_time"]
                df1 = pd.DataFrame(http.data_for_webui)
                df1.to_csv('{}/http_datavalues.csv'.format(http.result_dir), index=False)

            http.generate_report(date, num_stations=num_stations,
                                duration=duration, test_setup_info=test_setup_info, dataset=dataset, lis=lis,
                                bands=bands, threshold_2g=threshold_2g, threshold_5g=threshold_5g,
                                threshold_both=threshold_both, dataset2=dataset2, dataset1=dataset1,
                                # summary_table_value=summary_table_value,
                                result_data=result_data, rx_rate=rx_rate,
                                test_rig=test_rig, test_tag=test_tag, dut_hw_version=dut_hw_version,
                                dut_sw_version=dut_sw_version, dut_model_num=dut_model_num,
                                dut_serial_num=dut_serial_num, test_id=test_id,
                                test_input_infor=test_input_infor, csv_outfile=csv_outfile)
            http.postcleanup()
            # FOR WEBGUI, filling csv at the end to get the last terminal logs
            if dowebgui:
                http.copy_reports_to_home_dir()

    # def run_ftp_test(
    #     self,
    #     local_lf_report_dir="",
    #     upstream_port='eth1',
    #     ssid=None,
    #     passwd=None,
    #     security=None,
    #     group_name=None,
    #     profile_name=None,
    #     file_name=None,
    #     ap_name=None,
    #     ap_ip=None,
    #     twog_radio='wiphy1',
    #     fiveg_radio='wiphy0',
    #     sixg_radio='wiphy2',
    #     lf_username='lanforge',
    #     lf_password='lanforge',
    #     traffic_duration=None,
    #     clients_type=None,
    #     dowebgui=False,
    #     ssh_port=22,
    #     bands=["5G", "2.4G", "6G", "Both"],
    #     directions=["Download", "Upload"],
    #     file_sizes=["2MB", "500MB", "1000MB"],
    #     num_stations=0,
    #     result_dir='',
    #     device_list=[],
    #     test_name=None,
    #     expected_passfail_value=None,
    #     device_csv_name=None,
    #     wait_time=60,
    #     config=False,
    #     test_rig="",
    #     test_tag="",
    #     dut_hw_version="",
    #     dut_sw_version="",
    #     dut_model_num="",
    #     dut_serial_num="",
    #     test_priority="",
    #     test_id="FTP Data",
    #     csv_outfile="",
    #     eap_method='DEFAULT',
    #     eap_identity='',
    #     ieee8021x=False,
    #     ieee80211u=False,
    #     ieee80211w=1,
    #     enable_pkc=False,
    #     bss_transition=False,
    #     power_save=False,
    #     disable_ofdma=False,
    #     roam_ft_ds=False,
    #     key_management='DEFAULT',
    #     pairwise='NA',
    #     private_key='NA',
    #     ca_cert='NA',
    #     client_cert='NA',
    #     pk_passwd='NA',
    #     pac_file='NA',
    #     get_live_view=False,
    #     total_floors="0",
    #     lf_logger_config_json=None,
    #     help_summary=False
    # ):
    #     print('bands',bands)
    #     # exit(0)
    #     if help_summary:
    #         print(help_summary)
    #         exit(0)

    #     # set up logger
    #     logger_config = lf_logger_config.lf_logger_config()
    #     if lf_logger_config_json:
    #         # logger_config.lf_logger_config_json = "lf_logger_config.json"
    #         logger_config.lf_logger_config_json = lf_logger_config_json
    #         logger_config.load_lf_logger_config()

    #     # 1st time stamp for test duration
    #     time_stamp1 = datetime.now()

    #     # use for creating ftp_test dictionary
    #     interation_num = 0

    #     # empty dictionary for whole test data
    #     ftp_data = {}

    #     def pass_fail_duration(band, file_size):
    #         '''Method for set duration according file size and band which are given by user'''

    #         if band == "2.4G":

    #             for size in file_sizes:
    #                 if size == file_size:
    #                     index = list(file_sizes).index(size)
    #         elif band == "5G":
    #             for size in file_sizes:
    #                 if size == file_size:
    #                     index = list(file_sizes).index(size)
    #         else:
    #             for size in file_sizes:
    #                 if size == file_size:
    #                     index = list(file_sizes).index(size)
    #         if duration.isdigit():
    #             duration = int(duration)
    #         else:
    #             duration = float(duration)

    #         return duration

    #     # validate_args(args)
    #     if traffic_duration.endswith('s') or traffic_duration.endswith('S'):
    #         traffic_duration = int(traffic_duration[0:-1])
    #     elif traffic_duration.endswith('m') or traffic_duration.endswith('M'):
    #         traffic_duration = int(traffic_duration[0:-1]) * 60
    #     elif traffic_duration.endswith('h') or traffic_duration.endswith('H'):
    #         traffic_duration = int(traffic_duration[0:-1]) * 60 * 60
    #     elif traffic_duration.endswith(''):
    #         traffic_duration = int(traffic_duration)

    #     # For all combinations ftp_data of directions, file size and client counts, run the test
    #     for band in bands:
    #         for direction in directions:
    #             for file_size in file_sizes:
    #                 # Start Test
    #                 obj = FtpTest(lfclient_host=self.lanforge_ip,
    #                             lfclient_port=self.port,
    #                             result_dir=result_dir,
    #                             upstream=upstream_port,
    #                             dut_ssid=ssid,
    #                             group_name=group_name,
    #                             profile_name=profile_name,
    #                             file_name=file_name,
    #                             dut_passwd=passwd,
    #                             dut_security=security,
    #                             num_sta=num_stations,
    #                             band=band,
    #                             ap_name=ap_name,
    #                             file_size=file_size,
    #                             direction=direction,
    #                             twog_radio=twog_radio,
    #                             fiveg_radio=fiveg_radio,
    #                             sixg_radio=sixg_radio,
    #                             lf_username=lf_username,
    #                             lf_password=lf_password,
    #                             # duration=pass_fail_duration(band, file_size),
    #                             traffic_duration=traffic_duration,
    #                             ssh_port=ssh_port,
    #                             clients_type=clients_type,
    #                             dowebgui=dowebgui,
    #                             device_list=device_list,
    #                             test_name=test_name,
    #                             eap_method=eap_method,
    #                             eap_identity=eap_identity,
    #                             ieee80211=ieee8021x,
    #                             ieee80211u=ieee80211u,
    #                             ieee80211w=ieee80211w,
    #                             enable_pkc=enable_pkc,
    #                             bss_transition=bss_transition,
    #                             power_save=power_save,
    #                             disable_ofdma=disable_ofdma,
    #                             roam_ft_ds=roam_ft_ds,
    #                             key_management=key_management,
    #                             pairwise=pairwise,
    #                             private_key=private_key,
    #                             ca_cert=ca_cert,
    #                             client_cert=client_cert,
    #                             pk_passwd=pk_passwd,
    #                             pac_file=pac_file,
    #                             expected_passfail_val=expected_passfail_value,
    #                             csv_name=device_csv_name,
    #                             wait_time=wait_time,
    #                             config=config,
    #                             get_live_view= get_live_view,
    #                             total_floors = total_floors
    #                             )

    #                 interation_num = interation_num + 1
    #                 obj.file_create()
    #                 if clients_type == "Real":
    #                     if not isinstance(device_list, list):
    #                         obj.device_list = obj.filter_iOS_devices(device_list)
    #                         if len(obj.device_list) == 0:
    #                             logger.info("There are no devices available")
    #                             exit(1)
    #                     endp_input_list, graph_input_list, config_devices, group_device_map = query_real_clients(args)

    #                 if dowebgui and group_name:
    #                     # If no devices are configured,update the Web UI with "Stopped" status
    #                     if len(configured_device) == 0:
    #                         logger.warning("No device is available to run the test")
    #                         obj1 = {
    #                             "status": "Stopped",
    #                             "configuration_status": "configured"
    #                         }
    #                         obj.updating_webui_runningjson(obj1)
    #                         return
    #                     # If devices are configured, update the Web UI with the list of configured devices
    #                     else:
    #                         obj1 = {
    #                             "configured_devices": configured_device,
    #                             "configuration_status": "configured"
    #                         }
    #                         obj.updating_webui_runningjson(obj1)
    #                 obj.set_values()
    #                 obj.precleanup()
    #                 obj.build()
    #                 if not obj.passes():
    #                     logger.info(obj.get_fail_message())
    #                     exit(1)

    #                 if obj.clients_type == 'Real':
    #                     obj.monitor_cx()
    #                     logger.info(f'Test started on the devices : {obj.input_devices_list}')
    #                 # First time stamp
    #                 time1 = datetime.now()
    #                 logger.info("Traffic started running at %s", time1)
    #                 obj.start(False, False)
    #                 # to fetch runtime values during the execution and fill the csv.
    #                 if dowebgui or clients_type == "Real":
    #                     obj.monitor_for_runtime_csv()
    #                     obj.my_monitor_for_real_devices()
    #                 else:
    #                     time.sleep(traffic_duration)
    #                     obj.my_monitor()

    #                 # # return list of download/upload completed time stamp
    #                 # time_list = obj.my_monitor(time1)
    #                 # # print("pass_fail_duration - time_list:{time_list}".format(time_list=time_list))
    #                 # # check pass or fail
    #                 # pass_fail = obj.pass_fail_check(time_list)

    #                 # # dictionary of whole data
    #                 # ftp_data[interation_num] = obj.ftp_test_data(time_list, pass_fail, bands, file_sizes,
    #                 #                                              directions, num_stations)
    #                 # # print("pass_fail_duration - ftp_data:{ftp_data}".format(ftp_data=ftp_data))
    #                 obj.stop()
    #                 print("Traffic stopped running")

    #                 obj.postcleanup()
    #                 time2 = datetime.now()
    #                 logger.info("Test ended at %s", time2)

    #     # 2nd time stamp for test duration
    #     time_stamp2 = datetime.now()

    #     # total time for test duration
    #     # test_duration = str(time_stamp2 - time_stamp1)[:-7]

    #     date = str(datetime.now()).split(",")[0].replace(" ", "-").split(".")[0]

    #     # print(ftp_data)

    #     input_setup_info = {
    #         "AP IP": ap_ip,
    #         "File Size": file_sizes,
    #         "Bands": bands,
    #         "Direction": directions,
    #         "Stations": num_stations,
    #         "Upstream": upstream_port,
    #         "SSID": ssid,
    #         "Security": security,
    #         "Contact": "support@candelatech.com"
    #     }
    #     if dowebgui:
    #         obj.data_for_webui["status"] = ["STOPPED"] * len(obj.url_data)

    #         df1 = pd.DataFrame(obj.data_for_webui)
    #         df1.to_csv('{}/ftp_datavalues.csv'.format(obj.result_dir), index=False)
    #         # copying to home directory i.e home/user_name
    #         # obj.copy_reports_to_home_dir()
    #     # Report generation when groups are specified
    #     if group_name:
    #         obj.generate_report(ftp_data, date, input_setup_info, test_rig=test_rig,
    #                             test_tag=test_tag, dut_hw_version=dut_hw_version,
    #                             dut_sw_version=dut_sw_version, dut_model_num=dut_model_num,
    #                             dut_serial_num=dut_serial_num, test_id=test_id,
    #                             bands=bands, csv_outfile=csv_outfile, local_lf_report_dir=local_lf_report_dir, config_devices=configuration)
    #     # Generating report without group-specific device configuration
    #     else:
    #         obj.generate_report(ftp_data, date, input_setup_info, test_rig=test_rig,
    #                             test_tag=test_tag, dut_hw_version=dut_hw_version,
    #                             dut_sw_version=dut_sw_version, dut_model_num=dut_model_num,
    #                             dut_serial_num=dut_serial_num, test_id=test_id,
    #                             bands=bands, csv_outfile=csv_outfile, local_lf_report_dir=local_lf_report_dir)

    #     if dowebgui:
    #         obj.copy_reports_to_home_dir()

    def start_ftp_test(self,
                       ssid=None,
                       password=None,
                       security=None,
                       ap_name='',
                       band='5g',
                       direction='Download',
                       file_size='12MB',
                       traffic_duration=60,
                       upstream='eth1',
                       lf_username='lanforge',
                       lf_password='lanforge',
                       ssh_port=22,
                       clients_type='Real',
                       device_list=[],
                       background=False,
                       file_name=None,
                 profile_name=None,group_name=None,eap_method=None,
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
                 pac_file=None,expected_passfail_val=None,csv_name=None,wait_time=60,config=False):
        """
        Method to start FTP test on the given device list

        Args:
            ssid (str): SSID of the DUT
            password (str): Password for the SSID. [BLANK] if encryption is open.
            security (str): Encryption for the SSID.
            ap_name (str, optional): Name of the AP. Defaults to ''.
            band (str, optional): 2g, 5g or 6g. Defaults to '5g'.
            direction (str, optional): Download or Upload. Defaults to 'Download'.
            file_size (str, optional): File Size. Defaults to '12MB'.
            traffic_duration (int, optional): Duration of the test in seconds. Defaults to 60.
            upstream (str, optional): Upstream port. Defaults to 'eth1'.
            lf_username (str, optional): Username of LANforge. Defaults to 'lanforge'.
            lf_password (str, optional): Password of LANforge. Defaults to 'lanforge'.
            ssh_port (int, optional): SSH port. Defaults to 22.
            clients_type (str, optional): Clients type. Defaults to 'Real'.
            device_list (list, optional): List of port numbers of the devices in shelf.resource format. Defaults to [].
            background_run(bool): If true, it runs the test without considering test duration.

        Returns:
            data (dict): Test results.
        """
        # for band in bands:
        #     for direction in directions:
        #         for file_size in file_sizes:
        # Start Test
        device_list = self.filter_iOS_devices(device_list)
        if not group_name and len(device_list) == 0:
            print('No devices specified.')
            exit(1)
        if group_name:
            selected_groups = group_name.split(',')
        else:
            selected_groups = []  # Default to empty list if group name is not provided
        if profile_name:
            selected_profiles = profile_name.split(',')
        else:
            selected_profiles = []  # Default to empty list if profile name is not provided

        if csv_name and expected_passfail_val:
            logger.error("Enter either --device_csv_name or --expected_passfail_value")
            exit(1)
        if clients_type == 'Real' and config and group_name is None:
            if ssid and security and security.lower() == 'open' and (password is None or password == ''):
                password = '[BLANK]'
            if ssid is None:
                logger.error('Specify SSID for confiuration, Password(Optional for "open" type security) , Security')
                exit(1)
            elif ssid and password:
                if security is None:
                    logger.error('Security must be provided when SSID and Password specified')
                    exit(1)
                elif security.lower() == 'open' and password != '[BLANK]':
                    logger.error("For a open type security there will be no password or the password should be left blank (i.e., set to '' or [BLANK]).")
                    exit(1)
            elif ssid and password == '[BLANK]' and security and security.lower() != 'open':
                logger.error('Please provide valid password and security configuration')
                exit(1)
        if group_name and (file_name is None or profile_name is None):
            logger.error("Please provide file name and profile name for group configuration")
            exit(1)
        elif file_name and (group_name is None or profile_name is None):
            logger.error("Please provide group name and profile name for file configuration")
            exit(1)
        elif profile_name and (group_name is None or file_name is None):
            logger.error("Please provide group name and file name for profile configuration")
            exit(1)
        if len(selected_groups) != len(selected_profiles):
            logger.error("Number of groups should match number of profiles")
            exit(1)
        elif group_name and profile_name and file_name and device_list != []:
            logger.error("Either group name or device list should be entered, not both")
            exit(1)
        elif ssid and profile_name:
            logger.error("Either SSID or profile name should be given")
            exit(1)
        elif config and group_name is None and ((ssid is None or (password is None and security != 'open') or (password is None and security is None))):
            logger.error("Please provide SSID, password, and security for configuration of devices")
            exit(1)
        elif config and device_list != [] and (ssid is None or password is None or security is None):
            logger.error("Please provide SSID, password, and security when device list is given")
            exit(1)
        self.ftp_test = FtpTest(lfclient_host=self.lanforge_ip,
                        lfclient_port=self.port,
                        upstream=upstream,
                        dut_ssid=ssid,
                        dut_passwd=password,
                        dut_security=security,
                        band=band,
                        ap_name=ap_name,
                        file_size=file_size,
                        direction=direction,
                        lf_username=lf_username,
                        lf_password=lf_password,
                        # duration=pass_fail_duration(band, file_size),
                        traffic_duration=traffic_duration,
                        ssh_port=ssh_port,
                        clients_type=clients_type,
                        device_list=device_list,
                        group_name=group_name,
                        profile_name=profile_name,
                        file_name=file_name,eap_method=eap_method,
                        eap_identity=eap_identity,
                        ieee80211=ieee80211,
                        ieee80211u=ieee80211u,
                        ieee80211w=ieee80211w,
                        enable_pkc=enable_pkc,
                        bss_transition=bss_transition,
                        power_save=power_save,
                        disable_ofdma=disable_ofdma,
                        roam_ft_ds=roam_ft_ds,
                        key_management=key_management,
                        pairwise=pairwise,
                        private_key=private_key,
                        ca_cert=ca_cert,
                        client_cert=client_cert,
                        pk_passwd=pk_passwd,
                        pac_file=pac_file,
                        csv_name=csv_name,expected_passfail_val=expected_passfail_val,wait_time=wait_time,config=config)

        self.ftp_test.data = {}
        self.ftp_test.file_create()
        if clients_type == "Real":
            _, configuration = self.ftp_test.query_realclients()
        self.ftp_test.configuration = configuration
        self.ftp_test.set_values()
        self.ftp_test.count = 0
        self.ftp_test.radio = ['1.1.wiphy0']
        # obj.precleanup()
        self.ftp_test.build()
        if not self.ftp_test.passes():
            logger.info(self.ftp_test.get_fail_message())
            exit(1)

        # First time stamp
        test_start_time = datetime.now()
        logger.info("Traffic started running at {}".format(test_start_time))
        self.ftp_test.start_time = test_start_time
        self.ftp_test.monitor_cx()
        self.ftp_test.start(False, False)
        self.ftp_test.monitor_for_runtime_csv()
        if not background:
            # time.sleep(int(self.ftp_test.traffic_duration))
            self.stop_ftp_test()
            self.generate_report_ftp_test()

    def stop_ftp_test(self):
        """
        Method to stop FTP test.
        """
        self.ftp_test.stop()
        logger.info("Traffic stopped running")
        # self.ftp_test.my_monitor()
        self.ftp_test.postcleanup()
        test_end_time = datetime.now()
        logger.info("Test ended at {}".format(test_end_time))
        self.ftp_test.end_time = test_end_time

    def generate_report_ftp_test(self):
        """
        Method to generate report for FTP test.
        """

        date = str(datetime.now()).split(",")[0].replace(" ", "-").split(".")[0]
        input_setup_info = {
            "AP": self.ftp_test.ap_name,
            "File Size": self.ftp_test.file_size,
            "Bands": self.ftp_test.band,
            "Direction": self.ftp_test.direction,
            "Stations": len(self.ftp_test.device_list),
            "Upstream": self.ftp_test.upstream,
            "SSID": self.ftp_test.ssid,
            "Security": self.ftp_test.security,
            "Contact": "support@candelatech.com"
        }
        if not self.ftp_test.traffic_duration:
            self.ftp_test.traffic_duration = (self.ftp_test.end_time - self.ftp_test.start_time).seconds
        self.ftp_test.generate_report(self.ftp_test.data, date, input_setup_info, bands=self.ftp_test.band,
                        test_rig="", test_tag="", dut_hw_version="",
                        dut_sw_version="", dut_model_num="",
                        dut_serial_num="", test_id="FTP Data",
                        csv_outfile="",
                        local_lf_report_dir="",config_devices=self.ftp_test.configuration)
        return self.ftp_test.data


    def run_qos_test(
        self,
        device_list=[],
        test_name=None,
        result_dir='',
        upstream_port='eth1',
        security="open",
        ssid=None,
        passwd='[BLANK]',
        traffic_type=None,
        upload=None,
        download=None,
        test_duration="2m",
        ap_name="Test-AP",
        tos=None,
        dowebgui=False,
        debug=False,
        help_summary=False,
        group_name=None,
        profile_name=None,
        file_name=None,
        eap_method='DEFAULT',
        eap_identity='',
        ieee8021x=False,
        ieee80211u=False,
        ieee80211w=1,
        enable_pkc=False,
        bss_transition=False,
        power_save=False,
        disable_ofdma=False,
        roam_ft_ds=False,
        key_management='DEFAULT',
        pairwise='NA',
        private_key='NA',
        ca_cert='NA',
        client_cert='NA',
        pk_passwd='NA',
        pac_file='NA',
        expected_passfail_value=None,
        device_csv_name=None,
        wait_time=60,
        config=False,
        get_live_view=False,
        total_floors="0"
    ):
        test_results = {'test_results': []}
        loads = {}
        data = {}

        if download and upload:
            loads = {'upload': str(upload).split(","), 'download': str(download).split(",")}
            loads_data = loads["download"]
        elif download:
            loads = {'upload': [], 'download': str(download).split(",")}
            for i in range(len(download)):
                loads['upload'].append(0)
            loads_data = loads["download"]
        else:
            if upload:
                loads = {'upload': str(upload).split(","), 'download': []}
                for i in range(len(upload)):
                    loads['download'].append(0)
                loads_data = loads["upload"]
        if download and upload:
            direction = 'L3_' + traffic_type.split('_')[1].upper() + '_BiDi'
        elif upload:
            direction = 'L3_' + traffic_type.split('_')[1].upper() + '_UL'
        else:
            direction = 'L3_' + traffic_type.split('_')[1].upper() + '_DL'

        # validate_args(args)
        if test_duration.endswith('s') or test_duration.endswith('S'):
            test_duration = int(test_duration[0:-1])
        elif test_duration.endswith('m') or test_duration.endswith('M'):
            test_duration = int(test_duration[0:-1]) * 60
        elif test_duration.endswith('h') or test_duration.endswith('H'):
            test_duration = int(test_duration[0:-1]) * 60 * 60
        elif test_duration.endswith(''):
            test_duration = int(test_duration)

        for index in range(len(loads_data)):
            throughput_qos = qos_test.ThroughputQOS(host=self.lanforge_ip,
                                            ip=self.lanforge_ip,
                                            port=self.port,
                                            number_template="0000",
                                            ap_name=ap_name,
                                            name_prefix="TOS-",
                                            upstream=upstream_port,
                                            ssid=ssid,
                                            password=passwd,
                                            security=security,
                                            test_duration=test_duration,
                                            use_ht160=False,
                                            side_a_min_rate=int(loads['upload'][index]),
                                            side_b_min_rate=int(loads['download'][index]),
                                            traffic_type=traffic_type,
                                            tos=tos,
                                            csv_direction=direction,
                                            dowebgui=dowebgui,
                                            test_name=test_name,
                                            result_dir=result_dir,
                                            device_list=device_list,
                                            _debug_on=debug,
                                            group_name=group_name,
                                            profile_name=profile_name,
                                            file_name=file_name,
                                            eap_method=eap_method,
                                            eap_identity=eap_identity,
                                            ieee80211=ieee8021x,
                                            ieee80211u=ieee80211u,
                                            ieee80211w=ieee80211w,
                                            enable_pkc=enable_pkc,
                                            bss_transition=bss_transition,
                                            power_save=power_save,
                                            disable_ofdma=disable_ofdma,
                                            roam_ft_ds=roam_ft_ds,
                                            key_management=key_management,
                                            pairwise=pairwise,
                                            private_key=private_key,
                                            ca_cert=ca_cert,
                                            client_cert=client_cert,
                                            pk_passwd=pk_passwd,
                                            pac_file=pac_file,
                                            expected_passfail_val=expected_passfail_value,
                                            csv_name=device_csv_name,
                                            wait_time=wait_time,
                                            config=config,
                                            get_live_view=get_live_view,
                                            total_floors=total_floors
                                            )
            throughput_qos.os_type()
            _, configured_device, _, configuration = throughput_qos.phantom_check()
            if dowebgui and group_name:
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
            # checking if we have atleast one device available for running test
            if throughput_qos.dowebgui == "True":
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
                    }]
                    )
                    df1.to_csv('{}/overall_throughput.csv'.format(throughput_qos.result_dir), index=False)
                    raise ValueError("Aborting the test....")
            throughput_qos.build()
            throughput_qos.monitor_cx()
            throughput_qos.start(False, False)
            time.sleep(10)
            connections_download, connections_upload, drop_a_per, drop_b_per, connections_download_avg, connections_upload_avg, avg_drop_a, avg_drop_b = throughput_qos.monitor()
            logger.info("connections download {}".format(connections_download))
            logger.info("connections upload {}".format(connections_upload))
            throughput_qos.stop()
            time.sleep(5)
            test_results['test_results'].append(throughput_qos.evaluate_qos(connections_download, connections_upload, drop_a_per, drop_b_per))
            data.update(test_results)
        test_end_time = datetime.now().strftime("%Y %d %H:%M:%S")
        print("Test ended at: ", test_end_time)

        input_setup_info = {
            "contact": "support@candelatech.com"
        }
        throughput_qos.cleanup()

        # Update webgui running json with latest entry and test status completed
        if throughput_qos.dowebgui == "True":
            last_entry = throughput_qos.overall[len(throughput_qos.overall) - 1]
            last_entry["status"] = "Stopped"
            last_entry["timestamp"] = datetime.now().strftime("%d/%m %I:%M:%S %p")
            last_entry["remaining_time"] = "0"
            last_entry["end_time"] = last_entry["timestamp"]
            throughput_qos.df_for_webui.append(
                last_entry
            )
            df1 = pd.DataFrame(throughput_qos.df_for_webui)
            df1.to_csv('{}/overall_throughput.csv'.format(result_dir, ), index=False)

            # copying to home directory i.e home/user_name
            throughput_qos.copy_reports_to_home_dir()
        if group_name:
            throughput_qos.generate_report(
                data=data,
                input_setup_info=input_setup_info,
                report_path=throughput_qos.result_dir,
                connections_upload_avg=connections_upload_avg,
                connections_download_avg=connections_download_avg,
                avg_drop_a=avg_drop_a,
                avg_drop_b=avg_drop_b, config_devices=configuration)
        else:
            throughput_qos.generate_report(
                data=data,
                input_setup_info=input_setup_info,
                report_path=throughput_qos.result_dir,
                connections_upload_avg=connections_upload_avg,
                connections_download_avg=connections_download_avg,
                avg_drop_a=avg_drop_a,
                avg_drop_b=avg_drop_b)

    def run_vs_test(
        self,
        ssid=None,
        passwd="something",
        encryp="psk",
        url="www.google.com",
        max_speed=0,
        urls_per_tenm=100,
        duration=None,
        test_name=None,
        dowebgui=False,
        result_dir='',
        lf_logger_config_json=None,
        log_level=None,
        debug=False,
        media_source='1',
        media_quality='0',
        device_list=None,
        webgui_incremental=None,
        incremental=False,
        no_laptops=True,
        postcleanup=False,
        precleanup=False,
        help_summary=False,
        group_name=None,
        profile_name=None,
        file_name=None,
        eap_method='DEFAULT',
        eap_identity='DEFAULT',
        ieee8021x=False,
        ieee80211u=False,
        ieee80211w=1,
        enable_pkc=False,
        bss_transition=False,
        power_save=False,
        disable_ofdma=False,
        roam_ft_ds=False,
        key_management='DEFAULT',
        pairwise='NA',
        private_key='NA',
        ca_cert='NA',
        client_cert='NA',
        pk_passwd='NA',
        pac_file='NA',
        upstream_port='NA',
        expected_passfail_value=None,
        csv_name=None,
        wait_time=60,
        config=False,
        device_csv_name=None,
        get_live_view=False,
        floors=0
    ):

        if self.lanforge_ip is None:
            print("--host/--mgr required")
            exit(1)

        if test_name is None:
            print("--test_name required")
            exit(1)

        media_source_dict = {
            'dash': '1',
            'smooth_streaming': '2',
            'hls': '3',
            'progressive': '4',
            'rtsp': '5'
        }
        media_quality_dict = {
            '4k': '0',
            '8k': '1',
            '1080p': '2',
            '720p': '3',
            '360p': '4'
        }

        if file_name:
            file_name = file_name.removesuffix('.csv')

        media_source, media_quality = media_source.capitalize(), media_quality
        media_source = media_source.lower()
        media_quality = media_quality.lower()

        if any(char.isalpha() for char in media_source):
            media_source = media_source_dict[media_source]

        if any(char.isalpha() for char in media_quality):
            media_quality = media_quality_dict[media_quality]

        logger_config = lf_logger_config.lf_logger_config()

        if log_level:
            logger_config.set_level(level=log_level)

        if lf_logger_config_json:
            logger_config.lf_logger_config_json = lf_logger_config_json
            logger_config.load_lf_logger_config()

        logger = logging.getLogger(__name__)

        obj = VideoStreamingTest(host=self.lanforge_ip, ssid=ssid, passwd=passwd, encryp=encryp,
                                suporrted_release=["7.0", "10", "11", "12"], max_speed=max_speed,
                                url=url, urls_per_tenm=urls_per_tenm, duration=duration,
                                resource_ids=device_list, dowebgui=dowebgui, media_quality=media_quality, media_source=media_source,
                                result_dir=result_dir, test_name=test_name, incremental=incremental, postcleanup=postcleanup,
                                precleanup=precleanup,
                                pass_fail_val=expected_passfail_value,
                                csv_name=device_csv_name,
                                groups=group_name,
                                profiles=profile_name,
                                config=config,
                                file_name=file_name,
                                floors=floors,
                                get_live_view=get_live_view
                                )
        upstream_port = obj.change_port_to_ip(upstream_port)
        obj.validate_args()
        config_obj = DeviceConfig.DeviceConfig(lanforge_ip=self.lanforge_ip, file_name=file_name)
        if not expected_passfail_value and device_csv_name is None:
            config_obj.device_csv_file(csv_name="device.csv")

        resource_ids_sm = []
        resource_set = set()
        resource_list = []
        resource_ids_generated = ""

        if group_name and file_name and profile_name:
            selected_groups = group_name.split(',')
            selected_profiles = profile_name.split(',')
            config_devices = {}
            for i in range(len(selected_groups)):
                config_devices[selected_groups[i]] = selected_profiles[i]
            config_obj.initiate_group()
            asyncio.run(config_obj.connectivity(config_devices, upstream=upstream_port))

            adbresponse = config_obj.adb_obj.get_devices()
            resource_manager = config_obj.laptop_obj.get_devices()
            all_res = {}
            df1 = config_obj.display_groups(config_obj.groups)
            groups_list = df1.to_dict(orient='list')
            group_devices = {}
            for adb in adbresponse:
                group_devices[adb['serial']] = adb['eid']
            for res in resource_manager:
                all_res[res['hostname']] = res['shelf'] + '.' + res['resource']
            eid_list = []
            for grp_name in groups_list.keys():
                for g_name in selected_groups:
                    if grp_name == g_name:
                        for j in groups_list[grp_name]:
                            if j in group_devices.keys():
                                eid_list.append(group_devices[j])
                            elif j in all_res.keys():
                                eid_list.append(all_res[j])
            device_list = ",".join(id for id in eid_list)
        else:
            # When group/profile are not provided
            config_dict = {
                'ssid': ssid,
                'passwd': passwd,
                'enc': encryp,
                'eap_method': eap_method,
                'eap_identity': eap_identity,
                'ieee80211': ieee8021x,
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
                'server_ip': upstream_port
            }
            if device_list:
                all_devices = config_obj.get_all_devices()
                if group_name is None and file_name is None and profile_name is None:
                    dev_list = device_list.split(',')
                    if config:
                        asyncio.run(config_obj.connectivity(device_list=dev_list, wifi_config=config_dict))
            else:
                if config:
                    all_devices = config_obj.get_all_devices()
                    device_list = []
                    for device in all_devices:
                        if device["type"] != 'laptop':
                            device_list.append(device["shelf"] + '.' + device["resource"] + " " + device["serial"])
                        elif device["type"] == 'laptop':
                            device_list.append(device["shelf"] + '.' + device["resource"] + " " + device["hostname"])
                    print("Available devices:")
                    for device in device_list:
                        print(device)
                    device_list = input("Enter the desired resources to run the test:")
                    dev1_list = device_list.split(',')
                    asyncio.run(config_obj.connectivity(device_list=dev1_list, wifi_config=config_dict))
                else:
                    obj.android_devices = obj.devices.get_devices(only_androids=True)
                    selected_devices, report_labels, selected_macs = obj.devices.query_user()
                    if not selected_devices:
                        logging.info("devices donot exist..!!")
                        return

                    obj.android_list = selected_devices
                    # Verify if all resource IDs are valid for Android devices
                    if obj.android_list:
                        resource_ids = ",".join([item.split(".")[1] for item in obj.android_list])

                        num_list = list(map(int, resource_ids.split(',')))

                        # Sort the list
                        num_list.sort()

                        # Join the sorted list back into a string
                        sorted_string = ','.join(map(str, num_list))

                        obj.resource_ids = sorted_string
                        resource_ids1 = list(map(int, sorted_string.split(',')))
                        modified_list = list(map(lambda item: int(item.split('.')[1]), obj.android_devices))
                        if not all(x in modified_list for x in resource_ids1):
                            logging.info("Verify Resource ids, as few are invalid...!!")
                            exit()
                        resource_ids_sm = obj.resource_ids
                        resource_list = resource_ids_sm.split(',')
                        resource_set = set(resource_list)
                        resource_list_sorted = sorted(resource_set)
                        resource_ids_generated = ','.join(resource_list_sorted)
                        available_resources = list(resource_set)

        if dowebgui:
            resource_ids_sm = device_list.split(',')
            resource_set = set(resource_ids_sm)
            resource_list = sorted(resource_set)
            resource_ids_generated = ','.join(resource_list)
            resource_list_sorted = resource_list
            selected_devices, report_labels, selected_macs = obj.devices.query_user(dowebgui=dowebgui, device_list=resource_ids_generated)
            obj.resource_ids = ",".join(id.split(".")[1] for id in device_list.split(","))
            available_resources = [int(num) for num in obj.resource_ids.split(',')]
        else:
            obj.android_devices = obj.devices.get_devices(only_androids=True)
            if device_list:
                device_list = device_list.split(',')
                # Extract resource IDs (after the dot), remove duplicates, and sort them
                resource_ids = sorted(set(int(item.split('.')[1]) for item in device_list if '.' in item))
                resource_list_sorted = resource_ids
                obj.resource_ids = ','.join(map(str, resource_ids))
                # Create a set of Android device IDs (e.g., "resource.123")
                android_device_ids = set(obj.android_devices)
                android_device_short_ids = {device.split('.')[0] + '.' + device.split('.')[1] for device in android_device_ids}
                obj.android_list = [dev for dev in android_device_short_ids if dev in device_list]
                # Log any devices in the list that are not available
                for dev in device_list:
                    if dev not in android_device_short_ids:
                        logger.info(f"{dev} device is not available")
                # Final list of available Android resource IDs
                available_resources = sorted(set(int(dev.split('.')[1]) for dev in obj.android_list))
                logger.info(f"Available devices: {available_resources}")
        if len(available_resources) != 0:
            available_resources = obj.filter_ios_devices(available_resources)
        if len(available_resources) == 0:
            logger.info("No devices which are selected are available in the lanforge")
            exit()
        gave_incremental = False
        if incremental and not webgui_incremental:
            if obj.resource_ids:
                logging.info("The total available devices are {}".format(len(available_resources)))
                obj.incremental = input('Specify incremental values as 1,2,3 : ')
                obj.incremental = [int(x) for x in obj.incremental.split(',')]
            else:
                logging.info("incremental Values are not needed as Android devices are not selected..")
        elif not incremental:
            gave_incremental = True
            obj.incremental = [len(available_resources)]

        if webgui_incremental:
            incremental = [int(x) for x in webgui_incremental.split(',')]
            if (len(webgui_incremental) == 1 and incremental[0] != len(resource_list_sorted)) or (len(webgui_incremental) > 1):
                obj.incremental = incremental

        if obj.incremental and obj.resource_ids:
            if obj.incremental[-1] > len(available_resources):
                logging.info("Exiting the program as incremental values are greater than the resource ids provided")
                exit()
            elif obj.incremental[-1] < len(available_resources) and len(obj.incremental) > 1:
                logging.info("Exiting the program as the last incremental value must be equal to selected devices")
                exit()

        # To create cx for selected devices
        obj.build()

        # To set media source and media quality
        time.sleep(10)

        # obj.run
        test_time = datetime.now()
        test_time = test_time.strftime("%b %d %H:%M:%S")

        logging.info("Initiating Test...")

        individual_dataframe_columns = []

        keys = list(obj.http_profile.created_cx.keys())

        # Extend individual_dataframe_column with dynamically generated column names
        for i in range(len(keys)):
            individual_dataframe_columns.extend([
                f'video_format_bitrate_{keys[i]}',
                f'total_wait_time_{keys[i]}',
                f'total_urls_{keys[i]}',
                f'RSSI_{keys[i]}',
                f'Link Speed_{keys[i]}',
                f'Total Buffer_{keys[i]}',
                f'Total Errors_{keys[i]}',
                f'Min_Video_Rate_{keys[i]}',
                f'Max_Video_Rate_{keys[i]}',
                f'Avg_Video_Rate_{keys[i]}',
                f'bytes_rd_{keys[i]}',
                f'rx rate_{keys[i]} bps',
                f'frame_rate_{keys[i]}',
                f'Video Quality_{keys[i]}'
            ])

        individual_dataframe_columns.extend(['overall_video_format_bitrate', 'timestamp', 'iteration', 'start_time', 'end_time', 'remaining_Time', 'status'])
        individual_df = pd.DataFrame(columns=individual_dataframe_columns)

        cx_order_list = []
        index = 0
        file_path = ""

        # Parsing test_duration
        if duration.endswith('s') or duration.endswith('S'):
            duration = round(int(duration[0:-1]) / 60, 2)

        elif duration.endswith('m') or duration.endswith('M'):
            duration = int(duration[0:-1])

        elif duration.endswith('h') or duration.endswith('H'):
            duration = int(duration[0:-1]) * 60

        elif duration.endswith(''):
            duration = int(duration)

        incremental_capacity_list_values = obj.get_incremental_capacity_list()
        if incremental_capacity_list_values[-1] != len(available_resources):
            logger.error("Incremental capacity doesnt match available devices")
            if postcleanup:
                obj.postcleanup()
            exit(1)
        # Process resource IDs and incremental values if specified
        if obj.resource_ids:
            if obj.incremental:
                test_setup_info_incremental_values = ','.join([str(n) for n in incremental_capacity_list_values])
                if len(obj.incremental) == len(available_resources):
                    test_setup_info_total_duration = duration
                elif len(obj.incremental) == 1 and len(available_resources) > 1:
                    if obj.incremental[0] == len(available_resources):
                        test_setup_info_total_duration = duration
                    else:
                        div = len(available_resources) // obj.incremental[0]
                        mod = len(available_resources) % obj.incremental[0]
                        if mod == 0:
                            test_setup_info_total_duration = duration * (div)
                        else:
                            test_setup_info_total_duration = duration * (div + 1)
                else:
                    test_setup_info_total_duration = duration * len(incremental_capacity_list_values)
            else:
                test_setup_info_total_duration = duration

            if webgui_incremental:
                test_setup_info_incremental_values = ','.join([str(n) for n in incremental_capacity_list_values])
            elif gave_incremental:
                test_setup_info_incremental_values = "No Incremental Value provided"
            obj.total_duration = test_setup_info_total_duration

        actual_start_time = datetime.now()

        iterations_before_test_stopped_by_user = []

        # Calculate and manage cx_order_list ( list of cross connections to run ) based on incremental values
        if obj.resource_ids:
            # Check if incremental  is specified
            if obj.incremental:

                # Case 1: Incremental list has only one value and it equals the length of keys
                if len(obj.incremental) == 1 and obj.incremental[0] == len(keys):
                    cx_order_list.append(keys[index:])

                # Case 2: Incremental list has only one value but length of keys is greater than 1
                elif len(obj.incremental) == 1 and len(keys) > 1:
                    incremental_value = obj.incremental[0]
                    max_index = len(keys)
                    index = 0

                    while index < max_index:
                        next_index = min(index + incremental_value, max_index)
                        cx_order_list.append(keys[index:next_index])
                        index = next_index

                # Case 3: Incremental list has multiple values and length of keys is greater than 1
                elif len(obj.incremental) != 1 and len(keys) > 1:

                    index = 0
                    for num in obj.incremental:

                        cx_order_list.append(keys[index: num])
                        index = num

                    if index < len(keys):
                        cx_order_list.append(keys[index:])

                # Iterate over cx_order_list to start tests incrementally
                for i in range(len(cx_order_list)):
                    if i == 0:
                        obj.data["start_time_webGUI"] = [datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
                        end_time_webGUI = (datetime.now() + timedelta(minutes=obj.total_duration)).strftime('%Y-%m-%d %H:%M:%S')
                        obj.data['end_time_webGUI'] = [end_time_webGUI]

                    # time.sleep(10)

                    # Start specific devices based on incremental capacity
                    obj.start_specific(cx_order_list[i])
                    if cx_order_list[i]:
                        logging.info("Test started on Devices with resource Ids : {selected}".format(selected=cx_order_list[i]))
                    else:
                        logging.info("Test started on Devices with resource Ids : {selected}".format(selected=cx_order_list[i]))
                    file_path = "video_streaming_realtime_data.csv"
                    if end_time_webGUI < datetime.now().strftime('%Y-%m-%d %H:%M:%S'):
                        obj.data['remaining_time_webGUI'] = ['0:00']
                    else:
                        date_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        obj.data['remaining_time_webGUI'] = [datetime.strptime(end_time_webGUI, "%Y-%m-%d %H:%M:%S") - datetime.strptime(date_time, "%Y-%m-%d %H:%M:%S")]

                    if dowebgui:
                        file_path = os.path.join(obj.result_dir, "../../Running_instances/{}_{}_running.json".format(obj.host, obj.test_name))
                        if os.path.exists(file_path):
                            with open(file_path, 'r') as file:
                                data = json.load(file)
                                if data["status"] != "Running":
                                    break
                        test_stopped_by_user = obj.monitor_for_runtime_csv(duration, file_path, individual_df, i, actual_start_time, resource_list_sorted, cx_order_list[i])
                    else:
                        test_stopped_by_user = obj.monitor_for_runtime_csv(duration, file_path, individual_df, i, actual_start_time, resource_list_sorted, cx_order_list[i])
                    if not test_stopped_by_user:
                        # Append current iteration index to iterations_before_test_stopped_by_user
                        iterations_before_test_stopped_by_user.append(i)
                    else:
                        # Append current iteration index to iterations_before_test_stopped_by_user
                        iterations_before_test_stopped_by_user.append(i)
                        break
        obj.stop()

        if obj.resource_ids:

            date = str(datetime.now()).split(",")[0].replace(" ", "-").split(".")[0]
            username = []

            try:
                eid_data = obj.json_get("ports?fields=alias,mac,mode,Parent Dev,rx-rate,tx-rate,ssid,signal")
            except KeyError:
                logger.error("Error: 'interfaces' key not found in port data")
                exit(1)

            resource_ids = list(map(int, obj.resource_ids.split(',')))
            for alias in eid_data["interfaces"]:
                for i in alias:
                    if int(i.split(".")[1]) > 1 and alias[i]["alias"] == 'wlan0':
                        resource_hw_data = obj.json_get("/resource/" + i.split(".")[0] + "/" + i.split(".")[1])
                        hw_version = resource_hw_data['resource']['hw version']
                        if not hw_version.startswith(('Win', 'Linux', 'Apple')) and int(resource_hw_data['resource']['eid'].split('.')[1]) in resource_ids:
                            username.append(resource_hw_data['resource']['user'])

            device_list_str = ','.join([f"{name} ( Android )" for name in username])

            test_setup_info = {
                "Testname": test_name,
                "Device List": device_list_str,
                "No of Devices": "Total" + "( " + str(len(keys)) + " ): Android(" + str(len(keys)) + ")",
                "Incremental Values": "",
                "URL": url,
                "Media Source": media_source.upper(),
                "Media Quality": media_quality
            }
            test_setup_info['Incremental Values'] = test_setup_info_incremental_values
            test_setup_info['Total Duration (min)'] = str(test_setup_info_total_duration)

        logging.info("Test Completed")

        # prev_inc_value = 0
        if obj.resource_ids and obj.incremental:
            obj.generate_report(date, list(set(iterations_before_test_stopped_by_user)), test_setup_info=test_setup_info, realtime_dataset=individual_df, cx_order_list=cx_order_list)
        elif obj.resource_ids:
            obj.generate_report(date, list(set(iterations_before_test_stopped_by_user)), test_setup_info=test_setup_info, realtime_dataset=individual_df)

        # Perform post-cleanup operations
        if postcleanup:
            obj.postcleanup()

        if dowebgui:
            obj.copy_reports_to_home_dir()

    def run_throughput_test(
        self,
        device_list=[],
        upstream_port='eth1',
        ssid=None,
        passwd='[BLANK]',
        traffic_type=None,
        upload='2560',
        download='2560',
        test_duration='',
        report_timer='1s',
        ap_name='Test-AP',
        dowebgui=False,
        tos='Best_Efforts',
        packet_size='-1',
        incremental_capacity=[],
        load_type='wc_per_client_load',
        do_interopability=False,
        postcleanup=False,
        precleanup=False,
        incremental=False,
        security='open',
        test_name=None,
        result_dir='',
        get_live_view=False,
        total_floors='0',
        expected_passfail_value=None,
        device_csv_name=None,
        eap_method='DEFAULT',
        eap_identity='',
        ieee8021x=False,
        ieee80211u=False,
        ieee80211w=1,
        enable_pkc=False,
        bss_transition=False,
        power_save=False,
        disable_ofdma=False,
        roam_ft_ds=False,
        key_management='DEFAULT',
        pairwise='NA',
        private_key='NA',
        ca_cert='NA',
        client_cert='NA',
        pk_passwd='NA',
        pac_file='NA',
        file_name=None,
        group_name=None,
        profile_name=None,
        wait_time=60,
        config=False,
        default_config=False,
        thpt_mbps=False,
        help_summary=False
    ):

        if help_summary:
            print(help_summary)
            exit(0)

        if dowebgui:
            if (upload == '0'):
                upload = '2560'
            if (download == '0'):
                download = '2560'

        logger_config = lf_logger_config.lf_logger_config()

        if(thpt_mbps):
            if download != '2560' and download != '0' and upload != '0' and upload != '2560':
                download = str(int(download) * 1000000)
                upload = str(int(upload) * 1000000)
            elif upload != '2560' and upload != '0':
                upload = str(int(upload) * 1000000)
            else:
                download = str(int(download) * 1000000)
        loads = {}
        iterations_before_test_stopped_by_user = []
        gave_incremental = False
        # Case based on download and upload arguments are provided
        if download and upload:
            loads = {'upload': str(upload).split(","), 'download': str(download).split(",")}
            loads_data = loads["download"]
        elif download:
            loads = {'upload': [], 'download': str(download).split(",")}
            for i in range(len(download)):
                loads['upload'].append(2560)
            loads_data = loads["download"]
        else:
            if upload:
                loads = {'upload': str(upload).split(","), 'download': []}
                for i in range(len(upload)):
                    loads['download'].append(2560)
                loads_data = loads["upload"]

        if download != '2560' and download != '0' and upload != '0' and upload != '2560':
            csv_direction = 'L3_' + traffic_type.split('_')[1].upper() + '_BiDi'
        elif upload != '2560' and upload != '0':
            csv_direction = 'L3_' + traffic_type.split('_')[1].upper() + '_UL'
        else:
            csv_direction = 'L3_' + traffic_type.split('_')[1].upper() + '_DL'

        # validate_args(args)
        if incremental_capacity == 'no_increment' and dowebgui:
            incremental_capacity = str(len(device_list.split(",")))
            gave_incremental = True

        if do_interopability:
            incremental_capacity = "1"

        # Parsing test_duration
        if test_duration.endswith('s') or test_duration.endswith('S'):
            test_duration = int(test_duration[0:-1])

        elif test_duration.endswith('m') or test_duration.endswith('M'):
            test_duration = int(test_duration[0:-1]) * 60

        elif test_duration.endswith('h') or test_duration.endswith('H'):
            test_duration = int(test_duration[0:-1]) * 60 * 60

        elif test_duration.endswith(''):
            test_duration = int(test_duration)

        # Parsing report_timer
        if report_timer.endswith('s') or report_timer.endswith('S'):
            report_timer = int(report_timer[0:-1])

        elif report_timer.endswith('m') or report_timer.endswith('M'):
            report_timer = int(report_timer[0:-1]) * 60

        elif report_timer.endswith('h') or report_timer.endswith('H'):
            report_timer = int(report_timer[0:-1]) * 60 * 60

        elif test_duration.endswith(''):
            report_timer = int(report_timer)

        if (int(packet_size) < 16 or int(packet_size) > 65507) and int(packet_size) != -1:
            logger.error("Packet size should be greater than 16 bytes and less than 65507 bytes incorrect")
            return

        for index in range(len(loads_data)):
            throughput = Throughput(host=self.lanforge_ip,
                                    ip=self.lanforge_ip,
                                    port=self.port,
                                    number_template="0000",
                                    ap_name=ap_name,
                                    name_prefix="TOS-",
                                    upstream=upstream_port,
                                    ssid=ssid,
                                    password=passwd,
                                    security=security,
                                    test_duration=test_duration,
                                    use_ht160=False,
                                    side_a_min_rate=int(loads['upload'][index]),
                                    side_b_min_rate=int(loads['download'][index]),
                                    side_a_min_pdu=int(packet_size),
                                    side_b_min_pdu=int(packet_size),
                                    traffic_type=traffic_type,
                                    tos=tos,
                                    dowebgui=dowebgui,
                                    test_name=test_name,
                                    result_dir=result_dir,
                                    device_list=device_list,
                                    incremental_capacity=incremental_capacity,
                                    report_timer=report_timer,
                                    load_type=load_type,
                                    do_interopability=do_interopability,
                                    incremental=incremental,
                                    precleanup=precleanup,
                                    get_live_view= get_live_view,
                                    total_floors = total_floors,
                                    csv_direction=csv_direction,
                                    expected_passfail_value=expected_passfail_value,
                                    device_csv_name=device_csv_name,
                                    file_name=file_name,
                                    group_name=group_name,
                                    profile_name=profile_name,
                                    eap_method=eap_method,
                                    eap_identity=eap_identity,
                                    ieee80211=ieee8021x,
                                    ieee80211u=ieee80211u,
                                    ieee80211w=ieee80211w,
                                    enable_pkc=enable_pkc,
                                    bss_transition=bss_transition,
                                    power_save=power_save,
                                    disable_ofdma=disable_ofdma,
                                    roam_ft_ds=roam_ft_ds,
                                    key_management=key_management,
                                    pairwise=pairwise,
                                    private_key=private_key,
                                    ca_cert=ca_cert,
                                    client_cert=client_cert,
                                    pk_passwd=pk_passwd,
                                    pac_file=pac_file,
                                    wait_time=wait_time,
                                    config=config
                                    )

            if gave_incremental:
                throughput.gave_incremental = True
            throughput.os_type()

            check_condition, clients_to_run = throughput.phantom_check()

            if check_condition == False:
                return

            check_increment_condition = throughput.check_incremental_list()

            if check_increment_condition == False:
                logger.error("Incremental values given for selected devices are incorrect")
                return

            elif (len(incremental_capacity) > 0 and check_increment_condition == False):
                logger.error("Incremental values given for selected devices are incorrect")
                return

            created_cxs = throughput.build()
            time.sleep(10)
            created_cxs = list(created_cxs.keys())
            individual_dataframe_column = []

            to_run_cxs, to_run_cxs_len, created_cx_lists_keys, incremental_capacity_list = throughput.get_incremental_capacity_list()

            for i in range(len(clients_to_run)):

                # Extend individual_dataframe_column with dynamically generated column names
                individual_dataframe_column.extend([f'Download{clients_to_run[i]}', f'Upload{clients_to_run[i]}', f'Rx % Drop A {clients_to_run[i]}',
                                                f'Rx % Drop B{clients_to_run[i]}', f'RSSI {clients_to_run[i]} ', f'Tx-Rate {clients_to_run[i]} ', f'Rx-Rate {clients_to_run[i]} '])

            individual_dataframe_column.extend(['Overall Download', 'Overall Upload', 'Overall Rx % Drop A', 'Overall Rx % Drop B', 'Iteration',
                                            'TIMESTAMP', 'Start_time', 'End_time', 'Remaining_Time', 'Incremental_list', 'status'])
            individual_df = pd.DataFrame(columns=individual_dataframe_column)

            overall_start_time = datetime.now()
            overall_end_time = overall_start_time + timedelta(seconds=int(test_duration) * len(incremental_capacity_list))

            for i in range(len(to_run_cxs)):
                if do_interopability:
                    # To get resource of device under test in interopability
                    device_to_run_resource = throughput.extract_digits_until_alpha(to_run_cxs[i][0])
                # Check the load type specified by the user
                if load_type == "wc_intended_load":
                    # Perform intended load for the current iteration
                    throughput.perform_intended_load(i, incremental_capacity_list)
                    if i != 0:

                        # Stop throughput testing if not the first iteration
                        throughput.stop()

                    # Start specific connections for the current iteration
                    throughput.start_specific(created_cx_lists_keys[:incremental_capacity_list[i]])
                else:
                    if (do_interopability and i != 0):
                        throughput.stop_specific(to_run_cxs[i - 1])
                        time.sleep(5)
                    if not default_config:
                        if (do_interopability and i == 0):
                            throughput.disconnect_all_devices()
                        if do_interopability and "iOS" not in to_run_cxs[i][0]:
                            logger.info("Configuring device of resource{}".format(to_run_cxs[i][0]))
                            throughput.configure_specific([device_to_run_resource])
                    throughput.start_specific(to_run_cxs[i])

                # Determine device names based on the current iteration
                device_names = created_cx_lists_keys[:to_run_cxs_len[i][-1]]

                # Monitor throughput and capture all dataframes and test stop status
                all_dataframes, test_stopped_by_user = throughput.monitor(i, individual_df, device_names, incremental_capacity_list, overall_start_time, overall_end_time)
                if do_interopability and "iOS" not in to_run_cxs[i][0] and not default_config:
                    # logger.info("Disconnecting device of resource{}".format(to_run_cxs[i][0]))
                    throughput.disconnect_all_devices([device_to_run_resource])
                # Check if the test was stopped by the user
                if test_stopped_by_user == False:

                    # Append current iteration index to iterations_before_test_stopped_by_user
                    iterations_before_test_stopped_by_user.append(i)
                else:

                    # Append current iteration index to iterations_before_test_stopped_by_user
                    iterations_before_test_stopped_by_user.append(i)
                    break

        #     logger.info("connections download {}".format(connections_download))
        #     logger.info("connections upload {}".format(connections_upload))
        throughput.stop()
        if postcleanup:
            throughput.cleanup()
        throughput.generate_report(list(set(iterations_before_test_stopped_by_user)), incremental_capacity_list, data=all_dataframes, data1=to_run_cxs_len, report_path=throughput.result_dir)
        if throughput.dowebgui:
            # copying to home directory i.e home/user_name
            throughput.copy_reports_to_home_dir()

    def run_mc_test(self,args):
        endp_types = "lf_udp"

        help_summary = '''\
    The Layer 3 Traffic Generation Test is designed to test the performance of the
    Access Point by running layer 3 TCP and/or UDP Traffic.  Layer-3 Cross-Connects represent a stream
    of data flowing through the system under test. A Cross-Connect (CX) is composed of two Endpoints,
    each of which is associated with a particular Port (physical or virtual interface).

    The test will create stations, create CX traffic between upstream port and stations, run traffic
    and generate a report.
    '''
        # args = parse_args()

        if args.help_summary:
            print(help_summary)
            exit(0)

        test_name = ""
        ip = ""
        if args.dowebgui:
            logger.info("In webGUI execution")
            if args.dowebgui:
                test_name = args.test_name
                ip = args.lfmgr
                logger.info(" dowebgui %s %s %s", args.dowebgui, test_name, ip)

        # initialize pass / fail
        test_passed = False

        # Configure logging
        logger_config = lf_logger_config.lf_logger_config()

        # set the logger level to debug
        if args.log_level:
            logger_config.set_level(level=args.log_level)

        # lf_logger_config_json will take presidence to changing debug levels
        if args.lf_logger_config_json:
            # logger_config.lf_logger_config_json = "lf_logger_config.json"
            logger_config.lf_logger_config_json = args.lf_logger_config_json
            logger_config.load_lf_logger_config()

        # validate_args(args)
        endp_input_list = []
        graph_input_list = []
        if args.real:
            endp_input_list, graph_input_list, config_devices, group_device_map = query_real_clients(args)
        # Validate existing station list configuration if specified before starting test
        if not args.use_existing_station_list and args.existing_station_list:
            logger.error("Existing stations specified, but argument \'--use_existing_station_list\' not specified")
            exit(1)
        elif args.use_existing_station_list and not args.existing_station_list:
            logger.error(
                "Argument \'--use_existing_station_list\' specified, but no existing stations provided. See \'--existing_station_list\'")
            exit(1)

        # Gather data for test reporting and KPI generation
        logger.info("Read in command line paramaters")
        interopt_mode = args.interopt_mode

        if args.endp_type:
            endp_types = args.endp_type

        if args.radio:
            radios = args.radio
        else:
            radios = None

        MAX_NUMBER_OF_STATIONS = 1000

        # Lists to help with station creation
        radio_name_list = []
        number_of_stations_per_radio_list = []
        ssid_list = []
        ssid_password_list = []
        ssid_security_list = []
        station_lists = []
        existing_station_lists = []

        # wifi settings configuration
        wifi_mode_list = []
        wifi_enable_flags_list = []

        # optional radio configuration
        reset_port_enable_list = []
        reset_port_time_min_list = []
        reset_port_time_max_list = []

        # wifi extra configuration
        key_mgmt_list = []
        pairwise_list = []
        group_list = []
        psk_list = []
        wep_key_list = []
        ca_cert_list = []
        eap_list = []
        identity_list = []
        anonymous_identity_list = []
        phase1_list = []
        phase2_list = []
        passwd_list = []
        pin_list = []
        pac_file_list = []
        private_key_list = []
        pk_password_list = []
        hessid_list = []
        realm_list = []
        client_cert_list = []
        imsi_list = []
        milenage_list = []
        domain_list = []
        roaming_consortium_list = []
        venue_group_list = []
        network_type_list = []
        ipaddr_type_avail_list = []
        network_auth_type_list = []
        anqp_3gpp_cell_net_list = []
        ieee80211w_list = []

        logger.debug("Parse radio arguments used for station configuration")
        if radios is not None:
            logger.info("radios {}".format(radios))
            for radio_ in radios:
                radio_keys = ['radio', 'stations', 'ssid', 'ssid_pw', 'security']
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

                logger.debug("radio_dict {}".format(radio_info_dict))

                for key in radio_keys:
                    if key not in radio_info_dict:
                        logger.critical(
                            "missing config, for the {}, all of the following need to be present {} ".format(
                                key, radio_keys))
                        exit(1)

                radio_name_list.append(radio_info_dict['radio'])
                number_of_stations_per_radio_list.append(
                    radio_info_dict['stations'])
                ssid_list.append(radio_info_dict['ssid'])
                ssid_password_list.append(radio_info_dict['ssid_pw'])
                ssid_security_list.append(radio_info_dict['security'])

                # check for set_wifi_extra
                # check for wifi_settings
                wifi_extra_keys = ['wifi_extra']
                wifi_extra_found = False
                for wifi_extra_key in wifi_extra_keys:
                    if wifi_extra_key in radio_info_dict:
                        logger.info("wifi_extra_keys found")
                        wifi_extra_found = True
                        break

                if wifi_extra_found:
                    logger.debug("wifi_extra: {extra}".format(
                        extra=radio_info_dict['wifi_extra']))

                    wifi_extra_dict = dict(
                        map(
                            lambda x: x.split('&&'),
                            str(radio_info_dict['wifi_extra']).replace(
                                '"',
                                '').replace(
                                '[',
                                '').replace(
                                ']',
                                '').replace(
                                "'",
                                "").replace(
                                ",",
                                " ").replace(
                                "!!",
                                " "
                            )
                            .split()))

                    logger.info("wifi_extra_dict: {wifi_extra}".format(
                        wifi_extra=wifi_extra_dict))

                    if 'key_mgmt' in wifi_extra_dict:
                        key_mgmt_list.append(wifi_extra_dict['key_mgmt'])
                    else:
                        key_mgmt_list.append('[BLANK]')

                    if 'pairwise' in wifi_extra_dict:
                        pairwise_list.append(wifi_extra_dict['pairwise'])
                    else:
                        pairwise_list.append('[BLANK]')

                    if 'group' in wifi_extra_dict:
                        group_list.append(wifi_extra_dict['group'])
                    else:
                        group_list.append('[BLANK]')

                    if 'psk' in wifi_extra_dict:
                        psk_list.append(wifi_extra_dict['psk'])
                    else:
                        psk_list.append('[BLANK]')

                    if 'wep_key' in wifi_extra_dict:
                        wep_key_list.append(wifi_extra_dict['wep_key'])
                    else:
                        wep_key_list.append('[BLANK]')

                    if 'ca_cert' in wifi_extra_dict:
                        ca_cert_list.append(wifi_extra_dict['ca_cert'])
                    else:
                        ca_cert_list.append('[BLANK]')

                    if 'eap' in wifi_extra_dict:
                        eap_list.append(wifi_extra_dict['eap'])
                    else:
                        eap_list.append('[BLANK]')

                    if 'identity' in wifi_extra_dict:
                        identity_list.append(wifi_extra_dict['identity'])
                    else:
                        identity_list.append('[BLANK]')

                    if 'anonymous' in wifi_extra_dict:
                        anonymous_identity_list.append(
                            wifi_extra_dict['anonymous'])
                    else:
                        anonymous_identity_list.append('[BLANK]')

                    if 'phase1' in wifi_extra_dict:
                        phase1_list.append(wifi_extra_dict['phase1'])
                    else:
                        phase1_list.append('[BLANK]')

                    if 'phase2' in wifi_extra_dict:
                        phase2_list.append(wifi_extra_dict['phase2'])
                    else:
                        phase2_list.append('[BLANK]')

                    if 'passwd' in wifi_extra_dict:
                        passwd_list.append(wifi_extra_dict['passwd'])
                    else:
                        passwd_list.append('[BLANK]')

                    if 'pin' in wifi_extra_dict:
                        pin_list.append(wifi_extra_dict['pin'])
                    else:
                        pin_list.append('[BLANK]')

                    if 'pac_file' in wifi_extra_dict:
                        pac_file_list.append(wifi_extra_dict['pac_file'])
                    else:
                        pac_file_list.append('[BLANK]')

                    if 'private_key' in wifi_extra_dict:
                        private_key_list.append(wifi_extra_dict['private_key'])
                    else:
                        private_key_list.append('[BLANK]')

                    if 'pk_password' in wifi_extra_dict:
                        pk_password_list.append(wifi_extra_dict['pk_password'])
                    else:
                        pk_password_list.append('[BLANK]')

                    if 'hessid' in wifi_extra_dict:
                        hessid_list.append(wifi_extra_dict['hessid'])
                    else:
                        hessid_list.append("00:00:00:00:00:00")

                    if 'realm' in wifi_extra_dict:
                        realm_list.append(wifi_extra_dict['realm'])
                    else:
                        realm_list.append('[BLANK]')

                    if 'client_cert' in wifi_extra_dict:
                        client_cert_list.append(wifi_extra_dict['client_cert'])
                    else:
                        client_cert_list.append('[BLANK]')

                    if 'imsi' in wifi_extra_dict:
                        imsi_list.append(wifi_extra_dict['imsi'])
                    else:
                        imsi_list.append('[BLANK]')

                    if 'milenage' in wifi_extra_dict:
                        milenage_list.append(wifi_extra_dict['milenage'])
                    else:
                        milenage_list.append('[BLANK]')

                    if 'domain' in wifi_extra_dict:
                        domain_list.append(wifi_extra_dict['domain'])
                    else:
                        domain_list.append('[BLANK]')

                    if 'roaming_consortium' in wifi_extra_dict:
                        roaming_consortium_list.append(
                            wifi_extra_dict['roaming_consortium'])
                    else:
                        roaming_consortium_list.append('[BLANK]')

                    if 'venue_group' in wifi_extra_dict:
                        venue_group_list.append(wifi_extra_dict['venue_group'])
                    else:
                        venue_group_list.append('[BLANK]')

                    if 'network_type' in wifi_extra_dict:
                        network_type_list.append(wifi_extra_dict['network_type'])
                    else:
                        network_type_list.append('[BLANK]')

                    if 'ipaddr_type_avail' in wifi_extra_dict:
                        ipaddr_type_avail_list.append(
                            wifi_extra_dict['ipaddr_type_avail'])
                    else:
                        ipaddr_type_avail_list.append('[BLANK]')

                    if 'network_auth_type' in wifi_extra_dict:
                        network_auth_type_list.append(
                            wifi_extra_dict['network_auth_type'])
                    else:
                        network_auth_type_list.append('[BLANK]')

                    if 'anqp_3gpp_cell_net' in wifi_extra_dict:
                        anqp_3gpp_cell_net_list.append(
                            wifi_extra_dict['anqp_3gpp_cell_net'])
                    else:
                        anqp_3gpp_cell_net_list.append('[BLANK]')

                    if 'ieee80211w' in wifi_extra_dict:
                        ieee80211w_list.append(wifi_extra_dict['ieee80211w'])
                    else:
                        ieee80211w_list.append('Optional')

                    '''
                    # wifi extra configuration
                    key_mgmt_list.append(key_mgmt)
                    pairwise_list.append(pairwise)
                    group_list.append(group)
                    psk_list.append(psk)
                    eap_list.append(eap)
                    identity_list.append(identity)
                    anonymous_identity_list.append(anonymous_identity)
                    phase1_list.append(phase1)
                    phase2_list.append(phase2)
                    passwd_list.append(passwd)
                    pin_list.append(pin)
                    pac_file_list.append(pac_file)
                    private_key_list.append(private)
                    pk_password_list.append(pk_password)
                    hessid_list.append(hssid)
                    realm_list.append(realm)
                    client_cert_list.append(client_cert)
                    imsi_list.append(imsi)
                    milenage_list.append(milenage)
                    domain_list.append(domain)
                    roaming_consortium_list.append(roaming_consortium)
                    venue_group_list.append(venue_group)
                    network_type_list.append(network_type)
                    ipaddr_type_avail_list.append(ipaddr_type_avail)
                    network_auth_type_list.append(network_ath_type)
                    anqp_3gpp_cell_net_list.append(anqp_3gpp_cell_net)

                    '''
                # no wifi extra for this station
                else:
                    key_mgmt_list.append('[BLANK]')
                    pairwise_list.append('[BLANK]')
                    group_list.append('[BLANK]')
                    psk_list.append('[BLANK]')
                    # for testing
                    # psk_list.append(radio_info_dict['ssid_pw'])
                    wep_key_list.append('[BLANK]')
                    ca_cert_list.append('[BLANK]')
                    eap_list.append('[BLANK]')
                    identity_list.append('[BLANK]')
                    anonymous_identity_list.append('[BLANK]')
                    phase1_list.append('[BLANK]')
                    phase2_list.append('[BLANK]')
                    passwd_list.append('[BLANK]')
                    pin_list.append('[BLANK]')
                    pac_file_list.append('[BLANK]')
                    private_key_list.append('[BLANK]')
                    pk_password_list.append('[BLANK]')
                    hessid_list.append("00:00:00:00:00:00")
                    realm_list.append('[BLANK]')
                    client_cert_list.append('[BLANK]')
                    imsi_list.append('[BLANK]')
                    milenage_list.append('[BLANK]')
                    domain_list.append('[BLANK]')
                    roaming_consortium_list.append('[BLANK]')
                    venue_group_list.append('[BLANK]')
                    network_type_list.append('[BLANK]')
                    ipaddr_type_avail_list.append('[BLANK]')
                    network_auth_type_list.append('[BLANK]')
                    anqp_3gpp_cell_net_list.append('[BLANK]')
                    ieee80211w_list.append('Optional')

                # check for wifi_settings
                wifi_settings_keys = ['wifi_settings']
                wifi_settings_found = True
                for key in wifi_settings_keys:
                    if key not in radio_info_dict:
                        logger.debug("wifi_settings_keys not enabled")
                        wifi_settings_found = False
                        break

                if wifi_settings_found:
                    # Check for additional flags
                    if {'wifi_mode', 'enable_flags'}.issubset(
                            radio_info_dict.keys()):
                        logger.debug("wifi_settings flags set")
                    else:
                        logger.debug("wifi_settings is present wifi_mode, enable_flags need to be set "
                                    "or remove the wifi_settings or set wifi_settings==False flag on "
                                    "the radio for defaults")
                        exit(1)
                    wifi_mode_list.append(radio_info_dict['wifi_mode'])
                    enable_flags_str = radio_info_dict['enable_flags'].replace(
                        '(', '').replace(')', '').replace('|', ',').replace('&&', ',')
                    enable_flags_list = list(enable_flags_str.split(","))
                    wifi_enable_flags_list.append(enable_flags_list)
                else:
                    wifi_mode_list.append(0)
                    wifi_enable_flags_list.append(
                        ["wpa2_enable", "80211u_enable", "create_admin_down"])
                    # 8021x_radius is the same as Advanced/8021x on the gui

                # check for optional radio key , currently only reset is enabled
                # update for checking for reset_port_time_min, reset_port_time_max
                optional_radio_reset_keys = ['reset_port_enable']
                radio_reset_found = True
                for key in optional_radio_reset_keys:
                    if key not in radio_info_dict:
                        # logger.debug("port reset test not enabled")
                        radio_reset_found = False
                        break

                if radio_reset_found:
                    reset_port_enable_list.append(
                        radio_info_dict['reset_port_enable'])
                    reset_port_time_min_list.append(
                        radio_info_dict['reset_port_time_min'])
                    reset_port_time_max_list.append(
                        radio_info_dict['reset_port_time_max'])
                else:
                    reset_port_enable_list.append(False)
                    reset_port_time_min_list.append('0s')
                    reset_port_time_max_list.append('0s')

            index = 0
            for (radio_name_, number_of_stations_per_radio_) in zip(
                    radio_name_list, number_of_stations_per_radio_list):
                number_of_stations = int(number_of_stations_per_radio_)
                if number_of_stations > MAX_NUMBER_OF_STATIONS:
                    logger.critical("number of stations per radio exceeded max of : {}".format(
                        MAX_NUMBER_OF_STATIONS))
                    quit(1)
                station_list = LFUtils.portNameSeries(
                    prefix_="sta",
                    start_id_=0 + index * 1000 + int(args.sta_start_offset),
                    end_id_=number_of_stations - 1 + index *
                    1000 + int(args.sta_start_offset),
                    padding_number_=10000,
                    radio=radio_name_)
                station_lists.append(station_list)
                index += 1

        # create a secondary station_list
        if args.use_existing_station_list:
            if args.existing_station_list is not None:
                # these are entered stations
                for existing_sta_list in args.existing_station_list:
                    existing_stations = str(existing_sta_list).replace(
                        '"',
                        '').replace(
                        '[',
                        '').replace(
                        ']',
                        '').replace(
                        "'",
                        "").replace(
                            ",",
                        " ").split()

                    for existing_sta in existing_stations:
                        existing_station_lists.append(existing_sta)
            else:
                logger.error(
                    "--use_station_list set true, --station_list is None Exiting")
                raise Exception(
                    "--use_station_list is used in conjunction with a --station_list")

        logger.info("existing_station_lists: {sta}".format(
            sta=existing_station_lists))

        # logger.info("endp-types: %s"%(endp_types))
        ul_rates = args.side_a_min_bps.replace(',', ' ').split()
        dl_rates = args.side_b_min_bps.replace(',', ' ').split()
        ul_pdus = args.side_a_min_pdu.replace(',', ' ').split()
        dl_pdus = args.side_b_min_pdu.replace(',', ' ').split()
        if args.attenuators == "":
            attenuators = []
        else:
            attenuators = args.attenuators.split(",")
        if args.atten_vals == "":
            atten_vals = [-1]
        else:
            atten_vals = args.atten_vals.split(",")

        if len(ul_rates) != len(dl_rates):
            # todo make fill assignable
            logger.info(
                "ul_rates %s and dl_rates %s arrays are of different length will fill shorter list with 256000\n" %
                (len(ul_rates), len(dl_rates)))
        if len(ul_pdus) != len(dl_pdus):
            logger.info(
                "ul_pdus %s and dl_pdus %s arrays are of different lengths will fill shorter list with size AUTO \n" %
                (len(ul_pdus), len(dl_pdus)))

        # Configure reporting
        logger.info("Configuring report")
        report, kpi_csv, csv_outfile = configure_reporting(**vars(args))

        logger.debug("Configure test object")
        ip_var_test = L3VariableTime(
            endp_types=endp_types,
            args=args,
            tos=args.tos,
            side_b=args.upstream_port,
            side_a=args.downstream_port,
            radio_name_list=radio_name_list,
            number_of_stations_per_radio_list=number_of_stations_per_radio_list,
            ssid_list=ssid_list,
            ssid_password_list=ssid_password_list,
            ssid_security_list=ssid_security_list,
            wifi_mode_list=wifi_mode_list,
            enable_flags_list=wifi_enable_flags_list,
            station_lists=station_lists,
            name_prefix="LT-",
            outfile=csv_outfile,
            reset_port_enable_list=reset_port_enable_list,
            reset_port_time_min_list=reset_port_time_min_list,
            reset_port_time_max_list=reset_port_time_max_list,
            side_a_min_rate=ul_rates,
            side_b_min_rate=dl_rates,
            side_a_min_pdu=ul_pdus,
            side_b_min_pdu=dl_pdus,
            rates_are_totals=args.rates_are_totals,
            mconn=args.multiconn,
            attenuators=attenuators,
            atten_vals=atten_vals,
            number_template="00",
            test_duration=args.test_duration,
            polling_interval=args.polling_interval,
            lfclient_host=args.lfmgr,
            lfclient_port=args.lfmgr_port,
            debug=args.debug,
            kpi_csv=kpi_csv,
            no_cleanup=args.no_cleanup,
            use_existing_station_lists=args.use_existing_station_list,
            existing_station_lists=existing_station_lists,
            wait_for_ip_sec=args.wait_for_ip_sec,
            exit_on_ip_acquired=args.exit_on_ip_acquired,
            ap_read=args.ap_read,
            ap_module=args.ap_module,
            ap_test_mode=args.ap_test_mode,
            ap_ip=args.ap_ip,
            ap_user=args.ap_user,
            ap_passwd=args.ap_passwd,
            ap_scheme=args.ap_scheme,
            ap_serial_port=args.ap_serial_port,
            ap_ssh_port=args.ap_ssh_port,
            ap_telnet_port=args.ap_telnet_port,
            ap_serial_baud=args.ap_serial_baud,
            ap_if_2g=args.ap_if_2g,
            ap_if_5g=args.ap_if_5g,
            ap_if_6g=args.ap_if_6g,
            ap_report_dir="",
            ap_file=args.ap_file,
            ap_band_list=args.ap_band_list.split(','),

            # for webgui execution
            test_name=test_name,
            dowebgui=args.dowebgui,
            ip=ip,
            get_live_view= args.get_live_view,
            total_floors = args.total_floors,
            # for uniformity from webGUI result_dir as variable is used insead of local_lf_report_dir
            result_dir=args.local_lf_report_dir,

            # wifi extra configuration
            key_mgmt_list=key_mgmt_list,
            pairwise_list=pairwise_list,
            group_list=group_list,
            psk_list=psk_list,
            wep_key_list=wep_key_list,
            ca_cert_list=ca_cert_list,
            eap_list=eap_list,
            identity_list=identity_list,
            anonymous_identity_list=anonymous_identity_list,
            phase1_list=phase1_list,
            phase2_list=phase2_list,
            passwd_list=passwd_list,
            pin_list=pin_list,
            pac_file_list=pac_file_list,
            private_key_list=private_key_list,
            pk_password_list=pk_password_list,
            hessid_list=hessid_list,
            realm_list=realm_list,
            client_cert_list=client_cert_list,
            imsi_list=imsi_list,
            milenage_list=milenage_list,
            domain_list=domain_list,
            roaming_consortium_list=roaming_consortium_list,
            venue_group_list=venue_group_list,
            network_type_list=network_type_list,
            ipaddr_type_avail_list=ipaddr_type_avail_list,
            network_auth_type_list=network_auth_type_list,
            anqp_3gpp_cell_net_list=anqp_3gpp_cell_net_list,
            ieee80211w_list=ieee80211w_list,
            interopt_mode=interopt_mode,
            endp_input_list=endp_input_list,
            graph_input_list=graph_input_list,
            real=args.real,
            expected_passfail_value=args.expected_passfail_value,
            device_csv_name=args.device_csv_name,
            group_name=args.group_name
        )

        # Perform pre-test cleanup, if configured to do so
        if args.no_pre_cleanup:
            logger.info("Skipping pre-test cleanup, '--no_pre_cleanup' specified")
        elif args.use_existing_station_list:
            logger.info("Skipping pre-test cleanup, '--use_existing_station_list' specified")
        else:
            logger.info("Performing pre-test cleanup")
            ip_var_test.pre_cleanup()

        # Build test configuration
        logger.info("Building test configuration")
        ip_var_test.build()
        if not ip_var_test.passes():
            logger.critical("Test configuration build failed")
            logger.critical(ip_var_test.get_fail_message())
            exit(1)

        # Run test
        logger.info("Starting test")
        ip_var_test.start(False)

        if args.wait > 0:
            logger.info(f"Pausing {args.wait} seconds for manual inspection before test conclusion and "
                        "possible traffic stop/post-test cleanup")
            time.sleep(args.wait)

        # Admin down the stations
        if args.no_stop_traffic:
            logger.info("Test complete, '--no_stop_traffic' specified, traffic continues to run")
        else:
            if args.quiesce_cx:
                logger.info("Test complete, quiescing traffic")
                ip_var_test.quiesce_cx()
                time.sleep(3)
            else:
                logger.info("Test complete, stopping traffic")
                ip_var_test.stop()

        # Set DUT information for reporting
        ip_var_test.set_dut_info(
            dut_model_num=args.dut_model_num,
            dut_hw_version=args.dut_hw_version,
            dut_sw_version=args.dut_sw_version,
            dut_serial_num=args.dut_serial_num)
        ip_var_test.set_report_obj(report=report)
        if args.dowebgui:
            ip_var_test.webgui_finalize()
        # Generate and write out test report
        logger.info("Generating test report")
        if args.real:
            ip_var_test.generate_report(config_devices, group_device_map)
        else:
            ip_var_test.generate_report()
        ip_var_test.write_report()

        # TODO move to after reporting
        if not ip_var_test.passes():
            logger.warning("Test Ended: There were Failures")
            logger.warning(ip_var_test.get_fail_message())

        if args.no_cleanup:
            logger.info("Skipping post-test cleanup, '--no_cleanup' specified")
        elif args.no_stop_traffic:
            logger.info("Skipping post-test cleanup, '--no_stop_traffic' specified")
        else:
            logger.info("Performing post-test cleanup")
            ip_var_test.cleanup()

        # TODO: This is redundant if '--no_cleanup' is not specified (already taken care of there)
        if args.cleanup_cx:
            logger.info("Performing post-test CX traffic pair cleanup")
            ip_var_test.cleanup_cx()

        if ip_var_test.passes():
            test_passed = True
            logger.info("Full test passed, all connections increased rx bytes")

        # Run WebGUI-specific post test logic
        if args.dowebgui:
            ip_var_test.copy_reports_to_home_dir()

        if test_passed:
            ip_var_test.exit_success()
        else:
            ip_var_test.exit_fail()


    def run_mc_test1(
        self,
        local_lf_report_dir="",
        results_dir_name="test_l3",
        test_rig="",
        test_tag="",
        dut_hw_version="",
        dut_sw_version="",
        dut_model_num="",
        dut_serial_num="",
        test_priority="",
        test_id="test l3",
        csv_outfile="",
        tty="",
        baud="9600",
        test_duration="3m",
        tos="BE",
        debug=False,
        log_level=None,
        interopt_mode=False,
        endp_type="lf_udp",
        upstream_port="eth1",
        downstream_port=None,
        polling_interval="60s",
        radio=None,
        side_a_min_bps="0",
        side_a_min_pdu="MTU",
        side_b_min_bps="256000",
        side_b_min_pdu="MTU",
        rates_are_totals=False,
        multiconn=1,
        attenuators="",
        atten_vals="",
        wait=0,
        sta_start_offset="0",
        no_pre_cleanup=False,
        no_cleanup=False,
        cleanup_cx=False,
        csv_data_to_report=False,
        no_stop_traffic=False,
        quiesce_cx=False,
        use_existing_station_list=False,
        existing_station_list=None,
        wait_for_ip_sec="120s",
        exit_on_ip_acquired=False,
        lf_logger_config_json=None,
        ap_read=False,
        ap_module=None,
        ap_test_mode=True,
        ap_scheme="serial",
        ap_serial_port="/dev/ttyUSB0",
        ap_serial_baud="115200",
        ap_ip="192.168.50.1",
        ap_ssh_port="1025",
        ap_telnet_port="23",
        ap_user="lanforge",
        ap_passwd="lanforge",
        ap_if_2g="wl0",
        ap_if_5g="wl1",
        ap_if_6g="wl2",
        ap_file=None,
        ap_band_list="2g,5g,6g",
        dowebgui=False,
        test_name=None,
        ssid=None,
        passwd=None,
        security=None,
        device_list=None,
        expected_passfail_value=None,
        device_csv_name=None,
        file_name=None,
        group_name=None,
        profile_name=None,
        eap_method="DEFAULT",
        eap_identity="",
        ieee8021x=False,
        ieee80211u=False,
        ieee80211w=1,
        enable_pkc=False,
        bss_transition=False,
        power_save=False,
        disable_ofdma=False,
        roam_ft_ds=False,
        key_management="DEFAULT",
        pairwise="NA",
        private_key="NA",
        ca_cert="NA",
        client_cert="NA",
        pk_passwd="NA",
        pac_file="NA",
        config=False,
        wait_time=60,
        real=False,
        get_live_view=False,
        total_floors="0",
        help_summary=False
    ):
        args = SimpleNamespace(**locals())
        args.lfmgr_port = self.port
        args.lfmgr = self.lanforge_ip
        self.run_mc_test(args)


    def run_yt_test(
            self,
            url=None,
            duration=None,
            ap_name="TIP",
            sec="wpa2",
            band="5GHZ",
            test_name=None,
            upstream_port=None,
            resource_list=None,
            no_pre_cleanup=False,
            no_post_cleanup=False,
            debug=False,
            log_level=None,
            res="Auto",
            lf_logger_config_json=None,
            ui_report_dir=None,
            do_webUI=False,
            file_name=None,
            group_name=None,
            profile_name=None,
            ssid=None,
            passwd=None,
            encryp=None,
            eap_method="DEFAULT",
            eap_identity="DEFAULT",
            ieee8021x=False,
            ieee80211u=False,
            ieee80211w=1,
            enable_pkc=False,
            bss_transition=False,
            power_save=False,
            disable_ofdma=False,
            roam_ft_ds=False,
            key_management="DEFAULT",
            pairwise="NA",
            private_key="NA",
            ca_cert="NA",
            pac_file="NA",
            client_cert="NA",
            pk_passwd="NA",
            help_summary=None,
            expected_passfail_value=None,
            device_csv_name=None,
            config=False
    ):
        try:
            if help_summary:
                logging.info(help_summary)
                exit(0)

            # set the logger level to debug
            logger_config = lf_logger_config.lf_logger_config()

            if log_level:
                logger_config.set_level(level=log_level)

            if lf_logger_config_json:
                logger_config.lf_logger_config_json = lf_logger_config_json
                logger_config.load_lf_logger_config()

            mgr_ip = self.lanforge_ip
            mgr_port = self.port
            url = url
            duration = duration

            do_webUI = do_webUI
            ui_report_dir = ui_report_dir
            debug = debug
            # Print debug information if debugging is enabled
            if debug:
                logging.info('''Specified configuration:
                ip:                       {}
                port:                     {}
                Duration:                 {}
                debug:                    {}
                '''.format(mgr_ip, mgr_port, duration, debug))

            if True:

                if expected_passfail_value is not None and device_csv_name is not None:
                    logging.error("Specify either expected_passfail_value or device_csv_name")
                    exit(1)

                if group_name is not None:
                    group_name = group_name.strip()
                    selected_groups = group_name.split(',')
                else:
                    selected_groups = []

                if profile_name is not None:
                    profile_name = profile_name.strip()
                    selected_profiles = profile_name.split(',')
                else:
                    selected_profiles = []

                if len(selected_groups) != len(selected_profiles):
                    logging.error("Number of groups should match number of profiles")
                    exit(0)

                elif group_name is not None and profile_name is not None and file_name is not None and resource_list is not None:
                    logging.error("Either group name or device list should be entered not both")
                    exit(0)
                elif ssid is not None and profile_name is not None:
                    logging.error("Either ssid or profile name should be given")
                    exit(0)
                elif file_name is not None and (group_name is None or profile_name is None):
                    logging.error("Please enter the correct set of arguments")
                    exit(0)
                elif config and ((ssid is None or (passwd is None and sec.lower() != 'open') or (passwd is None and sec is None))):
                    logging.error("Please provide ssid password and security for configuration of devices")
                    exit(0)

                Devices = RealDevice(manager_ip=mgr_ip,
                                    server_ip='192.168.1.61',
                                    ssid_2g='Test Configured',
                                    passwd_2g='',
                                    encryption_2g='',
                                    ssid_5g='Test Configured',
                                    passwd_5g='',
                                    encryption_5g='',
                                    ssid_6g='Test Configured',
                                    passwd_6g='',
                                    encryption_6g='',
                                    selected_bands=['5G'])
                Devices.get_devices()

                # Create a YouTube object with the specified parameters

                youtube = Youtube(
                    host=mgr_ip,
                    port=mgr_port,
                    url=url,
                    duration=duration,
                    lanforge_password='lanforge',
                    sta_list=[],
                    do_webUI=do_webUI,
                    ui_report_dir=ui_report_dir,
                    debug=debug,
                    resolution=res,
                    ap_name=ap_name,
                    ssid=ssid,
                    security=encryp,
                    band=band,
                    test_name=test_name,
                    upstream_port=upstream_port,
                    config=config,
                    selected_groups=selected_groups,
                    selected_profiles=selected_profiles)
                youtube.start_flask_server()
                upstream_port = youtube.change_port_to_ip(upstream_port)

                resources = []
                youtube.Devices = Devices
                if file_name:
                    new_filename = file_name.removesuffix(".csv")
                else:
                    new_filename = file_name
                config_obj = DeviceConfig.DeviceConfig(lanforge_ip=self.lanforge_ip, file_name=new_filename)
                if not expected_passfail_value and device_csv_name is None:
                    config_obj.device_csv_file(csv_name="device.csv")
                if group_name is not None and file_name is not None and profile_name is not None:
                    selected_groups = group_name.split(',')
                    selected_profiles = profile_name.split(',')
                    config_devices = {}
                    for i in range(len(selected_groups)):
                        config_devices[selected_groups[i]] = selected_profiles[i]

                    config_obj.initiate_group()

                    asyncio.run(config_obj.connectivity(config_devices))

                    adbresponse = config_obj.adb_obj.get_devices()
                    resource_manager = config_obj.laptop_obj.get_devices()
                    all_res = {}
                    df1 = config_obj.display_groups(config_obj.groups)
                    groups_list = df1.to_dict(orient='list')
                    group_devices = {}

                    for adb in adbresponse:
                        group_devices[adb['serial']] = adb['eid']
                    for res in resource_manager:
                        all_res[res['hostname']] = res['shelf'] + '.' + res['resource']
                    eid_list = []
                    for grp_name in groups_list.keys():
                        for g_name in selected_groups:
                            if grp_name == g_name:
                                for j in groups_list[grp_name]:
                                    if j in group_devices.keys():
                                        eid_list.append(group_devices[j])
                                    elif j in all_res.keys():
                                        eid_list.append(all_res[j])
                    resource_list = ",".join(id for id in eid_list)
                else:
                    config_dict = {
                        'ssid': ssid,
                        'passwd': passwd,
                        'enc': encryp,
                        'eap_method': eap_method,
                        'eap_identity': eap_identity,
                        'ieee80211': ieee8021x,
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
                        'server_ip': upstream_port,
                    }
                    if resource_list:
                        all_devices = config_obj.get_all_devices()
                        if group_name is None and file_name is None and profile_name is None:
                            dev_list = resource_list.split(',')
                            if config:
                                asyncio.run(config_obj.connectivity(device_list=dev_list, wifi_config=config_dict))
                    else:
                        all_devices = config_obj.get_all_devices()
                        device_list = []
                        for device in all_devices:
                            if device["type"] != 'laptop':
                                device_list.append(device["shelf"] + '.' + device["resource"] + " " + device["serial"])
                            elif device["type"] == 'laptop':
                                device_list.append(device["shelf"] + '.' + device["resource"] + " " + device["hostname"])

                        print("Available devices:")
                        for device in device_list:
                            print(device)

                        resource_list = input("Enter the desired resources to run the test:")
                        dev1_list = resource_list.split(',')
                        if config:
                            asyncio.run(config_obj.connectivity(device_list=dev1_list, wifi_config=config_dict))

                if not do_webUI:
                    if resource_list:
                        resources = [r.strip() for r in resource_list.split(',')]
                        resources = [r for r in resources if len(r.split('.')) > 1]

                        youtube.select_real_devices(real_devices=Devices, real_sta_list=resources, base_interop_obj=Devices)

                    else:
                        youtube.select_real_devices(real_devices=Devices)
                else:
                    resources = [r.strip() for r in resource_list.split(',')]

                    extracted_parts = [res.split('.')[:2] for res in resources]
                    formatted_parts = ['.'.join(parts) for parts in extracted_parts]
                    youtube.select_real_devices(real_devices=Devices, real_sta_list=formatted_parts, base_interop_obj=Devices)

                    if do_webUI:

                        if len(youtube.real_sta_hostname) == 0:
                            logging.error("No device is available to run the test")
                            obj = {
                                "status": "Stopped",
                                "configuration_status": "configured"
                            }
                            youtube.updating_webui_runningjson(obj)
                            return
                        else:
                            obj = {
                                "configured_devices": youtube.real_sta_hostname,
                                "configuration_status": "configured",
                                "no_of_devices": f' Total({len(youtube.real_sta_os_types)}) : W({youtube.windows}),L({youtube.linux}),M({youtube.mac})',
                                "device_list": youtube.hostname_os_combination

                            }
                            youtube.updating_webui_runningjson(obj)

                # Perform pre-test cleanup if not skipped
                if not no_pre_cleanup:
                    youtube.cleanup()

                # Check if the required tab exists, and exit if not
                if not youtube.check_tab_exists():
                    logging.error('Generic Tab is not available.\nAborting the test.')
                    exit(0)

                if len(youtube.real_sta_list) > 0:
                    logging.info(f"checking real sta list while creating endpionts {youtube.real_sta_list}")
                    youtube.create_generic_endp(youtube.real_sta_list)
                else:
                    logging.info(f"checking real sta list while creating endpionts {youtube.real_sta_list}")
                    logging.error("No Real Devies Available")
                    exit(0)

                logging.info("TEST STARTED")
                logging.info('Running the Youtube Streaming test for {} minutes'.format(duration))

                time.sleep(10)

                youtube.start_time = datetime.now()
                youtube.start_generic()

                duration = duration
                end_time = datetime.now() + timedelta(minutes=duration)
                initial_data = youtube.get_data_from_api()

                while len(initial_data) == 0:
                    initial_data = youtube.get_data_from_api()
                    time.sleep(1)
                if initial_data:
                    end_time_webgui = []
                    for i in range(len(youtube.device_names)):
                        end_time_webgui.append(initial_data['result'].get(youtube.device_names[i], {}).get('stop', False))
                else:
                    for i in range(len(youtube.device_names)):
                        end_time_webgui.append("")

                end_time = datetime.now() + timedelta(minutes=duration)

                while datetime.now() < end_time or not youtube.check_gen_cx():
                    youtube.get_data_from_api()
                    time.sleep(1)

                youtube.generic_endps_profile.stop_cx()
                logging.info("Duration ended")

                logging.info('Stopping the test')
                if do_webUI:
                    youtube.create_report(youtube.stats_api_response, youtube.ui_report_dir)
                else:

                    youtube.create_report(youtube.stats_api_response, '')

                # Perform post-test cleanup if not skipped
                if not no_post_cleanup:
                    youtube.generic_endps_profile.cleanup()
        except Exception as e:
            logging.error(f"Error occured {e}")
            # traceback.print_exc()
        finally:
            if not ('--help' in sys.argv or '-h' in sys.argv):
                youtube.stop()
                # Stopping the Youtube test
                if do_webUI:
                    youtube.stop_test_yt()
                logging.info("Waiting for Cleanup of Browsers in Devices")
                time.sleep(10)





candela_apis = Candela(ip='192.168.204.74', port=8080)


#WITHOUT CONFIG
# candela_apis.run_ping_test(real=True,target="192.168.204.59",ping_interval='5',ping_duration=1,passwd="Openwifi",use_default_config=True)
# candela_apis.run_http_test(upstream_port='eth1',bands=["5G"],duration='1m',file_size="2MB",device_list="1.95,1.12")
# candela_apis.start_ftp_test(ssid='Walkin_open', password='[BLANK]', security='open',
#                                 device_list='1.16,1.95',background=False)
# candela_apis.run_qos_test(upstream_port="eth1",test_duration="1m",download ="0",upload="1000000",traffic_type ="lf_udp",tos="BK,BE,VI,VO",device_list="1.12,1.16,1.95")
# candela_apis.run_vs_test(
#     url="https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8",
#     media_source="hls",
#     media_quality="1080P",
#     duration="1m",
#     device_list="1.12,1.15",
#     debug=True,
#     test_name="video_streaming_test"
# )
# candela_apis.run_throughput_test(
#     upstream_port="eth1",
#     test_duration="1m",
#     download="1000000",
#     traffic_type="lf_udp",
#     device_list="1.15,1.12,1.95,1.400",
#     do_interopability=True,
#     default_config=True
# )
# candela_apis.run_mc_test1(
#     test_duration="1m",
#     polling_interval="5s",
#     upstream_port="1.1.eth1",
#     endp_type="mc_udp",
#     rates_are_totals=True,
#     side_b_min_bps="30000000",
#     tos="VI",
#     real=True,
#     ssid="NETGEAR_5G_wpa2",
#     passwd="Password@123",
#     security="wpa2",
#     log_level="info",
#     device_list=["1.11,1.95,1.360"]
# )


# candela_apis.run_yt_test(
#     url="https://youtu.be/BHACKCNDMW8?si=psTEUzrc77p38aU1",
#     duration=1,
#     res="1080p",
#     upstream_port="1.1.eth1",
#     resource_list="1.12,1.15"
# )
