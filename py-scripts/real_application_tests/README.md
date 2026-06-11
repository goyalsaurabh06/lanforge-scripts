# flake8: noqa
# Zoom, YouTube Video Streaming, MS Teams Call, Ookla Speed Test, VLC Streaming, and Real Browser Automation

## Objective
This project aims to automate Zoom call tests, YouTube video streaming tests, MS Teams call tests, Ookla speed tests, VLC streaming tests, and real browser tests across multiple laptops, collect network performance statistics, and store the data in a CSV file. Additionally, automated graphs will be generated using the collected data.

## Hardware Requirements

| Device         | Supported Version         |
|---------------|--------------------------|
| LANforge Unit | f36 and above            |
| Linux Laptop  | Ubuntu 20.04.6 and above |
| Windows Laptop | Windows 10 and above    |
| MacBook       | v12.7.4 and above        |


## Prerequisites
- Cluster all laptops to LANforge.
- Ensure real clients access the internet only via the wireless interface by disabling the Ethernet interface.
- Ensure files are placed in the respective paths as per the tables below.
- Install Python (>=3.9.x) and Selenium (>4.17.x).
- Disable public and private firewalls on Windows laptops.
- Install the necessary dependencies before running the tests using the `install_dependencies.py` file.

---

## Script Files and Their Placement

### Zoom Call Test

| Device      | Path                                                          | Files |
|------------|----------------------------------------------------------------|-------|
| Windows    | `C:\Program Files (x86)\LANforge-Server`                        | `install_dependencies.py`, `zoom_host.py`, `zoom_client.py` |
| Linux      | `/home/lanforge`                                                | `install_dependencies.py`, `zoom_host.py`, `zoom_client.py`, `ctzoom.bash` |
| MacOS      | `/Users/lanforge`                                               | `install_dependencies.py`, `zoom_host.py`, `zoom_client.py`, `ctzoom.bash` |

### Teams Call Test

| Device      | Path                                                          | Files |
|------------|----------------------------------------------------------------|-------|
| Windows    | `C:\Program Files (x86)\LANforge-Server`                        | `teams_host.py`, `teams_client.py` |
| Linux      | `/home/lanforge`                                                | `teams_host.py`, `teams_client.py`, `ctteams.bash` |
| MacOS      | `/Users/lanforge`                                               | `teams_host.py`, `teams_client.py`, `ctteams.bash` |

### VLC Streaming Test

| Device      | Path                                                          | Files |
|------------|----------------------------------------------------------------|-------|
| Windows    | `C:\Program Files (x86)\LANforge-Server`                        | `ctvlc.py` |
| Linux      | `/home/lanforge`                                                | `ctvlc.py`, `ctvlc.bash` |
| MacOS      | `/Users/lanforge`                                               | `ctvlc.py`, `ctvlc.bash` |

### YouTube Streaming Test

| Device          | Path                                      | Files |
|---------------|--------------------------------|-------|
| Windows        | `C:\Program Files (x86)\LANforge-Server` | `youtube.py`, `youtube_stream.bat` |
| Linux         | `/home/lanforge` | `youtube.py`, `ctyt.bash` |
| MacOS         | `/Users/lanforge` | `youtube.py`, `ctyt.bash` |

### Ookla Speed Test

| Device          | Path                                      | Files |
|---------------|--------------------------------|-------|
| Windows        | `C:\Program Files (x86)\LANforge-Server` | `ookla.py` |
| Linux         | `/home/lanforge` | `ookla.py` |
| MacOS         | `/Users/lanforge` | `ookla.py` |

### Real Browser Test

| Device      | Path                                                          | Files |
|------------|----------------------------------------------------------------|-------|
| Windows    | `C:\Program Files (x86)\LANforge-Server`                        | `real_browser.py`, `real_browser.bat` |
| Linux      | `/home/lanforge`                                                | `real_browser.py`, `ctrb.bash` |
| MacOS      | `/Users/lanforge`                                               | `real_browser.py`, `ctrb.bash` |

---

# Zoom Call Automation Test

## Overview of Scripts

| Script                 | Description |
|------------------------|-------------|
| `install_dependencies.py` | Installs Python dependencies required for the Real Application Tests. |
| `zoom_host.py`         | Python Selenium script that launches a browser and creates a Zoom meeting. |
| `zoom_client.py`       | Python Selenium script that joins the Zoom meeting created by the host. |
| `ctzoom.bash`          | Bash script for pre-cleanup, post-cleanup, and triggering Zoom scripts on Linux and macOS. |

## Additional Packages for Linux Laptops

**Linux Devices:**
```bash
sudo apt install xclip
sudo apt install python3-tk python3-dev
```

---

# YouTube Video Streaming Test

## Overview of Scripts

| Script              | Description |
|---------------------|-------------|
| `youtube.py`       | Selenium script that launches a browser, opens a YouTube video, sets resolution, and opens 'Stats for Nerds'. |
| `youtube_stream.bat` | Windows batch script for pre-cleanup, post-cleanup, and triggering `youtube.py`. |
| `ctyt.bash`       | Linux/macOS script for pre-cleanup, post-cleanup, and triggering `youtube.py`. |

---

# Real Browser Test

## Overview of Scripts

| Script              | Description |
|---------------------|-------------|
| `real_browser.py`  | Python Selenium script for opening a browser and reloading a test URL. |
| `real_browser.bat` | Windows batch script for pre-cleanup, post-cleanup, and triggering `real_browser.py`. |
| `ctrb.bash`       | Linux/macOS script for pre-cleanup, post-cleanup, and triggering `real_browser.py`. |

---

# Ookla Speed Test

## Overview of Scripts

| Script              | Description |
|---------------------|-------------|
| `ookla.py`       | Selenium script that launches a browser and initiates Ookla speedtest for laptops, for Android need Ookla speedtest app. |

## Running the Ookla Speed Test
Navigate to `/home/lanforge/lanforge-scripts/py-scripts/` and execute the script:

```bash
python3 lf_interop_speedtest.py --mgr 192.168.214.219 --device_list 1.10,1.23 --iteration 2 --dowebgui --cleanup
```

---

## Notes:
- **Please run the `install_dependencies.py` file on the client side before executing any tests.**

---

## Installing Dependencies

### Windows
Run the following command as an **Administrator** user:
```cmd
py install_dependencies.py
```

### Ubuntu
Run the following command as **root** user:
```bash
python3 install_dependencies.py
```

### macOS
Run the following command as **root** user:
```bash
python3 install_dependencies.py
```

### If Installation is Blocked (macOS / Ubuntu)
If the system blocks the dependency installation, use the following command instead:
```bash
pip3 install selenium requests pyperclip pytz pyautogui clipboard --break-system-packages
```

---

## Installing Dependencies for Teams Automation

Teams automation requires a virtual environment. Follow the steps below for each platform.

### Ubuntu
Navigate to `/home/lanforge` and execute:
```bash
python3 -m venv venv
source venv/bin/activate
python3 install_dependencies.py
```

### macOS
Navigate to `/Users/lanforge` and execute:
```bash
python3 -m venv venv
source venv/bin/activate
python3 install_dependencies.py
```

### Windows
Run the following command as an **Administrator** user:
```cmd
py install_dependencies.py
```
