import pyshark
import csv
import json
import os
import shutil

class RoamAnalyzer:

    def __init__(self, pcap_file, clients, ap_bssids, tshark_path="/usr/bin/tshark"):
        self.pcap_file = pcap_file
        self.clients = clients
        self.ap_bssids = set([b.lower() for b in ap_bssids])
        self.tshark_path = tshark_path
        self.client_names = {name: [] for name in clients}

    def analyze(self):
        for name, mac in self.clients.items():
            print(f"\nProcessing {name}: {mac}")
            self._process_client(name, mac)

        # self._write_csv()

    def _process_client(self, name, mac):

        cap = pyshark.FileCapture(
            self.pcap_file,
            display_filter=f"wlan.addr == {mac} && (wlan.fc.type_subtype == 0 or  wlan.fc.type_subtype ==1 or  wlan.fc.type_subtype ==2 or  wlan.fc.type_subtype ==3 or  wlan.fc.type_subtype == 11 or wlan.fc.type_subtype == 10 or eapol)",
            tshark_path=self.tshark_path
        )

        state = None
        start_time = None
        start_tsf = None
        last_bssid = None
        from_bssid = None
        to_bssid = None
        auth_seen = False

        for pkt in cap:
            try:
                # for management frame
                if not hasattr(pkt, 'wlan'):
                    continue
                # 
                ts = float(pkt.sniff_timestamp)

                tsf = None
                if hasattr(pkt, 'wlan_radio') and hasattr(pkt.wlan_radio, 'timestamp'):
                    try:
                        tsf = int(pkt.wlan_radio.timestamp)
                    except:
                        tsf = None

                if hasattr(pkt.wlan, 'bssid'):
                    current_bssid = pkt.wlan.bssid.lower()
                else:
                    continue

                if last_bssid is None:
                    last_bssid = current_bssid

                # to check if it is valid roam, to check whther it is in current ap list 
                is_valid_roam = (
                    current_bssid in self.ap_bssids and
                    (
                        last_bssid not in self.ap_bssids or
                        last_bssid != current_bssid
                    )
                )

                if hasattr(pkt.wlan, 'fc_type_subtype'):
                    subtype = pkt.wlan.fc_type_subtype
                    #  to check if it is auth request
                    if subtype == '0x000b' and is_valid_roam:

                        from_bssid = last_bssid
                        to_bssid = current_bssid

                        # print(f"\n{name} ROAM (AUTH)")
                        # print(f"{from_bssid} → {to_bssid}")

                        if state is None:
                            state = "STARTED"
                            start_time = ts
                            start_tsf = tsf
                            auth_seen = True
                            # print(f"{name} AUTH START at {ts}")
                    # to check if it is ressoc request
                    elif subtype == '0x0002' and is_valid_roam:

                        from_bssid = last_bssid
                        to_bssid = current_bssid

                        # print(f"\n{name} ROAM (REASSOC)")
                        # print(f"{from_bssid} → {to_bssid}")

                        if state is None and not auth_seen:
                            state = "STARTED"
                            start_time = ts
                            start_tsf = tsf
                            # print(f"{name} REASSOC START at {ts}")

                # to get the eapol message whether it is 4
                if (
                    hasattr(pkt, 'eapol') and
                    hasattr(pkt.eapol, 'wlan_rsna_keydes_msgnr') and
                    str(pkt.eapol.wlan_rsna_keydes_msgnr) == '4' and
                    state == "STARTED" and
                    current_bssid in self.ap_bssids   
                ):

                    # print(f"{name} END at {ts}")

                    roam_time = ts - start_time

                    roam_time_tsf_us = None
                    roam_time_tsf_ms = None

                    if start_tsf and tsf:
                        roam_time_tsf_us = tsf - start_tsf
                        roam_time_tsf_ms = roam_time_tsf_us / 1000
                    #  appending data results dict
                    self.client_names[name].append({
                        "from_bssid": from_bssid,
                        "to_bssid": to_bssid,
                        "start_time": start_time,
                        "end_time": ts,
                        "roam_time_sec": roam_time,
                        # "start_tsf": start_tsf,
                        # "end_tsf": tsf,
                        # "roam_time_tsf_us": roam_time_tsf_us,
                        # "roam_time_tsf_ms": roam_time_tsf_ms,
                        # "start_type": "auth" if auth_seen else "reassoc"
                    })
                    #  setting the these times to be none to capture new roam times.
                    state = None
                    start_time = None
                    start_tsf = None
                    auth_seen = False

                # Always update last BSSID
                last_bssid = current_bssid

            except Exception as e:
                print("Error:", e)

        cap.close()



    def _write_csv(self, path=""):

        # If path is provided, create subfolder
        if path:
            output_dir = os.path.join(path, "client_roaming_csvs")
        else:
            output_dir = "client_roaming_csvs"

        os.makedirs(output_dir, exist_ok=True)
        print(self.client_names)
        for name in self.client_names:
            filename = os.path.join(output_dir, f"{name}_roam_times.csv")

            with open(filename, "w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "from_bssid",
                        "to_bssid",
                        "start_time",
                        "end_time",
                        "roam_time_sec",
                    ]
                )

                writer.writeheader()
                writer.writerows(self.client_names[name])

            print(f"Saved {filename}")


    def save_pcap_to_dir(self, pcap_path, path):

        filename = os.path.basename(pcap_path)

        dest_path = os.path.join(path, filename)

        shutil.copy2(pcap_path, dest_path)

        print(f"PCAP saved to {dest_path}")

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    CONFIG_PATH = os.path.join(BASE_DIR, "../..", "candela_roaming_client_ap.json")
    CONFIG_PATH = os.path.abspath(CONFIG_PATH)
    PCAP_PATH = os.path.join(BASE_DIR,"../..", "10_iterations_5devices_2.pcap")
    print(PCAP_PATH)

    def load_config(path):
        with open(path, "r") as f:
            return json.load(f)
            
    config = load_config(CONFIG_PATH)

    clients = config["clients"]
    ap_bssids = config["ap_bssids"]

    analyzer = RoamAnalyzer(
        pcap_file=PCAP_PATH,
        clients=clients,
        ap_bssids=ap_bssids
    )

    analyzer.analyze()
    analyzer._write_csv(path = "/home/lanforge/local/interop-webGUI/results/dukwdh")
    analyzer.save_pcap_to_dir(PCAP_PATH, "/home/lanforge/local/interop-webGUI/results/ping123")