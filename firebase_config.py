import firebase_admin
from firebase_admin import credentials, auth

# Ganti dengan path ke file key kamu
cred = credentials.Certificate("serviceAccountKey.json")

# Inisialisasi Firebase Admin SDK
firebase_admin.initialize_app(cred)
