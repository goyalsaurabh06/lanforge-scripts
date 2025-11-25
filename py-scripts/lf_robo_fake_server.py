from flask import Flask, jsonify, request
import random
import time

app = Flask(__name__)

@app.route("/reeman/battery", methods=["GET"])
def battery():
    # Simulate random battery level
    level = random.randint(40, 100)
    return jsonify({"level": level})

@app.route("/cmd/nav_name", methods=["POST"])
def nav_name():
    data = request.json
    print(f"[FAKE SERVER] Move request: {data}")
    print("Waiting for 5 seconds to MOVE")
    time.sleep(5)  # Simulate movement delay
    return jsonify({"status": "success", "message": "Reached target"}), 200

@app.route("/cmd/nav_angle", methods=["POST"])
def nav_angle():
    data = request.json
    print(f"[FAKE SERVER] Rotate request: {data}")
    print("Waiting for 5 seconds to ROTATE=================")
    time.sleep(5)  # Simulate rotation delay
    return jsonify({"status": "success", "message": "Rotation complete"}), 200

if __name__ == "__main__":
    print("🚀 Fake Robot Server running on http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000)
