/* 
   app.js — RupiahScan
   Semua logika JavaScript untuk deteksi uang rupiah otomatis
    */

'use strict';

/* KONFIGURASI
   Ubah nilai-nilai ini jika ingin menyesuaikan perilaku sistem
  */
const CFG = {
    detectInterval : 2000,   // Deteksi setiap 1.5 detik
    speechCooldown : 6000,   // Jeda minimum antar ucapan yang sama (ms)
    bannerDuration : 4000,   // Berapa lama banner hasil ditampilkan (ms)
    waveDuration   : 2500,   // Berapa lama animasi gelombang tampil (ms)
    minConfidence  : 0.80,   // Confidence minimum untuk umumkan hasil (70%)
};

/* STATE APLIKASI
   Menyimpan kondisi aplikasi saat berjalan
    */
const S = {
    stream        : null,    // MediaStream dari kamera
    loop          : null,    // ID dari setInterval deteksi
    busy          : false,   // True saat sedang request ke server
    modelReady    : false,   // True saat model AI sudah siap
    lastSpeech    : '',      // Teks terakhir yang diucapkan
    lastSpeechAt  : 0,       // Timestamp terakhir ucapan (ms)
    lastStatus    : '',      // Status posisi terakhir
    lastNominal   : '',      // Nominal terakhir yang terdeteksi
    audioUnlocked : false,   // True setelah audio di-unlock browser
};

/* REFERENSI ELEMEN DOM 
   Dikumpulkan sekali di awal agar tidak query DOM berulang kali
   */
const D = {
    video      : document.getElementById('camera-video'),
    loadScreen : document.getElementById('loading-screen'),
    loadMsg    : document.getElementById('loading-msg'),
    errScreen  : document.getElementById('error-screen'),
    errTitle   : document.getElementById('error-title'),
    errMsg     : document.getElementById('error-msg'),
    guide      : document.getElementById('guide-frame'),
    banner     : document.getElementById('result-banner'),
    nominal    : document.getElementById('result-nominal'),
    words      : document.getElementById('result-words'),
    statusText : document.getElementById('status-text'),
    statusIcon : document.getElementById('status-icon'),
    wave       : document.getElementById('audio-wave'),
    confFill   : document.getElementById('confidence-fill'),
    aria       : document.getElementById('aria-live'),
};

/* 
   INISIALISASI — Berjalan otomatis saat halaman dimuat
    */
window.addEventListener('load', () => {
    // Unlock audio saat sentuhan/klik pertama (wajib di browser mobile)
    ['touchstart', 'click'].forEach(ev =>
        document.addEventListener(ev, unlockAudio, { once: true })
    );

    // Mulai inisialisasi setelah 800ms (beri waktu browser siap)
    setTimeout(init, 800);
});

/* Urutan inisialisasi:
   1. Cek server → 2. Buka kamera → 3. Mulai deteksi */
async function init() {
    setLoading('Memeriksa server...');
    await checkServer();
}

/* 
   CEK STATUS SERVER
   Polling setiap 3 detik sampai model siap
    */
async function checkServer() {
    try {
        const r = await fetch('/model-status');
        const d = await r.json();

        if (d.model_loaded) {
            S.modelReady = true;
            setLoading('Model siap! Membuka kamera...');
            await openCamera();
        } else {
            // Model belum siap, coba lagi 3 detik kemudian
            setLoading('Model sedang dimuat, harap tunggu...');
            setTimeout(checkServer, 3000);
        }
    } catch {
        showErr(
            'Server Tidak Tersedia',
            'Pastikan Flask sudah dijalankan, lalu ketuk layar untuk mencoba lagi.'
        );
    }
}

/* 
   BUKA KAMERA SECARA OTOMATIS
   Menggunakan kamera belakang HP (facingMode: environment)
    */
