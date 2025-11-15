import firebase_admin
from firebase_admin import credentials, auth as admin_auth
import pyrebase

# Inisialisasi Firebase Admin SDK
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred)

# Konfigurasi Pyrebase
firebase_config = {
    "apiKey": "AIzaSyAMLCngjVKhzpoWZ-rJorqcAmy1h48EdJQ",
    "authDomain": "leafie-project.firebaseapp.com",
    "projectId": "leafie-project",
    "storageBucket": "leafie-project.firebasestorage.app",
    "messagingSenderId": "392209039380",
    "appId": "1:392209039380:web:44114ae9fc22f882d96701",
    "databaseURL": "https://leafie-project-default-rtdb.firebaseio.com" 
}

firebase = pyrebase.initialize_app(firebase_config)

# Untuk login user
auth = firebase.auth()

db = firebase.database()
