from flask import Flask, render_template, session, redirect, url_for
from routes.auth_login import auth_bp

app = Flask(__name__)
app.secret_key = "rahasia_leafie"
app.register_blueprint(auth_bp)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/lupaPassword')
def lupaPassword():
    return render_template('lupaPassword.html')

@app.route('/verifikasiOTP')
def verifikasiOTP():
    return render_template('verifikasiOTP.html')

@app.route('/resetPss')
def resetPss():
    return render_template('resetPss.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('auth_bp.login'))
    return render_template('dashboard.html')

if __name__ == '__main__':
    app.run(debug=True)
