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

部署用檔案：
requirements.txt:
    flask
    gunicorn

Procfile:
    web: gunicorn bike_gps_tracking_app:app
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

# 最新位置與軌跡資料存在記憶體
# 注意：Render 若重啟，這些記憶體資料會消失
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
    """
    將 GPS 資料附加寫入 CSV。
    注意：雲端平台的檔案系統不一定適合長期保存資料。
    正式版建議改用 PostgreSQL / Firebase / Supabase。
    """
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
    """
    檢查手機端傳來的 GPS 資料是否合理。
    """
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
    """
    手機端上傳單筆 GPS 位置。
    """
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

    return jsonify({
        "ok": True,
        "received": data
    })


@app.route("/api/bulk_location", methods=["POST"])
def api_bulk_location():
    """
    手機端斷線後批次補傳 GPS 位置。
    """
    payload = request.get_json(silent=True)

    if not isinstance(payload, list):
        return jsonify({
            "ok": False,
            "error": "Payload must be a list."
        }), 400

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

    return jsonify({
        "ok": True,
        "received_count": received,
        "errors": errors
    })


@app.route("/api/latest")
def api_latest():
    """
    電腦監控端取得所有騎士最新位置。
    """
    return jsonify({
        "ok": True,
        "latest": latest_locations,
        "server_time": utc_now_iso()
    })


@app.route("/api/track")
def api_track():
    """
    電腦監控端取得指定騎士軌跡。
    """
    rider = request.args.get("rider", "rider01")

    return jsonify({
        "ok": True,
        "rider": rider,
        "track": tracks.get(rider, [])
    })


@app.route("/api/route")
def api_route():
    """
    取得預定騎行路線。
    """
    return jsonify({
        "ok": True,
        "route": PLANNED_ROUTE
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
      background: #eee;
      padding: 2px 6px;
      border-radius: 4px;
    }
  </style>
</head>
<body>
  <h1>Bike GPS Tracking</h1>
  <p>自行車 GPS 即時追蹤系統</p>

  <a href="/monitor">電腦端監控頁面 /monitor</a>
  <a href="/track?rider=rider01">手機端追蹤頁面 /track?rider=rider01</a>

  <p>部署到 Render 之後，網址會類似：</p>
  <code>https://bike-gps-tracker.onrender.com/track?rider=rider01</code>
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

    .start {
      background: #1976d2;
      color: white;
    }

    .stop {
      background: #c62828;
      color: white;
    }

    .row {
      margin: 8px 0;
    }

    .label {
      color: #666;
      font-size: 14px;
    }

    .value {
      font-size: 18px;
      font-weight: bold;
    }

    .online {
      color: #2e7d32;
    }

    .offline {
      color: #c62828;
    }

    .small {
      font-size: 13px;
      color: #666;
    }
  </style>
</head>

<body>
  <div class="card">
    <h2>手機 GPS 追蹤端</h2>

    <div class="row">
      <span class="label">Rider ID：</span>
      <span id="rider" class="value"></span>
    </div>

    <div class="row">
      <span class="label">狀態：</span>
      <span id="status" class="value">尚未開始</span>
    </div>

    <div class="row">
      <span class="label">網路：</span>
      <span id="netStatus" class="value"></span>
    </div>

    <div class="row">
      <span class="label">本地暫存：</span>
      <span id="bufferCount" class="value">0</span> 筆
    </div>

    <button class="start" onclick="startTracking()">開始追蹤</button>
    <button class="stop" onclick="stopTracking()">停止追蹤</button>
  </div>

  <div class="card">
    <h3>目前 GPS</h3>

    <div class="row">
      <span class="label">Latitude：</span>
      <span id="lat" class="value">--</span>
    </div>

    <div class="row">
      <span class="label">Longitude：</span>
      <span id="lng" class="value">--</span>
    </div>

    <div class="row">
      <span class="label">Speed：</span>
      <span id="speed" class="value">--</span> m/s
    </div>

    <div class="row">
      <span class="label">Accuracy：</span>
      <span id="accuracy" class="value">--</span> m
    </div>

    <div class="row">
      <span class="label">最後更新：</span>
      <span id="time" class="value">--</span>
    </div>
  </div>

  <div class="card small">
    <p>建議設定：</p>
    <p>1. 騎手手機請使用 HTTPS 網址開啟此頁面。</p>
    <p>2. 按下「開始追蹤」後，請允許瀏覽器使用定位權限。</p>
    <p>3. 山路斷網時，資料會先暫存在手機 localStorage。</p>
    <p>4. 網路恢復後，會自動批次補傳。</p>
    <p>5. 長時間騎行建議搭配行動電源，並關閉螢幕。</p>
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

  // 避免手機 localStorage 資料太多，只保留最近 5000 筆
  setBuffer(arr.slice(-5000));
}

