#!/usr/bin/env python3
'''
  This Scrip has two classes :
          1. LoadScenario : It will load the existing saved scenario to the Lanforge (Here used for Loading Bridged VAP)
          2. CreateSTA_CX : It will create stations and L3 Cross connects and start them
          3. Login_DUT : This class is specifically used to test the Linux based DUT that has SSH Server. It is used to read the CPU Core temperature during testing
    In this example, Another Lanforge is used as DUT
    It also have a function : GenerateReport that generates the report in xlsx format as well as it plots the Graph of throughput over time with temperature
    It also have Plot function that generates a html page that contains the plot
    Prerequisite Installation

    pip install paramiko
    pip install bokeh
    pip install XlsxWriter

    Example
    .\Lexus_Final.py --lf_host 192.168.200.15 --dut_host 192.168.200.18 --dut_radio wiphy1 --lf_radio wiphy1 --num_sta 1 --sta_id 1 --lf_ssid lanforge_ap --dut_ssid lexusap --security open --dut_upstream eth2 --lf_upstream eth1 --protocol lf_udp --min_bps 1000 --max_bps 10000 --time 1
  This Script is intended to automate the testing of DUT That has stations as well as AP.
  To automate the simultaenous testing and check the DUT Temperature
'''

import sys
if sys.version_info[0] != 3:
    print("This script requires Python 3")
    exit(1)
if 'py-json' not in sys.path:
    sys.path.append('../py-json')


import argparse
import time
from LANforge import LFUtils
from LANforge import lfcli_base
from LANforge.lfcli_base import LFCliBase
from LANforge.LFUtils import *
import realm

from realm import Realm
import logging

import paramiko as pm
from paramiko.ssh_exception import NoValidConnectionsError as exception
import xlsxwriter
from bokeh.io import output_file, show
from bokeh.plotting import figure
from bokeh.models import LinearAxis, Range1d
from bokeh.models import HoverTool
from bokeh.layouts import row


# Specifically for Measuring CPU Core Temperatures
class Login_DUT:

    def __init__(self, threadID, name, HOST):
      self.threadID = threadID
      self.name = name
      self.host=HOST
      self.USERNAME = "lanforge"
      self.PASSWORD = "lanforge"
      self.CLIENT= pm.SSHClient()
      self.LF1= self.Connect()
      self.data_core1=[]
      self.data_core2=[]
      if self.CLIENT == 0:
        exit()
      print("Connected to " +HOST+" DUT to Measure the Core Temperature")
    def run(self):
        stdin, stdout, stderr= self.CLIENT.exec_command("sensors")
        out_lines = stdout.readlines()
        err_lines = stderr.readlines()
        print(out_lines[len(out_lines)-3], out_lines[len(out_lines)-2])
        self.data_core1.append(out_lines[len(out_lines)-3])
        self.data_core2.append(out_lines[len(out_lines)-2])
        
    def Connect(self):
        self.CLIENT.load_system_host_keys()
        self.CLIENT.set_missing_host_key_policy(pm.AutoAddPolicy())
        try:
            self.CLIENT.connect(self.host, username=self.USERNAME, password=self.PASSWORD,timeout=10)
            return None    
        except exception as error:
            self.CLIENT = 0;
            return None


# Class to Load a Scenario that has been Created in Chamber View saved under DB/[Database_Name]
class LoadScenario(LFCliBase):
    def __init__(self, host, port, db_name, security_debug_on=False, _exit_on_error=False,_exit_on_fail=False):
        super().__init__(host, port, _debug=security_debug_on, _halt_on_error=_exit_on_error, _exit_on_fail=_exit_on_fail)
        self.host = host
        self.port = port
        self.json_post("/cli-json/load", { "name": db_name, "action": 'overwrite' })
        print("Scenario Loaded...")
        time.sleep(2)

