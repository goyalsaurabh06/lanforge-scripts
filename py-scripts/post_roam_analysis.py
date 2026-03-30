import pyshark
import csv
import json
import os
import shutil
from datetime import datetime
import glob
import importlib
import pandas as pd

lf_report = importlib.import_module("lf_report")
lf_report = lf_report.lf_report
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
            display_filter=f"wlan.addr == {mac} && (wlan.fc.type_subtype == 0 or wlan.fc.type_subtype == 1 or wlan.fc.type_subtype == 2 or wlan.fc.type_subtype == 3 or wlan.fc.type_subtype == 11 or wlan.fc.type_subtype == 10 or wlan.fc.type_subtype == 12 or eapol)",
            tshark_path=self.tshark_path
        )

        state = None
        start_time = None
        start_tsf = None
        last_bssid = None
        from_bssid = None
        to_bssid = None
        auth_seen = False
        threshold_time_sec = 0.15
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

                if hasattr(pkt.wlan, 'fc_type_subtype'):
                    subtype = pkt.wlan.fc_type_subtype
                    present_bssid = ""
                    if hasattr(pkt.wlan, 'bssid'):
                        present_bssid = pkt.wlan.bssid.lower()
                    else:
                        continue
                    # ✅ DEAUTH
                    if subtype == '0x000c':
                        self.disconnect_events[name].append({
                            "event_type": "deauth",
                            "bssid": present_bssid,
                            "timestamp": ts
                        })
                        continue

                    # ✅ DISASSOC
                    elif subtype == '0x000a':
                        self.disconnect_events[name].append({
                            "event_type": "disassoc",
                            "bssid": present_bssid,
                            "timestamp": ts
                        })
                        continue
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

                    # # ✅ DEAUTH
                    # if subtype == '0x000c':
                    #     self.disconnect_events[name].append({
                    #         "event_type": "deauth",
                    #         "bssid": current_bssid,
                    #         "timestamp": ts
                    #     })

                    # # ✅ DISASSOC
                    # elif subtype == '0x000a':
                    #     self.disconnect_events[name].append({
                    #         "event_type": "disassoc",
                    #         "bssid": current_bssid,
                    #         "timestamp": ts
                    #     })

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
                        "MLD Address": dest_addr if dest_addr not in self.ap_bssids else "-",
                        "to_bssid": to_bssid,
                        "start_time": start_time_hr,
                        "end_time": end_time_hr,
                        "roam_time_sec": roam_time,
                        "Status": "PASS" if roam_time <= threshold_time_sec else "FAIL"
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
                        "MLD Address",
                        "start_time",
                        "end_time",
                        "roam_time_sec",
                        "Status"
                    ]
                )

                writer.writeheader()
                writer.writerows(self.client_names[name])

            print(f"Saved {filename}")
    

    def generate_report_from_csv(self, path=""):
        if path:
            csv_dir = os.path.join(path, "client_roaming_csvs")
            report_base_path = path
        else:
            csv_dir = "client_roaming_csvs"
            report_base_path = os.getcwd()

        if not os.path.isdir(csv_dir):
            print(f"CSV directory not found: {csv_dir}")
            return None

        report = lf_report(
            _output_pdf="roaming_analysis_report.pdf",
            _output_html="roaming_analysis_report.html",
            _results_dir_name="roaming_analysis_report",
            _path=report_base_path
        )
        report_path_date_time = report.get_path_date_time()

        report.set_title("Wi-Fi Roaming Analysis Report")
        report.build_banner()

        report.set_table_title("Objective:")
        report.build_table_title()
        report.set_text(
            "The objective is to analyze roaming performance per client from generated roam CSV files, "
            "including roam duration, PASS/FAIL counts, and disconnect events."
        )
        report.build_text_simple()

        report.set_table_title("Test Parameters:")
        report.build_table_title()
        test_parameters = pd.DataFrame(
            [{
                "PCAP File": self.pcap_file,
                "No of Clients": len(self.clients),
                "Configured AP BSSIDs": len(self.ap_bssids),
                "Roam PASS Threshold (sec)": 0.15
            }]
        )
        report.set_table_dataframe(test_parameters)
        report.build_table()

        roam_csv_files = sorted(glob.glob(os.path.join(csv_dir, "*_roam_times.csv")))
        summary_rows = []
        client_dfs = []

        for csv_file in roam_csv_files:
            try:
                client_name = os.path.basename(csv_file).replace("_roam_times.csv", "")
                df = pd.read_csv(csv_file)

                if df.empty:
                    summary_rows.append(
                        {
                            "Client": client_name,
                            "Total Roams": 0,
                            "PASS": 0,
                            "FAIL": 0,
                            "Avg Roam Time (sec)": 0.0,
                            "Max Roam Time (sec)": 0.0,
                            "Min Roam Time (sec)": 0.0
                        }
                    )
                    client_dfs.append((client_name, df))
                    shutil.copy2(csv_file, os.path.join(report_path_date_time, os.path.basename(csv_file)))
                    continue

                df["roam_time_sec"] = pd.to_numeric(df["roam_time_sec"], errors="coerce")
                pass_count = int((df["Status"] == "PASS").sum()) if "Status" in df.columns else 0
                fail_count = int((df["Status"] == "FAIL").sum()) if "Status" in df.columns else 0

                summary_rows.append(
                    {
                        "Client": client_name,
                        "Total Roams": int(len(df)),
                        "PASS": pass_count,
                        "FAIL": fail_count,
                        "Avg Roam Time (sec)": round(float(df["roam_time_sec"].mean()), 6),
                        "Max Roam Time (sec)": round(float(df["roam_time_sec"].max()), 6),
                        "Min Roam Time (sec)": round(float(df["roam_time_sec"].min()), 6)
                    }
                )
                client_dfs.append((client_name, df))
                shutil.copy2(csv_file, os.path.join(report_path_date_time, os.path.basename(csv_file)))
            except Exception as e:
                print(f"Skipping CSV {csv_file}, reason: {e}")

        report.set_table_title("Roam Summary:")
        report.build_table_title()
        if summary_rows:
            summary_df = pd.DataFrame(summary_rows)
            report.set_table_dataframe(summary_df)
            report.build_table()
        else:
            report.set_obj_html(
                _obj_title="Roam Summary",
                _obj="No per-client roam CSV files were found."
            )
            report.build_objective()

        for client_name, df in client_dfs:
            report.set_obj_html(
                _obj_title=f"Client Roam Events: {client_name}",
                _obj="Detailed per-roam entries for this client."
            )
            report.build_objective()
            report.set_table_dataframe(df)
            report.build_table()

        disconnect_csv = os.path.join(csv_dir, "all_clients_disconnect.csv")
        if os.path.isfile(disconnect_csv):
            try:
                disconnect_df = pd.read_csv(disconnect_csv)
                if not disconnect_df.empty and "timestamp" in disconnect_df.columns:
                    disconnect_df["timestamp"] = pd.to_datetime(
                        disconnect_df["timestamp"], unit="s", errors="coerce"
                    ).astype(str)

                report.set_obj_html(
                    _obj_title="Disconnect Events (Deauth + Disassoc)",
                    _obj="Combined disconnect timeline for all clients."
                )
                report.build_objective()
                report.set_table_dataframe(disconnect_df)
                report.build_table()

                shutil.copy2(disconnect_csv, os.path.join(report_path_date_time, os.path.basename(disconnect_csv)))
            except Exception as e:
                report.set_obj_html(
                    _obj_title="Disconnect Events (Deauth + Disassoc)",
                    _obj=f"Disconnect CSV exists but could not be parsed: {e}"
                )
                report.build_objective()

        report.build_footer()
        report.write_html()
        try:
            report.write_pdf(_page_size="A4", _orientation="Portrait")
        except Exception as e:
            print(f"PDF generation skipped/failed: {e}")

        print(f"Report generated at: {report_path_date_time}")
        return report_path_date_time


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

    def save_pcap_to_dir(self, pcap_path, path):

        filename = os.path.basename(pcap_path)

        dest_path = os.path.join(path, filename)

        shutil.copy2(pcap_path, dest_path)

        print(f"PCAP saved to {dest_path}")

