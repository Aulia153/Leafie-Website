import firebase_admin
from firebase_admin import credentials, auth as admin_auth
import pyrebase

# Inisialisasi Firebase Admin SDK (untuk operasi server, misal: manajemen user)
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

# Konfigurasi untuk Pyrebase (autentikasi user)
firebase_config = {
    "apiKey": "AIzaSyAMLCngjVKhzpoWZ-rJorqcAmy1h48EdJQ",
    "authDomain": "leafie-project.firebaseapp.com",
    "projectId": "leafie-project",
    "storageBucket": "leafie-project.firebasestorage.app",
    "messagingSenderId": "392209039380",
    "appId": "1:392209039380:web:44114ae9fc22f882d96701",
    "databaseURL": ""  # biarkan kosong jika tidak pakai Realtime Database
}

# Inisialisasi Pyrebase untuk login user biasa
firebase = pyrebase.initialize_app(firebase_config)
auth = firebase.auth()  # ini yang kamu import di file login
