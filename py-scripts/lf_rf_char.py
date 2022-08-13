#!/usr/bin/env python3

"""
NAME: lf_rf_test.py

PURPOSE:
RF Characteristics Test

SETUP:
There need to be a vAP in a Virtual Router  on LANforge , goal is to eventually have autogenerated

EXAMPLE:


COPYRIGHT:
    Copyright 2023 Candela Technologies Inc
    License: Free to distribute and modify. LANforge systems must be licensed.

INCLUDE_IN_README
"""
import argparse
import sys
import os
import logging
import importlib
import datetime
import pandas as pd
import requests
from pandas import json_normalize
import json
import traceback
import csv
import time
import re
import platform

sys.path.append(os.path.join(os.path.abspath(__file__ + "../../../")))
lanforge_api = importlib.import_module("lanforge_client.lanforge_api")

from lanforge_client.lanforge_api import LFJsonQuery
from lanforge_client.lanforge_api import LFJsonCommand
from lanforge_client.lanforge_api import LFSession
LFUtils = importlib.import_module("py-json.LANforge.LFUtils")


lf_json_api = importlib.import_module("py-scripts.lf_json_api")
lf_report = importlib.import_module("py-scripts.lf_report")
lf_graph = importlib.import_module("py-scripts.lf_graph")
lf_bar_graph = lf_graph.lf_bar_graph

lf_kpi_csv = importlib.import_module("py-scripts.lf_kpi_csv")
lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")

realm = importlib.import_module("py-json.realm")
Realm = realm.Realm


logger = logging.getLogger(__name__)


if sys.version_info[0] != 3:
    print("This script requires Python 3")
    exit(1)


# RF Characteristics Test
# TODO try to have utilites in own file
class lf_rf_char(Realm):
    def __init__(self,
                 lf_mgr=None,
                 lf_port=None,
                 lf_user=None,
                 lf_passwd=None,
                 debug=False
                 ):
        self.lf_mgr = lf_mgr
        self.lf_port = lf_port
        self.lf_user = lf_user
        self.lf_passwd = lf_passwd
        self.debug = debug
        self.vap_port = ''
        self.radio = ''
        self.vap = ''
        self.port = ''
        self.shelf = ''
        self.resource = ''
        self.duration = ''
        self.polling_interval = ''
        # create api_json
        self.json_api = lf_json_api.lf_json_api(lf_mgr=self.lf_mgr,
                                                lf_port=self.lf_port,
                                                lf_user=self.lf_user,
                                                lf_passwd=self.lf_passwd)

        # create a session
        #self.session = LFSession(lfclient_url="http://{lf_mgr}:{lf_port}".format(lf_mgr=self.lf_mgr, lf_port=self.lf_port),
        self.session = LFSession(lfclient_url="http://%s:8080" % self.lf_mgr,
                                 debug=debug,
                                 connection_timeout_sec=4.0,
                                 stream_errors=True,
                                 stream_warnings=True,
                                 require_session=True,
                                 exit_on_error=True)
        # type hinting
        self.command: LFJsonCommand
        self.command = self.session.get_command()
        self.query: LFJsonQuery
        self.query = self.session.get_query()

        # vap configuration
        self.shelf = ''
        self.resource = ''
        self.port_name = ''
        self.vap_radio = ''
        self.vap_channel = ''
        self.vap_antenna = ''

        # logging
        self.debug = debug


    def clear_port_counters(self):
        self.shelf, self.resource, self.port_name, *nil = LFUtils.name_to_eid(self.vap_port)
        # may have to add extra to
        self.command.post_clear_port_counters(shelf=self.shelf,
                                              resource=self.resource,
                                              port=self.port_name,
                                              extra=None)

        

    def modify_radio(self):

        self.shelf, self.resource, self.port_name, *nil = LFUtils.name_to_eid(self.vap_radio)
        self.command.post_set_wifi_radio(
            shelf=self.shelf,
            resource=self.resource,
            radio=self.port_name, 
            antenna=self.vap_antenna,
            channel=self.vap_channel,
            debug=self.debug)

    def start(self):
        logger.info("clear port counters")
        self.clear_port_counters()
        # first read with
        self.json_api.port=self.vap_port
        self.json_api.update_port_info()
        self.json_api.csv_mode='write'
        self.json_api.update_csv_mode()
        self.json_api.request = 'port'
        self.json_api.get_request_port_information()

        self.json_api.csv_mode='append'
        self.json_api.update_csv_mode()

        cur_time = datetime.datetime.now()
        end_time = self.parse_time(self.duration) + cur_time
        polling_interval_seconds = self.duration_time_to_seconds(self.polling_interval)
        while cur_time < end_time:
            interval_time = cur_time + datetime.timedelta(seconds=polling_interval_seconds)

            while cur_time < interval_time:
                cur_time = datetime.datetime.now()
                time.sleep(.2)
            json_port_stats, *nil = self.json_api.get_request_port_information()
            # todo read the info from the data frame

        self.json_api.csv_mode='write'
        self.json_api.update_csv_mode()
        # TODO make the get_request more generic just set the request
        self.json_api.request = 'wifi-stats'
        json_wifi_stats, *nil = self.json_api.get_request_wifi_stats_information()

        return json_port_stats, json_wifi_stats

            # gather interval samples read stations to get RX Bytes, TX Bytes, TX Retries, 

        # read the extended mgr tab to get rx tx MCS, NSS



    def read_wifi_stats(self):
        pass

    def read_stations(self):
        pass


