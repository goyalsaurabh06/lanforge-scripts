import os
import requests
import time
import json
import logging
import math

class RobotClass:
    def __init__(self, robo_ip=None, angle_list=None):
        self.robo_ip = robo_ip
        self.navdata_json = {}
        self.current_coordinate = None
        self.current_angle = None
        self.result_directory = None
        self.runtime_dir = None
        self.ip = ""
        self.angle_list = angle_list

    def move_to_coordinate(self, coord=None, result_dir=None):
        url = f"http://{self.robo_ip}/cmd/nav_name"
        data = {"coordinate": coord}
        self.result_directory = result_dir
        stopped = False
        print(f"[MOVE] Sending coordinates: {data}")
        robo_moved = False
        self.navdata_json = {
            "Canbee_location": coord,
            "status": "Running",
            "Canbee_angle": 0
        }
        self._save_navdata(result_dir)

        try:
            response = requests.post(url, json=data)
        except requests.exceptions.RequestException as e:
            print("[MOVE] Request failed:", e)
            self.navdata_json["status"] = "Failed"
            self._save_navdata(result_dir)
            return self.navdata_json

        if response.status_code == 200:
            print("[MOVE] Robot reached the target.")
            time.sleep(5)
            self.navdata_json["status"] = "Stopped"
            robo_moved = True
        else:
            print("[MOVE] Failed:", response.text)
            self.navdata_json["status"] = "Failed"
        
        if self.result_directory is not None and self.check_test_status():
            stopped=True
            return robo_moved,stopped


        self._save_navdata(result_dir)
        print("[SAVE] Updated navdata.json:", self.navdata_json)
        return robo_moved,stopped

    def rotate_angle(self, x=0, y=0, angle_degree=0):
        url = f"http://{self.robo_ip}/cmd/nav_angle"
        data = {"x": x, "y": y, "angle": angle_degree}

        print(f"[ROTATE] Rotating: {data}")
        try:
            response = requests.post(url, json=data)
        except requests.exceptions.RequestException as e:
            print("[ROTATE] Request failed:", e)
            return False

        # ✅ Only update the angle key — don't overwrite
        if not self.navdata_json:
            self.navdata_json = {}
    
    def angles_to_radians(self, angles):
        result = []
        for angle in angles:
            angle=float(angle)
            if angle > 180:
                angle -= 360
            elif angle <= -180:
                angle += 360
            result.append(round(math.radians(angle), 2))
        return result

      
      
      
        self.navdata_json["Canbee_angle"] = angle
        self._save_navdata(self.result_directory)

        if response.status_code == 200:
            print("[ROTATE] Success: Rotation completed.")
            return True
        else:
            print("[ROTATE] Failed:", response.text)
            return False

    # def wait_for_battery(self):
    #     url = f"http://{self.robo_ip}/reeman/battery"
    #     try:
    #         response = requests.get(url)
    #         data = response.json()
    #         level = data.get("level", 0)
    #     except Exception as e:
    #         print("[BATTERY] Error fetching battery info:", e)
    #         return "error"

    #     if level < 20:
    #         print(f"[BATTERY] Low ({level}%). Waiting for charge...")
    #         time.sleep(2)
    #     else:
    #         print(f"[BATTERY] OK ({level}%). Continuing.")
    #     return "ok"
    def check_test_status(self):
        file_path = os.path.join(
            self.runtime_dir,
            "Running_instances/{}_{}_running.json".format(self.ip, self.testname))
        
        print("ffff",file_path)
        if not os.path.exists(file_path):
            return True
        
        with open(file_path, 'r') as f:
            run_status = json.load(f)

            if 'status' in run_status.keys() and run_status["status"] != "Running":
                logging.info("Test is stopped by the user")
                return True
       
        return False
    
    def wait_for_battery(self, battery = 80, stop=None):
        """
        Simplified version:
        - No API calls
        - Uses only time.sleep
        - You pass the current battery level as an argument
        """

        paused = False
        stopped = False

        # Battery low condition
        if battery <= 21:
            paused = True

            if stop is not None:
                stop()

            logging.info(f"Battery low ({battery}%). Pausing test...")
            logging.info("Sending robot to charging point... (simulated)")
            
            # Simulate time for robot to reach charging point
            print("==============================================")
            time.sleep(10)   # adjust as needed
            if self.result_directory is not None and self.check_test_status():
                stopped=True
                return paused,stopped

            logging.info("Robot reached charger. Charging... (simulated)")
            
            # Simulate charging time
            # Example: 5 minutes = 300 seconds
            charging_duration = 10    # change as needed
            time.sleep(charging_duration)

            logging.info("Battery charged. Resuming test...===============================================")
            return paused, stopped

        else:
            # Battery OK
            logging.info(f"[OK] Battery at {battery}%. Continuing test.")
            return paused, stopped

    
    def _save_navdata(self, result_dir=None):
        if result_dir:
            os.makedirs(result_dir, exist_ok=True)
            file_path = os.path.join(result_dir, "nav_data.json")
        else:
            file_path = "nav_data.json"
        with open(file_path, "w") as f:
            json.dump(self.navdata_json, f, indent=4)
        print("[SAVE] nav_data.json updated at:", file_path)

def main():
    robo = RobotClass()
    robo.robo_ip = "127.0.0.1:5000"  # Local test API

    robo.wait_for_battery()

    x, y, theta = 1, 2, 3
    for i in range(3):
        move_status = robo.move_to_coordinate({"x": x, "y": y, "theta": theta}, result_dir="results")

        if move_status.get("status") == "Stopped":
            print("[MAIN] Move successful, now rotating...")
            rotate_status = robo.rotate_angle(x, y, theta)
            if rotate_status:
                print("[MAIN] All operations completed successfully.")
            else:
                print("[MAIN] Rotation failed.")
        else:
            print("[MAIN] Move failed.")

if __name__ == "__main__":
    main()
