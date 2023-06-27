#!/usr/bin/env python3

"""
NAME: create_l3_stations.py

PURPOSE:
            This script creates variable number of stations with individual cross-connects and endpoints.
            Stations are set to UP state, but cross-connections remain stopped.

EXAMPLE:
        Default configuration:
            Endpoint A: List of stations (default: 2 stations, unless specified with --num_stations)
            Endpoint B: eth1

        * Creating specified number of station names and Layer-3 CX :

            ./create_l3_stations.py --mgr localhost --num_stations 5 --radio wiphy0 --ssid SSID --password Password@123 --security wpa2

        * Creating stations with specified start ID (--num_template) and Layer-3 CX :

            ./create_l3_stations.py --mgr localhost --number_template 007 --radio wiphy0 --ssid SSID --password Password@123 --security wpa2

        * Creating stations with specified names and Layer-3 CX :

            ./create_l3_stations.py --mgr localhost --station_list sta00,sta01 --radio wiphy0 --ssid SSID --password Password@123 --security wpa2

        * For creating stations and layer-3 cx creation on particular specified AP mac & mode:

            ./create_l3_stations.py --mgr localhost --radio wiphy0 --ssid SSID --password Password@123 --security wpa2 --ap "00:0e:8e:78:e1:76"
            --mode 13

        * For creating specified number of stations and layer-3 cx creation (Customise the traffic and upstream port):

            ./create_l3_stations.py --mgr localhost --station_list sta00  --radio wiphy0 --ssid SSID --password Password@123 --security wpa2
             --upstream_port eth2 --endp_a_min 6200000 --endp_b_min 6200000

      Generic command layout:

        python3 ./create_l3_stations.py
            --upstream_port eth1
            --radio wiphy0
            --num_stations 32
            --security {open|wep|wpa|wpa2|wpa3}
            --ssid netgear
            --password admin123
            --endp_a_min 1000
            --endp_b_min 1000
            --ap "00:0e:8e:78:e1:76"
            --number_template 0000
            --mode   1
                {"auto"   : "0",
                "a"      : "1",
                "b"      : "2",
                "g"      : "3",
                "abg"    : "4",
                "abgn"   : "5",
                "bgn"    : "6",
                "bg"     : "7",
                "abgnAC" : "8",
                "anAC"   : "9",
                "an"     : "10",
                "bgnAC"  : "11",
                "abgnAX" : "12",
                "bgnAX"  : "13",
            --debug

SCRIPT_CLASSIFICATION:  Creation

SCRIPT_CATEGORIES:   Functional

NOTES:
        Create Layer-3 Cross Connection Using LANforge JSON API : https://www.candelatech.com/cookbook.php?vol=fire&book=scripted+layer-3+test
        Written by Candela Technologies Inc.

        * Supports creating of stations and creates Layer-3 cross-connection with the endpoint_A as stations created and endpoint_B as upstream port.
        * Supports regression testing for QA

STATUS: BETA RELEASE

VERIFIED_ON:   27-JUN-2023,
             Build Version:  5.4.6
             Kernel Version: 6.2.14+

LICENSE:
          Free to distribute and modify. LANforge systems must be licensed.
          Copyright 2023 Candela Technologies Inc

INCLUDE_IN_README: False
"""

import sys
import os
import importlib
import logging

logger = logging.getLogger(__name__)

if sys.version_info[0] != 3:
    logger.critical("This script requires Python 3")
    exit(1)

if 'py-json' not in sys.path:
    sys.path.append(os.path.join(os.path.abspath('..'), 'py-json'))

import argparse
from LANforge.lfcli_base import LFCliBase
from LANforge import LFUtils
from realm import Realm
lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")


