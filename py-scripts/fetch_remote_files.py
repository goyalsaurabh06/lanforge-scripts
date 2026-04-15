
# Import your RemoteSniffer class
from candela_base_class import RemoteSniffer

def test_fetch_combined_roaming_zip():
    # Fill in your SSH details and remote folder
    hostname = "10.17.1.43"
    username = "lanforge"
    password = "lanforge"
    remote_folder = "/home/lanforge/2026-04-13_09-50-33_sample_test/"  # e.g., "/home/lanforge/results"
    local_folder = "./2026-04-13_09-50-33_sample_test/"

    sniffer = RemoteSniffer(hostname, username, password=password)
    sniffer.connect()
    try:
        print("Testing fetch_combined_roaming_zip...")
        zip_path = sniffer.fetch_combined_roaming_zip(remote_folder, local_folder)
        print(f"Downloaded zip to: {zip_path}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sniffer.close()

def test_run_command_and_fetch_folder():
    # Fill in your SSH details and remote folder
    hostname = "10.17.1.43"
    username = "lanforge"
    password = "lanforge"
    remote_folder = "2026-04-15_16-09-37_rt5361"  # e.g., "/home/lanforge/results"
    local_folder = ""

    sniffer = RemoteSniffer(hostname, username, password=password)
    sniffer.connect()
    try:
        print("Testing run_command_and_fetch_folder...")
        sniffer.run_command_and_fetch_folder(remote_folder, local_folder)
        print("Completed run_command_and_fetch_folder.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        sniffer.close()

if __name__ == "__main__":
    # Uncomment the test you want to run
    # test_fetch_combined_roaming_zip()
    test_run_command_and_fetch_folder()