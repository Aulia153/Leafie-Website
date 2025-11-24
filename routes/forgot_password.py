from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from firebase_config import auth                  # Pyrebase
from firebase_config import admin_auth       # Admin SDK

import random, time, smtplib
from email.mime.text import MIMEText

forgot_bp = Blueprint('forgot_bp', __name__)

# Temporary OTP storage (gunakan DB utk production)
otp_store = {}

# === 1️⃣ LUPA PASSWORD ===
@forgot_bp.route('/lupaPassword', methods=['GET', 'POST'])
def lupa_password():
    if request.method == 'POST':
        email = request.form.get('email')

        if not email:
            flash('Email wajib diisi.', 'warning')
            return render_template('lupaPassword.html')

        # 🔍 Cek email di Firebase via Admin SDK
        try:
            admin_auth.get_user_by_email(email)
        except admin_auth.UserNotFoundError:
            flash('❌ Email tidak terdaftar.', 'danger')
            return render_template('lupaPassword.html')
        except Exception as e:
            print("Error cek email:", e)
            flash("Terjadi kesalahan server.", "danger")
            return render_template('lupaPassword.html')

        # Buat OTP
        otp = str(random.randint(100000, 999999))
        expiry = time.time() + 300  # 5 menit
        otp_store[email] = {"otp": otp, "expiry": expiry}

        # Kirim OTP ke email
        try:
            send_email(email, otp)
            flash("Kode OTP telah dikirim ke email Anda.", "info")
        except Exception as e:
            flash("Gagal mengirim OTP.", "danger")
            print("Email error:", e)
            return render_template('lupaPassword.html')

        session["reset_email"] = email
        return redirect(url_for("forgot_bp.verifikasi_otp"))

    return render_template("lupaPassword.html")


# === 2️⃣ VERIFIKASI OTP ===
@forgot_bp.route('/verifikasiOTP', methods=['GET', 'POST'])
def verifikasi_otp():
    email = session.get("reset_email")
    if not email:
        flash("Sesi habis. Ulangi proses.", "warning")
        return redirect(url_for("forgot_bp.lupa_password"))

    if request.method == 'POST':
        otp_input = request.form.get("otp")
        data = otp_store.get(email)

        if not data:
            flash("OTP tidak ditemukan.", "danger")
            return redirect(url_for("forgot_bp.lupa_password"))

        if data["otp"] == otp_input and time.time() < data["expiry"]:
            session["otp_verified"] = True
            flash("OTP benar! Silakan atur password baru.", "success")
            return redirect(url_for("forgot_bp.reset_password"))
        else:
            flash("OTP salah atau kadaluarsa.", "danger")

    return render_template("verifikasiOTP.html")


# === 3️⃣ RESET PASSWORD ===
@forgot_bp.route('/resetPassword', methods=['GET', 'POST'])
def reset_password():
    email = session.get("reset_email")
    verified = session.get("otp_verified")

    if not email or not verified:
        flash("Akses tidak sah.", "warning")
        return redirect(url_for("forgot_bp.lupa_password"))

    if request.method == 'POST':
        new_password = request.form.get("password")

        if not new_password:
            flash("Password wajib diisi.", "warning")
            return render_template("resetPss.html")

        try:
            # Kirim link reset password default Firebase
            auth.send_password_reset_email(email)
            flash("Tautan reset password telah dikirim ke email Anda.", "info")

            session.clear()
            return redirect(url_for("auth_bp.login"))
        except Exception as e:
            print("Error reset password:", e)
            flash("Gagal mengirim tautan reset password.", "danger")

    return render_template("resetPss.html")


# === 4️⃣ RESEND OTP ===
@forgot_bp.route('/resend_otp', methods=['POST'])
def resend_otp():
    email = session.get("reset_email")

    if not email:
        return {"status": "error", "message": "Sesi tidak ditemukan"}, 400

    otp = str(random.randint(100000, 999999))
    otp_store[email] = {"otp": otp, "expiry": time.time() + 300}

    try:
        send_email(email, otp)
        return {"status": "success", "message": "OTP baru dikirim"}
    except Exception as e:
        print("Error:", e)
        return {"status": "error", "message": "Gagal mengirim email"}, 500


# === 5️⃣ KIRIM EMAIL ===
def send_email(to_email, otp):
    sender = "hanntok2802@gmail.com"
    password = "uelj bbid eymw hnwl"  # Gmail App Password saja

    msg = MIMEText(f"Kode OTP Anda: {otp}\nBerlaku 5 menit.")
    msg["Subject"] = "Reset Password - Leafie"
    msg["From"] = sender
    msg["To"] = to_email

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender, password)
        server.send_message(msg)

    print(f"[EMAIL TERKIRIM] OTP {otp} → {to_email}")
