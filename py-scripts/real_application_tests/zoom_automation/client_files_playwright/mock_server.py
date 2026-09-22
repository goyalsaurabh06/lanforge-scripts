"""
mock_server.py
--------------
Simulates the real Flask backend for both ZoomHost and ZoomClient.

Run this BEFORE running test_zoom_host.py or test_zoom_client.py:
    python mock_server.py

Fill in the fields marked <-- below before running.
The host script will populate login_url and login_passwd automatically
once it joins the meeting — the client reads them from there.
If running the client standalone (no host), fill login_url and
login_passwd manually with your meeting ID and password.
"""

from flask import Flask, jsonify, request
from datetime import datetime, timedelta
import pytz

app = Flask(__name__)

tz = pytz.timezone("Asia/Kolkata")
now = datetime.now(tz)

# --- Shared state ---
state = {
    # Host credentials
    "host_email":            "candelatech2@gmail.com",   # <-- change this
    "host_passwd":           "CANDELAtech1@530048",           # <-- change this

    # Set these if running the client WITHOUT the host script.
    # The host script populates these automatically after it joins.
    "login_url":             "81687746290",  # <-- e.g. "12345678901"
    "login_passwd":          "KVVtjQ9l4Fwapbbv1tTzxtuVYbwqnz.1",        # <-- e.g. "abc123"

    "login_completed":       False,
    "test_started":          False,
    "participants_required": 1,
    "participants_joined":   0,
    "start_time":            (now + timedelta(seconds=10)).isoformat(),
    "end_time":              (now + timedelta(seconds=40)).isoformat(),
    "stop":                  False,
    "download_csv":          False,
    "audio_stats":           True,
    "video_stats":           True,
    "clients_disconnected":  False,
    "uploaded_stats":        [],
}


# ---------- GET endpoints ----------

@app.route("/get_host_email")
def get_host_email():
    return jsonify({"host_email": state["host_email"]})


@app.route("/get_host_passwd")
def get_host_passwd():
    return jsonify({"host_passwd": state["host_passwd"]})


@app.route("/login_completed")
def login_completed():
    state["login_completed"] = True
    print("[SERVER] login_completed called")
    return jsonify({"status": "ok"})


@app.route("/get_participants_req")
def get_participants_req():
    return jsonify({"participants": state["participants_required"]})


@app.route("/get_start_end_time")
def get_start_end_time():
    return jsonify({
        "start_time": state["start_time"],
        "end_time":   state["end_time"],
    })


@app.route("/check_stop")
def check_stop():
    return jsonify({"stop": state["stop"]})


@app.route("/download_csv")
def download_csv():
    return jsonify({"download_csv": state["download_csv"]})


@app.route("/stats_opt")
def stats_opt():
    return jsonify({
        "audio_stats": state["audio_stats"],
        "video_stats": state["video_stats"],
    })


# ---------- POST endpoints ----------

@app.route("/login_url", methods=["GET"])
def get_login_url():
    print(f"[SERVER] login_url fetched: {state['login_url']}")
    return jsonify({"login_url": state["login_url"]})


@app.route("/login_passwd", methods=["GET"])
def get_login_passwd():
    print(f"[SERVER] login_passwd fetched: {state['login_passwd']}")
    return jsonify({"login_passwd": state["login_passwd"]})


@app.route("/login_url", methods=["POST"])
def post_login_url():
    state["login_url"] = request.json.get("login_url")
    print(f"[SERVER] login_url received: {state['login_url']}")
    return jsonify({"status": "ok"})


@app.route("/login_passwd", methods=["POST"])
def post_login_passwd():
    state["login_passwd"] = request.json.get("login_passwd")
    print(f"[SERVER] login_passwd received: {state['login_passwd']}")
    return jsonify({"status": "ok"})


@app.route("/test_started", methods=["POST"])
def test_started():
    state["test_started"] = request.json.get("test_started", False)
    print(f"[SERVER] test_started: {state['test_started']}")
    return jsonify({"status": "ok"})


@app.route("/set_participants_joined", methods=["POST"])
def set_participants_joined():
    state["participants_joined"] = request.json.get("participants_joined")
    print(f"[SERVER] participants_joined: {state['participants_joined']}")
    return jsonify({"status": "ok"})


@app.route("/clients_disconnected", methods=["POST"])
def clients_disconnected():
    state["clients_disconnected"] = request.json.get("clients_disconnected", False)
    print(f"[SERVER] clients_disconnected: {state['clients_disconnected']}")
    return jsonify({"status": "ok"})


@app.route("/upload_stats", methods=["POST"])
def upload_stats():
    data = request.json
    state["uploaded_stats"].append(data)
    print(f"[SERVER] stats received: {data}")
    return jsonify({"status": "ok"})


@app.route("/upload_csv", methods=["POST"])
def upload_csv():
    data = request.json
    print(f"[SERVER] CSV received: filename={data.get('filename')}, rows={len(data.get('rows', []))}")
    return jsonify({"status": "ok"})



@app.route("/debug")
def debug():
    return jsonify(state)


if __name__ == "__main__":
    print("=" * 50)
    print("Mock server starting on http://127.0.0.1:5000")
    print("Edit credentials and meeting details in state{} before running!")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False)
