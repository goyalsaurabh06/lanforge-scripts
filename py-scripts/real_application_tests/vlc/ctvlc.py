import subprocess
import socket
import time
import argparse
import sys
import os
import platform
import requests


def find_vlc_path():
    system_os = platform.system()
    if system_os == "Windows":
        for path in [
            r"C:\Program Files\VideoLAN\VLC\vlc.exe",
            r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
        ]:
            if os.path.exists(path):
                return path
        raise FileNotFoundError("VLC not found in standard locations on Windows.")
    elif system_os == "Darwin":
        return "open"
    else:
        return "vlc"


def build_vlc_command(mode, media_file, mcast_ip, port, rc_port, client_id):
    system_os = platform.system()
    vlc = find_vlc_path()
    stream_url = f"udp://@{mcast_ip}:{port}"
    if system_os == "Darwin":
        cmd = [vlc, "-a", "VLC", "--args"]
    else:
        cmd = [vlc]

    if mode == "host":
        cmd.append(media_file)
        sout = f"#duplicate{{dst=display,dst=std{{access=udp,mux=ts,dst={mcast_ip}:{port}}}}}"
        cmd += ["--sout", sout]
    elif mode == "client":
        cmd.append(stream_url)

    # macOS uses the native interface; skip --intf qt
    if system_os != "Darwin":
        cmd += ["--intf", "qt"]
    if system_os == "Linux":
        sta_name = client_id.split(".")
        sta_id = sta_name[2] if len(sta_name) >= 3 else "wlan0"
        cmd += ["--miface", f"{sta_id}"]

    cmd += ["--extraintf", "rc", "--rc-host", f"localhost:{rc_port}", "--loop"]

    return cmd


def connect_rc_socket(rc_port):
    for _ in range(20):
        try:
            sock = socket.create_connection(("localhost", rc_port), timeout=2)
            try:
                sock.recv(4096)
            except Exception as e:
                print(e)
            return sock
        except Exception as e:
            print(e)
            time.sleep(1)
    return None


def monitor_stats(sock, duration, fserver, client_id):
    start_time = time.time()
    try:
        while True:
            if time.time() - start_time > duration:
                print(f"Done collecting stats for {duration} seconds.")
                break
            try:
                sock.sendall(b"stats\n")
                time.sleep(1)
                data = sock.recv(8192).decode()
                stats = parse_stats(data)
                report_starts_to_server(stats, client_id, fserver)
                time.sleep(2)
            except Exception as e:
                print(f"Error during stats collection: {e}")
                time.sleep(2)
    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        try:
            print("Stopping")
            sock.sendall(b"quit\n")
            sock.close()
        except Exception as e:
            print(e)
            print("error stopping")
            pass


def parse_stats(text):
    stats = {}

    for line in text.splitlines():
        line = line.strip()
        if "input bytes read" in line:
            stats["input_bytes_read"] = line.split(":")[-1].strip()
        elif "input bitrate" in line:
            stats["input_bitrate"] = line.split(":")[-1].strip()
        elif "demux bytes read" in line:
            stats["demux_bytes_read"] = line.split(":")[-1].strip()
        elif "demux bitrate" in line:
            stats["demux_bitrate"] = line.split(":")[-1].strip()
        elif "demux corrupted" in line:
            stats["demux_corrupted"] = line.split(":")[-1].strip()
        elif "discontinuities" in line:
            stats["discontinuities"] = line.split(":")[-1].strip()
        elif "video decoded" in line:
            stats["video_decoded"] = line.split(":")[-1].strip()
        elif "frames displayed" in line:
            stats["frames_displayed"] = line.split(":")[-1].strip()
        elif "frames lost" in line:
            stats["frames_lost"] = line.split(":")[-1].strip()
        elif "audio decoded" in line:
            stats["audio_decoded"] = line.split(":")[-1].strip()
        elif "buffers played" in line:
            stats["buffers_played"] = line.split(":")[-1].strip()
        elif "buffers lost" in line:
            stats["buffers_lost"] = line.split(":")[-1].strip()

    defaults = {
        "input_bytes_read": "0",
        "input_bitrate": "0 kb/s",
        "demux_bytes_read": "0",
        "demux_bitrate": "0 kb/s",
        "demux_corrupted": "0",
        "discontinuities": "0",
        "video_decoded": "0",
        "frames_displayed": "0",
        "frames_lost": "0",
        "audio_decoded": "0",
        "buffers_played": "0",
        "buffers_lost": "0",
    }
    for k, v in defaults.items():
        stats.setdefault(k, v)
    print(stats)
    return stats


def report_starts_to_server(
    stats, client_id="client1", server_url="http://0.0.0.0:5959/stats"
):
    try:
        payload = {client_id: stats}
        res = requests.post(server_url, json=payload)
        print(f"Sent stats: {res.status_code}")
    except Exception as e:
        print(f"Error sending stats to server: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Cross-platform VLC Launcher (host/client)"
    )
    parser.add_argument(
        "mode", choices=["host", "client"], help="Launch VLC as host or client"
    )
    parser.add_argument("--media", help="Path to media file (host only)")
    parser.add_argument("--mcast_ip", default="239.255.0.1", help="Multicast IP")
    parser.add_argument("--port", type=int, default=1234, help="Multicast port")
    parser.add_argument(
        "--rc_port", type=int, default=4212, help="RC port for remote control"
    )
    parser.add_argument(
        "--duration", type=int, default=30, help="Duration in seconds to collect stats"
    )
    parser.add_argument("--fserver", type=str, default="0.0.0.0:5959")
    parser.add_argument("--client_id", type=str, default=None)

    args = parser.parse_args()

    if args.mode == "host" and not args.media:
        print("ERROR Host mode requires --media argument")
        sys.exit(1)
    client_id = args.client_id
    if not client_id:
        client_id = socket.gethostname()
    cmd = build_vlc_command(
        args.mode, args.media, args.mcast_ip, args.port, args.rc_port, client_id
    )
    print(f"Launching VLC in {args.mode.upper()} mode...")
    print("cmmand is ", cmd)
    vlc_proc = subprocess.Popen(
        cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    print("Connecting to RC socket...")
    print(args.rc_port)
    sock = connect_rc_socket(args.rc_port)
    if not sock:
        print("ERROR Could not connect to VLC RC socket")
        vlc_proc.terminate()
        sys.exit(1)

    monitor_stats(sock, args.duration, "http://" + args.fserver + "/stats", client_id)
    print("terminating..")
    vlc_proc.terminate()
    if platform.system() == "Darwin":
        subprocess.Popen("osascript -e 'quit app \"VLC\"'", shell=True)


if __name__ == "__main__":
    main()
