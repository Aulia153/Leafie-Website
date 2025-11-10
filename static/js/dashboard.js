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
    pushToChart(tempChart, row.timestamp.split(' ')[1], row.temperature);
    pushToChart(soilChart, row.timestamp.split(' ')[1], row.soil_moisture);
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

// === Toggle Camera ===
async function toggleCamera() {
  const cameraFeed = document.getElementById('cameraFeed');
  const btn = document.getElementById('cameraBtn');

  if (cameraOn) {
    cameraFeed.src = "{{ url_for('static', filename='image/camera_off.png') }}";
    btn.textContent = "Nyalakan Kamera";
    prependActivity("Kamera dimatikan");
  } else {
    cameraFeed.src = "/video_feed"; // stream dari Flask
    btn.textContent = "Matikan Kamera";
    prependActivity("Kamera dinyalakan");
  }

  cameraOn = !cameraOn;
}

// === Init ===
document.addEventListener('DOMContentLoaded', async () => {
  await loadInitial();
  await pollSensor();
  setInterval(pollSensor, 5000);

  document.getElementById('pumpBtn').addEventListener('click', togglePump);
  document.getElementById('cameraBtn').addEventListener('click', toggleCamera);
  document.getElementById('exportBtn').addEventListener('click', () => {
    window.location = '/api/export';
  });
});