class CreateL3(Realm):
    def __init__(
            self,
            ssid,
            security,
            password,
            sta_list,
            name_prefix,
            upstream,
            radio,
            host="localhost",
            port=8080,
            mode=0,
            ap=None,
            side_a_min_rate=56,
            side_a_max_rate=0,
            side_b_min_rate=56,
            side_b_max_rate=0,
            number_template="00000",
            use_ht160=False,
            _debug_on=False,
            _exit_on_error=False,
            _exit_on_fail=False):
        super().__init__(host, port)
        self.upstream = upstream
        self.host = host
        self.port = port
        self.ssid = ssid
        self.sta_list = sta_list
        self.security = security
        self.password = password
        self.radio = radio
        self.mode = mode
        self.ap = ap
        self.number_template = number_template
        self.debug = _debug_on
        self.name_prefix = name_prefix
        self.station_profile = self.new_station_profile()
        self.cx_profile = self.new_l3_cx_profile()
        self.station_profile.lfclient_url = self.lfclient_url
        self.station_profile.ssid = self.ssid
        self.station_profile.ssid_pass = self.password
        self.station_profile.security = self.security
        self.station_profile.number_template_ = self.number_template
        self.station_profile.debug = self.debug
        self.station_profile.use_ht160 = use_ht160
        if self.station_profile.use_ht160:
            self.station_profile.mode = 9
        self.station_profile.mode = mode
        if self.ap is not None:
            self.station_profile.set_command_param("add_sta", "ap", self.ap)
        # self.station_list= LFUtils.portNameSeries(prefix_="sta", start_id_=0,
        # end_id_=2, padding_number_=10000, radio='wiphy0') #Make radio a user
        # defined variable from terminal.

        self.cx_profile.host = self.host
        self.cx_profile.port = self.port
        self.cx_profile.name_prefix = self.name_prefix
        self.cx_profile.side_a_min_bps = side_a_min_rate
        self.cx_profile.side_a_max_bps = side_a_max_rate
        self.cx_profile.side_b_min_bps = side_b_min_rate
        self.cx_profile.side_b_max_bps = side_b_max_rate

    def pre_cleanup(self):
        logger.info('pre_cleanup')
        self.cx_profile.cleanup_prefix()
        for sta in self.sta_list:
            self.rm_port(sta, check_exists=True, debug_=False)

    def build(self):

        self.station_profile.use_security(security_type=self.security,
                                          ssid=self.ssid,
                                          passwd=self.password)
        self.station_profile.set_number_template(self.number_template)
        logger.info("Creating stations")
        self.station_profile.set_command_flag("add_sta", "create_admin_down", 1)
        self.station_profile.set_command_param(
            "set_port", "report_timer", 1500)
        self.station_profile.set_command_flag("set_port", "rpt_timer", 1)

        sta_timeout = 300
        # sta_timeout=3 # expect this to fail
        rv = self.station_profile.create(radio=self.radio,
                                         sta_names_=self.sta_list,
                                         debug=self.debug,
                                         timeout=sta_timeout)
        if not rv:
            self._fail("create_l3_stations: could not create all ports, exiting with error.")
        else:
            self._pass("Station creation succeeded.")
            self.start()
            cx_timeout = 300
            # cx_timeout=0 # expect this to fail
            rv = self.cx_profile.create(endp_type="lf_udp",
                                        side_a=self.station_profile.station_names,
                                        side_b=self.upstream,
                                        sleep_time=0,
                                        timeout=cx_timeout)
            if rv:
                self._pass("CX creation finished")
            else:
                self._fail("create_l3_stations: could not create all cx/endpoints.")

    def start(self):
        logger.info("Bringing up stations")
        self.admin_up(self.upstream)
        for sta in self.station_profile.station_names:
            logger.info("Bringing up station %s" % sta)
            self.admin_up(sta)

    def stop(self):
        logger.info("Bringing down stations")
        # self.admin_up(self.upstream)
        for sta in self.station_profile.station_names:
            logger.info("Bringing down station %s" % sta)
            self.admin_down(sta)

    def cleanup(self):
        logger.info("Clean up stations")
        self.cx_profile.cleanup_prefix()
        for sta in self.sta_list:
            self.rm_port(sta, check_exists=True, debug_=False)


