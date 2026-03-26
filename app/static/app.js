/* 
   app.js — RupiahScan
   Versi dengan SISTEM KONFIRMASI:
   Prediksi harus konsisten N kali sebelum diumumkan via suara.
    */

'use strict';

/* KONFIGURASI */
const CFG = {
    detectInterval : 1000,  // Deteksi setiap 1 detik
    speechCooldown : 4000,  // Jeda antar ucapan nominal yang sama (ms)
    bannerDuration : 5000,  // Durasi banner hasil tampil (ms)
    minConfidence  : 0.80,  // Confidence minimum per prediksi (80%)

    // Nominal harus muncul sebanyak ini BERTURUT-TURUT
    // sebelum sistem boleh bicara.
    // Nilai 3 = harus dapat prediksi sama 3x berturut-turut
    // Naikkan jika sistem masih sering salah bicara
    confirmNeeded  : 3,
};

/* STATE */
const S = {
    stream           : null,
    loop             : null,
    busy             : false,
    modelReady       : false,
    lastSpeechAt     : 0,
    lastStatus       : '',
    audioUnlocked    : false,

    // State konfirmasi
    confirmNominal   : '',  // Nominal yang sedang dikumpulkan
    confirmCount     : 0,   // Sudah berapa kali dapat nominal ini berturut-turut
    confirmedNominal : '',  // Nominal yang terakhir berhasil diumumkan
    confirmTimer     : null,
};

/* DOM */
const D = {
    video       : document.getElementById('camera-video'),
    loadScreen  : document.getElementById('loading-screen'),
    loadMsg     : document.getElementById('loading-msg'),
    errScreen   : document.getElementById('error-screen'),
    errTitle    : document.getElementById('error-title'),
    errMsg      : document.getElementById('error-msg'),
    guide       : document.getElementById('guide-frame'),
    banner      : document.getElementById('result-banner'),
    nominal     : document.getElementById('result-nominal'),
    words       : document.getElementById('result-words'),
    statusText  : document.getElementById('status-text'),
    statusIcon  : document.getElementById('status-icon'),
    wave        : document.getElementById('audio-wave'),
    confFill    : document.getElementById('confidence-fill'),
    dots        : document.getElementById('confirm-dots'),
    aria        : document.getElementById('aria-live'),
};

/* 
   INISIALISASI OTOMATIS
   */
window.addEventListener('load', () => {
    ['touchstart', 'click'].forEach(ev =>
        document.addEventListener(ev, unlockAudio, { once: true })
    );
    setTimeout(init, 800);
});

async function init() {
    setLoading('Memeriksa server...');
    await checkServer();
}

/* 
   CEK SERVER
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
            setLoading('Model sedang dimuat, harap tunggu...');
            setTimeout(checkServer, 3000);
        }
    } catch {
        showErr('Server Tidak Tersedia',
            'Pastikan Flask sudah dijalankan, lalu ketuk layar untuk mencoba lagi.');
    }
}

/* 
   BUKA KAMERA OTOMATIS
   */
async function openCamera() {
    try {
        setLoading('Membuka kamera...');
        S.stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode : { ideal: 'environment' },
                width      : { ideal: 1280 },
                height     : { ideal: 720 },
            },
            audio: false,
        });
        D.video.srcObject = S.stream;
        await new Promise(r => { D.video.onloadedmetadata = r; });

        hideLoading();
        setStatus('Arahkan uang ke kamera', '📷');

        setTimeout(() =>
            speak('Selamat datang di RupiahScan. Arahkan uang ke kamera.')
        , 700);

        S.loop = setInterval(detect, CFG.detectInterval);

    } catch (e) {
        if (e.name === 'NotAllowedError') {
            showErr('Izin Kamera Ditolak',
                'Izinkan akses kamera di pengaturan browser, lalu ketuk layar untuk mencoba lagi.');
            speak('Akses kamera ditolak. Silakan izinkan akses kamera.');
        } else {
            showErr('Kamera Tidak Tersedia',
                'Kamera tidak bisa dibuka. Pastikan tidak dipakai aplikasi lain.');
        }
    }
}

/* 
   LOOP DETEKSI OTOMATIS
   */
