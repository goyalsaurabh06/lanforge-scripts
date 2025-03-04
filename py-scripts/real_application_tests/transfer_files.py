import paramiko
import os
import csv
import argparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class TransferFiles:
    def __init__(self) -> None:
        self.successful_hosts = []
        self.failed_hosts = {}

    def ssh_and_transfer_files(self, ip_address, username, password, os_type, device_status):
        if device_status == 0:
            logging.info(f"Skipping file transfer to {ip_address} (status: {device_status})")
            return

        client = None
        try:
            # Initialize SSH client
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname=ip_address, username=username, password=password)

            # Set remote directory based on OS type
            if os_type.lower() == 'windows':
                remote_dir = r'C:\\Program Files (x86)\\LANforge-Server'
                files_to_transfer = ['./zoom_automation/zoom_client.py',
                                     './zoom_automation/zoom_host.py',
                                     './zoom_automation/install_dependencies.py',
                                     './real_browser/real_browser.py',
                                     './real_browser/real_browser.bat',
                                     './youtube/youtube_stream.bat',
                                     './youtube/youtube.py']
            elif os_type.lower() == 'linux':
                remote_dir = '/home/lanforge'
                files_to_transfer = ['./zoom_automation/zoom_client.py',
                                     './zoom_automation/zoom_host.py',
                                     './zoom_automation/ctzoom.bash',
                                     './zoom_automation/install_dependencies.py',
                                     './youtube/ctyt.bash',
                                     './youtube/youtube.py',
                                     './real_browser/real_browser.py',
                                     './real_browser/ctrb.bash'
                                     ]
            elif os_type.lower() == 'mac':
                remote_dir = '/Users/lanforge'
                files_to_transfer = ['./zoom_automation/zoom_client.py',
                                     './zoom_automation/zoom_host.py',
                                     './zoom_automation/ctzoom.bash',
                                     './zoom_automation/install_dependencies.py',
                                     './youtube/ctyt.bash',
                                     './youtube/youtube.py',
                                     './real_browser/real_browser.py',
                                     './real_browser/ctrb.bash'
                                     ]
            else:
                error_msg = f"Unsupported OS type: {os_type}"
                logging.error(error_msg)
                self.failed_hosts[ip_address] = error_msg
                return

            # Start SFTP for file transfer
            sftp = client.open_sftp()

            # Transfer the relevant files
            for file in files_to_transfer:
                local_path = os.path.join(os.path.dirname(__file__), file)
                remote_path = os.path.join(remote_dir, os.path.basename(file))
                logging.info(f"Transferring {local_path} to {remote_path}")

                # Transfer the file via SFTP
                try:
                    sftp.put(local_path, remote_path)
                    logging.info(f"  - Successfully transferred '{file}' to {ip_address}:{remote_path}")
                except Exception as file_transfer_error:
                    error_msg = f"Failed to transfer {file} to {ip_address}: {file_transfer_error}"
                    logging.error(error_msg)
                    self.failed_hosts[ip_address] = error_msg
                    break

            self.successful_hosts.append(ip_address)
            sftp.close()

        except Exception as e:
            error_msg = f"Error while transferring files to {ip_address}: {e}"
            logging.error(error_msg)
            self.failed_hosts[ip_address] = error_msg

        finally:
            if client:
                client.close()

    def read_data_from_csv(self, csv_file):
        with open(csv_file, mode='r') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                ip_address = row['ip_address'].strip()
                username = row['username'].strip()
                password = row['password'].strip()
                os_type = row['os_type'].strip()
                device_status = int(row['device_status'])

                self.ssh_and_transfer_files(ip_address, username, password, os_type, device_status)

    def print_transfer_results(self):
        logging.info("\nTransfer Summary:")

        if self.successful_hosts:
            logging.info("\nSuccessful Transfers:")
            for host in self.successful_hosts:
                logging.info(f"  - {host}")
        else:
            logging.info("\nNo successful transfers.")

        if self.failed_hosts:
            logging.error("\nFailed Transfers:")
            for host, reason in self.failed_hosts.items():
                logging.error(f"  - {host}: {reason}")
        else:
            logging.info("\nNo failed transfers.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', type=str, help='CSV file containing device details', required=True)
    args = parser.parse_args()

    transferfiles = TransferFiles()
    transferfiles.read_data_from_csv(args.csv)
    transferfiles.print_transfer_results()


if __name__ == "__main__":
    main()
