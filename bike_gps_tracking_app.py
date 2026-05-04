# -*- coding: utf-8 -*-
"""
Bike GPS Tracking Website
自行車即時 GPS 追蹤網站

功能：
1. /track   ：手機端頁面，取得 GPS 並回傳到伺服器
2. /monitor ：電腦端監控頁面，顯示地圖、預定路線、即時位置、已走軌跡
3. /api/location ：手機端上傳位置 API
4. /api/latest   ：電腦端取得最新位置 API
5. /api/route    ：取得預設路線 API

安裝：
    pip install flask

執行：
    python bike_gps_tracking_app.py

使用：
    電腦端監控頁面：
        http://你的電腦IP:5000/monitor

    手機端追蹤頁面：
        http://你的電腦IP:5000/track?rider=rider01

注意：
1. 手機與電腦需要在同一個 Wi-Fi，或你的電腦伺服器需要能被外網連到。
2. 手機瀏覽器取得 GPS 時，正式部署通常需要 HTTPS；但在 localhost 或部分區網測試環境可能可用。
3. 山區斷網時，手機端會先把資料存在 localStorage，恢復網路後批次補傳。
"""

from flask import Flask, request, jsonify, Response
from datetime import datetime, timezone
import csv
import os

app = Flask(__name__)

# =========================
# 基本設定
# =========================
DATA_DIR = "tracking_data"
CSV_FILE = os.path.join(DATA_DIR, "gps_log.csv")
os.makedirs(DATA_DIR, exist_ok=True)

# 記憶體中的最新位置與軌跡
# 結構：
# latest_locations = {
#   "rider01": {
#       "rider": "rider01",
#       "lat": 24.123,
#       "lng": 120.456,
#       "speed": 8.2,
#       "accuracy": 12.5,
#       "timestamp": "2026-05-03T10:00:00Z",
#       "server_time": "..."
#   }
# }
latest_locations = {}
tracks = {}


# =========================
# 預定路線設定
# 你可以把這裡改成真正比賽路線的 GPS 點
# 格式：[lat, lng]
# =========================
PLANNED_ROUTE = [
    [24.13720, 120.68690],
    [24.13820, 120.68850],
    [24.13980, 120.69010],
    [24.14110, 120.69200],
    [24.14280, 120.69420],
    [24.14420, 120.69650],
    [24.14600, 120.69910],
]


# =========================
# 工具函式
# =========================
def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def append_csv(data):
    file_exists = os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "server_time",
                "client_time",
                "rider",
                "lat",
                "lng",
                "speed_mps",
                "accuracy_m",
                "altitude_m",
                "heading_deg",
            ])
        writer.writerow([
            data.get("server_time", ""),
            data.get("timestamp", ""),
            data.get("rider", ""),
            data.get("lat", ""),
            data.get("lng", ""),
            data.get("speed", ""),
            data.get("accuracy", ""),
            data.get("altitude", ""),
            data.get("heading", ""),
        ])


def validate_location(payload):
    if not isinstance(payload, dict):
        return False, "Payload must be JSON object."

    rider = payload.get("rider", "rider01")
    lat = payload.get("lat")
    lng = payload.get("lng")

    try:
        lat = float(lat)
        lng = float(lng)
    except Exception:
        return False, "lat/lng must be numbers."

    if not (-90 <= lat <= 90):
        return False, "lat out of range."
    if not (-180 <= lng <= 180):
        return False, "lng out of range."

    payload["rider"] = str(rider)
    payload["lat"] = lat
    payload["lng"] = lng

    for key in ["speed", "accuracy", "altitude", "heading"]:
        if payload.get(key) is not None:
            try:
                payload[key] = float(payload[key])
            except Exception:
                payload[key] = None

    return True, payload


# =========================
# API
# =========================
@app.route("/api/location", methods=["POST"])
def api_location():
    """手機端上傳 GPS 位置。"""
    payload = request.get_json(silent=True)
    ok, result = validate_location(payload)
    if not ok:
        return jsonify({"ok": False, "error": result}), 400

    data = result
    data["server_time"] = utc_now_iso()
    data.setdefault("timestamp", data["server_time"])

    rider = data["rider"]
    latest_locations[rider] = data
    tracks.setdefault(rider, []).append(data)

    # 避免記憶體無限增加，只保留最近 5000 筆
    if len(tracks[rider]) > 5000:
        tracks[rider] = tracks[rider][-5000:]

    append_csv(data)

    return jsonify({"ok": True, "received": data})


