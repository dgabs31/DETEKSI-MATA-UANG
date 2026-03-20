"""
predict.py - Script Inferensi untuk Deteksi Uang Rupiah
=======================================================
Script ini digunakan untuk melakukan prediksi nominal uang rupiah
dari gambar menggunakan model yang telah dilatih.

Penggunaan:
    python predict.py --image path/to/image.jpg
    python predict.py --image path/to/image.jpg --model path/to/model.h5

Contoh output:
    Nominal: 50000 Rupiah
    Confidence: 98.7%
    Label: Rp 50.000
"""

import os
import sys
import json
import argparse
import numpy as np
from PIL import Image


# ============================================================
# KONFIGURASI DEFAULT
# ============================================================
DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'model', 'rupiah_model.h5')
DEFAULT_LABELS_PATH = os.path.join(os.path.dirname(__file__), '..', 'model', 'class_labels.json')
IMG_SIZE = (224, 224)  # Harus sama dengan ukuran saat training

# Mapping nominal ke ucapan dalam Bahasa Indonesia
NOMINAL_TO_WORDS = {
    '1000':   'seribu rupiah',
    '2000':   'dua ribu rupiah',
    '5000':   'lima ribu rupiah',
    '10000':  'sepuluh ribu rupiah',
    '20000':  'dua puluh ribu rupiah',
    '50000':  'lima puluh ribu rupiah',
    '75000':  'tujuh puluh lima ribu rupiah',  # Edisi khusus 2020
    '100000': 'seratus ribu rupiah',
}


