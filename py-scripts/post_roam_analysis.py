import pyshark
import csv


class RoamAnalyzer:

    def __init__(self, pcap_file, clients, ap_bssids, tshark_path="/usr/bin/tshark"):
        self.pcap_file = pcap_file
        self.clients = clients
        self.ap_bssids = set([b.lower() for b in ap_bssids])
        self.tshark_path = tshark_path
        self.results = {name: [] for name in clients}

    def analyze(self):
        for name, mac in self.clients.items():
            print(f"\nProcessing {name}: {mac}")
            self._process_client(name, mac)

        self._write_csv()

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
                    self.results[name].append({
                        "from_bssid": from_bssid,
                        "to_bssid": to_bssid,
                        "start_time": start_time,
                        "end_time": ts,
                        "roam_time_sec": roam_time,
                        "start_tsf": start_tsf,
                        "end_tsf": tsf,
                        "roam_time_tsf_us": roam_time_tsf_us,
                        "roam_time_tsf_ms": roam_time_tsf_ms,
                        "start_type": "auth" if auth_seen else "reassoc"
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

    def _write_csv(self):
        for name in self.results:
            filename = f"{name}_roam_times.csv"

            with open(filename, "w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "from_bssid",
                        "to_bssid",
                        "start_time",
                        "end_time",
                        "roam_time_sec",
                        "start_tsf",
                        "end_tsf",
                        "roam_time_tsf_us",
                        "roam_time_tsf_ms",
                        "start_type"
                    ]
                )
                writer.writeheader()
                writer.writerows(self.results[name])

            print(f"Saved {filename}")


if __name__ == "__main__":
    analyzer = RoamAnalyzer(
        pcap_file="/home/lanforge/Day2_trail1_issue.pcap",
        clients={
            "vivo": "38:39:cd:76:57:41",
            "iphone": "66:c6:97:ac:b3:64",
            "samsung": "34:f0:43:d7:21:43"
        },
        ap_bssids={
            "06:03:7f:19:01:05",
            "06:03:7f:19:01:09",
            "06:03:7f:41:15:07",
        }
    )

    analyzer.analyze()