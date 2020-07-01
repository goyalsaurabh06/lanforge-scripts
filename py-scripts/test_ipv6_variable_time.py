#!/usr/bin/env python3

import sys

if sys.version_info[0] != 3:
    print("This script requires Python 3")
    exit(1)

if 'py-json' not in sys.path:
    sys.path.append('../py-json')

import argparse
from LANforge.lfcli_base import LFCliBase
from LANforge.LFUtils import *
import realm
import time
import datetime


class IPV6VariableTime(LFCliBase):
    def __init__(self, host, port, ssid, security, password, num_stations, side_a_min_rate=56, side_b_min_rate=56, side_a_max_rate=0,
                 side_b_max_rate=0, prefix="00000", test_duration="5m",
                 _debug_on=False,
                 _exit_on_error=False,
                 _exit_on_fail=False):
        super().__init__(host, port, _debug=_debug_on, _halt_on_error=_exit_on_error, _exit_on_fail=_exit_on_fail)
        self.host = host
        self.port = port
        self.ssid = ssid
        self.security = security
        self.password = password
        self.num_stations = num_stations
        self.prefix = prefix
        self.local_realm = realm.Realm(lfclient_host=self.host, lfclient_port=self.port)
        self.station_profile = realm.StationProfile(self.lfclient_url, ssid=self.ssid, ssid_pass=self.password,
                                                    security=self.security, prefix=self.prefix, mode=0, up=True,
                                                    dhcp=True,
                                                    debug_=False)
        self.cx_profile = realm.L3CXProfile(self.host, self.port, self.local_realm, side_a_min_rate=side_a_min_rate,
                                            side_b_min_rate=side_b_min_rate, side_a_max_rate=side_a_max_rate,
                                            side_b_max_rate=side_b_max_rate, debug_=False)
        self.test_duration = test_duration

    def __set_all_cx_state(self, state, sleep_time=5):
        print("Setting CX States to %s" % state)
        cx_list = list(self.local_realm.cx_list())
        for cx_name in cx_list:
            if cx_name != 'handler' or cx_name != 'uri':
                req_url = "cli-json/set_cx_state"
                data = {
                    "test_mgr": "default_tm",
                    "cx_name": cx_name,
                    "cx_state": state
                }
                self.json_post(req_url, data)
        time.sleep(sleep_time)

    def __get_rx_values(self):
        cx_list = self.json_get("endp?fields=name,rx+bytes", debug_=True)
        #print("==============\n", cx_list, "\n==============")
        cx_rx_map = {}
        for cx_name in cx_list['endpoint']:
            if cx_name != 'uri' and cx_name != 'handler':
                for item, value in cx_name.items():
                    for value_name, value_rx in value.items():
                      if value_name == 'rx bytes':
                        cx_rx_map[item] = value_rx
        return cx_rx_map

    def __compare_vals(self, old_list, new_list):
        passes = 0
        expected_passes = 0
        if len(old_list) == len(new_list):
            for item, value in old_list.items():
                expected_passes += 1
                if new_list[item] > old_list[item]:
                    passes += 1
                # print(item, new_list[item], old_list[item], passes, expected_passes)

            if passes == expected_passes:
                return True
            else:
                return False
        else:
            return False

    def run_test(self, print_pass=False, print_fail=False):
        cur_time = datetime.datetime.now()
        old_cx_rx_values = self.__get_rx_values()
        end_time = self.local_realm.parse_time(self.test_duration) + cur_time
        self.__set_all_cx_state("RUNNING")
        passes = 0
        expected_passes = 0
        while cur_time < end_time:
            interval_time = cur_time + datetime.timedelta(minutes=1)
            while cur_time < interval_time:
                cur_time = datetime.datetime.now()
                time.sleep(1)

            new_cx_rx_values = self.__get_rx_values()
            # print(old_cx_rx_values, new_cx_rx_values)
            # print("\n-----------------------------------")
            # print(cur_time, end_time, cur_time + datetime.timedelta(minutes=1))
            # print("-----------------------------------\n")
            expected_passes += 1
            if self.__compare_vals(old_cx_rx_values, new_cx_rx_values):
                passes += 1
            else:
                self._fail("FAIL: Not all stations increased traffic", print_fail)
                break
            old_cx_rx_values = new_cx_rx_values
            cur_time = datetime.datetime.now()

        if passes == expected_passes:
            self._pass("PASS: All tests passed", print_pass)

        self.__set_all_cx_state("STOPPED")

    def cleanup(self):
        print("Cleaning up stations")
        port_list = self.local_realm.station_list()
        sta_list = []
        for item in list(port_list):
            # print(list(item))
            if "sta" in list(item)[0]:
                sta_list.append(self.local_realm.name_to_eid(list(item)[0])[2])

        for sta_name in sta_list:
            req_url = "cli-json/rm_vlan"
            data = {
                "shelf": 1,
                "resource": 1,
                "port": sta_name
            }
            # print(data)
            self.json_post(req_url, data)

        cx_list = list(self.local_realm.cx_list())
        if cx_list is not None:
            print("Cleaning up cxs")
            for cx_name in cx_list:
                if cx_name != 'handler' or cx_name != 'uri':
                    req_url = "cli-json/rm_cx"
                    data = {
                        "test_mgr": "default_tm",
                        "cx_name": cx_name
                    }
                    self.json_post(req_url, data)

        print("Cleaning up endps")
        endp_list = self.json_get("/endp")
        if endp_list is not None:
            endp_list = list(endp_list['endpoint'])
            for endp_name in range(len(endp_list)):
                name = list(endp_list[endp_name])[0]
                req_url = "cli-json/rm_endp"
                data = {
                    "endp_name": name
                }
                self.json_post(req_url, data)

    def run(self):
        sta_list = []

        self.station_profile.use_wpa2(True, self.ssid, self.password)
        self.station_profile.set_prefix(self.prefix)
        print("Creating stations")
        self.station_profile.create(resource=1, radio="wiphy0", num_stations=self.num_stations, debug=False)

        for name in list(self.local_realm.station_list()):
            if "sta" in list(name)[0]:
                sta_list.append(list(name)[0])

        print("sta_list", sta_list)
        self.cx_profile.create(endp_type="lf_udp6", side_a=sta_list, side_b="1.eth1", sleep_time=.5)


def main():
    lfjson_host = "localhost"
    lfjson_port = 8080
    ip_var_test = IPV6VariableTime(lfjson_host, lfjson_port, prefix="00", ssid="jedway-wpa2-x2048-4-4",
                                   password="jedway-wpa2-x2048-4-4",
                                   security="open", num_stations=10, test_duration="5m",
                                   side_a_min_rate=256, side_b_min_rate=256)
    ip_var_test.cleanup()
    ip_var_test.run()
    time.sleep(5)
    ip_var_test.run_test(print_pass=True, print_fail=True)
    ip_var_test.cleanup()


if __name__ == "__main__":
    main()
