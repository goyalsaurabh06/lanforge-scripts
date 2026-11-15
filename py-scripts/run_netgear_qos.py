#!/usr/bin/env python3
"""Optionally configure a NETGEAR Orbi AP, then run the existing LANforge QoS test."""

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path('/home/lanforge')
SCRIPTS = ROOT / 'lanforge-scripts' / 'py-scripts'
AP_SCRIPT = ROOT / 'lanforge-scripts' / 'py-json' / 'netgear_ap_config.py'
QOS_SCRIPT = SCRIPTS / 'throughput_qos.py'
VRF_SCRIPT = ROOT / 'vrf_exec.bash'


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--push_config', action='store_true', help='Configure AP before QoS test')
    parser.add_argument('--mgr', required=True, help='LANforge manager IP')
    parser.add_argument('--mgr_port', type=int, default=8080)
    parser.add_argument('--upstream', default='eth2', help='VRF interface and QoS upstream port')
    parser.add_argument('--ssid', required=True)
    parser.add_argument('--password', required=True, help='Wi-Fi passphrase shared by AP and stations')
    parser.add_argument('--security', default='wpa2', choices=['wpa2', 'wpa3', 'wpa2+wpa3', 'wpa2mixed', 'wpa3mixed'])
    parser.add_argument('--bands', default='5g', choices=['2.4g', '5g', 'dualband'])
    parser.add_argument('--num_stations_2g', type=int, default=0)
    parser.add_argument('--num_stations_5g', type=int, default=10)
    parser.add_argument('--radio_2g', default='wiphy0')
    parser.add_argument('--radio_5g', default='wiphy0')
    parser.add_argument('--2g_channel', type=int, default=1)
    parser.add_argument('--5g_channel', type=int, default=36)
    parser.add_argument('--gateway_ip', default='10.168.168.1')
    parser.add_argument('--login_user', default='admin')
    parser.add_argument('--login_pw', help='AP admin password; otherwise AP script uses its existing fallback')
    parser.add_argument('--ap_wait', type=int, default=15, help='Additional seconds after AP config returns')
    parser.add_argument('--test_duration', default='10m')
    parser.add_argument('--download', default='100000000')
    parser.add_argument('--upload', default='100000000')
    parser.add_argument('--traffic_type', choices=['lf_tcp', 'lf_udp'], default='lf_tcp')
    parser.add_argument('--tos', default='VO,VI,BK,BE')
    parser.add_argument('--ap_name', default='Netgear-Orbi371')
    parser.add_argument('--no_create_sta', action='store_true', help='Use existing stations instead')
    args = parser.parse_args()
    if args.bands == '5g' and args.num_stations_5g <= 0:
        parser.error('--num_stations_5g must be positive for 5g')
    if args.bands == '2.4g' and args.num_stations_2g <= 0:
        parser.error('--num_stations_2g must be positive for 2.4g')
    if args.bands == 'dualband' and (args.num_stations_2g <= 0 or args.num_stations_5g <= 0):
        parser.error('dualband requires positive station counts for both bands')
    if args.ap_wait < 0:
        parser.error('--ap_wait cannot be negative')
    return args


def run_command(command, label):
    print(f'\n=== {label} ===', flush=True)
    # Do not print command arguments: they contain Wi-Fi and possibly admin passwords.
    result = subprocess.run(command, cwd=str(SCRIPTS), check=False)
    if result.returncode != 0:
        raise RuntimeError(f'{label} failed (exit code {result.returncode})')


def main():
    args = parse_args()
    for path in (QOS_SCRIPT, AP_SCRIPT):
        if not path.is_file():
            raise FileNotFoundError(f'Missing script: {path}')

    if args.push_config:
        if not VRF_SCRIPT.is_file():
            raise FileNotFoundError(f'Missing VRF script: {VRF_SCRIPT}')
        ap_cmd = [str(VRF_SCRIPT), args.upstream, sys.executable, str(AP_SCRIPT),
                  '--action', 'wireless_config', '--ssid', args.ssid,
                  '--password', args.password, '--security', args.security,
                  '--2g_channel', str(getattr(args, '2g_channel')),
                  '--5g_channel', str(getattr(args, '5g_channel')),
                  '--gateway_ip', args.gateway_ip, '--login_user', args.login_user]
        if args.login_pw is not None:
            ap_cmd += ['--login_pw', args.login_pw]
        run_command(ap_cmd, 'NETGEAR AP configuration')
        if args.ap_wait:
            print(f'Waiting {args.ap_wait}s for AP to settle...', flush=True)
            time.sleep(args.ap_wait)

    qos_cmd = [sys.executable, str(QOS_SCRIPT), '--mgr', args.mgr,
               '--mgr_port', str(args.mgr_port), '--upstream', args.upstream,
               '--bands', args.bands, '--test_duration', args.test_duration,
               '--download', args.download, '--upload', args.upload,
               '--traffic_type', args.traffic_type, '--tos', args.tos,
               '--ap_name', args.ap_name]
    active_bands = ('2.4g', '5g') if args.bands == 'dualband' else (args.bands,)
    for band, suffix in [('2.4g', '2g'), ('5g', '5g')]:
        if band in active_bands:
            qos_cmd += [f'--ssid_{suffix}', args.ssid,
                        f'--passwd_{suffix}', args.password,
                        f'--security_{suffix}', args.security,
                        f'--radio_{suffix}', getattr(args, f'radio_{suffix}'),
                        f'--num_stations_{suffix}', str(getattr(args, f'num_stations_{suffix}'))]
    if not args.no_create_sta:
        qos_cmd.append('--create_sta')
    run_command(qos_cmd, 'LANforge QoS test')
    print('\nQOS Test successfully completed.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
