# from candela_base_class import initialize_sniffer_obj
# import time
# from datetime import datetime
# print("hiiiii")
# sniffer_obj = initialize_sniffer_obj(mgr="10.17.1.208",port=8080,sniff_radio="1.2.wiphy1",sniff_channel="44")
# monitor_created = sniffer_obj.create_monitor()
# time.sleep(10)
# if monitor_created:
#     # sniffer_obj.start_sniff()
#     # remote_path = "home/lanforge/captures_at_{}".format(datetime.now())
#     remote_path = "/home/lanforge/".format(
#     datetime.now().strftime("%Y%m%d_%H%M%S")
# )
#     # here get ip from port's the below IP's should be clustred resource IPs
#     sniffer_obj.start_sniff_remote(ip="10.17.1.43",username="lanforge",password="lanforge",remote_path=remote_path)

#     # after call the stop with same obj
#     time.sleep(10)
#     sniffer_obj.stop_sniff_remote()
#     # sniffer_obj.fetch_pcap(local_path="./captures_new")
#     # sniffer_obj.stop_sniff()
# else:
#     print("FAILED TO create Monitor")

# FOR MULTIPLE RADIOS build LISTS OF EQUAL SIZE RESPECTIVE LISTS
# EXAMPLE radios=["1.1.wiphy0","1.1.wiphy1","1.1.wiphy2"]
#channels = ["5","6","7"]
#radio            channel
#"1.1.wiphy0"        5
#"1.1.wiphy1"        6
#"1.1.wiphy2"        7
#can create objects for each radio and start sniffing and stopping accordingly
    



# from candela_base_class import initialize_sniffer_obj,RemoteSniffer
# import time
# from datetime import datetime
# sniffer_obj = initialize_sniffer_obj(mgr="10.17.1.208",port=8080,sniff_radio="1.2.wiphy1",sniff_channel="44",moni_name="moni11w0")
# monitor_created = sniffer_obj.create_monitor()
# time.sleep(15)
# sniffer = RemoteSniffer("10.17.1.43", "lanforge", password="lanforge", moni_name="moni11w0", pcap_name="capture_clad.pcap")
# sniffer.connect()
# remote_pcap_path = sniffer.start_sniff("/home/lanforge")
# print("remote pcap path",remote_pcap_path)
# time.sleep(10)  # capture for 10 seconds
# sniffer.stop_sniff()
# sniffer.fetch_pcap(remote_pcap_path, "./downloaded_capture.pcap")
# sniffer.close()


from candela_base_class import initialize_sniffer_obj,RemoteSniffer
import time
from datetime import datetime
from post_roam_analysis import RoamAnalyzer
# sniffer_obj = initialize_sniffer_obj(mgr="10.17.1.208",port=8080,sniff_radio="1.2.wiphy1",sniff_channel="44",moni_name="moni11w0")
# monitor_created = sniffer_obj.create_monitor()
# time.sleep(15)
# sniffer = RemoteSniffer("10.17.1.43", "lanforge", password="lanforge", moni_name="moni11w0", pcap_name="10_roams_capture.pcap")
# sniffer.connect()
# remote_pcap_path = sniffer.start_sniff("/home/lanforge/lanforge-scripts/py-scripts")
# print("remote pcap path",remote_pcap_path)
# time.sleep(5)  # capture for 10 seconds
# sniffer.stop_sniff()
# sniffer.fetch_pcap(remote_pcap_path, "./10_roams_capture.pcap")
# sniffer.close()

# analyzer = RoamAnalyzer(
#     pcap_file="/home/litin/Document/lanforge-scripts/py-scripts/10_roams_capture.pcap",
#     clients={
#         "vivo": "38:39:cd:76:57:41",
#         "iphone": "66:c6:97:ac:b3:64",
#         "samsung": "34:f0:43:d7:21:43"
#     },
#     ap_bssids={
#         "06:03:7f:19:01:05",
#         "06:03:7f:19:01:09",
#         "06:03:7f:41:15:07",
#     }
# )
# analyzer.analyze()



from candela_base_class import initialize_sniffer_obj, RemoteSniffer
import time
from datetime import datetime
from post_roam_analysis import RoamAnalyzer
import os

from candela_base_class import initialize_sniffer_obj

sniffer_obj1 = initialize_sniffer_obj(
    mgr="10.17.1.208",
    port=8080,
    sniff_radio="1.2.wiphy0",
    sniff_channel=11,
    moni_name="moni2g"
)

sniffer_obj2 = initialize_sniffer_obj(
    mgr="10.17.1.208",
    port=8080,
    sniff_radio="1.2.wiphy1",
    sniff_channel=44,
    moni_name="moni5g"
)

sniffer_obj3 = initialize_sniffer_obj(
    mgr="10.17.1.208",
    port=8080,
    sniff_radio="1.2.wiphy2",
    sniff_channel=239,
    moni_name="moni6g"
)

sniffer_obj1.clear_monitor_interfaces()

monitor_created1 = sniffer_obj1.create_monitor()
monitor_created2 = sniffer_obj2.create_monitor()
monitor_created3 = sniffer_obj3.create_monitor()


if not monitor_created1:
    print("FAILED to create 2.4GHz monitor")
    exit()

if not monitor_created2:
    print("FAILED to create 5GHz monitor")
    exit()

if not monitor_created3:
    print("FAILED to create 6GHz monitor")
    exit()

print("Monitors created successfully")

# sniffer_obj1.start_sniff()
# sniffer_obj2.start_sniff()
# sniffer_obj3.start_sniff()
sniffer = RemoteSniffer(
    "10.17.1.43",
    "lanforge",
    password="lanforge",
    moni_name="moni11w0",
    pcap_name="tri_band.pcap"
)

try:
    sniffer.connect()
    remote_pcap_path = sniffer.start_sniff_for_triband("/home/lanforge", moni2g="moni2g", moni5g="moni5g", moni6g="moni6g")

    print("Sniffing started")
    print("Remote pcap path:", remote_pcap_path)

    time.sleep(10)  # capture duration

    sniffer.stop_sniff()
    sniffer.fetch_pcap(remote_pcap_path, "./tri_band.pcap")
    sniffer.close()

except Exception as e:
    print("Error:", e)
    exit()

path = "./tri_band.pcap"

if os.path.isfile(path):
    print("File exists")
else:
    print("File does not exist")
    exit()

# analyzer = RoamAnalyzer(
#     pcap_file=path,
#     clients={
#         "vivo": "38:39:cd:76:57:41",
#         "iphone": "66:c6:97:ac:b3:64",
#         "samsung": "34:f0:43:d7:21:43"
#     },
#     ap_bssids={
#         "06:03:7f:19:01:05",
#         "06:03:7f:19:01:09",
#         "06:03:7f:41:15:07",
#     }
# )

# analyzer.analyze()