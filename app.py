import os
import random
import requests
import csv
from datetime import datetime
from io import StringIO
from flask import Flask, render_template, session, redirect, url_for, jsonify, request, Response
from werkzeug.utils import secure_filename

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
ESP32_IP = "192.168.74.253"
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

# ==== ROUTES ====
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("auth_bp.login"))

    # --- AMBIL DATA TERBARU DARI FIREBASE ---
    try:
        raw = db.child("sensor").get().val()
        if raw:
            # raw = { id: {...sensor data...} }
            reading = raw
        else:
            reading = {
                "temperature": "-",
                "humidity": "-",
                "soil_moisture": "-",
                "timestamp": "-"
            }
    except Exception as e:
        print("Warning: gagal mengambil data dari Firebase:", e)
        reading = {
            "temperature": "-",
            "humidity": "-",
            "soil_moisture": "-",
            "timestamp": "-"
        }

    # --- AMBIL ACTIVITY ---
    try:
        raw = db.child("activity").get().val()
        if raw:
            items = sorted(raw.items(), key=lambda kv: kv[1].get("time", ""))
            activity_list = [v for k, v in items]
        else:
            activity_list = []
    except:
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
    try:
        raw = db.child("sensor").get().val()

        # Jika raw adalah {randomKey: {...}}
        if isinstance(raw, dict) and len(raw)==1 and isinstance(list(raw.values())[0], dict):
            reading = list(raw.values())[0]
        else:
            reading = raw or {}

    except:
        reading = {}

    # Pastikan semua field ada
    reading.setdefault("temperature", 0)
    reading.setdefault("humidity", 0)
    reading.setdefault("soil_moisture", 0)
    reading.setdefault("timestamp", "")

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

@app.route("/api/camera", methods=["POST"])
def api_camera():
    current = get_state("camera")
    new = "OFF" if current == "ON" else "ON"
    set_state("camera", new)
    add_activity(f"Kamera diubah menjadi {new}", type="camera")
    return jsonify({"camera": new})

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
            "path": "/static/gambar/leaf_latest.jpg"
        })

    except Exception as e:
        print("Error capture:", e)
        return jsonify({"success": False}), 500

# ==== UPLOAD GAMBAR DAUN ====
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/upload_leaf", methods=["POST"])
def upload_leaf():
    try:
        if "image" not in request.files:
            return jsonify({"success": False, "message": "Tidak ada file dikirim"}), 400

        file = request.files["image"]
        if file.filename == "":
            return jsonify({"success": False, "message": "Nama file kosong"}), 400

        if not allowed_file(file.filename):
            return jsonify({"success": False, "message": "Format file tidak didukung"}), 400

        if request.content_length and request.content_length > MAX_UPLOAD_SIZE:
            return jsonify({"success": False, "message": "File terlalu besar (max 5 MB)"}), 413

        filename = "leaf_latest.jpg"
        save_path = os.path.join(STATIC_IMG_DIR, secure_filename(filename))
        file.save(save_path)

        add_activity("Gambar daun di-upload manual oleh user", type="camera")

        return jsonify({"success": True, "message": "Upload berhasil", "path": "/static/gambar/leaf_latest.jpg"})
    except Exception as e:
        print("Upload error:", e)
        return jsonify({"success": False, "message": "Terjadi kesalahan server"}), 500


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
        "image": "/static/gambar/leaf_latest.jpg"
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
