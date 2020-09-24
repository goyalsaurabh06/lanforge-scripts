#!/usr/bin/env python3
'''

  This Script Loads the Existing Scenario and Run the Simultaenous Throughput over time and Generate Report and Plot the Graph
  This Scrip has three classes :
          1. LoadScenario : It will load the existing saved scenario to the Lanforge (Here used for Loading Bridged VAP)
          2. FindPorts : Fetch the L3CX Throughput and VAP Throughput
          3. Login_DUT : This class is specifically used to test the Linux based DUT that has SSH Server. It is used to read the CPU Core temperature during testing
    In this example, Another Lanforge is used as DUT
    It also have a function : GenerateReport that generates the report in xlsx format as well as it plots the Graph of throughput over time with temperature
    It also have Plot function that generates a html page that contains the plot
    
    
    Prerequisite 
    Start the Lanforge Manager both Sides
    
    Installation
    pip install paramiko
    pip install bokeh
    pip install XlsxWriter

    Example
    ./test_l3_scenario_throughput.py --manager 192.168.200.18 --scenario Test_Scenario --report_name test_Report --duration 5 --test_detail "Single Station Test"   
    
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
from bokeh.models import HoverTool, Range1d
from bokeh.layouts import row
from datetime import datetime

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
        print(host+ " : Scenario Loaded...")
        time.sleep(2)




# Generates XLSX Report        
def GenerateReport(scenario, detail, throughput_sta, throughput_vap, absolute_time, relative_time, core1_temp, core2_temp, duration, name):
    workbook = xlsxwriter.Workbook(name)
    worksheet = workbook.add_worksheet()
    worksheet.write('A1',"Scenario Runned: "+scenario+"\n Scenario Details: "+detail)
    worksheet.write('A2', 'ABSOLUTE TIME')
    worksheet.write('B2', 'RELATIVE TIME (ms)')
    worksheet.write('C2', 'THROUGHPUT STATION SIDE (Mbps)')
    worksheet.write('D2', 'THROUGHPUT VAP SIDE (Mbps)')
    worksheet.write('E2', 'CORE 0 TEMP (Degree Celsius)')
    worksheet.write('F2', 'CORE 1 TEMP (Degree Celsius)')
    core1=[]
    core2=[]
   
    
    j=3
    for i in absolute_time:
        worksheet.write('A'+str(j),i)
        j=j+1

    j=3
    for i in relative_time:
        worksheet.write('B'+str(j),i)
        j=j+1
   
    sta_throu=[]
    vap_throu=[]
    j=3
    for i in throughput_sta:
        print(i)
        sta_throu.append(i/1000000)
        worksheet.write('C'+str(j), str(i/1000000)+" Mbps")
        j=j+1
    j=3
    for i in throughput_vap:
        print(i)
        vap_throu.append(i/1000000)
        worksheet.write('D'+str(j), str(i/1000000)+" Mbps")
        j=j+1
    j=3
    for i in core1_temp:
        core1.append(int(str(i).split(':')[1].split('(')[0].split('.')[0].split('+')[1]))
        worksheet.write('E'+str(j),str(i).split(':')[1].split('(')[0] )
        j=j+1
    j=3
    for i in core2_temp:
        core2.append(int(str(i).split(':')[1].split('(')[0].split('.')[0].split('+')[1]))
        worksheet.write('F'+str(j), str(i).split(':')[1].split('(')[0])
        j=j+1

    Time =[]
    for i in range(0,int(duration)*5):
        Time.append(i)
    plot(sta_throu, vap_throu, core1, core2, Time)
    workbook.close()


# Plotting Function for Parameters
def plot(throughput_sta, throughput_vap, core1_temp, core2_temp, Time):

    print(throughput_vap)
    s1 = figure(plot_width=1000, plot_height=600)
    s1.title.text = "WIFI Throughput vs Temperature Plot"
    s1.xaxis.axis_label = "Time "
    s1.yaxis.axis_label = "Throughput in Mbps"
    
    s1.line( Time, throughput_sta, color='black', legend_label ="Throughput Over Station Connections ")
    #s1.circle(Time, throughput_sta, color='red')

    s1.line( Time, throughput_vap, color='blue', legend_label ="Throughput Over VAP ")
    #s1.circle(Time, throughput_vap, color='blue')
    
    s1.extra_y_ranges = {"Temperature": Range1d(start=0, end=150)}
    s1.add_layout(LinearAxis(y_range_name="Temperature", axis_label="Temperature in Degree Celsius"), 'right')
    
    s1.line(Time, core1_temp, y_range_name='Temperature', color='red', legend_label ="CPU CORE 0 TEMPERATURE ")
    #s1.circle(Time, core1_temp, y_range_name='Temperature', color='red')

    s1.line(Time, core2_temp, y_range_name='Temperature', color='green', legend_label ="CPU CORE 1 TEMPERATURE ")
    #s1.circle(Time, core2_temp, y_range_name='Temperature', color='blue')

    show(s1)

    
# Creates the Instance for LFCliBase
class VAP_Measure(LFCliBase):
    def __init__(self, lfclient_host, lfclient_port):
        super().__init__(lfclient_host, lfclient_port)






# Added Standard Function to Fetch L3 CX and VAP Directly 
class FindPorts(LFCliBase):
     def __init__(self, host, port, security_debug_on=False, _exit_on_error=False,_exit_on_fail=False):
        super().__init__(host, port, _debug=security_debug_on, _halt_on_error=_exit_on_error, _exit_on_fail=_exit_on_fail)
        self.host = host
        self.port = port

        #Creating a Realm Object
        self.local_realm = Realm(lfclient_host=host, lfclient_port=port)


     def FindExistingCX(self):

         return self.local_realm.cx_list()

     def FindVAP(self):
         return self.local_realm.vap_list()

# Utility to Find the Traffic Running on Existing CX and VAP   
def PortUtils(host, port, duration, report_name, scenario, detail):

    lf_utils = FindPorts(host, port)
    
    # cx data will be having all parameters of L3 Connections available in the Realm. It is needed to get the names of all L3 CX, which is stored in cx_names. It is required so as we can extract the real time data running on that CX
    cx_data = lf_utils.FindExistingCX()
    #print(cx_data)
    
    # vap_list will have the List of all the vap ports available, This is required to get the VAP names in order to fetch the throughput over that vap
    vap_list =lf_utils.FindVAP()
    vap_measure_obj=VAP_Measure(host,port)

    dut_temp_obj = Login_DUT(1, "Thread-1", "192.168.200.18")

    #print(vap_list)
    vap_names=[]
    for i in vap_list:
        vap_names.append(str(i.keys()).split('.')[2].split('\'')[0])
    print(vap_names[0])

    cx_names = list(cx_data.keys())
    cx_names.remove('handler')
    cx_names.remove('uri')
    absolute_time=[]
    temp_time =[]
    
    Total_Throughput_CX_Side =[]
    Total_Throughput_VAP_Side =[]
    print(lf_utils.local_realm.json_get("/cx/"+cx_names[0]).get(cx_names[0]).get('state'))
    for i in cx_names:
        while(lf_utils.local_realm.json_get("/cx/"+cx_names[0]).get(cx_names[0]).get('state') != 'Run'):
            continue
    offset=int(round(time.time() * 1000))
    for i in range(0,int(duration)):
        temp=0
        for i in cx_names:
            temp=temp+int(lf_utils.local_realm.json_get("/cx/"+i).get(i).get('bps rx a'))
            #temp=temp+lf_utils.local_realm.json_get("/cx/"+i).get(i).get('bps rx b')
        for i in vap_names:
            Total_Throughput_VAP_Side.append(int(vap_measure_obj.json_get("/port/1/1/"+str(i)).get('interface').get('bps rx')))
        absolute_time.append(datetime.now().strftime("%H:%M:%S"))
        temp_time.append(int(round(time.time() * 1000)-offset))
        Total_Throughput_CX_Side.append(temp)
        dut_temp_obj.run()
        time.sleep(5)
    relative_time=[]
    relative_time.append(0)
    for i in range (0,len(temp_time)-1):
        relative_time.append(temp_time[i+1]-temp_time[i])
    print(Total_Throughput_CX_Side)
    print(Total_Throughput_VAP_Side)
    GenerateReport(scenario, detail, Total_Throughput_CX_Side, Total_Throughput_VAP_Side, absolute_time, relative_time, dut_temp_obj.data_core1, dut_temp_obj.data_core2, duration, report_name)
    
# main method
def main():


    parser = argparse.ArgumentParser(description="Test Scenario of DUT Temperature measurement along with simultaneous throughput on VAP as well as stations")
    
    parser.add_argument("-m", "--manager", type=str, help="Enter the address of Lanforge Manager (By default localhost)")
    parser.add_argument("-sc", "--scenario", type=str, help="Enter the Name of the Scenario you want to load (by Default DFLT)")

    parser.add_argument("-t", "--duration", type=int, help="Enter the Time for which you want to run test (In Minutes)")
    parser.add_argument("-o", "--report_name", type=str, help="Enter the Name of the Output file ('Report.xlsx')")
    parser.add_argument("-td", "--test_detail", type=str, help="Enter the Test Detail in Quotes ")
    
    args = None
     
    try:
      args = parser.parse_args()
      # Lanforge Manager IP Address
      if (args.manager is None):
         manager = "localhost"
      if (args.manager is not None):
         manager = args.manager
      if (args.scenario is not None):
         scenario = args.scenario
      if (args.duration is not None):
         duration = (args.duration * 60)/5
      if (args.report_name is not None):
         report_name = args.report_name
      if (args.duration is None):
         duration = (1 * 60)/5
      if (args.report_name is None):
         report_name = "report.xlsx"
      if (args.test_detail is not None):
         test_detail = args.test_detail
      if (args.test_detail is None):
         test_detail = "Blank test"
    except Exception as e:
      logging.exception(e)
      exit(2)
    

    
    # Loading DUT Scenario
    Scenario_1 = LoadScenario("192.168.200.18", 8080, "Lexus_Dut")
    
    
    # Loading LF Scenario
    DB_Lanforge_2 = "LF_Device"
    Scenario_2 = LoadScenario(manager, 8080, scenario)
    #Wait for Sometime
    time.sleep(10)
   
    # Port Utility function for reading CX and VAP
    PortUtils(manager,8080, duration, report_name, scenario, test_detail)
    
    
        

    
if __name__ == '__main__':
    main()

