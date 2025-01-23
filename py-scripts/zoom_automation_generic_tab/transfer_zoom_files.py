import paramiko
import os
import csv
import argparse
from scp import SCPClient

class TransferFiles:
    def __init__(self) -> None:
        self.successful_hosts = []
        self.failed_hosts = []

    def ssh_and_transfer_files(self, ip_address, username, password, os_type, device_status):

        if device_status == 0:
            print(f"Skipping file transfer to {ip_address} (status: {device_status})")
            return
        client = None
        try:
            # Initialize SSH client
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(hostname=ip_address, username=username, password=password)

            # Set remote directory based on OS type
            if os_type.lower() == 'windows':
                remote_dir = r'C:\Program Files (x86)\LANforge-Server'
                files_to_transfer = ['zoom_client.py', 'zoom_host.py', 'install_dependencies.py']
            elif os_type.lower() == 'linux':
                remote_dir = '/home/lanforge'
                files_to_transfer = ['zoom_client.py', 'zoom_host.py', 'ctzoom.bash', 'install_dependencies.py']
            elif os_type.lower() == 'mac':
                remote_dir = '/Users/lanforge'
                files_to_transfer = ['zoom_client.py', 'zoom_host.py', 'ctzoom.bash', 'install_dependencies.py']
            else:
                print(f"Unsupported OS type: {os_type}")
                self.failed_hosts.append(ip_address)
                return

            # Start SFTP for file transfer
            sftp = client.open_sftp()

            # Transfer the relevant files
            for file in files_to_transfer:
                local_path = os.path.join(os.path.dirname(__file__), file)
                remote_path = os.path.join(remote_dir, file)
                print(f"Transferring {local_path} to {remote_path}")

                # Transfer the file via SFTP
                with open(local_path, 'rb') as f:
                    sftp.put(local_path, remote_path)
                    print(f"  - Successfully transferred '{file}' to {ip_address}:{remote_path}")

            self.successful_hosts.append(ip_address)

            # Close the SFTP connection
            sftp.close()

        except Exception as e:
            print(f"Error while Transferring files to {ip_address}: {e}")
            self.failed_hosts.append(ip_address)

        finally:
            if client:
                client.close()

    # Function to read from CSV and call ssh_and_transfer_files for each row
    def read_data_from_csv(self, csv_file):
        with open(csv_file, mode='r') as file:
            csv_reader = csv.DictReader(file)

            for row in csv_reader:
                ip_address = row['ip_address'].strip()
                username = row['username'].strip()
                password = row['password'].strip()
                os_type = row['os_type'].strip()
                device_status = int(row['device_status'])

                # Call method to transfer files
                self.ssh_and_transfer_files(ip_address, username, password, os_type, device_status)

    def print_transfer_results(self):
        print("\nTransfer Results:")
        print("Successful transfers:")
        for host in self.successful_hosts:
            print(f"  - {host}")

        print("\nFailed transfers:")
        for host in self.failed_hosts:
            print(f"  - {host}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--csv', type=str, help='csv_file', required=True)
    transferfiles = TransferFiles()
    args = parser.parse_args()
    csv_file = args.csv
    transferfiles.read_data_from_csv(csv_file)

    transferfiles.print_transfer_results()

if __name__ == "__main__":
    main()