if __name__ == "__main__":
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    CONFIG_PATH = os.path.join(BASE_DIR, "../..", "candela_roaming_client_ap.json")
    CONFIG_PATH = os.path.abspath(CONFIG_PATH)
    # PCAP_PATH = os.path.join(BASE_DIR, "Day2_trail1_issue.pcapng")
    # PCAP_PATH = os.path.join(BASE_DIR, "../../","local/interop-webGUI/results/roaming_with_ocean_view/roaming.pcap")
    PCAP_PATH = os.path.join(os.getcwd(), "roaming.pcap")

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
    # analyzer.generate_report_from_csv()











































# import pyshark
# import csv
# import json
# import os
# import shutil

# class RoamAnalyzer:

#     def __init__(self, pcap_file, clients, ap_bssids, tshark_path="/usr/bin/tshark"):
#         self.pcap_file = pcap_file
#         self.clients = clients
#         self.ap_bssids = set([b.lower() for b in ap_bssids])
#         self.tshark_path = tshark_path
#         self.client_names = {name: [] for name in clients}

#     def analyze(self):
#         for name, mac in self.clients.items():
#             print(f"\nProcessing {name}: {mac}")
#             self._process_client(name, mac)

#         # self._write_csv()

#     def _process_client(self, name, mac):

#         cap = pyshark.FileCapture(
#             self.pcap_file,
#             display_filter=f"wlan.addr == {mac} && (wlan.fc.type_subtype == 0 or  wlan.fc.type_subtype ==1 or  wlan.fc.type_subtype ==2 or  wlan.fc.type_subtype ==3 or  wlan.fc.type_subtype == 11 or wlan.fc.type_subtype == 10 or eapol)",
#             tshark_path=self.tshark_path
#         )

