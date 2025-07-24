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
from test_l3 import L3VariableTime,change_port_to_ip,configure_reporting,query_real_clients,valid_endp_types
from lf_kpi_csv import lf_kpi_csv
import lf_cleanup
import os
import sys
import argparse
import json
import traceback
from types import SimpleNamespace
import matplotlib
from pathlib import Path
realm = importlib.import_module("py-json.realm")
Realm = realm.Realm
error_logs = "" 
test_results_df = pd.DataFrame(columns=['test_name', 'status'])
matplotlib.use('Agg')  # Before importing pyplot
base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
print('base path',base_path)
sys.path.insert(0, os.path.join(base_path, 'py-json'))     # for interop_connectivity, LANforge
sys.path.insert(0, os.path.join(base_path, 'py-json', 'LANforge'))  # for LFUtils
sys.path.insert(0, os.path.join(base_path, 'py-scripts'))  # for lf_logger_config
througput_test=importlib.import_module("py-scripts.lf_interop_throughput")
video_streaming_test=importlib.import_module("py-scripts.lf_interop_video_streaming")
web_browser_test=importlib.import_module("py-scripts.real_application_tests.real_browser.lf_interop_real_browser_test")
zoom_test=importlib.import_module("py-scripts.real_application_tests.zoom_automation.lf_interop_zoom")
yt_test=importlib.import_module("py-scripts.real_application_tests.youtube.lf_interop_youtube")
lf_report_pdf = importlib.import_module("py-scripts.lf_report")
lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")
logger = logging.getLogger(__name__)
RealBrowserTest = getattr(web_browser_test, "RealBrowserTest")
Youtube = getattr(yt_test, "Youtube")
ZoomAutomation = getattr(zoom_test, "ZoomAutomation")
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
class Candela(Realm):
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
        super().__init__(lfclient_host=ip,
                         lfclient_port=port)
        self.lanforge_ip = ip
        self.port = port
        self.api_url = 'http://{}:{}'.format(self.lanforge_ip, self.port)
        self.cleanup = lf_cleanup.lf_clean(host=self.lanforge_ip, port=self.port, resource='all')
        self.ftp_test = None
        self.http_test = None
        self.generic_endps_profile = self.new_generic_endp_profile()
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

    def misc_clean_up(self,layer3=False,layer4=False,generic=False):
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
        if generic:
            resp = self.json_get('/generic?fields=name')
            if 'endpoints' in resp:
                for i in resp['endpoints']:
                    if list(i.values())[0]['name']:
                        self.generic_endps_profile.created_cx.append('CX_' + list(i.values())[0]['name'])
                        self.generic_endps_profile.created_endp.append(list(i.values())[0]['name'])
            self.generic_endps_profile.cleanup()


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


    def run_ping_test(
        self,
        target: str = '1.1.eth1',
        ping_interval: str = '1',
        ping_duration: float = 1,
        ssid: str = None,
        mgr_passwd: str = 'lanforge',
        server_ip: str = None,
        security: str = 'open',
        passwd: str = '[BLANK]',
        virtual: bool = False,
        num_sta: int = 1,
        radio: str = None,
        real: bool = True,
        use_default_config: bool = True,
        debug: bool = False,
        local_lf_report_dir: str = "",
        log_level: str = None,
        lf_logger_config_json: str = None,
        help_summary: bool = False,
        group_name: str = None,
        profile_name: str = None,
        file_name: str = None,
        eap_method: str = 'DEFAULT',
        eap_identity: str = '',
        ieee8021x: bool = False,
        ieee80211u: bool = False,
        ieee80211w: int = 1,
        enable_pkc: bool = False,
        bss_transition: bool = False,
        power_save: bool = False,
        disable_ofdma: bool = False,
        roam_ft_ds: bool = False,
        key_management: str = 'DEFAULT',
        pairwise: str = '[BLANK]',
        private_key: str = '[BLANK]',
        ca_cert: str = '[BLANK]',
        client_cert: str = '[BLANK]',
        pk_passwd: str = '[BLANK]',
        pac_file: str = '[BLANK]',
        expected_passfail_value: str = None,
        device_csv_name: str = None,
        wait_time: int = 60,
        dev_list: str = None
    ):

        # set the logger level to debug
        logger_config = lf_logger_config.lf_logger_config()

        if log_level:
            logger_config.set_level(level=log_level)

        if lf_logger_config_json:
            # logger_config.lf_logger_config_json = "lf_logger_config.json"
            logger_config.lf_logger_config_json = lf_logger_config_json
            logger_config.load_lf_logger_config()
        # validate_args(args)

        mgr_ip = self.lanforge_ip
        mgr_password = mgr_passwd
        mgr_port = self.port
        server_ip = server_ip
        ssid = ssid
        security = security
        password = passwd
        num_sta = num_sta
        radio = radio
        target = target
        interval = ping_interval
        duration = ping_duration
        configure = not use_default_config
        debug = debug
        group_name = group_name
        file_name = file_name
        profile_name = profile_name
        eap_method = eap_method
        eap_identity = eap_identity
        ieee80211 = ieee8021x
        ieee80211u = ieee80211u
        ieee80211w = ieee80211w
        enable_pkc = enable_pkc
        bss_transition = bss_transition
        power_save = power_save
        disable_ofdma = disable_ofdma
        roam_ft_ds = roam_ft_ds
        key_management = key_management
        pairwise = pairwise
        private_key = private_key
        ca_cert = ca_cert
        client_cert = client_cert
        pk_passwd = pk_passwd
        pac_file = pac_file

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
                '''.format(mgr_ip, mgr_port, ssid, security, password, target, interval, duration, virtual, num_sta, radio, real, debug))

        # ping object creation
        ping = Ping(host=mgr_ip, port=mgr_port, ssid=ssid, security=security, password=password, radio=radio,
                    lanforge_password=mgr_password, target=target, interval=interval, sta_list=[], virtual=virtual, real=real, duration=duration, debug=debug, csv_name=device_csv_name,
                    expected_passfail_val=expected_passfail_value, wait_time=wait_time, group_name=group_name)

        # changing the target from port to IP
        ping.change_target_to_ip()

        # creating virtual stations if --virtual flag is specified
        if (virtual):

            logging.info('Proceeding to create {} virtual stations on {}'.format(num_sta, radio))
            station_list = LFUtils.portNameSeries(
                prefix_='sta', start_id_=0, end_id_=num_sta - 1, padding_number_=100000, radio=radio)
            ping.sta_list = station_list
            if (debug):
                logging.info('Virtual Stations: {}'.format(station_list).replace(
                    '[', '').replace(']', '').replace('\'', ''))

        # selecting real clients if --real flag is specified
        if (real):
            Devices = RealDevice(manager_ip=mgr_ip, selected_bands=[])
            Devices.get_devices()
            ping.Devices = Devices
            # ping.select_real_devices(real_devices=Devices)
            # If config is True, attempt to bring up all devices in the list and perform tests on those that become active
            if (configure):
                config_devices = {}
                obj = DeviceConfig.DeviceConfig(lanforge_ip=mgr_ip, file_name=file_name, wait_time=wait_time)
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
                    if dev_list is None:
                        dev_list = input("Enter the desired resources to run the test:")
                    dev_list = dev_list.split(',')
                    dev_list = asyncio.run(obj.connectivity(device_list=dev_list, wifi_config=config_dict))
                    Devices.get_devices()
                    ping.select_real_devices(real_devices=Devices, device_list=dev_list)
            # Case 3: Config is False, no device list is provided, and no group is selected
            # Prompt the user to manually input devices for running the test
            else:
                device_list = ping.Devices.get_devices()
                logger.info(f"Available devices: {device_list}")
                if dev_list is None:
                    dev_list = input("Enter the desired resources to run the test:")
                dev_list = dev_list.split(',')
                # dev_list = input("Enter the desired resources to run the test:").split(',')
                ping.select_real_devices(real_devices=Devices, device_list=dev_list)

        # station precleanup
        ping.cleanup() #11 change

        # building station if virtual
        if (virtual):
            ping.buildstation()

        # check if generic tab is enabled or not
        if (not ping.check_tab_exists()):
            logging.error('Generic Tab is not available.\nAborting the test.')
            return False

        ping.sta_list += ping.real_sta_list

        # creating generic endpoints
        ping.create_generic_endp()

        logging.info(ping.generic_endps_profile.created_cx)

        # run the test for the given duration
        logging.info('Running the ping test for {} minutes'.format(duration))

        # start generate endpoint
        ping.start_generic()
        # time_counter = 0
        ports_data_dict = ping.json_get('/ports/all/')['interfaces']
        ports_data = {}
        for ports in ports_data_dict:
            port, port_data = list(ports.keys())[0], list(ports.values())[0]
            ports_data[port] = port_data

        time.sleep(duration * 60)

        logging.info('Stopping the test')
        ping.stop_generic()

        result_data = ping.get_results()
        # logging.info(result_data)
        logging.info(ping.result_json)
        if (virtual):
            ports_data_dict = ping.json_get('/ports/all/')['interfaces']
            ports_data = {}
            for ports in ports_data_dict:
                port, port_data = list(ports.keys())[0], list(ports.values())[0]
                ports_data[port] = port_data
            if (isinstance(result_data, dict)):
                for station in ping.sta_list:
                    if (station not in ping.real_sta_list):
                        current_device_data = ports_data[station]
                        if (station.split('.')[2] in result_data['name']):
                            # t_rtt = 0
                            # min_rtt = 10000
                            # max_rtt = 0
                            # for result in result_data['last results'].split('\n'):
                            #     # logging.info(result)
                            #     if (result == ''):
                            #         continue
                            #     rt_time = result.split()[6]
                            #     logging.info(rt_time.split('time='))
                            #     time_value = float(rt_time.split('time=')[1])
                            #     t_rtt += time_value
                            #     if (time_value < min_rtt):
                            #         min_rtt = time_value
                            #     if (max_rtt < time_value):
                            #         max_rtt = time_value
                            # avg_rtt = t_rtt / float(result_data['rx pkts'])
                            # logging.info(t_rtt, min_rtt, max_rtt, avg_rtt)
                            try:
                                ping.result_json[station] = {
                                    'command': result_data['command'],
                                    'sent': result_data['tx pkts'],
                                    'recv': result_data['rx pkts'],
                                    'dropped': result_data['dropped'],
                                    'min_rtt': [result_data['last results'].split('\n')[-2].split()[-1].split('/')[0] if len(result_data['last results']) != 0 and 'min/avg/max' in result_data['last results'].split('\n')[-2] else '0'][0],  # noqa E501
                                    'avg_rtt': [result_data['last results'].split('\n')[-2].split()[-1].split('/')[1] if len(result_data['last results']) != 0 and 'min/avg/max' in result_data['last results'].split('\n')[-2] else '0'][0],  # noqa E501
                                    'max_rtt': [result_data['last results'].split('\n')[-2].split()[-1].split('/')[2] if len(result_data['last results']) != 0 and 'min/avg/max' in result_data['last results'].split('\n')[-2] else '0'][0],  # noqa E501
                                    'mac': current_device_data['mac'],
                                    'channel': current_device_data['channel'],
                                    'ssid': current_device_data['ssid'],
                                    'mode': current_device_data['mode'],
                                    'name': station,
                                    'os': 'Virtual',
                                    'remarks': [],
                                    'last_result': [result_data['last results'].split('\n')[-2] if len(result_data['last results']) != 0 else ""][0]
                                }
                                ping.result_json[station]['remarks'] = ping.generate_remarks(ping.result_json[station])
                            except BaseException:
                                logging.error('Failed parsing the result for the station {}'.format(station))

            else:
                for station in ping.sta_list:
                    if (station not in ping.real_sta_list):
                        current_device_data = ports_data[station]
                        for ping_device in result_data:
                            ping_endp, ping_data = list(ping_device.keys())[
                                0], list(ping_device.values())[0]
                            if (station.split('.')[2] in ping_endp):
                                # t_rtt = 0
                                # min_rtt = 10000
                                # max_rtt = 0
                                # for result in ping_data['last results'].split('\n'):
                                #     if (result == ''):
                                #         continue
                                #     rt_time = result.split()[6]
                                #     time_value = float(rt_time.split('time=')[1])
                                #     t_rtt += time_value
                                #     if (time_value < min_rtt):
                                #         min_rtt = time_value
                                #     if (max_rtt < time_value):
                                #         max_rtt = time_value
                                # avg_rtt = t_rtt / float(ping_data['rx pkts'])
                                # logging.info(t_rtt, min_rtt, max_rtt, avg_rtt)
                                try:
                                    ping.result_json[station] = {
                                        'command': ping_data['command'],
                                        'sent': ping_data['tx pkts'],
                                        'recv': ping_data['rx pkts'],
                                        'dropped': ping_data['dropped'],
                                        'min_rtt': [ping_data['last results'].split('\n')[-2].split()[-1].split('/')[0] if len(ping_data['last results']) != 0 and 'min/avg/max' in ping_data['last results'].split('\n')[-2] else '0'][0],  # noqa E501
                                        'avg_rtt': [ping_data['last results'].split('\n')[-2].split()[-1].split('/')[1] if len(ping_data['last results']) != 0 and 'min/avg/max' in ping_data['last results'].split('\n')[-2] else '0'][0],  # noqa E501
                                        'max_rtt': [ping_data['last results'].split('\n')[-2].split()[-1].split('/')[2] if len(ping_data['last results']) != 0 and 'min/avg/max' in ping_data['last results'].split('\n')[-2] else '0'][0],  # noqa E501
                                        'mac': current_device_data['mac'],
                                        'ssid': current_device_data['ssid'],
                                        'channel': current_device_data['channel'],
                                        'mode': current_device_data['mode'],
                                        'name': station,
                                        'os': 'Virtual',
                                        'remarks': [],
                                        'last_result': [ping_data['last results'].split('\n')[-2] if len(ping_data['last results']) != 0 else ""][0]
                                    }
                                    ping.result_json[station]['remarks'] = ping.generate_remarks(ping.result_json[station])
                                except BaseException:
                                    logging.error('Failed parsing the result for the station {}'.format(station))

        if (real):
            if (isinstance(result_data, dict)):
                for station in ping.real_sta_list:
                    current_device_data = Devices.devices_data[station]
                    # logging.info(current_device_data)
                    if (station in result_data['name']):
                        try:
                            # logging.info(result_data['last results'].split('\n'))
                            ping.result_json[station] = {
                                'command': result_data['command'],
                                'sent': result_data['tx pkts'],
                                'recv': result_data['rx pkts'],
                                'dropped': result_data['dropped'],
                                'min_rtt': [result_data['last results'].split('\n')[-2].split()[-1].split(':')[-1].split('/')[0] if len(result_data['last results']) != 0 and 'min/avg/max' in result_data['last results'].split('\n')[-2] else '0'][0],  # noqa E501
                                'avg_rtt': [result_data['last results'].split('\n')[-2].split()[-1].split(':')[-1].split('/')[1] if len(result_data['last results']) != 0 and 'min/avg/max' in result_data['last results'].split('\n')[-2] else '0'][0],  # noqa E501
                                'max_rtt': [result_data['last results'].split('\n')[-2].split()[-1].split(':')[-1].split('/')[2] if len(result_data['last results']) != 0 and 'min/avg/max' in result_data['last results'].split('\n')[-2] else '0'][0],  # noqa E501
                                'mac': current_device_data['mac'],
                                'ssid': current_device_data['ssid'],
                                'channel': current_device_data['channel'],
                                'mode': current_device_data['mode'],
                                'name': [current_device_data['user'] if current_device_data['user'] != '' else current_device_data['hostname']][0],
                                'os': ['Windows' if 'Win' in current_device_data['hw version'] else 'Linux' if 'Linux' in current_device_data['hw version'] else 'Mac' if 'Apple' in current_device_data['hw version'] else 'Android'][0],  # noqa E501
                                'remarks': [],
                                'last_result': [result_data['last results'].split('\n')[-2] if len(result_data['last results']) != 0 else ""][0]
                            }
                            ping.result_json[station]['remarks'] = ping.generate_remarks(ping.result_json[station])
                        except BaseException:
                            logging.error('Failed parsing the result for the station {}'.format(station))
            else:
                for station in ping.real_sta_list:
                    current_device_data = Devices.devices_data[station]
                    for ping_device in result_data:
                        ping_endp, ping_data = list(ping_device.keys())[
                            0], list(ping_device.values())[0]
                        if (station in ping_endp):
                            try:
                                ping.result_json[station] = {
                                    'command': ping_data['command'],
                                    'sent': ping_data['tx pkts'],
                                    'recv': ping_data['rx pkts'],
                                    'dropped': ping_data['dropped'],
                                    'min_rtt': [ping_data['last results'].split('\n')[-2].split()[-1].split(':')[-1].split('/')[0] if len(ping_data['last results']) != 0 and 'min/avg/max' in ping_data['last results'].split('\n')[-2] else '0'][0],  # noqa E501
                                    'avg_rtt': [ping_data['last results'].split('\n')[-2].split()[-1].split(':')[-1].split('/')[1] if len(ping_data['last results']) != 0 and 'min/avg/max' in ping_data['last results'].split('\n')[-2] else '0'][0],  # noqa E501
                                    'max_rtt': [ping_data['last results'].split('\n')[-2].split()[-1].split(':')[-1].split('/')[2] if len(ping_data['last results']) != 0 and 'min/avg/max' in ping_data['last results'].split('\n')[-2] else '0'][0],  # noqa E501
                                    'mac': current_device_data['mac'],
                                    'ssid': current_device_data['ssid'],
                                    'channel': current_device_data['channel'],
                                    'mode': current_device_data['mode'],
                                    'name': [current_device_data['user'] if current_device_data['user'] != '' else current_device_data['hostname']][0],
                                    'os': ['Windows' if 'Win' in current_device_data['hw version'] else 'Linux' if 'Linux' in current_device_data['hw version'] else 'Mac' if 'Apple' in current_device_data['hw version'] else 'Android'][0],  # noqa E501
                                    'remarks': [],
                                    'last_result': [ping_data['last results'].split('\n')[-2] if len(ping_data['last results']) != 0 else ""][0]
                                }
                                ping.result_json[station]['remarks'] = ping.generate_remarks(ping.result_json[station])
                            except BaseException:
                                logging.error('Failed parsing the result for the station {}'.format(station))

        logging.info(ping.result_json)

        # station post cleanup
        ping.cleanup() #12 change

        if local_lf_report_dir == "":
            # Report generation when groups are specified but no custom report path is provided
            if group_name:
                ping.generate_report(config_devices=config_devices, group_device_map=group_device_map)
            # Report generation when no group is specified and no custom report path is provided
            else:
                ping.generate_report()
        else:
            # Report generation when groups are specified and a custom report path is provided
            if group_name:
                ping.generate_report(config_devices=config_devices, group_device_map=group_device_map, report_path=local_lf_report_dir)
            # Report generation when no group is specified but a custom report path is provided
            else:
                ping.generate_report(report_path=local_lf_report_dir)
        return True

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
                            return False
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
                        return False
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
            if client_type == "Real":
                test_setup_info["failed_cx's"] = http.failed_cx if http.failed_cx else "NONE"
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
            return True

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
    #     # return False
    #     if help_summary:
    #         print(help_summary)
    #         return False

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
    #                             return False
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
    #                     return False

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

    # def start_ftp_test(self,
    #                    ssid=None,
    #                    password=None,
    #                    security=None,
    #                    ap_name='',
    #                    band='5g',
    #                    direction='Download',
    #                    file_size='12MB',
    #                    traffic_duration=60,
    #                    upstream='eth1',
    #                    lf_username='lanforge',
    #                    lf_password='lanforge',
    #                    ssh_port=22,
    #                    clients_type='Real',
    #                    device_list=[],
    #                    background=False,
    #                    file_name=None,
    #              profile_name=None,group_name=None,eap_method=None,
    #              eap_identity=None,
    #              ieee8021x=None,
    #              ieee80211u=None,
    #              ieee80211w=None,
    #              enable_pkc=None,
    #              bss_transition=None,
    #              power_save=None,
    #              disable_ofdma=None,
    #              roam_ft_ds=None,
    #              key_management=None,
    #              pairwise=None,
    #              private_key=None,
    #              ca_cert=None,
    #              client_cert=None,
    #              pk_passwd=None,
    #              pac_file=None,expected_passfail_val=None,device_csv_name=None,wait_time=60,config=False):
    #     """
    #     Method to start FTP test on the given device list

    #     Args:
    #         ssid (str): SSID of the DUT
    #         password (str): Password for the SSID. [BLANK] if encryption is open.
    #         security (str): Encryption for the SSID.
    #         ap_name (str, optional): Name of the AP. Defaults to ''.
    #         band (str, optional): 2g, 5g or 6g. Defaults to '5g'.
    #         direction (str, optional): Download or Upload. Defaults to 'Download'.
    #         file_size (str, optional): File Size. Defaults to '12MB'.
    #         traffic_duration (int, optional): Duration of the test in seconds. Defaults to 60.
    #         upstream (str, optional): Upstream port. Defaults to 'eth1'.
    #         lf_username (str, optional): Username of LANforge. Defaults to 'lanforge'.
    #         lf_password (str, optional): Password of LANforge. Defaults to 'lanforge'.
    #         ssh_port (int, optional): SSH port. Defaults to 22.
    #         clients_type (str, optional): Clients type. Defaults to 'Real'.
    #         device_list (list, optional): List of port numbers of the devices in shelf.resource format. Defaults to [].
    #         background_run(bool): If true, it runs the test without considering test duration.

    #     Returns:
    #         data (dict): Test results.
    #     """
    #     # for band in bands:
    #     #     for direction in directions:
    #     #         for file_size in file_sizes:
    #     # Start Test
    #     print(traffic_duration)
    #     if type(traffic_duration) == str:
    #         if traffic_duration[-1].lower()=='s':
    #             traffic_duration = int(traffic_duration[:-1])
    #         elif traffic_duration[-1].lower()=='m':
    #             traffic_duration = int(traffic_duration[:-1])*60
    #         elif traffic_duration[-1].lower()=='h':
    #             traffic_duration = int(traffic_duration[:-1])*60*60
    #     device_list = self.filter_iOS_devices(device_list)
    #     if group_name:
    #         selected_groups = group_name.split(',')
    #     else:
    #         selected_groups = []  # Default to empty list if group name is not provided
    #     if profile_name:
    #         selected_profiles = profile_name.split(',')
    #     else:
    #         selected_profiles = []  # Default to empty list if profile name is not provided
    #     self.ftp_test = FtpTest(lfclient_host=self.lanforge_ip,
    #                     lfclient_port=self.port,
    #                     upstream=upstream,
    #                     dut_ssid=ssid,
    #                     dut_passwd=password,
    #                     dut_security=security,
    #                     band=band,
    #                     ap_name=ap_name,
    #                     file_size=file_size,
    #                     direction=direction,
    #                     lf_username=lf_username,
    #                     lf_password=lf_password,
    #                     # duration=pass_fail_duration(band, file_size),
    #                     traffic_duration=traffic_duration,
    #                     ssh_port=ssh_port,
    #                     clients_type=clients_type,
    #                     device_list=device_list,
    #                     group_name=group_name,
    #                     profile_name=profile_name,
    #                     file_name=file_name,eap_method=eap_method,
    #                     eap_identity=eap_identity,
    #                     ieee80211=ieee8021x,
    #                     ieee80211u=ieee80211u,
    #                     ieee80211w=ieee80211w,
    #                     enable_pkc=enable_pkc,
    #                     bss_transition=bss_transition,
    #                     power_save=power_save,
    #                     disable_ofdma=disable_ofdma,
    #                     roam_ft_ds=roam_ft_ds,
    #                     key_management=key_management,
    #                     pairwise=pairwise,
    #                     private_key=private_key,
    #                     ca_cert=ca_cert,
    #                     client_cert=client_cert,
    #                     pk_passwd=pk_passwd,
    #                     pac_file=pac_file,
    #                     csv_name=device_csv_name,expected_passfail_val=expected_passfail_val,wait_time=wait_time,config=config)

    #     self.ftp_test.data = {}
    #     self.ftp_test.file_create()
    #     if clients_type == "Real":
    #         _, configuration = self.ftp_test.query_realclients()
    #     self.ftp_test.configuration = configuration
    #     self.ftp_test.set_values()
    #     self.ftp_test.count = 0
    #     self.ftp_test.radio = ['1.1.wiphy0']
    #     # obj.precleanup()
    #     self.ftp_test.build()
    #     if not self.ftp_test.passes():
    #         logger.info(self.ftp_test.get_fail_message())
    #         return False

    #     # First time stamp
    #     test_start_time = datetime.now()
    #     logger.info("Traffic started running at {}".format(test_start_time))
    #     self.ftp_test.start_time = test_start_time
    #     self.ftp_test.monitor_cx()
    #     self.ftp_test.start(False, False)
    #     self.ftp_test.monitor_for_runtime_csv()
    #     if not background:
    #         # time.sleep(int(self.ftp_test.traffic_duration))
    #         self.stop_ftp_test()
    #         self.generate_report_ftp_test()
    #     return True

    # def stop_ftp_test(self):
    #     """
    #     Method to stop FTP test.
    #     """
    #     self.ftp_test.stop()
    #     logger.info("Traffic stopped running")
    #     # self.ftp_test.my_monitor()
    #     self.ftp_test.postcleanup()
    #     test_end_time = datetime.now()
    #     logger.info("Test ended at {}".format(test_end_time))
    #     self.ftp_test.end_time = test_end_time

    # def generate_report_ftp_test(self):
    #     """
    #     Method to generate report for FTP test.
    #     """

    #     date = str(datetime.now()).split(",")[0].replace(" ", "-").split(".")[0]
    #     input_setup_info = {
    #         "AP": self.ftp_test.ap_name,
    #         "File Size": self.ftp_test.file_size,
    #         "Bands": self.ftp_test.band,
    #         "Direction": self.ftp_test.direction,
    #         "Stations": len(self.ftp_test.device_list),
    #         "Upstream": self.ftp_test.upstream,
    #         "SSID": self.ftp_test.ssid,
    #         "Security": self.ftp_test.security,
    #         "Contact": "support@candelatech.com"
    #     }
    #     if not self.ftp_test.traffic_duration:
    #         self.ftp_test.traffic_duration = (self.ftp_test.end_time - self.ftp_test.start_time).seconds
    #     self.ftp_test.generate_report(self.ftp_test.data, date, input_setup_info, bands=self.ftp_test.band,
    #                     test_rig="", test_tag="", dut_hw_version="",
    #                     dut_sw_version="", dut_model_num="",
    #                     dut_serial_num="", test_id="FTP Data",
    #                     csv_outfile="",
    #                     local_lf_report_dir="",config_devices=self.ftp_test.configuration)
    #     return self.ftp_test.data

    def run_ftp_test(
        self,
        mgr='localhost',
        mgr_port=8080,
        upstream_port='eth1',
        ssid=None,
        passwd=None,
        security=None,
        group_name=None,
        profile_name=None,
        file_name=None,
        ap_name=None,
        traffic_duration=None,
        clients_type="Real",
        dowebgui=False,
        directions=["Download"],
        file_sizes=["2MB", "500MB", "1000MB"],
        local_lf_report_dir="",
        ap_ip=None,
        twog_radio='wiphy1',
        fiveg_radio='wiphy0',
        sixg_radio='wiphy2',
        lf_username='lanforge',
        lf_password='lanforge',
        ssh_port=22,
        bands=["5G", "2.4G", "6G", "Both"],
        num_stations=0,
        result_dir='',
        device_list=[],
        test_name=None,
        expected_passfail_value=None,
        device_csv_name=None,
        wait_time=60,
        config=False,
        test_rig="",
        test_tag="",
        dut_hw_version="",
        dut_sw_version="",
        dut_model_num="",
        dut_serial_num="",
        test_priority="",
        test_id="FTP Data",
        csv_outfile="",
        eap_method="DEFAULT",
        eap_identity='',
        ieee8021x=False,
        ieee80211u=False,
        ieee80211w=1,
        enable_pkc=False,
        bss_transition=False,
        power_save=False,
        disable_ofdma=False,
        roam_ft_ds=False,
        key_management="DEFAULT",
        pairwise='NA',
        private_key='NA',
        ca_cert='NA',
        client_cert='NA',
        pk_passwd='NA',
        pac_file='NA',
        get_live_view=False,
        total_floors="0",
        lf_logger_config_json=None,
        help_summary=False
    ):
        args = SimpleNamespace(**locals())
        args.mgr = self.lanforge_ip
        args.mgr_port = int(self.port)
        print('args',args)
        return self.run_ftp_test1(args)

    def run_ftp_test1(self,args):
        # 1st time stamp for test duration
        time_stamp1 = datetime.now()

        # use for creating ftp_test dictionary
        interation_num = 0

        # empty dictionary for whole test data
        ftp_data = {}

        # validate_args(args)
        if args.traffic_duration.endswith('s') or args.traffic_duration.endswith('S'):
            args.traffic_duration = int(args.traffic_duration[0:-1])
        elif args.traffic_duration.endswith('m') or args.traffic_duration.endswith('M'):
            args.traffic_duration = int(args.traffic_duration[0:-1]) * 60
        elif args.traffic_duration.endswith('h') or args.traffic_duration.endswith('H'):
            args.traffic_duration = int(args.traffic_duration[0:-1]) * 60 * 60
        elif args.traffic_duration.endswith(''):
            args.traffic_duration = int(args.traffic_duration)

        # For all combinations ftp_data of directions, file size and client counts, run the test
        for band in args.bands:
            for direction in args.directions:
                for file_size in args.file_sizes:
                    # Start Test
                    obj = FtpTest(lfclient_host=args.mgr,
                                lfclient_port=args.mgr_port,
                                result_dir=args.result_dir,
                                upstream=args.upstream_port,
                                dut_ssid=args.ssid,
                                group_name=args.group_name,
                                profile_name=args.profile_name,
                                file_name=args.file_name,
                                dut_passwd=args.passwd,
                                dut_security=args.security,
                                num_sta=args.num_stations,
                                band=band,
                                ap_name=args.ap_name,
                                file_size=file_size,
                                direction=direction,
                                twog_radio=args.twog_radio,
                                fiveg_radio=args.fiveg_radio,
                                sixg_radio=args.sixg_radio,
                                lf_username=args.lf_username,
                                lf_password=args.lf_password,
                                # duration=pass_fail_duration(band, file_size),
                                traffic_duration=args.traffic_duration,
                                ssh_port=args.ssh_port,
                                clients_type=args.clients_type,
                                dowebgui=args.dowebgui,
                                device_list=args.device_list,
                                test_name=args.test_name,
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
                                get_live_view= args.get_live_view,
                                total_floors = args.total_floors
                                )

                    interation_num = interation_num + 1
                    obj.file_create()
                    if args.clients_type == "Real":
                        if not isinstance(args.device_list, list):
                            obj.device_list = obj.filter_iOS_devices(args.device_list)
                            if len(obj.device_list) == 0:
                                logger.info("There are no devices available")
                                return False
                        configured_device, configuration = obj.query_realclients()

                    if args.dowebgui and args.group_name:
                        # If no devices are configured,update the Web UI with "Stopped" status
                        if len(configured_device) == 0:
                            logger.warning("No device is available to run the test")
                            obj1 = {
                                "status": "Stopped",
                                "configuration_status": "configured"
                            }
                            obj.updating_webui_runningjson(obj1)
                            return
                        # If devices are configured, update the Web UI with the list of configured devices
                        else:
                            obj1 = {
                                "configured_devices": configured_device,
                                "configuration_status": "configured"
                            }
                            obj.updating_webui_runningjson(obj1)
                    obj.set_values()
                    obj.precleanup()
                    obj.build()
                    if not obj.passes():
                        logger.info(obj.get_fail_message())
                        return False

                    if obj.clients_type == 'Real':
                        obj.monitor_cx()
                        logger.info(f'Test started on the devices : {obj.input_devices_list}')
                    # First time stamp
                    time1 = datetime.now()
                    logger.info("Traffic started running at %s", time1)
                    obj.start(False, False)
                    # to fetch runtime values during the execution and fill the csv.
                    if args.dowebgui or args.clients_type == "Real":
                        obj.monitor_for_runtime_csv()
                        obj.my_monitor_for_real_devices()
                    else:
                        time.sleep(args.traffic_duration)
                        obj.my_monitor()

                    # # return list of download/upload completed time stamp
                    # time_list = obj.my_monitor(time1)
                    # # print("pass_fail_duration - time_list:{time_list}".format(time_list=time_list))
                    # # check pass or fail
                    # pass_fail = obj.pass_fail_check(time_list)

                    # # dictionary of whole data
                    # ftp_data[interation_num] = obj.ftp_test_data(time_list, pass_fail, args.bands, args.file_sizes,
                    #                                              args.directions, args.num_stations)
                    # # print("pass_fail_duration - ftp_data:{ftp_data}".format(ftp_data=ftp_data))
                    obj.stop()
                    print("Traffic stopped running")

                    obj.postcleanup()
                    time2 = datetime.now()
                    logger.info("Test ended at %s", time2)

        # 2nd time stamp for test duration
        time_stamp2 = datetime.now()

        # total time for test duration
        # test_duration = str(time_stamp2 - time_stamp1)[:-7]

        date = str(datetime.now()).split(",")[0].replace(" ", "-").split(".")[0]

        # print(ftp_data)

        input_setup_info = {
            "AP IP": args.ap_ip,
            "File Size": args.file_sizes,
            "Bands": args.bands,
            "Direction": args.directions,
            "Stations": args.num_stations,
            "Upstream": args.upstream_port,
            "SSID": args.ssid,
            "Security": args.security,
            "Contact": "support@candelatech.com"
        }
        if args.dowebgui:
            obj.data_for_webui["status"] = ["STOPPED"] * len(obj.url_data)

            df1 = pd.DataFrame(obj.data_for_webui)
            df1.to_csv('{}/ftp_datavalues.csv'.format(obj.result_dir), index=False)
            # copying to home directory i.e home/user_name
            # obj.copy_reports_to_home_dir()
        # Report generation when groups are specified
        if args.group_name:
            obj.generate_report(ftp_data, date, input_setup_info, test_rig=args.test_rig,
                                test_tag=args.test_tag, dut_hw_version=args.dut_hw_version,
                                dut_sw_version=args.dut_sw_version, dut_model_num=args.dut_model_num,
                                dut_serial_num=args.dut_serial_num, test_id=args.test_id,
                                bands=args.bands, csv_outfile=args.csv_outfile, local_lf_report_dir=args.local_lf_report_dir, config_devices=configuration)
        # Generating report without group-specific device configuration
        else:
            obj.generate_report(ftp_data, date, input_setup_info, test_rig=args.test_rig,
                                test_tag=args.test_tag, dut_hw_version=args.dut_hw_version,
                                dut_sw_version=args.dut_sw_version, dut_model_num=args.dut_model_num,
                                dut_serial_num=args.dut_serial_num, test_id=args.test_id,
                                bands=args.bands, csv_outfile=args.csv_outfile, local_lf_report_dir=args.local_lf_report_dir)

        if args.dowebgui:
            obj.copy_reports_to_home_dir()
        
        return True

        
    def run_qos_test(
        self,
        device_list=None,
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
        return True

    def run_vs_test(self,args):

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

        if args.file_name:
            args.file_name = args.file_name.removesuffix('.csv')

        media_source, media_quality = args.media_source.capitalize(), args.media_quality
        args.media_source = args.media_source.lower()
        args.media_quality = args.media_quality.lower()

        if any(char.isalpha() for char in args.media_source):
            args.media_source = media_source_dict[args.media_source]

        if any(char.isalpha() for char in args.media_quality):
            args.media_quality = media_quality_dict[args.media_quality]

        logger_config = lf_logger_config.lf_logger_config()

        if args.log_level:
            logger_config.set_level(level=args.log_level)

        if args.lf_logger_config_json:
            logger_config.lf_logger_config_json = args.lf_logger_config_json
            logger_config.load_lf_logger_config()

        logger = logging.getLogger(__name__)

        obj = VideoStreamingTest(host=args.host, ssid=args.ssid, passwd=args.passwd, encryp=args.encryp,
                                suporrted_release=["7.0", "10", "11", "12"], max_speed=args.max_speed,
                                url=args.url, urls_per_tenm=args.urls_per_tenm, duration=args.duration,
                                resource_ids=args.device_list, dowebgui=args.dowebgui, media_quality=args.media_quality, media_source=args.media_source,
                                result_dir=args.result_dir, test_name=args.test_name, incremental=args.incremental, postcleanup=args.postcleanup,
                                precleanup=args.precleanup,
                                pass_fail_val=args.expected_passfail_value,
                                csv_name=args.device_csv_name,
                                groups=args.group_name,
                                profiles=args.profile_name,
                                config=args.config,
                                file_name=args.file_name,
                                floors=args.floors,
                                get_live_view=args.get_live_view
                                )
        args.upstream_port = obj.change_port_to_ip(args.upstream_port)
        obj.validate_args()
        config_obj = DeviceConfig.DeviceConfig(lanforge_ip=args.host, file_name=args.file_name)
        # if not args.expected_passfail_value and args.device_csv_name is None:
        #     config_obj.device_csv_file(csv_name="device.csv")

        resource_ids_sm = []
        resource_set = set()
        resource_list = []
        resource_ids_generated = ""

        if args.group_name and args.file_name and args.profile_name:
            selected_groups = args.group_name.split(',')
            selected_profiles = args.profile_name.split(',')
            config_devices = {}
            for i in range(len(selected_groups)):
                config_devices[selected_groups[i]] = selected_profiles[i]
            config_obj.initiate_group()
            asyncio.run(config_obj.connectivity(config_devices, upstream=args.upstream_port))

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
            args.device_list = ",".join(id for id in eid_list)
        else:
            # When group/profile are not provided
            config_dict = {
                'ssid': args.ssid,
                'passwd': args.passwd,
                'enc': args.encryp,
                'eap_method': args.eap_method,
                'eap_identity': args.eap_identity,
                'ieee80211': args.ieee8021x,
                'ieee80211u': args.ieee80211u,
                'ieee80211w': args.ieee80211w,
                'enable_pkc': args.enable_pkc,
                'bss_transition': args.bss_transition,
                'power_save': args.power_save,
                'disable_ofdma': args.disable_ofdma,
                'roam_ft_ds': args.roam_ft_ds,
                'key_management': args.key_management,
                'pairwise': args.pairwise,
                'private_key': args.private_key,
                'ca_cert': args.ca_cert,
                'client_cert': args.client_cert,
                'pk_passwd': args.pk_passwd,
                'pac_file': args.pac_file,
                'server_ip': args.upstream_port
            }
            if args.device_list:
                all_devices = config_obj.get_all_devices()
                if args.group_name is None and args.file_name is None and args.profile_name is None:
                    dev_list = args.device_list.split(',')
                    if args.config:
                        asyncio.run(config_obj.connectivity(device_list=dev_list, wifi_config=config_dict))
            else:
                if args.config:
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
                    args.device_list = input("Enter the desired resources to run the test:")
                    dev1_list = args.device_list.split(',')
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
                            return False
                        resource_ids_sm = obj.resource_ids
                        resource_list = resource_ids_sm.split(',')
                        resource_set = set(resource_list)
                        resource_list_sorted = sorted(resource_set)
                        resource_ids_generated = ','.join(resource_list_sorted)
                        available_resources = list(resource_set)

        if args.dowebgui:
            resource_ids_sm = args.device_list.split(',')
            resource_set = set(resource_ids_sm)
            resource_list = sorted(resource_set)
            resource_ids_generated = ','.join(resource_list)
            resource_list_sorted = resource_list
            selected_devices, report_labels, selected_macs = obj.devices.query_user(dowebgui=args.dowebgui, device_list=resource_ids_generated)
            obj.resource_ids = ",".join(id.split(".")[1] for id in args.device_list.split(","))
            available_resources = [int(num) for num in obj.resource_ids.split(',')]
        else:
            obj.android_devices = obj.devices.get_devices(only_androids=True)
            if args.device_list:
                device_list = args.device_list.split(',')
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
            return False
        gave_incremental = False
        if args.incremental and not args.webgui_incremental:
            if obj.resource_ids:
                logging.info("The total available devices are {}".format(len(available_resources)))
                obj.incremental = input('Specify incremental values as 1,2,3 : ')
                obj.incremental = [int(x) for x in obj.incremental.split(',')]
            else:
                logging.info("incremental Values are not needed as Android devices are not selected..")
        elif not args.incremental:
            gave_incremental = True
            obj.incremental = [len(available_resources)]

        if args.webgui_incremental:
            incremental = [int(x) for x in args.webgui_incremental.split(',')]
            if (len(args.webgui_incremental) == 1 and incremental[0] != len(resource_list_sorted)) or (len(args.webgui_incremental) > 1):
                obj.incremental = incremental

        if obj.incremental and obj.resource_ids:
            if obj.incremental[-1] > len(available_resources):
                logging.info("Exiting the program as incremental values are greater than the resource ids provided")
                return False
            elif obj.incremental[-1] < len(available_resources) and len(obj.incremental) > 1:
                logging.info("Exiting the program as the last incremental value must be equal to selected devices")
                return False

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
        if args.duration.endswith('s') or args.duration.endswith('S'):
            args.duration = round(int(args.duration[0:-1]) / 60, 2)

        elif args.duration.endswith('m') or args.duration.endswith('M'):
            args.duration = int(args.duration[0:-1])

        elif args.duration.endswith('h') or args.duration.endswith('H'):
            args.duration = int(args.duration[0:-1]) * 60

        elif args.duration.endswith(''):
            args.duration = int(args.duration)

        incremental_capacity_list_values = obj.get_incremental_capacity_list()
        if incremental_capacity_list_values[-1] != len(available_resources):
            logger.error("Incremental capacity doesnt match available devices")
            if args.postcleanup:
                obj.postcleanup()
            return False
        # Process resource IDs and incremental values if specified
        if obj.resource_ids:
            if obj.incremental:
                test_setup_info_incremental_values = ','.join([str(n) for n in incremental_capacity_list_values])
                if len(obj.incremental) == len(available_resources):
                    test_setup_info_total_duration = args.duration
                elif len(obj.incremental) == 1 and len(available_resources) > 1:
                    if obj.incremental[0] == len(available_resources):
                        test_setup_info_total_duration = args.duration
                    else:
                        div = len(available_resources) // obj.incremental[0]
                        mod = len(available_resources) % obj.incremental[0]
                        if mod == 0:
                            test_setup_info_total_duration = args.duration * (div)
                        else:
                            test_setup_info_total_duration = args.duration * (div + 1)
                else:
                    test_setup_info_total_duration = args.duration * len(incremental_capacity_list_values)
            else:
                test_setup_info_total_duration = args.duration

            if args.webgui_incremental:
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

                    if args.dowebgui:
                        file_path = os.path.join(obj.result_dir, "../../Running_instances/{}_{}_running.json".format(obj.host, obj.test_name))
                        if os.path.exists(file_path):
                            with open(file_path, 'r') as file:
                                data = json.load(file)
                                if data["status"] != "Running":
                                    break
                        test_stopped_by_user = obj.monitor_for_runtime_csv(args.duration, file_path, individual_df, i, actual_start_time, resource_list_sorted, cx_order_list[i])
                    else:
                        test_stopped_by_user = obj.monitor_for_runtime_csv(args.duration, file_path, individual_df, i, actual_start_time, resource_list_sorted, cx_order_list[i])
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
                return False

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
                "Testname": args.test_name,
                "Device List": device_list_str,
                "No of Devices": "Total" + "( " + str(len(keys)) + " ): Android(" + str(len(keys)) + ")",
                "Incremental Values": "",
                "URL": args.url,
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
        if args.postcleanup:
            obj.postcleanup()

        if args.dowebgui:
            obj.copy_reports_to_home_dir()
        return True


    def run_vs_test1(
        self,
        ssid=None,
        passwd="something",
        encryp="psk",
        url="www.google.com",
        max_speed=0,
        urls_per_tenm=100,
        duration=None,
        test_name="video_streaming_test",
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
        args = SimpleNamespace(**locals())
        args.host = self.lanforge_ip
        return self.run_vs_test(args)

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
        default_config=True,
        thpt_mbps=False,
        help_summary=False
    ):

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
                                    config=config,
                                    default_config = default_config
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
                individual_dataframe_column.extend([f'Download{clients_to_run[i]}', f'Upload{clients_to_run[i]}', f'Rx % Drop  {clients_to_run[i]}',
                                                f'Tx % Drop{clients_to_run[i]}', f'Average RTT {clients_to_run[i]} ', f'RSSI {clients_to_run[i]} ', f'Tx-Rate {clients_to_run[i]} ', f'Rx-Rate {clients_to_run[i]} '])

            individual_dataframe_column.extend(['Overall Download', 'Overall Upload', 'Overall Rx % Drop ', 'Overall Tx % Drop', 'Iteration',
                                            'TIMESTAMP', 'Start_time', 'End_time', 'Remaining_Time', 'Incremental_list', 'status'])
            individual_df = pd.DataFrame(columns=individual_dataframe_column)

            overall_start_time = datetime.now()
            overall_end_time = overall_start_time + timedelta(seconds=int(test_duration) * len(incremental_capacity_list))

            for i in range(len(to_run_cxs)):
                is_device_configured = True
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
                            is_device_configured = throughput.configure_specific([device_to_run_resource])
                    if is_device_configured:
                        throughput.start_specific(to_run_cxs[i])

                # Determine device names based on the current iteration
                device_names = created_cx_lists_keys[:to_run_cxs_len[i][-1]]

                # Monitor throughput and capture all dataframes and test stop status
                all_dataframes, test_stopped_by_user = throughput.monitor(i, individual_df, device_names, incremental_capacity_list, overall_start_time, overall_end_time, is_device_configured)
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
        return True

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

        test_name = ""
        ip = ""
        # print('newww',args.local_lf_report_dir)
        # exit(0)
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
            return False
        elif args.use_existing_station_list and not args.existing_station_list:
            logger.error(
                "Argument \'--use_existing_station_list\' specified, but no existing stations provided. See \'--existing_station_list\'")
            return False

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
                        return False

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
                        return False
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
            return False

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
        return True


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
        endp_type="mc_udp",
        upstream_port="eth1",
        downstream_port=None,
        polling_interval="5s",
        radio=None,
        side_a_min_bps="0",
        side_a_min_pdu="MTU",
        side_b_min_bps="256000",
        side_b_min_pdu="MTU",
        rates_are_totals=True,
        multiconn=1,
        attenuators="",
        atten_vals="",
        wait=0,
        sta_start_offset="0",
        no_pre_cleanup=False,
        no_cleanup=True,
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
        real=True,
        get_live_view=False,
        total_floors="0",
        help_summary=False
    ):
        args = SimpleNamespace(**locals())
        args.lfmgr_port = self.port
        args.lfmgr = self.lanforge_ip
        args.local_lf_report_dir = os.getcwd()
        return self.run_mc_test(args)


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
            print('duration',duration)
            if type(duration) == int:
                pass
            elif duration.endswith('s') or duration.endswith('S'):
                duration = int(duration[0:-1])/60
            elif duration.endswith('m') or duration.endswith('M'):
                duration = int(duration[0:-1])
            elif duration.endswith('h') or duration.endswith('H'):
                duration = int(duration[0:-1])*60
            else:
                duration = int(duration)

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
                # if not expected_passfail_value and device_csv_name is None:
                #     config_obj.device_csv_file(csv_name="device.csv")
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
                # if not no_pre_cleanup:
                #     youtube.cleanup()

                # Check if the required tab exists, and exit if not
                if not youtube.check_tab_exists():
                    logging.error('Generic Tab is not available.\nAborting the test.')
                    return False

                if len(youtube.real_sta_list) > 0:
                    logging.info(f"checking real sta list while creating endpionts {youtube.real_sta_list}")
                    youtube.create_generic_endp(youtube.real_sta_list)
                else:
                    logging.info(f"checking real sta list while creating endpionts {youtube.real_sta_list}")
                    logging.error("No Real Devies Available")
                    return False

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
                # if not no_post_cleanup:
                #     youtube.generic_endps_profile.cleanup()
        except Exception as e:
            logging.error(f"Error occured {e}")
            # traceback.print_exc()
        finally:
            if not ('--help' in sys.argv or '-h' in sys.argv):
                traceback.print_exc()
                youtube.stop()
                # Stopping the Youtube test
                if do_webUI:
                    youtube.stop_test_yt()
                logging.info("Waiting for Cleanup of Browsers in Devices")
                time.sleep(10)
        return True

    def run_zoom_test(
            self,
        duration: int,
        signin_email: str,
        signin_passwd: str,
        participants: int,
        audio: bool = False,
        video: bool = False,
        wait_time: int = 30,
        log_level: str = None,
        lf_logger_config_json: str = None,
        resource_list: str = None,
        do_webUI: bool = False,
        report_dir: str = None,
        testname: str = None,
        zoom_host: str = None,
        file_name: str = None,
        group_name: str = None,
        profile_name: str = None,
        ssid: str = None,
        passwd: str = None,
        encryp: str = None,
        eap_method: str = 'DEFAULT',
        eap_identity: str = 'DEFAULT',
        ieee8021x: bool = False,
        ieee80211u: bool = False,
        ieee80211w: int = 1,
        enable_pkc: bool = False,
        bss_transition: bool = False,
        power_save: bool = False,
        disable_ofdma: bool = False,
        roam_ft_ds: bool = False,
        key_management: str = 'DEFAULT',
        pairwise: str = 'NA',
        private_key: str = 'NA',
        ca_cert: str = 'NA',
        client_cert: str = 'NA',
        pk_passwd: str = 'NA',
        pac_file: str = 'NA',
        upstream_port: str = 'NA',
        help_summary: str = None,
        expected_passfail_value: str = None,
        device_csv_name: str = None,
        config: bool = False
    ):
        try:
            lanforge_ip = self.lanforge_ip

            if True:

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


                zoom_automation = ZoomAutomation(audio=audio, video=video, lanforge_ip=lanforge_ip, wait_time=wait_time, testname=testname,
                                                upstream_port=upstream_port, config=config, selected_groups=selected_groups, selected_profiles=selected_profiles)
                upstream_port = zoom_automation.change_port_to_ip(upstream_port)
                realdevice = RealDevice(manager_ip=lanforge_ip,
                                        server_ip="192.168.1.61",
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
                laptops = realdevice.get_devices()

                if file_name:
                    new_filename = file_name.removesuffix(".csv")
                else:
                    new_filename = file_name
                config_obj = DeviceConfig.DeviceConfig(lanforge_ip=lanforge_ip, file_name=new_filename)

                # if not expected_passfail_value and device_csv_name is None:
                #     config_obj.device_csv_file(csv_name="device.csv")
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
                    if zoom_host in eid_list:
                        # Remove the existing instance of zoom_host from the list
                        eid_list.remove(zoom_host)
                        # Insert zoom_host at the beginning of the list
                        eid_list.insert(0, zoom_host)

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
                            if not do_webUI:
                                zoom_host = zoom_host.strip()
                                if zoom_host in dev_list:
                                    dev_list.remove(zoom_host)
                                dev_list.insert(0, zoom_host)
                            if config:
                                asyncio.run(config_obj.connectivity(device_list=dev_list, wifi_config=config_dict))
                            resource_list = ",".join(id for id in dev_list)
                    else:
                        # If no resources provided, prompt user to select devices manually
                        if config:
                            all_devices = config_obj.get_all_devices()
                            device_list = []
                            for device in all_devices:
                                if device["type"] != 'laptop':
                                    device_list.append(device["shelf"] + '.' + device["resource"] + " " + device["serial"])
                                elif device["type"] == 'laptop':
                                    device_list.append(device["shelf"] + '.' + device["resource"] + " " + device["hostname"])
                            print("Available Devices For Testing")
                            for device in device_list:
                                print(device)
                            zm_host = input("Enter Host Resource for the Test : ")
                            zm_host = zm_host.strip()
                            resource_list = input("Enter client Resources to run the test :")
                            resource_list = zm_host + "," + resource_list
                            dev1_list = resource_list.split(',')
                            asyncio.run(config_obj.connectivity(device_list=dev1_list, wifi_config=config_dict))

                result_list = []
                if not do_webUI:
                    if resource_list:
                        resources = resource_list.split(',')
                        resources = [r for r in resources if len(r.split('.')) > 1]
                        # resources = sorted(resources, key=lambda x: int(x.split('.')[1]))
                        get_data = zoom_automation.select_real_devices(real_device_obj=realdevice, real_sta_list=resources)
                        for item in get_data:
                            item = item.strip()
                            # Find and append the matching lap to result_list
                            matching_laps = [lap for lap in laptops if lap.startswith(item)]
                            result_list.extend(matching_laps)
                        if not result_list:
                            logging.info("Resources donot exist hence Terminating the test.")
                            return
                        if len(result_list) != len(get_data):
                            logging.info("Few Resources donot exist")
                    else:
                        resources = zoom_automation.select_real_devices(real_device_obj=realdevice)
                else:
                    if do_webUI:
                        zoom_automation.path = report_dir
                    resources = resource_list.split(',')
                    extracted_parts = [res.split('.')[:2] for res in resources]
                    formatted_parts = ['.'.join(parts) for parts in extracted_parts]

                    zoom_automation.select_real_devices(real_device_obj=realdevice, real_sta_list=formatted_parts)
                    if do_webUI:

                        if len(zoom_automation.real_sta_hostname) == 0:
                            logging.info("No device is available to run the test")
                            obj = {
                                "status": "Stopped",
                                "configuration_status": "configured"
                            }
                            zoom_automation.updating_webui_runningjson(obj)
                            return False
                        else:
                            obj = {
                                "configured_devices": zoom_automation.real_sta_hostname,
                                "configuration_status": "configured",
                                "no_of_devices": f' Total({len(zoom_automation.real_sta_os_type)}) : W({zoom_automation.windows}),L({zoom_automation.linux}),M({zoom_automation.mac})',
                                "device_list": zoom_automation.hostname_os_combination,
                                # "zoom_host":zoom_automation.zoom_host

                            }
                            zoom_automation.updating_webui_runningjson(obj)

                if not zoom_automation.check_tab_exists():
                    logging.error('Generic Tab is not available.\nAborting the test.')
                    return False

                zoom_automation.run(duration, upstream_port, signin_email, signin_passwd, participants)
                zoom_automation.data_store.clear()
                zoom_automation.generate_report()
                logging.info("Test Completed Sucessfully")
        except Exception as e:
            logging.error(f"AN ERROR OCCURED WHILE RUNNING TEST {e}")
            traceback.print_exc()
        finally:
            if not ('--help' in sys.argv or '-h' in sys.argv):
                if do_webUI:
                    try:
                        url = f"http://{lanforge_ip}:5454/update_status_yt"
                        headers = {
                            'Content-Type': 'application/json',
                        }

                        data = {
                            'status': 'Completed',
                            'name': testname
                        }

                        response = requests.post(url, json=data, headers=headers)

                        if response.status_code == 200:
                            logging.info("Successfully updated STOP status to 'Completed'")
                            pass
                        else:
                            logging.error(f"Failed to update STOP status: {response.status_code} - {response.text}")

                    except Exception as e:
                        # Print an error message if an exception occurs during the request
                        logging.error(f"An error occurred while updating status: {e}")

                zoom_automation.redis_client.set('login_completed', 0)
                zoom_automation.stop_signal = True
                logging.info("Waiting for Browser Cleanup in Laptops")
                time.sleep(10)
                # zoom_automation.generic_endps_profile.cleanup()
        return True


    def run_rb_test1(self,args):
        try:
            logger_config = lf_logger_config.lf_logger_config()

            if args.log_level:
                logger_config.set_level(level=args.log_level)

            if args.lf_logger_config_json:
                logger_config.lf_logger_config_json = args.lf_logger_config_json
                logger_config.load_lf_logger_config()
            if args.url.lower().startswith("www."):
                args.url = "https://" + args.url
            if args.url.lower().startswith("http://"):
                args.url = "https://" + args.url.removeprefix("http://")

            # Initialize an instance of RealBrowserTest with various parameters
            obj = RealBrowserTest(host=args.host,
                                ssid=args.ssid,
                                passwd=args.passwd,
                                encryp=args.encryp,
                                suporrted_release=["7.0", "10", "11", "12"],
                                max_speed=args.max_speed,
                                url=args.url, count=args.count,
                                duration=args.duration,
                                resource_ids=args.device_list,
                                dowebgui=args.dowebgui,
                                result_dir=args.result_dir,
                                test_name=args.test_name,
                                incremental=args.incremental,
                                no_postcleanup=args.no_postcleanup,
                                no_precleanup=args.no_precleanup,
                                file_name=args.file_name,
                                group_name=args.group_name,
                                profile_name=args.profile_name,
                                eap_method=args.eap_method,
                                eap_identity=args.eap_identity,
                                ieee80211=args.ieee80211,
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
                                upstream_port=args.upstream_port,
                                expected_passfail_value=args.expected_passfail_value,
                                device_csv_name=args.device_csv_name,
                                wait_time=args.wait_time,
                                config=args.config,
                                selected_groups=args.group_name,
                                selected_profiles=args.profile_name
                                )
            obj.change_port_to_ip()
            obj.validate_and_process_args()
            obj.config_obj = DeviceConfig.DeviceConfig(lanforge_ip=obj.host, file_name=obj.file_name, wait_time=obj.wait_time)
            # if not obj.expected_passfail_value and obj.device_csv_name is None:
            #     obj.config_obj.device_csv_file(csv_name="device.csv")
            obj.run_flask_server()
            if obj.group_name and obj.profile_name and obj.file_name:
                available_resources = obj.process_group_profiles()
            else:
                # --- Build configuration dictionary for WiFi parameters ---
                config_dict = {
                    'ssid': args.ssid,
                    'passwd': args.passwd,
                    'enc': args.encryp,
                    'eap_method': args.eap_method,
                    'eap_identity': args.eap_identity,
                    'ieee80211': args.ieee80211,
                    'ieee80211u': args.ieee80211u,
                    'ieee80211w': args.ieee80211w,
                    'enable_pkc': args.enable_pkc,
                    'bss_transition': args.bss_transition,
                    'power_save': args.power_save,
                    'disable_ofdma': args.disable_ofdma,
                    'roam_ft_ds': args.roam_ft_ds,
                    'key_management': args.key_management,
                    'pairwise': args.pairwise,
                    'private_key': args.private_key,
                    'ca_cert': args.ca_cert,
                    'client_cert': args.client_cert,
                    'pk_passwd': args.pk_passwd,
                    'pac_file': args.pac_file,
                    'server_ip': obj.upstream_port,
                }
                available_resources = obj.process_resources(config_dict)
            if len(available_resources) != 0:
                available_resources = obj.filter_ios_devices(available_resources)
            if len(available_resources) == 0:
                logging.error("No devices available to run the test. Exiting...")
                return False

            # --- Print available resources ---
            logging.info("Devices available: {}".format(available_resources))
            if obj.expected_passfail_value or obj.device_csv_name:
                obj.update_passfail_value(available_resources)
            # --- Handle incremental values ---
            obj.handle_incremental(args, obj, available_resources, available_resources)
            obj.handle_duration()
            obj.run_test(available_resources)

        except Exception as e:
            logging.error("Error occured", e)
            # traceback.print_exc()
        finally:
            if '--help' not in sys.argv and '-h' not in sys.argv:
                obj.create_report()
                if obj.dowebgui:
                    obj.webui_stop()
                obj.stop()

                # if not args.no_postcleanup:
                #     obj.postcleanup()
        return True


    def run_rb_test(
        self,
        ssid: str = None,
        passwd: str = None,
        encryp: str = None,
        url: str = "https://google.com",
        max_speed: int = 0,
        count: int = 1,
        duration: str = None,
        test_name: str = None,
        dowebgui: bool = False,
        result_dir: str = '',
        lf_logger_config_json: str = None,
        log_level: str = None,
        debug: bool = False,
        device_list: str = None,
        webgui_incremental: str = None,
        incremental: bool = False,
        no_laptops: bool = False,
        no_postcleanup: bool = False,
        no_precleanup: bool = False,
        file_name: str = None,
        group_name: str = None,
        profile_name: str = None,
        eap_method: str = 'DEFAULT',
        eap_identity: str = 'DEFAULT',
        ieee80211: bool = False,
        ieee80211u: bool = False,
        ieee80211w: int = 1,
        enable_pkc: bool = False,
        bss_transition: bool = False,
        power_save: bool = False,
        disable_ofdma: bool = False,
        roam_ft_ds: bool = False,
        key_management: str = 'DEFAULT',
        pairwise: str = 'NA',
        private_key: str = 'NA',
        ca_cert: str = 'NA',
        client_cert: str = 'NA',
        pk_passwd: str = 'NA',
        pac_file: str = 'NA',
        upstream_port: str = 'NA',
        help_summary: str = None,
        expected_passfail_value: str = None,
        device_csv_name: str = None,
        wait_time: int = 60,
        config: bool = False
    ):
        args = SimpleNamespace(**locals())
        args.host = self.lanforge_ip
        return self.run_rb_test1(args)

def validate_individual_args(args,test_name):
    if test_name == 'ping_test':
        return True
    elif test_name =='http_test':
        return True
    elif test_name =='ftp_test':
        return True
    elif test_name =='thput_test':
        return True
    elif test_name =='qos_test':
        return True
    elif test_name =='vs_test':
        return True
    elif test_name =="zoom_test":
        if args["zoom_signin_email"] is None:
            return False
        if args["zoom_signin_passwd"] is None:
            return False
        if args["zoom_participants"] is None:
            return False
        return True
    elif test_name =="yt_test":
        if args["yt_url"] is None:
            return False
    elif test_name == "rb_test":
        return True








def validate_args(args):
    # pass/fail , config , groups-profiles arg validation
    tests = ["http_test","ping_test","ftp_test","thput_test","qos_test","vs_test","mcast_test","yt_test","rb_test","zoom_test"]
    for test in tests:
        flag_test = True
        if args[test]:
            logger.info(f"validating args for {test}...")
            flag_test = validate_individual_args(args,test)
            test = test.split('_')[0]
            if args[f'{test}_expected_passfail_value'] and args[f'{test}_device_csv_name']:
                logger.error(f"Specify either --{test}_expected_passfail_value or --{test}_device_csv_name")
                flag_test = False
            if args[f'{test}_group_name']:
                selected_groups = args[f'{test}_group_name'].split(',')
            else:
                selected_groups = []
            if args[f'{test}_profile_name']:
                selected_profiles = args['profile_name'].split(',')
            else:
                selected_profiles = []

            if len(selected_groups) != len(selected_profiles):
                logger.error(f"Number of groups should match number of profiles")
                flag_test = False
            elif args[f'{test}_group_name'] and args[f'{test}_profile_name'] and args[f'{test}_file_name'] and args[f'{test}_device_list'] != []:
                logger.error(f"Either --{test}_group_name or --{test}_device_list should be entered not both")
                flag_test = False
            elif args[f'{test}_ssid'] and args[f'{test}_profile_name']:
                logger.error(f"Either --{test}_ssid or --{test}_profile_name should be given")
                flag_test = False

            elif args[f'{test}_file_name'] and (args.get(f'{test}_group_name') is None or args.get(f'{test}_profile_name') is None):
                logger.error(f"Please enter the correct set of arguments for configuration")
                flag_test = False

            if args[f'{test}_config'] and args.get(f'{test}_group_name') is None:
                if args.get(f'{test}_ssid') and args.get(f'{test}_security') and args[f'{test}_security'].lower() == 'open' and (args.get(f'{test}_passwd') is None or args[f'{test}_passwd'] == ''):
                    args[f'{test}_passwd'] = '[BLANK]'

                if args.get(f'{test}_ssid') is None or args.get(f'{test}_passwd') is None or args[f'{test}_passwd'] == '':
                    logger.error(f'For configuration need to Specify --{test}_ssid , --{test}_passwd (Optional for "open" type security) , --{test}_security')
                    flag_test = False

                elif args.get(f'{test}_ssid') and args[f'{test}_passwd'] == '[BLANK]' and args.get(f'{test}_security') and args[f'{test}_security'].lower() != 'open':
                    logger.error(f'Please provide valid --{test}_passwd and --{test}_security configuration')
                    flag_test = False

                elif args.get(f'{test}_ssid') and args.get(f'{test}_passwd'):
                    if args.get(f'{test}_security') is None:
                        logger.error(f'Security must be provided when --{test}_ssid and --{test}_password specified')
                        flag_test = False
                    elif args[f'{test}_passwd'] == '[BLANK]' and args[f'{test}_security'].lower() != 'open':
                        logger.error(f'Please provide valid passwd and security configuration')
                        flag_test = False
                    elif args[f'{test}_security'].lower() == 'open' and args[f'{test}_passwd'] != '[BLANK]':
                        logger.error(f"For an open type security, the password should be left blank (i.e., set to '' or [BLANK]).")
                        flag_test = False
            if flag_test:
                logger.info(f"Arg validation check done for {test}")


def main():

    parser = argparse.ArgumentParser(
    prog="lf_interop_throughput.py",
    formatter_class=argparse.RawTextHelpFormatter,
    )
    parser = argparse.ArgumentParser(description="Run Candela API Tests")
    #Always Common
    parser.add_argument('--mgr', '--lfmgr', default='localhost', help='hostname for where LANforge GUI is running')
    parser.add_argument('--mgr_port', '--port', default=8080, help='port LANforge GUI HTTP service is running on')
    parser.add_argument('--upstream_port', '-u', default='eth1', help='non-station port that generates traffic: <resource>.<port>, e.g: 1.eth1')
    #Common
    parser.add_argument('--device_list', help="Enter the devices on which the test should be run", default=[])
    parser.add_argument('--duration', help='Please enter the duration in s,m,h (seconds or minutes or hours).Eg: 30s,5m,48h')
    parser.add_argument('--parallel',
                          action="store_true",
                          help='to run in parallel')
    parser.add_argument("--tests",type=str,help="Comma-separated ordered list of tests to run (e.g., ping_test,http_test,ping_test)")
    parser.add_argument('--series_tests', help='Comma-separated list of tests to run in series')
    parser.add_argument('--parallel_tests', help='Comma-separated list of tests to run in parallel')
    parser.add_argument('--order_priority', choices=['series', 'parallel'], default='series',
                    help='Which tests to run first: series or parallel')

    #NOt common
    #ping
    #without config
    parser.add_argument('--ping_test',
                          action="store_true",
                          help='ping_test consists')
    parser.add_argument('--ping_target',
                          type=str,
                          help='Target URL or port for ping test',
                          default='1.1.eth1')
    parser.add_argument('--ping_interval',
                          type=str,
                          help='Interval (in seconds) between the echo requests',
                          default='1')

    parser.add_argument('--ping_duration',
                          type=float,
                          help='Duration (in minutes) to run the ping test',
                          default=1)
    parser.add_argument('--ping_use_default_config',
                          action='store_true',
                          help='specify this flag if wanted to proceed with existing Wi-Fi configuration of the devices')
    parser.add_argument('--ping_device_list', help="Enter the devices on which the ping test should be run", default=[])
    #ping pass fail value
    parser.add_argument("--ping_expected_passfail_value", help="Specify the expected number of urls", default=None)
    parser.add_argument("--ping_device_csv_name", type=str, help='Specify the csv name to store expected url values', default=None)
    #ping with groups and profile configuration
    parser.add_argument('--ping_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    parser.add_argument('--ping_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    parser.add_argument('--ping_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')

    #ping configuration with --config
    parser.add_argument("--ping_config", action="store_true", help="Specify for configuring the devices")
    parser.add_argument('--ping_ssid', help='WiFi SSID for script objects to associate to')
    parser.add_argument('--ping_passwd', '--ping_password', '--ping_key', default="[BLANK]", help='WiFi passphrase/password/key')
    parser.add_argument('--ping_security', help='WiFi Security protocol: < open | wep | wpa | wpa2 | wpa3 >', default="open")
    parser.add_argument("--ping_eap_method", type=str, default='DEFAULT', help="Specify the EAP method for authentication.")
    parser.add_argument("--ping_eap_identity", type=str, default='', help="Specify the EAP identity for authentication.")
    parser.add_argument("--ping_ieee8021x", action="store_true", help='Enables 802.1X enterprise authentication for test stations.')
    parser.add_argument("--ping_ieee80211u", action="store_true", help='Enables IEEE 802.11u (Hotspot 2.0) support.')
    parser.add_argument("--ping_ieee80211w", type=int, default=1, help='Enables IEEE 802.11w (Management Frame Protection) support.')
    parser.add_argument("--ping_enable_pkc", action="store_true", help='Enables pkc support.')
    parser.add_argument("--ping_bss_transition", action="store_true", help='Enables BSS transition support.')
    parser.add_argument("--ping_power_save", action="store_true", help='Enables power-saving features.')
    parser.add_argument("--ping_disable_ofdma", action="store_true", help='Disables OFDMA support.')
    parser.add_argument("--ping_roam_ft_ds", action="store_true", help='Enables fast BSS transition (FT) support')
    parser.add_argument("--ping_key_management", type=str, default='DEFAULT', help='Specify the key management method (e.g., WPA-PSK, WPA-EAP')
    parser.add_argument("--ping_pairwise", type=str, default='NA')
    parser.add_argument("--ping_private_key", type=str, default='NA', help='Specify EAP private key certificate file.')
    parser.add_argument("--ping_ca_cert", type=str, default='NA', help='Specifiy the CA certificate file name')
    parser.add_argument("--ping_client_cert", type=str, default='NA', help='Specify the client certificate file name')
    parser.add_argument("--ping_pk_passwd", type=str, default='NA', help='Specify the password for the private key')
    parser.add_argument("--ping_pac_file", type=str, default='NA', help='Specify the pac file name')
    # parser.add_argument('--ping_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    # parser.add_argument('--ping_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    # parser.add_argument('--ping_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')
    parser.add_argument("--ping_wait_time", type=int, help='Specify the maximum time to wait for Configuration', default=60)
    #http
    parser.add_argument('--http_test',
                          action="store_true",
                          help='http consists')
    parser.add_argument('--http_bands', nargs="+", help='specify which band testing you want to run eg 5G, 2.4G, 6G',
                          default=["5G", "2.4G", "6G"])
    parser.add_argument('--http_duration', help='Please enter the duration in s,m,h (seconds or minutes or hours).Eg: 30s,5m,48h')
    parser.add_argument('--http_file_size', type=str, help='specify the size of file you want to download', default='5MB')
    parser.add_argument('--http_device_list', help="Enter the devices on which the ping test should be run", default=[])
    #http pass fail value
    parser.add_argument("--http_expected_passfail_value", help="Specify the expected number of urls", default=None)
    parser.add_argument("--http_device_csv_name", type=str, help='Specify the csv name to store expected url values', default=None)
    #http with groups and profile configuration
    parser.add_argument('--http_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    parser.add_argument('--http_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    parser.add_argument('--http_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')

    #http configuration with --config
    parser.add_argument("--http_config", action="store_true", help="Specify for configuring the devices")
    parser.add_argument('--http_ssid', help='WiFi SSID for script objects to associate to')
    parser.add_argument('--http_passwd', '--http_password', '--http_key', default="[BLANK]", help='WiFi passphrase/password/key')
    parser.add_argument('--http_security', help='WiFi Security protocol: < open | wep | wpa | wpa2 | wpa3 >', default="open")
    parser.add_argument("--http_eap_method", type=str, default='DEFAULT', help="Specify the EAP method for authentication.")
    parser.add_argument("--http_eap_identity", type=str, default='', help="Specify the EAP identity for authentication.")
    parser.add_argument("--http_ieee8021x", action="store_true", help='Enables 802.1X enterprise authentication for test stations.')
    parser.add_argument("--http_ieee80211u", action="store_true", help='Enables IEEE 802.11u (Hotspot 2.0) support.')
    parser.add_argument("--http_ieee80211w", type=int, default=1, help='Enables IEEE 802.11w (Management Frame Protection) support.')
    parser.add_argument("--http_enable_pkc", action="store_true", help='Enables pkc support.')
    parser.add_argument("--http_bss_transition", action="store_true", help='Enables BSS transition support.')
    parser.add_argument("--http_power_save", action="store_true", help='Enables power-saving features.')
    parser.add_argument("--http_disable_ofdma", action="store_true", help='Disables OFDMA support.')
    parser.add_argument("--http_roam_ft_ds", action="store_true", help='Enables fast BSS transition (FT) support')
    parser.add_argument("--http_key_management", type=str, default='DEFAULT', help='Specify the key management method (e.g., WPA-PSK, WPA-EAP')
    parser.add_argument("--http_pairwise", type=str, default='NA')
    parser.add_argument("--http_private_key", type=str, default='NA', help='Specify EAP private key certificate file.')
    parser.add_argument("--http_ca_cert", type=str, default='NA', help='Specifiy the CA certificate file name')
    parser.add_argument("--http_client_cert", type=str, default='NA', help='Specify the client certificate file name')
    parser.add_argument("--http_pk_passwd", type=str, default='NA', help='Specify the password for the private key')
    parser.add_argument("--http_pac_file", type=str, default='NA', help='Specify the pac file name')
    # parser.add_argument('--http_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    # parser.add_argument('--http_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    # parser.add_argument('--http_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')
    parser.add_argument("--http_wait_time", type=int, help='Specify the maximum time to wait for Configuration', default=60)

    #ftp
    parser.add_argument('--ftp_test',
                          action="store_true",
                          help='ftp_test consists')
    parser.add_argument('--ftp_bands', nargs="+", help='specify which band testing you want to run eg 5G, 2.4G, 6G',
                          default=["5G", "2.4G", "6G"])
    parser.add_argument('--ftp_duration', help='Please enter the duration in s,m,h (seconds or minutes or hours).Eg: 30s,5m,48h')
    parser.add_argument('--ftp_file_size', type=str, help='specify the size of file you want to download', default='5MB')
    parser.add_argument('--ftp_device_list', help="Enter the devices on which the ping test should be run", default=[])
    #ftp pass fail value
    parser.add_argument("--ftp_expected_passfail_value", help="Specify the expected number of urls", default=None)
    parser.add_argument("--ftp_device_csv_name", type=str, help='Specify the csv name to store expected url values', default=None)
    #ftp with groups and profile configuration
    parser.add_argument('--ftp_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    parser.add_argument('--ftp_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    parser.add_argument('--ftp_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')

    #ftp configuration with --config
    parser.add_argument("--ftp_config", action="store_true", help="Specify for configuring the devices")
    parser.add_argument('--ftp_ssid', help='WiFi SSID for script objects to associate to')
    parser.add_argument('--ftp_passwd', '--ftp_password', '--ftp_key', default="[BLANK]", help='WiFi passphrase/password/key')
    parser.add_argument('--ftp_security', help='WiFi Security protocol: < open | wep | wpa | wpa2 | wpa3 >', default="open")
    parser.add_argument("--ftp_eap_method", type=str, default='DEFAULT', help="Specify the EAP method for authentication.")
    parser.add_argument("--ftp_eap_identity", type=str, default='', help="Specify the EAP identity for authentication.")
    parser.add_argument("--ftp_ieee8021x", action="store_true", help='Enables 802.1X enterprise authentication for test stations.')
    parser.add_argument("--ftp_ieee80211u", action="store_true", help='Enables IEEE 802.11u (Hotspot 2.0) support.')
    parser.add_argument("--ftp_ieee80211w", type=int, default=1, help='Enables IEEE 802.11w (Management Frame Protection) support.')
    parser.add_argument("--ftp_enable_pkc", action="store_true", help='Enables pkc support.')
    parser.add_argument("--ftp_bss_transition", action="store_true", help='Enables BSS transition support.')
    parser.add_argument("--ftp_power_save", action="store_true", help='Enables power-saving features.')
    parser.add_argument("--ftp_disable_ofdma", action="store_true", help='Disables OFDMA support.')
    parser.add_argument("--ftp_roam_ft_ds", action="store_true", help='Enables fast BSS transition (FT) support')
    parser.add_argument("--ftp_key_management", type=str, default='DEFAULT', help='Specify the key management method (e.g., WPA-PSK, WPA-EAP')
    parser.add_argument("--ftp_pairwise", type=str, default='NA')
    parser.add_argument("--ftp_private_key", type=str, default='NA', help='Specify EAP private key certificate file.')
    parser.add_argument("--ftp_ca_cert", type=str, default='NA', help='Specifiy the CA certificate file name')
    parser.add_argument("--ftp_client_cert", type=str, default='NA', help='Specify the client certificate file name')
    parser.add_argument("--ftp_pk_passwd", type=str, default='NA', help='Specify the password for the private key')
    parser.add_argument("--ftp_pac_file", type=str, default='NA', help='Specify the pac file name')
    # parser.add_argument('--ftp_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    # parser.add_argument('--ftp_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    # parser.add_argument('--ftp_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')
    parser.add_argument("--ftp_wait_time", type=int, help='Specify the maximum time to wait for Configuration', default=60)

    #qos
    parser.add_argument('--qos_test',
                          action="store_true",
                          help='qos_test consists')
    parser.add_argument('--qos_duration', help='--qos_duration sets the duration of the test', default="2m")
    parser.add_argument('--qos_upload', help='--upload traffic load per connection (upload rate)')
    parser.add_argument('--qos_download', help='--download traffic load per connection (download rate)')
    parser.add_argument('--qos_traffic_type', help='Select the Traffic Type [lf_udp, lf_tcp]', required=False)
    parser.add_argument('--qos_tos', help='Enter the tos. Example1 : "BK,BE,VI,VO" , Example2 : "BK,VO", Example3 : "VI" ')
    parser.add_argument('--qos_device_list', help="Enter the devices on which the ping test should be run", default=[])
    #qos pass fail value
    parser.add_argument("--qos_expected_passfail_value", help="Specify the expected number of urls", default=None)
    parser.add_argument("--qos_device_csv_name", type=str, help='Specify the csv name to store expected url values', default=None)
    #qos with groups and profile configuration
    parser.add_argument('--qos_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    parser.add_argument('--qos_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    parser.add_argument('--qos_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')

    #qos configuration with --config
    parser.add_argument("--qos_config", action="store_true", help="Specify for configuring the devices")
    parser.add_argument('--qos_ssid', help='WiFi SSID for script objects to associate to')
    parser.add_argument('--qos_passwd', '--qos_password', '--qos_key', default="[BLANK]", help='WiFi passphrase/password/key')
    parser.add_argument('--qos_security', help='WiFi Security protocol: < open | wep | wpa | wpa2 | wpa3 >', default="open")
    #Optional qos config args
    parser.add_argument("--qos_eap_method", type=str, default='DEFAULT', help="Specify the EAP method for authentication.")
    parser.add_argument("--qos_eap_identity", type=str, default='', help="Specify the EAP identity for authentication.")
    parser.add_argument("--qos_ieee8021x", action="store_true", help='Enables 802.1X enterprise authentication for test stations.')
    parser.add_argument("--qos_ieee80211u", action="store_true", help='Enables IEEE 802.11u (Hotspot 2.0) support.')
    parser.add_argument("--qos_ieee80211w", type=int, default=1, help='Enables IEEE 802.11w (Management Frame Protection) support.')
    parser.add_argument("--qos_enable_pkc", action="store_true", help='Enables pkc support.')
    parser.add_argument("--qos_bss_transition", action="store_true", help='Enables BSS transition support.')
    parser.add_argument("--qos_power_save", action="store_true", help='Enables power-saving features.')
    parser.add_argument("--qos_disable_ofdma", action="store_true", help='Disables OFDMA support.')
    parser.add_argument("--qos_roam_ft_ds", action="store_true", help='Enables fast BSS transition (FT) support')
    parser.add_argument("--qos_key_management", type=str, default='DEFAULT', help='Specify the key management method (e.g., WPA-PSK, WPA-EAP')
    parser.add_argument("--qos_pairwise", type=str, default='NA')
    parser.add_argument("--qos_private_key", type=str, default='NA', help='Specify EAP private key certificate file.')
    parser.add_argument("--qos_ca_cert", type=str, default='NA', help='Specifiy the CA certificate file name')
    parser.add_argument("--qos_client_cert", type=str, default='NA', help='Specify the client certificate file name')
    parser.add_argument("--qos_pk_passwd", type=str, default='NA', help='Specify the password for the private key')
    parser.add_argument("--qos_pac_file", type=str, default='NA', help='Specify the pac file name')
    # parser.add_argument('--qos_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    # parser.add_argument('--qos_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    # parser.add_argument('--qos_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')
    parser.add_argument("--qos_wait_time", type=int, help='Specify the maximum time to wait for Configuration', default=60)


    #vs
    parser.add_argument('--vs_test',
                          action="store_true",
                          help='vs_test consists')
    parser.add_argument("--vs_url", default="www.google.com", help='specify the url you want to test on')
    parser.add_argument("--vs_media_source", type=str, default='1')
    parser.add_argument("--vs_media_quality", type=str, default='0')
    parser.add_argument('--vs_duration', type=str, help='time to run traffic')
    parser.add_argument('--vs_device_list', help="Enter the devices on which the ping test should be run", default=[])
    #vs pass fail value
    parser.add_argument("--vs_expected_passfail_value", help="Specify the expected number of urls", default=None)
    parser.add_argument("--vs_device_csv_name", type=str, help='Specify the csv name to store expected url values', default=None)
    #vs with groups and profile configuration
    parser.add_argument('--vs_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    parser.add_argument('--vs_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    parser.add_argument('--vs_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')

    #vs configuration with --config
    parser.add_argument("--vs_config", action="store_true", help="Specify for configuring the devices")
    parser.add_argument('--vs_ssid', help='WiFi SSID for script objects to associate to')
    parser.add_argument('--vs_passwd', '--vs_password', '--vs_key', default="[BLANK]", help='WiFi passphrase/password/key')
    parser.add_argument('--vs_security', help='WiFi Security protocol: < open | wep | wpa | wpa2 | wpa3 >', default="open")
    #Optional vs config args
    parser.add_argument("--vs_eap_method", type=str, default='DEFAULT', help="Specify the EAP method for authentication.")
    parser.add_argument("--vs_eap_identity", type=str, default='', help="Specify the EAP identity for authentication.")
    parser.add_argument("--vs_ieee8021x", action="store_true", help='Enables 802.1X enterprise authentication for test stations.')
    parser.add_argument("--vs_ieee80211u", action="store_true", help='Enables IEEE 802.11u (Hotspot 2.0) support.')
    parser.add_argument("--vs_ieee80211w", type=int, default=1, help='Enables IEEE 802.11w (Management Frame Protection) support.')
    parser.add_argument("--vs_enable_pkc", action="store_true", help='Enables pkc support.')
    parser.add_argument("--vs_bss_transition", action="store_true", help='Enables BSS transition support.')
    parser.add_argument("--vs_power_save", action="store_true", help='Enables power-saving features.')
    parser.add_argument("--vs_disable_ofdma", action="store_true", help='Disables OFDMA support.')
    parser.add_argument("--vs_roam_ft_ds", action="store_true", help='Enables fast BSS transition (FT) support')
    parser.add_argument("--vs_key_management", type=str, default='DEFAULT', help='Specify the key management method (e.g., WPA-PSK, WPA-EAP')
    parser.add_argument("--vs_pairwise", type=str, default='NA')
    parser.add_argument("--vs_private_key", type=str, default='NA', help='Specify EAP private key certificate file.')
    parser.add_argument("--vs_ca_cert", type=str, default='NA', help='Specifiy the CA certificate file name')
    parser.add_argument("--vs_client_cert", type=str, default='NA', help='Specify the client certificate file name')
    parser.add_argument("--vs_pk_passwd", type=str, default='NA', help='Specify the password for the private key')
    parser.add_argument("--vs_pac_file", type=str, default='NA', help='Specify the pac file name')
    # parser.add_argument('--vs_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    # parser.add_argument('--vs_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    # parser.add_argument('--vs_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')
    parser.add_argument("--vs_wait_time", type=int, help='Specify the maximum time to wait for Configuration', default=60)

    #thput
    parser.add_argument('--thput_test',
                          action="store_true",
                          help='thput_test consists')
    parser.add_argument('--thput_test_duration', help='--thput_test_duration sets the duration of the test', default="")
    parser.add_argument('--thput_download', help='--thput_download traffic load per connection (download rate)', default='2560')
    parser.add_argument('--thput_traffic_type', help='Select the Traffic Type [lf_udp, lf_tcp]', required=False)
    parser.add_argument('--thput_upload', help='--thput_download traffic load per connection (download rate)', default='2560')
    parser.add_argument('--thput_device_list', help="Enter the devices on which the test should be run", default=[])
    parser.add_argument('--thput_do_interopability', action='store_true', help='Ensures test on devices run sequentially, capturing each device’s data individually for plotting in the final report.')
    parser.add_argument("--thput_default_config", action="store_true", help="To stop configuring the devices in interoperability")
    #thput pass fail value
    parser.add_argument("--thput_expected_passfail_value", help="Specify the expected number of urls", default=None)
    parser.add_argument("--thput_device_csv_name", type=str, help='Specify the csv name to store expected url values', default=None)
    #thput with groups and profile configuration
    parser.add_argument('--thput_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    parser.add_argument('--thput_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    parser.add_argument('--thput_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')

    #thput configuration with --config
    parser.add_argument("--thput_config", action="store_true", help="Specify for configuring the devices")
    parser.add_argument('--thput_ssid', help='WiFi SSID for script objects to associate to')
    parser.add_argument('--thput_passwd', '--thput_password', '--thput_key', default="[BLANK]", help='WiFi passphrase/password/key')
    parser.add_argument('--thput_security', help='WiFi Security protocol: < open | wep | wpa | wpa2 | wpa3 >', default="open")
    #Optional thput config args
    parser.add_argument("--thput_eap_method", type=str, default='DEFAULT', help="Specify the EAP method for authentication.")
    parser.add_argument("--thput_eap_identity", type=str, default='', help="Specify the EAP identity for authentication.")
    parser.add_argument("--thput_ieee8021x", action="store_true", help='Enables 802.1X enterprise authentication for test stations.')
    parser.add_argument("--thput_ieee80211u", action="store_true", help='Enables IEEE 802.11u (Hotspot 2.0) support.')
    parser.add_argument("--thput_ieee80211w", type=int, default=1, help='Enables IEEE 802.11w (Management Frame Protection) support.')
    parser.add_argument("--thput_enable_pkc", action="store_true", help='Enables pkc support.')
    parser.add_argument("--thput_bss_transition", action="store_true", help='Enables BSS transition support.')
    parser.add_argument("--thput_power_save", action="store_true", help='Enables power-saving features.')
    parser.add_argument("--thput_disable_ofdma", action="store_true", help='Disables OFDMA support.')
    parser.add_argument("--thput_roam_ft_ds", action="store_true", help='Enables fast BSS transition (FT) support')
    parser.add_argument("--thput_key_management", type=str, default='DEFAULT', help='Specify the key management method (e.g., WPA-PSK, WPA-EAP')
    parser.add_argument("--thput_pairwise", type=str, default='NA')
    parser.add_argument("--thput_private_key", type=str, default='NA', help='Specify EAP private key certificate file.')
    parser.add_argument("--thput_ca_cert", type=str, default='NA', help='Specifiy the CA certificate file name')
    parser.add_argument("--thput_client_cert", type=str, default='NA', help='Specify the client certificate file name')
    parser.add_argument("--thput_pk_passwd", type=str, default='NA', help='Specify the password for the private key')
    parser.add_argument("--thput_pac_file", type=str, default='NA', help='Specify the pac file name')
    # parser.add_argument('--thput_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    # parser.add_argument('--thput_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    # parser.add_argument('--thput_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')
    parser.add_argument("--thput_wait_time", type=int, help='Specify the maximum time to wait for Configuration', default=60)
    #mcast
    parser.add_argument('--mcast_test',
                          action="store_true",
                          help='mcast_test consists')
    parser.add_argument(
        '--mcast_test_duration',
        help='--test_duration <how long to run>  example --time 5d (5 days) default: 3m options: number followed by d, h, m or s',
        default='3m')
    parser.add_argument(
        '--mcast_endp_type',
        help=(
            '--endp_type <types of traffic> example --endp_type \"lf_udp lf_tcp mc_udp\" '
            ' Default: lf_udp , options: lf_udp, lf_udp6, lf_tcp, lf_tcp6, mc_udp, mc_udp6'),
        default='lf_udp',
        type=valid_endp_types)
    parser.add_argument(
        '--mcast_upstream_port',
        help='--mcast_upstream_port <cross connect upstream_port> example: --mcast_upstream_port eth1',
        default='eth1')
    parser.add_argument(
        '--mcast_side_b_min_bps',
        help='''--side_b_min_bps or --download_min_bps, requested upstream min tx rate, comma separated list for multiple iterations.  Default 256000
                When runnign with tcp/udp and mcast will use this value''',
        default="256000")
    parser.add_argument(
        '--mcast_tos',
        help='--tos:  Support different ToS settings: BK,BE,VI,VO,numeric',
        default="BE")
    parser.add_argument(
        '--mcast_device_list',
        action='append',
        help='Specify the Resource IDs for real clients. Accepts a comma-separated list (e.g., 1.11,1.95,1.360).'
    )
    #mcast pass fail value
    parser.add_argument("--mcast_expected_passfail_value", help="Specify the expected number of urls", default=None)
    parser.add_argument("--mcast_device_csv_name", type=str, help='Specify the csv name to store expected url values', default=None)
    #mcast with groups and profile configuration
    parser.add_argument('--mcast_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    parser.add_argument('--mcast_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    parser.add_argument('--mcast_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')

    #mcast configuration with --config
    parser.add_argument("--mcast_config", action="store_true", help="Specify for configuring the devices")
    parser.add_argument('--mcast_ssid', help='WiFi SSID for script objects to associate to')
    parser.add_argument('--mcast_passwd', '--mcast_password', '--mcast_key', default="[BLANK]", help='WiFi passphrase/password/key')
    parser.add_argument('--mcast_security', help='WiFi Security protocol: < open | wep | wpa | wpa2 | wpa3 >', default="open")
    #Optional mcast config args
    parser.add_argument("--mcast_eap_method", type=str, default='DEFAULT', help="Specify the EAP method for authentication.")
    parser.add_argument("--mcast_eap_identity", type=str, default='', help="Specify the EAP identity for authentication.")
    parser.add_argument("--mcast_ieee8021x", action="store_true", help='Enables 802.1X enterprise authentication for test stations.')
    parser.add_argument("--mcast_ieee80211u", action="store_true", help='Enables IEEE 802.11u (Hotspot 2.0) support.')
    parser.add_argument("--mcast_ieee80211w", type=int, default=1, help='Enables IEEE 802.11w (Management Frame Protection) support.')
    parser.add_argument("--mcast_enable_pkc", action="store_true", help='Enables pkc support.')
    parser.add_argument("--mcast_bss_transition", action="store_true", help='Enables BSS transition support.')
    parser.add_argument("--mcast_power_save", action="store_true", help='Enables power-saving features.')
    parser.add_argument("--mcast_disable_ofdma", action="store_true", help='Disables OFDMA support.')
    parser.add_argument("--mcast_roam_ft_ds", action="store_true", help='Enables fast BSS transition (FT) support')
    parser.add_argument("--mcast_key_management", type=str, default='DEFAULT', help='Specify the key management method (e.g., WPA-PSK, WPA-EAP')
    parser.add_argument("--mcast_pairwise", type=str, default='NA')
    parser.add_argument("--mcast_private_key", type=str, default='NA', help='Specify EAP private key certificate file.')
    parser.add_argument("--mcast_ca_cert", type=str, default='NA', help='Specifiy the CA certificate file name')
    parser.add_argument("--mcast_client_cert", type=str, default='NA', help='Specify the client certificate file name')
    parser.add_argument("--mcast_pk_passwd", type=str, default='NA', help='Specify the password for the private key')
    parser.add_argument("--mcast_pac_file", type=str, default='NA', help='Specify the pac file name')
    # parser.add_argument('--mcast_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    # parser.add_argument('--mcast_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    # parser.add_argument('--mcast_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')
    parser.add_argument("--mcast_wait_time", type=int, help='Specify the maximum time to wait for Configuration', default=60)
    #YOUTUBE
    parser.add_argument('--yt_test',
                          action="store_true",
                          help='mcast_test consists')
    parser.add_argument('--yt_url', type=str, help='youtube url')
    parser.add_argument('--yt_duration', help='duration to run the test in sec')
    parser.add_argument('--yt_res', default='Auto', help="to set resolution to  144p,240p,720p")
    # parser.add_argument('--yt_upstream_port', type=str, help='Specify The Upstream Port name or IP address', required=True)
    parser.add_argument('--yt_device_list', help='Specify the real device ports seperated by comma')
    #mcast pass fail value
    parser.add_argument("--yt_expected_passfail_value", help="Specify the expected number of urls", default=None)
    parser.add_argument("--yt_device_csv_name", type=str, help='Specify the csv name to store expected url values', default=None)
    #yt with groups and profile configuration
    parser.add_argument('--yt_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    parser.add_argument('--yt_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    parser.add_argument('--yt_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')

    #yt configuration with --config
    parser.add_argument("--yt_config", action="store_true", help="Specify for configuring the devices")
    parser.add_argument('--yt_ssid', help='WiFi SSID for script objects to associate to')
    parser.add_argument('--yt_passwd', '--yt_password', '--yt_key', default="[BLANK]", help='WiFi passphrase/password/key')
    parser.add_argument('--yt_security', help='WiFi Security protocol: < open | wep | wpa | wpa2 | wpa3 >', default="open")
    #Optional yt config args
    parser.add_argument("--yt_eap_method", type=str, default='DEFAULT', help="Specify the EAP method for authentication.")
    parser.add_argument("--yt_eap_identity", type=str, default='', help="Specify the EAP identity for authentication.")
    parser.add_argument("--yt_ieee8021x", action="store_true", help='Enables 802.1X enterprise authentication for test stations.')
    parser.add_argument("--yt_ieee80211u", action="store_true", help='Enables IEEE 802.11u (Hotspot 2.0) support.')
    parser.add_argument("--yt_ieee80211w", type=int, default=1, help='Enables IEEE 802.11w (Management Frame Protection) support.')
    parser.add_argument("--yt_enable_pkc", action="store_true", help='Enables pkc support.')
    parser.add_argument("--yt_bss_transition", action="store_true", help='Enables BSS transition support.')
    parser.add_argument("--yt_power_save", action="store_true", help='Enables power-saving features.')
    parser.add_argument("--yt_disable_ofdma", action="store_true", help='Disables OFDMA support.')
    parser.add_argument("--yt_roam_ft_ds", action="store_true", help='Enables fast BSS transition (FT) support')
    parser.add_argument("--yt_key_management", type=str, default='DEFAULT', help='Specify the key management method (e.g., WPA-PSK, WPA-EAP')
    parser.add_argument("--yt_pairwise", type=str, default='NA')
    parser.add_argument("--yt_private_key", type=str, default='NA', help='Specify EAP private key certificate file.')
    parser.add_argument("--yt_ca_cert", type=str, default='NA', help='Specifiy the CA certificate file name')
    parser.add_argument("--yt_client_cert", type=str, default='NA', help='Specify the client certificate file name')
    parser.add_argument("--yt_pk_passwd", type=str, default='NA', help='Specify the password for the private key')
    parser.add_argument("--yt_pac_file", type=str, default='NA', help='Specify the pac file name')
    # parser.add_argument('--yt_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    # parser.add_argument('--yt_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    # parser.add_argument('--yt_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')
    parser.add_argument("--yt_wait_time", type=int, help='Specify the maximum time to wait for Configuration', default=60)
    #real browser
    parser.add_argument('--rb_test',
                          action="store_true",
                          help='mcast_test consists')
    parser.add_argument("--rb_url", default="https://google.com", help='specify the url you want to test on')
    parser.add_argument('--rb_duration', type=str, help='time to run traffic')
    parser.add_argument('--rb_device_list', type=str, help='provide resource_ids of android devices. for instance: "10,12,14"')
    parser.add_argument('--rb_webgui_incremental', '--rb_incremental_capacity', help="Specify the incremental values <1,2,3..>", dest='webgui_incremental', type=str)
    parser.add_argument('--rb_incremental', help="to add incremental capacity to run the test", action='store_true')
    #mcast pass fail value
    parser.add_argument("--rb_expected_passfail_value", help="Specify the expected number of urls", default=None)
    parser.add_argument("--rb_device_csv_name", type=str, help='Specify the csv name to store expected url values', default=None)
    #rb with groups and profile configuration
    parser.add_argument('--rb_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    parser.add_argument('--rb_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    parser.add_argument('--rb_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')

    #rb configuration with --config
    parser.add_argument("--rb_config", action="store_true", help="Specify for configuring the devices")
    parser.add_argument('--rb_ssid', help='WiFi SSID for script objects to associate to')
    parser.add_argument('--rb_passwd', '--rb_password', '--rb_key', default="[BLANK]", help='WiFi passphrase/password/key')
    parser.add_argument('--rb_security', help='WiFi Security protocol: < open | wep | wpa | wpa2 | wpa3 >', default="open")
    #Optional rb config args
    parser.add_argument("--rb_eap_method", type=str, default='DEFAULT', help="Specify the EAP method for authentication.")
    parser.add_argument("--rb_eap_identity", type=str, default='', help="Specify the EAP identity for authentication.")
    parser.add_argument("--rb_ieee80211", action="store_true", help='Enables 802.1X enterprise authentication for test stations.')
    parser.add_argument("--rb_ieee80211u", action="store_true", help='Enables IEEE 802.11u (Hotspot 2.0) support.')
    parser.add_argument("--rb_ieee80211w", type=int, default=1, help='Enables IEEE 802.11w (Management Frame Protection) support.')
    parser.add_argument("--rb_enable_pkc", action="store_true", help='Enables pkc support.')
    parser.add_argument("--rb_bss_transition", action="store_true", help='Enables BSS transition support.')
    parser.add_argument("--rb_power_save", action="store_true", help='Enables power-saving features.')
    parser.add_argument("--rb_disable_ofdma", action="store_true", help='Disables OFDMA support.')
    parser.add_argument("--rb_roam_ft_ds", action="store_true", help='Enables fast BSS transition (FT) support')
    parser.add_argument("--rb_key_management", type=str, default='DEFAULT', help='Specify the key management method (e.g., WPA-PSK, WPA-EAP')
    parser.add_argument("--rb_pairwise", type=str, default='NA')
    parser.add_argument("--rb_private_key", type=str, default='NA', help='Specify EAP private key certificate file.')
    parser.add_argument("--rb_ca_cert", type=str, default='NA', help='Specifiy the CA certificate file name')
    parser.add_argument("--rb_client_cert", type=str, default='NA', help='Specify the client certificate file name')
    parser.add_argument("--rb_pk_passwd", type=str, default='NA', help='Specify the password for the private key')
    parser.add_argument("--rb_pac_file", type=str, default='NA', help='Specify the pac file name')
    # parser.add_argument('--rb_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    # parser.add_argument('--rb_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    # parser.add_argument('--rb_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')
    parser.add_argument("--rb_wait_time", type=int, help='Specify the maximum time to wait for Configuration', default=60)
    #zoom
    parser.add_argument('--zoom_test',
                          action="store_true",
                          help='mcast_test consists')
    parser.add_argument('--zoom_duration', type=int, help="Duration of the Zoom meeting in minutes")
    parser.add_argument('--zoom_signin_email', type=str, help="Sign-in email")
    parser.add_argument('--zoom_signin_passwd', type=str, help="Sign-in password")
    parser.add_argument('--zoom_participants', type=int, help="no of participanrs")
    parser.add_argument('--zoom_audio', action='store_true')
    parser.add_argument('--zoom_video', action='store_true')
    parser.add_argument('--zoom_device_list', help="resources participated in the test")
    parser.add_argument('--zoom_host', help="Host of the test")
    #zoom config args
    parser.add_argument("--zoom_expected_passfail_value", help="Specify the expected number of urls", default=None)
    parser.add_argument("--zoom_device_csv_name", type=str, help='Specify the csv name to store expected url values', default=None)
    #zoom with groups and profile configuration
    parser.add_argument('--zoom_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    parser.add_argument('--zoom_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    parser.add_argument('--zoom_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')

    #zoom configuration with --config
    parser.add_argument("--zoom_config", action="store_true", help="Specify for configuring the devices")
    parser.add_argument('--zoom_ssid', help='WiFi SSID for script objects to associate to')
    parser.add_argument('--zoom_passwd', '--zoom_password', '--zoom_key', default="[BLANK]", help='WiFi passphrase/password/key')
    parser.add_argument('--zoom_security', help='WiFi Security protocol: < open | wep | wpa | wpa2 | wpa3 >', default="open")
    #Optional zoom config args
    parser.add_argument("--zoom_eap_method", type=str, default='DEFAULT', help="Specify the EAP method for authentication.")
    parser.add_argument("--zoom_eap_identity", type=str, default='', help="Specify the EAP identity for authentication.")
    parser.add_argument("--zoom_ieee8021x", action="store_true", help='Enables 802.1X enterprise authentication for test stations.')
    parser.add_argument("--zoom_ieee80211u", action="store_true", help='Enables IEEE 802.11u (Hotspot 2.0) support.')
    parser.add_argument("--zoom_ieee80211w", type=int, default=1, help='Enables IEEE 802.11w (Management Frame Protection) support.')
    parser.add_argument("--zoom_enable_pkc", action="store_true", help='Enables pkc support.')
    parser.add_argument("--zoom_bss_transition", action="store_true", help='Enables BSS transition support.')
    parser.add_argument("--zoom_power_save", action="store_true", help='Enables power-saving features.')
    parser.add_argument("--zoom_disable_ofdma", action="store_true", help='Disables OFDMA support.')
    parser.add_argument("--zoom_roam_ft_ds", action="store_true", help='Enables fast BSS transition (FT) support')
    parser.add_argument("--zoom_key_management", type=str, default='DEFAULT', help='Specify the key management method (e.g., WPA-PSK, WPA-EAP')
    parser.add_argument("--zoom_pairwise", type=str, default='NA')
    parser.add_argument("--zoom_private_key", type=str, default='NA', help='Specify EAP private key certificate file.')
    parser.add_argument("--zoom_ca_cert", type=str, default='NA', help='Specifiy the CA certificate file name')
    parser.add_argument("--zoom_client_cert", type=str, default='NA', help='Specify the client certificate file name')
    parser.add_argument("--zoom_pk_passwd", type=str, default='NA', help='Specify the password for the private key')
    parser.add_argument("--zoom_pac_file", type=str, default='NA', help='Specify the pac file name')
    # parser.add_argument('--zoom_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    # parser.add_argument('--zoom_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    # parser.add_argument('--zoom_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')
    parser.add_argument("--zoom_wait_time", type=int, help='Specify the maximum time to wait for Configuration', default=60)
    # #yt
    # parser.add_argument('--yt_test',
    #                       action="store_true",
    #                       help='mcast_test consists')
    # parser.add_argument('--yt_url', type=str, help='youtube url')
    # parser.add_argument('--yt_duration', type=int, help='duration to run the test in sec')
    # parser.add_argument('--yt_res', default='Auto', help="to set resolution to  144p,240p,720p")
    # parser.add_argument('--yt_resources', help='Specify the real device ports seperated by comma')

    # #yt_config
    # parser.add_argument("--yt_expected_passfail_value", help="Specify the expected number of urls", default=None)
    # parser.add_argument("--yt_device_csv_name", type=str, help='Specify the csv name to store expected url values', default=None)
    # #yt with groups and profile configuration
    # parser.add_argument('--yt_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    # parser.add_argument('--yt_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    # parser.add_argument('--yt_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')

    # #yt configuration with --config
    # parser.add_argument("--yt_config", action="store_true", help="Specify for configuring the devices")
    # parser.add_argument('--yt_ssid', help='WiFi SSID for script objects to associate to')
    # parser.add_argument('--yt_passwd', '--yt_password', '--yt_key', default="[BLANK]", help='WiFi passphrase/password/key')
    # parser.add_argument('--yt_security', help='WiFi Security protocol: < open | wep | wpa | wpa2 | wpa3 >', default="open")
    # #Optional yt config args
    # parser.add_argument("--yt_eap_method", type=str, default='DEFAULT', help="Specify the EAP method for authentication.")
    # parser.add_argument("--yt_eap_identity", type=str, default='', help="Specify the EAP identity for authentication.")
    # parser.add_argument("--yt_ieee8021x", action="store_true", help='Enables 802.1X enterprise authentication for test stations.')
    # parser.add_argument("--yt_ieee80211u", action="store_true", help='Enables IEEE 802.11u (Hotspot 2.0) support.')
    # parser.add_argument("--yt_ieee80211w", type=int, default=1, help='Enables IEEE 802.11w (Management Frame Protection) support.')
    # parser.add_argument("--yt_enable_pkc", action="store_true", help='Enables pkc support.')
    # parser.add_argument("--yt_bss_transition", action="store_true", help='Enables BSS transition support.')
    # parser.add_argument("--yt_power_save", action="store_true", help='Enables power-saving features.')
    # parser.add_argument("--yt_disable_ofdma", action="store_true", help='Disables OFDMA support.')
    # parser.add_argument("--yt_roam_ft_ds", action="store_true", help='Enables fast BSS transition (FT) support')
    # parser.add_argument("--yt_key_management", type=str, default='DEFAULT', help='Specify the key management method (e.g., WPA-PSK, WPA-EAP')
    # parser.add_argument("--yt_pairwise", type=str, default='NA')
    # parser.add_argument("--yt_private_key", type=str, default='NA', help='Specify EAP private key certificate file.')
    # parser.add_argument("--yt_ca_cert", type=str, default='NA', help='Specifiy the CA certificate file name')
    # parser.add_argument("--yt_client_cert", type=str, default='NA', help='Specify the client certificate file name')
    # parser.add_argument("--yt_pk_passwd", type=str, default='NA', help='Specify the password for the private key')
    # parser.add_argument("--yt_pac_file", type=str, default='NA', help='Specify the pac file name')
    # # parser.add_argument('--yt_file_name', type=str, help='Specify the file name containing group details. Example:file1')
    # # parser.add_argument('--yt_group_name', type=str, help='Specify the groups name that contains a list of devices. Example: group1,group2')
    # # parser.add_argument('--yt_profile_name', type=str, help='Specify the profile name to apply configurations to the devices.')
    # parser.add_argument("--yt_wait_time", type=int, help='Specify the maximum time to wait for Configuration', default=60)


    args = parser.parse_args()
    args_dict = vars(args)
    print('argsss',args_dict)
    # exit(0)
    validate_args(args_dict)
    candela_apis = Candela(ip=args.mgr, port=args.mgr_port)
    candela_apis.misc_clean_up(layer3=True,layer4=True,generic=True)
    print(args)
    test_map = {
    "ping_test":   (run_ping_test, "PING TEST"),
    "http_test":   (run_http_test, "HTTP TEST"),
    "ftp_test":    (run_ftp_test, "FTP TEST"),
    "qos_test":    (run_qos_test, "QoS TEST"),
    "vs_test":     (run_vs_test, "VIDEO STREAMING TEST"),
    "thput_test":  (run_thput_test, "THROUGHPUT TEST"),
    "mcast_test":  (run_mcast_test, "MULTICAST TEST"),
    "yt_test":     (run_yt_test, "YOUTUBE TEST"),
    "rb_test":     (run_rb_test, "REAL BROWSER TEST"),
    "zoom_test":   (run_zoom_test, "ZOOM TEST"),
    }

    # threads = []

    # if args.ping_test:
    #     threads.append(threading.Thread(target=run_test_safe(run_ping_test, "PING TEST", args, candela_apis)))

    # if args.http_test:
    #     threads.append(threading.Thread(target=run_test_safe(run_http_test, "HTTP TEST", args, candela_apis)))

    # if args.ftp_test:
    #     threads.append(threading.Thread(target=run_test_safe(run_ftp_test, "FTP TEST", args, candela_apis)))

    # if args.qos_test:
    #     threads.append(threading.Thread(target=run_test_safe(run_qos_test, "QoS TEST", args, candela_apis)))

    # if args.vs_test:
    #     threads.append(threading.Thread(target=run_test_safe(run_vs_test, "VIDEO STREAMING TEST", args, candela_apis)))

    # if args.thput_test:
    #     threads.append(threading.Thread(target=run_test_safe(run_thput_test, "THROUGHPUT TEST", args, candela_apis)))

    # if args.mcast_test:
    #     threads.append(threading.Thread(target=run_test_safe(run_mcast_test, "MULTICAST TEST", args, candela_apis)))

    # if args.yt_test:
    #     threads.append(threading.Thread(target=run_test_safe(run_yt_test, "YOUTUBE TEST", args, candela_apis)))

    # if args.rb_test:
    #     threads.append(threading.Thread(target=run_test_safe(run_rb_test, "REAL BROWSER TEST", args, candela_apis)))

    # if args.zoom_test:
    #     threads.append(threading.Thread(target=run_test_safe(run_zoom_test, "ZOOM TEST", args, candela_apis)))
    if not args.series_tests and not args.parallel_tests:
        logger.error("Please provide tests cases --parallel_tests or --series_tests")
        logger.info(f"availbe tests are {test_map.keys()}")
        exit(0)

    flag=1
    if args.series_tests:
        tests_to_run_series = args.series_tests.split(',')
        for test in tests_to_run_series:
            if test not in test_map:
                logger.error(f"{test} is not availble in test suite")
                flag = 0
    if args.parallel_tests:
        tests_to_run_parallel = args.parallel_tests.split(',')
        for test in tests_to_run_parallel:
            if test not in test_map:
                logger.error(f"{test} is not availble in test suite")
                flag = 0


    if not flag:
        logger.info(f"availble tests are {test_map.keys()}")
        exit(0)
    if args.parallel_tests and (len(tests_to_run_parallel) != len(set(tests_to_run_parallel))):
        logger.error("in -parallel dont specify duplicate tests")
        exit(0)

    if args.series_tests or args.parallel_tests:
        series_threads = []
        parallel_threads = []
        
        # Process series tests
        if args.series_tests:
            ordered_series_tests = args.series_tests.split(',')
            for idx, test_name in enumerate(ordered_series_tests):
                test_name = test_name.strip().lower()
                if test_name in test_map:
                    func, label = test_map[test_name]
                    series_threads.append(threading.Thread(
                        target=run_test_safe(func, f"{label} [Series {idx+1}]", args, candela_apis)
                    ))
                else:
                    print(f"Warning: Unknown test '{test_name}' in --series_tests")
        
        # Process parallel tests
        if args.parallel_tests:
            ordered_parallel_tests = args.parallel_tests.split(',')
            for idx, test_name in enumerate(ordered_parallel_tests):
                test_name = test_name.strip().lower()
                if test_name in test_map:
                    func, label = test_map[test_name]
                    parallel_threads.append(threading.Thread(
                        target=run_test_safe(func, f"{label} [Parallel {idx+1}]", args, candela_apis)
                    ))
                else:
                    print(f"Warning: Unknown test '{test_name}' in --parallel_tests")
        
        # Execute based on order priority
        if args.order_priority == 'series':
            # candela_apis.misc_clean_up(layer3=True,layer4=True,generic=True)
            # Run series tests first (one at a time)
            for t in series_threads:
                t.start()
                t.join()
            
            # Then run parallel tests
            if len(parallel_threads) != 0:
                candela_apis.misc_clean_up(layer3=True,layer4=True,generic=True)
                print('starting parallel tests.......')
                time.sleep(20)

            for t in parallel_threads:
                t.start()
            for t in parallel_threads:
                t.join()
        else:
            # candela_apis.misc_clean_up(layer3=True,layer4=True,generic=True)
            # Run parallel tests first
            for t in parallel_threads:
                t.start()
            for t in parallel_threads:
                t.join()
            # candela_apis.misc_clean_up(layer3=True,layer4=True,generic=True)
            # Then run series tests (one at a time)
            if len(series_threads) != 0:
                candela_apis.misc_clean_up(layer3=True,layer4=True,generic=True)
                print('starting Series tests.......')
                time.sleep(20)
            for t in series_threads:
                t.start()
                t.join()
                # candela_apis.misc_clean_up(layer3=True,layer4=True,generic=True)
    else:
        logger.error("provide either --paralell_tests or --series_tests")
        exit(1)
    candela_apis.misc_clean_up(layer3=True,layer4=True,generic=True)
    log_file = save_logs()
    print(f"Logs saved to: {log_file}")
    
    # You can also access the test results dataframe:
    print("\nTest Results Summary:")
    print(test_results_df)


    # threads = []

    # if args.tests:
    #     ordered_tests = args.tests.split(',')

    #     for idx, test_name in enumerate(ordered_tests):
    #         test_name = test_name.strip().lower()

    #         if test_name in test_map:
    #             func, label = test_map[test_name]
    #             threads.append(threading.Thread(
    #                 target=run_test_safe(func, f"{label} [{idx+1}]", args, candela_apis)
    #             ))
    #         else:
    #             print(f"Warning: Unknown test '{test_name}' in --test_order")

    # if args.parallel:
    #     for t in threads:
    #         t.start()
    #     for t in threads:
    #         t.join()
    # else:
    #     for t in threads:
    #         t.start()
    #         t.join()


# def log(line):
#     logger.info(line)
#     LOG_BUFFER.append(line)

# def save_log_to_file(test_name):
#     timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
#     base_dir = Path(__file__).parent / "base_class_logs"
#     base_dir.mkdir(parents=True, exist_ok=True)
#     file_path = base_dir / f"{test_name}_{timestamp}.txt"

#     with open(file_path, "w", encoding="utf-8") as f:
#         f.write("\n".join(LOG_BUFFER))

#     print(f"Log saved to {file_path}")


# def run_test_safe(test_func, test_name, args, candela_apis):
#     def wrapper():
#         try:
#             result = test_func(args, candela_apis)
#             if not result:
#                 log(f"{test_name} FAILED")
#             else:
#                 log(f"{test_name} PASSED")
#         except SystemExit as e:
#             log(f"{test_name} exited with code {e.code}")
#             save_log_to_file(test_name)
#         except Exception:
#             log(f"{test_name} crashed unexpectedly:")
#             log("Traceback (most recent call last):")
#             tb_lines = traceback.format_exc().splitlines()
#             for line in tb_lines:
#                 log(line)
#             save_log_to_file(test_name)
#     return wrapper

def run_test_safe(test_func, test_name, args, candela_apis):
    global error_logs
    global test_results_df
    
    def wrapper():
        global error_logs
        global test_results_df
        
        try:
            result = test_func(args, candela_apis)
            if not result:
                status = "NOT EXECUTED"
                logger.error(f"{test_name} NOT EXECUTED")
            else:
                status = "EXECUTED"
                logger.info(f"{test_name} EXECUTED")
                
            # Update the dataframe with test result
            test_results_df.loc[len(test_results_df)] = [test_name, status]
            
        except SystemExit as e:
            if e.code != 0:
                status = "NOT EXECUTED"
            else:
                status = "EXECUTED"
            error_msg = f"{test_name} exited with code {e.code}\n"
            logger.error(error_msg)
            error_logs += error_msg
            test_results_df.loc[len(test_results_df)] = [test_name, status]
            
        except Exception as e:
            status = "NOT EXECUTED"
            error_msg = f"{test_name} crashed unexpectedly\n"
            logger.exception(error_msg)
            tb_str = traceback.format_exc()
            traceback.print_exc()
            full_error = error_msg + tb_str + "\n"
            error_logs += full_error
            test_results_df.loc[len(test_results_df)] = [test_name, status]
            
    return wrapper

def save_logs():
    """Save accumulated error logs to a timestamped file in base_class_logs directory"""
    global error_logs
    
        
    # Create directory if it doesn't exist
    log_dir = "base_class_logs"
    os.makedirs(log_dir, exist_ok=True)
    
    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{log_dir}/test_logs_{timestamp}.txt"
    
    # Write logs to file
    with open(log_filename, 'w') as f:
        f.write(error_logs)
        
    logger.info(f"Test logs saved to {log_filename}")
    return log_filename

def run_ping_test(args, candela_apis):
    return candela_apis.run_ping_test(
        real=True,
        target=args.ping_target,
        ping_interval=args.ping_interval,
        ping_duration=args.ping_duration,
        use_default_config=False if args.ping_config else True,
        dev_list=args.ping_device_list,
        expected_passfail_value=args.ping_expected_passfail_value,
        device_csv_name=args.ping_device_csv_name,
        file_name=args.ping_file_name,
        group_name=args.ping_group_name,
        profile_name=args.ping_profile_name,
        ssid=args.ping_ssid,
        passwd=args.ping_passwd,
        security=args.ping_security,
        eap_method=args.ping_eap_method,
        eap_identity=args.ping_eap_identity,
        ieee8021x=args.ping_ieee8021x,
        ieee80211u=args.ping_ieee80211u,
        ieee80211w=args.ping_ieee80211w,
        enable_pkc=args.ping_enable_pkc,
        bss_transition=args.ping_bss_transition,
        power_save=args.ping_power_save,
        disable_ofdma=args.ping_disable_ofdma,
        roam_ft_ds=args.ping_roam_ft_ds,
        key_management=args.ping_key_management,
        pairwise=args.ping_pairwise,
        private_key=args.ping_private_key,
        ca_cert=args.ping_ca_cert,
        client_cert=args.ping_client_cert,
        pk_passwd=args.ping_pk_passwd,
        pac_file=args.ping_pac_file,
        wait_time=args.ping_wait_time
    )

def run_http_test(args, candela_apis):
    return candela_apis.run_http_test(
        upstream_port=args.upstream_port,
        bands=args.http_bands,
        duration=args.http_duration,
        file_size=args.http_file_size,
        device_list=args.http_device_list,
        expected_passfail_value=args.http_expected_passfail_value,
        device_csv_name=args.http_device_csv_name,
        file_name=args.http_file_name,
        group_name=args.http_group_name,
        profile_name=args.http_profile_name,
        config=args.http_config,
        ssid=args.http_ssid,
        passwd=args.http_passwd,
        security=args.http_security,
        eap_method=args.http_eap_method,
        eap_identity=args.http_eap_identity,
        ieee8021x=args.http_ieee8021x,
        ieee80211u=args.http_ieee80211u,
        ieee80211w=args.http_ieee80211w,
        enable_pkc=args.http_enable_pkc,
        bss_transition=args.http_bss_transition,
        power_save=args.http_power_save,
        disable_ofdma=args.http_disable_ofdma,
        roam_ft_ds=args.http_roam_ft_ds,
        key_management=args.http_key_management,
        pairwise=args.http_pairwise,
        private_key=args.http_private_key,
        ca_cert=args.http_ca_cert,
        client_cert=args.http_client_cert,
        pk_passwd=args.http_pk_passwd,
        pac_file=args.http_pac_file,
        wait_time=args.http_wait_time
    )

def run_ftp_test(args, candela_apis):
    return candela_apis.run_ftp_test(
        device_list=args.ftp_device_list,
        file_sizes=[args.ftp_file_size],
        traffic_duration=args.ftp_duration,
        bands=args.ftp_bands,
        expected_passfail_value=args.ftp_expected_passfail_value,
        device_csv_name=args.ftp_device_csv_name,
        file_name=args.ftp_file_name,
        group_name=args.ftp_group_name,
        profile_name=args.ftp_profile_name,
        config=args.ftp_config,
        ssid=args.ftp_ssid,
        passwd=args.ftp_passwd,
        security=args.ftp_security,
        eap_method=args.ftp_eap_method,
        eap_identity=args.ftp_eap_identity,
        ieee8021x=args.ftp_ieee8021x,
        ieee80211u=args.ftp_ieee80211u,
        ieee80211w=args.ftp_ieee80211w,
        enable_pkc=args.ftp_enable_pkc,
        bss_transition=args.ftp_bss_transition,
        power_save=args.ftp_power_save,
        disable_ofdma=args.ftp_disable_ofdma,
        roam_ft_ds=args.ftp_roam_ft_ds,
        key_management=args.ftp_key_management,
        pairwise=args.ftp_pairwise,
        private_key=args.ftp_private_key,
        ca_cert=args.ftp_ca_cert,
        client_cert=args.ftp_client_cert,
        pk_passwd=args.ftp_pk_passwd,
        pac_file=args.ftp_pac_file,
        wait_time=args.ftp_wait_time
    )

def run_qos_test(args, candela_apis):
    print("QOS_LIST",args.qos_device_list)
    return candela_apis.run_qos_test(
        upstream_port=args.upstream_port,
        test_duration=args.qos_duration,
        download=args.qos_download,
        upload=args.qos_upload,
        traffic_type=args.qos_traffic_type,
        tos=args.qos_tos,
        device_list=args.qos_device_list,
        expected_passfail_value=args.qos_expected_passfail_value,
        device_csv_name=args.qos_device_csv_name,
        file_name=args.qos_file_name,
        group_name=args.qos_group_name,
        profile_name=args.qos_profile_name,
        config=args.qos_config,
        ssid=args.qos_ssid,
        passwd=args.qos_passwd,
        security=args.qos_security,
        eap_method=args.qos_eap_method,
        eap_identity=args.qos_eap_identity,
        ieee8021x=args.qos_ieee8021x,
        ieee80211u=args.qos_ieee80211u,
        ieee80211w=args.qos_ieee80211w,
        enable_pkc=args.qos_enable_pkc,
        bss_transition=args.qos_bss_transition,
        power_save=args.qos_power_save,
        disable_ofdma=args.qos_disable_ofdma,
        roam_ft_ds=args.qos_roam_ft_ds,
        key_management=args.qos_key_management,
        pairwise=args.qos_pairwise,
        private_key=args.qos_private_key,
        ca_cert=args.qos_ca_cert,
        client_cert=args.qos_client_cert,
        pk_passwd=args.qos_pk_passwd,
        pac_file=args.qos_pac_file,
        wait_time=args.qos_wait_time
    )

def run_vs_test(args, candela_apis):
    return candela_apis.run_vs_test1(
        url=args.vs_url,
        media_source=args.vs_media_source,
        media_quality=args.vs_media_quality,
        duration=args.vs_duration,
        device_list=args.vs_device_list,
        expected_passfail_value=args.vs_expected_passfail_value,
        device_csv_name=args.vs_device_csv_name,
        file_name=args.vs_file_name,
        group_name=args.vs_group_name,
        profile_name=args.vs_profile_name,
        config=args.vs_config,
        ssid=args.vs_ssid,
        passwd=args.vs_passwd,
        encryp=args.vs_security,
        eap_method=args.vs_eap_method,
        eap_identity=args.vs_eap_identity,
        ieee8021x=args.vs_ieee8021x,
        ieee80211u=args.vs_ieee80211u,
        ieee80211w=args.vs_ieee80211w,
        enable_pkc=args.vs_enable_pkc,
        bss_transition=args.vs_bss_transition,
        power_save=args.vs_power_save,
        disable_ofdma=args.vs_disable_ofdma,
        roam_ft_ds=args.vs_roam_ft_ds,
        key_management=args.vs_key_management,
        pairwise=args.vs_pairwise,
        private_key=args.vs_private_key,
        ca_cert=args.vs_ca_cert,
        client_cert=args.vs_client_cert,
        pk_passwd=args.vs_pk_passwd,
        pac_file=args.vs_pac_file,
        wait_time=args.vs_wait_time,
        upstream_port=args.upstream_port
    )

def run_thput_test(args, candela_apis):
    if args.thput_do_interopability and args.thput_config:
        args.thput_default_config = False
        args.thput_config = False
    return candela_apis.run_throughput_test(
        upstream_port=args.upstream_port,
        test_duration=args.thput_test_duration,
        download=args.thput_download,
        upload=args.thput_upload,
        traffic_type=args.thput_traffic_type,
        device_list=args.thput_device_list,
        do_interopability=args.thput_do_interopability,
        default_config=args.thput_default_config,
        expected_passfail_value=args.thput_expected_passfail_value,
        device_csv_name=args.thput_device_csv_name,
        file_name=args.thput_file_name,
        group_name=args.thput_group_name,
        profile_name=args.thput_profile_name,
        config=args.thput_config,
        ssid=args.thput_ssid,
        passwd=args.thput_passwd,
        security=args.thput_security,
        eap_method=args.thput_eap_method,
        eap_identity=args.thput_eap_identity,
        ieee8021x=args.thput_ieee8021x,
        ieee80211u=args.thput_ieee80211u,
        ieee80211w=args.thput_ieee80211w,
        enable_pkc=args.thput_enable_pkc,
        bss_transition=args.thput_bss_transition,
        power_save=args.thput_power_save,
        disable_ofdma=args.thput_disable_ofdma,
        roam_ft_ds=args.thput_roam_ft_ds,
        key_management=args.thput_key_management,
        pairwise=args.thput_pairwise,
        private_key=args.thput_private_key,
        ca_cert=args.thput_ca_cert,
        client_cert=args.thput_client_cert,
        pk_passwd=args.thput_pk_passwd,
        pac_file=args.thput_pac_file,
        wait_time=args.thput_wait_time
    )

def run_mcast_test(args, candela_apis):
    return candela_apis.run_mc_test1(
        test_duration=args.mcast_test_duration,
        upstream_port=args.upstream_port,
        endp_type=args.mcast_endp_type,
        side_b_min_bps=args.mcast_side_b_min_bps,
        tos=args.mcast_tos,
        device_list=args.mcast_device_list,
        expected_passfail_value=args.mcast_expected_passfail_value,
        device_csv_name=args.mcast_device_csv_name,
        file_name=args.mcast_file_name,
        group_name=args.mcast_group_name,
        profile_name=args.mcast_profile_name,
        config=args.mcast_config,
        ssid=args.mcast_ssid,
        passwd=args.mcast_passwd,
        security=args.mcast_security,
        eap_method=args.mcast_eap_method,
        eap_identity=args.mcast_eap_identity,
        ieee8021x=args.mcast_ieee8021x,
        ieee80211u=args.mcast_ieee80211u,
        ieee80211w=args.mcast_ieee80211w,
        enable_pkc=args.mcast_enable_pkc,
        bss_transition=args.mcast_bss_transition,
        power_save=args.mcast_ieee8021x,
        disable_ofdma=args.mcast_disable_ofdma,
        roam_ft_ds=args.mcast_roam_ft_ds,
        key_management=args.mcast_key_management,
        pairwise=args.mcast_pairwise,
        private_key=args.mcast_private_key,
        ca_cert=args.mcast_ca_cert,
        client_cert=args.mcast_client_cert,
        pk_passwd=args.mcast_pk_passwd,
        pac_file=args.mcast_pac_file,
        wait_time=args.mcast_wait_time
    )

def run_yt_test(args, candela_apis):
    return candela_apis.run_yt_test(
        url=args.yt_url,
        duration=args.yt_duration,
        res=args.yt_res,
        upstream_port=args.upstream_port,
        resource_list=args.yt_device_list,
        expected_passfail_value=args.yt_expected_passfail_value,
        device_csv_name=args.yt_device_csv_name,
        file_name=args.yt_file_name,
        group_name=args.yt_group_name,
        profile_name=args.yt_profile_name,
        config=args.yt_config,
        ssid=args.yt_ssid,
        passwd=args.yt_passwd,
        encryp=args.yt_security,
        eap_method=args.yt_eap_method,
        eap_identity=args.yt_eap_identity,
        ieee8021x=args.yt_ieee8021x,
        ieee80211u=args.yt_ieee80211u,
        ieee80211w=args.yt_ieee80211w,
        enable_pkc=args.yt_enable_pkc,
        bss_transition=args.yt_bss_transition,
        power_save=args.yt_ieee8021x,
        disable_ofdma=args.yt_disable_ofdma,
        roam_ft_ds=args.yt_roam_ft_ds,
        key_management=args.yt_key_management,
        pairwise=args.yt_pairwise,
        private_key=args.yt_private_key,
        ca_cert=args.yt_ca_cert,
        client_cert=args.yt_client_cert,
        pk_passwd=args.yt_pk_passwd,
        pac_file=args.yt_pac_file
    )

def run_rb_test(args, candela_apis):
    return candela_apis.run_rb_test(
        url=args.rb_url,
        upstream_port=args.upstream_port,
        device_list=args.rb_device_list,
        expected_passfail_value=args.rb_expected_passfail_value,
        device_csv_name=args.rb_device_csv_name,
        file_name=args.rb_file_name,
        group_name=args.rb_group_name,
        profile_name=args.rb_profile_name,
        config=args.rb_config,
        ssid=args.rb_ssid,
        passwd=args.rb_passwd,
        encryp=args.rb_security,
        eap_method=args.rb_eap_method,
        eap_identity=args.rb_eap_identity,
        ieee80211=args.rb_ieee80211,
        ieee80211u=args.rb_ieee80211u,
        ieee80211w=args.rb_ieee80211w,
        enable_pkc=args.rb_enable_pkc,
        bss_transition=args.rb_bss_transition,
        power_save=args.rb_power_save,
        disable_ofdma=args.rb_disable_ofdma,
        roam_ft_ds=args.rb_roam_ft_ds,
        key_management=args.rb_key_management,
        pairwise=args.rb_pairwise,
        private_key=args.rb_private_key,
        ca_cert=args.rb_ca_cert,
        client_cert=args.rb_client_cert,
        pk_passwd=args.rb_pk_passwd,
        pac_file=args.rb_pac_file,
        wait_time=args.rb_wait_time,
        duration=args.rb_duration
    )

def run_zoom_test(args, candela_apis):
    return candela_apis.run_zoom_test(
        duration=args.zoom_duration,
        signin_email=args.zoom_signin_email,
        signin_passwd=args.zoom_signin_passwd,
        participants=args.zoom_participants,
        audio=args.zoom_audio,
        video=args.zoom_video,
        upstream_port=args.upstream_port,
        resource_list=args.zoom_device_list,
        zoom_host=args.zoom_host,
        expected_passfail_value=args.zoom_expected_passfail_value,
        device_csv_name=args.zoom_device_csv_name,
        file_name=args.zoom_file_name,
        group_name=args.zoom_group_name,
        profile_name=args.zoom_profile_name,
        config=args.zoom_config,
        ssid=args.zoom_ssid,
        passwd=args.zoom_passwd,
        encryp=args.zoom_security,
        eap_method=args.zoom_eap_method,
        eap_identity=args.zoom_eap_identity,
        ieee8021x=args.zoom_ieee8021x,
        ieee80211u=args.zoom_ieee80211u,
        ieee80211w=args.zoom_ieee80211w,
        enable_pkc=args.zoom_enable_pkc,
        bss_transition=args.zoom_bss_transition,
        power_save=args.zoom_power_save,
        disable_ofdma=args.zoom_disable_ofdma,
        roam_ft_ds=args.zoom_roam_ft_ds,
        key_management=args.zoom_key_management,
        pairwise=args.zoom_pairwise,
        private_key=args.zoom_private_key,
        ca_cert=args.zoom_ca_cert,
        client_cert=args.zoom_client_cert,
        pk_passwd=args.zoom_pk_passwd,
        pac_file=args.zoom_pac_file,
        wait_time=args.zoom_wait_time
    )
main()
