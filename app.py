from flask import Flask, jsonify, request, redirect, send_from_directory
import requests
from flask_cors import CORS
import os

app = Flask(__name__, static_folder="static")
CORS(app, resources={r"/*": {"origins": "*"}})

WDA_URL = "http://127.0.0.1:8100"
MJPEG_STREAM_URL = "http://127.0.0.1:9100"  # MJPEG stream forwarded by iProxy

session_id = None

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, "index.html")

@app.route('/start_session', methods=['POST'])
def start_session():
    global session_id
    capabilities = {
        "capabilities": {
            "alwaysMatch": {},
            "firstMatch": [{}]
        }
    }
    try:
        response = requests.post(f"{WDA_URL}/session", json=capabilities)
        if response.status_code == 200:
            session_id = response.json().get('value', {}).get('sessionId')
            return jsonify({"status": "success", "session_id": session_id})
        else:
            return jsonify({"status": "error", "message": response.text}), response.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/end_session', methods=['POST'])
def end_session():
    global session_id
    if not session_id:
        return jsonify({"status": "error", "message": "No active session"}), 400
    try:
        requests.delete(f"{WDA_URL}/session/{session_id}")
        session_id = None
        return jsonify({"status": "success", "message": "Session ended"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/tap', methods=['POST'])
def tap():
    global session_id
    if not session_id:
        return jsonify({"status": "error", "message": "No active session"}), 400
    try:
        data = request.json
        x, y = data.get('x'), data.get('y')
        
        # Validate coordinates are provided
        if x is None or y is None:
            return jsonify({"status": "error", "message": "Missing x or y coordinates"}), 400
        
        # Get device dimensions for validation
        device_info_response = requests.get(f"{WDA_URL}/status")
        device_width, device_height = 375, 812  # defaults
        if device_info_response.status_code == 200:
            data_info = device_info_response.json()
            os_info = data_info.get("value", {}).get("os", {})
            if "width" in os_info and "height" in os_info:
                device_width = os_info["width"]
                device_height = os_info["height"]
        
        # Validate coordinates are within device bounds
        if not (0 <= x < device_width and 0 <= y < device_height):
            return jsonify({
                "status": "error", 
                "message": f"Coordinates ({x}, {y}) out of bounds for device ({device_width}x{device_height})"
            }), 400
        
        actions = {
            "actions": [
                {
                    "type": "pointer",
                    "id": "finger1",
                    "parameters": { "pointerType": "touch" },
                    "actions": [
                        { "type": "pointerMove", "x": x, "y": y },
                        { "type": "pointerDown" },
                        { "type": "pointerUp" }
                    ]
                }
            ]
        }
        response = requests.post(f"{WDA_URL}/session/{session_id}/actions", json=actions)
        return jsonify(response.json())
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stream')
def stream():
    try:
        return redirect(MJPEG_STREAM_URL)
    except Exception as e:
        return jsonify({"error": "Failed to connect to MJPEG stream", "details": str(e)}), 500

@app.route('/device_info', methods=['GET'])
def device_info():
    try:
        response = requests.get(f"{WDA_URL}/status")
        if response.status_code == 200:
            data = response.json()
            device_info = {
                "width": 375,
                "height": 812
            }
            os_info = data.get("value", {}).get("os", {})
            if "width" in os_info and "height" in os_info:
                device_info["width"] = os_info["width"]
                device_info["height"] = os_info["height"]
            return jsonify(device_info)
        else:
            return jsonify({"error": "Could not fetch device info"}), 500
    except Exception as e:
        return jsonify({"error": f"Failed to connect to WDA: {str(e)}"}), 500

if __name__ == "__main__":
    if not os.path.exists("static"):
        os.makedirs("static")
    if not os.path.exists(os.path.join("static", "index.html")):
        raise FileNotFoundError("Ensure 'index.html' exists in the 'static' folder.")
    app.run(host="0.0.0.0", port=5000)
