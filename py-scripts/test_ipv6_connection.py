#!/usr/bin/env python3

import sys
import os
if sys.version_info[0] != 3:
    print("This script requires Python 3")
    exit(1)

if 'py-json' not in sys.path:
    sys.path.append(os.path.join(os.path.abspath('..'), 'py-json'))
import LANforge
from LANforge.lfcli_base import LFCliBase
from LANforge import LFUtils
import argparse
import realm
import time
import pprint


class IPv6Test(LFCliBase):
    def __init__(self, host, port, ssid, security, password, sta_list=None, num_stations=0, prefix="00000",
                 _debug_on=False, timeout=120, radio="wiphy0",
                 _exit_on_error=False,
                 _exit_on_fail=False,
                 number_template="00"):
        super().__init__(host, port, _debug=_debug_on, _halt_on_error=_exit_on_error, _exit_on_fail=_exit_on_fail)
        self.host = host
        self.port = port
        self.ssid = ssid
        self.radio = radio
        self.security = security
        self.password = password
        self.num_stations = num_stations
        self.sta_list = sta_list
        self.timeout = timeout
        self.prefix = prefix
        self.debug = _debug_on
        self.number_template = number_template
        self.local_realm = realm.Realm(lfclient_host=self.host, lfclient_port=self.port)
        self.station_profile = self.local_realm.new_station_profile()

        self.station_profile.lfclient_url = self.lfclient_url
        self.station_profile.ssid = self.ssid
        self.station_profile.ssid_pass = self.password,
        self.station_profile.security = self.security
        self.station_profile.number_template_ = self.number_template
        self.station_profile.mode = 0

    def build(self):
        self.station_profile.use_security(self.security, self.ssid, self.password)
        self.station_profile.set_number_template(self.prefix)
        print("Creating stations")
        self.station_profile.set_command_flag("add_sta", "create_admin_down", 1)
        self.station_profile.set_command_param("set_port", "report_timer", 1500)
        self.station_profile.set_command_flag("set_port", "rpt_timer", 1)
        self.station_profile.create(radio=self.radio, sta_names_=self.sta_list, debug=self.debug)
        self._pass("PASS: Station build finished")

    def start(self, sta_list, print_pass, print_fail):
        self.station_profile.admin_up()
        associated_map = {}
        ip_map = {}
        print("Starting test...")
        for sec in range(self.timeout):
            for sta_name in sta_list:
                shelf = self.local_realm.name_to_eid(sta_name)[0]
                resource = self.local_realm.name_to_eid(sta_name)[1]
                name = self.local_realm.name_to_eid(sta_name)[2]
                sta_status = self.json_get("port/%s/%s/%s?fields=port,alias,ipv6+address,ap" % (shelf, resource, name),
                                           debug_=self.debug)
                # print(sta_status)
                if sta_status is None or sta_status['interface'] is None or sta_status['interface']['ap'] is None:
                    continue
                if len(sta_status['interface']['ap']) == 17 and sta_status['interface']['ap'][-3] == ':':
                    # print("Associated", sta_name, sta_status['interface']['ap'], sta_status['interface']['ip'])
                    associated_map[sta_name] = 1
                if sta_status['interface']['ipv6 address'] != 'DELETED' and \
                        not sta_status['interface']['ipv6 address'].startswith('fe80') \
                        and sta_status['interface']['ipv6 address'] != 'AUTO':
                    # print("IP", sta_name, sta_status['interface']['ap'], sta_status['interface']['ip'])
                    ip_map[sta_name] = 1
            if (len(sta_list) == len(ip_map)) and (len(sta_list) == len(associated_map)):
                break
            else:
                time.sleep(1)

        if self.debug:
            print("sta_list", len(sta_list), sta_list)
            print("ip_map", len(ip_map), ip_map)
            print("associated_map", len(associated_map), associated_map)
        if (len(sta_list) == len(ip_map)) and (len(sta_list) == len(associated_map)):
            self._pass("PASS: All stations associated with IP", print_pass)
        else:
            self._fail("FAIL: Not all stations able to associate/get IP", print_fail)
            print("sta_list", sta_list)
            print("ip_map", ip_map)
            print("associated_map", associated_map)

        return self.passes()

    def stop(self):
        # Bring stations down
        self.station_profile.admin_down()

    def cleanup(self, sta_list):
        self.station_profile.cleanup(sta_list)
        LFUtils.wait_until_ports_disappear(base_url=self.lfclient_url, port_list=sta_list,
                                           debug=self.debug)


def main():
    lfjson_port = 8080

    parser = LFCliBase.create_basic_argparse(
        prog='test_ipv6_connection.py',
        # formatter_class=argparse.RawDescriptionHelpFormatter,
        formatter_class=argparse.RawTextHelpFormatter,
        epilog='''\
            Create stations that attempt to authenticate, associate, and receive IPV6 addresses on the 
            chosen SSID
                ''',

        description='''\
    test_ipv6_connection.py:
--------------------
Generic command example:
python3 ./test_ipv6_connection.py --upstream_port eth1 \\
    --radio wiphy0 \\
    --num_stations 3 \\
    --security {open|wep|wpa|wpa2|wpa3} \\
    --ssid netgear \\
    --passwd admin123 \\
    --dest 10.40.0.1 \\
    --test_duration 2m \\
    --interval 1s \\
    --debug
            ''')

    parser.add_argument('--timeout', help='--timeout sets the length of time to wait until a connection is successful', default=120)

    args = parser.parse_args()

    station_list = LFUtils.portNameSeries(prefix_="sta", start_id_=0, end_id_=1, padding_number_=10000,
                                          radio=args.radio)

    ipv6_test = IPv6Test(args.mgr, lfjson_port, ssid=args.ssid, password=args.passwd,
                         security=args.security, sta_list=station_list)
    ipv6_test.cleanup(station_list)
    ipv6_test.build()
    if not ipv6_test.passes():
        print(ipv6_test.get_fail_message())
        exit(1)
    ipv6_test.start(station_list, False, False)
    ipv6_test.stop()
    if not ipv6_test.passes():
        print(ipv6_test.get_fail_message())
        exit(1)
    time.sleep(10)
    ipv6_test.cleanup(station_list)
    if ipv6_test.passes():
        print("Full test passed, all stations associated and got IP")


if __name__ == "__main__":
    main()
