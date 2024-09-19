#!/usr/bin/env python3

from lf_report import lf_report
from lf_graph import lf_bar_graph_horizontal
import os
import sys
import argparse
import time
import logging
import datetime
import importlib
import paramiko
import traceback
# from itertools import combinations # to generate pair combinations for attenuators


logger = logging.getLogger(__name__)
if sys.version_info[0] != 3:
    logger.critical("This script requires Python 3")
    exit(1)

sys.path.append(os.path.join(os.path.abspath(__file__ + "../../../")))
realm = importlib.import_module("py-json.realm")
LFUtils = importlib.import_module("py-json.LANforge.LFUtils")
sta_connect = importlib.import_module("py-scripts.sta_connect2")
Realm = realm.Realm

lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")


class Roam(Realm):
    def __init__(self,
                 lanforge_ip='localhost',
                 port=8080,
                 ssh_username='root',
                 ssh_password='lanforge',
                 sniff_radio='1.1.wiphy0',
                 station_radio='1.1.wiphy0',
                 band='5G',
                #  ap1_bssid=None,
                #  ap2_bssid=None,
                #  attenuator1=None,
                #  attenuator2=None,
                 attenuators=[],
                 bssids=[],
                 step=100,
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
                 wait_time=30,
                 sniff_duration=300,
                 channel='AUTO',
                 frequency=-1,
                 iterations=None,
                 softroam=True,
                 real_devices=True
                 ):
        super().__init__(lanforge_ip, port)

        self.lanforge_ip = lanforge_ip
        self.port = port
        self.upstream = upstream

        # self.ap1_bssid = ap1_bssid
        # self.ap2_bssid = ap2_bssid
        # self.attenuator1 = attenuator1
        # self.attenuator2 = attenuator2
        self.attenuators = attenuators
        self.step = step
        self.max_attenuation = max_attenuation
        self.bssids = bssids

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
        self.channel = channel
        self.frequency = frequency
        self.iterations = iterations
        self.soft_roam = softroam

        self.real_devices = real_devices
        self.sniff_radio = sniff_radio
        self.sniff_duration = sniff_duration
        self.station_radio = station_radio
        self.band = band

        #ssh
        self.ssh_username = ssh_username
        self.ssh_password = ssh_password
        self.ssh_port = "22"
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # reporting variable
        self.roam_data = {}
        self.bssid_based_totals = {}
        self.station_based_roam_count = {}
        self.pcap_names = []

        if(len(self.attenuators) == 1):
            logging.error('Cannot perform roaming with only one attenuator. Please provide atleast two attenuators.')
            exit(1)
        # self.attenuator_combinations = list(combinations(self.attenuators, 2)) # generating 2 pair combinations for the given attenuators
        self.attenuator_combinations  = []
        attenuators = self.attenuators + [self.attenuators[0]]
        for atten_index in range(len(attenuators) - 1):
            self.attenuator_combinations.append((attenuators[atten_index], attenuators[atten_index + 1]))
        logging.info('Test will be performed on the APs with the following attenuator combinations {}'.format(self.attenuator_combinations))

        all_attenuators = self.atten_list()
        if(all_attenuators is None or all_attenuators == []):
            logging.error('There are no attenuators in the given LANforge {}. Exiting the test.'.format(self.lanforge_ip))
            exit(1)
        else:
            for atten_serial in all_attenuators:
                atten_serial_name, atten_values = list(atten_serial.keys())[0], list(atten_serial.values())[0]
                if(atten_serial_name not in self.attenuators):
                    if(atten_values['state'] != 'Phantom'):
                        logging.info('Attenuator {} is not in the test attenuators list. Setting the attenuation value to max.'.format(atten_serial_name))
                        self.set_atten(atten_serial_name, self.max_attenuation)

        self.sniff_radio_resource, self.sniff_radio_shelf, self.sniff_radio_port, _ = self.name_to_eid(
            self.sniff_radio)

        self.monitor = self.new_wifi_monitor_profile(
            resource_=self.sniff_radio_resource, up_=False)
        self.create_monitor()

        self.staConnect = sta_connect.StaConnect2(host=self.lanforge_ip, port=self.port,
                                                  outfile="sta_connect2.csv")
        
        # self.cx_profile = self.new_l3_cx_profile()
        # self.cx_profile.host = self.lanforge_ip
        # self.cx_profile.port = self.port
        # self.cx_profile.name_prefix = 'ROAM-'
        # self.cx_profile.side_a_min_bps = '1000000'
        # self.cx_profile.side_a_max_bps = '1000000'
        # self.cx_profile.side_b_min_bps = '1000000'
        # self.cx_profile.side_b_max_bps = '1000000'

        self.attenuator_increments = list(
            range(0, self.max_attenuation+1, self.step))
        if (self.max_attenuation not in self.attenuator_increments):
            self.attenuator_increments.append(self.max_attenuation)

        self.attenuator_decrements = list(
            range(self.max_attenuation, -1, -self.step))
        if (0 not in self.attenuator_decrements):
            self.attenuator_decrements.append(0)

    def create_cx(self):
        self.cx_profile.create(endp_type='lf_udp',
                               side_a=self.station_list,
                               side_b=self.upstream)
    
    def start_cx(self):
        self.cx_profile.start_cx()
    
    def stop_cx(self):
        for cx_name in self.cx_profile.created_cx.keys():
            print(cx_name)
            self.stop_cx(cx_name)

    def set_attenuators(self, atten1, atten2):
        logging.info('Setting attenuation to {} for attenuator {}'.format(
            0, atten1))
        self.set_atten(atten1, 0)

        logging.info(
            'Setting active attenuator as {}'.format(atten1))
        self.active_attenuator = atten1

        logging.info(
            'Setting passive attenuator as {}'.format(atten2))
        self.passive_attenuator = atten2

        logging.info('Setting attenuation to {} for attenuator {}'.format(
            self.max_attenuation, atten2))
        self.set_atten(atten2, self.max_attenuation)

        for atten in self.attenuators:
            if(atten not in [atten1, atten2]):
                logging.info('Setting unused attenuator {} value to maximum attenuation.'.format(atten))
                self.set_atten(atten, self.max_attenuation)

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
        self.monitor.create(resource_=self.sniff_radio_resource,
                            radio_=self.sniff_radio_port, channel=self.channel, frequency=self.frequency, name_='sniffer0')

    def connect(self):
        """
        Method to initiate an SSH connection.
        """        
        try:
            self.ssh_client.connect(
                self.lanforge_ip, username=self.ssh_username, password=self.ssh_password)
            self.sftp = self.ssh_client.open_sftp()
        except Exception as e:
            print(traceback.print_exception(e))
            exit(1)

    def disconnect(self):
        """
        Method to terminate the SSH connection.
        """        
        try:
            self.ssh_client.close()
        except Exception as e:
            print(traceback.print_exception(e))
            exit(1)    

    def ssh_execute(self, cmd='hostname', inline_input=None):
        """
        Method to execute any command in the remote system.

        Args:
            cmd (str, optional): Command to run on remote system. Defaults to 'hostname'.
            inline_input (str, optional): If sudo is included in the cmd argument, then you can pass the password in this inline_input. Defaults to None.

        Returns:
            tuple: Returns the stdin, stdout and stderr for the executed command.
        """        
        try:
            if inline_input:
                stdin, stdout, stderr = self.ssh_client.exec_command(
                    command=cmd, get_pty=True)
                stdin.write('{}\n'.format(inline_input))
                stdin.flush()
            else:
                stdin, stdout, stderr = self.ssh_client.exec_command(
                    command=cmd)
            return stdin, stdout, stderr
        except Exception as e:
            print(traceback.print_exception(e))
            exit(1)
    
    def start_sniff(self, interface='sniffer0', pcap_name='~/Desktop/sniff.pcap'):
        """
        Method to start sniffing on a selected interface with a pcap name.

        Args:
            interface (str, optional): Interface to start the tshark sniffer. Defaults to 'eth1'.
            pcap_name (str, optional): PCAP name to store the sniffer output. Defaults to '~/Desktop/sniff.pcap'.
        """

        self.create_monitor()
        self.pcap_names.append(pcap_name)
        sniff_cmd = 'tshark -i {} -w {} > /dev/null 2>&1 &'.format(
            interface, pcap_name)
        print(sniff_cmd)
        self.ssh_execute(sniff_cmd)
        
        stdin, stdout, stderr = self.ssh_execute(
            'ps -aux | grep "{}"'.format(sniff_cmd))
        self.monitor_pid = stdout.readline().split()[1]
        pid = self.monitor_pid
        
        print('Started sniffer on {} with pid {}'.format(interface, pid))
    
    def save_files(self, test_dir_name=""):
        # self.connect()
        if os.path.exists(test_dir_name):
            for file in self.pcap_names:
                try:
                    print("Test Directory PATH: ", os.getcwd() + '/' + test_dir_name + '/' + file.split('/')[-1])
                    self.sftp.get(remotepath=file, localpath=os.getcwd() + '/' + test_dir_name + '/' + file.split('/')[-1])
                except Exception as e:
                    print('SFTP failed with exception {}.\nFile may be corrupted while transfer.'.format(e))
                # self.sftp.close()
        else:
            print('SCP failed.')

    def stop_sniff(self):
        """
        Method to stop sniffer on the selected interface.

        Args:
            interface (str, optional): Interface to stop sniffing. Defaults to 'eth1'.
        """

        stop_sniff_cmd = 'killall -9 tshark'
        stdin, stdout, stderr = self.ssh_execute(stop_sniff_cmd)

    def get_bssids(self):
        bssids = []
        removable_stations = []
        for station in self.station_list:
            t_bssid = self.get_port_data(station, 'ap')
            if (t_bssid is not None):
                if len(t_bssid) != 17:
                    bssid = []
                    for duplet in t_bssid.split(':'):
                        if len(duplet) != 2:
                            bssid.append('0' + duplet)
                        else:
                            bssid.append(duplet)
                    bssid = ':'.join(bssid)
                else:
                    bssid = t_bssid   
                bssids.append(bssid.upper())         
            else:
                removable_stations.append(station)
        for station in removable_stations:
            self.station_list.remove(station)
        return bssids

     # get existing stations list
    def get_station_list(self):
        sta = self.staConnect.station_list()
        if sta == "no response":
            return "no response"
        sta_list = []
        for i in sta:
            for j in i:
                sta_list.append(j)
        return sta_list

    def create_clients(self, start_id=0, sta_prefix='sta'):
        station_profile = self.new_station_profile()


        if self.station_flag is not None:
            _flags = self.station_flag.split(',')
            for flags in _flags:
                logger.info(f"Selected Flags: '{flags}'")
                station_profile.set_command_flag("add_sta", flags, 1)


        radio = self.station_radio
        sta_list = self.get_station_list()
        print("Available list of stations on lanforge-GUI :", sta_list)
        logging.info(str(sta_list))
        if not sta_list:
            print("No stations are available on lanforge-GUI")
            logging.info("No stations are available on lanforge-GUI")
        else:
            station_profile.cleanup(sta_list, delay=1)
            self.wait_until_ports_disappear(sta_list=sta_list,
                                            debug_=True)
        print("Creating stations.")
        logging.info("Creating stations.")
        station_list = LFUtils.portNameSeries(prefix_=sta_prefix, start_id_=start_id,
                                              end_id_=self.num_sta - 1, padding_number_=10000,
                                              radio=radio)
        if self.sta_type == "normal":
            station_profile.set_command_flag("add_sta", "power_save_enable", 1)
            if not self.soft_roam:
                station_profile.set_command_flag("add_sta", "disable_roam", 1)
            if self.soft_roam:
                print("Soft roam true")
                logging.info("Soft roam true")
                if self.option == "otds":
                    print("OTDS present")
                    station_profile.set_command_flag(
                        "add_sta", "ft-roam-over-ds", 1)

        if self.sta_type == "11r-sae-802.1x":
            dut_passwd = "[BLANK]"
        station_profile.use_security(self.security, self.ssid, self.password)
        station_profile.set_number_template("00")

        station_profile.set_command_flag("add_sta", "create_admin_down", 1)

        station_profile.set_command_param("set_port", "report_timer", 1500)

        # connect station to particular bssid
        # self.station_profile.set_command_param("add_sta", "ap", self.bssid[0])

        station_profile.set_command_flag("set_port", "rpt_timer", 1)
        if self.sta_type == "11r":
            station_profile.set_command_flag("add_sta", "80211u_enable", 0)
            station_profile.set_command_flag("add_sta", "8021x_radius", 1)
            if not self.soft_roam:
                # station_profile.ssid_pass = self.security_key
                station_profile.set_command_flag("add_sta", "disable_roam", 1)
            if self.soft_roam:
                print("Soft roam true")
                logging.info("Soft roam true")
                if self.option == "otds":
                    print("OTDS present")
                    station_profile.set_command_flag(
                        "add_sta", "ft-roam-over-ds", 1)
            station_profile.set_command_flag("add_sta", "power_save_enable", 1)
            station_profile.set_wifi_extra(key_mgmt="FT-PSK     ",
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
        if self.sta_type == "11r-sae":
            station_profile.set_command_flag("add_sta", "ieee80211w", 2)
            station_profile.set_command_flag("add_sta", "80211u_enable", 0)
            station_profile.set_command_flag("add_sta", "8021x_radius", 1)
            # station_profile.set_command_flag("add_sta", "disable_roam", 1)
            if not self.soft_roam:
                station_profile.set_command_flag("add_sta", "disable_roam", 1)
            if self.soft_roam:
                if self.option == "otds":
                    station_profile.set_command_flag(
                        "add_sta", "ft-roam-over-ds", 1)
            station_profile.set_command_flag("add_sta", "power_save_enable", 1)
            station_profile.set_wifi_extra(key_mgmt="FT-SAE     ",
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
        if self.sta_type == "11r-sae-802.1x":
            station_profile.set_command_flag("set_port", "rpt_timer", 1)
            station_profile.set_command_flag("add_sta", "ieee80211w", 2)
            station_profile.set_command_flag("add_sta", "80211u_enable", 0)
            station_profile.set_command_flag("add_sta", "8021x_radius", 1)
            if not self.soft_roam:
                station_profile.set_command_flag("add_sta", "disable_roam", 1)
            if self.soft_roam:
                if self.option == "otds":
                    station_profile.set_command_flag(
                        "add_sta", "ft-roam-over-ds", 1)
            # station_profile.set_command_flag("add_sta", "disable_roam", 1)
            station_profile.set_command_flag("add_sta", "power_save_enable", 1)
            # station_profile.set_command_flag("add_sta", "ap", "68:7d:b4:5f:5c:3f")
            station_profile.set_wifi_extra(key_mgmt="FT-EAP     ",
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
        station_profile.create(radio=radio, sta_names_=station_list)
        print("Waiting for ports to appear")
        logging.info("Waiting for ports to appear")
        self.wait_until_ports_appear(sta_list=station_list)

        if self.soft_roam:
            for sta_name in station_list:
                sta = sta_name.split(".")[2]  # TODO:  Use name_to_eid
                # wpa_cmd = "roam " + str(checker2)

                bgscan = {
                    "shelf": 1,
                    # TODO:  Do not hard-code resource, get it from radio eid I think.
                    "resource": 1,
                    "port": str(sta),
                    "type": 'NA',
                    "text": 'bgscan="simple:30:-65:300"'
                }

                print(bgscan)
                logging.info(str(bgscan))
                self.json_post("/cli-json/set_wifi_custom", bgscan)
                # time.sleep(2)

        station_profile.admin_up()
        print("Waiting for ports to admin up")
        logging.info("Waiting for ports to admin up")
        if self.wait_for_ip(station_list):
            print("All stations got IPs")
            logging.info("All stations got IPs")
            self.station_list = station_list
            # exit()
            return True
        else:
            print("Stations failed to get IPs")
            logging.info("Stations failed to get IPs")
            return False

    def soft_roam_test(self):
        for station in self.station_list:
            self.station_based_roam_count[station] = 0
        for bssid in self.bssids:
            self.bssid_based_totals[bssid.upper()] = 0

        if (self.iteration_based):
            logging.info(
                'Performing Roaming Test for {} iterations.'.format(self.iterations))
            for current_iteration in range(1, self.iterations + 1):
                logging.info(
                    'Initiating iteration {}'.format(current_iteration))

                before_iteration_bssid_data = self.get_bssids()
                current_iteration_roam_data = {}
                for atten_set in self.attenuator_combinations:
                    self.start_sniff(pcap_name='/home/lanforge/Desktop/iteration_{}_roam_{}.pcap'.format(current_iteration, self.attenuator_combinations.index(atten_set)))
                    self.roam_data[atten_set] = {

                    }
                    
                    # for displaying purpose
                    print('========================================================================')
                    print('Roaming test started on the attenuator combination {} - {}'.format(atten_set[0], atten_set[1]))
                    print('========================================================================')

                    atten1, atten2 = atten_set
                    self.set_attenuators(atten1=atten1, atten2=atten2)

                    # logging.info(
                    #     'Starting sniffer with roam_test_{}.pcap'.format(current_iteration))
                    # self.start_sniff(
                    #     capname='roam_test_{}.pcap'.format(current_iteration))

                    for attenuator_change_index in range(len(self.attenuator_increments)):

                        logging.info('Setting the attenuation to {} for attenuator {}'.format(
                            self.attenuator_increments[attenuator_change_index], self.active_attenuator))
                        self.set_atten(
                            self.active_attenuator, self.attenuator_increments[attenuator_change_index])

                        logging.info('Setting the attenuation to {} for attenuator {}'.format(
                            self.attenuator_decrements[attenuator_change_index], self.passive_attenuator))
                        self.set_atten(
                            self.passive_attenuator, self.attenuator_decrements[attenuator_change_index])

                        logging.info(
                            'Waiting for {} seconds before monitoring the stations'.format(self.wait_time))
                        time.sleep(self.wait_time)

                        logging.info('Monitoring the stations')
                        current_step_bssid_data = self.get_bssids()
                        for bssid_index in range(len(current_step_bssid_data)):
                            if self.station_list[bssid_index] not in current_iteration_roam_data:
                                current_iteration_roam_data[self.station_list[bssid_index]] = {
                                    'BSSID before iteration':   before_iteration_bssid_data[bssid_index],
                                    'BSSID after iteration':   current_step_bssid_data[bssid_index],
                                    'Signal Strength':   self.get_port_data(self.station_list[bssid_index], 'signal'),
                                    'Status': False
                                }
                                if current_step_bssid_data[bssid_index] not in [None, 'NA', ''] and current_step_bssid_data[bssid_index] != before_iteration_bssid_data[bssid_index]:
                                    current_iteration_roam_data[self.station_list[bssid_index]]['Status'] = True
                            else:
                                if current_step_bssid_data[bssid_index] not in [None, 'NA', ''] and before_iteration_bssid_data[bssid_index] != current_step_bssid_data[bssid_index]:
                                    current_iteration_roam_data[self.station_list[bssid_index]] = {
                                        'BSSID before iteration':   before_iteration_bssid_data[bssid_index],
                                        'BSSID after iteration':   current_step_bssid_data[bssid_index],
                                        'Signal Strength':   self.get_port_data(self.station_list[bssid_index], 'signal'),
                                        'Status':   True
                                    }
                        print(current_iteration_roam_data)
                    print(current_iteration_roam_data)
                    logging.info('Stopping sniffer')
                    self.stop_sniff()
                    self.active_attenuator, self.passive_attenuator = self.passive_attenuator, self.active_attenuator
                logging.info('Iteration {} complete'.format(current_iteration))
                self.roam_data[atten_set].update({
                    current_iteration: current_iteration_roam_data
                })
                print(self.roam_data)
                # self.roam_data[current_iteration] = current_iteration_roam_data

                # logging.info('Stopping sniffer')
                # self.stop_sniff()
        else:
            logging.info(
                'Duration based roaming test is still under development.')
        logging.info('Stopping sniffer')
        # self.stop_sniff()
        logging.info(self.roam_data)

    def generate_report(self, result_json=None, result_dir='Roam_Test_Report', report_path=''):
        if result_json is not None:
            self.roam_data = result_json

        total_attempted_roams = len(self.station_list) * self.iterations * len(self.attenuator_combinations)
        # total_successful_roams = sum([len(station)
        #                              for station in self.roam_data.values()])
        total_successful_roams = 0
        for atten_set in self.attenuator_combinations:
            for iteration_values in self.roam_data[atten_set].values():
                for station_data in iteration_values.values():
                    if 'Status' in station_data.keys() and station_data['Status']:
                        total_successful_roams += 1
                        print(list(iteration_values.keys())[0], station_data)
                        self.bssid_based_totals[station_data['BSSID after iteration']] += 1
                        self.station_based_roam_count[list(iteration_values.keys())[0]] += 1
        total_failed_roams = total_attempted_roams - total_successful_roams

        logging.info('{}'.format(self.bssid_based_totals))
        logging.info('{}'.format(self.station_based_roam_count))
        
        logging.info('Generating Report')

        report = lf_report(_output_pdf='roam_test.pdf',
                           _output_html='roam_test.html',
                           _results_dir_name=result_dir,
                           _path=report_path)
        report_path = report.get_path()
        report_path_date_time = report.get_path_date_time()
        logging.info('path: {}'.format(report_path))
        logging.info('path_date_time: {}'.format(report_path_date_time))

        # setting report title
        report.set_title('Roam Test Report')
        report.build_banner()

        # test setup info
        test_setup_info = {
            'SSID': [self.ssid if self.ssid else 'TEST CONFIGURED'][0],
            'Security': [self.security if self.ssid else 'TEST CONFIGURED'][0],
            'Sniffer Radio': [self.sniff_radio if self.sniff_radio else 'TEST CONFIGURED'][0],
            # 'Station Type': self.sta_type,
            'Iterations': self.iterations,
            'No of Devices': len(self.station_list),
            # 'No of Devices': '{} (V:{}, A:{}, W:{}, L:{}, M:{})'.format(len(self.sta_list), len(self.sta_list) - len(self.real_sta_list), self.android, self.windows, self.linux, self.mac),
        }
        report.test_setup_table(
            test_setup_data=test_setup_info, value='Test Setup Information')

        # objective and description
        report.set_obj_html(_obj_title='Objective',
                            _obj='''The Candela Roam test uses the forced roam method to create and roam hundreds of WiFi stations 
                            between two or more APs with the same SSID or the same channel of different channels. The user can run 
                            thousands of roams over long durations and the test measures roaming delay for each roam, station 
                            connection times, network down time, packet loss etc.. The user can run this test using different security 
                            methods and compare the roaming performance. The expected behavior is the roaming delay should be 
                            50msecs or less for all various kinds of fast roaming methods to avoid any form of service interruption to 
                            real-time delay sensitive applications.
                            ''')
        report.build_objective()

        # Migration Totals
        report.set_table_title(
            'Total Roams attempted vs Successful vs Failed')
        report.build_table_title()

        # graph for above
        total_roams_graph = lf_bar_graph_horizontal(_data_set=[[total_attempted_roams], [total_successful_roams], [total_failed_roams]],
                                        _xaxis_name='Roam Count',
                                        _yaxis_name='Wireless Clients',
                                        _label=[
                                            'Attempted Roams', 'Successful Roams', 'Failed Roams'],
                                        _graph_image_name='Total Roams attempted vs Successful vs Failed',
                                        _yaxis_label=['Stations'],
                                        _yaxis_categories=['Stations'],
                                        _yaxis_step=1,
                                        _yticks_font=8,
                                        _graph_title='Total Roams attempted vs Successful vs Failed',
                                        _title_size=16,
                                        _color=['orange',
                                                'darkgreen', 'red'],
                                        _color_edge=['black'],
                                        _bar_height=0.15,
                                        _legend_loc="best",
                                        _legend_box=(1.0, 1.0),
                                        _dpi=96,
                                        _show_bar_value=False,
                                        _enable_csv=True,
                                        _color_name=['orange', 'darkgreen', 'red'])

        total_roams_graph_png = total_roams_graph.build_bar_graph_horizontal()
        logging.info('graph name {}'.format(total_roams_graph_png))
        report.set_graph_image(total_roams_graph_png)
        # need to move the graph image to the results directory
        report.move_graph_image()
        report.set_csv_filename(total_roams_graph_png)
        report.move_csv_file()
        report.build_graph()

        # bssid based roam count
        report.set_table_title(
            'BSSID based Successful vs Failed')
        report.build_table_title()

        # graph for above
        bssid_based_total_attempted_roams = [total_attempted_roams // 2] * len(list(self.bssid_based_totals.values()))
        bssid_based_failed_roams = [bssid_based_total_attempted_roams[roam] - list(self.bssid_based_totals.values())[roam] for roam in range(len(self.bssid_based_totals.values()))]
        bssid_based_graph = lf_bar_graph_horizontal(_data_set=[list(self.bssid_based_totals.values())],
                                        _xaxis_name='Roam Count',
                                        _yaxis_name='Wireless Clients',
                                        _label=['Roams'],
                                        _graph_image_name='BSSID based Successful vs Failed',
                                        _yaxis_label=list(self.bssid_based_totals.keys()),
                                        _yaxis_categories=list(self.bssid_based_totals.keys()),
                                        _yaxis_step=1,
                                        _yticks_font=8,
                                        _graph_title='BSSID based Successful vs Failed',
                                        _title_size=16,
                                        _color=['darkgreen', 'darkgreen', 'red'],
                                        _color_edge=['black'],
                                        _bar_height=0.15,
                                        _legend_loc="best",
                                        _legend_box=(1.0, 1.0),
                                        _dpi=96,
                                        _show_bar_value=False,
                                        _enable_csv=True,
                                        _color_name=['darkgreen', 'darkgreen', 'red'])

        bssid_based_graph_png = bssid_based_graph.build_bar_graph_horizontal()
        logging.info('graph name {}'.format(bssid_based_graph_png))
        report.set_graph_image(bssid_based_graph_png)
        # need to move the graph image to the results directory
        report.move_graph_image()
        report.set_csv_filename(bssid_based_graph_png)
        report.move_csv_file()
        report.build_graph()


        # station based roam count
        report.set_table_title(
            'Station based Successful vs Failed')
        report.build_table_title()

        # graph for above
        station_based_total_attempted_roams = [total_attempted_roams // len(self.station_list)] * len(self.station_list)
        station_based_failed_roams = []
        # for station_index in range(len(station_based_roam_count)):
        #     station_based_failed_roams.append(station_based_total_attempted_roams[station_index] - station_based_roam_count[station_index])
        for station in self.station_based_roam_count:
            station_based_failed_roams.append((total_attempted_roams // len(self.station_list)) - self.station_based_roam_count[station])
        station_based_graph = lf_bar_graph_horizontal(_data_set=[station_based_total_attempted_roams, list(self.station_based_roam_count.values()), station_based_failed_roams],
                                        _xaxis_name='Roam Count',
                                        _yaxis_name='Wireless Clients',
                                        _label=['Total', 'Successful', 'Failed'],
                                        _graph_image_name='Station based Successful vs Failed',
                                        _yaxis_label=list(self.station_based_roam_count.keys()),
                                        _yaxis_categories=list(self.station_based_roam_count.keys()),
                                        _yaxis_step=1,
                                        _yticks_font=8,
                                        _graph_title='Station based Successful vs Failed',
                                        _title_size=16,
                                        _color=['orange', 'darkgreen', 'red'],
                                        _color_edge=['black'],
                                        _bar_height=0.15,
                                        _legend_loc="best",
                                        _legend_box=(1.0, 1.0),
                                        _dpi=96,
                                        _show_bar_value=False,
                                        _enable_csv=True,
                                        _color_name=['orange', 'darkgreen', 'red'])

        station_based_graph_png = station_based_graph.build_bar_graph_horizontal()
        logging.info('graph name {}'.format(station_based_graph_png))
        report.set_graph_image(station_based_graph_png)
        # need to move the graph image to the results directory
        report.move_graph_image()
        report.set_csv_filename(station_based_graph_png)
        report.move_csv_file()
        report.build_graph()

        # closing
        report.build_custom()
        report.build_footer()
        report.write_html()
        report.write_pdf()

        # pulling pcaps
        self.save_files(test_dir_name=report_path_date_time)

        # self.disconnect()


def main():
    help_summary = '''
'''
    parser = argparse.ArgumentParser(
        prog='roam_test.py',
    )
    required = parser.add_argument_group('Required Arguments')

    # required.add_argument('--ap1_bssid',
    #                       help='BSSID of Access Point 1',
    #                       required=True)
    # required.add_argument('--ap2_bssid',
    #                       help='BSSID of Access Point 2',
    #                       required=True)
    # required.add_argument('--attenuator1',
    #                       help='Serial number of attenuator near AP1',
    #                       required=True)
    # required.add_argument('--attenuator2',
    #                       help='Serial number of attenuator near AP2',
    #                       required=True)

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
                          " 11r-sae-802.1x or simple as none", default="11r")

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
                          help='Attenuation increment/decrement step size',
                          type=int,
                          default=10)
    optional.add_argument('--max_attenuation',
                          help='Maximum attenuation value (dBm) for the attenuators',
                          type=int,
                          default=95)
    # optional.add_argument('--iteration_based',
    #                       help='Enable this flag to run the roam test based on iterations rather than duration',
    #                       action='store_true')
    optional.add_argument('--attenuators',
                          nargs='+',
                          help='Attenuator serials', 
                          required=True)
    optional.add_argument('--bssids',
                          nargs='+',
                          help='BSSIDs', 
                          required=True)
    optional.add_argument('--iterations',
                          help='Number of iterations to perform roam test',
                          type=int,
                          default=2)
    # optional.add_argument('--duration',
    #                       help='Roam test time (seconds)',
    #                       type=int,
    #                       default=2)
    optional.add_argument('--wait_time',
                          help='Waiting time (seconds) between iterations',
                          type=int,
                          default=30)

    optional.add_argument('--channel',
                          help='Channel',
                          type=str,
                          default='AUTO')

    optional.add_argument('--frequency',
                          help='Frequency',
                          type=int,
                          default=-1)
    
    optional.add_argument('--ssh_username',
                          help='SSH username',
                          default='lanforge')
    
    optional.add_argument('--ssh_password',
                          help='SSH password',
                          default='lanforge')
    # optional.add_argument('--hardroam',
    #                       help='Enable this flag to perform hardroam',
    #                       action='store_true')
    # optional.add_argument('--real',
    #                       help='Enable this flag to perform test on real devices',
    #                       action='store_true')

    optional.add_argument('--station_list',
                          help='List of stations to perform roam test (comma seperated)')
    
    optional.add_argument('--station_flag',
                          help='station flags to add. eg: --station_flag use-bss-transition',
                          required=False,
                          default=None)

    optional.add_argument('--sniff_radio',
                          help='Sniffer Radio',
                          default='1.1.wiphy0')
    # optional.add_argument('--sniff_duration',
    #                       help='Sniff duration',
    #                       type=int,
    #                       default=300)

    parser.add_argument('--help_summary',
                        help='Show summary of what this script does',
                        default=None,
                        action="store_true")

    # logging configuration:
    parser.add_argument('--log_level', default=None,
                        help='Set logging level: debug | info | warning | error | critical')

    parser.add_argument("--lf_logger_config_json",
                        help="--lf_logger_config_json <json file> , json configuration of logger")

    args = parser.parse_args()

    # help summary
    if (args.help_summary):
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

    if (args.station_list is not None):
        stations = args.station_list.split(',')
        roam_test = Roam(
            lanforge_ip=args.mgr,
            port=args.port,
            sniff_radio=args.sniff_radio,
            # ap1_bssid=args.ap1_bssid,
            # ap2_bssid=args.ap2_bssid,
            # attenuator1=args.attenuator1,
            # attenuator2=args.attenuator2,
            attenuators=args.attenuators,
            bssids=args.bssids,
            step=args.step,
            max_attenuation=args.max_attenuation,
            ssh_username=args.ssh_username,
            ssh_password=args.ssh_password,
            # sniff_duration=args.sniff_duration,
            upstream=args.upstream,
            # ssid=args.ssid,
            # security=args.security,
            # password=args.password,
            wait_time=args.wait_time,
            channel=args.channel,
            frequency=args.frequency,
            iterations=args.iterations
        )
        roam_test.station_list = stations
        logging.info('Selected stations\t{}'.format(stations))
    else:
        roam_test = Roam(
            lanforge_ip=args.mgr,
            port=args.port,
            sniff_radio=args.sniff_radio,
            station_radio=args.sta_radio,
            band=args.band,
            # ap1_bssid=args.ap1_bssid,
            # ap2_bssid=args.ap2_bssid,
            # attenuator1=args.attenuator1,
            # attenuator2=args.attenuator2,
            attenuators=args.attenuators,
            bssids=args.bssids,
            step=args.step,
            max_attenuation=args.max_attenuation,
            ssh_username=args.ssh_username,
            ssh_password=args.ssh_password,
            # sniff_duration=args.sniff_duration,
            upstream=args.upstream,
            ssid=args.ssid,
            security=args.security,
            password=args.password,
            num_sta=args.num_sta,
            station_flag=args.station_flag,
            option=args.option,
            identity=args.identity,
            ttls_pass=args.ttls_pass,
            sta_type=args.sta_type,
            wait_time=args.wait_time,
            channel=args.channel,
            frequency=args.frequency,
            iterations=args.iterations
        )
        logging.info(
            'Starting sniffer with roam_test.pcap')
        # roam_test.start_sniff(
        #     capname='roam_test.pcap')

        # roam_test.create_clients()
        # roam_test.create_cx()
        # roam_test.start_cx()

    roam_test.connect()
    if (roam_test.soft_roam):
        logging.info('Initiating soft roam test')

        roam_test.soft_roam_test()
        # roam_test.stop_cx()

    roam_test.generate_report()


if __name__ == '__main__':
    main()