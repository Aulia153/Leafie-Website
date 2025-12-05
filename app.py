import os
import requests
import csv
from datetime import datetime
from io import StringIO
from flask import Flask, render_template, session, redirect, url_for, jsonify, request, Response, flash
from werkzeug.utils import secure_filename

from firebase_config import db 
from klasifikasi_daun import get_classifier

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

# ==== FILE UPLOAD CONFIG ====
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max untuk Flask

# ==== ESP32 CONFIG ====
ESP32_IP = "10.214.26.253"
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

def allowed_file(filename):
    """Cek apakah file extension valid"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==== ROUTES ====
@app.route("/")
def home():
    return render_template("home.html")

@app.route('/lupaPassword', methods=['GET', 'POST'])
def LupaPassword():
    if request.method == 'POST':
        email = request.form.get('identifier')

        try:
            user = db.child("user").order_by_child("identifier").equal_to(email).get().val()
        except Exception as e:
            print("Error cek email:", e)
            flash("Terjadi kesalahan server saat mengakses database.", "error")
            return render_template("lupaPassword.html")

        if not user:
            flash('Email tidak terdaftar. Silakan periksa kembali.', 'error')
            return render_template('lupaPassword.html')

        flash('Kode OTP telah dikirim ke email Anda!', 'success')
        return redirect(url_for('verify_otp'))

    return render_template('lupaPassword.html')

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("auth_bp.login"))

    # --- AMBIL DATA TERBARU DARI FIREBASE ---
    try:
        raw = db.child("sensor").get().val()
        if raw:
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

@app.route("/api/sensor")
def api_sensor():
    try:
        raw = db.child("sensor").get().val()

        if isinstance(raw, dict) and len(raw)==1 and isinstance(list(raw.values())[0], dict):
            reading = list(raw.values())[0]
        else:
            reading = raw or {}

    except:
        reading = {}

    reading.setdefault("temperature", 0)
    reading.setdefault("humidity", 0)
    reading.setdefault("soil_moisture", 0)
    reading.setdefault("timestamp", "")

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

# ==== CAPTURE GAMBAR DARI ESP32 ====
@app.route("/capture_leaf", methods=["POST"])
def capture_leaf():
    try:
        # Ambil gambar dari ESP32
        resp = requests.get(ESP32_CAPTURE_URL, timeout=5)
        if resp.status_code != 200:
            return jsonify({
                "success": False, 
                "message": "Gagal mengambil gambar dari ESP32"
            }), 500

        # Simpan ke file
        path = os.path.join(STATIC_IMG_DIR, "leaf_latest.jpg")
        with open(path, "wb") as f:
            f.write(resp.content)

        # Catat aktivitas di Firebase
        add_activity("Gambar daun berhasil diambil dari ESP32 CAM", type="camera")

        return jsonify({
            "success": True,
            "path": "/static/image/leaf_latest.jpg",
            "message": "Gambar berhasil diambil!"
        })

    except requests.Timeout:
        return jsonify({
            "success": False, 
            "message": "Timeout: ESP32 tidak merespon"
        }), 500
    except requests.ConnectionError:
        return jsonify({
            "success": False, 
            "message": "Koneksi ke ESP32 gagal. Periksa IP address"
        }), 500
    except Exception as e:
        print("Error capture:", e)
        return jsonify({
            "success": False, 
            "message": f"Error: {str(e)}"
        }), 500

# ===============================================
# 1. Upload gambar dari HP/Laptop → langsung prediksi
# ===============================================
@app.route("/upload_leaf", methods=["POST"])
def upload_leaf():
    if 'image' not in request.files:
        return jsonify({"success": False, "message": "Tidak ada file"}), 400

    file = request.files['image']
    if file.filename == '':
        return jsonify({"success": False, "message": "Tidak ada file terpilih"}), 400
    
    if not file.filename.lower().rsplit('.', 1)[1] in ALLOWED_EXTENSIONS:
        return jsonify({"success": False, "message": "Format tidak didukung"}), 400

    # Baca file ke memory dulu (ini cara paling aman & akurat cek ukuran)
    file_bytes = file.read()

    if len(file_bytes) > MAX_UPLOAD_SIZE:
        return jsonify({"success": False, "message": "File terlalu besar (max 5MB)"}), 413

    # Simpan gambar
    save_path = os.path.join(STATIC_IMG_DIR, "leaf_latest.jpg")
    with open(save_path, "wb") as f:
        f.write(file_bytes)

    # Langsung prediksi
    classifier = get_classifier()
    result = classifier.predict(file_bytes)

    if not result["success"]:
        return jsonify({"success": False, "message": "Gagal klasifikasi"}), 500

    return jsonify({
        "success": True,
        "status": result["status"],
        "recommendations": result["recommendations"],
        "confidence": round(result.get("confidence", 0) * 100, 1),
        "image": "/static/image/leaf_latest.jpg"
    })

# ===============================================
# 2. Deteksi ulang gambar yang sudah ada (leaf_latest.jpg)
# ===============================================
@app.route("/api/detect_leaf", methods=["POST"])
def detect_leaf():
    path = os.path.join(STATIC_IMG_DIR, "leaf_latest.jpg")
    if not os.path.exists(path):
        return jsonify({"success": False, "message": "Belum ada foto daun"}), 400

    classifier = get_classifier()
    result = classifier.predict(path)

    if not result["success"]:
        return jsonify({"success": False, "message": "Gagal klasifikasi"}), 500

    return jsonify({
        "success": True,
        "status": result["status"],
        "recommendations": result["recommendations"],
        "image": "/static/image/leaf_latest.jpg",
        "confidence": round(result["confidence"] * 100, 1)
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

# ==== EXPORT CSV ====
@app.route("/export_csv")
def export_csv():
    try:
        data = db.child("activity").get().val()

        if not data:
            return Response("No activity data available", status=404)

        output = StringIO()
        writer = csv.writer(output)

        writer.writerow(["time", "type", "description"])

        for key, item in data.items():
            writer.writerow([
                item.get("time", ""),
                item.get("type", ""),
                item.get("desc", "")
            ])

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