async function uploadLocation(data) {
  try {
    const res = await fetch('/api/location', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    });

    if (!res.ok) {
      throw new Error('Upload failed');
    }

    return true;
  } catch (err) {
    return false;
  }
}

async function flushBuffer() {
  if (!navigator.onLine) {
    return;
  }

  const arr = getBuffer();

  if (arr.length === 0) {
    return;
  }

  try {
    const res = await fetch('/api/bulk_location', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(arr)
    });

    if (res.ok) {
      setBuffer([]);
    }
  } catch (err) {
    // 如果失敗就保留資料，等下次再傳
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
  document.getElementById('speed').textContent =
    data.speed === null ? '--' : data.speed.toFixed(2);
  document.getElementById('accuracy').textContent =
    data.accuracy === null ? '--' : data.accuracy.toFixed(1);
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

  if (err.code === 1) {
    msg = '使用者拒絕 GPS 權限';
  } else if (err.code === 2) {
    msg = '無法取得位置';
  } else if (err.code === 3) {
    msg = 'GPS 逾時';
  }

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

  <title>自行車 GPS 多人監控端</title>

  <link
    rel="stylesheet"
    href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css"
  />

  <script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>

  <style>
    html, body {
      height: 100%;
      width: 100%;
      margin: 0;
      padding: 0;
      overflow: hidden;
      font-family: Arial, 'Microsoft JhengHei', sans-serif;
    }

    #map {
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
    }

    .leaflet-container {
      width: 100%;
      height: 100%;
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
      min-width: 330px;
      max-width: 430px;
      max-height: 90vh;
      overflow-y: auto;
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

    .online {
      color: #2e7d32;
      font-weight: bold;
    }

    .offline {
      color: #c62828;
      font-weight: bold;
    }

    .weak {
      color: #ef6c00;
      font-weight: bold;
    }

    .rider-card {
      border-top: 1px solid #ddd;
      padding-top: 8px;
      margin-top: 8px;
    }

    .rider-title {
      font-size: 15px;
      font-weight: bold;
      margin-bottom: 4px;
    }

    .dot {
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 50%;
      margin-right: 6px;
    }

    .dot-rider01 {
      background: #d32f2f;
    }

    .dot-rider02 {
      background: #1976d2;
    }

    button {
      margin-top: 8px;
      padding: 8px;
      border-radius: 8px;
      border: 1px solid #bbb;
      cursor: pointer;
      background: white;
    }
  </style>
</head>

<body>
  <div id="map"></div>

  <div class="panel">
    <h2>自行車 GPS 多人監控</h2>

    <div class="row">
      <span class="label">監控對象：</span>
      <span class="value">rider01、rider02</span>
    </div>

    <div class="row">
      <span class="label">整體狀態：</span>
      <span id="globalStatus" class="value weak">等待騎手資料</span>
    </div>

    <div id="riderInfo"></div>

    <button onclick="fitRoute()">縮放到預定路線</button>
    <button onclick="fitAllRiders()">縮放到所有騎手</button>
    <button onclick="toggleFollow()">切換跟隨所有騎手</button>
  </div>

<script>
let map;
let routeLine;
let plannedRoute = [];
let followAllRiders = true;

// 目前先固定監控兩位騎手
const riderIds = ['rider01', 'rider02'];

// 每位騎手各自有 marker 與軌跡線
let riderMarkers = {};
let riderTrackLines = {};
let riderLastServerTime = {};
let latestCache = {};

const riderStyles = {
  rider01: {
    color: '#d32f2f',
    label: 'Rider 01'
  },
  rider02: {
    color: '#1976d2',
    label: 'Rider 02'
  }
};

const routeStyle = {
  color: '#333333',
  weight: 5,
  opacity: 0.65,
  dashArray: '8, 8'
};

function initMap() {
  map = L.map('map').setView([24.13720, 120.68690], 14);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);

  // 建立兩位 rider 的空軌跡線
  riderIds.forEach(riderId => {
    const style = riderStyles[riderId] || { color: '#000000' };

    riderTrackLines[riderId] = L.polyline([], {
      color: style.color,
      weight: 4,
      opacity: 0.85
    }).addTo(map);
  });
}

