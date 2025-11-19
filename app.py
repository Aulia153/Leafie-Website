import os
import random
import requests
import csv
from datetime import datetime
from io import StringIO
from flask import Flask, render_template, session, redirect, url_for, jsonify, request, Response

from firebase_config import db   # <-- pastikan ini adalah client Realtime Database (pyrebase/etc.)

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
ESP32_IP = "192.168.100.201"
ESP32_STREAM_URL = f"http://{ESP32_IP}:81/stream"
ESP32_CAPTURE_URL = f"http://{ESP32_IP}/capture"

# ==== FIREBASE HELPERS (Realtime DB) ====
def get_state(key):
    try:
        res = db.child("settings").child(key).get().val()
        return res if res is not None else "OFF"
    except Exception:
        return "OFF"

def set_state(key, value):
    db.child("settings").child(key).set(value)

def add_activity(message, type="general"):
    """
    Simpan activity ke Realtime DB dengan fields: time, desc, type
    """
    payload = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "desc": message,
        "type": type
    }
    try:
        db.child("activity").push(payload)
    except Exception as e:
        print("Warning: gagal push activity ke Firebase:", e)


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

    # ambil sensor palsu sekali saja (untuk awal load)
    reading = generate_reading()   # <- jangan pass None ke template

    # ambil activity dari firebase (Realtime DB)
    try:
        raw = db.child("activity").get().val()
        if raw:
            # raw is a dict of id -> record
            # convert to list and sort by time descending (latest dulu)
            items = sorted(raw.items(), key=lambda kv: kv[1].get("time", ""), reverse=True)
            activity_list = [v for k, v in items]
        else:
            activity_list = []
    except Exception as e:
        print("Warning: gagal ambil activity:", e)
        activity_list = []

    return render_template(
        "dashboard.html",
        data=reading,
        pump_state=get_state("pump"),
        camera_state=get_state("camera"),
        activity=activity_list,
        esp32_stream_url=ESP32_STREAM_URL
    )

# ==== GLOBAL LAST SENSOR STATE ====
last_temp = None
last_soil = None

@app.route("/api/sensor")
def api_sensor():
    global last_temp, last_soil

    # ambil data sensor
    reading = generate_reading()
    temperature = reading["temperature"]
    soil = reading["soil_moisture"]

    try:
        # simpan reading ke firebase (realtime)
        db.child("readings").push(reading)

        # ========== LOGGING KONDISI BERUBAH ==========
        if last_temp != temperature or last_soil != soil:
            add_activity(
                f"Sensor berubah → Suhu: {temperature}°C, Kelembapan Tanah: {soil}%",
                type="sensor"
            )

        # update nilai terakhir
        last_temp = temperature
        last_soil = soil

    except Exception as e:
        print("Warning: gagal push reading ke Firebase:", e)

    # tambahkan state
    reading["pump"] = get_state("pump")
    reading["camera"] = get_state("camera")

    return jsonify(reading)


@app.route("/api/pump", methods=["POST"])
def api_pump():
    current = get_state("pump")
    new = "OFF" if current == "ON" else "ON"
    set_state("pump", new)
    add_activity(f"Pompa diubah menjadi {new}", type="pump")
    return jsonify({"pump": new})


@app.route("/capture_leaf", methods=["POST"])
def capture_leaf():
    try:
        # ambil gambar dari ESP32
        resp = requests.get(ESP32_CAPTURE_URL, timeout=5)
        if resp.status_code != 200:
            return jsonify({"success": False}), 500

        # simpan ke file
        path = os.path.join(STATIC_IMG_DIR, "leaf_latest.jpg")
        with open(path, "wb") as f:
            f.write(resp.content)

        # catat aktivitas di Firebase (camera/capture)
        add_activity("Gambar daun berhasil diambil", type="camera")

        return jsonify({
            "success": True,
            "path": "/static/image/leaf_latest.jpg"
        })

    except Exception as e:
        print("Error capture:", e)
        return jsonify({"success": False}), 500


@app.route("/api/camera", methods=["POST"])
def api_camera():
    current = get_state("camera")
    new = "OFF" if current == "ON" else "ON"
    set_state("camera", new)
    add_activity(f"Kamera diubah menjadi {new}", type="camera")
    return jsonify({"camera": new})


@app.route("/api/detect_leaf", methods=["POST"])
def detect_leaf():
    latest_img_path = os.path.join(STATIC_IMG_DIR, "leaf_latest.jpg")

    if not os.path.exists(latest_img_path):
        return jsonify({
            "success": False,
            "message": "Foto daun belum tersedia. Ambil foto dulu."
        }), 400

    # --- AI DETEKSI DUMMY ---
    kondisi_tidak_sehat = [
        "Daun Menguning — indikasi kekurangan nitrogen.",
        "Terdeteksi Bercak Coklat — potensi jamur.",
        "Daun Layu — kekurangan air.",
        "Daun Menghitam — terlalu banyak cahaya matahari."
    ]

    kondisi_sehat = [
        "Daun Sehat — tidak ditemukan gejala penyakit."
    ]

    # Random detection
    is_healthy = random.choice([True, False])

    if is_healthy:
        result = random.choice(kondisi_sehat)
        message = "Daun tampak sehat! Pertahankan perawatan terbaikmu 🌿"
        status = "HEALTHY"
    else:
        result = random.choice(kondisi_tidak_sehat)
        message = "⚠️ Daun terdeteksi tidak sehat, segera lakukan pengecekan!"
        status = "UNHEALTHY"

    # Simpan aktivitas ke Firebase (type leaf)
    add_activity(f"Hasil deteksi daun: {result}", type="leaf")

    return jsonify({
        "success": True,
        "status": status,
        "result": result,
        "message": message,
        "image": "/static/image/leaf_latest.jpg"
    })


@app.route("/export_csv")
def export_csv():
    try:
        # ambil semua activity dari realtime db
        data = db.child("activity").get().val()

        if not data:
            return Response("No activity data available", status=404)

        # buffer CSV
        output = StringIO()
        writer = csv.writer(output)

        # header CSV (include type)
        writer.writerow(["time", "type", "description"])

        # isi data activity
        for key, item in data.items():
            writer.writerow([
                item.get("time", ""),
                item.get("type", ""),
                item.get("desc", "")
            ])

        # buat respon file
        response = Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=activity.csv"
            }
        )
        return response

    except Exception as e:
        print("CSV Export Error:", e)
        return Response("Error exporting CSV", status=500)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
