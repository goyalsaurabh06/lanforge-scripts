import requests
import time
import argparse
import importlib
import os
import json
import math
import logging

class RobotClass:
    def __init__(self,robo_ip=None,angle_list=None):
        self.robo_ip =robo_ip
        self.waypoint_list = []
        self.target_x=None
        self.target_y=None
        self.charge_point_name=None
        self.radian_list=[]
        self.angle_list=angle_list
        self.nav_data_path=None
        self.runtime_dir=None
        self.ip=None
        self.testname=None

    
    def create_waypointlist(self):
        position_url = 'http://'+self.robo_ip+'/reeman/position'
        data= requests.get(position_url)
        data=data.json()
        for wp in data.get("waypoints", []):
            self.waypoint_list.append({
                wp["name"]: {
                    "x": wp["pose"]["x"],
                    "y": wp["pose"]["y"],
                    "theta": wp["pose"]["theta"]
                }
            })

            if wp.get("type") == "charge":
                self.charge_point_name = wp["name"]
    
    def check_test_status(self):
        file_path = os.path.join(
            self.runtime_dir,
            "../../Running_instances/{}_{}_running.json".format(self.ip, self.testname))
        

        if not os.path.exists(file_path):
            return False
        
        with open(file_path, 'r') as f:
            run_status = json.load(f)

            if 'status' in run_status.keys() and run_status["status"] != "Running":
                logging.info("Test is stopped by the user")
                return True
       
        return False
    
    def wait_for_battery(self,stop=None):
        stopped = False
        pause=False
        last_battery_check=0
        battery_url = f"http://{self.robo_ip}/reeman/base_encode"
        status_url=f"http://{self.robo_ip}/reeman/nav_status"
        move_url=f"http://{self.robo_ip}/cmd/nav_name"
        while True:
            try:
                response = requests.get(battery_url, timeout=5)
                response.raise_for_status()
                data = response.json()
                battery = data.get("battery", 0)
                charge_flag = data.get("chargeFlag", 0)
                retries=0
                if battery <= 20:
                    pause=True
                    if stop is not None:
                        stop()
                    logging.info("Battery low ({}%). Pausing test until fully charged...{}".format(battery,time.time()))
                    requests.post(move_url,json={"point":self.charge_point_name})
                    while True:
                        matched = False
                        try:
                            response = requests.get(status_url,timeout=5)
                            response.raise_for_status()
                            nav_status = response.json()
                        except (requests.RequestException, ValueError) as e:
                            logging.info("[ERROR] Failed to get robot status: {}".format(e))
                            time.sleep(5)
                            retries+=1
                            if(retries == 15):
                                abort = True
                                break
                            
                            continue
                        goal = nav_status.get("goal","")
                        state=nav_status.get("res","")
                        distance=nav_status.get("dist","")
                        if goal == self.charge_point_name and state == 3 and distance<0.5:
                            matched = True
                            break

                    while True:
                        if self.runtime_dir is not None and self.check_test_status():
                            stopped=True
                            return pause,stopped
                            
                        
                        current_time = time.time()
                        if current_time - last_battery_check >= 300:
                            try:
                                resp = requests.get(battery_url, timeout=5)
                                resp.raise_for_status()
                                charge_data = resp.json()   
                                new_battery = charge_data.get("battery", 0)
                                logging.info("Current battery: {}%".format(new_battery))
                                if new_battery > 100:
                                    logging.info("Battery full. Resuming test...")
                                    return pause,stopped
                            except Exception as e:
                                logging.info("[ERROR] Checking charge: {}".format(e))

                            last_battery_check=time.time()
                        time.sleep(10)        
                else:
                    logging.info("[OK] Battery at {}%. Continuing test.".format(battery))
                    return pause,stopped

            except Exception as e:
                logging.info("[ERROR] Failed to check battery: {}".format(e))
                time.sleep(600)

    def move_to_coordinate(self,coord):
        abort=False
        moverobo_url = 'http://'+self.robo_ip+'/cmd/nav_name'
        status_url= 'http://'+self.robo_ip+'/reeman/nav_status'
        requests.post(moverobo_url,json={"point":coord})
        for wp in self.waypoint_list:
            if coord in wp:
                target_name =coord
                self.target_x = wp[coord]["x"]
                self.target_y = wp[coord]["y"]
        
        retries=0
        logging.info("Moving to point {}".format(coord))
        while True:
            matched = False
            try:
                response = requests.get(status_url,timeout=5)
                response.raise_for_status()
                nav_status = response.json()
            except (requests.RequestException, ValueError) as e:
                logging.info("[ERROR] Failed to get robot status: {}".format(e))
                time.sleep(5)
                retries+=1
                if(retries == 15):
                    abort = True
                    break
                
                continue
            goal = nav_status.get("goal","")
            state=nav_status.get("res","")
            distance=nav_status.get("dist","")
            if goal == coord and state == 3 and distance < 0.5:
                matched = True
                break
        
        # Store the coordinate in navdatajson only from webui
        if self.nav_data_path:
            if not os.path.exists(self.nav_data_path):
                with open(self.nav_data_path, "w") as file:
                    json.dump({}, file)
            with open(self.nav_data_path, 'r') as x:
                navdata = json.load(x)   
            if abort:
                navdata['status']="Stopped"
                navdata['Canbee_location']=''
                navdata['Canbee_angle']=''
            else:
                navdata['status']="Running"
                navdata['Canbee_location']=coord
                navdata['Canbee_angle']=''
            with open(self.nav_data_path, 'w') as x:
                json.dump(navdata, x, indent=4)

        return  matched,abort

    def rotate_angle(self,angle):
        nav_pathurl= 'http://'+self.robo_ip+'/cmd/nav'
        pose_url= 'http://'+self.robo_ip+'/reeman/pose'
        print("ddddd",self.target_x,self.target_y,angle)
        requests.post(nav_pathurl,json={"x":self.target_x,"y":self.target_y,"theta":angle})
        retries_for_theta=0
        rotated=False
        logging.info("Rotating to an angle".format(angle))
        while True:
            try:
                response = requests.get(pose_url,timeout=5)
                response.raise_for_status()
                data_pose=response.json()
            except (requests.RequestException, ValueError) as e:
                logging.info("[ERROR] Failed to get robot status of pose: {}".format(e))
                time.sleep(5)
                retries_for_theta+=1
                if(retries_for_theta == 5):
                    break
                continue

            theta=data_pose['theta']
            theta = round(theta, 2)
            if abs(angle - theta) <= 0.15:
                rotated = True
                if self.nav_data_path is not None:
                    with open(self.nav_data_path, 'r') as x:
                        navdata = json.load(x)                       
                        navdata['Canbee_angle']=angle
                    with open(self.nav_data_path, 'w') as x:
                        json.dump(navdata, x, indent=4)
                logging.info("Rotation completed to angle {}".format(angle))
                break
        
        return rotated
    
    def angles_to_radians(self,angles):
        result = []
        for angle in angles:
            angle=float(angle)
            if angle > 180:
                angle -= 360
            elif angle <= -180:
                angle += 360
            result.append(round(math.radians(angle), 2))
        print("result",result)
        return result


def main():

    parser = argparse.ArgumentParser(
        prog='lf_base_robo.py',
        formatter_class=argparse.RawTextHelpFormatter,
        description=''' ''')
    
    required = parser.add_argument_group('Required arguments')
    optional = parser.add_argument_group('Optional arguments')


    
if __name__ == "__main__":
    main()