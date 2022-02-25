#!/usr/bin/env python3

"""
NAME: cc_module_test.py

PURPOSE:
to test the dynamic import of a controller module

SETUP:
None

EXAMPLE:
    There is a unit test included to try sample command scenarios
     ./cc_module_test.py --scheme ssh --dest localhost --port 8887 --user admin --passwd Cisco123 --ap APCC9C.3EF11.1140 --series 9800 --prompt "WLC1" --timeout 10 --band '6g' --module 'cc_module_9800_3504'


COPYWRITE
    Copyright 2021 Candela Technologies Inc
    License: Free to distribute and modify. LANforge systems must be licensed.

INCLUDE_IN_README
"""

import sys
if sys.version_info[0] != 3:
    print("This script requires Python 3")
    exit()

import argparse
import logging
import importlib
import os

sys.path.append(os.path.join(os.path.abspath(__file__ + "././")))

logger = logging.getLogger(__name__)
lf_logger_config = importlib.import_module("py-scripts.lf_logger_config")


class create_module_test_object:
    def __init__(self,
                 cs=None):
        if cs is None:
            raise ValueError('Controller series must be passed in ')
        else:
            self.cs = cs

# please do not delete
# modifying existing tests.

    # This sample runs thought dumping status
    def sample_test_dump_status(self):
        self.cs.show_ap_config_slots()
        self.cs.show_ap_summary()
        self.cs.no_logging_console()
        self.cs.line_console_0()
        self.cs.show_wlan_summary()
        # cs.show_ap_dot11_5gz_summary()
        # cs.show_ap_dot11_24gz_summary()
        self.cs.show_ap_bssid_5ghz()

    # sample setting dtim dot11 5ghz : delivery traffic indication message
    def sample_test_setting_dtim(self):
        logger.info("sample_test_setting_dtim")
        # This needs to be here to disable and delete
        self.cs.dtim = '1'

        self.cs.wlan = 'wpa2_wlan_7'
        self.cs.wlanID = '7'
        self.cs.wlanSSID = 'wpa2_wlan_7'
        self.cs.tx_power = '1'
        self.cs.security_key = 'wpa2_wlan_7'

        self.cs.tag_policy = 'RM204-TB1'
        self.cs.policy_profile = 'default-policy-profile'
        # summary
        self.cs.show_ap_summary()

        # disable
        self.cs.show_ap_dot11_5gz_shutdown()
        self.cs.show_ap_dot11_24gz_shutdown()

        # disable_wlan
        self.cs.wlan_shutdown()
        # disable_network_5ghz
        self.cs.ap_dot11_5ghz_shutdown()
        # disable_network_24ghz
        self.cs.ap_dot11_24ghz_shutdown()
        # manual
        self.cs.ap_dot11_5ghz_radio_role_manual_client_serving()
        self.cs.ap_dot11_24ghz_radio_role_manual_client_serving()

        # Configuration for 5g

        # txPower
        self.cs.config_dot11_5ghz_tx_power()
        self.cs.bandwidth = '20'
        # bandwidth (to set to 20 if channel change does not support)
        self.cs.config_dot11_5ghz_channel_width()
        self.cs.channel = '100'
        # channel
        self.cs.config_dot11_5ghz_channel()
        self.cs.bandwidth = '40'
        # bandwidth
        self.cs.config_dot11_5ghz_channel_width()
        # show_wlan_summary
        self.cs.show_wlan_summary()

        # delete wlan
        self.cs.config_no_wlan()

        # create_wlan_wpa2
        self.cs.config_wlan_wpa2()

        # wireless_tag_policy
        self.cs.config_wireless_tag_policy_and_policy_profile()

        # show_wlan_summary
        self.cs.show_wlan_summary()

        # somehow during the configure the WLAN gets enabled
        # disable_wlan
        self.cs.wlan_shutdown()

        # show_wlan_summary
        self.cs.show_wlan_summary()

        # % WLAN needs to be disabled before performing this operation.
        self.cs.config_dtim_dot11_5ghz()

        # enable_wlan
        self.cs.config_enable_wlan_send_no_shutdown()
        # enable_network_5ghz
        self.cs.config_no_ap_dot11_5ghz_shutdown()
        # enable_network_24ghz
        # self.cs.config_no_ap_dot11_5ghz_shutdown()
        # enable
        self.cs.config_ap_no_dot11_5ghz_shutdown()
        # config_ap_no_dot11_24ghz_shutdown
        # advanced
        self.cs.show_ap_dot11_5gz_summary()
        # self.cs.show_ap_dot11_24gz_summary()
        # show_wlan_summary
        self.cs.show_wlan_summary()

    # This sample runs though the sequence of commands used
    # by tx_power script

    # TODO unit test for 6g wlan, 5g wlan, 2g wlan, and all three

    def sample_test_tx_power_sequence(self):

        # series of commands to create a wlan , similiar to how tx_power works.
        # pass in the ap and band from the command line
        # self.cs.ap = 'APA453.0E7B.CF9C'
        # self.cs.band = '5g'

        logger.info("sample_test_tx_power_sequence")
        # This needs to be here to disable and delete
        self.cs.wlan = 'wpa2_wlan_3'
        self.cs.wlanID = '3'
        self.cs.wlanSSID = 'wpa2_wlan_3'
        self.cs.tx_power = '1'
        self.cs.security_key = 'wpa2_wlan_3'

        self.cs.tag_policy = 'RM204-TB1'
        self.cs.policy_profile = 'default-policy-profile'

        # no_logging_console
        self.cs.no_logging_console()
        # line_console_0
        self.cs.line_console_0()
        # summary
        self.cs.show_ap_summary()

        # disable
        self.cs.show_ap_dot11_5gz_shutdown()
        self.cs.show_ap_dot11_24gz_shutdown()

        # disable_wlan
        self.cs.wlan_shutdown()
        # disable_network_5ghz
        self.cs.ap_dot11_5ghz_shutdown()
        # disable_network_24ghz
        self.cs.ap_dot11_24ghz_shutdown()
        # manual
        self.cs.ap_dot11_5ghz_radio_role_manual_client_serving()
        self.cs.ap_dot11_24ghz_radio_role_manual_client_serving()

        # Configuration for 5g

        # txPower
        self.cs.config_dot11_5ghz_tx_power()
        self.cs.bandwidth = '20'
        # bandwidth (to set to 20 if channel change does not support)
        self.cs.config_dot11_5ghz_channel_width()
        self.cs.channel = '100'
        # channel
        self.cs.config_dot11_5ghz_channel()
        self.cs.bandwidth = '40'
        # bandwidth
        self.cs.config_dot11_5ghz_channel_width()
        # show_wlan_summary
        self.cs.show_wlan_summary()

        # Configuration for 6g
        # txPower
        # self.cs.config_dot11_6ghz_tx_power()
        # self.cs.bandwidth = '20'
        # # bandwidth (to set to 20 if channel change does not support)
        # self.cs.config_dot11_6ghz_channel_width()
        # self.cs.channel = '36'
        # # channel
        # self.cs.config_dot11_6ghz_channel()
        # self.cs.bandwidth = '40'
        # # bandwidth
        # self.cs.config_dot11_6ghz_channel_width()
        # # show_wlan_summary
        # self.cs.show_wlan_summary()

        # delete_wlan
        # TODO (there were two in tx_power the logs)
        # need to check if wlan present
        # delete wlan
        self.cs.config_no_wlan()

        # Create open
        # self.cs.wlan = 'open-wlan_3'
        # self.cs.wlanID = '3'
        # self.cs.wlanSSID = 'open-wlan_3'

        # create_wlan  open
        # self.cs.wlan = 'open-wlan'
        # self.cs.wlanID = '1'
        # self.cs.wlanSSID = 'open-wlan'
        # self.cs.config_wlan_open()

        # create_wlan_wpa2
        self.cs.config_wlan_wpa2()

        # create_wlan_wpa3
        # self.cs.wlan = 'wpa3_wlan_4'
        # self.cs.wlanID = '4'
        # self.cs.wlanSSID = 'wpa3_wlan_4'
        # self.cs.security_key = 'hello123'
        # self.cs.config_wlan_wpa3()

        # wireless_tag_policy
        self.cs.config_wireless_tag_policy_and_policy_profile()
        # enable_wlan
        self.cs.config_enable_wlan_send_no_shutdown()
        # enable_network_5ghz
        self.cs.config_no_ap_dot11_5ghz_shutdown()
        # enable_network_24ghz
        # self.cs.config_no_ap_dot11_5ghz_shutdown()
        # enable
        self.cs.config_ap_no_dot11_5ghz_shutdown()
        # config_ap_no_dot11_24ghz_shutdown
        # advanced
        self.cs.show_ap_dot11_5gz_summary()
        # self.cs.show_ap_dot11_24gz_summary()
        # show_wlan_summary
        self.cs.show_wlan_summary()

    # TODO unit test for 6g wlan, 5g wlan, 2g wlan, and all three

    def test_config_tx_power_6g_wpa3(self):
        # TODO : leave for now for reference
        # WLC1#show ap summary
        # Number of APs: 3
        #
        # AP Name                            Slots    AP Model              Ethernet MAC    Radio MAC       Location
        # -------------------------------------------------------------------------------------------------------------------------
        # APCC9C.3EF4.DDE0                     3      CW9166I-B             cc9c.3ef4.dde0  10f9.20fd.e200  default location
        # APCC9C.3EF1.1140                     3      CW9164I-B             cc9c.3ef1.1140  10f9.20fd.fa60  default location
        # APA453.0E7B.CF9C                     2      C9120AXE-B            a453.0e7b.cf9c  d4ad.bda2.2ce0  default location

        # series of commands to create a wlan , similiar to how tx_power works.
        # pass in the ap and band from the command line
        # self.cs.ap = 'APA453.0E7B.CF9C'
        # self.cs.band = '5g'

        logger.info("test_config_tx_power_6g_wpa3")
        # This needs to be here to disable and delete
        self.cs.wlan = '6G-wpa3-AP3'
        self.cs.wlanID = '15'
        self.cs.wlanSSID = '6G-wpa3-AP3'
        self.cs.tx_power = '1'
        # self.cs.security_key = 'wpa3_wlan_4_6g'
        self.cs.security_key = 'hello123'

        self.cs.tag_policy = 'RM204-TB1-AP3'
        self.cs.policy_profile = 'default-policy-profile'

        # no_logging_console
        self.cs.no_logging_console()
        # line_console_0
        self.cs.line_console_0()
        # summary
        self.cs.show_ap_summary()

        # disable
        self.cs.show_ap_dot11_6gz_shutdown()
        self.cs.show_ap_dot11_5gz_shutdown()
        self.cs.show_ap_dot11_24gz_shutdown()

        # disable_wlan
        self.cs.wlan_shutdown()
        # disable_network_6ghz
        self.cs.ap_dot11_6ghz_shutdown()
        # disable_network_5ghz
        self.cs.ap_dot11_5ghz_shutdown()
        # disable_network_24ghz
        self.cs.ap_dot11_24ghz_shutdown()
        # manual
        self.cs.ap_dot11_6ghz_radio_role_manual_client_serving()
        self.cs.ap_dot11_5ghz_radio_role_manual_client_serving()
        self.cs.ap_dot11_24ghz_radio_role_manual_client_serving()

        # Configuration for 6g

        # Configuration for 6g
        # txPower
        # TODO is this still needed
        self.cs.config_dot11_6ghz_tx_power()
        self.cs.bandwidth = '20'
        # bandwidth (to set to 20 if channel change does not support)
        self.cs.config_dot11_6ghz_channel_width()
        self.cs.channel = '1'
        # channel
        self.cs.config_dot11_6ghz_channel()
        self.cs.bandwidth = '40'
        # bandwidth
        self.cs.config_dot11_6ghz_channel_width()
        # show_wlan_summary
        self.cs.show_wlan_summary()

        # delete_wlan
        # TODO (there were two in tx_power the logs)
        # need to check if wlan present
        # delete wlan
        # self.cs.config_no_wlan()

        # create_wlan_wpa3
        self.cs.config_wlan_wpa3()

        # wireless_tag_policy
        self.cs.config_wireless_tag_policy_and_policy_profile()
        # enable_wlan
        self.cs.config_enable_wlan_send_no_shutdown()
        # enable_network_5ghz
        self.cs.config_no_ap_dot11_6ghz_shutdown()
        # enable_network_24ghz
        # self.cs.config_no_ap_dot11_5ghz_shutdown()
        # enable
        self.cs.config_ap_no_dot11_6ghz_shutdown()
        # config_ap_no_dot11_24ghz_shutdown
        # advanced
        self.cs.show_ap_dot11_6gz_summary()
        # show_wlan_summary
        self.cs.show_wlan_summary()

    def test_config_tx_power_5g_open(self):

        logger.info("test_config_tx_power_open")
        # configure once at the top
        self.cs.wlan = 'open-wlan-14'
        self.cs.wlanID = '14'
        self.cs.wlanSSID = 'open-wlan-14'
        self.cs.config_wlan_open()

        # wireless_tag_policy
        self.cs.tag_policy = 'RM204-TB1-AP2'
        self.cs.policy_profile = 'default-policy-profile'
        self.cs.config_wireless_tag_policy_and_policy_profile()

        self.cs.tx_power = '1'
        self.cs.channel = '149'
        self.cs.bandwidth = '40'

        # no_logging_console
        self.cs.no_logging_console()
        # line_console_0
        self.cs.line_console_0()
        # summary
        self.cs.show_ap_summary()

        # disable
        self.cs.show_ap_dot11_5gz_shutdown()
        self.cs.show_ap_dot11_24gz_shutdown()

        # disable_wlan only need wlan
        self.cs.wlan_shutdown()
        # disable_network_5ghz
        self.cs.ap_dot11_5ghz_shutdown()
        # disable_network_24ghz
        self.cs.ap_dot11_24ghz_shutdown()
        # manual
        self.cs.ap_dot11_5ghz_radio_role_manual_client_serving()
        self.cs.ap_dot11_24ghz_radio_role_manual_client_serving()

        # Configuration for 5g

        # txPower
        self.cs.config_dot11_5ghz_tx_power()
        # bandwidth (to set to 20 if channel change does not support)
        self.cs.bandwidth = '20'
        self.cs.config_dot11_5ghz_channel_width()
        # channel
        self.cs.channel = '100'
        self.cs.config_dot11_5ghz_channel()
        self.cs.channel = '5'
        self.cs.config_dot11_24ghz_channel()
        # bandwidth
        self.cs.bandwidth = '40'
        self.cs.config_dot11_5ghz_channel_width()
        # show_wlan_summary
        self.cs.show_wlan_summary()

        # delete_wlan
        # TODO (there were two in tx_power the logs)
        # need to check if wlan present
        # delete wlan
        # self.cs.config_no_wlan()

        # create_wlan  open

        # enable_wlan
        self.cs.config_enable_wlan_send_no_shutdown()
        # enable_network_5ghz
        self.cs.config_no_ap_dot11_5ghz_shutdown()
        # enable_network_24ghz
        self.cs.config_no_ap_dot11_24ghz_shutdown()
        # enable
        self.cs.config_ap_no_dot11_5ghz_shutdown()
        self.cs.config_ap_no_dot11_24ghz_shutdown()
        # config_ap_no_dot11_24ghz_shutdown
        # advanced
        self.cs.show_ap_dot11_5gz_summary()
        self.cs.show_ap_dot11_24gz_summary()
        # show_wlan_summary
        self.cs.show_wlan_summary()

        self.cs.show_ap_dot11_5gz_summary()
        self.cs.show_ap_bssid_5ghz()

    # 2g test

    def test_config_tx_power_2g_open(self):

        logger.info("test_config_tx_power_open_2g")
        # configure once at the top
        self.cs.wlan = 'open-wlan-2-2g'
        self.cs.wlanID = '2'
        self.cs.wlanSSID = 'open-wlan-2-2g'
        self.cs.config_wlan_open()

        # wireless_tag_policy
        self.cs.tag_policy = 'RM204-TB1-AP2'
        self.cs.policy_profile = 'default-policy-profile'
        self.cs.config_wireless_tag_policy_and_policy_profile()

        self.cs.tx_power = '5'
        self.cs.channel = '2'
        self.cs.bandwidth = '20'

        # no_logging_console
        self.cs.no_logging_console()
        # line_console_0
        self.cs.line_console_0()
        # summary
        self.cs.show_ap_summary()

        # disable
        self.cs.show_ap_dot11_5gz_shutdown()
        self.cs.show_ap_dot11_24gz_shutdown()

        # disable_wlan only need wlan
        self.cs.wlan_shutdown()
        # disable_network_5ghz
        self.cs.ap_dot11_5ghz_shutdown()
        # disable_network_24ghz
        self.cs.ap_dot11_24ghz_shutdown()
        # manual
        self.cs.ap_dot11_5ghz_radio_role_manual_client_serving()
        # self.cs.ap_dot11_24ghz_radio_role_manual_client_serving()

        # Configuration for 5g

        # txPower
        self.cs.config_dot11_24ghz_tx_power()
        # bandwidth (to set to 20 if channel change does not support)
        self.cs.bandwidth = '20'
        # self.cs.config_dot11_24ghz_channel_width()
        # channel
        self.cs.config_dot11_24ghz_channel()
        # bandwidth
        self.cs.bandwidth = '20'
        # self.cs.config_dot11_24ghz_channel_width()
        # show_wlan_summary
        self.cs.show_wlan_summary()

        # delete_wlan
        # TODO (there were two in tx_power the logs)
        # need to check if wlan present
        # delete wlan
        self.cs.config_no_wlan()

        # create_wlan  open

        # enable_wlan
        self.cs.config_enable_wlan_send_no_shutdown()
        # enable_network_5ghz
        # self.cs.config_no_ap_dot11_5ghz_shutdown()
        # enable_network_24ghz
        self.cs.config_no_ap_dot11_24ghz_shutdown()
        # enable
        # self.cs.config_ap_no_dot11_5ghz_shutdown()
        self.cs.config_ap_no_dot11_24ghz_shutdown()
        # config_ap_no_dot11_24ghz_shutdown
        # advanced
        # self.cs.show_ap_dot11_5gz_summary()
        self.cs.show_ap_dot11_24gz_summary()
        # show_wlan_summary
        self.cs.show_wlan_summary()

        self.cs.show_ap_dot11_24gz_summary()
        self.cs.show_ap_bssid_24ghz()

    # tb2

    def test_config_tx_power_5g_open_tb2_AP2(self):

        logger.info("test_config_tx_power_open")
        # configure once at the top
        self.cs.wlan = 'open-wlan-14'
        self.cs.wlanID = '14'
        self.cs.wlanSSID = 'open-wlan-14'
        self.cs.config_wlan_open()

        # wireless_tag_policy
        self.cs.tag_policy = 'RM204-TB2-AP1'
        self.cs.policy_profile = 'default-policy-profile'
        self.cs.config_wireless_tag_policy_and_policy_profile()

        self.cs.tx_power = '1'
        self.cs.channel = '36'
        self.cs.bandwidth = '40'

        # no_logging_console
        self.cs.no_logging_console()
        # line_console_0
        self.cs.line_console_0()
        # summary
        self.cs.show_ap_summary()

        # disable
        self.cs.show_ap_dot11_5gz_shutdown()
        self.cs.show_ap_dot11_24gz_shutdown()

        # disable_wlan only need wlan
        self.cs.wlan_shutdown()
        # disable_network_5ghz
        self.cs.ap_dot11_5ghz_shutdown()
        # disable_network_24ghz
        self.cs.ap_dot11_24ghz_shutdown()
        # manual
        self.cs.ap_dot11_5ghz_radio_role_manual_client_serving()
        self.cs.ap_dot11_24ghz_radio_role_manual_client_serving()

        # Configuration for 5g

        # txPower
        self.cs.config_dot11_5ghz_tx_power()
        # bandwidth (to set to 20 if channel change does not support)
        self.cs.bandwidth = '20'
        self.cs.config_dot11_5ghz_channel_width()
        # channel
        self.cs.config_dot11_5ghz_channel()
        # bandwidth
        self.cs.bandwidth = '40'
        self.cs.config_dot11_5ghz_channel_width()
        # show_wlan_summary
        self.cs.show_wlan_summary()

        # delete_wlan
        # TODO (there were two in tx_power the logs)
        # need to check if wlan present
        # delete wlan
        # self.cs.config_no_wlan()

        # create_wlan  open

        # enable_wlan
        self.cs.config_enable_wlan_send_no_shutdown()
        # enable_network_5ghz
        self.cs.config_no_ap_dot11_5ghz_shutdown()
        # enable_network_24ghz
        self.cs.config_no_ap_dot11_24ghz_shutdown()
        # enable
        self.cs.config_ap_no_dot11_5ghz_shutdown()
        self.cs.config_ap_no_dot11_24ghz_shutdown()
        # config_ap_no_dot11_24ghz_shutdown
        # advanced
        self.cs.show_ap_dot11_5gz_summary()
        self.cs.show_ap_dot11_24gz_summary()
        # show_wlan_summary
        self.cs.show_wlan_summary()

    def test_config_tx_power_5g_open_tb2_AP1(self):

        logger.info("test_config_tx_power_open")
        # configure once at the top
        self.cs.wlan = 'open-wlan-13'
        self.cs.wlanID = '13'
        self.cs.wlanSSID = 'open-wlan-13'
        self.cs.config_wlan_open()

        # wireless_tag_policy
        self.cs.tag_policy = 'RM204-TB2-AP1'
        self.cs.policy_profile = 'default-policy-profile'
        self.cs.config_wireless_tag_policy_and_policy_profile()

        self.cs.tx_power = '1'
        self.cs.channel = '100'
        self.cs.bandwidth = '40'

        # no_logging_console
        self.cs.no_logging_console()
        # line_console_0
        self.cs.line_console_0()
        # summary
        self.cs.show_ap_summary()

        # disable
        self.cs.show_ap_dot11_5gz_shutdown()
        self.cs.show_ap_dot11_24gz_shutdown()

        # disable_wlan only need wlan
        self.cs.wlan_shutdown()
        # disable_network_5ghz
        self.cs.ap_dot11_5ghz_shutdown()
        # disable_network_24ghz
        self.cs.ap_dot11_24ghz_shutdown()
        # manual
        self.cs.ap_dot11_5ghz_radio_role_manual_client_serving()
        self.cs.ap_dot11_24ghz_radio_role_manual_client_serving()

        # Configuration for 5g

        # txPower
        self.cs.config_dot11_5ghz_tx_power()
        # bandwidth (to set to 20 if channel change does not support)
        self.cs.bandwidth = '20'
        self.cs.config_dot11_5ghz_channel_width()
        # channel
        self.cs.config_dot11_5ghz_channel()
        # bandwidth
        self.cs.bandwidth = '40'
        self.cs.config_dot11_5ghz_channel_width()
        # show_wlan_summary
        self.cs.show_wlan_summary()

        # delete_wlan
        # TODO (there were two in tx_power the logs)
        # need to check if wlan present
        # delete wlan
        # self.cs.config_no_wlan()

        # create_wlan  open

        # enable_wlan
        self.cs.config_enable_wlan_send_no_shutdown()
        # enable_network_5ghz
        self.cs.config_no_ap_dot11_5ghz_shutdown()
        # enable_network_24ghz
        self.cs.config_no_ap_dot11_24ghz_shutdown()
        # enable
        self.cs.config_ap_no_dot11_5ghz_shutdown()
        self.cs.config_ap_no_dot11_24ghz_shutdown()
        # config_ap_no_dot11_24ghz_shutdown
        # advanced
        self.cs.show_ap_dot11_5gz_summary()
        self.cs.show_ap_dot11_24gz_summary()
        # show_wlan_summary
        self.cs.show_wlan_summary()

    def test_config_tx_power_wpa2(self):

        logger.info("sample_test_tx_power_sequence")

        # no_logging_console
        self.cs.no_logging_console()
        # line_console_0
        self.cs.line_console_0()
        # summary
        self.cs.show_ap_summary()

        # disable
        self.cs.show_ap_dot11_5gz_shutdown()
        self.cs.show_ap_dot11_24gz_shutdown()
        # This needs to be here to disable and delete
        self.cs.wlan = 'wpa2_wlan_3'

        # disable_wlan
        self.cs.wlan_shutdown()
        # disable_network_5ghz
        self.cs.ap_dot11_5ghz_shutdown()
        # disable_network_24ghz
        self.cs.ap_dot11_24ghz_shutdown()
        # manual
        self.cs.ap_dot11_5ghz_radio_role_manual_client_serving()
        # self.cs.ap_dot11_24ghz_radio_role_manual_client_serving()
        self.cs.tx_power = '1'

        # Configuration for 5g

        # txPower
        self.cs.config_dot11_5ghz_tx_power()
        self.cs.bandwidth = '20'
        # bandwidth (to set to 20 if channel change does not support)
        self.cs.config_dot11_5ghz_channel_width()
        self.cs.channel = '100'
        # channel
        self.cs.config_dot11_5ghz_channel()
        self.cs.bandwidth = '40'
        # bandwidth
        self.cs.config_dot11_5ghz_channel_width()
        # show_wlan_summary
        self.cs.show_wlan_summary()

        # delete_wlan
        # TODO (there were two in tx_power the logs)
        # need to check if wlan present
        self.cs.wlan = 'wpa2_wlan_3'

        # delete wlan
        self.cs.config_no_wlan()

        # create_wlan_wpa2
        self.cs.wlan = 'wpa2_wlan_3'
        self.cs.wlanID = '3'
        self.cs.wlanSSID = 'wpa2_wlan_3'
        self.cs.security_key = 'hello123'
        self.cs.config_wlan_wpa2()

        # wireless_tag_policy
        self.cs.tag_policy = 'RM204-TB1'
        self.cs.policy_profile = 'default-policy-profile'
        self.cs.config_wireless_tag_policy_and_policy_profile()
        # enable_wlan
        self.cs.config_enable_wlan_send_no_shutdown()
        # enable_network_5ghz
        self.cs.config_no_ap_dot11_5ghz_shutdown()
        # enable_network_24ghz
        # self.cs.config_no_ap_dot11_24ghz_shutdown()
        # enable
        self.cs.config_ap_no_dot11_5ghz_shutdown()
        # config_ap_no_dot11_24ghz_shutdown
        # advanced
        self.cs.show_ap_dot11_5gz_summary()
        # self.cs.show_ap_dot11_24gz_summary()
        # show_wlan_summary
        self.cs.show_wlan_summary()

    def test_config_tx_power_wpa2_IDIC(self):

        logger.info("sample_test_tx_power_sequence")

        # no_logging_console
        self.cs.no_logging_console()
        # line_console_0
        self.cs.line_console_0()
        # summary
        self.cs.show_ap_summary()

        # disable
        self.cs.show_ap_dot11_5gz_shutdown()
        self.cs.show_ap_dot11_24gz_shutdown()
        # This needs to be here to disable and delete
        self.cs.wlan = 'wpa2_wlan_3_CF9C'

        # disable_wlan
        self.cs.wlan_shutdown()
        # disable_network_5ghz
        self.cs.ap_dot11_5ghz_shutdown()
        # disable_network_24ghz
        self.cs.ap_dot11_24ghz_shutdown()
        # manual
        self.cs.ap_dot11_5ghz_radio_role_manual_client_serving()
        # self.cs.ap_dot11_24ghz_radio_role_manual_client_serving()
        self.cs.tx_power = '1'

        # Configuration for 5g

        # txPower
        self.cs.config_dot11_5ghz_tx_power()
        self.cs.bandwidth = '20'
        # bandwidth (to set to 20 if channel change does not support)
        self.cs.config_dot11_5ghz_channel_width()
        self.cs.channel = '100'
        # channel
        self.cs.config_dot11_5ghz_channel()
        self.cs.bandwidth = '40'
        # bandwidth
        self.cs.config_dot11_5ghz_channel_width()
        # show_wlan_summary
        self.cs.show_wlan_summary()

        # delete_wlan
        # TODO (there were two in tx_power the logs)
        # need to check if wlan present
        self.cs.wlan = 'wpa2_wlan_3'

        # delete wlan
        self.cs.config_no_wlan()

        # create_wlan_wpa2
        self.cs.wlan = 'wpa2_wlan_3_CF9C'
        self.cs.wlanID = '3'
        self.cs.wlanSSID = 'wpa2_wlan_3_CF9C'
        self.cs.security_key = 'hello123'
        self.cs.config_wlan_wpa2()

        # wireless_tag_policy
        self.cs.tag_policy = 'RM204-TB1'
        self.cs.policy_profile = 'default-policy-profile'
        self.cs.config_wireless_tag_policy_and_policy_profile()
        # enable_wlan
        self.cs.config_enable_wlan_send_no_shutdown()
        # enable_network_5ghz
        self.cs.config_no_ap_dot11_5ghz_shutdown()
        # enable_network_24ghz
        # self.cs.config_no_ap_dot11_24ghz_shutdown()
        # enable
        self.cs.config_ap_no_dot11_5ghz_shutdown()
        # config_ap_no_dot11_24ghz_shutdown
        # advanced
        self.cs.show_ap_dot11_5gz_summary()
        # self.cs.show_ap_dot11_24gz_summary()
        # show_wlan_summary
        self.cs.show_wlan_summary()

        summary = self.cs.show_ap_wlan_summary()
        logger.info(summary)


