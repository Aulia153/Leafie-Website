from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from firebase_config import auth
import random, time, smtplib
from email.mime.text import MIMEText

# Buat blueprint
forgot_bp = Blueprint('forgot_bp', __name__)

# Simpan OTP di memori sementara (sementara, sebaiknya pakai DB di produksi)
otp_store = {}

# === 1️⃣ LUPA PASSWORD ===
@forgot_bp.route('/lupaPassword', methods=['GET', 'POST'])
def lupa_password():
    if request.method == 'POST':
        email = request.form.get('email')

        if not email:
            flash('Email wajib diisi.', 'warning')
            return render_template('lupaPassword.html')

        # 🔍 Cek apakah email terdaftar di Firebase
        try:
            user = auth.get_user_by_email(email)
        except Exception as e:
            print("Email tidak ditemukan di Firebase:", e)
            flash('❌ Email tidak terdaftar. Silakan gunakan email yang valid.', 'danger')
            return render_template('lupaPassword.html')

        # ✅ Buat OTP & simpan
        otp = str(random.randint(100000, 999999))
        expiry = time.time() + 300  # 5 menit
        otp_store[email] = {'otp': otp, 'expiry': expiry}

        # ✅ Kirim OTP via email
        try:
            send_email(email, otp)
            flash('✅ Kode OTP telah dikirim ke email Anda.', 'info')
        except Exception as e:
            flash(f'⚠️ Gagal mengirim email OTP: {e}', 'danger')
            print("Error kirim email:", e)
            return render_template('lupaPassword.html')

        session['reset_email'] = email
        return redirect(url_for('forgot_bp.verifikasi_otp'))

    return render_template('lupaPassword.html')

# === 2️⃣ VERIFIKASI OTP ===
@forgot_bp.route('/verifikasiOTP', methods=['GET', 'POST'])
def verifikasi_otp():
    email = session.get('reset_email')
    if not email:
        flash('Sesi telah berakhir. Silakan ulangi proses.', 'warning')
        return redirect(url_for('forgot_bp.lupa_password'))

    if request.method == 'POST':
        otp_input = request.form.get('otp')
        data = otp_store.get(email)

        if not data:
            flash('OTP tidak ditemukan. Silakan kirim ulang.', 'danger')
            return redirect(url_for('forgot_bp.lupa_password'))

        if data['otp'] == otp_input and time.time() < data['expiry']:
            session['otp_verified'] = True
            flash('OTP benar! Silakan atur password baru.', 'success')
            return redirect(url_for('forgot_bp.reset_password'))
        else:
            flash('OTP salah atau sudah kadaluarsa.', 'danger')

    return render_template('verifikasiOTP.html')


# === 3️⃣ RESET PASSWORD ===
@forgot_bp.route('/resetPassword', methods=['GET', 'POST'])
def reset_password():
    email = session.get('reset_email')
    verified = session.get('otp_verified')

    if not email or not verified:
        flash('Akses tidak sah. Silakan ulangi dari awal.', 'warning')
        return redirect(url_for('forgot_bp.lupa_password'))

    if request.method == 'POST':
        new_pass = request.form.get('password')
        if not new_pass:
            flash('Password baru wajib diisi.', 'warning')
            return render_template('resetPss.html')

        try:
            # Firebase hanya mendukung kirim tautan reset password (bukan ubah langsung)
            auth.send_password_reset_email(email)
            flash('Tautan reset password telah dikirim ke email Anda.', 'info')
            session.clear()
            return redirect(url_for('auth_bp.login'))
        except Exception as e:
            print('Error Firebase:', e)
            flash('Gagal mengatur ulang password. Coba lagi.', 'danger')

    return render_template('resetPss.html')

# fungsi resend_otp
@forgot_bp.route('/resend_otp', methods=['POST'])
def resend_otp():
    email = session.get('reset_email')
    if not email:
        return {"status": "error", "message": "Sesi tidak ditemukan"}, 400

    if email not in otp_store:
        return {"status": "error", "message": "OTP tidak ditemukan"}, 400

    otp = str(random.randint(100000, 999999))
    otp_store[email] = {'otp': otp, 'expiry': time.time() + 300}

    try:
        send_email(email, otp)
        return {"status": "success", "message": "OTP baru dikirim"}
    except Exception as e:
        print("Error:", e)
        return {"status": "error", "message": "Gagal mengirim email"}, 500


# === 4️⃣ FUNGSI KIRIM EMAIL OTP ===
def send_email(to_email, otp):
    sender = "hanntok2802@gmail.com"
    password = "uelj bbid eymw hnwl"  # gunakan App Password Gmail (bukan password biasa)

    msg = MIMEText(f"Kode OTP Anda adalah {otp}. Berlaku selama 5 menit.")
    msg["Subject"] = "Reset Password - Leafie"
    msg["From"] = sender
    msg["To"] = to_email
    
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
        print(f"[✅ EMAIL TERKIRIM] ke {to_email} — OTP: {otp}")
    except Exception as e:
        print("[❌ GAGAL KIRIM EMAIL]:", e)
        raise e  # biar error bisa ditangkap di route