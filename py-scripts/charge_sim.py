from flask import Flask, jsonify, request
import time
import threading
import math

app = Flask(__name__)

# ----------------------------
# SIMULATION TOGGLE
# ----------------------------
SIMULATE_BATTERY = False

# ----------------------------
# GLOBAL STATE (Fake Robot)
# ----------------------------
state = {
    "battery": 15,
    "charging": False,
    "current_goal": "",
    "nav_calls": 0,
    "charge_calls": 0,
    "x": 2.5,
    "y": 1.8,
    "theta": 0.0
}
if SIMULATE_BATTERY is False:
    state["battery"] = 90

WAYPOINTS = [
    {
        "name": "P1",
        "type": "normal",
        "pose": {"x": 2.5, "y": 1.8, "theta": 0.0}
    },
    {
        "name": "CHARGE",
        "type": "charge",
        "pose": {"x": 0.5, "y": 0.5, "theta": 0.0}
    }
]

# ----------------------------
# BACKGROUND BATTERY LOGIC
# ----------------------------
def battery_simulator():
    while True:
        time.sleep(10)

        if not SIMULATE_BATTERY:
            continue

        if state["charging"]:
            state["battery"] = min(100, state["battery"] + 2)
        else:
            state["battery"] = max(5, state["battery"] - 1)

threading.Thread(target=battery_simulator, daemon=True).start()

# ----------------------------
# API ENDPOINTS
# ----------------------------

@app.route("/reeman/position", methods=["GET"])
def position():
    time.sleep(0.5)
    return jsonify({"waypoints": WAYPOINTS})


@app.route("/cmd/nav_name", methods=["POST"])
def nav_name():
    data = request.json
    state["current_goal"] = data.get("point", "")
    state["nav_calls"] = 0

    if state["current_goal"] == "CHARGE" and SIMULATE_BATTERY:
        state["charging"] = True
        state["charge_calls"] = 0
    else:
        state["charging"] = False

    time.sleep(0.3)
    return jsonify({"status": "accepted"})


@app.route("/reeman/nav_status", methods=["GET"])
def nav_status():
    time.sleep(0.7)
    state["nav_calls"] += 1

    if state["nav_calls"] <= 5:
        return jsonify({
            "goal": state["current_goal"],
            "res": 1,
            "dist": 3.2
        })

    return jsonify({
        "goal": state["current_goal"],
        "res": 3,
        "dist": 0.3
    })


@app.route("/reeman/base_encode", methods=["GET"])
def base_encode():
    time.sleep(0.4)

    if not SIMULATE_BATTERY:
        return jsonify({"battery": state["battery"]})

    if state["charging"]:
        state["charge_calls"] += 1

        if state["charge_calls"] <= 5:
            state["battery"] = min(
               100,
                state["battery"] + (100 - state["battery"]) // (6 - state["charge_calls"])
            )
        else:
            state["battery"] = 100

    return jsonify({"battery": state["battery"]})


@app.route("/cmd/nav", methods=["POST"])
def nav():
    data = request.json
    state["x"] = data.get("x", state["x"])
    state["y"] = data.get("y", state["y"])
    state["theta"] = data.get("theta", state["theta"])
    time.sleep(0.3)
    return jsonify({"status": "rotating"})


@app.route("/reeman/pose", methods=["GET"])
def pose():
    time.sleep(0.5)
    state["theta"] = round(state["theta"], 2)
    return jsonify({
        "x": state["x"],
        "y": state["y"],
        "theta": state["theta"]
    })


# ----------------------------
# START SERVER
# ----------------------------
if __name__ == "__main__":
    print("🚀 Fake Robot API running on http://127.0.0.1:5008")
    app.run(host="0.0.0.0", port=5008)