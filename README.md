# RupiahScan: Inovasi Deteksi Nominal Rupiah untuk Tunanetra

**RupiahScan** adalah aplikasi berbasis Web-AI yang dirancang untuk membantu penyandang disabilitas netra mengenali nominal uang kertas Rupiah secara *real-time*[cite: 180, 187]. 
Sistem ini bertindak sebagai "mata" digital yang mengonversi visual uang menjadi informasi suara[cite: 187].

## 📊 Dataset & Preprocessing
Dataset yang digunakan dalam proyek ini merupakan **gabungan hasil kurasi mandiri** dari dua sumber publik utama di Kaggle. Hal ini dilakukan untuk memperkaya variasi data latih (augmentation by source).

Sumber Utama:[Rupiah Banknotes - Nurul Alfiyyah](https://www.kaggle.com/datasets/nurulalfiyyah/rupiah-banknotes)
Sumber Tambahan:[Indonesian Banknotes - Brotoa](https://www.kaggle.com/datasets/brotoa/indonesian-banknotes-for-machine-learning)

*Unduh Dataset Gabungan (ZIP):*
Karena batasan ukuran file di GitHub, dataset yang telah dikurasi dapat diunduh melalui tautan berikut:
👉 **[Download Dataset RupiahScan via Google Drive](https://drive.google.com/drive/folders/1F7AMyKLAekq1eYbLlxawwjTTfOB4QCbg?usp=sharing)**

*Instruksi Setup Dataset*:
1. Buat direktori bernama `dataset/` di root proyek.
2. Unduh dan ekstrak kedua dataset di atas.
3. Masukkan gambar ke dalam sub-folder sesuai label nominalnya (misal: `1000`, `2000`, dst).
4. Pastikan hanya menggunakan emisi uang yang sesuai dengan ruang lingkup proyek (Emisi 2016 & 2022).

## 🚀 Fitur Utama
* **Pemindaian Otomatis:** Kamera melakukan *scanning* aktif secara otomatis tanpa perlu menekan tombol[cite: 297].
* **Output Suara Bahasa Indonesia:** Menggunakan *Web Speech API* untuk membacakan nominal uang secara jernih[cite: 298].
* **Arsitektur Client-Server:** Pemrosesan AI dilakukan di *backend* sehingga aplikasi tetap ringan dijalankan di perangkat berspesifikasi rendah[cite: 189, 190].
* **Robust terhadap Kondisi Riil:** Model dilatih untuk mengenali uang lusuh, terlipat, hingga dalam kondisi cahaya minim[cite: 194, 195].

## 📦 Instalasi
1. Ikuti langkah-langkah berikut untuk menjalankan proyek ini di komputer lokal Anda:
Clone repository ini
```
Bash
# Clone repository ini
git clone https://github.com/username/nama-repo.git

# Masuk ke direktori proyek
cd nama-repo

# Install dependensi
pip install -r requirements.txt
```

## Struktur Proyek Aplikasi 
```text
RupiahScan/
├── backend/ (Flask Framework) 
│   ├── app.py (Server Flask & RESTful API) [cite: 10, 11]
│   ├── model/
│   │   └── mobilenetv2_rupiah.h5 (Bobot model terbaik) [cite: 107, 161]
│   └── utils/
│       └── parser.py (Fungsi Regex untuk parsing folder) [cite: 26, 29]
├── frontend/ (Web Interface) [cite: 17]
│   ├── index.html (Tampilan minimalis) [cite: 123]
│   ├── css/
│   │   └── style.css [cite: 17]
│   └── js/
│       └── script.js (Logika kamera & Web Speech API) [cite: 17, 119]
└── dataset/ (Rupiah Banknotes Dataset) [cite: 21]
    ├── 2022-100D/ 
    ├── 2022-100B/ 
    └── ... (Total 26 direktori)
```

## 🛠️ Arsitektur Teknologi
* **Frontend:** HTML5, CSS3, JavaScript[cite: 196].
* **Backend:** Python & Flask Framework (RESTful API)[cite: 190].
* **AI Model:** MobileNetV2 (Transfer Learning)[cite: 220].
* **Dataset:** Rupiah Banknotes Dataset dari Kaggle[cite: 200].

## 🧠 Detail Pengembangan Model
Pengembangan model menggunakan metode *Transfer Learning* dengan dua fase pelatihan[cite: 220, 227]:
1.  **Fase 1 (Membangun Pondasi):** Melatih *classifier head* baru dengan *learning rate* $1\times10^{-4}$[cite: 230, 231].
2.  **Fase 2 (Fine-tuning):** Membuka 30 lapisan terakhir MobileNetV2 dengan *learning rate* lebih kecil ($1\times10^{-5}$) untuk spesialisasi detail mata uang[cite: 234, 235].

Akurasi akhir mencapai **100%** pada data validasi[cite: 269].

## 📦 Alur Kerja Sistem (Workflow)
1.  **Client:** Menangkap *frame* kamera setiap 2 detik dan mengirimkannya ke server dalam format Base64[cite: 196, 332, 333].
2.  **Server:** Melakukan *preprocessing* dan inferensi menggunakan model MobileNetV2[cite: 334].
3.  **Threshold:** Hasil deteksi hanya dikirim jika probabilitas keyakinan model $> 0.70$[cite: 335].
4.  **Output:** Browser menerima respon JSON dan menjalankan *Web Speech API*[cite: 336].

## 💻 Instalasi & Menjalankan (Lokal)

1.  **Persiapkan Lingkungan Python**
    ```bash
    pip install flask tensorflow pillow flask-cors
    ```
2.  **Jalankan Flask Server**
    ```bash
    python app.py
    ```
3.  **Akses Aplikasi**
    Buka file `index.html` di browser atau melalui alamat lokal yang disediakan Flask[cite: 332].

## 📄 Penutup
Inovasi ini bertujuan meningkatkan kemandirian ekonomi penyandang tunanetra dengan meminimalisir risiko penipuan saat bertransaksi[cite: 185, 357].

---

👨‍💻 Penulis Dame Gabriela Silitonga & Nakeisya Zahratul Adhara Program Studi Teknologi Sains Data Universitas Airlangga
