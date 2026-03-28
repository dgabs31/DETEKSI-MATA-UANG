# road-signs-classification
# Autonomous Vehicle Vision: Cascade Pipeline for Traffic Sign Recognition

Sistem pendeteksi rambu lalu lintas cerdas yang mengimplementasikan arsitektur **Cascade Pipeline**. Proyek ini tidak hanya mendeteksi *bounding box* dari sebuah rambu lalu lintas, tetapi juga mengekstrak konteks spesifik di dalamnya menggunakan gabungan *Deep Learning* dan *Computer Vision* klasik.

## Latar Belakang
Mendeteksi objek (seperti rambu jalan) saja tidak cukup bagi sistem *Advanced Driver Assistance Systems* (ADAS). Sistem harus mengerti *apa* yang ada di dalam rambu tersebut. Proyek ini mengatasi batasan dataset anotasi dengan memecah tugas menjadi dua tahap (Multi-Stage Inference), meminimalkan beban komputasi sekaligus memaksimalkan ekstraksi informasi.

## Arsitektur Pipeline

Proyek ini dibangun menggunakan arsitektur 2 Tahap (Cascade):
1. **Stage 1 (Pendeteksi Lokasi):** Menggunakan **Faster R-CNN** (ResNet50 Backbone) untuk mendeteksi 4 kelas dasar: `trafficlight`, `speedlimit`, `crosswalk`, dan `stop`.
2. **Stage 2 (Pengekstrak Konteks):** Memotong (*crop*) *bounding box* yang terdeteksi dan mengirimkannya ke pakar spesifik:
   - 🚦 **Modul Traffic Light:** Menggunakan OpenCV (Color Space HSV) untuk menghitung dominasi piksel dan menentukan warna lampu (Merah/Kuning/Hijau).
   - 🔢 **Modul Speed Limit:** Menggunakan Tesseract OCR (`pytesseract`) dengan konfigurasi *whitelist* numerik untuk mengekstrak angka batas kecepatan.

## Kinerja Model (Faster R-CNN Base)
Dilatih hanya dalam **5 Epochs** menggunakan dataset turunan Andrewmvd, model dasar ini mencapai tingkat kewaspadaan yang sangat tinggi:
- **Macro Avg F1-Score:** 0.92
- **Recall:** 0.97 *(Sangat krusial untuk keselamatan otonom; model hampir tidak pernah melewatkan rambu di jalan).*
- **Precision:** 0.88
- **Highlight:** Mendeteksi kelas `speedlimit` dengan tingkat *True Positives* sempurna (783/783) tanpa *False Negatives*.

## Struktur Direktori
```text
road_sign_web/
│
├── app.py                     # Jantung utama aplikasi (Routing Flask)
├── inference.py               # Script Dapur AI (Load model, pipeline HSV & OCR)
├── requirements.txt           # Daftar dependensi library
│
├── models/
│   └── best_model.pth         # Bobot (weights) model Faster R-CNN terbaik
│
├── static/
│   ├── css/
│   │   └── style.css          # Styling antarmuka web
│   ├── uploads/               # Direktori penyimpanan sementara input user
│   └── results/               # Direktori output gambar hasil deteksi
│
└── templates/
    └── index.html             # Tampilan antarmuka utama
```

🚀 Instalasi & Cara Penggunaan
1. Prasyarat Sistem
Python 3.8+

Tesseract OCR (Wajib di-install di OS Anda, khususnya untuk pengguna Windows).

2. Setup Environment
Clone repositori ini dan buat virtual environment:

Bash
git clone [https://github.com/USERNAME_GITHUB_KAMU/road-sign-detection.git](https://github.com/USERNAME_GITHUB_KAMU/road-sign-detection.git)
cd road-sign-detection
python -m venv .venv
Aktifkan environment:

Windows: .\.venv\Scripts\activate

Mac/Linux: source .venv/bin/activate

3. Install Dependensi
Bash
pip install -r requirements.txt
(Catatan: Pastikan Anda menggunakan opencv-python-headless di server Linux untuk menghindari error GUI).

4. Konfigurasi Tesseract (Khusus Windows)
Buka file inference.py, dan pastikan path instalasi Tesseract Anda sudah benar pada baris berikut:

Python
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
5. Jalankan Aplikasi
Eksekusi server lokal:

Bash
python app.py
Buka browser dan akses: http://localhost:5000

👨‍💻 Penulis
Khairunnisa Keisha Anjani
Quinnaira Aqila Azfa Azwa
Program Studi Teknologi Sains Data
Universitas Airlangga