async function openCamera() {
    try {
        setLoading('Membuka kamera...');

        S.stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode : { ideal: 'environment' }, // Kamera belakang
                width      : { ideal: 1280 },
                height     : { ideal: 720 },
            },
            audio: false,
        });

        D.video.srcObject = S.stream;

        // Tunggu video benar-benar siap sebelum mulai deteksi
        await new Promise(resolve => {
            D.video.onloadedmetadata = resolve;
        });

        // Sembunyikan loading screen
        hideLoading();

        // Tampilkan status awal
        setStatus('Arahkan uang ke kamera', '📷');

        // Ucapkan sambutan setelah 700ms (beri waktu loading screen hilang)
        setTimeout(() =>
            speak('Selamat datang di RupiahScan. Arahkan uang ke kamera untuk mendeteksi nominal uang.')
        , 700);

        // Mulai loop deteksi otomatis
        S.loop = setInterval(detect, CFG.detectInterval);

    } catch (e) {
        if (e.name === 'NotAllowedError') {
            showErr(
                'Izin Kamera Ditolak',
                'Izinkan akses kamera di pengaturan browser, lalu ketuk layar untuk mencoba lagi.'
            );
            speak('Akses kamera ditolak. Silakan izinkan akses kamera.');
        } else {
            showErr(
                'Kamera Tidak Tersedia',
                'Kamera tidak bisa dibuka. Pastikan tidak dipakai aplikasi lain.'
            );
        }
    }
}

/* 
   LOOP DETEKSI OTOMATIS
   Berjalan setiap CFG.detectInterval milidetik
   Mengambil frame → kirim ke Flask → proses hasil
    */
async function detect() {
    // Jangan jalankan jika sedang proses atau video belum siap
    if (S.busy || !D.video.videoWidth) return;
    S.busy = true;

    try {
        // Ambil satu frame dari video menggunakan canvas
        const cv  = document.createElement('canvas');
        cv.width  = D.video.videoWidth;
        cv.height = D.video.videoHeight;
        cv.getContext('2d').drawImage(D.video, 0, 0);

        // Kompres ke JPEG 75% untuk hemat bandwidth
        const img = cv.toDataURL('image/jpeg', 0.75);

        // Kirim frame ke Flask server
        const res = await fetch('/detect-realtime', {
            method  : 'POST',
            headers : { 'Content-Type': 'application/json' },
            body    : JSON.stringify({ image: img }),
        });

        if (!res.ok) return;

        const data = await res.json();
        if (data.success) handle(data);

    } catch {
        // Abaikan error jaringan — tidak mengganggu UX
    } finally {
        S.busy = false;
    }
}

/* 
   PROSES HASIL DETEKSI DARI SERVER
   Mengupdate UI dan memutuskan kapan harus berbicara
    */
function handle(data) {
    const st = data.position_status;

    // Update confidence bar
    if (data.confidence) {
        D.confFill.style.height = data.confidence + '%';
    }

    // Update warna frame panduan (kuning → hijau saat terdeteksi)
    D.guide.classList.toggle('detected', st === 'detected');

    // ── Uang belum terlihat di kamera ──
    if (st === 'not_detected') {
        setStatus('Arahkan uang ke kamera', '📷');
        hideBanner();
        maybeSpeak('Arahkan uang ke kamera', st);
        return;
    }

    // ── Uang terlalu jauh ──
    if (st === 'too_far') {
        setStatus('Dekatkan uang ke kamera', '🔍');
        hideBanner();
        maybeSpeak('Uang terlalu jauh, mohon dekatkan', st);
        return;
    }

    // ── Uang terlalu dekat ──
    if (st === 'too_close') {
        setStatus('Jauhkan sedikit dari kamera', '↔️');
        hideBanner();
        maybeSpeak('Uang terlalu dekat, mohon dijauhkan sedikit', st);
        return;
    }

    // ── Posisi ideal + ada prediksi ──
    if (st === 'detected' && data.nominal) {
        const conf = (data.confidence || 0) / 100;

        // Jika confidence belum cukup, minta user tahan dulu
        if (conf < CFG.minConfidence) {
            setStatus('Tahan sebentar...', '⏳');
            return;
        }

        const label = data.label
            || 'Rp ' + parseInt(data.nominal).toLocaleString('id-ID');
        const txt = data.speech_text
            || 'Ini adalah uang ' + (data.words || data.nominal);

        // Update status bar dan banner
        setStatus(label, '✅');
        showBanner(label, data.words || '');

        // Ucapkan nominal:
        // - Langsung (force) jika nominal berubah dari sebelumnya
        // - Dengan cooldown jika nominal sama
        if (data.nominal !== S.lastNominal) {
            S.lastNominal = data.nominal;
            forceSpeak(txt);
        } else {
            maybeSpeak(txt, 'ok_' + data.nominal);
        }
    }
}

/* 
   TEXT-TO-SPEECH (WEB SPEECH API)
    */