# Class to create stations and run L3 Cross connects and run them for given time. It also stores the endpoint names for measuring throughput
class CreateSTA_CX(LFCliBase):
    
    def __init__(self, host, port, radio, num_sta, sta_id, ssid, security, password, upstream, protocol, min_bps, max_bps, security_debug_on=True, _exit_on_error=True, _exit_on_fail=True):
        super().__init__(host, port, _debug=security_debug_on, _halt_on_error=_exit_on_error, _exit_on_fail=_exit_on_fail)
        
        self.host = host
        self.port = port
        self.radio = radio
        
        self.num_sta = num_sta
        self.sta_id = sta_id

        self.ssid = ssid

        self.security = security
        self.password = password

        self.upstream = upstream
        self.protocol = protocol

        self.min_bps =min_bps
        self.max_bps =max_bps

        #Creating a Realm Object
        self.local_realm = Realm(lfclient_host=host, lfclient_port=port)

        #Creating Profile Objects
        self.station_profile = self.local_realm.new_station_profile()
        self.cx_profile = self.local_realm.new_l3_cx_profile()

        #Setting CX Name
        self.cx_profile.name_prefix_="Connection"
        self.cx_names = []
        self.sta_list = []
        self.endp=[]
        for i in range(sta_id,sta_id+num_sta):
            self.sta_list.append("sta00")
        
        #portDhcpUpRequest
        '''
        upstream_dhcp = LFRequest.LFRequest("http://"+str(host)+":"+str(port)+"/"+"/cli-form/set_port")
        upstream_dhcp.addPostData( LFUtils.portSetDhcpDownRequest(1, upstream))
        upstream_dhcp.formPost()
        time.sleep(2)
        upstream_dhcp.addPostData( LFUtils.portUpRequest(1, upstream))
        upstream_dhcp.formPost()
        print(upstream + "Set to DHCP For Cross Connects")
        '''

    def build(self):

        #Creating Stations of Given Profile Settings
        self.station_profile.use_security(self.security, self.ssid, passwd=self.password)
        self.station_profile.create(self.radio, num_stations=self.num_sta, sta_names_=self.sta_list)
        self.station_profile.admin_up()
        #Wait for a while
        time.sleep(15)
        
        #Setting up the Parameters for CX
        self.cx_profile.side_a_min_bps = self.min_bps
        self.cx_profile.side_b_min_bps = self.min_bps
        self.cx_profile.side_a_max_bps = self.max_bps
        self.cx_profile.side_b_max_bps = self.max_bps
        
        self.cx_profile.side_a_min_pdu = 'Auto'
        self.cx_profile.side_b_min_pdu = 'Auto'
        self.cx_profile.report_timer = 1000
        self.cx_profile.side_a_min_pkt='Same'
        self.cx_profile.side_a_max_pkt='Same'
        
        #Create Connections of Given Parameters
        self.cx_profile.create(self.protocol, side_a="1.1."+self.upstream, side_b=list(self.local_realm.find_ports_like("sta0+")))
        time.sleep(15)
        
        # Getting all the Endpoint Names for measuring Throughput Later
        for i in self.cx_profile.get_cx_names():
           self.cx_names.append(i)
        for j in self.cx_names:
            x=self.local_realm.json_get("/cx/"+j)
            self.endp.append(x.get(j).get('endpoints')[0])
        #print(self.endp)
        return 0
        

    def start(self):
        #self.station_profile.admin_up()
        
        self.cx_profile.start_cx()
        time.sleep(5)
        return 0

    def stop(self):
        self.cx_profile.stop_cx()
        time.sleep(5)
        self.lf_stations.admin_down()
        time.sleep(5)
        return 0

    def cleanup(self):
        self.local_realm.cleanup_cxe_prefix(self.cx_profile.name_prefix)
        station_map = self.local_realm.find_ports_like("sta+")
        for eid,record in station_map.items():
            self.local_realm.remove_vlan_by_eid(eid)
            time.sleep(0.03)
        del_sta_names = []
        try:
            for eid,value in station_map.items():
                tname = eid[eid.rfind('.'):]
                del_sta_names.append(tname)
        except Exception as x:
            self.local_realm.error(x)
        try:
            LFUtils.waitUntilPortsDisappear(base_url=self.local_realm.lfclient_url, port_list=del_sta_names, debug=True)
            print("Ports Successfully Cleaned up")
            return 0
        except:    
            print("Ports Successfully Cleaned up")
        time.sleep(5)
        return 0


