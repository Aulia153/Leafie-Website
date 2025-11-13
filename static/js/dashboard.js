let tempChart, soilChart;
let cameraOn = true;

// === Fetch History Data ===
async function fetchHistory() {
  const res = await fetch('/api/history?limit=50');
  return res.json();
}

// === Create Charts ===
function createCharts() {
  const tctx = document.getElementById('tempChart').getContext('2d');
  const sctx = document.getElementById('soilChart').getContext('2d');

  tempChart = new Chart(tctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'Suhu (°C)',
        data: [],
        borderColor: '#e53935',
        backgroundColor: 'rgba(229,57,53,0.12)',
        fill: true,
        tension: 0.3
      }]
    },
    options: { animation: false, scales: { y: { beginAtZero: false } } }
  });

  soilChart = new Chart(sctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'Soil Moisture (%)',
        data: [],
        borderColor: '#1b5e20',
        backgroundColor: 'rgba(27,94,32,0.12)',
        fill: true,
        tension: 0.3
      }]
    },
    options: { animation: false, scales: { y: { beginAtZero: true, max: 100 } } }
  });
}

function pushToChart(chart, label, value, maxPoints = 30) {
  chart.data.labels.push(label);
  chart.data.datasets[0].data.push(value);
  if (chart.data.labels.length > maxPoints) {
    chart.data.labels.shift();
    chart.data.datasets[0].data.shift();
  }
  chart.update();
}

function prependActivity(text) {
  const list = document.getElementById('activityList');
  if (!list) return;
  const item = document.createElement('div');
  item.className = 'activity-item';
  const now = new Date().toLocaleString('id-ID', { hour12: false });
  item.innerHTML = `
    <div class="activity-content">
      <div class="activity-time">${now}</div>
      <div class="activity-desc">${text}</div>
    </div>`;
  list.prepend(item);
}

// === Load Initial Data ===
async function loadInitial() {
  createCharts();
  const history = await fetchHistory();
  history.forEach(row => {
    const timePart = (row.timestamp || '').split(' ')[1] || row.timestamp;
    pushToChart(tempChart, timePart, row.temperature);
    pushToChart(soilChart, timePart, row.soil_moisture);
  });
}

// === Poll Sensor Data ===
async function pollSensor() {
  try {
    const res = await fetch('/api/sensor');
    const data = await res.json();

    document.getElementById('tempValue').textContent = `${data.temperature} °C`;
    document.getElementById('timeValue').textContent = data.timestamp;
    document.getElementById('soilValue').textContent = `${data.soil_moisture}%`;
    const soilStatus = data.soil_moisture > 70 ? 'Basah' : (data.soil_moisture < 50 ? 'Kering' : 'Stabil');
    document.getElementById('soilStatus').textContent = soilStatus;

    const timeLabel = data.timestamp.split(' ')[1];
    pushToChart(tempChart, timeLabel, data.temperature);
    pushToChart(soilChart, timeLabel, data.soil_moisture);

    prependActivity(`Sensor update — T: ${data.temperature}°C, Soil: ${data.soil_moisture}%`);
  } catch (err) {
    console.error('poll error', err);
  }
}

// === Toggle Pump ===
async function togglePump() {
  try {
    const res = await fetch('/api/pump', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'TOGGLE' })
    });
    const j = await res.json();
    document.getElementById('pumpState').textContent = j.pump;
    prependActivity(`Pompa diubah menjadi ${j.pump}`);
  } catch (err) {
    console.error('pump error', err);
  }
}

// === Toggle Camera (utama) ===
async function toggleCamera() {
  const cameraFeed = document.getElementById('cameraFeed');
  const btn = document.getElementById('cameraBtn');

  try {
    const res = await fetch('/api/camera', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'TOGGLE' })
    });
    const j = await res.json();

    if (j.camera === "ON") {
      cameraFeed.src = "/video_feed";
      btn.textContent = "Matikan Kamera";
      prependActivity("Kamera dinyalakan");
    } else {
      cameraFeed.src = "/static/image/camera_off.png";
      btn.textContent = "Nyalakan Kamera";
      prependActivity("Kamera dimatikan");
    }
  } catch (err) {
    console.error('camera toggle error', err);
  }
}