def main():
    parser = LFCliBase.create_basic_argparse(
        prog='create_l3_stations.py',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog='''\
            Create stations to test connection and traffic on VAPs of varying security types (WEP, WPA, WPA2, WPA3, Open)
            ''',

        description='''\
"""
NAME: create_l3_stations.py

PURPOSE:
            This script creates variable number of stations with individual cross-connects and endpoints.
            Stations are set to UP state, but cross-connections remain stopped.

EXAMPLE:
        Default configuration:
            Endpoint A: List of stations (default: 2 stations, unless specified with --num_stations)
            Endpoint B: eth1 
                
        * Creating specified number of station names and Layer-3 CX :

            ./create_l3_stations.py --mgr localhost --num_stations 5 --radio wiphy0 --ssid SSID --password Password@123 --security wpa2
            
        * Creating stations with specified start ID (--num_template) and Layer-3 CX :
        
            ./create_l3_stations.py --mgr localhost --number_template 007 --radio wiphy0 --ssid SSID --password Password@123 --security wpa2
                
        * Creating stations with specified names and Layer-3 CX :

            ./create_l3_stations.py --mgr localhost --station_list sta00,sta01 --radio wiphy0 --ssid SSID --password Password@123 --security wpa2
         
        * For creating stations and layer-3 cx creation on particular specified AP mac & mode:
        
            ./create_l3_stations.py --mgr localhost --radio wiphy0 --ssid SSID --password Password@123 --security wpa2 --ap "00:0e:8e:78:e1:76"
            --mode 13

        * For creating specified number of stations and layer-3 cx creation (Customise the traffic and upstream port):
        
            ./create_l3_stations.py --mgr localhost --station_list sta00  --radio wiphy0 --ssid SSID --password Password@123 --security wpa2
             --upstream_port eth2 --endp_a_min 6200000 --endp_b_min 6200000
         
      Generic command layout:

        python3 ./create_l3_stations.py
            --upstream_port eth1
            --radio wiphy0
            --num_stations 32
            --security {open|wep|wpa|wpa2|wpa3} 
            --ssid netgear
            --password admin123
            --endp_a_min 1000
            --endp_b_min 1000
            --ap "00:0e:8e:78:e1:76"
            --number_template 0000 
            --mode   1
                {"auto"   : "0",
                "a"      : "1",
                "b"      : "2",
                "g"      : "3",
                "abg"    : "4",
                "abgn"   : "5",
                "bgn"    : "6",
                "bg"     : "7",
                "abgnAC" : "8",
                "anAC"   : "9",
                "an"     : "10",
                "bgnAC"  : "11",
                "abgnAX" : "12",
                "bgnAX"  : "13",
            --debug

SCRIPT_CLASSIFICATION:  Creation

SCRIPT_CATEGORIES:   Functional

NOTES:
        Create Layer-3 Cross Connection Using LANforge JSON API : https://www.candelatech.com/cookbook.php?vol=fire&book=scripted+layer-3+test
        Written by Candela Technologies Inc.

        * Supports creating of stations and creates Layer-3 cross-connection with the endpoint_A as stations created and endpoint_B as upstream port.
        * Supports regression testing for QA

STATUS: BETA RELEASE

VERIFIED_ON:   27-JUN-2023,
             Build Version:  5.4.6
             Kernel Version: 6.2.14+

LICENSE:
          Free to distribute and modify. LANforge systems must be licensed.
          Copyright 2023 Candela Technologies Inc

INCLUDE_IN_README: False

''')

    parser.add_argument(
        '--endp_a_min',
        help='--endp_a_min bps rate minimum for side_a',
        default=256000)
    parser.add_argument(
        '--endp_b_min',
        help='--endp_b_min bps rate minimum for side_b',
        default=256000)
    parser.add_argument(
        '--mode', help='Used to force mode of stations')
    parser.add_argument(
        '--ap', help='Used to force a connection to a particular AP')
    parser.add_argument(
        '--number_template',
        help='Start the station numbering with a particular number. Default is 0000',
        default=0000)
    parser.add_argument(
        '--station_list',
        help='Optional: User defined station names, can be a comma or space separated list',
        nargs='+',
        default=None)
    args = parser.parse_args()

    logger_config = lf_logger_config.lf_logger_config()
    # set the logger level to requested value
    logger_config.set_level(level=args.log_level)
    logger_config.set_json(json_file=args.lf_logger_config_json)

    num_sta = 2
    if args.num_stations:
        num_sta = int(args.num_stations)
    elif args.station_list:
        num_sta = len(args.station_list)

    if not args.station_list:
        station_list = LFUtils.portNameSeries(
            prefix_="sta", start_id_=int(
                args.number_template), end_id_=num_sta + int(
                args.number_template) - 1, padding_number_=10000, radio=args.radio)
    else:
        if ',' in args.station_list[0]:
            station_list = args.station_list[0].split(',')
        elif ' ' in args.station_list[0]:
            station_list = args.station_list[0].split()
        else:
            station_list = args.station_list
    ip_var_test = CreateL3(host=args.mgr, port=args.mgr_port, number_template=str(args.number_template),
                           sta_list=station_list, name_prefix="VT", upstream=args.upstream_port, ssid=args.ssid,
                           password=args.passwd, radio=args.radio, security=args.security, side_a_min_rate=args.endp_a_min,
                           side_b_min_rate=args.endp_b_min, mode=args.mode, ap=args.ap, _debug_on=args.debug)

    if not args.no_cleanup:
        ip_var_test.pre_cleanup()
    ip_var_test.build()

    # TODO:  Do cleanup by default, allow --no_cleanup option to skip cleanup.

    if ip_var_test.passes():
        logger.info("Created %s stations and connections" % num_sta)
        ip_var_test.exit_success()
    else:
        ip_var_test.exit_fail()

if __name__ == "__main__":
    main()
