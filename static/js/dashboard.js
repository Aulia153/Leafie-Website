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
  leafStatus: document.getElementById('leafHealthStatus')
};

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
    el.soilValue.textContent = `${data.soil}%`;

    el.soilStatus.textContent =
      data.soil > 70 ? 'Basah' :
      data.soil < 50 ? 'Kering' : 'Stabil';

    const timeLabel = data.timestamp?.split(" ")[1] || new Date().toLocaleTimeString('id-ID');

    pushToChart(tempChart, timeLabel, data.temperature);
    pushToChart(soilChart, timeLabel, data.soil);

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
  el.btnPump.textContent = "Ubah Pompa";
  pumpLock = false;
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
    } else {
      prependActivity("❗ Capture gagal");
    }
  } catch {
    prependActivity("❗ Error capture daun");
  }
}

// =====================
// LEAF DETECTION (DISABLED, ROUTE BELUM ADA)
// =====================
async function detectLeaf() {
  alert("Fitur deteksi daun belum diaktifkan. Tambahkan route /detect_leaf di backend.");
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
});