def main():
    # arguments
    parser = argparse.ArgumentParser(
        prog='lf_rf_char.py',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog='''\
            lf_rf_char.py : RF Characteristics test
            ''',
        description='''\
lf_rf_char.py
-----------

Summary :
---------

Example :
---------
            ''')
    # LANforge configuration
    parser.add_argument("--lf_mgr", type=str, help="address of the LANforge GUI machine (localhost is default)", default='localhost')
    parser.add_argument("--lf_port", help="IP Port the LANforge GUI is listening on (8080 is default)", default=8080)
    parser.add_argument("--lf_user", type=str, help="user: lanforge", default='lanforge')
    parser.add_argument("--lf_passwd", type=str, help="passwd: lanforge", default='lanforge')
    parser.add_argument("--vap_port", type=str, help=" port : 1.1.vap3  provide full eid  (endpoint id")
    parser.add_argument("--vap_radio", type=str, help=" --vap_radio wiphy0")
    parser.add_argument("--vap_channel", type=str, help=" --vap_channel '36'  channel of the radio e.g. 6 (2.4G) , 36 (5G), ")
    parser.add_argument("--vap_antenna", help='number of spatial streams: 0 Diversity (All), 1 Fixed-A (1x1), 4 AB (2x2), 7 ABC (3x3), 8 ABCD (4x4), 9 (8x8)')

    # Reporting Configuration
    parser.add_argument('--local_lf_report_dir', help='--local_lf_report_dir override the report path, primary use when running test in test suite', default="")
    parser.add_argument("--test_rig", default="lanforge",
                        help="test rig for kpi.csv, testbed that the tests are run on")
    parser.add_argument("--test_tag", default="kpi_generation",
                        help="test tag for kpi.csv,  test specific information to differenciate the test")
    parser.add_argument("--dut_hw_version", default="hw_01",
                        help="dut hw version for kpi.csv, hardware version of the device under test")
    parser.add_argument("--dut_sw_version", default="sw_01",
                        help="dut sw version for kpi.csv, software version of the device under test")
    parser.add_argument("--dut_model_num", default="can_ap",
                        help="dut model for kpi.csv,  model number / name of the device under test")
    parser.add_argument("--dut_serial_num", default="can_123",
                        help="dut serial num for kpi.csv,  model serial number ")

    parser.add_argument("--test_priority", default="95",
                        help="dut model for kpi.csv,  test-priority is arbitrary number")
    parser.add_argument("--test_id", default="kpi_unit_test", help="test-id for kpi.csv,  script or test name")
    parser.add_argument("--csv_outfile", default="lf_rf_char", help=" csv outfile")


    # Logging Configuration
    parser.add_argument('--log_level', default=None, help='Set logging level: debug | info | warning | error | critical')
    parser.add_argument("--lf_logger_config_json", help="--lf_logger_config_json <json file> , json configuration of logger")
    parser.add_argument('--debug', help='Legacy debug flag', action='store_true')

    # Test Configuration
    parser.add_argument('--duration', help="--duration <seconds>", default='20s')
    parser.add_argument('--polling_interval', help="--polling_interval <seconds>", default='1s')

    args = parser.parse_args()

    # set up logger
    logger_config = lf_logger_config.lf_logger_config()

    # set the logger level to debug
    if args.log_level:
        logger_config.set_level(level=args.log_level)

    # lf_logger_config_json will take presidence to changing debug levels
    if args.lf_logger_config_json:
        # logger_config.lf_logger_config_json = "lf_logger_config.json"
        logger_config.lf_logger_config_json = args.lf_logger_config_json
        logger_config.load_lf_logger_config()

    # Gather data for test reporting
    # for kpi.csv generation
    logger.info("read in command line paramaters")
    local_lf_report_dir = args.local_lf_report_dir
    test_rig = args.test_rig
    test_tag = args.test_tag
    dut_hw_version = args.dut_hw_version
    dut_sw_version = args.dut_sw_version
    dut_model_num = args.dut_model_num
    dut_serial_num = args.dut_serial_num
    # test_priority = args.test_priority  # this may need to be set per test
    test_id = args.test_id

    # Create report, when running with the test framework (lf_check.py)
    # results need to be in the same directory
    logger.info("configure reporting")
    if local_lf_report_dir != "":
        report = lf_report.lf_report(
            _path=local_lf_report_dir,
            _results_dir_name="rf_char",
            _output_html="rf_char.html",
            _output_pdf="rf_char.pdf")
    else:
        report = lf_report.lf_report(
            _results_dir_name="rf_characteristics_test",
            _output_html="rf_char.html",
            _output_pdf="rf_char.pdf")

    kpi_path = report.get_report_path()
    logger.info("Report and kpi_path :{kpi_path}".format(kpi_path=kpi_path))

    kpi_csv = lf_kpi_csv.lf_kpi_csv(
        _kpi_path=kpi_path,
        _kpi_test_rig=test_rig,
        _kpi_test_tag=test_tag,
        _kpi_dut_hw_version=dut_hw_version,
        _kpi_dut_sw_version=dut_sw_version,
        _kpi_dut_model_num=dut_model_num,
        _kpi_dut_serial_num=dut_serial_num,
        _kpi_test_id=test_id)

    if args.csv_outfile is not None:
        current_time = time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
        csv_outfile = "{}_{}_lf_rf_char.csv".format(
            args.csv_outfile, current_time)
        csv_outfile = report.file_add_path(csv_outfile)
        logger.info("csv output file : {}".format(csv_outfile))

    # begin creating the report
    report.set_title("RF Characteristics Test")
    report.build_banner_left()
    report.start_content_div2()
    report.set_obj_html("Objective", "RF Characteristics Test: Report Rx and Tx characteristics")
    report.build_objective()

    test_setup_info = {
        "DUT Name": args.dut_model_num,
        "DUT Hardware Version": args.dut_hw_version,
        "DUT Software Version": args.dut_sw_version,
        "DUT Serial Number": args.dut_serial_num,
    }

    report.set_table_title("Device Under Test Information")
    report.build_table_title()
    report.test_setup_table(value="Device Under Test", test_setup_data=test_setup_info)

    test_input_info = {
        "LANforge ip": args.lf_mgr,
        "LANforge port": args.lf_port,
        "Test Duration": args.duration,
        "Polling Interval": args.polling_interval,
        "vAP Channel": args.vap_channel
    }

    report.set_table_title("Test Configuration")
    report.build_table_title()
    report.test_setup_table(value="Test Configuration", test_setup_data=test_input_info)



    # Set up the RF Characteristic test
    logger.info("Configure RF Characteristic test")
    rf_char = lf_rf_char(lf_mgr=args.lf_mgr,
                            lf_port=args.lf_port,
                            lf_user=args.lf_user,
                            lf_passwd=args.lf_passwd,
                            debug=args.debug)

    if not args.vap_radio:
        logger.info("No radio name provided")
        exit(1)

    # Start traffic : Currently manually done
    # TODO this needs to be a list to sweep though channels
    rf_char.vap_radio = args.vap_radio
    rf_char.vap_channel = args.vap_channel
    rf_char.vap_antenna = args.vap_antenna
    rf_char.modify_radio()

    # TODO detect that the station is back up
    rf_char.vap_port = args.vap_port
    rf_char.clear_port_counters()

    rf_char.duration = args.duration
    rf_char.polling_interval = args.polling_interval

    # run the test
    json_port_stats, json_wifi_stats, *nil = rf_char.start()

    
    # get dataset for port
    wifi_stats_json = json_wifi_stats[args.vap_port]

    # retrieve rx data from json for MODE
    rx_mode = []
    rx_mode_value_str = []
    rx_mode_value = []
    rx_mode_value_percent = []
    rx_mode_total_count = 0

    # TODO change value to count
    # retrieve each mode value from json 
    for iterator in wifi_stats_json:
        if 'rx_mode' in iterator:
            rx_mode.append(iterator)
            rx_mode_value_str.append(str(wifi_stats_json[iterator]))
            rx_mode_value.append(wifi_stats_json[iterator])
            rx_mode_total_count += wifi_stats_json[iterator]

    # calculate percentages
    for rx_mode_count in rx_mode_value:
        rx_mode_value_percent.append(round((rx_mode_count/rx_mode_total_count)*100, 2)) 

    # print(rx_mode)
    # print(rx_mode_value)

    # rx_mode values
    report.set_table_title("Rx Mode Histogram")
    report.build_table_title()


    df_rx_mode = pd.DataFrame({" Rx Mode ": [k for k in rx_mode], " Total Packets ": [i for i in rx_mode_value],
        " Percentage ": [j for j in rx_mode_value_percent]})

    report.set_table_dataframe(df_rx_mode)
    report.build_table()


    # RX MODE
    graph = lf_bar_graph(_data_set=[rx_mode_value_percent],
                        _xaxis_name="RX Mode",
                        _yaxis_name="Percentage Mode",
                        _xaxis_categories=rx_mode,
                        _graph_image_name="RX Mode",
                        _label=["Percentage Total Packets"],
                        _color=['blue'],
                        _color_edge='black',
                        _figsize=(16,7),
                        _grp_title='RX Mode',
                        _xaxis_step=1,
                        _show_bar_value=True,
                        _text_font=7,
                        _text_rotation=45,
                        _xticks_font=7,
                        _legend_loc="best",
                        _legend_box=(1, 1),
                        _legend_ncol=1,
                        _legend_fontsize=None,
                        _enable_csv=False)
    
    graph_png = graph.build_bar_graph()
    report.set_graph_image(graph_png)
    report.move_graph_image()
    report.build_graph()

    # retrieve tx data from json for MODE
    tx_mode = []
    tx_mode_value_str = []
    tx_mode_value = []
    tx_mode_value_percent = []
    tx_mode_total_count = 0

    # TODO change value to count
    # retrieve each mode value from json 
    for iterator in wifi_stats_json:
        if 'tx_mode' in iterator:
            tx_mode.append(iterator)
            tx_mode_value_str.append(str(wifi_stats_json[iterator]))
            tx_mode_value.append(wifi_stats_json[iterator])
            tx_mode_total_count += wifi_stats_json[iterator]

    # calculate percentages
    for tx_mode_count in tx_mode_value:
        tx_mode_value_percent.append(round((tx_mode_count/tx_mode_total_count)*100, 2)) 

    # print(tx_mode)
    # print(tx_mode_value)

    # tx_mode values
    report.set_table_title("Tx Mode Histogram")
    report.build_table_title()


    df_tx_mode = pd.DataFrame({" Tx Mode ": [k for k in tx_mode], " Total Packets ": [i for i in tx_mode_value],
        " Percentage ": [j for j in tx_mode_value_percent]})

    report.set_table_dataframe(df_tx_mode)
    report.build_table()

    # TX MODE
    graph = lf_bar_graph(_data_set=[tx_mode_value_percent],
                        _xaxis_name="TX Mode",
                        _yaxis_name="Percentage Mode",
                        _xaxis_categories=tx_mode,
                        _graph_image_name="TX Mode",
                        _label=["Percentage Total Packets"],
                        _color=['blue'],
                        _color_edge='black',
                        _figsize=(16,7),
                        _grp_title='TX Mode',
                        _xaxis_step=1,
                        _show_bar_value=True,
                        _text_font=7,
                        _text_rotation=45,
                        _xticks_font=7,
                        _legend_loc="best",
                        _legend_box=(1, 1),
                        _legend_ncol=1,
                        _legend_fontsize=None,
                        _enable_csv=False)
    
    graph_png = graph.build_bar_graph()
    report.set_graph_image(graph_png)
    report.move_graph_image()
    report.build_graph()


    # retrieve rx data from json for BW
    rx_bw = []
    rx_bw_value_str = []
    rx_bw_value = []
    rx_bw_value_percent = []
    rx_bw_total_count = 0

    # TODO change value to count
    # retrieve each nss value from json 
    for iterator in wifi_stats_json:
        if 'rx_bw' in iterator:
            rx_bw.append(iterator)
            rx_bw_value_str.append(str(wifi_stats_json[iterator]))
            rx_bw_value.append(wifi_stats_json[iterator])
            rx_bw_total_count += wifi_stats_json[iterator]

    # calculate percentages
    for rx_bw_count in rx_bw_value:
        rx_bw_value_percent.append(round((rx_bw_count/rx_bw_total_count)*100, 2)) 

    # print(rx_bw)
    # print(rx_bw_value)

    # rx_bw values
    report.set_table_title("Rx BW Histogram")
    report.build_table_title()


    df_rx_bw = pd.DataFrame({" Rx BW ": [k for k in rx_bw], " Total Packets ": [i for i in rx_bw_value],
        " Percentage ": [j for j in rx_bw_value_percent]})

    report.set_table_dataframe(df_rx_bw)
    report.build_table()

    # RX BW
    graph = lf_bar_graph(_data_set=[rx_bw_value_percent],
                        _xaxis_name="RX BW",
                        _yaxis_name="Percentage BW",
                        _xaxis_categories=rx_bw,
                        _graph_image_name="RX BW",
                        _label=["Percentage Total Packets"],
                        _color=['blue'],
                        _color_edge='black',
                        _figsize=(16,7),
                        _grp_title='RX BW',
                        _xaxis_step=1,
                        _show_bar_value=True,
                        _text_font=7,
                        _text_rotation=45,
                        _xticks_font=7,
                        _legend_loc="best",
                        _legend_box=(1, 1),
                        _legend_ncol=1,
                        _legend_fontsize=None,
                        _enable_csv=False)
    
    graph_png = graph.build_bar_graph()
    report.set_graph_image(graph_png)
    report.move_graph_image()
    report.build_graph()

    # retrieve tx data from json for BW
    tx_bw = []
    tx_bw_value_str = []
    tx_bw_value = []
    tx_bw_value_percent = []
    tx_bw_total_count = 0

    # TODO change value to count
    # retrieve each nss value from json 
    for iterator in wifi_stats_json:
        if 'tx_bw' in iterator:
            tx_bw.append(iterator)
            tx_bw_value_str.append(str(wifi_stats_json[iterator]))
            tx_bw_value.append(wifi_stats_json[iterator])
            tx_bw_total_count += wifi_stats_json[iterator]

    # calculate percentages
    for tx_bw_count in tx_bw_value:
        tx_bw_value_percent.append(round((tx_bw_count/tx_bw_total_count)*100, 2)) 

    # print(tx_bw)
    # print(tx_bw_value)

    # tx_bw values
    report.set_table_title("Tx BW Histogram")
    report.build_table_title()


    df_tx_bw = pd.DataFrame({" Tx BW ": [k for k in tx_bw], " Total Packets ": [i for i in tx_bw_value],
        " Percentage ": [j for j in tx_bw_value_percent]})

    report.set_table_dataframe(df_tx_bw)
    report.build_table()

    # TX BW
    graph = lf_bar_graph(_data_set=[tx_bw_value_percent],
                        _xaxis_name="TX BW",
                        _yaxis_name="Percentage BW",
                        _xaxis_categories=tx_bw,
                        _graph_image_name="TX BW",
                        _label=["Percentage Total Packets"],
                        _color=['blue'],
                        _color_edge='black',
                        _figsize=(16,7),
                        _grp_title='TX BW',
                        _xaxis_step=1,
                        _show_bar_value=True,
                        _text_font=7,
                        _text_rotation=45,
                        _xticks_font=7,
                        _legend_loc="best",
                        _legend_box=(1, 1),
                        _legend_ncol=1,
                        _legend_fontsize=None,
                        _enable_csv=False)
    
    graph_png = graph.build_bar_graph()
    report.set_graph_image(graph_png)
    report.move_graph_image()
    report.build_graph()



    # retrieve rx data from json for NSS
    rx_nss = []
    rx_nss_value_str = []
    rx_nss_value = []
    rx_nss_value_percent = []
    rx_nss_total_count = 0

    # TODO change value to count
    # retrieve each nss value from json 
    for iterator in wifi_stats_json:
        if 'rx_nss' in iterator:
            rx_nss.append(iterator)
            rx_nss_value_str.append(str(wifi_stats_json[iterator]))
            rx_nss_value.append(wifi_stats_json[iterator])
            rx_nss_total_count += wifi_stats_json[iterator]

    # calculate percentages
    for rx_nss_count in rx_nss_value:
        rx_nss_value_percent.append(round((rx_nss_count/rx_nss_total_count)*100, 2)) 

    # print(rx_nss)
    # print(rx_nss_value)

    # rx_nss values
    report.set_table_title("Rx NSS Histogram")
    report.build_table_title()


    df_rx_nss = pd.DataFrame({" Rx NSS ": [k for k in rx_nss], " Total Packets ": [i for i in rx_nss_value],
        " Percentage ": [j for j in rx_nss_value_percent]})

    report.set_table_dataframe(df_rx_nss)
    report.build_table()

    # RX NSS
    graph = lf_bar_graph(_data_set=[rx_nss_value_percent],
                        _xaxis_name="RX NSS",
                        _yaxis_name="Percentage NSS",
                        _xaxis_categories=rx_nss,
                        _graph_image_name="RX NSS",
                        _label=["Percentage Total Packets"],
                        _color=['blue'],
                        _color_edge='black',
                        _figsize=(16,7),
                        _grp_title='RX NSS',
                        _xaxis_step=1,
                        _show_bar_value=True,
                        _text_font=7,
                        _text_rotation=45,
                        _xticks_font=7,
                        _legend_loc="best",
                        _legend_box=(1, 1),
                        _legend_ncol=1,
                        _legend_fontsize=None,
                        _enable_csv=False)
    
    graph_png = graph.build_bar_graph()
    report.set_graph_image(graph_png)
    report.move_graph_image()
    report.build_graph()


    # retrieve tx data from json for NSS
    tx_nss = []
    tx_nss_value_str = []
    tx_nss_value = []
    tx_nss_value_percent = []
    tx_nss_total_count = 0

    # TODO change value to count
    # retrieve each nss value from json 
    for iterator in wifi_stats_json:
        if 'tx_nss' in iterator:
            tx_nss.append(iterator)
            tx_nss_value_str.append(str(wifi_stats_json[iterator]))
            tx_nss_value.append(wifi_stats_json[iterator])
            tx_nss_total_count += wifi_stats_json[iterator]

    # calculate percentages
    for tx_nss_count in tx_nss_value:
        tx_nss_value_percent.append(round((tx_nss_count/tx_nss_total_count)*100, 2)) 

    # print(tx_nss)
    # print(tx_nss_value)

    # tx_nss values
    report.set_table_title("Tx NSS Histogram")
    report.build_table_title()


    df_tx_nss = pd.DataFrame({" Tx NSS ": [k for k in tx_nss], " Total Packets ": [i for i in tx_nss_value],
        " Percentage ": [j for j in tx_nss_value_percent]})

    report.set_table_dataframe(df_tx_nss)
    report.build_table()

    # TX NSS
    graph = lf_bar_graph(_data_set=[tx_nss_value_percent],
                        _xaxis_name="TX NSS",
                        _yaxis_name="Percentage NSS",
                        _xaxis_categories=tx_nss,
                        _graph_image_name="TX NSS",
                        _label=["Percentage Total Packets"],
                        _color=['blue'],
                        _color_edge='black',
                        _figsize=(16,7),
                        _grp_title='TX NSS',
                        _xaxis_step=1,
                        _show_bar_value=True,
                        _text_font=7,
                        _text_rotation=45,
                        _xticks_font=7,
                        _legend_loc="best",
                        _legend_box=(1, 1),
                        _legend_ncol=1,
                        _legend_fontsize=None,
                        _enable_csv=False)
    
    graph_png = graph.build_bar_graph()
    report.set_graph_image(graph_png)
    report.move_graph_image()
    report.build_graph()




    # retrieve rx data from json for MCS
    rx_mcs = []
    rx_mcs_value_str = []
    rx_mcs_value = []
    rx_mcs_value_percent = []
    rx_mcs_total_count = 0

    # TODO change value to count
    # retrieve each mcs value from json 
    for iterator in wifi_stats_json:
        if 'rx_mcs' in iterator:
            rx_mcs.append(iterator)
            rx_mcs_value_str.append(str(wifi_stats_json[iterator]))
            rx_mcs_value.append(wifi_stats_json[iterator])
            rx_mcs_total_count += wifi_stats_json[iterator]

    # calculate percentages
    for rx_mcs_count in rx_mcs_value:
        rx_mcs_value_percent.append(round((rx_mcs_count/rx_mcs_total_count)*100, 2)) 

    # print(rx_mcs)
    # print(rx_mcs_value)

    # rx_mcs values
    report.set_table_title("Rx MCS Histogram")
    report.build_table_title()


    df_rx_mcs = pd.DataFrame({" Rx MCS ": [k for k in rx_mcs], " Total Packets ": [i for i in rx_mcs_value],
        " Percentage ": [j for j in rx_mcs_value_percent]})

    report.set_table_dataframe(df_rx_mcs)
    report.build_table()

    # RX MCS encoding
    graph = lf_bar_graph(_data_set=[rx_mcs_value_percent],
                        _xaxis_name="RX MCS encoding",
                        _yaxis_name="Percentage Received Packets with MCS encoding",
                        _xaxis_categories=rx_mcs,
                        _graph_image_name="RX MCS encoding",
                        _label=["Percentage Total Packets"],
                        _color=['blue'],
                        _color_edge='black',
                        _figsize=(16,7),
                        _grp_title='RX MCS encoding',
                        _xaxis_step=1,
                        _show_bar_value=True,
                        _text_font=7,
                        _text_rotation=45,
                        _xticks_font=7,
                        _legend_loc="best",
                        _legend_box=(1, 1),
                        _legend_ncol=1,
                        _legend_fontsize=None,
                        _enable_csv=False)
    
    graph_png = graph.build_bar_graph()
    report.set_graph_image(graph_png)
    report.move_graph_image()
    report.build_graph()

    # retrieve tx  mcs value from json 
    tx_mcs = []
    tx_mcs_value_str = []
    tx_mcs_value = []
    tx_mcs_value_percent = []
    tx_mcs_total_count = 0

    for iterator in wifi_stats_json:
        if 'tx_mcs' in iterator:
            tx_mcs.append(iterator)
            tx_mcs_value_str.append(str(wifi_stats_json[iterator]))
            tx_mcs_value.append(wifi_stats_json[iterator])
            tx_mcs_total_count += wifi_stats_json[iterator]

    # calculate percentages
    for tx_mcs_count in tx_mcs_value:
        if tx_mcs_total_count == 0:
            tx_mcs_value_percent.append(0)
        else:
            tx_mcs_value_percent.append(round((tx_mcs_count/tx_mcs_total_count)*100, 2)) 

    # print(tx_mcs)
    # print(tx_mcs_value)

    # tx_mcs values
    report.set_table_title("Tx MCS Histogram")
    report.build_table_title()


    df_tx_mcs = pd.DataFrame({" Tx MCS ": [k for k in tx_mcs], " Total Packets ": [i for i in tx_mcs_value],
        " Percentage ": [j for j in tx_mcs_value_percent]})

    report.set_table_dataframe(df_tx_mcs)
    report.build_table()

    # TX MCS encoding
    graph = lf_bar_graph(_data_set=[tx_mcs_value_percent],
                        _xaxis_name="TX MCS encoding",
                        _yaxis_name="Percentage Received Packets with MCS encoding",
                        _xaxis_categories=tx_mcs,
                        _graph_image_name="TX MCS encoding",
                        _label=["Percentage Total Packets"],
                        _color=['blue'],
                        _color_edge='black',
                        _figsize=(16,7),
                        _grp_title='TX MCS encoding',
                        _xaxis_step=1,
                        _show_bar_value=True,
                        _text_font=7,
                        _text_rotation=45,
                        _xticks_font=7,
                        _legend_loc="best",
                        _legend_box=(1, 1),
                        _legend_ncol=1,
                        _legend_fontsize=None,
                        _enable_csv=False)
    
    graph_png = graph.build_bar_graph()
    report.set_graph_image(graph_png)
    report.move_graph_image()
    report.build_graph()

    # retrieve rx data from json for ampdu
    rx_ampdu = []
    rx_ampdu_value_str = []
    rx_ampdu_value = []
    rx_ampdu_value_percent = []
    rx_ampdu_total_count = 0

    # TODO change value to count
    # retrieve each mcs value from json 
    for iterator in wifi_stats_json:
        if 'rx_ampdu' in iterator:
            rx_ampdu.append(iterator)
            rx_ampdu_value_str.append(str(wifi_stats_json[iterator]))
            rx_ampdu_value.append(wifi_stats_json[iterator])
            rx_ampdu_total_count += wifi_stats_json[iterator]

    # calculate percentages
    for rx_ampdu_count in rx_ampdu_value:
        rx_ampdu_value_percent.append(round((rx_ampdu_count/rx_ampdu_total_count)*100, 2)) 

    # print(rx_ampdu)
    # print(rx_ampdu_value)

    # rx_ampdu values
    report.set_table_title("Rx ampdu Histogram")
    report.build_table_title()


    df_rx_ampdu = pd.DataFrame({" Rx ampdu ": [k for k in rx_ampdu], " Total Packets ": [i for i in rx_ampdu_value],
        " Percentage ": [j for j in rx_ampdu_value_percent]})

    report.set_table_dataframe(df_rx_ampdu)
    report.build_table()

    # RX ampdu encoding
    graph = lf_bar_graph(_data_set=[rx_ampdu_value_percent],
                        _xaxis_name="RX ampdu",
                        _yaxis_name="Percentage Received Packets ampdu",
                        _xaxis_categories=rx_ampdu,
                        _graph_image_name="RX ampdu encoding",
                        _label=["Percentage Total Packets"],
                        _color=['blue'],
                        _color_edge='black',
                        _figsize=(16,7),
                        _grp_title='RX ampdu',
                        _xaxis_step=1,
                        _show_bar_value=True,
                        _text_font=7,
                        _text_rotation=45,
                        _xticks_font=7,
                        _legend_loc="best",
                        _legend_box=(1, 1),
                        _legend_ncol=1,
                        _legend_fontsize=None,
                        _enable_csv=False)
    
    graph_png = graph.build_bar_graph()
    report.set_graph_image(graph_png)
    report.move_graph_image()
    report.build_graph()

    # retrieve tx ampdu value from json 
    tx_ampdu = []
    tx_ampdu_value_str = []
    tx_ampdu_value = []
    tx_ampdu_value_percent = []
    tx_ampdu_total_count = 0

    for iterator in wifi_stats_json:
        if 'tx_ampdu' in iterator:
            tx_ampdu.append(iterator)
            tx_ampdu_value_str.append(str(wifi_stats_json[iterator]))
            tx_ampdu_value.append(wifi_stats_json[iterator])
            tx_ampdu_total_count += wifi_stats_json[iterator]

    # calculate percentages
    for tx_ampdu_count in tx_ampdu_value:
        if tx_ampdu_total_count == 0:
            tx_ampdu_value_percent.append(0)
        else:
            tx_ampdu_value_percent.append(round((tx_ampdu_count/tx_ampdu_total_count)*100, 2)) 

    # print(tx_ampdu)
    # print(tx_ampdu_value)

    # tx_ampdu values
    report.set_table_title("Tx ampdu Histogram")
    report.build_table_title()


    df_tx_ampdu = pd.DataFrame({" Tx ampdu ": [k for k in tx_ampdu], " Total Packets ": [i for i in tx_ampdu_value],
        " Percentage ": [j for j in tx_ampdu_value_percent]})

    report.set_table_dataframe(df_tx_ampdu)
    report.build_table()

    # TX MCS encoding
    graph = lf_bar_graph(_data_set=[tx_ampdu_value_percent],
                        _xaxis_name="TX ampdu",
                        _yaxis_name="Percentage Received Packets ampdu",
                        _xaxis_categories=tx_ampdu,
                        _graph_image_name="TX ampdu encoding",
                        _label=["Percentage Total Packets"],
                        _color=['blue'],
                        _color_edge='black',
                        _figsize=(16,7),
                        _grp_title='TX ampdu',
                        _xaxis_step=1,
                        _show_bar_value=True,
                        _text_font=7,
                        _text_rotation=45,
                        _xticks_font=7,
                        _legend_loc="best",
                        _legend_box=(1, 1),
                        _legend_ncol=1,
                        _legend_fontsize=None,
                        _enable_csv=False)
    
    graph_png = graph.build_bar_graph()
    report.set_graph_image(graph_png)
    report.move_graph_image()
    report.build_graph()




    # Finish the report
    report.build_footer()
    report.copy_js()

    report.write_html_with_timestamp()
    report.write_index_html()

    if platform.system() == 'Linux':
        report.write_pdf_with_timestamp(_page_size='A4', _orientation='Landscape')




if __name__ == "__main__":
    main()