#         state = None
#         start_time = None
#         start_tsf = None
#         last_bssid = None
#         from_bssid = None
#         to_bssid = None
#         auth_seen = False

#         for pkt in cap:
#             try:
#                 # for management frame
#                 if not hasattr(pkt, 'wlan'):
#                     continue
#                 # 
#                 ts = float(pkt.sniff_timestamp)

#                 tsf = None
#                 if hasattr(pkt, 'wlan_radio') and hasattr(pkt.wlan_radio, 'timestamp'):
#                     try:
#                         tsf = int(pkt.wlan_radio.timestamp)
#                     except:
#                         tsf = None

#                 if hasattr(pkt.wlan, 'bssid'):
#                     current_bssid = pkt.wlan.bssid.lower()
#                 else:
#                     continue

#                 if last_bssid is None:
#                     last_bssid = current_bssid

#                 # to check if it is valid roam, to check whther it is in current ap list 
#                 is_valid_roam = (
#                     current_bssid in self.ap_bssids and
#                     (
#                         last_bssid not in self.ap_bssids or
#                         last_bssid != current_bssid
#                     )
#                 )

#                 if hasattr(pkt.wlan, 'fc_type_subtype'):
#                     subtype = pkt.wlan.fc_type_subtype
#                     #  to check if it is auth request
#                     if subtype == '0x000b' and is_valid_roam:

#                         from_bssid = last_bssid
#                         to_bssid = current_bssid

#                         # print(f"\n{name} ROAM (AUTH)")
#                         # print(f"{from_bssid} → {to_bssid}")

#                         if state is None:
#                             state = "STARTED"
#                             start_time = ts
#                             start_tsf = tsf
#                             auth_seen = True
#                             # print(f"{name} AUTH START at {ts}")
#                     # to check if it is ressoc request
#                     elif subtype == '0x0002' and is_valid_roam:

#                         from_bssid = last_bssid
#                         to_bssid = current_bssid

#                         # print(f"\n{name} ROAM (REASSOC)")
#                         # print(f"{from_bssid} → {to_bssid}")

