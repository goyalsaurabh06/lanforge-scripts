import sys
import os
import importlib
import time
sys.path.append(os.path.join(os.path.abspath(__file__ + "../../../")))
realm = importlib.import_module("py-json.realm")
Realm = realm.Realm

class MonitorInteropData(Realm):
    def __init__(self,host="localhost",port=8080):
        super().__init__(lfclient_host=host,
                         lfclient_port=port)
        self.host = host
        self.port = port

    def monitor_layer3_data(self, cx_list, duration=60):
        """
        Monitor Layer 3 data for a specified duration.
        :param duration: Duration in seconds to monitor the data.
        """
        print(f"Starting Layer 3 data monitoring for {duration} seconds...")
        # Placeholder for actual monitoring logic
        # This would typically involve fetching data from the LANforge API
        # and processing it as needed.
        time.sleep(duration)
        print("Layer 3 data monitoring completed.")
    
    def monitor_l3_endp_data(self, cx_list, duration=60,direction='bidirectional'):
        """
        Monitor Layer 3 endpoint data for a specified duration.
        :param duration: Duration in seconds to monitor the endpoint data.
        """
        print(f"Starting Layer 3 endpoint data monitoring for {duration} seconds...")
        cx_list_endp = []
        for i in cx_list:
            cx_list_endp.append(i + '-A')
            cx_list_endp.append(i + '-B')
        
        # print("Monitoring till rates appear in CX's")
        start_time = time.time()
        while time.time() - start_time < duration:
            try:
                l3_endp_data = list(self.json_get('/endp/{}/list?fields=rx rate (last),rx drop %25,name,run,name'.format(','.join(cx_list_endp)))['endpoint'])
            except Exception as e:
                print("Failed to get Layer 3 endpoint data: {}".format(e))
                break
            for cx in cx_list:
                for j in l3_endp_data:
                    key, value = next(iter(j.items()))
                    endp_a = cx + '-A'
                    endp_b = cx + '-B'
                    if direction == 'bidirectional':
                        if value['rx rate (last)'] > 0:
                            return True
                    elif direction == 'upload' and value['name'] == endp_b:
                        if value['rx rate (last)'] > 0:
                            return True
                    elif direction == 'download' and value['name'] == endp_a:
                        if value['rx rate (last)'] > 0:
                            return True
            time.sleep(2)
        
        return False

    def monitor_l4_endp_data(self, cx_list, duration=60):
        """
        Monitor Layer 4 endpoint data for a specified duration.
        :param duration: Duration in seconds to monitor the endpoint data.
        """
        print(f"Starting Layer 4 endpoint data monitoring for {duration} seconds...")
        # Placeholder for actual monitoring logic
        # This would typically involve fetching endpoint data from the LANforge API
        # and processing it as needed.
        time.sleep(duration)
        print("Layer 4 endpoint data monitoring completed.")