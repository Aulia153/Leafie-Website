/* =========================================================
   GLOBAL STATE
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
  uploadLeaf: qs('#uploadLeafInput'),

  filterButtons: '[data-filter]'
};

function qs(sel) {
  return document.querySelector(sel);
}

/* Default leaf image fallback */
if (el.leafImg && (!el.leafImg.src || el.leafImg.src.trim() === '')) {
  el.leafImg.src = '/static/image/leaf_latest.jpg';
}

/* =========================================================
   CHARTS
========================================================= */
function createCharts() {
  const tempCanvas = qs('#tempChart');
  const soilCanvas = qs('#soilChart');
  if (!tempCanvas || !soilCanvas) return;

  const baseOptions = {
    animation: false,
    responsive: true,
    maintainAspectRatio: false
  };

  tempChart = new Chart(tempCanvas, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'Suhu (°C)',
        data: [],
        borderColor: '#e53935',
        backgroundColor: 'rgba(229,57,53,0.12)',
        fill: true,
        tension: 0.35
      }]
    },
    options: baseOptions
  });

  soilChart = new Chart(soilCanvas, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'Kelembapan Tanah (%)',
        data: [],
        borderColor: '#1b5e20',
        backgroundColor: 'rgba(27,94,32,0.12)',
        fill: true,
        tension: 0.35
      }]
    },
    options: {
      ...baseOptions,
      scales: { y: { beginAtZero: true, max: 100 } }
    }
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
        item.style.display =
          filter === 'all' || item.dataset.type === filter ? 'block' : 'none';
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
      data.soil_moisture < 50 ? 'Kering' :
      'Stabil';

    const timeLabel = data.timestamp.split(' ')[1];
    pushToChart(tempChart, timeLabel, data.temperature);
    pushToChart(soilChart, timeLabel, data.soil_moisture);

  } catch (err) {
    prependActivity('sensor', '❗ Sensor error');
  }
}

/* =========================================================
   PUMP
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
    prependActivity('pump', '❗ Error mengubah pompa');
  }

  el.btnPump.disabled = false;
  el.btnPump.textContent = 'Toggle Pompa';
  pumpLock = false;
}

/* =========================================================
   CAMERA
========================================================= */
async function toggleCamera() {
  try {
    const res = await fetch('/api/camera', { method: 'POST' });
    const data = await res.json();

    el.cameraBtn.textContent =
      data.camera === 'ON' ? 'Matikan Kamera' : 'Nyalakan Kamera';

    prependActivity('camera', `Kamera ${data.camera}`);

  } catch {
    prependActivity('camera', '❗ Error mengubah kamera');
  }
}

/* =========================================================
   CAPTURE + AUTO-DETECT
========================================================= */
async function captureLeaf() {
  try {
    const res = await fetch('/capture_leaf', { method: 'POST' });
    const data = await res.json();

    if (!data.success) {
      prependActivity('camera', '❗ Capture gagal');
      return;
    }

    el.leafImg.src = `${data.path}?t=${Date.now()}`;
    prependActivity('camera', 'Foto daun diambil');

    /* AUTO-DETECT */
    await detectLeaf();

  } catch {
    prependActivity('camera', '❗ Error capture daun');
  }
}

/* =========================================================
   UPLOAD LEAF IMAGE (MANUAL)
========================================================= */
async function uploadLeafImage() {
  const file = el.uploadLeaf?.files?.[0];
  if (!file) return;

  // Preview langsung sebelum diproses
  el.leafImg.src = URL.createObjectURL(file);
  el.leafStatus.textContent = 'Mengunggah & menganalisis...';
  el.leafStatus.classList.remove('healthy', 'unhealthy');

  const formData = new FormData();
  formData.append('image', file);

  try {
    const res = await fetch('/upload_leaf', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();

    if (!data.success) {
      el.leafStatus.textContent = 'Upload gagal';
      prependActivity('leaf', '❗ Upload daun gagal');
      return;
    }

    // Update foto jika backend memberikan path
    if (data.image) el.leafImg.src = `${data.image}?t=${Date.now()}`;

    el.leafStatus.textContent = `${data.result} — ${data.message}`;
    if (data.status === 'HEALTHY') {
      el.leafStatus.classList.add('healthy');
      prependActivity('leaf', `Upload & deteksi: SEHAT — ${data.result}`);
    } else {
      el.leafStatus.classList.add('unhealthy');
      prependActivity('leaf', `Upload & deteksi: TIDAK SEHAT — ${data.result}`);
      alert('⚠️ Hasil menunjukkan daun tidak sehat!');
    }

  } catch (err) {
    console.error(err);
    el.leafStatus.textContent = 'Error deteksi';
    prependActivity('leaf', '❗ Error upload / deteksi daun');
  }
}

/* =========================================================
   LEAF HEALTH DETECTION
========================================================= */
async function detectLeaf() {
  try {
    el.leafStatus.textContent = 'Mendeteksi...';
    el.leafStatus.classList.remove('healthy', 'unhealthy');

    const res = await fetch('/api/detect_leaf', { method: 'POST' });
    const data = await res.json();

    if (!data.success) {
      el.leafStatus.textContent = 'Deteksi gagal';
      el.leafStatus.classList.add('unhealthy');
      prependActivity('leaf', '❗ Deteksi daun gagal');
      return;
    }

    if (data.image) el.leafImg.src = `${data.image}?t=${Date.now()}`;

    el.leafStatus.textContent = `${data.result} — ${data.message}`;

    if (data.status === 'HEALTHY') {
      el.leafStatus.classList.add('healthy');
      prependActivity('leaf', `Hasil deteksi: SEHAT — ${data.result}`);
    } else {
      el.leafStatus.classList.add('unhealthy');
      prependActivity('leaf', `Hasil deteksi: TIDAK SEHAT — ${data.result}`);
      alert('⚠️ Daun tidak sehat!');
    }

  } catch {
    el.leafStatus.textContent = 'Error deteksi';
    el.leafStatus.classList.add('unhealthy');
    prependActivity('leaf', '❗ Error deteksi daun');
  }
}

/* =========================================================
   EXPORT CSV
========================================================= */
async function exportCSV() {
  try {
    const res = await fetch('/export_csv');
    if (!res.ok) {
      prependActivity('general', '❗ Export gagal');
      return;
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `activity_${Date.now()}.csv`;
    a.click();

    URL.revokeObjectURL(url);
    prependActivity('general', 'Export CSV berhasil');

  } catch {
    prependActivity('general', '❗ Error export CSV');
  }
}

/* =========================================================
   INIT
========================================================= */
document.addEventListener('DOMContentLoaded', () => {
  createCharts();
  pollSensor();
  setInterval(pollSensor, 5000);

  el.btnPump?.addEventListener('click', togglePump);
  el.btnCapture?.addEventListener('click', captureLeaf);
  el.uploadLeaf?.addEventListener('change', uploadLeafImage);
  el.cameraBtn?.addEventListener('click', toggleCamera);
  el.exportBtn?.addEventListener('click', exportCSV);

  setupActivityFilter();
});