@app.route("/api/bulk_location", methods=["POST"])
def api_bulk_location():
    """手機端斷線後批次補傳 GPS 位置。"""
    payload = request.get_json(silent=True)
    if not isinstance(payload, list):
        return jsonify({"ok": False, "error": "Payload must be a list."}), 400

    received = 0
    errors = []

    for item in payload:
        ok, result = validate_location(item)
        if not ok:
            errors.append(result)
            continue

        data = result
        data["server_time"] = utc_now_iso()
        data.setdefault("timestamp", data["server_time"])
        rider = data["rider"]

        latest_locations[rider] = data
        tracks.setdefault(rider, []).append(data)
        append_csv(data)
        received += 1

    for rider in list(tracks.keys()):
        if len(tracks[rider]) > 5000:
            tracks[rider] = tracks[rider][-5000:]

    return jsonify({"ok": True, "received_count": received, "errors": errors})


@app.route("/api/latest")
def api_latest():
    """電腦端取得所有騎士最新位置。"""
    return jsonify({
        "ok": True,
        "latest": latest_locations,
        "server_time": utc_now_iso(),
    })


@app.route("/api/track")
def api_track():
    """電腦端取得指定騎士軌跡。"""
    rider = request.args.get("rider", "rider01")
    return jsonify({
        "ok": True,
        "rider": rider,
        "track": tracks.get(rider, []),
    })


@app.route("/api/route")
def api_route():
    """取得預定騎行路線。"""
    return jsonify({
        "ok": True,
        "route": PLANNED_ROUTE,
    })


@app.route("/")
def index():
    return Response(INDEX_HTML, mimetype="text/html")


@app.route("/track")
def track_page():
    return Response(TRACK_HTML, mimetype="text/html")


@app.route("/monitor")
def monitor_page():
    return Response(MONITOR_HTML, mimetype="text/html")


# =========================
# 首頁
# =========================
INDEX_HTML = r"""
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Bike GPS Tracking</title>
  <style>
    body {
      font-family: Arial, 'Microsoft JhengHei', sans-serif;
      padding: 32px;
      line-height: 1.6;
    }
    a {
      display: block;
      margin: 12px 0;
      font-size: 20px;
    }
    code {
      display: inline-block;
      background: #eee;
      padding: 4px 8px;
      border-radius: 4px;
      margin: 4px 0 12px 0;
    }
    .section {
      margin-top: 24px;
    }
  </style>
</head>
<body>
  <h1>Bike GPS Tracking</h1>
  <p>自行車 GPS 即時追蹤系統</p>

  <div class="section">
    <h2>監控端</h2>
    <a href="/monitor">電腦端多人監控頁面 /monitor</a>
    <code>https://bike-gps-tracker.onrender.com/monitor</code>
  </div>

  <div class="section">
    <h2>手機端追蹤頁面</h2>
    <a href="/track?rider=rider01">騎手 1：手機端追蹤頁面 /track?rider=rider01</a>
    <code>https://bike-gps-tracker.onrender.com/track?rider=rider01</code>

    <a href="/track?rider=rider02">騎手 2：手機端追蹤頁面 /track?rider=rider02</a>
    <code>https://bike-gps-tracker.onrender.com/track?rider=rider02</code>
  </div>

  <div class="section">
    <h2>使用方式</h2>
    <p>騎手 1 開啟 rider01 連結並按下「開始追蹤」。</p>
    <p>騎手 2 開啟 rider02 連結並按下「開始追蹤」。</p>
    <p>監控者開啟 /monitor，即可同時查看 rider01 與 rider02 的即時位置。</p>
  </div>
</body>
</html>
"""


