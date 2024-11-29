# python3 lf_interop_youtube.py --mgr 192.168.246.138 --url "https://youtu.be/BHACKCNDMW8?si=psTEUzrc77p38aU1" --duration 3 --debug --no_pre_cleanup

#!/usr/bin/env python3

"""
    NAME: lf_interop_youtube.py

    PURPOSE: lf_interop_youtube.py provides the available devices and allows the user to run YouTube on selected devices by specifying the video URL and duration.

    EXAMPLE-1:
    Command Line Interface to run YouTube with the specified URL and duration:
    python3 lf_interop_youtube.py --mgr 192.168.214.219 --url "https://youtu.be/BHACKCNDMW8?si=psTEUzrc77p38aU1" --duration 2 

        CASE-1:
        If the given duration is longer than the actual video duration, the video will loop.

        CASE-2:
        If the given duration is shorter than the actual video duration, the video will stop after the specified duration.

    EXAMPLE-2:
    Command Line Interface to run YouTube on multiple devices:
    python3 lf_interop_youtube.py --mgr 192.168.214.219 --url "https://youtu.be/BHACKCNDMW8?si=psTEUzrc77p38aU1" --duration 2 --resources "1.13,1.14..."

    EXAMPLE-3:
    Command Line Interface to run YouTube without pre-cleanup of existing cross-connections:
    python3 lf_interop_youtube.py --mgr 192.168.214.219 --url "https://youtu.be/BHACKCNDMW8?si=psTEUzrc77p38aU1" --duration 2 --no_pre_cleanup

    EXAMPLE-4:
    Command Line Interface to run YouTube without post-cleanup of cross-connections:
    python3 lf_interop_youtube.py --mgr 192.168.214.219 --url "https://youtu.be/BHACKCNDMW8?si=psTEUzrc77p38aU1" --duration 2 --no_post_cleanup

    SCRIPT CLASSIFICATION: Test

    NOTES:
    1. Use './lf_interop_youtube.py --help' to see command line usage and options.
    2. Always specify the duration in minutes (for example: --duration 3 indicates a duration of 3 minutes).
    3. If --resources are not given after passing the CLI, a list of available devices (laptops) will be displayed on the terminal.
    4. Enter the resource numbers separated by commas (,) in the resource argument.
    5. For --url, you can specify the YouTube URL (e.g., https://youtu.be/BHACKCNDMW8?si=psTEUzrc77p38aU1).

"""

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
import re


# Add necessary paths if not already included
if 'py-json' not in sys.path:
    #sys.path.append(os.path.join(os.path.abspath('..'), 'py-json'))
    #sys.path.append('/home/laxmi/Documents/lanforge-scripts/py-json/')
    sys.path.append('/home/lanforge/lanforge-scripts/py-json')
    

if 'py-scripts' not in sys.path:
    #sys.path.append('/home/agent11/Desktop/lanforge-scripts/py-scripts')
    #sys.path.append('/home/laxmi/Documents/lanforge-scripts/py-scripts/')
    sys.path.append('/home/lanforge/lanforge-scripts/py-scripts')





# Import LANforge-related modules
from lf_base_interop_profile import RealDevice
from datetime import datetime, timedelta
from lf_graph import lf_bar_graph_horizontal
from lf_graph import lf_bar_graph
from lf_report import lf_report

# Set up logging
logger = logging.getLogger(__name__)

# Import LF logger configuration module
lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")

# Ensure Python 3 compatibility
if sys.version_info[0] != 3:
    print("This script requires Python 3")
    exit(1)

# Import realm module
realm = importlib.import_module("py-json.realm")
Realm = realm.Realm

# Import base interop profile module
base = importlib.import_module('py-scripts.lf_base_interop_profile')
base_RealDevice = base.RealDevice

DeviceConfig = importlib.import_module("py-scripts.DeviceConfig")


