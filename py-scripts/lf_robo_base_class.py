import os
import requests
import time
import json

class RobotClass:
    def __init__(self):
        self.robo_ip = ""
        self.navdata_json = {}
        self.current_coordinate = None
        self.current_angle = None
        self.result_directory = None

    def move_to_coordinate(self, coordinate=None, result_dir=None):
        url = f"http://{self.robo_ip}/cmd/nav_name"
        data = {"coordinate": coordinate}
        self.result_directory = result_dir
        print(f"[MOVE] Sending coordinates: {data}")

        self.navdata_json = {
            "Canbee_location": coordinate,
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
        else:
            print("[MOVE] Failed:", response.text)
            self.navdata_json["status"] = "Failed"

        self._save_navdata(result_dir)
        print("[SAVE] Updated navdata.json:", self.navdata_json)
        return self.navdata_json

    def rotate_angle(self, x, y, angle):
        url = f"http://{self.robo_ip}/cmd/nav_angle"
        data = {"x": x, "y": y, "angle": angle}

        print(f"[ROTATE] Rotating: {data}")
        try:
            response = requests.post(url, json=data)
        except requests.exceptions.RequestException as e:
            print("[ROTATE] Request failed:", e)
            return False

        # ✅ Only update the angle key — don't overwrite
        if not self.navdata_json:
            self.navdata_json = {}

      
      
      
        self.navdata_json["Canbee_angle"] = angle
        self._save_navdata(self.result_directory)

        if response.status_code == 200:
            print("[ROTATE] Success: Rotation completed.")
            return True
        else:
            print("[ROTATE] Failed:", response.text)
            return False

    def wait_for_battery(self):
        url = f"http://{self.robo_ip}/reeman/battery"
        try:
            response = requests.get(url)
            data = response.json()
            level = data.get("level", 0)
        except Exception as e:
            print("[BATTERY] Error fetching battery info:", e)
            return "error"

        if level < 20:
            print(f"[BATTERY] Low ({level}%). Waiting for charge...")
            time.sleep(2)
        else:
            print(f"[BATTERY] OK ({level}%). Continuing.")
        return "ok"
    
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