#                         if state is None and not auth_seen:
#                             state = "STARTED"
#                             start_time = ts
#                             start_tsf = tsf
#                             # print(f"{name} REASSOC START at {ts}")

#                 # to get the eapol message whether it is 4
#                 if (
#                     hasattr(pkt, 'eapol') and
#                     hasattr(pkt.eapol, 'wlan_rsna_keydes_msgnr') and
#                     str(pkt.eapol.wlan_rsna_keydes_msgnr) == '4' and
#                     state == "STARTED" and
#                     current_bssid in self.ap_bssids   
#                 ):

#                     # print(f"{name} END at {ts}")

#                     roam_time = ts - start_time

#                     roam_time_tsf_us = None
#                     roam_time_tsf_ms = None

#                     if start_tsf and tsf:
#                         roam_time_tsf_us = tsf - start_tsf
#                         roam_time_tsf_ms = roam_time_tsf_us / 1000
#                     #  appending data results dict
#                     self.client_names[name].append({
#                         "from_bssid": from_bssid,
#                         "to_bssid": to_bssid,
#                         "start_time": start_time,
#                         "end_time": ts,
#                         "roam_time_sec": roam_time,
#                         # "start_tsf": start_tsf,
#                         # "end_tsf": tsf,
#                         # "roam_time_tsf_us": roam_time_tsf_us,
#                         # "roam_time_tsf_ms": roam_time_tsf_ms,
#                         # "start_type": "auth" if auth_seen else "reassoc"
#                     })
#                     #  setting the these times to be none to capture new roam times.
#                     state = None
#                     start_time = None
#                     start_tsf = None
#                     auth_seen = False

#                 # Always update last BSSID
#                 last_bssid = current_bssid

#             except Exception as e:
#                 print("Error:", e)

#         cap.close()



#     def _write_csv(self, path=""):

#         # If path is provided, create subfolder
#         if path:
#             output_dir = os.path.join(path, "client_roaming_csvs")
#         else:
#             output_dir = "client_roaming_csvs"

#         os.makedirs(output_dir, exist_ok=True)
#         print(self.client_names)
#         for name in self.client_names:
#             filename = os.path.join(output_dir, f"{name}_roam_times.csv")

#             with open(filename, "w", newline="") as f:
#                 writer = csv.DictWriter(
#                     f,
#                     fieldnames=[
#                         "from_bssid",
#                         "to_bssid",
#                         "start_time",
#                         "end_time",
#                         "roam_time_sec",
#                     ]
#                 )

#                 writer.writeheader()
#                 writer.writerows(self.client_names[name])

#             print(f"Saved {filename}")


#     def save_pcap_to_dir(self, pcap_path, path):

#         filename = os.path.basename(pcap_path)

#         dest_path = os.path.join(path, filename)

#         shutil.copy2(pcap_path, dest_path)

#         print(f"PCAP saved to {dest_path}")

# if __name__ == "__main__":
#     BASE_DIR = os.path.dirname(os.path.abspath(__file__))

#     CONFIG_PATH = os.path.join(BASE_DIR, "../..", "candela_roaming_client_ap.json")
#     CONFIG_PATH = os.path.abspath(CONFIG_PATH)
#     PCAP_PATH = os.path.join(BASE_DIR, "../../","local/interop-webGUI/results/roaming_with_ocean_view/roaming.pcap")
#     print(PCAP_PATH)

#     def load_config(path):
#         with open(path, "r") as f:
#             return json.load(f)
            
#     config = load_config(CONFIG_PATH)

#     clients = config["clients"]
#     ap_bssids = config["ap_bssids"]

#     analyzer = RoamAnalyzer(
#         pcap_file=PCAP_PATH,
#         clients=clients,
#         ap_bssids=ap_bssids
#     )

#     analyzer.analyze()
#     analyzer._write_csv(path = "/home/lanforge/local/interop-webGUI/results/dukwdh")
#     analyzer.save_pcap_to_dir(PCAP_PATH, "/home/lanforge/local/interop-webGUI/results/ping123")