# =========================
# 手機端追蹤頁面
# =========================
TRACK_HTML = r"""
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>手機 GPS 追蹤端</title>
  <style>
    body {
      font-family: Arial, 'Microsoft JhengHei', sans-serif;
      margin: 0;
      padding: 18px;
      background: #f5f5f5;
      color: #222;
    }
    .card {
      background: white;
      border-radius: 14px;
      padding: 16px;
      margin-bottom: 14px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    button {
      width: 100%;
      padding: 14px;
      margin-top: 8px;
      border: none;
      border-radius: 10px;
      font-size: 18px;
      cursor: pointer;
    }
    .start { background: #1976d2; color: white; }
    .stop { background: #c62828; color: white; }
    .row { margin: 8px 0; }
    .label { color: #666; font-size: 14px; }
    .value { font-size: 18px; font-weight: bold; }
    .online { color: #2e7d32; }
    .offline { color: #c62828; }
    .small { font-size: 13px; color: #666; }
  </style>
</head>
<body>
  <div class="card">
    <h2>手機 GPS 追蹤端</h2>
    <div class="row"><span class="label">Rider ID：</span><span id="rider" class="value"></span></div>
    <div class="row"><span class="label">狀態：</span><span id="status" class="value">尚未開始</span></div>
    <div class="row"><span class="label">網路：</span><span id="netStatus" class="value"></span></div>
    <div class="row"><span class="label">本地暫存：</span><span id="bufferCount" class="value">0</span> 筆</div>
    <button class="start" onclick="startTracking()">開始追蹤</button>
    <button class="stop" onclick="stopTracking()">停止追蹤</button>
  </div>

  <div class="card">
    <h3>目前 GPS</h3>
    <div class="row"><span class="label">Latitude：</span><span id="lat" class="value">--</span></div>
    <div class="row"><span class="label">Longitude：</span><span id="lng" class="value">--</span></div>
    <div class="row"><span class="label">Speed：</span><span id="speed" class="value">--</span> m/s</div>
    <div class="row"><span class="label">Accuracy：</span><span id="accuracy" class="value">--</span> m</div>
    <div class="row"><span class="label">最後更新：</span><span id="time" class="value">--</span></div>
  </div>

  <div class="card small">
    <p>建議設定：</p>
    <p>GPS 取樣：每 5 秒左右由瀏覽器決定。</p>
    <p>上傳：每次取得位置就嘗試上傳；若山區斷網，會先存在手機 localStorage，恢復網路後補傳。</p>
    <p>長時間騎行建議搭配行動電源，並關閉螢幕。</p>
  </div>

<script>
const params = new URLSearchParams(window.location.search);
const riderId = params.get('rider') || 'rider01';
document.getElementById('rider').textContent = riderId;

let watchId = null;
const BUFFER_KEY = 'bike_gps_buffer_' + riderId;

function setStatus(text, cls) {
  const el = document.getElementById('status');
  el.textContent = text;
  el.className = 'value ' + (cls || '');
}

function updateNetStatus() {
  const el = document.getElementById('netStatus');
  if (navigator.onLine) {
    el.textContent = 'Online';
    el.className = 'value online';
  } else {
    el.textContent = 'Offline';
    el.className = 'value offline';
  }
}

function getBuffer() {
  try {
    return JSON.parse(localStorage.getItem(BUFFER_KEY) || '[]');
  } catch (e) {
    return [];
  }
}

function setBuffer(arr) {
  localStorage.setItem(BUFFER_KEY, JSON.stringify(arr));
  document.getElementById('bufferCount').textContent = arr.length;
}

function addToBuffer(data) {
  const arr = getBuffer();
  arr.push(data);
  // 避免手機 localStorage 爆掉，只保留最近 5000 筆
  setBuffer(arr.slice(-5000));
}

async function uploadLocation(data) {
  try {
    const res = await fetch('/api/location', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Upload failed');
    return true;
  } catch (err) {
    return false;
  }
}

async function flushBuffer() {
  if (!navigator.onLine) return;
  const arr = getBuffer();
  if (arr.length === 0) return;

  try {
    const res = await fetch('/api/bulk_location', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(arr)
    });
    if (res.ok) {
      setBuffer([]);
    }
  } catch (err) {
    // 保留資料，等下次再傳
  }
}

async function handlePosition(pos) {
  const c = pos.coords;
  const data = {
    rider: riderId,
    lat: c.latitude,
    lng: c.longitude,
    speed: c.speed,
    accuracy: c.accuracy,
    altitude: c.altitude,
    heading: c.heading,
    timestamp: new Date(pos.timestamp).toISOString()
  };

  document.getElementById('lat').textContent = data.lat.toFixed(7);
  document.getElementById('lng').textContent = data.lng.toFixed(7);
  document.getElementById('speed').textContent = data.speed === null ? '--' : data.speed.toFixed(2);
  document.getElementById('accuracy').textContent = data.accuracy === null ? '--' : data.accuracy.toFixed(1);
  document.getElementById('time').textContent = new Date().toLocaleTimeString();

  await flushBuffer();
  const ok = await uploadLocation(data);
  if (!ok) {
    addToBuffer(data);
    setStatus('追蹤中，但目前無法上傳，已暫存', 'offline');
  } else {
    setStatus('追蹤中，位置已上傳', 'online');
  }
}

function handleError(err) {
  let msg = 'GPS 錯誤';
  if (err.code === 1) msg = '使用者拒絕 GPS 權限';
  if (err.code === 2) msg = '無法取得位置';
  if (err.code === 3) msg = 'GPS 逾時';
  setStatus(msg, 'offline');
}

function startTracking() {
  if (!navigator.geolocation) {
    setStatus('此瀏覽器不支援 GPS', 'offline');
    return;
  }

  if (watchId !== null) {
    setStatus('已經在追蹤中', 'online');
    return;
  }

  setStatus('正在取得 GPS...', '');

  watchId = navigator.geolocation.watchPosition(
    handlePosition,
    handleError,
    {
      enableHighAccuracy: true,
      maximumAge: 3000,
      timeout: 15000
    }
  );
}

function stopTracking() {
  if (watchId !== null) {
    navigator.geolocation.clearWatch(watchId);
    watchId = null;
  }
  setStatus('已停止追蹤', '');
}

window.addEventListener('online', () => {
  updateNetStatus();
  flushBuffer();
});
window.addEventListener('offline', updateNetStatus);

updateNetStatus();
setBuffer(getBuffer());
setInterval(() => {
  updateNetStatus();
  flushBuffer();
}, 15000);
</script>
</body>
</html>
"""


