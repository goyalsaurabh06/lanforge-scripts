#!/usr/bin/env python3
# flake8: noqa
import sys
import os
import importlib
from pprint import pformat
from pprint import pprint
import csv
import pandas as pd
import time
import datetime
import json
import logging

sys.path.append(os.path.join(os.path.abspath(__file__ + "../../../")))

LFUtils = importlib.import_module("py-json.LANforge.LFUtils")
lfcli_base = importlib.import_module("py-json.LANforge.lfcli_base")
LFCliBase = lfcli_base.LFCliBase
pandas_extensions = importlib.import_module("py-json.LANforge.pandas_extensions")

logger = logging.getLogger(__name__)


DEFAULT_IDLE_STATUSES = ("Stopped", "WAITING", "NO-CX", "FTM_WAIT")


class GenCXProfile(LFCliBase):
    def __init__(self, lfclient_host, lfclient_port, local_realm, debug_=False):
        super().__init__(lfclient_host, lfclient_port, debug_)
        self.lfclient_host = lfclient_host
        self.lfclient_port = lfclient_port
        self.lfclient_url = "http://%s:%s" % (lfclient_host, lfclient_port)
        self.debug = debug_
        self.type = "lfping"
        self.dest = "127.0.0.1"
        self.interval = 1
        self.cmd = ""
        self.local_realm = local_realm
        self.name_prefix = "generic"
        self.created_cx = []
        self.created_endp = []
        self.file_output = "/dev/null"
        self.loop_count = 1
        self.speedtest_min_dl = 0
        self.speedtest_min_up = 0
        self.speedtest_max_ping = 0
        self.last_statuses = {}
        self._stall_since = {}
        self._gave_up = set()

    # setting endpoint report timer
    def set_report_timer(self, endp_name=None, timer=5000):
        if(endp_name is not None):
            # NOTE API needs the timer in milliseconds
            data = {
                'endp_name': endp_name,
                'milliseconds': timer
            }
            logger.info(data)
            logger.info('Setting the report timer to {} milliseconds for endpoint {}'.format(timer, endp_name))
            self.json_post('/cli-json/set_endp_report_timer', data, debug_=True)
        else:
            logger.warning('Endpoint name not specified for setting the report timer')

    # If not specified, default client_type is linux
    def parse_command(self, sta_name, gen_name, client_type="linux", ip=None):
        if self.type == "lfping":
            self._parse_ping_cmd(sta_name=sta_name, client_type=client_type, ip=ip)

        elif self.type == "generic":
            if self.cmd == "":
                logger.critical("Please ensure cmd has been set correctly")
                raise ValueError("Please ensure cmd has been set correctly")

        elif self.type == "speedtest":
            self.cmd = "vrf_exec.bash %s speedtest-cli --json --share" % sta_name

        elif self.type == "iperf3" and self.dest:
            self.cmd = "iperf3 --forceflush --format k --precision 4 -c %s -t 60 --tos 0 -b 1K --bind_dev %s -i 1 " \
                       "--pidfile /tmp/lf_helper_iperf3_%s.pid" % (self.dest, sta_name, gen_name)

        elif self.type == "iperf3_serv" and self.dest:
            self.cmd = "iperf3 --forceflush --format k --precision 4 -s --bind_dev %s -i 1 " \
                       "--pidfile /tmp/lf_helper_iperf3_%s.pid" % (sta_name, gen_name)

        elif self.type == "lfcurl":
            if self.file_output:
                self.cmd = "./scripts/lf_curl.sh  -p %s -i AUTO -o %s -n %s -d %s" % \
                           (sta_name, self.file_output, self.loop_count, self.dest)
            else:
                logger.critical("Please ensure file_output has been set correctly")
                raise ValueError("Please ensure file_output has been set correctly")
        elif self.type == "zoom":
            pass
        elif self.type == 'youtube':
            pass
        elif self.type == "real_browser":
            pass
        elif self.type == "teams":
            pass
        else:
            logger.critical("Unknown command type")
            raise ValueError("Unknown command type")

    # Matches ping command builder in GenCreationGUI.java
    #
    # Args:
    #   client_type is one of "android", "linux", "macos", or "windows"
    def _parse_ping_cmd(self, client_type, sta_name, ip=None):
        if not self.dest or not self.interval:
            logger.critical("Please ensure dest and interval have been set correctly")
            raise ValueError("Please ensure dest and interval have been set correctly")

        if client_type != "android" and client_type != "linux" and client_type != "macos" \
            and client_type != "windows":
            logger.critical("Incorrect client type specified %s" % (client_type))
            raise ValueError("Incorrect client type specified %s" % (client_type))

        # TODO: Count, size, pattern for all client types
        if client_type == "windows":
            # NOTE: Unable to specify interval for Windows ping
            self.cmd = "py lfping.py -S %s -n -1 -dest_ip %s" % (ip, self.dest)

        elif client_type == "macos":
            self.cmd = "lfping -b %s -i %s %s" % (sta_name, self.interval, self.dest)

        elif client_type == "android":
            self.cmd = "ping -i %s %s" % (self.interval, self.dest)

        else: # linux and virtual stations
            self.cmd = "lfping -I %s -i %s %s" % (sta_name, self.interval, self.dest)

    def start_cx(self, cx_names=None, report_timer=None, endp_names=None):
        """Set CXs to RUNNING; defaults to all created CXs."""
        cx_names = list(self.created_cx if cx_names is None else cx_names)
        logger.info("Starting CXs: %s" % cx_names)
        logger.info("Created-Endp: %s" % self.created_endp)
        if report_timer:
            self.set_report_timers(report_timer, endp_names)
        for cx_name in cx_names:
            self.json_post("/cli-json/set_cx_state", {
                "test_mgr": "default_tm",
                "cx_name": cx_name,
                "cx_state": "RUNNING"
            }, debug_=True)
        return cx_names

    def stop_cx(self, cx_names=None, skip_endps=None):
        """Set CXs to STOPPED; defaults to all created CXs."""
        logger.info("Stopping CXs...")
        if skip_endps:
            self.untrack_endps(skip_endps)
        cx_names = list(self.created_cx if cx_names is None else cx_names)
        for cx_name in cx_names:
            self.json_post("/cli-json/set_cx_state", {
                "test_mgr": "default_tm",
                "cx_name": cx_name,
                "cx_state": "STOPPED"
            }, debug_=True)
        return cx_names

    def cleanup(self):
        logger.info("Cleaning up cxs and endpoints")
        for cx_name in self.created_cx:
            req_url = "cli-json/rm_cx"
            data = {
                "test_mgr": "default_tm",
                "cx_name": cx_name
            }
            self.json_post(req_url, data)

        for endp_name in self.created_endp:
            req_url = "cli-json/rm_endp"
            data = {
                "endp_name": endp_name
            }
            self.json_post(req_url, data)

    def set_flags(self, endp_name, flag_name, val):
        data = {
            "name": endp_name,
            "flag": flag_name,
            "val": val
        }
        # print('Setting flags', data)
        self.json_post("cli-json/set_endp_flag", data, debug_=self.debug)

    def set_cmd(self, endp_name, cmd):
        data = {
            "name": endp_name,
            "command": cmd
        }
        # print('Setting cmd', data)
        self.json_post("cli-json/set_gen_cmd", data, debug_=self.debug)

    def parse_command_gen(self, sta_name, dest):
        if self.type == "lfping":
            if self.dest and self.interval:
                self.cmd = "%s  -i %s -I %s %s" % (self.type, self.interval, sta_name, dest)
                logger.debug(self.cmd)
            else:
                logger.critical("Please ensure dest and interval have been set correctly")
                raise ValueError("Please ensure dest and interval have been set correctly")

        elif self.type == "generic":
            if self.cmd == "":
                logger.critical("Please ensure cmd has been set correctly")
                raise ValueError("Please ensure cmd has been set correctly")

        elif self.type == "speedtest":
            self.cmd = "vrf_exec.bash %s speedtest-cli --json --share" % sta_name

        elif self.type == "iperf3" and self.dest:
            self.cmd = "iperf3 --forceflush --format k --precision 4 -c %s -t 60 --tos 0 -b 1K --bind_dev %s -i 1 " \
                       "--pidfile /tmp/lf_helper_iperf3_test.pid" % (self.dest, sta_name)

        elif self.type == "lfcurl":
            if self.file_output:
                self.cmd = "./scripts/lf_curl.sh  -p %s -i AUTO -o %s -n %s -d %s" % \
                           (sta_name, self.file_output, self.loop_count, self.dest)
            else:
                logger.critical("Please ensure file_output has been set correctly")
                raise ValueError("Please ensure file_output has been set correctly")
        else:
            logger.critical("Unknown command type")
            raise ValueError("Unknown command type")

    def create_gen(self, sta_port, dest, add, sleep_time=.5, debug_=False, suppress_related_commands_=None):
        if self.debug:
            debug_ = True
        post_data = []
        endp_tpls = []

        if type(sta_port) == str:
            if sta_port != "1.1.eth1":
                count = 5
            else:
                count = 40
            for i in range(0, count):
                port_info = self.local_realm.name_to_eid(sta_port)
                resource = port_info[1]
                shelf = port_info[0]
                name = port_info[2]

                gen_name_a = "%s-%s" % (self.name_prefix, name) + "_" + str(i) + add
                gen_name_b = "D_%s-%s" % (self.name_prefix, name) + "_" + str(i) + add
                endp_tpls.append((shelf, resource, name, gen_name_a, gen_name_b))

            print(endp_tpls)
        elif type(sta_port) == list:
            for port_name in sta_port:
                logger.info("hello............{sta_port}".format(sta_port=sta_port))
                for i in range(0, 5):
                    port_info = self.local_realm.name_to_eid(port_name)
                    try:
                        resource = port_info[1]
                        shelf = port_info[0]
                        name = port_info[2]
                    except ValueError:
                        logger.critical("Unexpected name for port_name {port_name}".format(port_name=port_name))
                        raise ValueError("Unexpected name for port_name {port_name}".format(port_name=port_name))

                    # this naming convention follows what you see when you use
                    # lf_firemod.pl --action list_endp after creating a generic endpoint
                    gen_name_a = "%s-%s" % (self.name_prefix, name) + "_" + str(i) + add
                    gen_name_b = "D_%s-%s" % (self.name_prefix, name) + "_" + str(i) + add
                    endp_tpls.append((shelf, resource, name, gen_name_a, gen_name_b))

        logger.info(endp_tpls)

        for endp_tpl in endp_tpls:
            shelf = endp_tpl[0]
            resource = endp_tpl[1]
            name = endp_tpl[2]
            gen_name_a = endp_tpl[3]

            data = {
                "alias": gen_name_a,
                "shelf": shelf,
                "resource": resource,
                "port": name,
                "type": "gen_generic"
            }
            logger.info(pformat(data))

            self.json_post("cli-json/add_gen_endp", data, debug_=self.debug)

        self.local_realm.json_post("/cli-json/nc_show_endpoints", {"endpoint": "all"})
        time.sleep(sleep_time)

        for endp_tpl in endp_tpls:
            gen_name_a = endp_tpl[3]
            gen_name_b = endp_tpl[4]
            self.set_flags(gen_name_a, "ClearPortOnStart", 1)
        time.sleep(sleep_time)

        if type(dest) == str:
            for endp_tpl in endp_tpls:
                name = endp_tpl[2]
                gen_name_a = endp_tpl[3]
                # gen_name_b  = endp_tpl[4]
                self.parse_command_gen(name, dest)
                self.set_cmd(gen_name_a, self.cmd)
            time.sleep(sleep_time)

        elif type(dest) == list:
            mm = 0
            for endp_tpl in endp_tpls:
                name = endp_tpl[2]
                gen_name_a = endp_tpl[3]
                # gen_name_b  = endp_tpl[4]
                self.parse_command_gen(name, dest[mm])
                self.set_cmd(gen_name_a, self.cmd)
                mm = mm + 1
                if mm == 8:
                    mm = 0
            time.sleep(sleep_time)

        j = 0
        for endp_tpl in endp_tpls:
            name = endp_tpl[2]
            gen_name_a = endp_tpl[3]
            gen_name_b = endp_tpl[4]
            cx_name = "CX_%s-%s" % (self.name_prefix, name) + "_" + str(j) + add
            j = j + 1
            data = {
                "alias": cx_name,
                "test_mgr": "default_tm",
                "tx_endp": gen_name_a,
                "rx_endp": gen_name_b
            }
            post_data.append(data)
            # self.created_cx = []
            self.created_cx.append(cx_name)
            # self.created_endp = []
            self.created_endp.append(gen_name_a)
            self.created_endp.append(gen_name_b)
        time.sleep(sleep_time)

        logger.info(self.created_cx)

        for data in post_data:
            url = "/cli-json/add_cx"
            logger.info(pformat(data))
            self.local_realm.json_post(url, data, debug_=debug_, suppress_related_commands_=suppress_related_commands_)
            time.sleep(2)
        time.sleep(sleep_time)
        for data in post_data:
            self.local_realm.json_post("/cli-json/show_cx", {
                "test_mgr": "default_tm",
                "cross_connect": data["alias"]
            })
        time.sleep(sleep_time)

    def create(self, ports=None, sleep_time=.5, debug_=False, suppress_related_commands_=None, real_client_os_types=None):
        if ports and real_client_os_types and len(real_client_os_types) == 0:
            logging.error('Real client operating systems types is empty list')
            raise ValueError('Real client operating systems types is empty list')

        if not ports:
            ports = []

        if self.debug:
            debug_ = True

        post_data = []
        endp_tpls = []
        for port_name in ports:
            port_info = self.local_realm.name_to_eid(port_name)
            resource = port_info[1]
            shelf = port_info[0]
            if real_client_os_types:
                name = port_name
            else:
                name = port_info[2]

            # this naming convention follows what you see when you use
            # lf_firemod.pl --action list_endp after creating a generic endpoint
            gen_name_a = "%s-%s" % (self.name_prefix, name)
            endp_tpls.append((shelf, resource, name, gen_name_a))

        for endp_tpl in endp_tpls:
            shelf = endp_tpl[0]
            resource = endp_tpl[1]
            if real_client_os_types:
                name = endp_tpl[2].split('.')[2]
            else:
                name = endp_tpl[2]
            gen_name_a = endp_tpl[3]

            data = {
                "alias": gen_name_a,
                "shelf": shelf,
                "resource": resource,
                "port": name,
                "type": "gen_generic"
            }
            logger.debug(pformat(data))
            # print('Adding endpoint ', data)
            self.json_post("cli-json/add_gen_endp", data, debug_=self.debug)

        self.local_realm.json_post("/cli-json/nc_show_endpoints", {"endpoint": "all"})
        if sleep_time:
            time.sleep(sleep_time)

        for endp_tpl in endp_tpls:
            gen_name_a = endp_tpl[3]
            self.set_flags(gen_name_a, "ClearPortOnStart", 1)
        if sleep_time:
            time.sleep(sleep_time)

        # Assumes ordering of endpoint tuples matches ports passed
        # That way can get OS type for port (and endpoint) w/ same index
        for ix, endp_tpl in enumerate(endp_tpls):
            gen_name_a = endp_tpl[3]

            if real_client_os_types:
                name = endp_tpl[2].split('.')[2]
                ip_response = self.json_get('/port/{}/{}/{}?fields=ip'.format(endp_tpl[0], endp_tpl[1], name))
                if(ip_response == None or ip_response == "" or ip_response == " " or (type(ip_response) is dict and 'interface' not in ip_response.keys())):
                    logger.critical('Client {} not found'.format(endp_tpl[2]))
                    logger.info('Consider upgrading LANforge to 5.4.7 or later versions')
                else:
                    if('ip' not in ip_response['interface']):
                        logger.critical('Client {} has no attribute IP'.format(endp_tpl[2]))
                    else:
                        current_device_ip = ip_response['interface']['ip']
                        if(current_device_ip == "" or current_device_ip is None):
                            logger.critical('IP Address not found for the Client {}'.format(endp_tpl[2]))
                            current_device_ip = None
                self.parse_command(name, gen_name_a, client_type=real_client_os_types[ix], ip=current_device_ip)
            else:
                name = endp_tpl[2]
                self.parse_command(name, gen_name_a)
            # gen_name_b  = endp_tpl[4]
            self.set_cmd(gen_name_a, self.cmd)

        if sleep_time:
            time.sleep(sleep_time)

        for endp_tpl in endp_tpls:
            name = endp_tpl[2]
            gen_name_a = endp_tpl[3]
            cx_name = "CX_%s-%s" % (self.name_prefix, name)
            data = {
                "alias": cx_name,
                "test_mgr": "default_tm",
                "tx_endp": gen_name_a
            }
            post_data.append(data)
            self.created_cx.append(cx_name)
            self.created_endp.append(gen_name_a)

        if sleep_time:
            time.sleep(sleep_time)

        for data in post_data:
            url = "/cli-json/add_cx"
            logger.info(pformat(data))
            # print('Adding cx', data)
            self.local_realm.json_post(url, data, debug_=debug_, suppress_related_commands_=suppress_related_commands_)
            # time.sleep(2)
        if sleep_time:
            time.sleep(sleep_time)

        for data in post_data:
            self.local_realm.json_post("/cli-json/show_cx", {
                "test_mgr": "default_tm",
                "cross_connect": data["alias"]
            })
        return True

    # Looks incorrect to me. --Ben
    def choose_ping_command(self):
        gen_results = self.json_get("generic/list?fields=name,last+results", debug_=self.debug)
        logger.debug(pformat(gen_results))
        if gen_results['endpoints']:
            for name in gen_results['endpoints']:
                for k, v in name.items():
                    logger.info("k: %s  v: %s" % (k, v))
                    if v['name'] in self.created_endp and not v['name'].endswith('1'):
                        if v['last results'] != "" and "Unreachable" not in v['last results']:
                            return True, v['name']
                        else:
                            return False, v['name']

    def choose_lfcurl_command(self):
        gen_results = self.json_get("generic/list?fields=name,last+results", debug_=self.debug)
        logger.debug(pformat(gen_results))
        if gen_results['endpoints']:
            for name in gen_results['endpoints']:
                for k, v in name.items():
                    if v['name'] != '':
                        results = v['last results'].split()
                        if 'Finished' in v['last results']:
                            # TODO: What is this actually doing?
                            if results[1][:-1] == results[2]:
                                return True, v['name']
                            else:
                                return False, v['name']

    def choose_iperf3_command(self):
        gen_results = self.json_get("generic/list?fields=name,last+results", debug_=self.debug)
        if gen_results['endpoints']:
            logger.info(gen_results['endpoints'])
            # for name in gen_results['endpoints']:
            # pprint(name.items)
            # for k,v in name.items():
        exit(1)

    def choose_speedtest_command(self):
        gen_results = self.json_get("generic/list?fields=name,last+results", debug_=self.debug)
        if gen_results['endpoints']:
            for name in gen_results['endpoints']:
                for k, v in name.items():
                    if v['last results'] and v['name'] in self.created_endp and v['last results'] != '':
                        last_results = json.loads(v['last results'])
                        if not last_results['download'] and not last_results['upload'] and not last_results['ping']:
                            return False, v['name']
                        elif last_results['download'] >= self.speedtest_min_dl and \
                                last_results['upload'] >= self.speedtest_min_up and \
                                last_results['ping'] <= self.speedtest_max_ping:
                            return True, v['name']

    def choose_generic_command(self):
        gen_results = self.json_get("generic/list?fields=name,last+results", debug_=self.debug)
        if gen_results['endpoints']:
            for name in gen_results['endpoints']:
                for k, v in name.items():
                    if v['name'] in self.created_endp and not v['name'].endswith('1'):
                        if v['last results'] != "" and "not known" not in v['last results']:
                            return True, v['name']
                        else:
                            return False, v['name']

    # TODO monitor is broken
    # TODO:  Can only monitor ports on a single resource.
    def monitor(self,
                duration_sec=60,
                monitor_interval=2,  # seconds
                sta_list=None,
                resource_id=1,
                generic_cols=None,
                port_mgr_cols=None,
                must_increase_cols=None,
                monitor_endps=None,  # list of endpoints to monitor
                monitor=True,
                report_file=None,
                systeminfopath=None,
                output_format=None,
                script_name=None,
                arguments=None,
                compared_report=None,
                debug=False):
        try:
            duration_sec = self.parse_time(duration_sec).seconds
        except ValueError:
            if not duration_sec or (duration_sec <= 1):
                logger.critical("GenCXProfile::monitor wants duration_sec > 1 second")
                raise ValueError("GenCXProfile::monitor wants duration_sec > 1 second")
            if duration_sec <= monitor_interval:
                logger.critical("GenCXProfile::monitor wants duration_sec > monitor_interval")
                raise ValueError("GenCXProfile::monitor wants duration_sec > monitor_interval")
        if not report_file:
            logger.critical("Monitor requires an output file to be defined")
            raise ValueError("Monitor requires an output file to be defined")
        if not systeminfopath:
            logger.critical("Monitor requires a system info path to be defined")
            raise ValueError("Monitor requires a system info path to be defined")
        if not monitor_endps:
            logger.critical("Monitor needs a list of Endpoints to monitor")
            raise ValueError("Monitor needs a list of Endpoints to monitor")
        if not monitor_interval or (monitor_interval < 1):
            logger.critical("GenCXProfile::monitor wants monitor_interval >= 1 second")
            raise ValueError("GenCXProfile::monitor wants monitor_interval >= 1 second")
        if not generic_cols:
            logger.critical("GenCXProfile::monitor wants a list of column names to monitor")
            raise ValueError("GenCXProfile::monitor wants a list of column names to monitor")
        if output_format:
            if output_format.lower() != report_file.split('.')[-1]:
                logger.critical(
                    'Filename {report_file} has an extension that does not match output format {output_format}'.format(
                        report_file=report_file, output_format=output_format))
                raise ValueError(
                    'Filename {report_file} has an extension that does not match output format {output_format}'.format(
                        report_file=report_file, output_format=output_format))
        else:
            output_format = report_file.split('.')[-1]

        # default save to csv first
        if report_file.split('.')[-1] != 'csv':
            report_file = report_file.replace(str(output_format), 'csv', 1)
            logger.info("Saving rolling data into: " + str(report_file))

        # ================== Step 1, set column names and header row
        generic_cols = [self.replace_special_char(x) for x in generic_cols]
        generic_fields = ",".join(generic_cols)
        default_cols = ['Timestamp', 'Timestamp milliseconds epoch', 'Timestamp seconds epoch', 'Duration elapsed']
        default_cols.extend(generic_cols)
        if port_mgr_cols:
            default_cols.extend(port_mgr_cols)
        header_row = default_cols

        # csvwriter.writerow([systeminfo['VersionInfo']['BuildVersion'], script_name, str(arguments)])

        if port_mgr_cols:
            port_mgr_cols = [self.replace_special_char(x) for x in port_mgr_cols]
            port_mgr_cols_labelled = []
            for col_name in port_mgr_cols:
                port_mgr_cols_labelled.append("port mgr - " + col_name)

            port_mgr_fields = ",".join(port_mgr_cols)
            header_row.extend(port_mgr_cols_labelled)

        # create sys info file
        systeminfo = self.json_get('/')
        sysinfo = [str("LANforge GUI Build: " + systeminfo['VersionInfo']['BuildVersion']),
                   str("Script Name: " + script_name), str("Argument input: " + str(arguments))]
        with open(systeminfopath, 'w') as filehandle:
            for listitem in sysinfo:
                filehandle.write('%s\n' % listitem)

        # ================== Step 2, monitor columns
        start_time = datetime.datetime.now()
        end_time = start_time + datetime.timedelta(seconds=duration_sec)

        fail_incr_count = 0
        pass_incr_count = 0
        prev_results = {}  # dict of dicts
        if must_increase_cols:
            for en in monitor_endps:
                # print("Monitoring Endpoint: %s" % (en))
                prev_results[en] = {}  # dict of col names to values
                for cn in must_increase_cols:
                    prev_results[en][cn] = 0

        # instantiate csv file here, add specified column headers
        csvfile = open(str(report_file), 'w')
        csvwriter = csv.writer(csvfile, delimiter=",")
        csvwriter.writerow(header_row)

        # for x in range(0,int(round(iterations,0))):
        initial_starttime = datetime.datetime.now()
        logger.info("Starting Test Monitoring for %s seconds..." % duration_sec)
        while datetime.datetime.now() < end_time:
            t = datetime.datetime.now()
            timestamp = t.strftime("%m/%d/%Y %I:%M:%S")
            t_to_millisec_epoch = int(self.get_milliseconds(t))
            t_to_sec_epoch = int(self.get_seconds(t))
            time_elapsed = int(self.get_seconds(t)) - int(self.get_seconds(initial_starttime))
            basecolumns = [timestamp, t_to_millisec_epoch, t_to_sec_epoch, time_elapsed]

            # get endp values
            gen_url = "/generic/%s?fields=%s" % (",".join(monitor_endps), generic_fields)
            #print("gen-url: %s" % (gen_url))
            generic_response = self.json_get(gen_url)

            if port_mgr_cols:
                # get info from port manager with list of values from cx_a_side_list
                port_mgr_response = self.json_get("/port/1/%s/%s?fields=%s" % (resource_id, sta_list, port_mgr_fields))

            if ("endpoints" not in generic_response and "endpoint" not in generic_response) or not generic_response:
                logger.critical(generic_response)
                logger.critical("Json generic_response from LANforge... {generic_response}".format(generic_response=generic_response))
                logger.critical("Cannot find columns requested to be searched. Exiting script, please retry.")
                raise ValueError("Cannot find columns requested to be searched. Exiting script, please retry.")
            if port_mgr_cols:
                if "interfaces" not in port_mgr_response or not port_mgr_response:
                    logger.critical(port_mgr_response)
                    logger.critical("Cannot find columns requested to be searched. Exiting script, please retry.")
                    raise ValueError("Cannot find columns requested to be searched. Exiting script, please retry.")
                logger.debug("Json port_mgr_response from LANforge... {port_mgr_response}".format(port_mgr_response=port_mgr_response))

            #print("generic response: ")
            # pprint(generic_response)
            if "endpoints" in generic_response:
                endp_array = generic_response["endpoints"]
            elif "endpoint" in generic_response:
                endp_array = generic_response["endpoint"]
                # Second assignment to endp_array makes it consistent with the layout of multi-endpoint endp_array
                endp_array = [{endp_array['name'] : endp_array}]

            #print("endp-array: ")
            # pprint(endp_array)
            for endpoint in endp_array:  # each endpoint is a dictionary
                #print("endpoint: ")
                # pprint(endpoint)
                #print("endpoint values: ")
                # pprint(endpoint.values())

                endp_values_list = list(endpoint.values())
                # for x in endp_values_list:
                #    pprint(x)

                # There is only one value in the endp_values_list, the key is the name,
                # but the name is also in the value dict, so we ignore the key.
                endp_values = endp_values_list[0]

                endp_name = endp_values["name"]
                temp_list = basecolumns.copy()  # Must make a deep copy or we just keep appending to basecolumns object.
                for columnname in generic_cols:
                    val = endp_values[columnname]
                    #print("column-name: %s val: %s must-increase-cols: %s" % (columnname, val, must_increase_cols))
                    temp_list.append(val)
                    if must_increase_cols:
                        if columnname in must_increase_cols:
                            # Ensure this has increased since last sample.
                            #print("endp_name: %s columname: %s value: %s  endpoint: %s" % (endp_name, columnname, val, endpoint))
                            if prev_results[endp_name][columnname] >= LFUtils.speed_to_int(val):
                                self._fail("Endpoint %s column: %s did not increase, old: %s  new: %s" %
                                           (endp_name, columnname, prev_results[endp_name][columnname], val))
                                fail_incr_count += 1
                            else:
                                logger.debug("Endpoint %s column: %s did increase, old: %s  new: %s" %
                                             (endp_name, columnname, prev_results[endp_name][columnname], val))
                                pass_incr_count += 1

                    if port_mgr_cols:
                        for sta_name in sta_list_edit:
                            if sta_name in current_sta:
                                for interface in port_mgr_response["interfaces"]:
                                    if sta_name in list(interface.keys())[0]:
                                        merge = temp_endp_values.copy()
                                        # rename keys (separate port mgr 'rx bytes' from generic 'rx bytes')
                                        port_mgr_values_dict = list(interface.values())[0]
                                        renamed_port_cols = {}
                                        for key in port_mgr_values_dict.keys():
                                            renamed_port_cols['port mgr - ' + key] = port_mgr_values_dict[key]
                                        merge.update(renamed_port_cols)
                                        for name in port_mgr_cols:
                                            temp_list.append(merge[name])
                csvwriter.writerow(temp_list)

            time.sleep(monitor_interval)
            # End of while loop for duration of monitor period.

        csvfile.close()

        if fail_incr_count == 0:
            if pass_incr_count > 0:
                self._pass("Verified requested counters: %s increased each of %s monitor attempts" %
                           (must_increase_cols, pass_incr_count))
        else:
            if pass_incr_count > 0:
                self._fail("Partial success: Verified requested counters: %s increased % of % attempts" %
                           (must_increase_cols, pass_incr_count, (pass_incr_count + fail_incr_count)))

        # TODO:  This looks broken, figure out intent and fix, or remove.
        # comparison to last report / report inputted
        if compared_report:
            compared_df = pandas_extensions.compare_two_df(dataframe_one=pandas_extensions.file_to_df(report_file),
                                                           dataframe_two=pandas_extensions.file_to_df(compared_report))
            exit(1)
            # append compared df to created one
            if output_format.lower() != 'csv':
                pandas_extensions.df_to_file(dataframe=pd.read_csv(report_file), output_f=output_format,
                                             save_path=report_file)
        else:
            if output_format.lower() != 'csv':
                pandas_extensions.df_to_file(dataframe=pd.read_csv(report_file), output_f=output_format,
                                             save_path=report_file)

    def is_tab_enabled(self):
        """Return True if the Generic tab is enabled on the LANforge GUI."""
        response = self.json_get("generic")
        if not response:
            logger.error("Failed to fetch generic tab data.\nRequested URL: 'generic'\nResponse: %s", response)
            return False
        return True

    def has_endp(self, endp_name, api="generic"):
        """Return True if LANforge currently has an endpoint by this name; api is generic or layer4."""
        response = self.json_get("/{}/{}".format(api, endp_name))
        return bool(response and "endpoint" in response)

    def has_cx(self, cx_name):
        """Return True if LANforge currently has a CX by this name."""
        response = self.json_get("/cx/{}".format(cx_name))
        if not response or not isinstance(response, dict):
            return False
        response_text = str(response).lower()
        return cx_name.lower() in response_text and "not found" not in response_text

    def get_endp_cx_names(self, port, prefix=None, virtual=False, android=False):
        """Return the (endpoint name, CX name) that create_cx() uses for a port."""
        prefix = prefix or self.name_prefix
        if android:
            endp_name = "{}-{}".format(prefix, "_".join(port.split(".")))
            return endp_name, "CX_generic-{}".format(endp_name)
        endp_suffix = self.local_realm.name_to_eid(port)[2] if virtual else port
        endp_name = "{}-{}".format(prefix, endp_suffix)
        return endp_name, "CX_{}".format(endp_name)

    def list_endps(self):
        """Return the names of every generic endpoint on the manager, without the auto-created RX ("D_") side."""
        response = self.json_get("/generic/all?fields=name")
        if not response:
            return []
        endp_entries = response.get("endpoints", response.get("endpoint", []))
        if isinstance(endp_entries, dict):
            endp_entries = [{endp_entries.get("name", ""): endp_entries}]
        endp_names = [endp_values.get("name") for endp_entry in endp_entries for endp_values in endp_entry.values() if isinstance(endp_values, dict)]
        return [endp_name for endp_name in endp_names if endp_name and not endp_name.startswith("D_")]

    def find_endp_cx(self, endp_or_cx_name):
        """Return the (endpoint name, CX name) for an endpoint or CX name, or None if it does not exist."""
        endp_candidates = [endp_or_cx_name]
        if endp_or_cx_name.startswith("CX_generic-"):
            endp_candidates.append(endp_or_cx_name[len("CX_generic-"):])
        if endp_or_cx_name.startswith("CX_"):
            endp_candidates.append(endp_or_cx_name[len("CX_"):])
        endp_name = next((candidate_endp for candidate_endp in endp_candidates if self.has_endp(candidate_endp)), None)
        if endp_name is None:
            return None
        cx_candidates = [endp_or_cx_name] if endp_or_cx_name.startswith("CX_") else []
        cx_candidates += ["CX_{}".format(endp_name), "CX_generic-{}".format(endp_name)]
        cx_name = next((candidate_cx for candidate_cx in dict.fromkeys(cx_candidates) if self.json_get("/cx/{}".format(candidate_cx))), None)
        return endp_name, cx_name

    def track_endps(self, endp_or_cx_names):
        """Start tracking existing endpoints and their CXs, given by endpoint or CX name."""
        endp_cx_pairs = []
        for endp_or_cx_name in endp_or_cx_names:
            endp_cx_pair = self.find_endp_cx(endp_or_cx_name)
            if endp_cx_pair is None:
                logger.warning("Generic endpoint '%s' not found on the LANforge manager, skipping", endp_or_cx_name)
                continue
            endp_name, cx_name = endp_cx_pair
            if endp_name not in self.created_endp:
                self.created_endp.append(endp_name)
            if cx_name and cx_name not in self.created_cx:
                self.created_cx.append(cx_name)
            endp_cx_pairs.append(endp_cx_pair)
        return endp_cx_pairs

    def create_cx(self, ports=None, os_types=None, android_ports=None, android_host=None, cmds=None, prefix=None,
                  pre_cleanup=True, sleep_time=.5, on_error=None, debug_=False, suppress_related_commands_=None):
        """Create endpoints and CXs for virtual, real and Android clients; returns {port: endpoint name}."""
        ports = list(ports or [])
        android_ports = list(android_ports or [])
        cmds = cmds or {}
        if os_types is not None and len(os_types) != len(ports):
            raise ValueError("os_types needs one entry per port ({} ports, {} os_types)".format(len(ports), len(os_types)))
        os_types = list(os_types) if os_types is not None else [None] * len(ports)

        previous_prefix = self.name_prefix
        if prefix:
            self.name_prefix = prefix
        created_endps = {}
        try:
            if pre_cleanup:
                self.delete_cx(ports=ports, os_types=os_types, android_ports=android_ports, tracked=False)

            # Runs of the same kind (virtual or real) are created in one call, keeping the given order.
            batch_start = 0
            while batch_start < len(ports):
                is_virtual_batch = not os_types[batch_start]
                batch_end = batch_start
                while batch_end < len(ports) and (not os_types[batch_end]) == is_virtual_batch:
                    batch_end += 1
                batch_ports = ports[batch_start:batch_end]
                first_new_endp_index = len(self.created_endp)
                self.create(ports=batch_ports, sleep_time=sleep_time, debug_=debug_, suppress_related_commands_=suppress_related_commands_,
                            real_client_os_types=None if is_virtual_batch else os_types[batch_start:batch_end])
                new_endp_names = self.created_endp[first_new_endp_index:]
                if len(new_endp_names) != len(batch_ports):
                    logger.warning("Expected %d endpoints but the profile tracked %d", len(batch_ports), len(new_endp_names))
                created_endps.update(zip(batch_ports, new_endp_names))
                batch_start = batch_end

            if android_ports:
                realm = self.local_realm
                android_specs = []
                for port in android_ports:
                    port_eid = realm.name_to_eid(port)
                    if android_host is None:
                        host_resource = port_eid[1]
                    else:
                        host_text = str(android_host)
                        host_resource = host_text.split(".")[1] if "." in host_text else host_text
                    endp_name, cx_name = self.get_endp_cx_names(port, android=True)
                    android_specs.append({"port": port, "shelf": port_eid[0], "resource": host_resource, "endp_name": endp_name, "cx_name": cx_name})

                for android_spec in android_specs:
                    self.json_post("cli-json/add_gen_endp", {
                        "alias": android_spec["endp_name"],
                        "shelf": android_spec["shelf"],
                        "resource": android_spec["resource"],
                        "port": "eth0",
                        "type": "gen_generic"
                    }, debug_=debug_)
                realm.json_post("/cli-json/nc_show_endpoints", {"endpoint": "all"})
                if sleep_time:
                    time.sleep(sleep_time)

                for android_spec in android_specs:
                    self.set_flags(android_spec["endp_name"], "ClearPortOnStart", 1)

                for android_spec in android_specs:
                    response = realm.json_post("/cli-json/add_cx", {
                        "alias": android_spec["cx_name"],
                        "test_mgr": "default_tm",
                        "tx_endp": android_spec["endp_name"]
                    }, debug_=debug_, suppress_related_commands_=suppress_related_commands_)
                    if response is None:
                        message = "No response received from CX creation request; waiting for CX to appear"
                        logger.warning("%s: %s", android_spec["cx_name"], message)
                        if on_error:
                            on_error(android_spec["cx_name"], message)
                    self.created_cx.append(android_spec["cx_name"])
                    self.created_endp.append(android_spec["endp_name"])
                    created_endps[android_spec["port"]] = android_spec["endp_name"]
                if sleep_time:
                    time.sleep(sleep_time)

                for android_spec in android_specs:
                    realm.json_post("/cli-json/show_cx", {"test_mgr": "default_tm", "cross_connect": android_spec["cx_name"]})
        finally:
            self.name_prefix = previous_prefix

        for port, endp_name in created_endps.items():
            if port in cmds:
                self.set_cmd(endp_name, cmds[port])
        return created_endps

    def delete_cx(self, ports=None, os_types=None, android_ports=None, endp_or_cx_names=None, prefix=None, tracked=True, check_exists=True, settle=0):
        """Delete CXs and their endpoints, tracked ones and/or ones named by port or name; returns the endpoints removed."""
        port_endp_cx_names = []
        ports = list(ports or [])
        if os_types is not None and len(os_types) != len(ports):
            raise ValueError("os_types needs one entry per port ({} ports, {} os_types)".format(len(ports), len(os_types)))
        for port_index, port in enumerate(ports):
            if os_types is None or os_types[port_index]:
                port_endp_cx_names.append(self.get_endp_cx_names(port, prefix))
            if os_types is None or not os_types[port_index]:
                port_endp_cx_names.append(self.get_endp_cx_names(port, prefix, virtual=True))
        for port in android_ports or []:
            port_endp_cx_names.append(self.get_endp_cx_names(port, prefix, android=True))

        endp_names = list(self.created_endp) if tracked else []
        cx_names = list(self.created_cx) if tracked else []
        tracked_endps = set(endp_names)
        for endp_or_cx_name in endp_or_cx_names or []:
            endp_cx_pair = self.find_endp_cx(endp_or_cx_name)
            if endp_cx_pair is None:
                logger.warning("Generic endpoint '%s' not found on the LANforge manager, skipping", endp_or_cx_name)
                continue
            endp_names.append(endp_cx_pair[0])
            if endp_cx_pair[1]:
                cx_names.append(endp_cx_pair[1])
            tracked_endps.add(endp_cx_pair[0])
        for endp_name, cx_name in port_endp_cx_names:
            if endp_name in tracked_endps:
                continue
            if not check_exists or self.has_endp(endp_name):
                endp_names.append(endp_name)
                cx_names.append(cx_name)

        if check_exists:
            endp_names = [endp_name for endp_name in endp_names if endp_name not in tracked_endps or self.has_endp(endp_name)]
        endp_names = list(dict.fromkeys(endp_names))
        cx_names = list(dict.fromkeys(cx_names))

        logger.info("Cleaning up generic endpoints if exists: cx=%s, endp=%s", cx_names, endp_names)
        for cx_name in cx_names:
            self.json_post("cli-json/rm_cx", {"test_mgr": "default_tm", "cx_name": cx_name})
        if settle and endp_names:
            time.sleep(settle)
        for endp_name in endp_names:
            self.json_post("cli-json/rm_endp", {"endp_name": endp_name})

        if tracked:
            self.created_cx = []
            self.created_endp = []
            self._stall_since.clear()
            self._gave_up.clear()
        else:
            self.untrack_endps(endp_names)
        return endp_names

    def set_report_timers(self, timer, endp_names=None):
        """Set the report timer, in milliseconds, on the given endpoints."""
        for endp_name in self.created_endp if endp_names is None else endp_names:
            self.set_report_timer(endp_name=endp_name, timer=timer)

    def untrack_endps(self, endp_names):
        """Stop tracking the given endpoints, and their CXs, in the profile."""
        endp_names = set(endp_names)
        cx_names = {"CX_{}".format(endp_name) for endp_name in endp_names} | {"CX_generic-{}".format(endp_name) for endp_name in endp_names}
        self.created_endp = [endp_name for endp_name in self.created_endp if endp_name not in endp_names]
        self.created_cx = [cx_name for cx_name in self.created_cx if cx_name not in cx_names]
        for endp_name in endp_names:
            self._stall_since.pop(endp_name, None)
            self._gave_up.discard(endp_name)

    def get_endp_results(self, endp_names=None, api="generic"):
        """Return LANforge's answer for the endpoints: one endpoint's data, a list of {name: data}, the answer itself if it has neither, or None."""
        endp_names = list(self.created_endp if endp_names is None else endp_names)
        response = self.json_get("/{}/{}".format(api, ",".join(endp_names)))
        if response is None:
            return None
        return response.get("endpoints", response.get("endpoint", response))

    def get_endp_data(self, endp_names=None, batch=True, api="generic"):
        """Return {endpoint name: endpoint data}; defaults to the created endpoints, api is generic or layer4."""
        endp_names = list(self.created_endp if endp_names is None else endp_names)
        if not endp_names:
            return {}
        urls = ["/{}/{}".format(api, ",".join(endp_names))] if batch else ["/{}/{}".format(api, endp_name) for endp_name in endp_names]
        endp_data = {}
        for url in urls:
            response = self.json_get(url)
            if not response:
                logger.debug("No response for %s", url)
                continue
            endp_entries = response.get("endpoints", response.get("endpoint", []))
            if isinstance(endp_entries, dict):
                endp_entries = [{endp_entries["name"]: endp_entries}]
            for endp_entry in endp_entries:
                for endp_key, endp_values in endp_entry.items():
                    # Listing many endpoints keys each one by entity id; the real name is inside it.
                    endp_data[(endp_values.get("name") if isinstance(endp_values, dict) else None) or endp_key] = endp_values
        return endp_data

    def get_endp_statuses(self, endp_names=None, api="generic"):
        """Return {endpoint name: status or None}; None means the endpoint could not be fetched."""
        endp_names = list(self.created_endp if endp_names is None else endp_names)
        endp_data = self.get_endp_data(endp_names, batch=False, api=api)
        return {endp_name: (endp_data[endp_name].get("status", "") if endp_name in endp_data else None) for endp_name in endp_names}

    def get_endp_availability(self, endp_names=None, endp_data=None, running_status="run"):
        """Sort endpoints into missing, not_running and running sets."""
        endp_names = list(self.created_endp if endp_names is None else endp_names)
        endp_data = self.get_endp_data(endp_names) if endp_data is None else endp_data
        endp_availability = {"missing": set(), "not_running": set(), "running": set()}
        for endp_name in endp_names:
            if endp_name not in endp_data:
                endp_availability["missing"].add(endp_name)
            elif str(endp_data[endp_name].get("status", "")).lower() != running_status:
                endp_availability["not_running"].add(endp_name)
            else:
                endp_availability["running"].add(endp_name)
        return endp_availability

    def are_endps_idle(self, idle_statuses=DEFAULT_IDLE_STATUSES, stall_timeout=300, unreachable_is_idle=False,
                       stall_on_active=True, on_status=None, endp_names=None, api="generic"):
        """Return True once every endpoint is idle or has been waited on long enough."""
        now = time.monotonic()
        ready = True
        statuses = {}
        try:
            for endp_name in dict.fromkeys(self.created_endp if endp_names is None else endp_names):
                endp_values = self.get_endp_data([endp_name], batch=False, api=api).get(endp_name)
                status = None if endp_values is None else endp_values.get("status", "")
                statuses[endp_name] = status
                if on_status:
                    on_status(endp_name, status, endp_values)

                if status in idle_statuses or (status is None and unreachable_is_idle):
                    self._clear_stall(endp_name)
                    continue

                if status is not None and not stall_on_active:
                    self._clear_stall(endp_name)
                    ready = False
                    continue

                stalled_for = now - self._stall_since.setdefault(endp_name, now)
                if stalled_for >= stall_timeout:
                    if endp_name not in self._gave_up:
                        logger.warning("%s unresolved (status=%r) for %.0fs (limit %ss) - no longer waiting on it.",
                                       endp_name, status, stalled_for, stall_timeout)
                        self._gave_up.add(endp_name)
                    continue
                ready = False
        except Exception:
            logger.exception("Error while checking generic endpoint status")
            return False
        finally:
            self.last_statuses = statuses
        return ready

    def _clear_stall(self, endp_name):
        self._stall_since.pop(endp_name, None)
        self._gave_up.discard(endp_name)

    def monitor_endps(self, duration=None, interval=5, on_poll=None, stop_when=None, until_idle=False, idle_kwargs=None, batch=True,
                      endp_names=None):
        """Poll endpoints until duration, stop_when or until_idle ends it; returns (reason, endp_data)."""
        if duration is None and stop_when is None and not until_idle:
            raise ValueError("monitor_endps needs a duration, a stop_when callback or until_idle")
        idle_kwargs = idle_kwargs or {}
        start_time = time.monotonic()
        while True:
            endp_data = self.get_endp_data(endp_names, batch=batch)
            if on_poll:
                on_poll(endp_data)
            if stop_when and stop_when(endp_data):
                return "stop_when", endp_data
            if until_idle and self.are_endps_idle(endp_names=endp_names, **idle_kwargs):
                return "idle", endp_data
            remaining = None if duration is None else duration - (time.monotonic() - start_time)
            if remaining is not None and remaining <= 0:
                return "duration", endp_data
            time.sleep(interval if remaining is None else max(0, min(interval, remaining)))

    def get_report_data(self, endp_names=None, results=None, fields=None, parse=None):
        """Return {endpoint name: report values}: the selected fields plus whatever parse(endp_values) returns for each endpoint."""
        if results is None:
            endp_data = self.get_endp_data(endp_names)
        elif isinstance(results, dict):
            endp_data = results
        else:
            endp_data = {}
            for endp_result in results:
                endp_data.update(endp_result)
        report_endp_names = list(endp_data) if endp_names is None else [endp_name for endp_name in endp_names if endp_name in endp_data]
        report_data = {}
        for endp_name in report_endp_names:
            endp_values = endp_data[endp_name]
            endp_report = {field_name: field_value for field_name, field_value in endp_values.items() if fields is None or field_name in fields}
            if parse:
                endp_report.update(parse(endp_values))
            report_data[endp_name] = endp_report
        return report_data
