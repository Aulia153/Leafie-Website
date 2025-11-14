import os
import random
import requests
from datetime import datetime
from flask import Flask, render_template, session, redirect, url_for, jsonify, request

from firebase_config import db

# ==== FLASK ====
app = Flask(__name__)
app.secret_key = "rahasia_leafie"

# ==== REGISTER BLUEPRINTS ====
from routes.auth_login import auth_bp
from routes.forgot_password import forgot_bp

app.register_blueprint(auth_bp)
app.register_blueprint(forgot_bp)

# ==== STATIC FOLDER HANDLING ====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_IMG_DIR = os.path.join(BASE_DIR, "static", "image")
os.makedirs(STATIC_IMG_DIR, exist_ok=True)

# ==== ESP32 CONFIG ====
ESP32_IP = "192.168.1.50"
ESP32_STREAM_URL = f"http://{ESP32_IP}:81/stream"
ESP32_CAPTURE_URL = f"http://{ESP32_IP}/capture"

# ==== FIREBASE HELPERS ====
def get_state(key):
    res = db.child("settings").child(key).get().val()
    return res if res else "OFF"

def set_state(key, value):
    db.child("settings").child(key).set(value)

def add_activity(msg):
    """
    Simpan activity dengan keys: time, desc
    Template mengakses log.time dan log.desc
    """
    db.child("activity").push({
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "desc": msg
    })

def generate_reading():
    """
    Menghasilkan reading dengan field 'soil_moisture' agar sesuai dengan
    dashboard.js dan dashboard.html
    """
    return {
        "temperature": round(random.uniform(25, 31), 1),
        "humidity": random.randint(50, 85),
        "soil_moisture": random.randint(45, 80),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# ==== ROUTES ====
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("auth_bp.login"))

    # generate dummy reading and simpan (sama dengan behavior sebelumnya)
    reading = generate_reading()
    try:
        db.child("readings").push(reading)
    except Exception as e:
        # jangan crash bila koneksi firebase bermasalah
        print("Warning: gagal push reading ke Firebase:", e)

    # ambil activity terakhir (urut berdasarkan time)
    activity_data = {}
    try:
        # ambil semua lalu sortir berdasarkan time (string 'YYYY-MM-DD HH:MM:SS' -> lexicographic works)
        raw = db.child("activity").get().val()
        if raw:
            # raw is dict {id: {time:..., desc:...}, ...}
            items = sorted(raw.items(), key=lambda kv: kv[1].get("time", ""))
            activity_list = [v for k, v in items]  # list of {time, desc}
        else:
            activity_list = []
    except Exception as e:
        print("Warning: gagal baca activity dari Firebase:", e)
        activity_list = []

    return render_template(
        "dashboard.html",
        data=reading,
        pump_state=get_state("pump"),
        camera_state=get_state("camera"),
        activity=activity_list,
        esp32_stream_url=ESP32_STREAM_URL
    )


@app.route("/api/sensor")
def api_sensor():
    reading = generate_reading()
    try:
        db.child("readings").push(reading)
    except Exception as e:
        print("Warning: gagal push reading ke Firebase:", e)

    reading["pump"] = get_state("pump")
    reading["camera"] = get_state("camera")
    return jsonify(reading)


@app.route("/api/pump", methods=["POST"])
def api_pump():
    current = get_state("pump")
    new = "OFF" if current == "ON" else "ON"
    set_state("pump", new)
    add_activity(f"Pompa diubah menjadi {new}")
    return jsonify({"pump": new})


@app.route("/capture_leaf", methods=["POST"])
def capture_leaf():
    try:
        resp = requests.get(ESP32_CAPTURE_URL, timeout=5)
        if resp.status_code != 200:
            return jsonify({"success": False}), 500

        path = os.path.join(STATIC_IMG_DIR, "leaf_latest.jpg")
        with open(path, "wb") as f:
            f.write(resp.content)

        add_activity("Gambar daun berhasil diambil")
        return jsonify({"success": True, "path": "/static/image/leaf_latest.jpg"})
    except Exception as e:
        print("Error capture:", e)
        return jsonify({"success": False}), 500


# Tambahan kecil: route untuk mengubah camera state (opsional)
@app.route("/api/camera", methods=["POST"])
def api_camera():
    current = get_state("camera")
    new = "OFF" if current == "ON" else "ON"
    set_state("camera", new)
    add_activity(f"Kamera diubah menjadi {new}")
    return jsonify({"camera": new})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)