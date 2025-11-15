let tempChart, soilChart;

// =====================
// ELEMENT CACHE
// =====================
const el = {
  tempValue: document.getElementById('tempValue'),
  timeValue: document.getElementById('timeValue'),
  soilValue: document.getElementById('soilValue'),
  soilStatus: document.getElementById('soilStatus'),
  pumpState: document.getElementById('pumpState'),
  activityList: document.getElementById('activityList'),
  leafImg: document.getElementById('leafImage'),
  btnPump: document.getElementById('pumpBtn'),
  btnDetect: document.getElementById('detectLeafBtn'),
  btnCapture: document.getElementById('captureLeafBtn'),
  leafStatus: document.getElementById('leafHealthStatus'),
  cameraBtn: document.getElementById('cameraBtn'),
  exportBtn: document.getElementById('exportBtn')
};

// Set default leaf image if empty
if (el.leafImg && !el.leafImg.src) {
  el.leafImg.src = '/static/image/leaf_latest.jpg';
}

// =====================
// CHART INIT
// =====================
function createCharts() {
  const chartOptions = {
    animation: false,
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { labels: { boxWidth: 12 } } }
  };

  tempChart = new Chart(document.getElementById('tempChart'), {
    type: 'line',
    data: { labels: [], datasets: [{
      label: 'Suhu (°C)',
      data: [],
      borderColor: '#e53935',
      backgroundColor: 'rgba(229,57,53,0.12)',
      fill: true,
      tension: 0.35
    }]},
    options: chartOptions
  });

  soilChart = new Chart(document.getElementById('soilChart'), {
    type: 'line',
    data: { labels: [], datasets: [{
      label: 'Kelembapan Tanah (%)',
      data: [],
      borderColor: '#1b5e20',
      backgroundColor: 'rgba(27,94,32,0.12)',
      fill: true,
      tension: 0.35
    }]},
    options: {
      ...chartOptions,
      scales: { y: { beginAtZero: true, max: 100 } }
    }
  });
}

// =====================
// CHART UPDATE
// =====================
function pushToChart(chart, label, value, maxPoints = 30) {
  chart.data.labels.push(label);
  chart.data.datasets[0].data.push(value);

  if (chart.data.labels.length > maxPoints) {
    chart.data.labels.shift();
    chart.data.datasets[0].data.shift();
  }

  chart.update('none');
}

// =====================
// LOG ACTIVITY
// =====================
function prependActivity(text) {
  const item = document.createElement('div');
  item.className = 'activity-item';

  const timestamp = new Date().toLocaleString('id-ID', { hour12: false });

  item.innerHTML = `
    <div class="activity-content">
      <div class="activity-time">${timestamp}</div>
      <div class="activity-desc">${text}</div>
    </div>
  `;

  el.activityList?.prepend(item);
}

// =====================
// API → SENSOR POLLING
// =====================
async function pollSensor() {
  try {
    const res = await fetch('/api/sensor');
    const data = await res.json();

    el.tempValue.textContent = `${data.temperature} °C`;
    el.timeValue.textContent = data.timestamp || "-";
    el.soilValue.textContent = `${data.soil_moisture}%`;

    el.soilStatus.textContent =
      data.soil_moisture > 70 ? 'Basah' :
      data.soil_moisture < 50 ? 'Kering' : 'Stabil';

    const timeLabel = data.timestamp?.split(" ")[1] || new Date().toLocaleTimeString('id-ID');

    pushToChart(tempChart, timeLabel, data.temperature);
    pushToChart(soilChart, timeLabel, data.soil_moisture);

  } catch (err) {
    prependActivity("❗ Sensor error");
  }
}

// =====================
// PUMP TOGGLE
// =====================
let pumpLock = false;

async function togglePump() {
  if (pumpLock) return;
  pumpLock = true;

  el.btnPump.disabled = true;
  el.btnPump.textContent = "Memproses...";

  try {
    const res = await fetch('/api/pump', { method: 'POST' });
    const data = await res.json();

    el.pumpState.textContent = data.pump;
    prependActivity(`Pompa diubah menjadi ${data.pump}`);

  } catch {
    prependActivity("❗ Error mengubah status pompa");
  }

  el.btnPump.disabled = false;
  el.btnPump.textContent = "Toggle Pompa";
  pumpLock = false;
}