async function loadRoute() {
  const res = await fetch('/api/route');
  const data = await res.json();

  plannedRoute = data.route || [];

  if (routeLine) {
    routeLine.remove();
  }

  routeLine = L.polyline(plannedRoute, routeStyle).addTo(map);

  if (plannedRoute.length > 0) {
    fitRoute();
  }
}

function fitRoute() {
  if (routeLine && plannedRoute.length > 0) {
    map.fitBounds(routeLine.getBounds(), {
      padding: [30, 30]
    });
  }
}

function fitAllRiders() {
  const group = [];

  Object.values(riderMarkers).forEach(marker => {
    group.push(marker.getLatLng());
  });

  if (group.length > 0) {
    map.fitBounds(L.latLngBounds(group), {
      padding: [60, 60],
      maxZoom: 17
    });
  }
}

function toggleFollow() {
  followAllRiders = !followAllRiders;
}

function getRiderAgeSec(riderId) {
  const t = riderLastServerTime[riderId];

  if (!t) {
    return null;
  }

  return (new Date() - t) / 1000;
}

function getStatusByAge(ageSec) {
  if (ageSec === null) {
    return {
      text: '等待資料',
      cls: 'weak'
    };
  }

  if (ageSec < 30) {
    return {
      text: 'Online',
      cls: 'online'
    };
  }

  if (ageSec < 180) {
    return {
      text: '訊號偏弱 / 更新延遲',
      cls: 'weak'
    };
  }

  return {
    text: 'Offline，顯示最後位置',
    cls: 'offline'
  };
}

function updateGlobalStatus() {
  const el = document.getElementById('globalStatus');

  let onlineCount = 0;
  let hasAnyData = false;

  riderIds.forEach(riderId => {
    const ageSec = getRiderAgeSec(riderId);

    if (ageSec !== null) {
      hasAnyData = true;
    }

    if (ageSec !== null && ageSec < 30) {
      onlineCount += 1;
    }
  });

  if (!hasAnyData) {
    el.textContent = '等待騎手資料';
    el.className = 'value weak';
  } else if (onlineCount === riderIds.length) {
    el.textContent = '所有騎手 Online';
    el.className = 'value online';
  } else if (onlineCount > 0) {
    el.textContent = `${onlineCount}/${riderIds.length} 位騎手 Online`;
    el.className = 'value weak';
  } else {
    el.textContent = '所有騎手皆未即時更新';
    el.className = 'value offline';
  }
}

