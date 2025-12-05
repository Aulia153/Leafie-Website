import cv2
import numpy as np
import joblib
from skimage.feature import graycomatrix, graycoprops
from rembg import remove, new_session
from PIL import Image
import io
import warnings
warnings.filterwarnings("ignore")

class LeafClassifier:
    def __init__(self, 
                 model_path="./model/random_forest_daun_FINAL.pkl", 
                 scaler_path="./model/scaler_daun_FINAL.pkl"):
        self.model = joblib.load(model_path)
        self.scaler = joblib.load(scaler_path)
        self.IMG_SIZE = 128
        self.categories = ["Sehat", "Tidak_Sehat"]

        try:
            self.session = new_session("u2netp", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
        except:
            self.session = new_session("u2netp", providers=["CPUExecutionProvider"])
        
    def extract_features(self, img_bgr):
        _, buffer = cv2.imencode('.jpg', img_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        img_bgr = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        
        img_resized = cv2.resize(img_bgr, (self.IMG_SIZE, self.IMG_SIZE))
        img_gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
        img_gray = cv2.GaussianBlur(img_gray, (3, 3), 0)
        hsv = cv2.cvtColor(img_resized, cv2.COLOR_BGR2HSV)

        # GLCM
        glcm = graycomatrix(img_gray, distances=[1], angles=[0, np.pi/4, np.pi/2],
                            symmetric=True, normed=True)
        contrast = graycoprops(glcm, 'contrast').mean()
        homogeneity = graycoprops(glcm, 'homogeneity').mean()
        energy = graycoprops(glcm, 'energy').mean()
        correlation = graycoprops(glcm, 'correlation').mean()

        # Fitur tambahan
        mask_brown = cv2.inRange(hsv, (15, 50, 50), (35, 255, 200))
        brown_ratio = np.sum(mask_brown > 0) / (self.IMG_SIZE * self.IMG_SIZE)

        _, thresh = cv2.threshold(img_gray, 70, 255, cv2.THRESH_BINARY_INV)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        hole_area_ratio = sum(cv2.contourArea(c) for c in contours) / (self.IMG_SIZE * self.IMG_SIZE)
        num_holes = len(contours)

        glcm_features = [contrast, homogeneity, energy, correlation]
        extra_features = [brown_ratio, hole_area_ratio, num_holes]
        return np.hstack((glcm_features, extra_features))
    
    def preprocess_image(self, image_path_or_bytes):
        # Baca gambar
        if isinstance(image_path_or_bytes, str):
            img_pil = Image.open(image_path_or_bytes).convert("RGB")
        else:
            img_pil = Image.open(io.BytesIO(image_path_or_bytes)).convert("RGB")

        if max(img_pil.size) > 800:
            ratio = 800 / max(img_pil.size)
            new_size = (int(img_pil.width * ratio), int(img_pil.height * ratio))
            img_pil = img_pil.resize(new_size, Image.LANCZOS)

        # Convert ke bytes
        img_bytes = io.BytesIO()
        img_pil.save(img_bytes, format="PNG")
        img_bytes.seek(0)

        # Remove Bg
        output_data = remove(
            img_bytes.read(),
            session=self.session,  
            alpha_matting=False,
            alpha_matting_erode_size=10,
            background_threshold=30
        )

        # Composite ke background putih
        img_rgba = Image.open(io.BytesIO(output_data)).convert("RGBA")
        white_bg = Image.new("RGBA", img_rgba.size, (255, 255, 255, 255))
        img_clean = Image.alpha_composite(white_bg, img_rgba).convert("RGB")

        # Kompresi konsisten
        buffer = io.BytesIO()
        img_clean.save(buffer, format="JPEG", quality=90, optimize=True)
        buffer.seek(0)
        img_final = Image.open(buffer).convert("RGB")
        
        return cv2.cvtColor(np.array(img_final), cv2.COLOR_RGB2BGR)
    
    def predict(self, image_path_or_bytes):
        try:
            img_cv = self.preprocess_image(image_path_or_bytes)
            features = self.extract_features(img_cv)
            features_scaled = self.scaler.transform([features])
            
            prediction = self.model.predict(features_scaled)[0]
            prob = self.model.predict_proba(features_scaled)[0]
            
            is_healthy = (prediction == 0)
            status = "Sehat" if is_healthy else "Tidak_Sehat"
            
            recommendations = self._generate_recommendations(features, is_healthy)
            
            return {
                "success": True,
                "status": status,
                "label": status,
                "confidence": float(prob[prediction]),
                "recommendations": recommendations
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _generate_recommendations(self, features, is_healthy):
        recommendations = []
        contrast, homogeneity, energy, correlation, brown_ratio, hole_area_ratio, num_holes = features

        if is_healthy:
            recommendations = [
                "Daun dalam kondisi sehat!",
                "Pertahankan penyiraman yang cukup dan teratur.",
                "Pastikan tanaman mendapat sinar matahari yang optimal."
            ]
        else:
            if brown_ratio > 0.15:
                recommendations = [
                    "Daun tidak sehat — terdeteksi banyak bercak coklat.",
                    "Kemungkinan infeksi jamur atau kekurangan nutrisi."
                ]
            elif num_holes > 5 or hole_area_ratio > 0.1:
                recommendations = [
                    "Daun tidak sehat — terdeteksi banyak lubang.",
                    "Kemungkinan besar serangan hama (ulat/serangga)."
                ]
            else:
                recommendations = [
                    "Daun tidak sehat - Periksa kondisi tanaman secara menyeluruh.",
                    "Pastikan penyiraman dan nutrisi tercukupi.",
                    "Monitor suhu dan kelembapan lingkungan."
                ]
        return recommendations[:3]


classifier = None
def get_classifier():
    global classifier
    if classifier is None:
        classifier = LeafClassifier()
    return classifier