// =====================
// CAMERA TOGGLE
// =====================
async function toggleCamera() {
  try {
    const res = await fetch('/api/camera', { method: 'POST' });
    const data = await res.json();
    // update button text
    if (el.cameraBtn) {
      el.cameraBtn.textContent = data.camera === "ON" ? "Matikan Kamera" : "Nyalakan Kamera";
    }
    prependActivity(`Kamera diubah menjadi ${data.camera}`);
  } catch (err) {
    prependActivity("❗ Error mengubah status kamera");
  }
}

// =====================
// LEAF CAPTURE
// =====================
async function captureLeaf() {
  try {
    const res = await fetch('/capture_leaf', { method: 'POST' });
    const data = await res.json();

    if (data.success) {
      el.leafImg.src = `${data.path}?t=${Date.now()}`;
      prependActivity("Foto daun berhasil diambil");
      // langsung deteksi otomatis setelah capture
      await detectLeaf(); 
    } else {
      prependActivity("❗ Capture gagal");
    }
  } catch {
    prependActivity("❗ Error capture daun");
  }
}

// =====================
// LEAF DETECTION
// =====================
async function detectLeaf() {
  try {
    el.leafStatus.textContent = "Mendeteksi...";
    el.leafStatus.classList.remove("healthy", "unhealthy");

    const res = await fetch('/api/detect_leaf', {
      method: 'POST'
    });

    const data = await res.json();

    if (!data.success) {
      el.leafStatus.textContent = "Deteksi gagal — " + (data.message || "");
      el.leafStatus.classList.add("unhealthy");
      prependActivity("❗ Gagal deteksi daun");
      return;
    }

    // Update foto daun terbaru
    if (data.image) {
      el.leafImg.src = data.image + "?t=" + Date.now();
    }

    // Tampilkan hasil deteksi
    el.leafStatus.textContent = data.result + " — " + data.message;

    // Jika daun sehat
    if (data.status === "HEALTHY") {
      el.leafStatus.classList.remove("unhealthy");
      el.leafStatus.classList.add("healthy");
      prependActivity(`Hasil deteksi: SEHAT — ${data.result}`);
    }

    // Jika daun tidak sehat
    else {
      el.leafStatus.classList.remove("healthy");
      el.leafStatus.classList.add("unhealthy");

      prependActivity(`Hasil deteksi: TIDAK SEHAT — ${data.result}`);

      // 🔴 Peringatan dini
      alert("⚠️ Daun terdeteksi tidak sehat, segera lakukan pengecekan!");
    }

  } catch (err) {
    console.error("Error detectLeaf:", err);
    el.leafStatus.textContent = "Error deteksi";
    el.leafStatus.classList.add("unhealthy");
    prependActivity("❗ Error saat deteksi daun");
  }
}


// =====================
// EXPORT CSV (download history readings)
// =====================
async function exportCSV() {
  try {
    const res = await fetch('/export_csv');
    if (!res.ok) {
      prependActivity("❗ Gagal export CSV");
      return;
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `readings_${new Date().toISOString().slice(0,19).replace(/[:T]/g,'')}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    prependActivity("Export CSV berhasil");
  } catch (err) {
    prependActivity("❗ Error export CSV");
  }
}

// =====================
// INIT
// =====================
document.addEventListener('DOMContentLoaded', () => {
  createCharts();
  pollSensor();
  setInterval(pollSensor, 5000);

  el.btnPump?.addEventListener('click', togglePump);
  el.btnDetect?.addEventListener('click', detectLeaf);
  el.btnCapture?.addEventListener('click', captureLeaf);
  el.cameraBtn?.addEventListener('click', toggleCamera);
  el.exportBtn?.addEventListener('click', exportCSV);

  // set initial camera btn text based on pumpState element if available
  if (el.cameraBtn && document.getElementById('pumpState')) {
    // no-op; server will control actual state. You may populate camera button text on page render.
  }
});