/* Unlock audio — dipanggil saat sentuhan/klik pertama.
   Browser mobile tidak izinkan audio sebelum ada interaksi user. */
function unlockAudio() {
    if (S.audioUnlocked || !window.speechSynthesis) return;
    const u = new SpeechSynthesisUtterance(' ');
    u.volume = 0;   // Volume 0 = tidak terdengar, hanya untuk unlock
    speechSynthesis.speak(u);
    S.audioUnlocked = true;
}

/* Fungsi utama text-to-speech */
function speak(text) {
    if (!text || !window.speechSynthesis) return;

    S.lastSpeech   = text;
    S.lastSpeechAt = Date.now();

    // Batalkan ucapan yang sedang berjalan
    speechSynthesis.cancel();

    const u   = new SpeechSynthesisUtterance(text);
    u.lang    = 'id-ID';  // Bahasa Indonesia
    u.rate    = 0.88;     // Sedikit lebih lambat agar jelas
    u.pitch   = 1.0;
    u.volume  = 1.0;

    // Pilih suara Indonesia jika tersedia di perangkat
    const voices = speechSynthesis.getVoices();
    const idVoice = voices.find(v => v.lang.startsWith('id'));
    if (idVoice) u.voice = idVoice;

    // Tampilkan/sembunyikan animasi gelombang
    u.onstart = () => D.wave.classList.add('active');
    u.onend   = () => D.wave.classList.remove('active');

    speechSynthesis.speak(u);

    // Update ARIA live region (untuk screen reader TalkBack/VoiceOver)
    D.aria.textContent = '';
    setTimeout(() => { D.aria.textContent = text; }, 50);
}

/* Paksa bicara tanpa cooldown — untuk nominal baru */
function forceSpeak(text) {
    S.lastSpeechAt = 0;
    speak(text);
}

/* Bicara hanya jika status berubah atau cooldown sudah lewat */
function maybeSpeak(text, key) {
    const changed = key !== S.lastStatus;
    const expired = Date.now() - S.lastSpeechAt > CFG.speechCooldown;
    if (changed || expired) {
        S.lastStatus = key;
        speak(text);
    }
}

/* 
   UI HELPERS — Fungsi-fungsi untuk update tampilan
    */

/* Update teks dan ikon di status bar bawah */
function setStatus(text, icon) {
    D.statusText.textContent = text;
    D.statusIcon.textContent = icon || '';
}

/* Tampilkan banner hasil di atas layar */
let _bannerTimer;
function showBanner(nom, wrd) {
    D.nominal.textContent = nom;
    D.words.textContent   = wrd ? '"' + wrd + '"' : '';
    D.banner.classList.add('visible');

    // Auto-sembunyikan setelah beberapa detik
    clearTimeout(_bannerTimer);
    _bannerTimer = setTimeout(hideBanner, CFG.bannerDuration);
}

/* Sembunyikan banner hasil */
function hideBanner() {
    D.banner.classList.remove('visible');
}

/* Update pesan di loading screen */
function setLoading(msg) {
    D.loadMsg.textContent = msg;
}

/* Sembunyikan loading screen dengan animasi fade */
function hideLoading() {
    D.loadScreen.classList.add('fade-out');
    setTimeout(() => { D.loadScreen.style.display = 'none'; }, 900);
}

/* Tampilkan error screen dengan pesan */
function showErr(title, msg) {
    D.loadScreen.style.display = 'none';
    D.errTitle.textContent     = title;
    D.errMsg.textContent       = msg;
    D.errScreen.classList.add('show');
    speak(title + '. ' + msg);
}

/* Dipanggil saat tombol "Coba Lagi" di error screen ditekan */
function retryInit() {
    D.errScreen.classList.remove('show');
    D.loadScreen.style.cssText = 'display:flex; opacity:1';
    D.loadScreen.classList.remove('fade-out');
    setLoading('Mencoba ulang...');
    setTimeout(init, 500);
}

/* 
   INISIALISASI TAMBAHAN
    */

/* Inisialisasi voices — beberapa browser memuatnya secara async */
if (window.speechSynthesis) {
    speechSynthesis.getVoices();
    speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices();
}

/* Wake Lock — mencegah layar HP mati saat aplikasi sedang berjalan */
(async () => {
    try {
        if ('wakeLock' in navigator) {
            await navigator.wakeLock.request('screen');
        }
    } catch {
        // Tidak kritis jika gagal (browser lama tidak support)
    }
})();
