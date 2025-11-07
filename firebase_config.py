import pyrebase

firebaseConfig = {
    "apiKey": "AIzaSyAMLCngjVKhzpoWZ-rJorqcAmy1h48EdJQ",
    "authDomain": "leafie-project.firebaseapp.com",
    "projectId": "leafie-project",
    "storageBucket": "leafie-project.appspot.com",
    "messagingSenderId": "392209039380",
    "appId": "1:392209039380:web:44114ae9fc22f882d96701",
    "databaseURL": ""
}

firebase = pyrebase.initialize_app(firebaseConfig)
auth = firebase.auth()
