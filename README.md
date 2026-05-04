# Bike GPS Tracker

Bike GPS Tracker is a real-time bicycle GPS tracking web application built with Flask, Leaflet, and OpenStreetMap. The system is designed for monitoring a cyclist's live position during outdoor riding or bicycle racing. The rider uses a mobile phone as the GPS sender, while the monitor user can view the rider's real-time position and traveled path on a web-based map.

本專案是一套即時自行車 GPS 追蹤網站。騎手可使用手機瀏覽器作為 GPS 發送端，系統會透過 HTTPS 將經緯度、速度、精度與時間資料上傳至 Render雲端伺服器。監控者則可透過 `/monitor` 頁面查看騎手的即時位置、預定路線、已騎行軌跡與連線狀態。系統也具備簡易斷線暫存功能，適合用於山路騎行或自行車比賽的原型測試。

## Public Website

Main page:

```
https://bike-gps-tracker.onrender.com
```

Rider tracking page:

```
https://bike-gps-tracker.onrender.com/track?rider=rider01
```

Monitor page:

```
https://bike-gps-tracker.onrender.com/monitor
```

# System Purpose

This project aims to provide a lightweight GPS tracking system for bicycle riding scenarios. The system allows a rider and a monitor to be in different locations and communicate through the internet. The rider's mobile phone collects GPS data and uploads it to the cloud server, while the monitor page displays the latest position on a map.

## Main Features
### 1. Mobile GPS Tracking Page

The rider can open the tracking page on a smartphone:

```
/track?rider=rider01
```

This page provides:

- GPS position acquisition from the mobile browser
- Rider ID display
- Start and stop tracking buttons
- Current latitude and longitude display
- Current speed display
- GPS accuracy display
- Last update time
- Network status display
- Local temporary storage counter

The rider only needs to press Start Tracking and allow location permission in the browser.

2. Real-Time Monitor Map

The monitor can open:

```
/monitor
```

This page provides:

- Interactive map display
- Rider's real-time position marker
- Planned riding route display
- Traveled trajectory display
- Latest latitude and longitude
- Speed in km/h
- GPS accuracy
- Last update time
- Online, weak signal, and offline status indication
- Auto-follow function for the rider marker

3. Planned Route Display

A planned riding route can be displayed on the monitor map. The route is defined in the Python program as a list of GPS coordinates:

```
PLANNED_ROUTE = [
    [24.13720, 120.68690],
    [24.13820, 120.68850],
    [24.13980, 120.69010],
]
```

These points are drawn as a polyline on the map. The route can be replaced with the actual bicycle race route or GPX-converted coordinate points.

4. Real-Time GPS Upload

The smartphone uploads GPS data to the Flask server through:

```
/api/location
```

Each GPS data packet includes:

- Rider ID
- Latitude
- Longitude
- Speed
- GPS accuracy
- Altitude
- Heading
- Client timestamp
- Server timestamp

5. Offline Buffering for Weak Network Areas

The mobile tracking page includes a local buffering mechanism. If the rider enters an area with weak or unstable network coverage, GPS data will be stored temporarily in the phone browser's localStorage.

When the network is restored, the stored GPS data is automatically uploaded to the server through:

```
/api/bulk_location
```

This is useful for mountain roads or rural areas where mobile network coverage may be unstable.

6. Rider Status Monitoring

The monitor page evaluates the time since the last GPS update and shows the rider's communication status:

- Online: recent GPS update received
- Weak signal: GPS update delay is increasing
- Offline: no GPS update for a long time, showing the last known position

This helps the monitor distinguish between a stopped rider and a temporary communication loss.

7. Track History Display

The server stores recent GPS points in memory and provides them through:

```
/api/track?rider=rider01
```

The monitor page draws these points as the rider's traveled path.

8. CSV Logging

The server also writes GPS data into a CSV file:

```
tracking_data/gps_log.csv
```

The CSV includes:

- Server time
- Client time
- Rider ID
- Latitude
- Longitude
- Speed
- Accuracy
- Altitude
- Heading

This allows later analysis of the riding trajectory.


## API Endpoints

| Endpoint                   | Method | Description                |
| -------------------------- | ------ | -------------------------- |
| `/`                        | GET    | Main page                  |
| `/track?rider=rider01`     | GET    | Mobile GPS sender page     |
| `/monitor`                 | GET    | Real-time monitoring map   |
| `/api/location`            | POST   | Upload one GPS point       |
| `/api/bulk_location`       | POST   | Upload buffered GPS points |
| `/api/latest`              | GET    | Get latest rider location  |
| `/api/track?rider=rider01` | GET    | Get rider trajectory       |
| `/api/route`               | GET    | Get planned route          |


## System Architecture

Rider Smartphone
        |
        | GPS data through HTTPS
        v
Render Cloud Server
        |
        | Flask API
        v
Monitor Web Page
        |
        | Leaflet + OpenStreetMap
        v
Real-time rider position and trajectory display

## Deployment Platform
 
This project is deployed as a Python Web Service on Render.

The server runs:

```
gunicorn bike_gps_tracking_app:app
```

Required Python packages are listed in:

```
requirements.txt
flask
gunicorn
```

## Current Limitations

This version is suitable for prototype testing and demonstration. The current implementation stores latest positions and trajectories in server memory. Therefore, if the cloud server restarts, the in-memory track data may be cleared.

For long-duration bicycle races or formal use, the system should be upgraded with:

- PostgreSQL or another persistent database
- User authentication
- GPX route file import
- Multiple rider selection on the monitor page
- Battery level reporting
- Route deviation warning
- Exportable ride history
- More stable background tracking method for mobile devices

## Recommended Use

For a 7-hour mountain-road bicycle ride, the rider should:

- Use the HTTPS tracking link
- Allow GPS permission
- Keep mobile data enabled
- Use a power bank
- Keep the tracking page open
- Avoid closing the browser tab
- Use the same rider ID, such as rider01

The monitor should open:

```
https://bike-gps-tracker.onrender.com/monitor
```

and observe the live position, update time, and status indicator.












