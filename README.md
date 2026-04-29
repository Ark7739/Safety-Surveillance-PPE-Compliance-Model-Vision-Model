---
title: SafetyVision AI — PPE Compliance Monitor
emoji: 🛡️
colorFrom: indigo
colorTo: red
sdk: docker
app_port: 7860
pinned: true
license: mit
short_description: Real-time PPE detection & compliance monitoring with YOLOv8
tags:
  - yolov8
  - computer-vision
  - object-detection
  - ppe-detection
  - safety
  - flask
  - real-time
---

# 🛡️ SafetyVision AI — PPE Compliance Monitor

AI-powered real-time Personal Protective Equipment (PPE) compliance monitoring system for construction and industrial sites.

## 🎯 Features

- **Real-time PPE Detection** — Detects helmets, vests, gloves, goggles, boots, and harnesses using YOLOv8
- **Live Video Monitoring** — MJPEG streaming with annotated bounding boxes and compliance status
- **Manual Image Analysis** — Upload images for instant PPE compliance analysis
- **Compliance Analytics** — Real-time compliance rate gauge and trend charts
- **Violation Alerts** — Instant WebSocket alerts when workers are missing required PPE
- **Compliance Reports** — Downloadable JSON reports with full session analytics
- **Configurable PPE Rules** — Toggle which PPE items are required per site

## 🚀 How to Use

1. **Manual Mode**: Click "Manual Mode" → Upload an image → Get instant PPE analysis
2. **Live Mode**: Click "Start Monitoring" → Use webcam or upload a video file
3. **Settings**: Configure which PPE items are required using the settings panel

## 🤖 Model

Uses YOLOv8s with 7 detection classes:

| Class | Icon | Description |
|-------|------|-------------|
| Helmet | ⛑️ | Hard hat / safety helmet |
| Vest | 🦺 | High-visibility safety vest |
| Gloves | 🧤 | Protective gloves |
| Goggles | 🥽 | Safety goggles |
| Boots | 🥾 | Safety boots |
| Harness | 🪢 | Full body harness |
| Person | 👤 | Worker detection |

## 📡 API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard UI |
| `/api/detect_image` | POST | Upload image for analysis |
| `/api/start` | POST | Start monitoring |
| `/api/stop` | POST | Stop monitoring |
| `/api/stats` | GET | Current statistics |
| `/api/status` | GET | System status |

## 📄 License

MIT License
