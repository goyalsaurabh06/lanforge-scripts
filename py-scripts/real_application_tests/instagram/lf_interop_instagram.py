#!/usr/bin/env python3
import argparse
import importlib
import logging
import os
import sys

# LANforge paths
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

lf_logger_config = importlib.import_module('py-scripts.lf_logger_config')
realm = importlib.import_module('py-json.realm')
Realm = realm.Realm
base = importlib.import_module('py-scripts.lf_base_interop_profile')
RealDevice = base.RealDevice
DeviceConfig = importlib.import_module('py-scripts.DeviceConfig')

logger = logging.getLogger(__name__)


class Instagram(Realm):
    def __init__(self, mgr, mgr_port, username, password, duration, upstream_port):
        super().__init__(lfclient_host=mgr, lfclient_port=mgr_port)
        self.mgr = mgr
        self.username = username
        self.password = password
        self.duration = duration
        self.upstream_port = upstream_port
        self.real_sta_list = []
        self.real_sta_os_types = []
        self.real_sta_hostname = []

    #  IOS FILTER 
    def filter_ios_devices(self, device_list):
        filtered = []
        for dev in device_list:
            try:
                shelf, res = dev.split(".")[:2]
                r = self.json_get(f"/resource/{shelf}/{res}")
                hw = r["resource"].get("hw version", "")
                app_id = r["resource"].get("app-id", "")
                kernel = r["resource"].get("kernel", "")
                if "Apple" in hw and app_id and (app_id != "0" or kernel == ""):
                    logger.info(f"Skipping iOS device: {dev}")
                else:
                    filtered.append(dev)
            except Exception:
                continue
        return filtered

    #  REAL DEVICE SELECTION 
    def select_real_devices(self, real_sta_list=None):
        self.real_device_obj = RealDevice(manager_ip=self.mgr, selected_bands=[])
        self.real_device_obj.get_devices()

        if real_sta_list is None:
            self.real_sta_list, _, _ = self.real_device_obj.query_user()
        else:
            self.real_sta_list = real_sta_list

        self.real_sta_list = self.filter_ios_devices(self.real_sta_list)

        for sta in self.real_sta_list:
            if sta in self.real_device_obj.devices_data:
                info = self.real_device_obj.devices_data[sta]
                self.real_sta_os_types.append(info["ostype"])
                self.real_sta_hostname.append(info["hostname"])

    #  ANDROID SERIAL SELECTION (FIXED) 
    def get_android_serials_for_users(self, real_sta_list):
        """
        Only return Android devices 
        """
        users = set()
        for sta in real_sta_list:
            try:
                shelf, res = sta.split(".")[:2]
                r = self.json_get(f"/resource/{shelf}/{res}")
                user = r.get("resource", {}).get("user", "")
                if user:
                    users.add(user)
            except Exception:
                continue

        if not users:
            logger.info("No users found for selected real devices")
            return []

        adb_resp = self.json_get("/adb")
        adb_devices = adb_resp.get("devices", [])

        if isinstance(adb_devices, dict):
            adb_devices = [adb_devices]

        serials = []
        for dev in adb_devices:
            for serial, info in dev.items():
                if info.get("phantom", False):
                    continue
                if info.get("user-name") in users:
                    serials.append(serial.split(".")[-1])

        logger.info(f"Matched Android serials: {serials}")
        return serials

    # LAPTOP EXECUTION 
    def run_laptops(self):
        print("\nStarting Instagram Selenium on laptops...")
        self.laptop_profiles = []

        for sta, os_type, hostname in zip(
            self.real_sta_list,
            self.real_sta_os_types,
            self.real_sta_hostname
        ):
            profile = self.new_generic_endp_profile()
            profile.name_prefix = f"insta_{sta}"
            profile.create(ports=[sta], sleep_time=0.5)
            endp = profile.created_endp[0]

            if os_type == "windows":
                cmd = (
                    "\"C:\\Program Files (x86)\\LANforge-Server\\instagram_stream.bat\" "
                    f"--username {self.username} "
                    f"--password {self.password} "
                    f"--duration {self.duration}"
                )
            elif os_type == "linux":
                cmd = (
                    "su -l lanforge -c "
                    "\"/home/lanforge/instagram_stream.bash "
                    f"--username {self.username} "
                    f"--password {self.password} "
                    f"--duration {self.duration}\""
                )
            elif os_type == "macos":
                cmd = (
                    "sudo bash /Users/lanforge/instagram_stream_macos.bash "
                    f"--username {self.username} "
                    f"--password {self.password} "
                    f"--duration {self.duration}"
                )
            else:
                continue

            print(f"[{hostname}] {cmd}")
            profile.set_cmd(endp, cmd)
            self.laptop_profiles.append(profile)

        for profile in self.laptop_profiles:
            profile.start_cx()

    # ANDROID EXECUTION -
    def run_android_generic(self, android_serials):
        print("\nStarting Instagram Android via Generic Endpoint...")
        anchor_port = "1.1.eth0"

        profile = self.new_generic_endp_profile()
        profile.name_prefix = "insta_android"
        profile.create(ports=[anchor_port], sleep_time=0.5, real_client_os_types=["linux"])

        cmd = (
            "bash -lc '"
            "/usr/bin/python3 /home/lanforge/instagram_android.py "
            f"--devices {','.join(android_serials)} "
            f"--duration {self.duration} "
            f"--upstream_port {self.upstream_port} "
            "| tee /home/lanforge/instagram_android.log'"
        )

        print(f"[ANDROID] {cmd}")
        profile.set_cmd(profile.created_endp[0], cmd)
        profile.start_cx()


#  MAIN 
def main():
    parser = argparse.ArgumentParser(description="Instagram Automation")
    parser.add_argument("--mgr", required=True)
    parser.add_argument("--mgr_port", default=8080)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--duration", type=int, required=True)
    parser.add_argument("--upstream_port", required=True)
    parser.add_argument("--device_list", default=None)
    args = parser.parse_args()

    lf_logger_config.lf_logger_config().set_level("info")

    inst = Instagram(
        args.mgr,
        args.mgr_port,
        args.username,
        args.password,
        args.duration,
        args.upstream_port
    )

    inst.select_real_devices(
        args.device_list.split(",") if args.device_list else None
    )

    # Run laptop tests
    if inst.real_sta_list:
        inst.run_laptops()

    # Run Android tests ONLY if user-matched devices exist
    android_serials = inst.get_android_serials_for_users(inst.real_sta_list)
    if android_serials:
        inst.run_android_generic(android_serials)
    else:
        logger.info("No Android devices matched selected real devices. Skipping Android.")

    print("\nInstagram automation started successfully!")


if __name__ == "__main__":
    main()