function renderRiderPanel(latest) {
  const container = document.getElementById('riderInfo');
  let html = '';

  riderIds.forEach(riderId => {
    const loc = latest[riderId];
    const ageSec = getRiderAgeSec(riderId);
    const status = getStatusByAge(ageSec);

    let latText = '--';
    let lngText = '--';
    let speedText = '--';
    let accuracyText = '--';
    let lastUpdateText = '--';
    let ageText = '--';

    if (loc) {
      latText = Number(loc.lat).toFixed(7);
      lngText = Number(loc.lng).toFixed(7);

      if (loc.speed !== null && loc.speed !== undefined) {
        speedText = (Number(loc.speed) * 3.6).toFixed(1) + ' km/h';
      }

      if (loc.accuracy !== null && loc.accuracy !== undefined) {
        accuracyText = Number(loc.accuracy).toFixed(1) + ' m';
      }

      const t = riderLastServerTime[riderId];

      if (t) {
        lastUpdateText = t.toLocaleTimeString();
      }

      if (ageSec !== null) {
        ageText = ageSec.toFixed(0) + ' 秒';
      }
    }

    html += `
      <div class="rider-card">
        <div class="rider-title">
          <span class="dot dot-${riderId}"></span>${riderId}
        </div>
        <div class="row"><span class="label">狀態：</span><span class="${status.cls}">${status.text}</span></div>
        <div class="row"><span class="label">Latitude：</span><span class="value">${latText}</span></div>
        <div class="row"><span class="label">Longitude：</span><span class="value">${lngText}</span></div>
        <div class="row"><span class="label">Speed：</span><span class="value">${speedText}</span></div>
        <div class="row"><span class="label">Accuracy：</span><span class="value">${accuracyText}</span></div>
        <div class="row"><span class="label">最後更新：</span><span class="value">${lastUpdateText}</span></div>
        <div class="row"><span class="label">距上次回傳：</span><span class="value">${ageText}</span></div>
      </div>
    `;
  });

  container.innerHTML = html;
}

function createRiderIcon(riderId) {
  const style = riderStyles[riderId] || { color: '#000000' };

  return L.divIcon({
    className: 'custom-rider-icon',
    html: `
      <div style="
        background:${style.color};
        width:18px;
        height:18px;
        border-radius:50%;
        border:3px solid white;
        box-shadow:0 1px 6px rgba(0,0,0,0.45);
      "></div>
    `,
    iconSize: [24, 24],
    iconAnchor: [12, 12]
  });
}

async function updateLatest() {
  try {
    const res = await fetch('/api/latest');
    const data = await res.json();
    const latest = data.latest || {};
    latestCache = latest;

    riderIds.forEach(riderId => {
      const loc = latest[riderId];

      if (!loc) {
        return;
      }

      const latlng = [Number(loc.lat), Number(loc.lng)];
      const t = loc.server_time || loc.timestamp;

      riderLastServerTime[riderId] = t ? new Date(t) : new Date();

      if (!riderMarkers[riderId]) {
        riderMarkers[riderId] = L.marker(latlng, {
          icon: createRiderIcon(riderId)
        })
          .addTo(map)
          .bindPopup(riderId);
      } else {
        riderMarkers[riderId].setLatLng(latlng);
      }
    });

    renderRiderPanel(latest);
    updateGlobalStatus();

    if (followAllRiders) {
      fitAllRiders();
    }
  } catch (err) {
    const el = document.getElementById('globalStatus');
    el.textContent = '伺服器連線錯誤';
    el.className = 'value offline';
  }
}

async function updateTrackForRider(riderId) {
  try {
    const res = await fetch('/api/track?rider=' + encodeURIComponent(riderId));
    const data = await res.json();

    const track = data.track || [];
    const latlngs = track.map(p => [Number(p.lat), Number(p.lng)]);

    if (riderTrackLines[riderId]) {
      riderTrackLines[riderId].setLatLngs(latlngs);
    }
  } catch (err) {
    // ignore
  }
}

async function updateAllTracks() {
  for (const riderId of riderIds) {
    await updateTrackForRider(riderId);
  }
}

function updateAgeStatusOnly() {
  updateGlobalStatus();
  renderRiderPanel(latestCache);
}

initMap();
loadRoute();

setInterval(updateLatest, 2000);
setInterval(updateAllTracks, 5000);
setInterval(updateAgeStatusOnly, 1000);

updateLatest();
updateAllTracks();
</script>
</body>
</html>
"""


# =========================
# 本機執行用
# Render 部署時會用 gunicorn bike_gps_tracking_app:app
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