# Generates XLSX Report        
def GenerateReport(throughput_sta, throughput_vap, core1_temp, core2_temp, duration,name):
    workbook = xlsxwriter.Workbook(name)
    worksheet = workbook.add_worksheet()
    worksheet.write('A1', 'THROUGHPUT OVER TIME STA CX ')
    worksheet.write('B1', 'THROUGHPUT OVER TIME VAP ')
    worksheet.write('C1', 'CORE 0 TEMP')
    worksheet.write('D1', 'CORE 1 TEMP')
    core1=[]
    core2=[]
    sta_throu=[]
    vap_throu=[]
    j=2
    for i in throughput_sta:
        sta_throu.append(i/1000000)
        worksheet.write('A'+str(j), str(i/1000000)+" Mbps")
        j=j+1
    j=2
    for i in throughput_vap:
        vap_throu.append(i/1000000)
        worksheet.write('B'+str(j), str(i/1000000)+" Mbps")
        j=j+1
    j=2
    for i in core1_temp:
        core1.append(int(str(i).split(':')[1].split('(')[0].split('.')[0].split('+')[1]))
        worksheet.write('C'+str(j),str(i).split(':')[1].split('(')[0] )
        j=j+1
    j=2
    for i in core2_temp:
        core2.append(int(str(i).split(':')[1].split('(')[0].split('.')[0].split('+')[1]))
        worksheet.write('D'+str(j), str(i).split(':')[1].split('(')[0])
        j=j+1

    Time =[]
    for i in range(0,int(duration)*5):
        Time.append(i)
    plot(sta_throu, vap_throu, core1, core2, Time)
    workbook.close()


# Plotting Function for Parameters
def plot(throughput_sta, throughput_vap, core1_temp, core2_temp, Time):

    
    s1 = figure()
    s1.title.text = "WIFI Throughput vs Temperature Plot"
    s1.xaxis.axis_label = "Time in Seconds"
    s1.yaxis.axis_label = "Throughput in Mbps"

    s1.line( Time, throughput_sta, color='black')
    s1.circle(Time, throughput_sta, color='red')

    s1.line( Time, throughput_vap, color='orange')
    s1.circle(Time, throughput_vap, color='blue')
    
    s1.extra_y_ranges = {"Temperature": Range1d(start=0, end=150)}
    s1.add_layout(LinearAxis(y_range_name="Temperature", axis_label="Temperature in Degree Celsius"), 'right')
    
    s1.line(Time, core1_temp, y_range_name='Temperature', color='black')
    s1.circle(Time, core1_temp, y_range_name='Temperature', color='red')

    s1.line(Time, core2_temp, y_range_name='Temperature', color='green')
    s1.circle(Time, core2_temp, y_range_name='Temperature', color='blue')

    show(s1)

    
# Creates the Instance for LFCliBase
class VAP_Measure(LFCliBase):
    def __init__(self, lfclient_host, lfclient_port):
        super().__init__(lfclient_host, lfclient_port)