class RupiahPredictor:
    """
    Kelas utama untuk prediksi nominal uang rupiah.
    
    Cara penggunaan:
        predictor = RupiahPredictor()
        result = predictor.predict('path/to/image.jpg')
        print(result)
    """
    
    def __init__(self, model_path=None, labels_path=None):
        """
        Inisialisasi predictor dengan memuat model dan label.
        
        Args:
            model_path: Path ke file model (.h5)
            labels_path: Path ke file class labels (.json)
        """
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.labels_path = labels_path or DEFAULT_LABELS_PATH
        
        # Load model dan labels saat inisialisasi
        self.model = None
        self.idx_to_class = None
        self._load_model()
        self._load_labels()
    
    def _load_model(self):
        """Memuat model dari file .h5"""
        # Import TensorFlow hanya ketika diperlukan
        # (menghindari import lambat saat module diimport)
        import tensorflow as tf
        
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"Model tidak ditemukan di: {self.model_path}\n"
                f"Pastikan Anda sudah menjalankan notebook training terlebih dahulu!"
            )
        
        print(f"Memuat model dari: {self.model_path}")
        self.model = tf.keras.models.load_model(self.model_path)
        print(f"Model berhasil dimuat!")
    
    def _load_labels(self):
        """Memuat mapping indeks ke nama kelas dari file JSON"""
        if not os.path.exists(self.labels_path):
            raise FileNotFoundError(
                f"File labels tidak ditemukan di: {self.labels_path}"
            )
        
        with open(self.labels_path, 'r') as f:
            # JSON key adalah string, konversi ke int
            raw_labels = json.load(f)
            self.idx_to_class = {int(k): v for k, v in raw_labels.items()}
        
        print(f"Labels berhasil dimuat: {list(self.idx_to_class.values())}")
    
    def preprocess_image(self, image_input):
        """
        Preprocessing gambar sebelum prediksi.
        
        Langkah preprocessing:
        1. Buka gambar (bisa dari path file atau PIL Image)
        2. Konversi ke RGB (menghindari masalah dengan grayscale/RGBA)
        3. Resize ke 224x224
        4. Konversi ke numpy array
        5. Normalisasi pixel ke range [0, 1]
        6. Tambah dimensi batch
        
        Args:
            image_input: Path file gambar (str) atau PIL.Image object
        
        Returns:
            numpy array dengan shape (1, 224, 224, 3)
        """
        # Buka gambar
        if isinstance(image_input, str):
            if not os.path.exists(image_input):
                raise FileNotFoundError(f"Gambar tidak ditemukan: {image_input}")
            img = Image.open(image_input)
        elif isinstance(image_input, Image.Image):
            img = image_input
        else:
            # Coba konversi dari numpy array
            img = Image.fromarray(image_input)
        
        # Konversi ke RGB (penting untuk gambar RGBA atau grayscale)
        img = img.convert('RGB')
        
        # Resize ke ukuran yang sesuai dengan input model
        img = img.resize(IMG_SIZE, Image.Resampling.LANCZOS)
        
        # Konversi ke numpy array dan normalisasi
        img_array = np.array(img, dtype=np.float32) / 255.0
        
        # Tambah dimensi batch: (224, 224, 3) -> (1, 224, 224, 3)
        img_batch = np.expand_dims(img_array, axis=0)
        
        return img_batch
    
    def predict(self, image_input, top_k=3):
        """
        Melakukan prediksi nominal uang dari gambar.
        
        Args:
            image_input: Path file atau PIL.Image
            top_k: Jumlah prediksi teratas yang dikembalikan
        
        Returns:
            dict dengan kunci:
                - 'nominal': Nominal uang (str, misal '50000')
                - 'label': Label yang mudah dibaca (str, misal 'Rp 50.000')
                - 'words': Ucapan nominal (str, misal 'lima puluh ribu rupiah')
                - 'confidence': Probabilitas prediksi (float, 0-1)
                - 'confidence_pct': Probabilitas dalam persen (float)
                - 'top_predictions': List top-k prediksi
        """
        # Preprocessing
        img_batch = self.preprocess_image(image_input)
        
        # Prediksi menggunakan model
        predictions = self.model.predict(img_batch, verbose=0)
        proba = predictions[0]  # Ambil probabilitas untuk gambar pertama
        
        # Ambil indeks kelas dengan probabilitas tertinggi
        top_indices = np.argsort(proba)[::-1][:top_k]
        
        # Hasil prediksi utama
        best_idx = top_indices[0]
        best_class = self.idx_to_class[best_idx]
        best_confidence = float(proba[best_idx])
        
        # Daftar top-k prediksi
        top_predictions = []
        for idx in top_indices:
            class_name = self.idx_to_class[idx]
            top_predictions.append({
                'nominal': class_name,
                'label': f'Rp {int(class_name):,}',
                'words': NOMINAL_TO_WORDS.get(class_name, f'{class_name} rupiah'),
                'confidence': float(proba[idx]),
                'confidence_pct': float(proba[idx]) * 100,
            })
        
        return {
            'nominal': best_class,
            'label': f'Rp {int(best_class):,}',
            'words': NOMINAL_TO_WORDS.get(best_class, f'{best_class} rupiah'),
            'confidence': best_confidence,
            'confidence_pct': best_confidence * 100,
            'top_predictions': top_predictions,
            'speech_text': f'Ini adalah uang {NOMINAL_TO_WORDS.get(best_class, best_class + " rupiah")}'
        }
    
    def predict_with_details(self, image_input):
        """
        Versi predict yang lebih detail, cocok untuk debugging.
        
        Args:
            image_input: Path file atau PIL.Image
        
        Returns:
            dict lengkap dengan semua informasi prediksi
        """
        result = self.predict(image_input)
        
        print('\n' + '='*50)
        print('HASIL PREDIKSI UANG RUPIAH')
        print('='*50)
        print(f"Nominal     : {result['label']}")
        print(f"Confidence  : {result['confidence_pct']:.2f}%")
        print(f"Ucapan      : {result['speech_text']}")
        print('\nTop Prediksi:')
        for i, pred in enumerate(result['top_predictions'], 1):
            print(f"  {i}. {pred['label']:>15} - {pred['confidence_pct']:.2f}%")
        print('='*50)
        
        return result


