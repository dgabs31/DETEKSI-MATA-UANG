#"""
#app.py - Aplikasi Web untuk Deteksi Uang Rupiah
#===============================================
#Web application menggunakan Flask sebagai framework backend.
#
#Fitur:
#1. Upload gambar dan deteksi nominal uang
#2. Preview gambar yang diupload
#3. Deteksi real-time menggunakan kamera
#4. Panduan suara untuk tunanetra
#5. UI yang aksesibel (tombol besar, kontras tinggi)
#
#Cara menjalankan:
#    python app.py
#
#Kemudian buka browser: http://localhost:5000
#"""

import os
import sys
import json
import base64
import logging
import threading
from io import BytesIO
from datetime import datetime

import numpy as np
from PIL import Image
from flask import (
    Flask, render_template, request, jsonify, 
    send_from_directory, abort
)

# Tambahkan path agar bisa import predict.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================
# KONFIGURASI FLASK APP
# ============================================================
app = Flask(__name__)

# Konfigurasi upload
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Maks 16MB
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp'}

# Buat folder uploads jika belum ada
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Mapping nominal ke ucapan Bahasa Indonesia
NOMINAL_TO_WORDS = {
    '1000':   'seribu rupiah',
    '2000':   'dua ribu rupiah', 
    '5000':   'lima ribu rupiah',
    '10000':  'sepuluh ribu rupiah',
    '20000':  'dua puluh ribu rupiah',
    '50000':  'lima puluh ribu rupiah',
    '100000': 'seratus ribu rupiah',
}

# Status cooldown untuk audio feedback (mencegah suara berulang terus-menerus)
audio_state = {
    'last_status': None,
    'last_nominal': None,
    'last_update': 0,
    'cooldown_seconds': 3  # Cooldown 3 detik
}


# ============================================================
# LOAD MODEL (SINGLETON PATTERN)
# Model dimuat sekali saat aplikasi pertama dijalankan
# ============================================================
predictor = None
model_loaded = False
model_error = None

def load_predictor():
    """Memuat model secara lazy (pertama kali dibutuhkan)"""
    global predictor, model_loaded, model_error
    
    if model_loaded:
        return predictor
    
    try:
        from predict import RupiahPredictor
        
        model_path = os.path.join(
            os.path.dirname(__file__), '..', 'model', 'rupiah_model.h5'
        )
        labels_path = os.path.join(
            os.path.dirname(__file__), '..', 'model', 'class_labels.json'
        )
        
        logger.info("Memuat model...")
        predictor = RupiahPredictor(model_path=model_path, labels_path=labels_path)
        model_loaded = True
        logger.info("✅ Model berhasil dimuat!")
        
    except Exception as e:
        model_error = str(e)
        logger.error(f"❌ Gagal memuat model: {e}")
    
    return predictor


# Muat model di background thread saat startup
def preload_model():
    """Preload model di background"""
    load_predictor()

