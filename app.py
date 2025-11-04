from flask import Flask, render_template

app = Flask(__name__)

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

if __name__ == '__main__':
    app.run(debug=True)
