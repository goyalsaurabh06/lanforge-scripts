from candela_base_class import initialize_sniffer_obj, RemoteSniffer
import time
from datetime import datetime
from post_roam_analysis import RoamAnalyzer
import os

sniffer_obj = initialize_sniffer_obj(
    mgr="10.17.1.208",
    port=8080,
    sniff_radio="1.2.wiphy1",
    sniff_channel="44",
    moni_name="moni11w0"
)

monitor_created = sniffer_obj.create_monitor()

if not monitor_created:
    print("FAILED TO create Monitor")
    exit()

print("Monitor created")

sniffer = RemoteSniffer(
    "10.17.1.43",
    "lanforge",
    password="lanforge",
    moni_name="moni11w0",
    pcap_name="400_seconds.pcap"
)

try:
    sniffer.connect()
    remote_pcap_path = sniffer.start_sniff("/home/lanforge")

    print("Sniffing started")
    print("Remote pcap path:", remote_pcap_path)

    time.sleep(10)  # capture duration

    sniffer.stop_sniff()
    sniffer.fetch_pcap(remote_pcap_path, "./400_seconds.pcap")
    sniffer.close()

except Exception as e:
    print("Error:", e)
    exit()

path = "./400_seconds.pcap"

if os.path.isfile(path):
    print("File exists")
else:
    print("File does not exist")
    exit()

analyzer = RoamAnalyzer(
    pcap_file=path,
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