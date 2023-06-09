#!/usr/bin/env python3
"""
NAME: lf_port_probe.py

PURPOSE: This script will query and display information associated with a specified port.
EXAMPLE:
        # Sample CLI Formate:

            ./lf_port_probe.py --mgr localhost --port_eid 1.1.eth0

SCRIPT_CLASSIFICATION:  Port scanner

SCRIPT_CATEGORIES:  Functional 

NOTES:
        This script performs a targeted query on a specified port and subsequently presents 
        comprehensive information associated with it. The gathered details will include the port's 
        Radio information, Regulatory information.


STATUS: BETA RELEASE

VERIFIED_ON:   28-MAY-2023,
             GUI Version:  5.4.6
             Kernel Version: 6.2.14+

LICENSE:
          Free to distribute and modify. LANforge systems must be licensed.
          Copyright 2023 Candela Technologies Inc

INCLUDE_IN_README: False

"""


import json
import os
import pprint
import sys

if sys.version_info[0] != 3:
    print("This script requires Python 3")
    exit(1)

if 'py-json' not in sys.path:
    sys.path.append(os.path.join(os.path.abspath('..'), 'py-json'))

from time import sleep
from LANforge.lfcli_base import LFCliBase


# see https://stackoverflow.com/questions/9295439/python-json-loads-fails-with-valueerror-invalid-control-character-at-line-1-c/16544933#16544933
# re-load and reexport JSON with  strict=False?

class ProbePort2(LFCliBase):
    def __init__(self,
                 lfhost=None,
                 lfport=None,
                 debug=False,
                 eid_str=None):
        super().__init__(_lfjson_host=lfhost,
                         _lfjson_port=lfport,
                         _debug=debug)
        hunks = eid_str.split(".")
        self.probepath = "/probe/1/%s/%s" % (hunks[-2], hunks[-1])
        # self.decoder = json.JSONDecoder()

    def run(self):
        self.json_post(self.probepath, {})
        sleep(0.2)
        response = self.json_get(self.probepath)
        if not response:
            print("problem probing port %s" % self.probepath)
            exit(1)
        # pprint.pprint(response)
        if "probe-results" not in response:
            print("problem probing port %s" % self.probepath)
            exit(1)

        probe_res = response["probe-results"][0]
        #pprint.pprint(probe_res)
        for (key, value) in probe_res.items():
            # probe_results = [key]
            print("port "+key)
            # pprint.pprint(value['probe results'])
            xlated_results = str(value['probe results']).replace("\\n", "\n").replace("\\r", "\r").replace("\\t", "\t")
            print(xlated_results)


def main():
    parser = LFCliBase.create_bare_argparse(
        prog=__name__,
        description='''\
NAME: lf_port_probe.py

PURPOSE: This script will query and display information associated with a specified port.
EXAMPLE:
        # Sample CLI Formate:

            ./lf_port_probe.py --mgr localhost --port_eid 1.1.eth0

SCRIPT_CLASSIFICATION:  Port scanner

SCRIPT_CATEGORIES:  Functional 

NOTES:
        This script performs a targeted query on a specified port and subsequently presents 
        comprehensive information associated with it. The gathered details will include the port's 
        Radio information, Regulatory information.


STATUS: BETA RELEASE

VERIFIED_ON:   28-MAY-2023,
             GUI Version:  5.4.6
             Kernel Version: 6.2.14+

LICENSE:
          Free to distribute and modify. LANforge systems must be licensed.
          Copyright 2023 Candela Technologies Inc

INCLUDE_IN_README: False

        ''')

    parser.add_argument('--mode', help='Used to force mode of stations')
    parser.add_argument('--port_eid', help='EID of station to be used', default="1.1.eth0")

    args = parser.parse_args()
    probe = ProbePort2(lfhost=args.mgr,
                       lfport=args.mgr_port,
                       debug=args.debug,
                       eid_str=args.port_eid)
    probe.run()


if __name__ == "__main__":
    main()
