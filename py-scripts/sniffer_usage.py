from candela_base_class import initialize_sniffer_obj
import time
sniffer_obj = initialize_sniffer_obj(mgr="192.168.204.75",port=8080,sniff_radio="1.1.wiphy0",sniff_channel="7")
monitor_created = sniffer_obj.create_monitor()
if monitor_created:
    sniffer_obj.start_sniff()

    # after call the stop with same obj
    time.sleep(30)

    sniffer_obj.stop_sniff()
else:
    print("FAILED TO create Monitor")

# FOR MULTIPLE RADIOS build LISTS OF EQUAL SIZE RESPECTIVE LISTS
# EXAMPLE radios=["1.1.wiphy0","1.1.wiphy1","1.1.wiphy2"]
#channels = ["5","6","7"]
#radio            channel
#"1.1.wiphy0"        5
#"1.1.wiphy1"        6
#"1.1.wiphy2"        7
#can create objects for each radio and start sniffing and stopping accordingly