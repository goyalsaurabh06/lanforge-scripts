import os
import requests
import time
import json

class RobotClass:
    def __init__(self):
        self.robo_ip = ""
        self.navdata_json = {}

    def move_to_coordinate(self, coordinate=None, result_dir=None):
        url = f"http://{self.robo_ip}/cmd/nav_name"
        data = {"coordinate": coordinate}

        print(f"[MOVE] Sending coordinates: {data}")

        self.navdata_json = {
            "Canbee_location": coordinate,
            "status": "Running"
        }
        self._save_navdata(result_dir)

        response = requests.post(url, json=data)

        if response.status_code == 200:
            print("[MOVE] Robot reached the target.")
            time.sleep(1)
            self.navdata_json["status"] = "Stopped"
        else:
            print("[MOVE] Failed:", response.text)
            self.navdata_json["status"] = "Stopped"

        self._save_navdata(result_dir)
        print("[SAVE] Updated navdata.json:", self.navdata_json)
        return self.navdata_json

    def rotate_angle(self, x, y, angle):
        url = f"http://{self.robo_ip}/cmd/nav_angle"
        data = {"x": x, "y": y, "angle": angle}

        print(f"[ROTATE] Rotating: {data}")
        response = requests.post(url, json=data)

        if response.status_code == 200:
            print("[ROTATE] Success Rotation completed.")
            return True
        else:
            print("[ROTATE] Failed ", response.text)
            return False

    def wait_for_battery(self):
        url = f"http://{self.robo_ip}/reeman/battery"
        response = requests.get(url)
        data = response.json()
        level = data.get("level", 0)

        if level < 20:
            print(f"[BATTERY] Low ({level}%). Waiting for charge...")
            time.sleep(2)
        else:
            print(f"[BATTERY] OK ({level}%). Continuing.")
        return "ok"
    
    def _save_navdata(self, result_dir=None):
        print(result_dir)
        if result_dir:
            os.makedirs(result_dir, exist_ok=True)
            file_path = os.path.join(result_dir, "nav_data.json")
            print("file_path:", file_path)
        else:
            file_path = "nav_data.json"

        with open(file_path, "w") as f:
            json.dump(self.navdata_json, f, indent=4)

def main():
    robo = RobotClass()
    robo.robo_ip = "127.0.0.1:5000"  # Point to your fake robot API

    robo.wait_for_battery()

    # Example coordinates
    x, y, theta = 1, 2, 3
    for i in range(3):
        move_status = robo.move_to_coordinate(x, y, theta)
        if move_status == "success":
            print("[MAIN] Move successful, now rotating...")
            rotate_status = robo.rotate_angle(x, y, theta)
            if rotate_status == "success":
                print("[MAIN] All operations completed successfully ")
            else:
                print("[MAIN] Rotation failed ")
        else:
            print("[MAIN] Move failed ")

if __name__ == "__main__":
    main()