async function detect() {
    if (S.busy || !D.video.videoWidth) return;
    S.busy = true;
    try {
        const cv  = document.createElement('canvas');
        cv.width  = D.video.videoWidth;
        cv.height = D.video.videoHeight;
        cv.getContext('2d').drawImage(D.video, 0, 0);
        const img = cv.toDataURL('image/jpeg', 0.75);

        const res  = await fetch('http:192.168.1.8/detect-realtime', {
            method  : 'POST',
            headers : { 'Content-Type': 'application/json' },
            body    : JSON.stringify({ image: img }),
        });
        if (!res.ok) return;
        const data = await res.json();
        if (data.success) handle(data);

    } catch { /* abaikan error jaringan */ }
    finally  { S.busy = false; }
}

/* 
   PROSES HASIL DETEKSI
   */
function handle(data) {
    const st = data.position_status;

    if (data.confidence) {
        D.confFill.style.height = data.confidence + '%';
    }

    // Uang tidak terlihat / posisi salah 
    if (st === 'not_detected') {
        resetConfirm();
        D.guide.classList.remove('detected');
        setStatus('Arahkan uang ke kamera', '📷');
        hideBanner();
        renderDots(0);
        maybeSpeak('Arahkan uang ke kamera', st);
        return;
    }
    if (st === 'too_far') {
        resetConfirm();
        D.guide.classList.remove('detected');
        setStatus('Dekatkan uang ke kamera', '🔍');
        hideBanner();
        renderDots(0);
        maybeSpeak('Uang terlalu jauh, mohon dekatkan', st);
        return;
    }
    if (st === 'too_close') {
        resetConfirm();
        D.guide.classList.remove('detected');
        setStatus('Jauhkan sedikit dari kamera', '↔️');
        hideBanner();
        renderDots(0);
        maybeSpeak('Uang terlalu dekat, mohon dijauhkan sedikit', st);
        return;
    }

    // Posisi ideal, ada prediksi ─
    if (st === 'detected' && data.nominal) {
        const conf = (data.confidence || 0) / 100;

        // Confidence terlalu rendah → abaikan, jangan masuk hitungan
        if (conf < CFG.minConfidence) {
            setStatus('Tahan sebentar...', '⏳');
            return;
        }

        konfirmasi(data);
    }
}

/* 
   SISTEM KONFIRMASI
   

   Cara kerja (misal confirmNeeded = 3):

   Deteksi 1: dapat "50000" conf 95%
       → confirmNominal = "50000", confirmCount = 1
       → Tampilkan dots: ●○○  status: "Mengenali..."

   Deteksi 2: dapat "50000" conf 92%
       → confirmNominal = "50000", confirmCount = 2
       → Tampilkan dots: ●●○  status: "Mengenali..."

   Deteksi 3: dapat "2000" conf 85%   ← BERBEDA!
       → RESET: confirmNominal = "2000", confirmCount = 1
       → Tampilkan dots: ●○○  status: "Mengenali..."

   Deteksi 4: dapat "2000" conf 88%
       → confirmCount = 2
       → Tampilkan dots: ●●○

   Deteksi 5: dapat "2000" conf 91%
       → confirmCount = 3 >= confirmNeeded
       → UMUMKAN: "Ini adalah uang dua ribu rupiah"
       → Tampilkan dots: ●●● (hijau)

   */
function konfirmasi(data) {
    const nominal = data.nominal;

    // Reset timer — jika tidak ada prediksi masuk dalam 4 detik, reset
    clearTimeout(S.confirmTimer);
    S.confirmTimer = setTimeout(() => {
        resetConfirm();
        renderDots(0);
    }, 4000);

    // Jika nominal BERBEDA dari yang sedang dikonfirmasi → reset & mulai baru
    if (nominal !== S.confirmNominal) {
        S.confirmNominal = nominal;
        S.confirmCount   = 1;
        D.guide.classList.remove('detected');
        setStatus('Mengenali...', '🔄');
        renderDots(1);
        return;
    }

    // Nominal SAMA → tambah hitungan
    S.confirmCount++;
    renderDots(S.confirmCount);

    // Belum cukup → tampilkan progress, jangan bicara dulu
    if (S.confirmCount < CFG.confirmNeeded) {
        setStatus('Mengenali...', '🔄');
        D.guide.classList.remove('detected');
        return;
    }

    // KONFIRMASI BERHASIL 
    D.guide.classList.add('detected');
    renderDots(CFG.confirmNeeded, true); // semua dots hijau

    const label = data.label
        || 'Rp ' + parseInt(nominal).toLocaleString('id-ID');
    const txt = data.speech_text
        || 'Ini adalah uang ' + (data.words || nominal);

    setStatus(label, '✅');
    showBanner(label, data.words || '');

    // Ucapkan jika nominal berubah atau cooldown sudah lewat
    const berubah  = nominal !== S.confirmedNominal;
    const expired  = Date.now() - S.lastSpeechAt > CFG.speechCooldown;
    if (berubah || expired) {
        S.confirmedNominal = nominal;
        forceSpeak(txt);
    }

    // Reset counter setelah diumumkan agar tidak langsung bicara lagi
    // di iterasi berikutnya
    S.confirmCount = 0;
}

