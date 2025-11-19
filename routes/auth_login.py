from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from firebase_config import auth  # Pyrebase

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Jika sudah login, langsung ke dashboard
    if "user" in session:
        return redirect(url_for("dashboard"))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            # Login memakai Pyrebase
            user = auth.sign_in_with_email_and_password(email, password)

            # Ambil ID Token agar session valid & tidak diblok browser
            id_token = user['idToken']
            refresh_token = user['refreshToken']

            # SIMPAN SESSION LENGKAP
            session['user'] = {
                "email": email,
                "id_token": id_token,
                "refresh_token": refresh_token,
            }

            flash('✅ Login berhasil!', 'success')
            return redirect(url_for('dashboard'))

        except Exception as e:
            print("Login error:", e)
            flash('❌ Login gagal. Periksa email atau password Anda.', 'danger')

    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()  # jauh lebih aman
    flash('🚪 Anda telah logout.', 'info')
    return redirect(url_for('home'))