// === Leaf camera ON/OFF (lokal visual toggle) ===
function toggleLeafCameraVisual() {
  const leafImg = document.getElementById('leafImage');
  const btn = document.getElementById('leafCameraBtn');
  if (!leafImg || !btn) return;

  if (btn.dataset.on === "true") {
    // === Kamera OFF ===
    leafImg.classList.add("fade-out");
    setTimeout(() => {
      leafImg.src = "/static/image/camera_off.png";
      leafImg.classList.remove("fade-out");
      leafImg.classList.add("fade-in");
    }, 200);

    btn.textContent = "Kamera (OFF)";
    btn.dataset.on = "false";
    btn.classList.remove("btn-on");
    btn.classList.add("btn-off");
    prependActivity("Kamera daun dimatikan");
  } else {
    // === Kamera ON ===
    leafImg.classList.add("fade-out");
    setTimeout(() => {
      leafImg.src = "/static/image/sample_leaf.jpg";
      leafImg.classList.remove("fade-out");
      leafImg.classList.add("fade-in");
    }, 200);

    btn.textContent = "Kamera (ON)";
    btn.dataset.on = "true";
    btn.classList.remove("btn-off");
    btn.classList.add("btn-on");
    prependActivity("Kamera daun dinyalakan (visual)");
  }

  // Efek animasi klik tombol
  btn.classList.add("btn-pressed");
  setTimeout(() => btn.classList.remove("btn-pressed"), 150);
}

// === Deteksi Daun ===
async function detectLeaf() {
  const btn = document.getElementById("detectLeafBtn");
  const statusText = document.getElementById("leafHealthStatus");
  const img = document.getElementById("leafImage");

  if (!btn || !statusText || !img) return;

  btn.disabled = true;
  btn.textContent = "Mendeteksi...";
  statusText.textContent = "Mendeteksi daun...";

  try {
    const res = await fetch("/detect_leaf", { method: "POST" });
    const data = await res.json();

    if (data.status) {
      statusText.textContent = data.status === "Sehat" ? "✅ Sehat" : "❌ Sakit";
      img.src = data.image_url + "?t=" + new Date().getTime(); // hindari cache
      prependActivity(`Deteksi daun: ${data.status}`);
    } else if (data.status === "error") {
      statusText.textContent = "❌ " + (data.message || "Gagal mendeteksi");
      prependActivity(`Deteksi daun gagal: ${data.message || ''}`);
    } else {
      statusText.textContent = "Gagal mendeteksi daun.";
    }
  } catch (err) {
    console.error(err);
    statusText.textContent = "Error deteksi daun.";
    prependActivity("Error saat deteksi daun");
  }

  btn.disabled = false;
  btn.textContent = "Deteksi Daun";
}

// === Init ===
document.addEventListener('DOMContentLoaded', async () => {
  await loadInitial();
  await pollSensor();
  setInterval(pollSensor, 5000);

  const pumpBtn = document.getElementById('pumpBtn');
  if (pumpBtn) pumpBtn.addEventListener('click', togglePump);

  const cameraBtn = document.getElementById('cameraBtn');
  if (cameraBtn) cameraBtn.addEventListener('click', toggleCamera);

  const leafCameraBtn = document.getElementById('leafCameraBtn');
  if (leafCameraBtn) {
    // set initial data-on attribute
    leafCameraBtn.dataset.on = "true";
    leafCameraBtn.addEventListener('click', toggleLeafCameraVisual);
  }

  const detectLeafBtn = document.getElementById('detectLeafBtn');
  if (detectLeafBtn) detectLeafBtn.addEventListener('click', detectLeaf);

  const exportBtn = document.getElementById('exportBtn');
  if (exportBtn) exportBtn.addEventListener('click', () => {
    window.location = '/api/export';
  });
});
