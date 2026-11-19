import logging
import os
import posixpath
import shlex
import stat
import uuid
import importlib
import time
import paramiko

logger = logging.getLogger(__name__)


def prepare_roaming_interfaces(args, manager, port=8080):
    """Use supplied monitors or create monitors from the radio/channel arguments."""
    interfaces = {name: getattr(args, name, None) for name in ('moni2g', 'moni5g', 'moni6g')}
    selected = []
    for band in ('2g', '5g', '6g'):
        radio = getattr(args, 'sniff_radio_' + band, None)
        channel = getattr(args, 'sniff_channel_' + band, None)
        if bool(radio) != (channel not in (None, '')):
            raise ValueError(f'Provide both radio and channel for {band}')
        if channel not in (None, '') and int(channel) <= 0:
            raise ValueError(f'Capture channel for {band} must be positive')
        if radio and not interfaces['moni' + band]:
            selected.append((band, radio, channel))
    if not selected:
        if not any(interfaces.values()):
            raise ValueError('Provide at least one monitor interface or radio/channel pair')
        return interfaces
    realm = importlib.import_module('py-json.realm').Realm(lfclient_host=manager, lfclient_port=port)
    for band, radio, channel in selected:
        radio_eid = realm.name_to_eid(radio)
        shelf, resource = radio_eid[:2]
        name = 'moni' + band
        profile = realm.new_wifi_monitor_profile()
        profile.create(channel=int(channel), radio_=radio, name_=name)
        for attempt in range(60):
            response = realm.json_get(f'/port/{shelf}/{resource}/{name}?fields=down,phantom,channel')
            interface = (response or {}).get('interface', {})
            if (interface and interface.get('down') is False and interface.get('phantom') is False
                    and str(interface.get('channel')) == str(channel)):
                break
            time.sleep(1)
        else:
            raise RuntimeError(f'Monitor {name} on {radio} did not become ready on channel {channel}')
        interfaces[name] = name
    return interfaces


class RoamingCapture:
    """Capture AP-to-AP movement, splitting segments when charging interrupts a run."""

    def __init__(self, host, output_path, interfaces, username='lanforge', password=None,
                 key_filename=None, remote_base='/home/lanforge', test_prefix='zoom-roaming'):
        self.sniffer = RemoteSniffer(host, username, password=password, key_filename=key_filename,
                                     test_name=test_prefix + '-' + uuid.uuid4().hex[:12])
        self.output_path = output_path
        self.interfaces = interfaces
        self.remote_base = remote_base
        self.remote_folder = None
        self.route = None
        self.count = 0
        self.current_path = None

    def start_segment(self, from_ap, to_ap):
        """Start a named capture for movement between two AP coordinates."""
        self.stop_segment()
        for coordinate in (from_ap, to_ap):
            if not coordinate or '/' in coordinate or '\\' in coordinate:
                raise ValueError('AP coordinates must be valid file-name components')
        self.route = (from_ap, to_ap)
        self.resume()

    def resume(self):
        """Resume the active route in a new capture file after charging."""
        if self.route is None or self.current_path is not None:
            return
        if self.sniffer.ssh_client is None:
            self.sniffer.connect()
            self.remote_folder = self.sniffer.create_remote_test_folder(self.remote_base)
        self.count += 1
        self.sniffer.pcap_name = f'{self.route[0]}-{self.route[1]}_{self.count}.pcap'
        self.current_path = self.sniffer.start_sniff_for_triband(self.remote_folder, **self.interfaces)

    def pause(self):
        """Stop the active segment on the capture host while retaining its route."""
        if self.current_path is None:
            return
        self.sniffer.stop_sniff()
        # Keep raw PCAPs on the capture host; download analysis results separately.
        # RemoteSniffer.fetch_pcap remains available for explicit downloads.
        self.current_path = None

    def stop_segment(self):
        """Finish the active route, leaving its capture on the capture host."""
        self.pause()
        self.route = None

    def close(self):
        """Finish capture and close the SSH connection."""
        self.stop_segment()
        self.sniffer.close()


