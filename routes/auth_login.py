from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from firebase_config import auth

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            user = auth.sign_in_with_email_and_password(email, password)
            session['user'] = email
            flash('Login berhasil!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            print(e)
            flash('Login gagal. Periksa email atau password Anda.', 'danger')

    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    session.pop('user', None)
    flash('Anda telah logout.', 'info')
    return redirect(url_for('home'))  # setelah logout, kembali ke landing page