# unit test for controller wrapper
def main():
    # arguments
    parser = argparse.ArgumentParser(
        prog='cc_module_test.py',
        formatter_class=argparse.RawTextHelpFormatter,
        epilog='''\
            cc_module_test.py: wrapper for interface to a series of controllers
            ''',
        description='''\
NAME: cc_module_test.py

PURPOSE:
to test the dynamic import of a controller module

SETUP:
None

EXAMPLE:
    There is a unit test included to try sample command scenarios


COPYWRITE
    Copyright 2021 Candela Technologies Inc
    License: Free to distribute and modify. LANforge systems must be licensed.

INCLUDE_IN_README
---------
            ''')

# ./cc_module_test.py --scheme ssh --dest localhost --port 8887 --user admin --passwd Cisco123 --ap APA453.0E7B.CF9C --series 9800 --prompt "WLC1" --timeout 10 --band '5g' --module "cc_module_9800_3504"

    # These commands are just needed to interact it can be done in class methods.abs(
    parser.add_argument("--dest", type=str, help="address of the cisco controller", required=True)
    parser.add_argument("--port", type=str, help="control port on the controller", required=True)
    parser.add_argument("--user", type=str, help="credential login/username", required=True)
    parser.add_argument("--passwd", type=str, help="credential password", required=True)
    parser.add_argument("--ap", type=str, help="ap name APA453.0E7B.CF9C", required=True)
    parser.add_argument("--prompt", type=str, help="controller prompt", required=True)
    parser.add_argument("--band", type=str, help="band to test 24g, 5g, 6g", required=True)
    parser.add_argument("--series", type=str, help="controller series", choices=["9800", "3504"], required=True)
    parser.add_argument("--scheme", type=str, choices=["serial", "ssh", "telnet"], help="Connect via serial, ssh or telnet")
    parser.add_argument("--timeout", type=str, help="timeout value", default=3)
    parser.add_argument("--module", type=str, help="series module", required=True)

    args = parser.parse_args()

    # set up logger
    logger_config = lf_logger_config.lf_logger_config()

    # dynamic import of the controller module
    # 'cc_module_9800_3504'
    series = importlib.import_module(args.module)

    # create the controller
    cc = series.create_controller_series_object(
        scheme=args.scheme,
        dest=args.dest,
        user=args.user,
        passwd=args.passwd,
        prompt=args.prompt,
        series=args.series,
        ap=args.ap,
        port=args.port,
        band=args.band,
        timeout=args.timeout)

    # cc.show_ap_config_slots()

    mt = create_module_test_object(cs=cc)

    mt.sample_test_dump_status()

    mt.test_config_tx_power_6g_wpa3()

    # cc.show_ap_summary()
    # cc.no_logging_console()
    # cc.line_console_0()
    # cc.show_wlan_summary()
    # cc.show_ap_dot11_5gz_summary()


if __name__ == "__main__":
    main()