# main method
def main():

    parser = argparse.ArgumentParser(description="Test Scenario of DUT Temperature measurement along with simultaneous throughput on VAP as well as stations")
    
    parser.add_argument("-m", "--lf_host", type=str, help="Enter the address of LF which will test the DUT")
    parser.add_argument("-d", "--dut_host", type=str, help="Enter the address of LF Which is to be dut")
    parser.add_argument("-lr", "--lf_radio", type=str, help="Enter the radio on which you want to create a station/s on (Lanforge Side)")
    parser.add_argument("-dr", "--dut_radio", type=str, help="Enter the radio on which you want to create a station/s on (DUT Side)")
    parser.add_argument("-n", "--num_sta", type=int, help="Enter the Number of Stations You want to create")
    parser.add_argument("-st", "--sta_id", type=int, help="Enter Station id [for sta001, enter 1]")

    parser.add_argument("-ls", "--lf_ssid", type=str, help="Enter the ssid, with which you want to associate your stations (Enter the SSID of VAP in Lanforge)")
    parser.add_argument("-ds", "--dut_ssid", type=str, help="Enter the ssid, with which you want to associate your stations (Enter the SSID of VAP in DUT)")
    parser.add_argument("-sec", "--security", type=str, help="Enter the security type [open, wep, wpa, wpa2]")
    parser.add_argument("-p", "--password", type=str, help="Enter the password if security is not open")
    parser.add_argument("-lu", "--lf_upstream", type=str, help="Enter the upstream ethernet port")
    parser.add_argument("-du", "--dut_upstream", type=str, help="Enter the upstream ethernet port")
    parser.add_argument("-pr", "--protocol", type=str, help="Enter the protocol on which you want to run your connections [lf_udp, lf_tcp]")
    parser.add_argument("-minb", "--min_bps", type=str, help="Enter the Minimum Rate")
    parser.add_argument("-maxb", "--max_bps", type=str, help="Enter the Maximum Rate")
    parser.add_argument("-t", "--duration", type=int, help="Enter the Time for which you want to run test (In Minutes)")
    parser.add_argument("-r", "--report_name", type=str, help="Enter the Name of the Output file ('Report.xlsx')")
    
    args = None
     
    try:
      args = parser.parse_args()
      if (args.lf_host is not None):
         lf_host = args.lf_host
      if (args.dut_host is not None):
         dut_host = args.dut_host
      if (args.lf_radio is not None):
         lf_radio = args.lf_radio
      if (args.dut_radio is not None):
         dut_radio = args.dut_radio
      if (args.num_sta is not None):
         num_sta = args.num_sta   
      if (args.sta_id is not None):
         sta_id = args.sta_id   
      if (args.dut_ssid is not None):
         dut_ssid = args.dut_ssid
      if (args.lf_ssid is not None):
         lf_ssid = args.lf_ssid
      if (args.security is not None):
         security = args.security
      if (args.password is not None):
         password = args.password
      if (args.password is None):
         password = "[Blank]"
      if (args.lf_upstream is not None):
         lf_upstream = args.lf_upstream
      if (args.dut_upstream is not None):
         dut_upstream = args.dut_upstream
      if (args.protocol is not None):
         protocol = args.protocol
      if (args.min_bps is not None):
         min_bps = int(args.min_bps)*1000000
      if (args.max_bps is not None and args.max_bps is not "same"):
         max_bps = int(args.max_bps)*1000000
      if (args.max_bps is not None and args.max_bps is "same"):
         max_bps = args.min_bps
      if (args.duration is not None):
         duration = (args.duration * 60)/5
      if (args.report_name is not None):
         report_name = args.report_name
    except Exception as e:
      logging.exception(e)
      
      exit(2)

    DB_Lanforge_1 = "Lexus_DUT"
    #Loading the Scenario on Lanforge_1 (Here Considered as DUT) [Created VAP With SSID 'lexusap' on wiphy0 with eth1 as backhaul]
    Scenario_1 = LoadScenario(dut_host, 8080, DB_Lanforge_1)
    
    DB_Lanforge_2 = "LANforge_TEST"
    #Loading the Scenario on Lanforge_2 (Here Considered as LANFORGE Test) [Created VAP With SSID 'lanforge_ap' on wiphy0 with eth2 as backhaul]
    Scenario_2 = LoadScenario(lf_host, 8080, DB_Lanforge_2)

    # Object to Measure the Traffic at VAP
    vap_measure_obj = VAP_Measure(lf_host, 8080)
    
    
    
    
    
    #Create Station and cross connects on Lanforge_1 that connects on VAP on Lanforge_2
    dut_traffic_profile = CreateSTA_CX(dut_host, 8080, dut_radio, num_sta, sta_id, lf_ssid, security, password, dut_upstream, protocol, min_bps, max_bps)
    dut_traffic_profile.build()
    
    
    #Create Station and cross connects on Lanforge_2 that connects on VAP on Lanforge_1 (lexus_ap)
    lf_traffic_profile = CreateSTA_CX(lf_host, 8080, lf_radio, num_sta, sta_id, dut_ssid, security, password, lf_upstream, protocol, min_bps, max_bps)
    lf_traffic_profile.build()


    # Starting Running Traffic 
    lf_traffic_profile.start()
    dut_traffic_profile.start()
    
    
    print("Collecting Throughput Values...")
    dut_temp_obj = Login_DUT(1, "Thread-1", dut_host)
    
    time.sleep(10)
    
    #List for Storing the Total Throughput
    throughput_sta =[]
    throughput_vap =[]
    
    # This loop will get the Data from All the endpoints and sum up to give total Throughput over time
    for i in range(0,int(duration)):
        temp=0
        for j in lf_traffic_profile.endp:
            y=lf_traffic_profile.local_realm.json_get("/endp/"+j).get('endpoint').get('rx rate')
            temp=temp+y
        throughput_sta.append(temp)
        throughput_vap.append(vap_measure_obj.json_get("/port/1/1/vap0000/").get('interface').get('bps rx'))
        dut_temp_obj.run()
        print("Throughput Stations side: ", throughput_sta)
        print("\nThroughput VAP side: ", throughput_vap)
        time.sleep(5)
    print(throughput_sta)
    dut_traffic_profile.cleanup()
    lf_traffic_profile.cleanup()
    GenerateReport(throughput_sta, throughput_vap, dut_temp_obj.data_core1, dut_temp_obj.data_core2, duration)
    
    

    
if __name__ == '__main__':
    main()

