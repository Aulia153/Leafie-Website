import os
import random
import sqlite3
import cv2
import atexit
from datetime import datetime
from flask import (
    Flask, Response, render_template, session, redirect,
    url_for, jsonify, request, g, send_file
)
from routes.auth_login import auth_bp
from routes.forgot_password import forgot_bp
from firebase_config import auth


# ==============================
# 🔹 SETUP DASAR
# ==============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "leafie.db")
STATIC_IMG_DIR = os.path.join(BASE_DIR, "static", "image")
os.makedirs(STATIC_IMG_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = "rahasia_leafie"
app.register_blueprint(auth_bp)
app.register_blueprint(forgot_bp)


# ==============================
# 🔹 DATABASE
# ==============================
def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)
        db = g._database = sqlite3.connect(DB_PATH, check_same_thread=False)
        db.row_factory = sqlite3.Row
    return db


def init_db():
    db = get_db()
    cur = db.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        temperature REAL NOT NULL,
        humidity INTEGER NOT NULL,
        soil_moisture INTEGER NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        k TEXT PRIMARY KEY,
        v TEXT
    );
    """)

    cur.execute("INSERT OR IGNORE INTO settings(k, v) VALUES ('pump', 'OFF');")
    cur.execute("INSERT OR IGNORE INTO settings(k, v) VALUES ('camera', 'OFF');")
    db.commit()


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


# ==============================
# 🔹 UTILITAS DATA SENSOR
# ==============================
def generate_reading():
    """Simulasi data sensor yang realistis"""
    temp = round(random.uniform(25.0, 31.0), 1)
    humidity = random.randint(50, 85)
    soil = random.randint(45, 80)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "timestamp": ts,
        "temperature": temp,
        "humidity": humidity,
        "soil_moisture": soil
    }


def save_reading(reading):
    db = get_db()
    db.execute("""
        INSERT INTO readings(timestamp, temperature, humidity, soil_moisture)
        VALUES (?, ?, ?, ?)
    """, (reading["timestamp"], reading["temperature"], reading["humidity"], reading["soil_moisture"]))
    db.commit()


def get_latest_reading():
    cur = get_db().cursor()
    cur.execute("SELECT * FROM readings ORDER BY id DESC LIMIT 1")
    row = cur.fetchone()
    return dict(row) if row else None


def get_history(limit=50):
    cur = get_db().cursor()
    cur.execute("SELECT * FROM readings ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    return [dict(r) for r in rows[::-1]]


def get_state(key):
    cur = get_db().cursor()
    cur.execute("SELECT v FROM settings WHERE k=?", (key,))
    r = cur.fetchone()
    return r["v"] if r else "OFF"


def set_state(key, value):
    db = get_db()
    db.execute("INSERT OR REPLACE INTO settings(k, v) VALUES (?, ?)", (key, value))
    db.commit()


# ==============================
# 🔹 INISIALISASI DATABASE
# ==============================
with app.app_context():
    init_db()


# ==============================
# 🔹 ROUTES UTAMA
# ==============================
@app.route("/")
def home():
    return render_template("home.html")


@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/lupaPassword")
def lupaPassword():
    return render_template("lupaPassword.html")


@app.route("/verifikasiOTP")
def verifikasiOTP():
    return render_template("verifikasiOTP.html")


@app.route("/resetPss")
def resetPss():
    return render_template("resetPss.html")


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("auth_bp.login"))

    latest = get_latest_reading()
    if not latest:
        latest = generate_reading()
        save_reading(latest)

    return render_template(
        "dashboard.html",
        data=latest,
        pump_state=get_state("pump"),
        camera_state=get_state("camera"),
        activity=[]  # jika mau ambil aktivitas dari DB, ubah di sini
    )


# ==============================
# 🔹 API ENDPOINTS
# ==============================
@app.route("/api/sensor", methods=["GET"])
def api_sensor():
    """API pembaruan data sensor"""
    reading = generate_reading()
    save_reading(reading)
    reading["pump_status"] = get_state("pump")
    reading["camera_status"] = get_state("camera")
    return jsonify(reading)


@app.route("/api/history", methods=["GET"])
def api_history():
    limit = int(request.args.get("limit", 50))
    return jsonify(get_history(limit))


@app.route("/api/pump", methods=["POST"])
def api_pump():
    data = request.get_json() or {}
    action = data.get("action", "TOGGLE").upper()
    current = get_state("pump")
    new = "OFF" if current == "ON" else "ON" if action == "TOGGLE" else action
    set_state("pump", new)
    return jsonify({"pump": new})


@app.route("/api/camera", methods=["POST"])
def api_camera():
    data = request.get_json() or {}
    action = data.get("action", "TOGGLE").upper()
    current = get_state("camera")
    new = "OFF" if current == "ON" else "ON" if action == "TOGGLE" else action
    set_state("camera", new)
    return jsonify({"camera": new})


@app.route("/api/export", methods=["GET"])
def api_export():
    """Ekspor data sensor ke CSV"""
    import csv
    from io import StringIO
    rows = get_history(1000)
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(["timestamp", "temperature", "humidity", "soil_moisture"])
    for r in rows:
        writer.writerow([r["timestamp"], r["temperature"], r["humidity"], r["soil_moisture"]])
    output = si.getvalue()
    return app.response_class(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=leafie_readings.csv"},
    )

# ==============================
# 🔹 KAMERA & STREAMING
# ==============================
# Inisialisasi kamera (webcam default). Bisa gagal jika device tidak tersedia.
def create_camera(index=0):
    try:
        cam = cv2.VideoCapture(index)
        if not cam.isOpened():
            cam.release()
            return None
        return cam
    except Exception:
        return None

# single camera instance (dipakai untuk stream & deteksi sederhana)
camera = create_camera(0)

def gen_frames():
    """Generator untuk streaming MJPEG."""
    if camera is None:
        return

    try:
        while True:
            success, frame = camera.read()
            if not success:
                break
            # resize optional: frame = cv2.resize(frame, (640, 480))
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    except GeneratorExit:
        # normal saat client disconnect
        pass
    except Exception as e:
        app.logger.error("Error gen_frames: %s", e)

@app.route('/video_feed')
def video_feed():
    # Jika kamera OFF menurut setting, kirim gambar placeholder
    if get_state("camera") == "OFF" or camera is None:
        placeholder = os.path.join(STATIC_IMG_DIR, "camera_off.png")
        if os.path.exists(placeholder):
            return send_file(placeholder, mimetype='image/png')
        else:
            return ("", 404)
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ==============================
# 🔹 DETEKSI DAUN
# ==============================
@app.route('/detect_leaf', methods=['POST'])
def detect_leaf():
    """
    Ambil frame terbaru dari kamera (jika ada dan ON), jalankan deteksi sederhana
    berdasarkan rasio warna hijau, simpan gambar hasil, dan kembalikan status + url.
    """
    try:
        img = None
        # Ambil frame dari camera instance jika ON dan tersedia
        if get_state("camera") == "ON" and camera is not None:
            success, frame = camera.read()
            if success:
                img = frame.copy()

        # Fallback ke sample image
        if img is None:
            sample_path = os.path.join(STATIC_IMG_DIR, "sample_leaf.jpg")
            if not os.path.exists(sample_path):
                return jsonify({"status": "error", "message": "Sample image tidak ditemukan."}), 500
            img = cv2.imread(sample_path)

        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        lower = (35, 40, 40)
        upper = (90, 255, 255)
        mask = cv2.inRange(hsv, lower, upper)
        green_ratio = float((mask > 0).sum()) / (mask.size)

        status = "Sehat" if green_ratio > 0.30 else "Sakit"

        display = img.copy()
        text = f"{status} ({green_ratio*100:.1f}%)"
        color = (0, 255, 0) if status == "Sehat" else (0, 0, 255)
        cv2.putText(display, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2, cv2.LINE_AA)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"detected_{ts}.jpg"
        out_path = os.path.join(STATIC_IMG_DIR, filename)
        cv2.imwrite(out_path, display)

        image_url = url_for('static', filename=f"image/{filename}")

        app.logger.info(f"Deteksi daun: {status} ({green_ratio*100:.1f}%) saved: {filename}")

        return jsonify({
            "status": status,
            "green_ratio": green_ratio,
            "image_url": image_url
        })
    except Exception as e:
        app.logger.exception("Error detect_leaf:")
        return jsonify({"status": "error", "message": str(e)}), 500

# ==============================
# 🔹 SHUTDOWN / CLEANUP
# ==============================
def cleanup():
    try:
        if camera is not None:
            camera.release()
            app.logger.info("Camera released on shutdown.")
    except Exception as e:
        app.logger.error("Error releasing camera: %s", e)

atexit.register(cleanup)

# ==============================
# 🔹 MAIN
# ==============================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
