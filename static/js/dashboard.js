/* =========================================================
   GLOBAL STATE & HELPER
========================================================= */
let tempChart, soilChart;

const el = {
  tempValue: qs('#tempValue'),
  timeValue: qs('#timeValue'),
  soilValue: qs('#soilValue'),
  soilStatus: qs('#soilStatus'),
  pumpState: qs('#pumpState'),
  activityList: qs('#activityList'),
  leafImg: qs('#leafImage'),

  btnPump: qs('#pumpBtn'),
  btnCapture: qs('#captureLeafBtn'),
  cameraBtn: qs('#cameraBtn'),
  exportBtn: qs('#exportBtn'),

  leafStatus: qs('#leafHealthStatus'),

  filterButtons: '[data-filter]'
};

function qs(sel) {
  return document.querySelector(sel);
}

/* Default leaf image fallback */
if (el.leafImg && (!el.leafImg.src || el.leafImg.src.trim() === '')) {
  el.leafImg.src = '/static/image/leaf_latest.jpg';
}

/* Simple notification (kalau belum ada) */
function showNotification(message, type = 'info') {
  const toast = document.createElement('div');
  toast.style.cssText = `
    position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%);
    background: ${type === 'error' ? '#e74c3c' : type === 'info' ? '#3498db' : '#27ae60'};
    color: white; padding: 14px 28px; border-radius: 10px; z-index: 9999;
    font-size: 16px; font-weight: 500; box-shadow: 0 6px 20px rgba(0,0,0,0.3);
  `;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

/* =========================================================
   CHARTS
========================================================= */
function createCharts() {
  const tempCanvas = qs('#tempChart');
  const soilCanvas = qs('#soilChart');
  if (!tempCanvas || !soilCanvas) return;

  const baseOptions = { animation: false, responsive: true, maintainAspectRatio: false };

  tempChart = new Chart(tempCanvas, {
    type: 'line',
    data: { labels: [], datasets: [{ label: 'Suhu (°C)', data: [], borderColor: '#e53935', backgroundColor: 'rgba(229,57,53,0.12)', fill: true, tension: 0.35 }] },
    options: baseOptions
  });

  soilChart = new Chart(soilCanvas, {
    type: 'line',
    data: { labels: [], datasets: [{ label: 'Kelemb. Tanah (%)', data: [], borderColor: '#1b5e20', backgroundColor: 'rgba(27,94,32,0.12)', fill: true, tension: 0.35 }] },
    options: { ...baseOptions, scales: { y: { beginAtZero: true, max: 100 } } }
  });
}

function pushToChart(chart, label, value, max = 30) {
  if (!chart) return;
  chart.data.labels.push(label);
  chart.data.datasets[0].data.push(value);
  if (chart.data.labels.length > max) {
    chart.data.labels.shift();
    chart.data.datasets[0].data.shift();
  }
  chart.update('none');
}

/* =========================================================
   ACTIVITY LOG & FILTER
========================================================= */
function prependActivity(type, text) {
  if (!el.activityList) return;
  const time = new Date().toLocaleString('id-ID', { hour12: false });
  const div = document.createElement('div');
  div.className = 'activity-item';
  div.dataset.type = type;
  div.innerHTML = `
    <div class="activity-content">
      <div class="activity-time">${time}</div>
      <div class="activity-desc">${text}</div>
    </div>
  `;
  el.activityList.prepend(div);
}

function setupActivityFilter() {
  const buttons = document.querySelectorAll(el.filterButtons);
  if (!buttons.length) return;
  buttons.forEach(btn => {
    btn.addEventListener('click', () => {
      const filter = btn.dataset.filter;
      document.querySelectorAll('.activity-item').forEach(item => {
        item.style.display = (filter === 'all' || item.dataset.type === filter) ? 'block' : 'none';
      });
      buttons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });
}

/* =========================================================
   SENSOR POLLING
========================================================= */
async function pollSensor() {
  try {
    const res = await fetch('/api/sensor');
    const data = await res.json();
    if (!data) return;

    el.tempValue.textContent = `${data.temperature} °C`;
    el.soilValue.textContent = `${data.soil_moisture}%`;
    el.timeValue.textContent = data.timestamp;

    el.soilStatus.textContent =
      data.soil_moisture > 70 ? 'Basah' :
      data.soil_moisture < 50 ? 'Kering' : 'Stabil';

    const timeLabel = data.timestamp.split(' ')[1] || '';
    pushToChart(tempChart, timeLabel, data.temperature);
    pushToChart(soilChart, timeLabel, data.soil_moisture);

  } catch (err) {
    prependActivity('sensor', 'Sensor error');
  }
}

/* =========================================================
   PUMP & CAMERA CONTROL
========================================================= */
let pumpLock = false;

async function togglePump() {
  if (pumpLock) return;
  pumpLock = true;
  el.btnPump.disabled = true;
  el.btnPump.textContent = 'Memproses...';

  try {
    const res = await fetch('/api/pump', { method: 'POST' });
    const data = await res.json();
    el.pumpState.textContent = data.pump;
    prependActivity('pump', `Pompa diubah menjadi ${data.pump}`);
  } catch {
    prependActivity('pump', 'Error mengubah pompa');
  }

  el.btnPump.disabled = false;
  el.btnPump.textContent = 'Toggle Pompa';
  pumpLock = false;
}

async function toggleCamera() {
  try {
    const res = await fetch('/api/camera', { method: 'POST' });
    const data = await res.json();
    el.cameraBtn.textContent = data.camera === 'ON' ? 'Matikan Kamera' : 'Nyalakan Kamera';
    prependActivity('camera', `Kamera ${data.camera}`);
  } catch {
    prependActivity('camera', 'Error mengubah kamera');
  }
}

/* =========================================================
   CAPTURE FOTO DARI ESP32 + OTOMATIS DETEKSI
========================================================= */
document.getElementById('captureLeafBtn')?.addEventListener('click', () => {
  showNotification('Mengambil foto dari kamera...', 'info');

  fetch('/capture_leaf', { method: 'POST' })
    .then(r => r.json())
    .then(d => {
      if (d.success) {
        document.getElementById('leafImage').src = d.path + '?t=' + Date.now();
        showNotification('Foto berhasil diambil! Sedang menganalisis...');
        setTimeout(detectLeafHealth, 1200);
      } else {
        showNotification(d.message || 'Gagal ambil foto', 'error');
      }
    })
    .catch(() => showNotification('ESP32 tidak merespon', 'error'));
});

/* =========================================================
   FUNGSI DETEKSI KESEHATAN DAUN (dipakai capture & upload)
========================================================= */
function detectLeafHealth() {
  const statusEl = document.getElementById('leafHealthStatus');
  statusEl.textContent = 'Memproses...';
  statusEl.style.color = '#f39c12';

  fetch('/api/detect_leaf', { method: 'POST' })
    .then(r => r.json())
    .then(data => {
      if (data.success) {
        const statusText = data.status === 'Sehat' ? 'SEHAT' : 'TIDAK SEHAT';
        statusEl.textContent = `${statusText} - ${data.label}`;
        statusEl.style.color = data.status === 'Sehat' ? '#27ae60' : '#e74c3c';

        // Tampilkan rekomendasi
        const recBox = document.getElementById('recommendationsBox');
        const recList = document.getElementById('recommendationsList');
        recList.innerHTML = '';
        data.recommendations.forEach(rec => {
          const li = document.createElement('li');
          li.textContent = rec;
          li.style.marginBottom = '10px';
          recList.appendChild(li);
        });
        recBox.style.display = 'block';

        showNotification(data.message || 'Analisis selesai!');
      } else {
        statusEl.textContent = 'Gagal menganalisis';
        statusEl.style.color = '#e74c3c';
        showNotification(data.message || 'Error analisis', 'error');
      }
    })
    .catch(() => {
      statusEl.textContent = 'Error jaringan';
      statusEl.style.color = '#e74c3c';
      showNotification('Gagal terhubung ke server', 'error');
    });
}

/* =========================================================
   UPLOAD GAMBAR DARI HP/LAPTOP + LANGSUNG KLASIFIKASI
========================================================= */
function uploadLeafImage() {
  const fileInput = document.getElementById('leafFileInput');
  const file = fileInput.files[0];

  if (!file) {
    showNotification('Pilih file terlebih dahulu', 'error');
    return;
  }

  if (!['image/jpeg', 'image/jpg', 'image/png'].includes(file.type)) {
    showNotification('Format harus JPG atau PNG', 'error');
    return;
  }

  if (file.size > 16 * 1024 * 1024) {
    showNotification('Ukuran maksimal 16MB', 'error');
    return;
  }

  // Ubah tombol jadi loading
  const btn = document.getElementById('uploadLeafBtn');
  btn.textContent = 'Menganalisis...';
  btn.disabled = true;

  showNotification('Sedang menghapus background & menganalisis... (3–6 detik)', 'info');

  const statusEl = document.getElementById('leafHealthStatus');
  statusEl.textContent = 'Memproses...';
  statusEl.style.color = '#f39c12';

  const formData = new FormData();
  formData.append('image', file);

  fetch('/upload_leaf', { method: 'POST', body: formData })
    .then(res => {
      if (!res.ok) throw new Error('Server error');
      return res.json();
    })
    .then(data => {
      if (data.success) {
        document.getElementById('leafImage').src = data.image + '?t=' + Date.now();

        const statusText = data.status === 'Sehat' ? 'SEHAT' : 'TIDAK SEHAT';
        statusEl.textContent = `${statusText} - ${data.label}`;
        statusEl.style.color = data.status === 'Sehat' ? '#27ae60' : '#e74c3c';

        const recBox = document.getElementById('recommendationsBox');
        const recList = document.getElementById('recommendationsList');
        recList.innerHTML = '';
        data.recommendations.forEach(rec => {
          const li = document.createElement('li');
          li.textContent = rec;
          li.style.marginBottom = '10px';
          recList.appendChild(li);
        });
        recBox.style.display = 'block';

        showNotification(data.message || 'Analisis selesai!');
      } else {
        throw new Error(data.message || 'Gagal');
      }
    })
    .catch(err => {
      console.error(err);
      statusEl.textContent = 'Gagal menganalisis';
      statusEl.style.color = '#e74c3c';
      showNotification(err.message || 'Terjadi kesalahan', 'error');
    })
    .finally(() => {
      btn.textContent = 'Upload Gambar Daun';
      btn.disabled = false;
      fileInput.value = '';
    });
}

/* =========================================================
   EXPORT CSV
========================================================= */
async function exportCSV() {
  try {
    const res = await fetch('/export_csv');
    if (!res.ok) throw '';
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `activity_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    prependActivity('general', 'Export CSV berhasil');
  } catch {
    prependActivity('general', 'Gagal export CSV');
  }
}

/* =========================================================
   INIT — JALAN SAAT PAGE LOADED
========================================================= */
document.addEventListener('DOMContentLoaded', () => {
  createCharts();
  pollSensor();
  setInterval(pollSensor, 5000);

  el.btnPump?.addEventListener('click', togglePump);
  el.cameraBtn?.addEventListener('click', toggleCamera);
  el.exportBtn?.addEventListener('click', exportCSV);

  // Upload button trigger
  document.getElementById('uploadLeafBtn')?.addEventListener('click', () => {
    document.getElementById('leafFileInput').click();
  });

  document.getElementById('leafFileInput')?.addEventListener('change', () => {
    if (document.getElementById('leafFileInput').files.length > 0) {
      uploadLeafImage();
    }
  });

  setupActivityFilter();
});