class Youtube(Realm):
    """
    Class for automating YouTube streaming tests using LANforge.
    """
    def __init__(self,
                host = None,
                port = None,
                url = None,
                duration = 0,
                # resources = None,
                lanforge_password = 'lanforge',
                sta_list = None,
                do_webUI = False,
                ui_report_dir=None,
                debug = False,
                stats_api_response = {},
                resolution=None,
                ap_name=None,
                ssid=None,
                security=None,
                band=None,
                base_dir=None,
                test_name = None,
                

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
        super().__init__(lfclient_host=host,
                        lfclient_port=port)
        self.host = host
        self.lanforge_password = lanforge_password
        self.port = port 
        self.url = url
        self.duration = duration 
        # self.resources = resources
        self.lfclient_host = host
        self.lfclient_port = port
        self.debug = debug
        self.sta_list = sta_list
        self.real_sta_list = []
        self.real_sta_data_dict = {}
        self.linux = 0
        self.windows = 0
        self.mac = 0
        self.result_json = {}
        self.generic_endps_profile = self.new_generic_endp_profile()
        self.generic_endps_profile.type = 'youtube'
        self.generic_endps_profile.name_prefix = "yt"
        self.Devices = None
        self.start_time = ""
        self.stop_time = ""
        self.do_webUI = do_webUI
        self.ui_report_dir = ui_report_dir
        self.devices = base_RealDevice(manager_ip = self.host, selected_bands = [])
        self.device_names = []
        self.resolution=resolution
        self.ap_name=ap_name
        self.ssid=ssid
        self.security=security
        self.band=band
        self.start_time = None,
        self.est_end_time = None,
        self.end_time_webgui = []
        self.all_stop = False
        self.keys = []
        if(self.do_webUI):
            self.base_dir = os.path.abspath(os.path.join(ui_report_dir, "../../"))
            self.test_name = test_name
        
        self.mydatajson = {}
        self.final_data = None




    def cleanup(self):
        """
        Cleans up generic endpoints associated with the YouTube streaming test.

        This method iterates through the list of real stations (STA) and appends
        corresponding endpoint names to the `created_cx` and `created_endp` lists
        of the `generic_endps_profile`. It then performs cleanup operations on
        these endpoints and clears the lists afterwards.

        """
        # Append CX and endpoint names for each real station to be cleaned up
        for station in self.real_sta_list:
            self.generic_endps_profile.created_cx.append(
                'CX_yt-{}'.format(station))
            self.generic_endps_profile.created_endp.append(
                'yt-{}'.format(station))

        # Log cleanup initiation
        # Perform cleanup on generic endpoints
        self.generic_endps_profile.cleanup()
        # Clear the lists of created CX and endpoints after cleanup
        self.generic_endps_profile.created_cx = []
        self.generic_endps_profile.created_endp = []
        # Log cleanup completion
    

    def execute_youtube_test(self, duration, do_webUI):
        """
        Execute the YouTube test for monitoring 

        Args:
            duration (int): Duration of the test in minutes.
            do_webUI (bool): Flag to determine if the test is triggered from the web UI.
        """
        # Wait for 10 seconds before starting the test
        self.clear_previous_data()
    
        

        self.start_generic()
        time.sleep(5)

         # Initialize variables
        self.start_time = datetime.now()
        self.est_end_time = self.start_time + timedelta(minutes=duration, seconds=60)
        self.end_time_webgui = [False] * len(self.device_names)
        self.keys = self.generic_endps_profile.created_cx
        self.all_stop = False

        # Ensure initial data is fetched
        initial_data = self.get_data_from_api()
        while not initial_data:
            initial_data = self.get_data_from_api()
            time.sleep(1)

        # Monitoring loop
        while not self.all_stop:
            if do_webUI:
                stop_value = self.set_webUI_stop()
                if stop_value == "Completed":
                    break

            self._monitor_test(do_webUI)

            time.sleep(1)  # Adjust sleep time as needed

    
        logging.info("Duration ended. Stopping the test.")

        

    
    def _monitor_test(self, do_webUI):
        """
        Monitor the YouTube test execution and handle stop conditions.

        Args:
            do_webUI (bool): Flag to determine if the test is triggered from the web UI.
        """
        initial_data = self.get_data_from_api()
        if initial_data:
            for i in range(len(self.device_names)):
                stop_state = initial_data['result'].get(self.device_names[i], {}).get('stop', False)
                if stop_state:
                    self.end_time_webgui[i] = True
                if all(self.end_time_webgui) or datetime.now() >= self.est_end_time:
                    self.all_stop = True
                    return

            for i in range(len(self.device_names)):
                if not self.end_time_webgui[i]:
                    new_key = self.keys[i]
                    if new_key.startswith("CX_"):
                        new_key = self.keys[i][3:]
                    response = self.json_get(f'/generic/{new_key}')
                    if response['endpoint']['status'] in ['WAITING', 'Stopped']:
                        self.end_time_webgui[i] = True
        
        
    def check_tab_exists(self):
        """
        Checks if the 'generic' tab exists by making a JSON GET request.

        Returns:
        - True if the 'generic' tab exists (response is not None).
        - False if the 'generic' tab does not exist (response is None).
        """
        # Make a JSON GET request to check the existence of the 'generic' tab
        response = self.json_get("generic")
        # Check if the response is None (indicating the tab does not exist)
        if response is None:
            return False
        else:
            return True

    def create_generic_endp(self,query_resources):
        """
        Creates generic endpoints for the specified resources.
        Args:
        - query_resources (list): List of resources to create endpoints for.
        Steps:
        1. Retrieves information about all resources using a JSON GET request.
        2. Matches user-specified resources with available resources and retrieves necessary details (eid, ctrl-ip, hostname).
        3. Retrieves port information using a JSON GET request.
        4. Matches ports associated with retrieved resources and constructs a list of matching ports.
        5. Creates generic endpoints using the retrieved ports and other parameters.
        """
        ports_list = []
        eid = ""
        resource_ip = ""
        user_resources = ['.'.join(item.split('.')[:2]) for item in self.real_sta_list]

        # Step 1: Retrieve information about all resources
        response = self.json_get("/resource/all")

        # Step 2: Match user-specified resources with available resources sequentially
        if user_resources:
            # Iterate through user_resources sequentially, processing each value only once
            for user_resource in user_resources:
                # Break loop if no more user_resources left to process
                if not user_resources:
                    break

                for key, value in response.items():
                    if key == "resources":
                        for element in value:
                            for resource_key, resource_values in element.items():
                                # Match the current user_resource
                                if resource_key == user_resource:
                                    eid = resource_values["eid"]
                                    resource_ip = resource_values['ctrl-ip']
                                    self.device_names.append(resource_values['hostname'])
                                    ports_list.append({'eid': eid, 'ctrl-ip': resource_ip})
                                    break
                            else:
                                # Continue outer loop only if no break occurred
                                continue
                            # Break if a match was found and processed
                            break
        #print("checking port list",ports_list)
        gen_ports_list = []
        self.mac_list = []
        self.rssi_list = []
        self.link_rate_list = []
        self.ssid_list = []
        # Step 3: Retrieve port information
        response_port = self.json_get("/port/all")

        # Step 4: Match ports associated with retrieved resources in the order of ports_list
        for port_entry in ports_list:
            # Extract the eid and ctrl-ip from the current ports_list entry
            expected_eid = port_entry['eid']
        

            # Iterate over the port interfaces to find a matching port
            for interface in response_port['interfaces']:
                for port, port_data in interface.items():
                    # Extract the first two segments of the port identifier to match with expected_eid
                    result = '.'.join(port.split('.')[:2])

                    # Check if the result matches the current expected eid from ports_list
                    if result == expected_eid:
                        gen_ports_list.append(port.split('.')[-1])
                        break  
                else:
                    continue
                break
    
        for port_entry in ports_list:
            # Extract the eid and ctrl-ip from the current ports_list entry
            expected_eid = port_entry['eid']
        

            # Iterate over the port interfaces to find a matching port
            for interface in response_port['interfaces']:
                for port, port_data in interface.items():
                    # Extract the first two segments of the port identifier to match with expected_eid
                    result = '.'.join(port.split('.')[:2])

                    # Check if the result matches the current expected eid from ports_list
                    if result == expected_eid and port_data["parent dev"] == 'wiphy0':
                        self.mac_list.append(port_data["mac"])
                        self.rssi_list.append(port_data["signal"])
                        self.link_rate_list.append(port_data["rx-rate"])
                        self.ssid_list.append(port_data["ssid"])

            
                        
                        break  
                else:
                    continue
                break
        

        #print("Checking gen_ports_list:", gen_ports_list)
        # print("checking mac list",mac_list)
        # print("checking rssi list",rssi_list)
        # print("checking link_rate_list",link_rate_list)

        # Create generic endpoints using the retrieved ports and other parameters
        self.real_sta_os_types = [self.real_sta_data_dict[real_sta_name]['ostype'] for real_sta_name in self.real_sta_data_dict]
        self.real_sta_hostname = [self.real_sta_data_dict[real_sta_name]['hostname'] for real_sta_name in self.real_sta_data_dict]

        # print("checking self.real_sta_os_types",self.real_sta_os_types)
        # print(self.real_sta_hostname)
        # print(gen_ports_list)

        self.new_port_list = [item.split('.')[2] for item in self.real_sta_list]
        
        if (self.generic_endps_profile.create(ports=query_resources, sleep_time=.5, real_client_os_types=self.real_sta_os_types,)):
            logging.info(f"=================================================================================================")
            logging.info('Real client generic endpoint creation completed.')
        else:
            logging.error('Real client generic endpoint creation failed.')
            exit(0)
        
        for i in range(0,len(self.real_sta_os_types)):
            if self.real_sta_os_types[i] == 'windows':
                cmd = "youtube_stream.bat --url %s --host %s --device_name %s --duration %s --res %s" % (self.url, self.lfclient_host, self.real_sta_hostname[i], self.duration,self.resolution)
                self.generic_endps_profile.set_cmd(self.generic_endps_profile.created_endp[i],cmd)
            elif self.real_sta_os_types[i] == 'linux':
                cmd = "su -l lanforge  ctyt.bash %s %s %s %s %s %s" % (self.new_port_list[i], self.url, self.lfclient_host, self.real_sta_hostname[i], self.duration,self.resolution)
                self.generic_endps_profile.set_cmd(self.generic_endps_profile.created_endp[i],cmd)
            
            elif self.real_sta_os_types[i] == 'macos':
                cmd = "sudo bash youtube_stream.bash --url %s --host %s --device_name %s --duration %s --res %s" % (self.url, self.lfclient_host, self.real_sta_hostname[i], self.duration,self.resolution )
                self.generic_endps_profile.set_cmd(self.generic_endps_profile.created_endp[i],cmd)
            
        

    def select_real_devices(self, real_devices, real_sta_list=None, base_interop_obj=None):
        final_device_list = []
        """
        Selects real devices for testing.

        Args:
        - real_devices (RealDevice): Instance of RealDevice containing devices information.
        - real_sta_list (list, optional): List of specific real station names to select for testing.
        - base_interop_obj (object, optional): Base interop object to set for Devices.

        Returns:
        - list: list of selected real station names for testing.

        Steps:
        1. If `real_sta_list` is not provided, queries and retrieves all user-defined real stations from `real_devices`.
        2. Otherwise, assigns the provided `real_sta_list` to `self.real_sta_list`.
        3. If `base_interop_obj` is provided, assigns it to `self.Devices`.
        4. Sorts `self.real_sta_list` based on the second part of each station name.
        5. Logs an error and exits if no real stations are selected for testing.
        6. Logs the selected real station names.
        7. Adds real station data to `self.real_sta_data_dict`.
        8. Tracks the number of selected devices (`android`, `windows`, `mac`, `linux`).
        

        """
        # Query and retrieve all user-defined real stations if `real_sta_list` is not provided
        if real_sta_list is None:
            self.real_sta_list, _, _ = real_devices.query_user()
        else:
            interface_data = self.json_get("/port/all")
            interfaces = interface_data["interfaces"]
            #print("checking interfaces",interfaces)
            final_device_list = []  # Initialize the list

            for device in real_sta_list:  # Iterate over devices in `real_sta_list` to preserve order
                for interface_dict in interfaces:  # Iterate through `interfaces`
                    for key, value in interface_dict.items():  # Iterate through items of each interface dictionary
                        # Check conditions for adding the device
                        if (
                            key.startswith(device)
                            and not value["phantom"]
                            and not value["down"]
                            and value["parent dev"] != ""
                        ):
                            final_device_list.append(key)  # Add to final_device_list in order
                            break  # Stop after finding the first match for the current device to maintain order

            self.real_sta_list = final_device_list

        # Assign `base_interop_obj` to `self.Devices` if provided
        if base_interop_obj is not None:
            self.Devices = base_interop_obj

        # Sort `self.real_sta_list` based on the second part of each station name
        #self.real_sta_list = sorted(self.real_sta_list, key=lambda x: int(x.split('.')[1]))

        # Log an error and exit if no real stations are selected for testing
        if (len(self.real_sta_list) == 0):
            logger.error('There are no real devices in this testbed. Aborting test')
            exit(0)

        # Log the selected real station names
        #logging.info('{}'.format(*self.real_sta_list))
        # # Add real station data to `self.real_sta_data_dict`
        for sta_name in self.real_sta_list:
            if sta_name not in real_devices.devices_data:
                logger.error('Real station not in devices data, ignoring it from testing')
                continue

            self.real_sta_data_dict[sta_name] = real_devices.devices_data[sta_name]

        # for device_id, device_data in real_devices.devices_data.items():
        #     print("============================================================================================================================")
        #     print("checking device data",device_data)
        #     print("checking whether this loop is iterating or not")
        #     stripped_eid = device_data.get("eid", "").strip()
        #     if stripped_eid in (sta_name.strip() for sta_name in self.real_sta_list):
        #         print("==================================================")
        #         print("checking device data",device_data)
        #         # Store the matching object in real_sta_data_dict
        #         self.real_sta_data_dict[stripped_eid] = device_data
        #         print("device found")
        #     else:
        #         # Log if a real station is not in the devices data
        #         logger.error(f"Real station {stripped_eid} not in devices data, ignoring it from testing")

        # Track the selected devices
        self.android = self.Devices.android
        self.windows = self.Devices.windows
        self.mac = self.Devices.mac
        self.linux = self.Devices.linux
        # Return the sorted list of selected real station names
        return self.real_sta_list

    def start_generic(self):
        """
        Starts the generic endpoints' connections and sets the start time.

        Steps:
        1. Starts the connections of generic endpoints using `self.generic_endps_profile.start_cx()`.
        2. Sets the start time (`self.start_time`) to the current datetime.

        """
        # Start the connections of generic endpoints
        self.generic_endps_profile.start_cx()
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
        #self.generic_endps_profile.stop_cx_specific(cx_name)
        self.generic_endps_profile.stop_cx()        
        # Set the stop time to the current datetime
        self.stop_time = datetime.now()
    
    def set_webUI_stop(self,):
        """
        Sets the status of the webUI test to 'Completed' in the runtime_ping_data.json file.

        Procedure Followed:
        1. Opens the runtime_ping_data.json file located in `self.ui_report_dir` for reading.
        2. Loads the JSON data from the file into the `data` variable.
        3. Checks if 'status' key exists in `data` and if its value is not 'Aborted'.
        - If conditions are met, updates 'status' to 'Completed' in `data`.
        4. Writes the updated `data` back to the runtime_ping_data.json file with proper formatting.

        Note:
        - This method assumes `self.ui_report_dir` contains the path to the directory where runtime_ping_data.json is located.
        """
        # Open runtime_ping_data.json file for reading
        file_path = self.ui_report_dir
        file_name = '/running_status.json'
        with open(file_path + file_name, 'r') as f:
            # Step 2: Load JSON data from file into 'data' variable
            data = json.load(f)
            return data['status']

           


    def get_data_from_api(self):
        """
        Retrieves YouTube streaming statistics from an API endpoint.
        Returns:
            dict or None: The fetched data if successful, None otherwise.
        """
        # List to store device names (file names)
        self.devices_list = []

        # Define the API endpoint URL
        url = f"http://{self.host}:5454/youtube_stats"
        
        # Send an HTTP GET request to fetch data from the API
        response = requests.get(url)
        if response.status_code == 200:
            self.data = response.json()
            result_data = self.data.get("result", {})
            #print(result_data)
            for device, device_data in result_data.items():
                stats = device_data.get("stats", {}).get("stats", {})
                timestamp = device_data.get("stats", {}).get("Timestamp", {})

                if device not in self.mydatajson:
                    self.mydatajson[device] = {}
                if "maxbufferhealth" not in self.mydatajson[device]:
                    self.mydatajson[device]["maxbufferhealth"] = "0.0"
                else:
                    if (float(stats.get("BufferHealth", "0.0")) > float(self.mydatajson[device]["maxbufferhealth"])):
                        self.mydatajson[device]["maxbufferhealth"] = stats.get("BufferHealth", "0.0")

                if "minbufferhealth" not in self.mydatajson[device]:
                    self.mydatajson[device]["minbufferhealth"] = "100000.0"
                else:
                    if (float(stats.get("BufferHealth", "100000.0")) < float(self.mydatajson[device]["minbufferhealth"])):
                        self.mydatajson[device]["minbufferhealth"] = stats.get("BufferHealth", "0.0")

                # Define CSV file path using the key as the file name
                if self.do_webUI:
                    csv_file_path = os.path.join(self.ui_report_dir, f'{device}_youtube_stats_report.csv')
                else:
                    csv_file_path = f"/home/lanforge/lanforge-scripts/py-scripts/{device}_youtube_stats_report.csv"

                # Add the file path to the list of device files (now devices_list)
                self.devices_list.append(csv_file_path)

                file_exists = os.path.isfile(csv_file_path)
                
                headers = ["Instance Name", "TimeStamp", "Viewport", "DroppedFrames", "TotalFrames", "CurrentRes", "OptimalRes", "BufferHealth"]

                with open(csv_file_path, mode='a', newline='') as file:
                    writer = csv.writer(file)
                    
                    # Write the headers only if the file is new
                    if not file_exists:
                        writer.writerow(headers)
                    
                    # Write each row of data specific to the device (key)
                    # Assuming `device`, `timestamp`, and `stats` are predefined for each row
                    row = [device, timestamp]
                    
                    # Add values based on headers, filling in "NA" for any missing keys
                    for header in headers[2:]:  # Start from index 2 to skip "Instance Name" and "TimeStamp"
                        row.append(stats.get(header, "NA"))  # Use "NA" if header not in stats
                    
                    writer.writerow(row)

           
            
            self.stats_api_response = self.data
            return self.data
        else:
            return None
    def get_last_result_yt(self,):
            try:
                url = f"http://{self.host}:5454/read_youtube_data_from_csv"
                #url= f"http://10.253.8.108:8000/last_result_yt"
                # Make a GET request to the API
                response = requests.get(url)

                # Check if the request was successful
                if response.status_code == 200:
                    # Parse the JSON response
                    data = response.json()
                    #print("Data fetched successfully:", data)
                    return data
                else:
                    print(f"Failed to fetch data. Status code: {response.status_code}")
                    return None

            except requests.exceptions.RequestException as e:
                print(f"An error occurred: {e}")
                return None


    
    def send_stats_to_api(self, device_name, stop = False):
       # print("checking the value of stop",stop)
        """
            Sends YouTube streaming statistics to a specified API endpoint.
            Args:
                device_name (str): The name of the device for which statistics are being sent.
                stop (bool, optional): Indicates if the streaming has stopped. Default is False.
            Raises:
                Exception: If an error occurs during the API request.
        """
        try:
            # Define the API endpoint URL
            url = f"http://{self.host}:5454/youtube_stats"
            #url= f"http://10.253.8.108:8000/youtube_stats"
            
            # Set the headers for the HTTP POST request
            headers = {
            'Content-Type': 'application/json',
            }
            # the data payload for the POST request
            data = {
                'name' : device_name,
                'stats' : self.stats_api_response['result'][device_name]['stats'],
                'stop': stop,
            }
            # Send the HTTP POST request to the API endpoint
            response = requests.post(url, json=data, headers=headers)

            # Check the response status code to determine if the request was successful
            if response.status_code == 200:
                #logging.info("Successfully sent stats to API.")
                pass
            else:
                #logging.info(f"Failed to send stats to API. Status code: {response.status_code}")
                pass
        except Exception as e:
            # Print an error message if an exception occurs during the request
            logging.info(f"An error occurred while sending stats to API: {e}")
    
    def stop_test_yt(self,):
        try:
            # Define the API endpoint URL
            url = f"http://{self.host}:5454/update_status_yt"
            #url = f"http://10.253.8.108:8000/update_status_yt"
            
            # Set the headers for the HTTP POST request
            headers = {
                'Content-Type': 'application/json',
            }
            
            # The data payload for the POST request
            data = {
                'status': 'Completed',
                'name': self.test_name,
            }
            
            # Send the HTTP POST request to the API endpoint
            response = requests.post(url, json=data, headers=headers)

            # Check the response status code to determine if the request was successful
            if response.status_code == 200:
                logging.info("Successfully updated STOP status to 'Completed'")
                pass
            else:
                logging.error(f"Failed to update STOP status: {response.status_code} - {response.text}")
                
        except Exception as e:
            # Print an error message if an exception occurs during the request
            logging.error(f"An error occurred while updating status: {e}")
    def clear_previous_data(self,):
        try:
            # Define the API endpoint URL to clear previous data
            url = f"http://{self.host}:5454/youtube_stats"
            #url = "http://10.253.8.108:8000/youtube_stats"
            headers = {
                'Content-Type': 'application/json',
            }
            # Send a POST request with a specific flag to clear the data
            data = {
                'clear_data': True,
            }
            response = requests.post(url, json=data, headers=headers)
            if response.status_code == 200:
                logging.info("Successfully cleared previous test data.")
            else:
                logging.error(f"Failed to clear previous data. Status code: {response.status_code}")
        except Exception as e:
            logging.error(f"An error occurred while clearing previous data: {e}")
    
    def move_files(self,source_file, dest_dir):
        # Ensure the source file exists
        if not os.path.isfile(source_file):
            logging.ERROR(f"Source file '{source_file}' does not exist or is not a regular file.")
            return
        
        # Ensure the destination directory exists
        if not os.path.exists(dest_dir):
            logging.ERROR(f"Destination directory '{dest_dir}' does not exist.")
            return
        
        try:
            # Extract the filename from the source file path
            filename = os.path.basename(source_file)
            
            # Construct the destination file path
            dest_file = os.path.join(dest_dir, filename)
            
            # Move the file
            shutil.move(source_file, dest_file)
            
            logging.info(f"Successfully moved '{source_file}' to '{dest_file}'.")

        except Exception as e:
            logging.ERROR(f"Failed to move '{source_file}' to '{dest_dir}': {e}")

    def create_report(self,data,ui_report_dir):
        #print("==========================================================================================")
        #print("checking data inside create_report method",data)
        windows=0
        mac=0
        linux=0

        #print(data)

        for i in range(0,len(self.real_sta_os_types)):

            if (self.real_sta_os_types[i]=='windows'):
                windows=windows+1
            elif (self.real_sta_os_types[i]=='linux'):
                linux=linux+1
            elif (self.real_sta_os_types[i]=='macos'):
                mac=mac+1
        # print("checking real_sta_os_types",self.real_sta_os_types)
        # print("checking mac count",mac)
        
        if(self.do_webUI):
            result_data =data
            #print(result_data)
            for device, device_data in result_data.items():
                stats = device_data
                self.mydatajson[device].update({
                    "Viewport": stats.get("Viewport", ""),
                    "DroppedFrames": stats.get("DroppedFrames", "0"),
                    "TotalFrames": stats.get("TotalFrames", "0"),
                    "CurrentRes": stats.get("CurrentRes", ""),
                    "OptimalRes": stats.get("OptimalRes", ""),
                })
        else:

            result_data = data.get("result", {})
            for device, device_data in result_data.items():
                stats = device_data.get("stats", {}).get("stats", {})
               
                self.mydatajson[device].update({
                    "Viewport": stats.get("Viewport", ""),
                    "DroppedFrames": stats.get("DroppedFrames", "0"),
                    "TotalFrames": stats.get("TotalFrames", "0"),
                    "CurrentRes": stats.get("CurrentRes", ""),
                    "OptimalRes": stats.get("OptimalRes", ""),
                })
        # print(mydatajson)
        #print("checking mydatajson")
        #print(self.mydatajson)

        if(self.do_webUI):
            self.report = lf_report(_output_pdf='youtube_streaming.pdf',
                           _output_html='youtube_streaming.html',
                           _results_dir_name="youtube_streaming_report",
                           _path=ui_report_dir)
        else:
            self.report = lf_report(_output_pdf='youtube_streaming.pdf',
                           _output_html='youtube_streaming.html',
                           _results_dir_name="youtube_streaming_report",
                           _path='')
        self.report_path = self.report.get_path()
        self.report_path_date_time = self.report.get_path_date_time()
       

        # setting report title
        self.report.set_title('Youtube Streaming Report')
        self.report.build_banner()

        # objective and description
        self.report.set_obj_html(_obj_title='Objective',
                            _obj='''The Objective is to conduct automated Youtube Video Streaming test across multiple laptops to gather statistics. The test
                            will collect these statistics. Additionally,automated graphs will be generated using the collected data.
                            ''')
        self.report.build_objective()

        # Test setup info
        test_setup_info = {
            'Test Name': 'YouTube Streaming Test',
            'Duration (in Minutes)': self.duration,
            'Resolution':self.resolution,
            'No of Devices :':f' Total({len(self.real_sta_os_types)}) : W({windows}),L({linux}),M({mac})',
            "Video URL": self.url,


        }

        self.report.test_setup_table(
            test_setup_data=test_setup_info, value='Test Parameters')
        

        

        viewport_list = []
        current_res_list = []
        optimal_res_list = []

        dropped_frames_list=[]
        total_frames_list=[]
        max_buffer_health_list=[]
        min_buffer_health_list= []


        


        for hostname in self.real_sta_hostname:
            if hostname in self.mydatajson:
                stats = self.mydatajson[hostname]
                viewport_list.append(stats.get("Viewport", ""))
                current_res_list.append(stats.get("CurrentRes", ""))
                optimal_res_list.append(stats.get("OptimalRes", ""))
                
                dropped_frames = stats.get("DroppedFrames", "0")
                total_frames = stats.get("TotalFrames", "0")
                max_buffer_health = stats.get("maxbufferhealth","0,0")
                min_buffer_health = stats.get("minbufferhealth","0.0")
                try:
                    dropped_frames_list.append(int(dropped_frames))
                except ValueError:
                    dropped_frames_list.append(0)

                try:
                    total_frames_list.append(int(total_frames))
                except ValueError:
                    total_frames_list.append(0)
                try:
                    max_buffer_health_list.append(float(max_buffer_health))
                except ValueError:
                    max_buffer_health_list.append(0.0)

                try:
                    min_buffer_health_list.append(float(min_buffer_health))
                except ValueError:
                    min_buffer_health_list.append(0.0)

            else:
                viewport_list.append("NA")
                current_res_list.append("NA")
                optimal_res_list.append("NA")
                dropped_frames_list.append(0)
                total_frames_list.append(0)
                max_buffer_health_list.append(0.0)
                min_buffer_health_list.append(0.0)

                

        #graph of frames dropped
        self.report.set_graph_title("Total Frames vs Frames dropped")
        self.report.build_graph_title()
        x_fig_size = 25
        #print("check self.devicenames",)
        y_fig_size = len(self.device_names) * .5 + 4

        graph = lf_bar_graph_horizontal(_data_set=[dropped_frames_list,total_frames_list],
                         _xaxis_name="No of Frames",
                         _yaxis_name="Devices",
                         _yaxis_categories=self.real_sta_hostname,
                         _graph_image_name="Dropped Frames vs Total Frames",
                         _label=["dropped Frames", "Total Frames",],
                         _color=None,
                         _color_edge='red',
                         _figsize=(x_fig_size,y_fig_size),
                         _show_bar_value= True,
                        _text_font=6,
                        _text_rotation=True,
                        _enable_csv=True,
                        _legend_loc="upper right",
                        _legend_box=(1.1,1),
                        )
        graph_image=graph.build_bar_graph_horizontal()
        self.report.set_graph_image(graph_image)
        self.report.move_graph_image()
        self.report.build_graph()

        self.report.set_table_title('Test Results')
        self.report.build_table_title()

        test_results={
            "Hostname": self.real_sta_hostname,
            "OS Type": self.real_sta_os_types,
            "MAC": self.mac_list,
            "RSSI": self.rssi_list,
            "Link Rate": self.link_rate_list,
            "ViewPort": viewport_list,
            "SSID": self.ssid_list,
            "Video Resoultion": current_res_list,
            "Max Buffer Health (Seconds)" : max_buffer_health_list,
            "Min Buffer health (Seconds)": min_buffer_health_list,
            "Total Frames": total_frames_list,
            "Dropped Frames": dropped_frames_list,
            

        }

        test_results_df=pd.DataFrame(test_results)
        self.report.set_table_dataframe(test_results_df)
        self.report.build_table()

        
        

        # # Move the files after they are written
        # if not self.do_webUI:
        for file_path in self.devices_list:
            #file_to_move_path = os.path.join(self.report_path_date_time, '..', os.path.basename(file_path))
            self.move_files(file_path, self.report_path_date_time)
        
        original_dir = os.getcwd()

        # Get a list of all CSV files in the specific directory
        if self.do_webUI:
            csv_files = [f for f in os.listdir(self.report_path_date_time) if f.endswith('.csv')]
            os.chdir(self.report_path_date_time)
        else:
            csv_files = [f for f in os.listdir(self.report_path_date_time) if f.endswith('.csv')]
            os.chdir(self.report_path_date_time)



        # Iterate over each CSV file in the directory
        for file_name in csv_files:
            # Load the CSV file

            
            data = pd.read_csv(file_name)

            self.report.set_graph_title('Buffer Health vs Time Graph for {}'.format(file_name.split('_')[0]))
            self.report.build_graph_title()

            # Convert timestamp column to datetime format for easier manipulation
            try:
                data['TimeStamp'] = pd.to_datetime(data['TimeStamp'], format="%H:%M:%S").dt.time
            except Exception as e:
                print(f"Error in timestamp conversion for {file_name}: {e}")
                continue

            # Drop duplicate timestamps and keep only the first occurrence
            data = data.drop_duplicates(subset='TimeStamp', keep='first')

            # Sort data by timestamp
            data = data.sort_values(by='TimeStamp')

            # Extract the relevant columns for the graph
            #timestamps = data['TimeStamp']
            timestamps = data['TimeStamp'].apply(lambda t: t.strftime('%H:%M:%S'))
            buffer_health = data['BufferHealth']

            # Plot the Buffer Health vs Time graph with at least 30 timestamps on the x-axis
            fig, ax = plt.subplots(figsize=(20, 10))
            plt.plot(timestamps, buffer_health, color='blue', linewidth=2)

            # Customize the plot
            plt.xlabel('Time', fontweight='bold', fontsize=15)
            plt.ylabel('Buffer Health', fontweight='bold', fontsize=15)
            plt.title('Buffer Health vs Time Graph for {}'.format(file_name.split('_')[0]), fontsize=18)


            # Set the x-axis ticks to ensure at least 30 timestamps
            if len(timestamps) > 30:
                tick_interval = len(timestamps) // 30
                selected_ticks = timestamps[::tick_interval]
                ax.set_xticks(selected_ticks)
            else:
                ax.set_xticks(timestamps)

            plt.xticks(rotation=45, ha='right')

            # Save the plot as a PNG file
            output_file = '{}'.format(file_name.split('_')[0])+'buffer_health_vs_time.png'
            plt.tight_layout()
            plt.savefig(output_file, dpi=96)
            plt.close()

            # Print the saved plot file path
            print(f"Graph saved for {file_name}: {output_file}")

            self.report.set_graph_image(output_file)
    
            self.report.build_graph()

        os.chdir(original_dir)

       

        #Closing
        self.report.build_custom()
        self.report.build_footer()
        self.report.write_html()
        self.report.write_pdf()

    

        



        

        

def main():
    help_summary='''\
        Youtube streaming automation 
    '''
    parser = argparse.ArgumentParser(
        prog='lf_interop_youtube.py',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog='''
            Allows user to run the youtube streaming test on a target resource for the given duration.
        ''',
        description=''
        'youtube streaming automation '''
    )

    # Define required arguments group
    required = parser.add_argument_group('Required arguments')
    # Define optional arguments group
    optional = parser.add_argument_group('Optional arguments')
    # Define webUI specific arguments group
    webUI_args = parser.add_argument_group('webUI arguments')

    # Add required arguments
    required.add_argument('--mgr',type=str,help="hostname where LANforge GUI is running",required=True)
    required.add_argument('--url',type=str,help='youtube url',required=True)
    required.add_argument('--duration',type=int,help='duration to run the test in sec',required=True)
    required.add_argument('--ap_name',type=str,default="TIP",help="Name of the AP in which we run the test")
    required.add_argument('--sec',type=str,default="wpa2",help="security type used")
    required.add_argument('--band',type=str,default="5GHZ",help="Name of the Frequency band used")
    required.add_argument('--test_name',type=str,help="Test name while running through webgui")

    

    
    # Add optional arguments
    optional.add_argument('--resources',help='Specify the real device ports seperated by comma')
    optional.add_argument('--no_pre_cleanup',action="store_true",help='specify this flag to stop cleaning up generic cxs before the test')
    optional.add_argument('--no_post_cleanup',action="store_true",help='specify this flag to stop cleaning up generic cxs after the test')
    optional.add_argument('--debug', action="store_true", help='Enable debugging')
    optional.add_argument('--mgr_port',type=str,default=8080,help='port on which LANforge HTTP service is running')
    parser.add_argument('--log_level', default=None,help='Set logging level: debug | info | warning | error | critical')
    parser.add_argument('--res',default='Auto',help="to set resolution to  144p,240p,720p")
    parser.add_argument("--lf_logger_config_json",help="--lf_logger_config_json <json file> , json configuration of logger")

    # Add webUI specific arguments
    webUI_args.add_argument('--ui_report_dir', default=None, help='Specify the results directory to store the reports for webUI')
    webUI_args.add_argument('--do_webUI',action='store_true',help='specify this flag when triggering a test from webUI')

    # Arguments Related to Device Configurations
    parser.add_argument('--file_name',help="File name for DeviceConfig")
    parser.add_argument('--group_name', type=str, help='specify the group name')
    parser.add_argument('--profile_name', type=str, help='specify the profile name')
    parser.add_argument("--ssid", default=None, help='specify ssid on which the test will be running')
    parser.add_argument("--passwd", default=None, help='specify encryption password  on which the test will '
                                                 'be running')
    parser.add_argument("--encryp", default=None, help='specify the encryption type  on which the test will be '
                                                        'running eg :open|psk|psk2|sae|psk2jsae')
    
    parser.add_argument("--eap_method", type=str,default='DEFAULT')
    parser.add_argument("--eap_identity", type=str,default='')
    parser.add_argument("--ieee80211",action="store_true")
    parser.add_argument("--ieee80211u",action="store_true")
    parser.add_argument("--ieee80211w",type=int,default=1)
    parser.add_argument("--enable_pkc",action="store_true")
    parser.add_argument("--bss_transition",action="store_true")
    parser.add_argument("--power_save",action="store_true")
    parser.add_argument("--disable_ofdma",action="store_true")
    parser.add_argument("--roam_ft_ds",action="store_true")
    parser.add_argument("--key_management", type=str,default='DEFAULT')
    parser.add_argument("--pairwise", type=str,default='[BLANK]')
    parser.add_argument("--private_key", type=str,default='[BLANK]')
    parser.add_argument("--ca_cert", type=str,default='[BLANK]')
    parser.add_argument("--client_cert", type=str,default='[BLANK]')
    parser.add_argument("--pk_passwd", type=str,default='[BLANK]')
    parser.add_argument("--pac_file", type=str,default='[BLANK]')
    parser.add_argument("--server_ip",type=str,default=None)
    parser.add_argument('--help_summary', help='Show summary of what this script does', default=None)
    parser.add_argument("--expected_passfail_value",help="Specify the expected urlcount value for pass/fail")
    parser.add_argument("--device_csv_name",type=str,help="Specify the device csv name for pass/fail",default=None)


    args = parser.parse_args()

    if args.help_summary:
        logging.info(help_summary)
        exit(0)

    # set the logger level to debug
    logger_config = lf_logger_config.lf_logger_config()

    if args.log_level:
        logger_config.set_level(level=args.log_level)

    if args.lf_logger_config_json:
        logger_config.lf_logger_config_json = args.lf_logger_config_json
        logger_config.load_lf_logger_config()

    if(args.expected_passfail_value!=None and args.device_csv_name!=None):
            print("Specify either expected_passfail_value or device_csv_name")
            exit(1)

    if(args.group_name!=None):
        selected_groups=args.group_name.split(',')
    else:
        selected_groups=[]
    if(args.profile_name!=None):
        selected_profiles=args.profile_name.split(',')
    else:
        selected_profiles=[]
    
    # Assign arguments to variables for easier access
    mgr_ip = args.mgr 
    mgr_port = args.mgr_port
    url = args.url 
    duration = args.duration

    do_webUI = args.do_webUI
    ui_report_dir = args.ui_report_dir
    debug = args.debug

    # Print debug information if debugging is enabled
    if (debug):
        logging.info('''Specified configuration:
            ip:                       {}
            port:                     {}
            Duration:                 {}
            debug:                    {}
            '''.format(mgr_ip, mgr_port, duration, debug))
    
    if((args.group_name!=None and args.profile_name!=None and args.file_name!=None and args.resources==None and args.ssid==None and (len(selected_groups)==len(selected_profiles))) or(args.group_name==None and args.profile_name==None and args.file_name==None and args.ssid!=None and args.passwd!=None and args.encryp!=None) or (args.group_name==None and args.profile_name==None and args.file_name==None and args.ssid!=None and args.passwd==None and args.encryp.lower() =='open')):


        # Create a YouTube object with the specified parameters
        youtube = Youtube(host = mgr_ip, port = mgr_port, url = url, duration = args.duration, lanforge_password = 'lanforge', sta_list=[], do_webUI = args.do_webUI, ui_report_dir = ui_report_dir, debug = debug,resolution=args.res,ap_name=args.ap_name,ssid=args.ssid,security=args.sec,band=args.band,test_name=args.test_name)

        # Create a RealDevice object for device management
        Devices = RealDevice(manager_ip=mgr_ip,
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
        
        configure = False
        resources = []    
        laptops = Devices.get_devices()
        youtube.Devices = Devices
        # Initialize empty lists and dictionaries for resource management
        resource_ids_sm = []
        resource_set = set()
        resource_list = []
        resource_ids_generated = ""
        config_obj=DeviceConfig.DeviceConfig(lanforge_ip=args.mgr,file_name=args.file_name)
        if not args.expected_passfail_value and args.device_csv_name==None :
                    config_obj.device_csv_file(csv_name="device.csv")
        if(args.group_name!=None and args.file_name!=None and args.profile_name!=None):
            selected_groups=args.group_name.split(',')
            selected_profiles=args.profile_name.split(',')
            config_devices={}
            for i in range(len(selected_groups)):
                config_devices[selected_groups[i]]=selected_profiles[i]
        
        
            config_obj.initiate_group()
            asyncio.run(config_obj.connectivity(config_devices))
    
            adbresponse=config_obj.adb_obj.get_devices()
            resource_manager=config_obj.laptop_obj.get_devices()
            all_res={}
            df1=config_obj.display_groups(config_obj.groups)
            groups_list=df1.to_dict(orient='list')
            group_devices={}
            
            for adb in adbresponse:   
                group_devices[adb['serial']]=adb['eid']
            for res in resource_manager:
                all_res[res['hostname']]=res['shelf']+'.'+res['resource']
            eid_list=[]
            for grp_name in groups_list.keys():
                for g_name in selected_groups:
                    if(grp_name == g_name):
                        for j in groups_list[grp_name]:
                            if(j in group_devices.keys()):
                                eid_list.append(group_devices[j])
                            elif(j in all_res.keys()):
                                eid_list.append(all_res[j])
            args.resources = ",".join(id for id in eid_list)
        else:
            if args.resources:
                all_devices= config_obj.get_all_devices()
                config_dict={
                'ssid':args.ssid,
                'passwd':args.passwd,
                'enc':args.encryp,
                'eap_method':args.eap_method,
                'eap_identity':args.eap_identity,
                'ieee80211':args.ieee80211,
                'ieee80211u':args.ieee80211u,
                'ieee80211w':args.ieee80211w,
                'enable_pkc':args.enable_pkc,
                'bss_transition':args.bss_transition,
                'power_save':args.power_save,
                'disable_ofdma':args.disable_ofdma,
                'roam_ft_ds':args.roam_ft_ds,
                'key_management':args.key_management,
                'pairwise':args.pairwise,
                'private_key':args.private_key,
                'ca_cert':args.ca_cert,
                'client_cert':args.client_cert,
                'pk_passwd':args.pk_passwd,
                'pac_file':args.pac_file,
                'server_ip':args.server_ip
                }
                if(args.group_name==None and args.file_name==None and args.profile_name==None):
                    dev_list=args.resources.split(',')
                    asyncio.run(config_obj.connectivity(device_list=dev_list,wifi_config=config_dict))
            else:
                 all_devices= config_obj.get_all_devices()
                 device_list=[]
                 config_dict={
                 'ssid':args.ssid,
                 'passwd':args.passwd,
                 'enc':args.encryp,
                 'eap_method':args.eap_method,
                 'eap_identity':args.eap_identity,
                 'ieee80211':args.ieee80211,
                 'ieee80211u':args.ieee80211u,
                 'ieee80211w':args.ieee80211w,
                 'enable_pkc':args.enable_pkc,
                 'bss_transition':args.bss_transition,
                 'power_save':args.power_save,
                 'disable_ofdma':args.disable_ofdma,
                 'roam_ft_ds':args.roam_ft_ds,
                 'key_management':args.key_management,
                 'pairwise':args.pairwise,
                 'private_key':args.private_key,
                 'ca_cert':args.ca_cert,
                 'client_cert':args.client_cert,
                 'pk_passwd':args.pk_passwd,
                 'pac_file':args.pac_file,
                 'server_ip':args.server_ip,
                 }
                 for device in all_devices:
                     if(device["type"]!='laptop'):
                         device_list.append(device["shelf"]+'.'+device["resource"]+" "+device["serial"])
                     elif(device["type"]=='laptop'):
                         device_list.append(device["shelf"]+'.'+device["resource"]+" "+device["hostname"])
                 print("Available devices:", device_list)
                 args.resources = input("Enter the desired resources to run the test:")
                 dev1_list=args.resources.split(',')
                 asyncio.run(config_obj.connectivity(device_list=dev1_list,wifi_config=config_dict))
               





        # print("===============================================")
        # print("Checking args.resources value",args.resources)

        

        result_list = []
        if(not do_webUI):
            if args.resources:
                resources = [r.strip() for r in args.resources.split(',')]
                resources = [r for r in resources if len(r.split('.')) > 1]
                
                get_data = youtube.select_real_devices(real_devices=Devices, real_sta_list=resources, base_interop_obj=Devices)
            
                for item in get_data:
                    item = item.strip()
                    # Find and append the matching lap to result_list
                    matching_laps = [lap for lap in laptops if lap.startswith(item)]
                    result_list.extend(matching_laps)
                if not result_list:
                    logging.info("Resources donot exist hence Terminating the test.")
                    return 
                if len(result_list) != len(get_data):
                    logging.info("Few Resources donot exist hence Excluding Them from the Test")
                    
            else:
                resources = youtube.select_real_devices(real_devices=Devices)
        else:
            resources = [r.strip() for r in args.resources.split(',')]
            youtube.select_real_devices(real_devices=Devices, real_sta_list=resources, base_interop_obj=Devices)
        
        # Perform pre-test cleanup if not skipped
        if not args.no_pre_cleanup:
            youtube.cleanup()

        # Check if the required tab exists, and exit if not
        if (not youtube.check_tab_exists()):
            logging.error('Generic Tab is not available.\nAborting the test.')
            exit(0)

        # Combine station list with real devices list
        youtube.sta_list += youtube.real_sta_list 
        if(not do_webUI):
            youtube.clear_previous_data()

        # If valid resources exist, create generic endpoints
        
        if result_list:
            youtube.create_generic_endp(result_list)
        else:
            youtube.create_generic_endp(resources)

        logging.info("==============================================================================")
        logging.info(f"TEST STARTED")
        logging.info('Running the Youtube Streaming test for {} minutes'.format(duration))

        # Wait for 10 seconds before starting the test
        time.sleep(10)

        youtube.start_time = datetime.now() 
        youtube.start_generic()

        duration = args.duration  # Set your desired duration in minutes
        # Calculate end time based on duration 
        end_time = datetime.now() + timedelta(minutes=duration)

        time_counter = 0 


        # Get data from API and check for valid data
        initial_data = youtube.get_data_from_api()
        
        while not initial_data:
            initial_data = youtube.get_data_from_api()
            time.sleep(1)
        if initial_data:
            end_time_webgui = []
            for i in range(len(youtube.device_names)):
                end_time_webgui.append(initial_data['result'].get(youtube.device_names[i], {}).get('stop', False))
        else:
            for i in range(len(youtube.device_names)):
                end_time_webgui.append("")

        # Monitor and manage test execution until all endpoints stop or if not all endpoints stops then monitor and manage till estimated end time is reached
        all_stop = False

        keys = youtube.generic_endps_profile.created_cx

        start_time = datetime.now()
        est_end_time = datetime.now() + timedelta(minutes = duration, seconds = 60)
    

        if(do_webUI):
            while ((not all_stop)):
                    stop_value = youtube.set_webUI_stop()
                    if(stop_value == "Completed"):
                        break
                    initial_data = youtube.get_data_from_api()
                    if initial_data:
                        for i in range(len(youtube.device_names)):
                            stop_state = initial_data['result'].get(youtube.device_names[i], {}).get('stop', False)
                            if stop_state:
                                end_time_webgui[i] = True
                                if ((all(end_time_webgui))):
                                    all_stop = True 
                                if datetime.now() >= est_end_time:
                                    for key in range(len(youtube.device_names)):
                                        if ((all(end_time_webgui))):

                                            all_stop = True 
                                        if not end_time_webgui[key]:
                                            new_key = keys[key]
                                            if new_key.startswith("CX_"):
                                                new_key = keys[key][3:]
                                            response = youtube.json_get(f'/generic/{new_key}')
                                            if response['endpoint']['status'] in ['WAITING', 'Stopped']:
                                                end_time_webgui[key] = True
                            else:
                                if datetime.now() >= est_end_time:
                                    if ((all(end_time_webgui))):
                                        all_stop = True 
                                    for key in range(len(youtube.device_names)):
                                        if ((all(end_time_webgui))):
                                            all_stop = True 
                                        if not end_time_webgui[key]:
                                            new_key = keys[key]
                                            if new_key.startswith("CX_"):
                                                new_key = keys[key][3:]
                                            response = youtube.json_get(f'/generic/{new_key}')
                                        # logging.info(f"checking response: {response}")
                                            if response['endpoint']['status'] in ['WAITING', 'Stopped']:
                                                end_time_webgui[key] = True
                                    
                    
                    time.sleep(1)  # Adjust the sleep time as needed


        else:
            while ((not all_stop)):
                    initial_data = youtube.get_data_from_api()
                    if initial_data:
                        for i in range(len(youtube.device_names)):
                            stop_state = initial_data['result'].get(youtube.device_names[i], {}).get('stop', False)
                            if stop_state:
                
                                end_time_webgui[i] = True
                                if all(end_time_webgui):
                                    all_stop = True 
                                if datetime.now() >= est_end_time:
                                    for key in range(len(youtube.device_names)):
                                        if all(end_time_webgui):
                                            all_stop = True 
                                        if not end_time_webgui[key]:
                                            new_key = keys[key]
                                            if new_key.startswith("CX_"):
                                                new_key = keys[key][3:]
                                            response = youtube.json_get(f'/generic/{new_key}')
                                            
                                            if response['endpoint']['status'] in ['WAITING', 'Stopped']:
                                                end_time_webgui[key] = True
                            else:
                                if datetime.now() >= est_end_time:
                                    if all(end_time_webgui):
                                        all_stop = True 
                                    for key in range(len(youtube.device_names)):
                                        if all(end_time_webgui):
                                            all_stop = True 
                                        if not end_time_webgui[key]:
                                            new_key = keys[key]
                                            if new_key.startswith("CX_"):
                                                new_key = keys[key][3:]
                                            response = youtube.json_get(f'/generic/{new_key}')
                                            if response['endpoint']['status'] in ['WAITING', 'Stopped']:
                                                end_time_webgui[key] = True
                    
                    time.sleep(1)  # Adjust the sleep time as needed

            



        #Stopping the Youtube test
        if(do_webUI):
            youtube.stop_test_yt()
        
        youtube.generic_endps_profile.stop_cx()
        logging.info(f"=================================================================================================")
        logging.info("Duration ended")

        logging.info('Stopping the test')

        #print("youtube.data is ",youtube.data)

        if(do_webUI):
            time.sleep(3)
            final_data = youtube.get_last_result_yt()
            # print("checking final data =========================")
            # print(final_data)
            youtube.create_report(final_data,youtube.ui_report_dir)
        else:
            youtube.create_report(youtube.data,'')
        
        # Perform post-test cleanup if not skipped
        if not args.no_post_cleanup:
            youtube.cleanup()

if __name__ == "__main__":
    main()