def detect_money_in_frame(image_input):
    """
    Fungsi untuk mendeteksi keberadaan dan posisi uang dalam frame kamera.
    
    Menggunakan metode sederhana berbasis warna dan kontur untuk:
    1. Mendeteksi apakah ada objek uang dalam frame
    2. Menentukan ukuran relatif objek terhadap frame
    3. Memberikan panduan posisi
    
    Args:
        image_input: Path file atau numpy array dari frame kamera
    
    Returns:
        dict dengan status dan panduan
    """
    import cv2
    
    # Buka gambar
    if isinstance(image_input, str):
        img = cv2.imread(image_input)
    else:
        img = image_input
    
    if img is None:
        return {'status': 'error', 'message': 'Gagal membaca gambar'}
    
    height, width = img.shape[:2]
    frame_area = height * width
    
    # Konversi ke grayscale untuk deteksi tepi
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Gaussian blur untuk mengurangi noise
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Deteksi tepi dengan Canny
    edges = cv2.Canny(blurred, 50, 150)
    
    # Cari kontur
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return {
            'status': 'not_detected',
            'message': 'Uang belum terdeteksi, silakan arahkan uang ke kamera',
            'guidance': 'none',
            'bbox_ratio': 0
        }
    
    # Cari kontur terbesar (kemungkinan adalah uang)
    largest_contour = max(contours, key=cv2.contourArea)
    contour_area = cv2.contourArea(largest_contour)
    
    # Hitung rasio area kontur terhadap frame
    area_ratio = contour_area / frame_area
    
    # Threshold untuk panduan posisi
    # - Terlalu jauh: objek < 5% frame
    # - Terlalu dekat: objek > 70% frame  
    # - Ideal: 20% - 60% dari frame
    
    if area_ratio < 0.05:
        return {
            'status': 'too_far',
            'message': 'Uang terlalu jauh, mohon dekatkan',
            'guidance': 'closer',
            'bbox_ratio': area_ratio
        }
    elif area_ratio > 0.70:
        return {
            'status': 'too_close',
            'message': 'Uang terlalu dekat, mohon dijauhkan sedikit',
            'guidance': 'farther',
            'bbox_ratio': area_ratio
        }
    else:
        return {
            'status': 'detected',
            'message': 'Uang terdeteksi dengan jelas',
            'guidance': 'good',
            'bbox_ratio': area_ratio
        }


# ============================================================
# COMMAND LINE INTERFACE
# ============================================================

def main():
    """Fungsi utama untuk menjalankan prediksi dari command line"""
    
    parser = argparse.ArgumentParser(
        description='Deteksi Uang Rupiah menggunakan Computer Vision',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh penggunaan:
  python predict.py --image uang.jpg
  python predict.py --image uang.jpg --model model/rupiah_model.h5
        """
    )
    
    parser.add_argument(
        '--image', '-i',
        type=str,
        required=True,
        help='Path ke gambar uang yang ingin dideteksi'
    )
    
    parser.add_argument(
        '--model', '-m',
        type=str,
        default=DEFAULT_MODEL_PATH,
        help=f'Path ke file model (default: {DEFAULT_MODEL_PATH})'
    )
    
    parser.add_argument(
        '--labels', '-l',
        type=str,
        default=DEFAULT_LABELS_PATH,
        help=f'Path ke file class labels (default: {DEFAULT_LABELS_PATH})'
    )
    
    parser.add_argument(
        '--top-k',
        type=int,
        default=3,
        help='Jumlah prediksi teratas yang ditampilkan (default: 3)'
    )
    
    args = parser.parse_args()
    
    # Jalankan prediksi
    try:
        predictor = RupiahPredictor(
            model_path=args.model,
            labels_path=args.labels
        )
        
        result = predictor.predict_with_details(args.image)
        
        print(f'\nUcapan sistem: "{result["speech_text"]}"')
        
    except FileNotFoundError as e:
        print(f'\nError: {e}')
        sys.exit(1)
    except Exception as e:
        print(f'\nError tidak terduga: {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