class RemoteSniffer:
    """Capture traffic on existing remote monitor interfaces over SSH.

    Manage capture folders, start and stop tri-band tshark captures, and
    download completed PCAP files, and run and retrieve roaming analysis.
    """

    def __init__(self, hostname, username, password=None, key_filename=None,
                 pcap_name='capture.pcap', test_name='sample'):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.pcap_name = pcap_name
        self.testname = test_name
        self.ssh_client = None
        self.sftp = None
        self.remote_process_pid = None

    def connect(self):
        """Connect to the capture host using password or key authentication."""
        if self.ssh_client is not None:
            raise RuntimeError('Sniffer is already connected')
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(self.hostname, username=self.username,
                           password=self.password, key_filename=self.key_filename)
            self.sftp = client.open_sftp()
        except Exception:
            client.close()
            raise
        self.ssh_client = client

    def create_remote_test_folder(self, remote_base='/home/lanforge'):
        """Create the test folder beneath an existing remote base directory."""
        if self.sftp is None:
            raise RuntimeError('SSH connection not established')
        if not self.testname or self.testname in ('.', '..') or '/' in self.testname:
            raise ValueError('test_name must be a single folder name')
        remote_path = posixpath.join(remote_base, self.testname)
        try:
            self.sftp.stat(remote_path)
        except FileNotFoundError:
            self.sftp.mkdir(remote_path)
        return remote_path

    def start_sniff_for_triband(self, remote_dir, moni2g=None, moni5g=None, moni6g=None):
        """Start one tshark capture on the supplied monitor interfaces."""
        if self.ssh_client is None:
            raise RuntimeError('SSH connection not established')
        if self.remote_process_pid is not None:
            raise RuntimeError('Stop the current capture before starting another')
        interfaces = list(dict.fromkeys(i for i in (moni2g, moni5g, moni6g) if i))
        if not interfaces:
            raise ValueError('No monitor interfaces provided')
        if not self.pcap_name or self.pcap_name in ('.', '..') or '/' in self.pcap_name:
            raise ValueError('pcap_name must be a single file name')
        remote_path = posixpath.join(remote_dir, self.pcap_name)
        arguments = ['tshark']
        for interface in interfaces:
            arguments.extend(['-i', interface])
        arguments.extend(['-w', remote_path])
        command = 'nohup ' + ' '.join(shlex.quote(arg) for arg in arguments)
        _, stdout, stderr = self.ssh_client.exec_command(
            command + ' </dev/null >/dev/null 2>&1 & echo $!')
        pid = stdout.read().decode().strip()
        if not pid.isdigit() or int(pid) <= 0:
            raise RuntimeError('Failed to launch tshark: ' + stderr.read().decode())
        self.remote_process_pid = int(pid)
        return remote_path

    def stop_sniff(self):
        """Interrupt this capture, waiting for tshark to flush and exit."""
        if self.remote_process_pid is None:
            return
        pid = self.remote_process_pid
        command = (
            f'if kill -0 {pid} 2>/dev/null; then kill -2 {pid} || exit 1; fi; '
            f'for attempt in 1 2 3 4 5 6 7 8 9 10; do '
            f'kill -0 {pid} 2>/dev/null || exit 0; sleep 1; done; exit 1'
        )
        _, stdout, stderr = self.ssh_client.exec_command(command)
        if stdout.channel.recv_exit_status() != 0:
            raise RuntimeError('Capture did not stop: ' + stderr.read().decode())
        self.remote_process_pid = None

    def fetch_pcap(self, remote_path, local_path):
        """Download a completed capture to the supplied local file path."""
        if self.sftp is None:
            raise RuntimeError('SSH connection not established')
        if self.remote_process_pid is not None:
            raise RuntimeError('Stop the capture before downloading its PCAP')
        self.sftp.get(remote_path, local_path)
        return local_path

    def sftp_get_dir(self, remote_dir, local_dir):
        """Download a directory recursively, rejecting links and special files."""
        if self.sftp is None:
            raise RuntimeError('SSH connection not established')
        os.makedirs(local_dir, exist_ok=True)
        for entry in self.sftp.listdir_attr(remote_dir):
            name = entry.filename
            if name in ('.', '..') or '/' in name or '\\' in name:
                raise ValueError(f'Invalid remote entry name: {name!r}')
            remote_path = posixpath.join(remote_dir, name)
            local_path = os.path.join(local_dir, name)
            if os.path.islink(local_path):
                raise ValueError(f'Local destination is a symbolic link: {local_path}')
            if stat.S_ISDIR(entry.st_mode):
                self.sftp_get_dir(remote_path, local_path)
            elif stat.S_ISREG(entry.st_mode):
                self.sftp.get(remote_path, local_path)
            else:
                raise ValueError(f'Unsupported remote file type: {remote_path}')

    def _roaming_batch_names(self, remote_folder):
        """List roaming analysis output directories within a capture folder."""
        if self.sftp is None:
            raise RuntimeError('SSH connection not established')
        return sorted(entry.filename for entry in self.sftp.listdir_attr(remote_folder)
                      if entry.filename.startswith('pcap_batch') and stat.S_ISDIR(entry.st_mode))

    def fetch_combined_roaming_folder(self, remote_folder, local_folder=None, batch_name=None):
        """Download one analysis batch, including its CSVs and reports."""
        batches = self._roaming_batch_names(remote_folder)
        if batch_name is None:
            if len(batches) != 1:
                raise RuntimeError(f'Expected one analysis batch in {remote_folder}; found {batches}')
            batch_name = batches[0]
        if batch_name not in batches or '/' in batch_name or '\\' in batch_name:
            raise ValueError(f'Unknown analysis batch: {batch_name}')
        folder_name = posixpath.basename(remote_folder.rstrip('/'))
        if folder_name in ('', '.', '..'):
            raise ValueError('remote_folder must name a capture directory')
        destination = os.path.join(local_folder or '.', folder_name, batch_name)
        # A fresh destination prevents mixing results from separate analysis runs.
        os.makedirs(destination, exist_ok=False)
        self.sftp_get_dir(posixpath.join(remote_folder, batch_name), destination)
        return destination

    def run_command_and_fetch_folder(
            self, remote_folder, local_folder=None, mgmt_roam_time=500,
            data_roam_time=500, test_type='Zoom Call',
            analysis_script='roaming_development/wifi_roaming_cli.py',
            alias_file='roaming_development/ap_client_aliases.json',
            report_image='roaming_development/floor_plan.jpeg',
            workers=6, packets_per_chunk=15000, pcap_batch_workers=3):
        """Analyze completed captures remotely and download the new result batch.

        Remote paths may be absolute or relative to the SSH login directory.
        Thresholds are in milliseconds. Return the downloaded batch directory;
        raise an error if analysis fails or produces no unambiguous new batch.
        """
        if self.ssh_client is None or self.sftp is None:
            raise RuntimeError('SSH connection not established')
        if self.remote_process_pid is not None:
            raise RuntimeError('Stop the capture before running roaming analysis')
        for name, value in (('mgmt_roam_time', mgmt_roam_time), ('data_roam_time', data_roam_time),
                            ('workers', workers), ('packets_per_chunk', packets_per_chunk),
                            ('pcap_batch_workers', pcap_batch_workers)):
            if name == 'data_roam_time' and test_type == 'no_data':
                continue
            minimum = 0 if name.endswith('roam_time') else 1
            if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
                raise ValueError(f'{name} must be an integer >= {minimum}')
        before = set(self._roaming_batch_names(remote_folder))
        arguments = ['python3', analysis_script, '--mode', 'parallel', '--pcap-dir', remote_folder,
                     '--alias-file', alias_file, '--workers', str(workers),
                     '--packets-per-chunk', str(packets_per_chunk),
                     '--pcap-batch-workers', str(pcap_batch_workers), '--traffic-test', test_type,
                     '--auth-pass-ms', str(mgmt_roam_time)]
        if test_type != 'no_data':
            arguments.extend(['--gap-pass-ms', str(data_roam_time)])
        if report_image:
            arguments.extend(['--report-image', report_image])
        command = ' '.join(shlex.quote(arg) for arg in arguments)
        # Drain both output streams together so verbose analysis cannot block on stderr.
        stdin, stdout, stderr = self.ssh_client.exec_command(command + ' 2>&1')
        stdin.close()
        try:
            for line in stdout:
                logger.info('Roaming analysis: %s', line.rstrip())
            status = stdout.channel.recv_exit_status()
        finally:
            stdout.close()
            stderr.close()
        if status != 0:
            raise RuntimeError(f'Remote roaming analysis failed with exit status {status}; see analysis logs')
        new_batches = set(self._roaming_batch_names(remote_folder)) - before
        if len(new_batches) != 1:
            raise RuntimeError(f'Expected one new analysis batch; found {sorted(new_batches)}')
        return self.fetch_combined_roaming_folder(remote_folder, local_folder, new_batches.pop())

    def close(self):
        """Stop any active capture before closing the connection."""
        self.stop_sniff()
        try:
            if self.sftp is not None:
                self.sftp.close()
        finally:
            if self.ssh_client is not None:
                self.ssh_client.close()
            self.sftp = None
            self.ssh_client = None