/* Reset semua state konfirmasi */
function resetConfirm() {
    clearTimeout(S.confirmTimer);
    S.confirmNominal = '';
    S.confirmCount   = 0;
}

/* 
   RENDER DOTS — Indikator progress konfirmasi
   Dots diisi satu per satu saat prediksi konsisten.
   Semua menjadi hijau saat konfirmasi berhasil.
   */
function renderDots(count, allGreen = false) {
    if (!D.dots) return;
    const dots = D.dots.querySelectorAll('.dot');
    dots.forEach((dot, i) => {
        dot.className = 'dot';
        if (allGreen) {
            if (i < CFG.confirmNeeded) dot.classList.add('filled', 'green');
        } else {
            if (i < count) dot.classList.add('filled');
        }
    });
}

/* 
   TEXT-TO-SPEECH
   */
function unlockAudio() {
    if (S.audioUnlocked || !window.speechSynthesis) return;
    const u  = new SpeechSynthesisUtterance(' ');
    u.volume = 0;
    speechSynthesis.speak(u);
    S.audioUnlocked = true;
}

function speak(text) {
    if (!text || !window.speechSynthesis) return;
    S.lastSpeechAt = Date.now();
    speechSynthesis.cancel();

    const u   = new SpeechSynthesisUtterance(text);
    u.lang    = 'id-ID';
    u.rate    = 0.88;
    u.pitch   = 1.0;
    u.volume  = 1.0;

    const v = speechSynthesis.getVoices().find(v => v.lang.startsWith('id'));
    if (v) u.voice = v;

    u.onstart = () => D.wave.classList.add('active');
    u.onend   = () => D.wave.classList.remove('active');
    speechSynthesis.speak(u);

    D.aria.textContent = '';
    setTimeout(() => { D.aria.textContent = text; }, 50);
}

function forceSpeak(text) {
    S.lastSpeechAt = 0;
    speak(text);
}

function maybeSpeak(text, key) {
    const changed = key !== S.lastStatus;
    const expired = Date.now() - S.lastSpeechAt > CFG.speechCooldown;
    if (changed || expired) {
        S.lastStatus = key;
        speak(text);
    }
}

/* 
   UI HELPERS
   */
function setStatus(text, icon) {
    D.statusText.textContent = text;
    D.statusIcon.textContent = icon || '';
}

let _bannerTimer;
function showBanner(nom, wrd) {
    D.nominal.textContent = nom;
    D.words.textContent   = wrd ? '"' + wrd + '"' : '';
    D.banner.classList.add('visible');
    clearTimeout(_bannerTimer);
    _bannerTimer = setTimeout(hideBanner, CFG.bannerDuration);
}
function hideBanner() { D.banner.classList.remove('visible'); }

function setLoading(msg) { D.loadMsg.textContent = msg; }
function hideLoading() {
    D.loadScreen.classList.add('fade-out');
    setTimeout(() => { D.loadScreen.style.display = 'none'; }, 900);
}
function showErr(title, msg) {
    D.loadScreen.style.display = 'none';
    D.errTitle.textContent     = title;
    D.errMsg.textContent       = msg;
    D.errScreen.classList.add('show');
    speak(title + '. ' + msg);
}
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
if (window.speechSynthesis) {
    speechSynthesis.getVoices();
    speechSynthesis.onvoiceschanged = () => speechSynthesis.getVoices();
}

(async () => {
    try { if ('wakeLock' in navigator) await navigator.wakeLock.request('screen'); }
    catch {}
})();