# =========================
# 電腦端監控頁面
# =========================
MONITOR_HTML = r"""
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>自行車 GPS 監控端</title>

  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIINfQIB3dBzGM9XJ5edJ1A6rw0F1QagQAY="
    crossorigin=""
  />
  <script
    src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    crossorigin=""
  ></script>

  <style>
    html, body {
      height: 100%;
      margin: 0;
      font-family: Arial, 'Microsoft JhengHei', sans-serif;
    }
    #map {
      height: 100%;
      width: 100%;
    }
    .panel {
      position: absolute;
      top: 12px;
      left: 12px;
      z-index: 999;
      background: white;
      padding: 14px 16px;
      border-radius: 14px;
      box-shadow: 0 2px 12px rgba(0,0,0,0.25);
      min-width: 280px;
      max-width: 380px;
    }
    .panel h2 {
      margin: 0 0 8px 0;
      font-size: 20px;
    }
    .row {
      margin: 6px 0;
      font-size: 14px;
    }
    .label {
      color: #666;
    }
    .value {
      font-weight: bold;
    }
    .online { color: #2e7d32; }
    .offline { color: #c62828; }
    .weak { color: #ef6c00; }
    select, button {
      margin-top: 8px;
      padding: 8px;
      border-radius: 8px;
      border: 1px solid #bbb;
    }
    button { cursor: pointer; }
  </style>
</head>
<body>
  <div id="map"></div>

  <div class="panel">
    <h2>自行車 GPS 監控</h2>
    <div class="row"><span class="label">Rider：</span><span id="rider" class="value">rider01</span></div>
    <div class="row"><span class="label">狀態：</span><span id="status" class="value">等待資料</span></div>
    <div class="row"><span class="label">Latitude：</span><span id="lat" class="value">--</span></div>
    <div class="row"><span class="label">Longitude：</span><span id="lng" class="value">--</span></div>
    <div class="row"><span class="label">Speed：</span><span id="speed" class="value">--</span> km/h</div>
    <div class="row"><span class="label">Accuracy：</span><span id="accuracy" class="value">--</span> m</div>
    <div class="row"><span class="label">最後更新：</span><span id="lastUpdate" class="value">--</span></div>
    <div class="row"><span class="label">距上次回傳：</span><span id="age" class="value">--</span></div>
    <button onclick="fitRoute()">縮放到路線</button>
    <button onclick="followRider = !followRider">切換跟隨騎士</button>
  </div>

<script>
let map;
let routeLine;
let trackLine;
let riderMarker;
let plannedRoute = [];
let currentRider = 'rider01';
let followRider = true;
let lastServerTimestamp = null;

const routeStyle = {
  color: '#1976d2',
  weight: 5,
  opacity: 0.75
};

const trackStyle = {
  color: '#d32f2f',
  weight: 4,
  opacity: 0.85
};

function initMap() {
  map = L.map('map').setView([24.13720, 120.68690], 14);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);

  trackLine = L.polyline([], trackStyle).addTo(map);
}

async function loadRoute() {
  const res = await fetch('/api/route');
  const data = await res.json();
  plannedRoute = data.route || [];

  if (routeLine) routeLine.remove();
  routeLine = L.polyline(plannedRoute, routeStyle).addTo(map);

  if (plannedRoute.length > 0) {
    fitRoute();
  }
}

function fitRoute() {
  if (routeLine && plannedRoute.length > 0) {
    map.fitBounds(routeLine.getBounds(), { padding: [30, 30] });
  }
}

function setStatus(text, cls) {
  const el = document.getElementById('status');
  el.textContent = text;
  el.className = 'value ' + (cls || '');
}

function updateInfo(loc) {
  document.getElementById('rider').textContent = loc.rider || currentRider;
  document.getElementById('lat').textContent = loc.lat.toFixed(7);
  document.getElementById('lng').textContent = loc.lng.toFixed(7);

  let speedKmh = null;
  if (loc.speed !== null && loc.speed !== undefined) {
    speedKmh = loc.speed * 3.6;
  }
  document.getElementById('speed').textContent = speedKmh === null ? '--' : speedKmh.toFixed(1);
  document.getElementById('accuracy').textContent = loc.accuracy === null || loc.accuracy === undefined ? '--' : loc.accuracy.toFixed(1);

  const t = loc.server_time || loc.timestamp;
  lastServerTimestamp = t ? new Date(t) : new Date();
  document.getElementById('lastUpdate').textContent = lastServerTimestamp.toLocaleTimeString();
}

function updateAgeStatus() {
  if (!lastServerTimestamp) {
    document.getElementById('age').textContent = '--';
    return;
  }

  const ageSec = (new Date() - lastServerTimestamp) / 1000;
  document.getElementById('age').textContent = ageSec.toFixed(0) + ' 秒';

  if (ageSec < 30) {
    setStatus('Online，即時追蹤中', 'online');
  } else if (ageSec < 180) {
    setStatus('訊號偏弱或更新延遲', 'weak');
  } else {
    setStatus('Offline，顯示最後位置', 'offline');
  }
}

async function updateLatest() {
  try {
    const res = await fetch('/api/latest');
    const data = await res.json();
    const latest = data.latest || {};
    const loc = latest[currentRider];

    if (!loc) {
      setStatus('等待手機端資料', 'weak');
      return;
    }

    const latlng = [loc.lat, loc.lng];

    if (!riderMarker) {
      riderMarker = L.marker(latlng).addTo(map).bindPopup(currentRider);
    } else {
      riderMarker.setLatLng(latlng);
    }

    updateInfo(loc);

    if (followRider) {
      map.panTo(latlng);
    }
  } catch (err) {
    setStatus('伺服器連線錯誤', 'offline');
  }
}

async function updateTrack() {
  try {
    const res = await fetch('/api/track?rider=' + encodeURIComponent(currentRider));
    const data = await res.json();
    const track = data.track || [];
    const latlngs = track.map(p => [p.lat, p.lng]);
    trackLine.setLatLngs(latlngs);
  } catch (err) {
    // ignore
  }
}

initMap();
loadRoute();
setInterval(updateLatest, 2000);
setInterval(updateTrack, 5000);
setInterval(updateAgeStatus, 1000);
updateLatest();
updateTrack();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    # host="0.0.0.0" 代表讓同一個 Wi-Fi 的手機也能連進來
    app.run(host="0.0.0.0", port=5000, debug=True)
