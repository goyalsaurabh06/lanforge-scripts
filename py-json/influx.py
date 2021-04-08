#!/usr/bin/env python3

# pip3 install influxdb

import sys

if sys.version_info[0] != 3:
    print("This script requires Python 3")
    exit(1)

import requests
import json
from influxdb import InfluxDBClient
import datetime
from LANforge.lfcli_base import LFCliBase
import time


class RecordInflux(LFCliBase):
    def __init__(self,
                 _lfjson_host="lanforge",
                 _lfjson_port=8080,
                 _influx_host="localhost",
                 _influx_port=8086,
                 _influx_user=None,
                 _influx_passwd=None,
                 _influx_db=None,
                 _debug_on=False,
                 _exit_on_fail=False):
        super().__init__(_lfjson_host, _lfjson_port,
                         _debug=_debug_on,
                         _exit_on_fail=_exit_on_fail)
        self.influx_host = _influx_host
        self.influx_port = _influx_port
        self.influx_user = _influx_user
        self.influx_passwd = _influx_passwd
        self.influx_db = _influx_db
        self.client = InfluxDBClient(self.influx_host,
                                     self.influx_port,
                                     self.influx_user,
                                     self.influx_passwd,
                                     self.influx_db)

    def post_to_influx(self, key, value):
        data = dict()
        data["measurement"] = key
        data["tags"] = dict()
        data["tags"]["host"] = self.influx_host
        data["tags"]["region"] = 'us-west'
        data["time"] = str(datetime.datetime.utcnow().isoformat())
        data["fields"] = dict()
        data["fields"]["value"] = value
        data1 = [data]
        print(data1)

        json_body = [
            {
                "measurement": key,
                "tags": {
                    "host": self.influx_host,
                    "region": "us-west"
                },
                "time": str(datetime.datetime.utcnow().isoformat()),
                "fields": {
                    "value": value
                }
            }
        ]
        print(json_body)
        self.client.write_points(data1)

    # Don't use this unless you are sure you want to.
    # More likely you would want to generate KPI in the
    # individual test cases and poke those relatively small bits of
    # info into influxdb.
    # This will not return until the 'longevity' timer has expired.
    def monitor_port_data(self,
                          lanforge_host="localhost",
                          devices=None,
                          longevity=None,
                          monitor_interval=None):
        url = 'http://' + lanforge_host + ':8080/port/1/1/'
        end = datetime.datetime.now() + datetime.timedelta(0, longevity)
        while datetime.datetime.now() < end:
            for station in devices:
                url1 = url + station
                response = json.loads(requests.get(url1).text)

                # Poke everything into influx db
                for key in response['interface'].keys():
                    self.posttoinflux("%s-%s" % (station, key), response['interface'][key])

            time.sleep(monitor_interval)