threading.Thread(target=preload_model, daemon=True).start()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def allowed_file(filename):
    """Cek apakah ekstensi file diperbolehkan"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def preprocess_base64_image(base64_string):
    """
    Konversi gambar base64 menjadi PIL Image.
    Digunakan untuk memproses frame dari kamera (dikirim sebagai base64).
    
    Args:
        base64_string: String base64 gambar
    
    Returns:
        PIL.Image object
    """
    # Hapus header data URL jika ada (misal: "data:image/jpeg;base64,...")
    if ',' in base64_string:
        base64_string = base64_string.split(',')[1]
    
    img_bytes = base64.b64decode(base64_string)
    img = Image.open(BytesIO(img_bytes)).convert('RGB')
    return img


def detect_money_position(img_array):
    """
    Deteksi posisi/ukuran uang dalam frame menggunakan OpenCV.
    
    Memberikan panduan:
    - Terlalu jauh: bounding box kecil
    - Terlalu dekat: bounding box besar
    - Ideal: ukuran bounding box dalam range yang baik
    
    Args:
        img_array: numpy array gambar (RGB)
    
    Returns:
        dict dengan status dan panduan
    """
    try:
        import cv2
        
        # Konversi RGB ke BGR untuk OpenCV
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        height, width = img_bgr.shape[:2]
        frame_area = height * width
        
        # Konversi ke grayscale
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        
        # Gaussian blur untuk mengurangi noise
        blurred = cv2.GaussianBlur(gray, (7, 7), 0)
        
        # Deteksi tepi
        edges = cv2.Canny(blurred, 30, 120)
        
        # Morphological operations untuk menutup celah pada tepi
        kernel = np.ones((5, 5), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=2)
        edges = cv2.erode(edges, kernel, iterations=1)
        
        # Cari kontur
        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        if not contours:
            return {
                'status': 'not_detected',
                'message': 'Uang belum terdeteksi, silakan arahkan uang ke kamera',
                'guidance': 'none',
                'bbox_ratio': 0
            }
        
        # Filter kontur yang terlalu kecil (noise)
        significant_contours = [c for c in contours if cv2.contourArea(c) > 1000]
        
        if not significant_contours:
            return {
                'status': 'not_detected',
                'message': 'Uang belum terdeteksi, silakan arahkan uang ke kamera',
                'guidance': 'none',
                'bbox_ratio': 0
            }
        
        # Cari kontur terbesar
        largest_contour = max(significant_contours, key=cv2.contourArea)
        contour_area = cv2.contourArea(largest_contour)
        area_ratio = contour_area / frame_area
        
        # Tentukan status berdasarkan rasio area
        if area_ratio < 0.08:
            return {
                'status': 'too_far',
                'message': 'Uang terlalu jauh, mohon dekatkan',
                'guidance': 'closer',
                'bbox_ratio': area_ratio
            }
        elif area_ratio > 0.65:
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
    
    except ImportError:
        # Fallback jika OpenCV tidak tersedia: gunakan heuristik sederhana
        logger.warning("OpenCV tidak tersedia, menggunakan fallback detection")
        return {
            'status': 'detected',
            'message': 'Uang terdeteksi dengan jelas',
            'guidance': 'good',
            'bbox_ratio': 0.3
        }
    except Exception as e:
        logger.error(f"Error deteksi posisi: {e}")
        return {
            'status': 'detected',
            'message': 'Siap untuk dideteksi',
            'guidance': 'good',
            'bbox_ratio': 0.3
        }


def should_give_audio_feedback(new_status, new_nominal=None):
    """
    Menentukan apakah perlu memberikan feedback audio.
    Menggunakan cooldown untuk mencegah suara berulang terus-menerus.
    
    Args:
        new_status: Status baru ('not_detected', 'too_far', 'too_close', 'detected')
        new_nominal: Nominal uang yang terdeteksi (jika ada)
    
    Returns:
        bool: True jika harus memberikan feedback audio
    """
    import time
    
    current_time = time.time()
    
    # Selalu beri feedback jika status berubah
    if new_status != audio_state['last_status']:
        audio_state['last_status'] = new_status
        audio_state['last_nominal'] = new_nominal
        audio_state['last_update'] = current_time
        return True
    
    # Beri feedback jika nominal berubah
    if new_nominal and new_nominal != audio_state['last_nominal']:
        audio_state['last_nominal'] = new_nominal
        audio_state['last_update'] = current_time
        return True
    
    # Beri feedback berulang setelah cooldown
    if current_time - audio_state['last_update'] >= audio_state['cooldown_seconds']:
        audio_state['last_update'] = current_time
        return True
    
    return False


# ============================================================
# ROUTE: HALAMAN UTAMA
# ============================================================

@app.route('/')
def index():
    """Halaman utama aplikasi"""
    return render_template('index.html')


# ============================================================
# ROUTE: UPLOAD DAN DETEKSI GAMBAR
# ============================================================

@app.route('/detect', methods=['POST'])
def detect():
    """
    Endpoint untuk mendeteksi nominal uang dari gambar yang diupload.
    
    Menerima:
        - File gambar (multipart/form-data)
        - atau Base64 string (application/json)
    
    Mengembalikan:
        JSON dengan hasil deteksi
    """
    pred = load_predictor()
    
    if pred is None:
        error_msg = model_error or "Model belum tersedia"
        if "tidak ditemukan" in error_msg.lower():
            error_msg = (
                "Model belum tersedia. "
                "Silakan jalankan notebook training terlebih dahulu!"
            )
        return jsonify({'error': error_msg, 'success': False}), 503
    
    try:
        img = None
        
        # Cek apakah request berisi file upload
        if 'file' in request.files:
            file = request.files['file']
            
            if file.filename == '':
                return jsonify({'error': 'Tidak ada file yang dipilih', 'success': False}), 400
            
            if not allowed_file(file.filename):
                return jsonify({
                    'error': f'Format file tidak didukung. Gunakan: {", ".join(ALLOWED_EXTENSIONS)}',
                    'success': False
                }), 400
            
            img = Image.open(file.stream).convert('RGB')
        
        # Cek apakah request berisi base64 image
        elif request.is_json and 'image' in request.json:
            img = preprocess_base64_image(request.json['image'])
        
        else:
            return jsonify({
                'error': 'Tidak ada gambar yang diterima',
                'success': False
            }), 400
        
        # Lakukan prediksi
        result = pred.predict(img)
        
        # Tambah informasi tambahan
        result['success'] = True
        result['timestamp'] = datetime.now().isoformat()
        
        logger.info(
            f"Prediksi: {result['label']} "
            f"(confidence: {result['confidence_pct']:.1f}%)"
        )
        
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error saat prediksi: {e}")
        return jsonify({
            'error': f'Terjadi kesalahan: {str(e)}',
            'success': False
        }), 500


# ============================================================
# ROUTE: DETEKSI REAL-TIME (FRAME KAMERA)
# ============================================================

@app.route('/detect-realtime', methods=['POST'])
def detect_realtime():
    """
    Endpoint untuk deteksi real-time dari frame kamera.
    
    Alur:
    1. Terima frame kamera (base64)
    2. Deteksi posisi/ukuran uang dalam frame
    3. Jika posisi ideal, lakukan klasifikasi nominal
    4. Kembalikan hasil + panduan audio
    
    Menerima:
        JSON: {'image': '<base64 string>'}
    
    Mengembalikan:
        JSON dengan status, panduan, dan hasil deteksi
    """
    if not request.is_json:
        return jsonify({'error': 'Request harus JSON', 'success': False}), 400
    
    data = request.json
    
    if 'image' not in data:
        return jsonify({'error': 'Field "image" tidak ditemukan', 'success': False}), 400
    
    try:
        # Konversi base64 ke PIL Image
        img = preprocess_base64_image(data['image'])
        img_array = np.array(img)
        
        # Step 1: Deteksi posisi uang dalam frame
        position_result = detect_money_position(img_array)
        
        response = {
            'success': True,
            'position_status': position_result['status'],
            'guidance_message': position_result['message'],
            'guidance': position_result['guidance'],
            'bbox_ratio': position_result['bbox_ratio'],
            'give_audio': False,
            'nominal': None,
            'label': None,
            'words': None,
            'speech_text': position_result['message'],
            'confidence': None,
        }
        
        # Step 2: Jika posisi ideal, lakukan klasifikasi
        if position_result['status'] == 'detected':
            pred = load_predictor()
            
            if pred:
                pred_result = pred.predict(img)
                
                response.update({
                    'nominal': pred_result['nominal'],
                    'label': pred_result['label'],
                    'words': pred_result['words'],
                    'confidence': pred_result['confidence_pct'],
                    'speech_text': pred_result['speech_text'],
                    'top_predictions': pred_result['top_predictions']
                })
                
                # Cek apakah perlu memberikan audio feedback
                response['give_audio'] = should_give_audio_feedback(
                    'classified', pred_result['nominal']
                )
            else:
                response['guidance_message'] = 'Model sedang dimuat...'
        
        else:
            # Beri feedback posisi
            response['give_audio'] = should_give_audio_feedback(
                position_result['status']
            )
        
        return jsonify(response)
    
    except Exception as e:
        logger.error(f"Error deteksi real-time: {e}")
        return jsonify({
            'error': str(e),
            'success': False
        }), 500


# ============================================================
# ROUTE: STATUS MODEL
# ============================================================

@app.route('/model-status')
def model_status():
    """Cek status model apakah sudah siap atau belum"""
    pred = load_predictor()
    
    if pred:
        return jsonify({
            'status': 'ready',
            'message': 'Model siap digunakan',
            'model_loaded': True
        })
    else:
        return jsonify({
            'status': 'not_ready',
            'message': model_error or 'Model belum dimuat',
            'model_loaded': False
        }), 503


# ============================================================
# ROUTE: SERVE STATIC FILES
# ============================================================

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve file statis (CSS, JS, gambar)"""
    return send_from_directory(
        os.path.join(os.path.dirname(__file__), 'static'), 
        filename
    )


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(413)
def too_large(e):
    """Handle file terlalu besar"""
    return jsonify({
        'error': 'File terlalu besar. Maksimum ukuran file adalah 16MB.',
        'success': False
    }), 413


@app.errorhandler(404)
def not_found(e):
    """Handle halaman tidak ditemukan"""
    return jsonify({'error': 'Halaman tidak ditemukan', 'success': False}), 404


@app.errorhandler(500)
def internal_error(e):
    """Handle error internal server"""
    return jsonify({'error': 'Terjadi kesalahan server', 'success': False}), 500


# ============================================================
# JALANKAN APLIKASI
# ============================================================

if __name__ == '__main__':
    print('=' * 60)
    print('🏦 DETEKSI UANG RUPIAH - APLIKASI WEB')
    print('   Sistem Bantu Tunanetra')
    print('=' * 60)
    print(f'🌐 Buka browser: http://localhost:5000')
    print(f'📁 Upload folder: {app.config["UPLOAD_FOLDER"]}')
    print('=' * 60)
    
    # debug=False untuk production
    # host='0.0.0.0' agar bisa diakses dari jaringan lokal
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True  # Ubah ke False untuk production
    )
