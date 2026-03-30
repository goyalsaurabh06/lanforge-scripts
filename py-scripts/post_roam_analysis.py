import pyshark
import csv
import json
import os
import shutil
from datetime import datetime
class RoamAnalyzer:

    def __init__(self, pcap_file, clients, ap_bssids, tshark_path="/usr/bin/tshark"):
        self.pcap_file = pcap_file
        self.clients = clients
        self.ap_bssids = set([b.lower() for b in ap_bssids])
        self.tshark_path = tshark_path
        self.client_names = {name: [] for name in clients}

        # ✅ store disconnect events (deauth + disassoc)
        self.disconnect_events = {name: [] for name in clients}

    def analyze(self):
        for name, mac in self.clients.items():
            print(f"\nProcessing {name}: {mac}")
            self._process_client(name, mac)

    def _process_client(self, name, mac):

        cap = pyshark.FileCapture(
            self.pcap_file,
            display_filter=f"wlan.addr == {mac} && (wlan.fc.type_subtype == 0 or wlan.fc.type_subtype == 1 or wlan.fc.type_subtype == 2 or wlan.fc.type_subtype == 3 or wlan.fc.type_subtype == 11 or wlan.fc.type_subtype == 10 or wlan.fc.type_subtype == 12 or wlan.fc.type_subtype == 10 or eapol)",
            tshark_path=self.tshark_path
        )

        state = None
        start_time = None
        start_tsf = None
        last_bssid = None
        from_bssid = None
        to_bssid = None
        auth_seen = False

        roam_count = 1

        for pkt in cap:
            try:
                if not hasattr(pkt, 'wlan'):
                    continue

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

                is_valid_roam = (
                    current_bssid in self.ap_bssids and
                    (
                        last_bssid not in self.ap_bssids or
                        last_bssid != current_bssid
                    )
                )

                if hasattr(pkt.wlan, 'fc_type_subtype'):
                    subtype = pkt.wlan.fc_type_subtype

                    # ✅ DEAUTH
                    if subtype == '0x000c':
                        self.disconnect_events[name].append({
                            "event_type": "deauth",
                            "bssid": current_bssid,
                            "timestamp": ts
                        })

                    # ✅ DISASSOC
                    elif subtype == '0x000a':
                        self.disconnect_events[name].append({
                            "event_type": "disassoc",
                            "bssid": current_bssid,
                            "timestamp": ts
                        })

                    # AUTH
                    if subtype == '0x000b' and is_valid_roam:
                        from_bssid = last_bssid
                        to_bssid = current_bssid

                        if state is None:
                            state = "STARTED"
                            start_time = ts
                            start_tsf = tsf
                            auth_seen = True

                    # REASSOC
                    elif subtype == '0x0002' and is_valid_roam:
                        from_bssid = last_bssid
                        to_bssid = current_bssid

                        if state is None and not auth_seen:
                            state = "STARTED"
                            start_time = ts
                            start_tsf = tsf

                # EAPOL message 4 → roam end
                if (
                    hasattr(pkt, 'eapol') and
                    hasattr(pkt.eapol, 'wlan_rsna_keydes_msgnr') and
                    str(pkt.eapol.wlan_rsna_keydes_msgnr) == '4' and
                    state == "STARTED" and
                    current_bssid in self.ap_bssids
                ):
                    dest_addr = None
                    if hasattr(pkt.wlan, 'da'):
                        dest_addr = pkt.wlan.da.lower()
                    roam_time = ts - start_time
                    start_time_hr = datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S.%f')
                    end_time_hr = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S.%f')
                    self.client_names[name].append({
                        "roam_no": roam_count,
                        "from_bssid": from_bssid,
                        "to_bssid": to_bssid,
                        "start_time": start_time_hr,
                        "end_time": end_time_hr,
                        "roam_time_sec": roam_time,
                        "MLD bssid": dest_addr if dest_addr not in self.ap_bssids else "",
                    })

                    roam_count += 1

                    state = None
                    start_time = None
                    start_tsf = None
                    auth_seen = False

                last_bssid = current_bssid

            except Exception as e:
                print("Error:", e)

        cap.close()

    def _write_csv(self, path=""):

        if path:
            output_dir = os.path.join(path, "client_roaming_csvs")
        else:
            output_dir = "client_roaming_csvs"

        os.makedirs(output_dir, exist_ok=True)

        for name in self.client_names:
            filename = os.path.join(output_dir, f"{name}_roam_times.csv")

            with open(filename, "w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "roam_no",
                        "from_bssid",
                        "to_bssid",
                        "start_time",
                        "end_time",
                        "roam_time_sec",
                        "MLD bssid"
                    ]
                )

                writer.writeheader()
                writer.writerows(self.client_names[name])

            print(f"Saved {filename}")

    # ✅ Combined disconnect CSV (deauth + disassoc)
    def _write_disconnect_csv(self, path=""):

        if path:
            output_dir = os.path.join(path, "client_roaming_csvs")
        else:
            output_dir = "client_roaming_csvs"

        os.makedirs(output_dir, exist_ok=True)

        filename = os.path.join(output_dir, "all_clients_disconnect.csv")

        with open(filename, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "client_name",
                    "event_type",
                    "bssid",
                    "timestamp"
                ]
            )

            writer.writeheader()

            all_events = []
            for name in self.disconnect_events:
                for event in self.disconnect_events[name]:
                    all_events.append({
                        "client_name": name,
                        "event_type": event["event_type"],
                        "bssid": event["bssid"],
                        "timestamp": event["timestamp"]
                    })

            all_events.sort(key=lambda x: x["timestamp"])

            writer.writerows(all_events)

        print(f"Saved {filename}")


if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    CONFIG_PATH = os.path.join(BASE_DIR, "../..", "candela_roaming_client_ap.json")
    CONFIG_PATH = os.path.abspath(CONFIG_PATH)
    # PCAP_PATH = os.path.join(BASE_DIR, "Day2_trail1_issue.pcapng")
    PCAP_PATH = os.path.join(BASE_DIR, "10_iterations_5devices_2.pcap")

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
    analyzer._write_csv()
    analyzer._write_disconnect_csv()