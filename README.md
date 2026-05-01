# 🛡️ SafetyVision AI — PPE Compliance Monitor

AI-powered real-time Personal Protective Equipment (PPE) compliance monitoring system for construction and industrial sites.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-purple.svg)
![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 🎯 Features

- **Real-time PPE Detection** — Detects helmets, vests, gloves, goggles, boots, and harnesses using YOLOv8
- **Live Video Monitoring** — MJPEG streaming with annotated bounding boxes and compliance status
- **Compliance Analytics** — Real-time compliance rate gauge and trend charts
- **Violation Alerts** — Instant WebSocket alerts when workers are missing required PPE
- **Multi-Source Input** — Webcam, video file upload, or RTSP camera streams
- **Compliance Reports** — Downloadable JSON reports with full session analytics
- **Configurable PPE Rules** — Toggle which PPE items are required per site
- **GPU Accelerated** — CUDA-enabled inference for real-time performance

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Web Dashboard                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐  │
│  │Live Video│  │Compliance│  │Violation │  │ Report │  │
│  │  Feed    │  │  Gauge   │  │  Alerts  │  │  Chart │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └───┬────┘  │
│       │ MJPEG       │SocketIO     │SocketIO    │ REST   │
├───────┴─────────────┴─────────────┴────────────┴────────┤
│                   Flask Backend                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ YOLOv8   │  │ Compliance│  │  SQLite  │              │
│  │ Detector │  │  Engine   │  │    DB    │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install flask flask-socketio eventlet ultralytics opencv-python pyyaml
```

### 2. Run the Application

```bash
# Start with webcam
python app.py

# Start with a video file
python app.py --source path/to/video.mp4

# Custom port
python app.py --port 8080
```

### 3. Open Dashboard

Navigate to **http://localhost:5000** in your browser.

## 🤖 Model Training

### Step 1: Prepare Dataset

```bash
# Generate sample images for pipeline testing
python scripts/download_dataset.py --sample

# Or download from Roboflow (requires free account)
python scripts/download_dataset.py --api-key YOUR_ROBOFLOW_KEY
```

### Step 2: Train Model

```bash
# Train with default settings (YOLOv8s, 100 epochs)
python scripts/train_model.py

# Custom configuration
python scripts/train_model.py --model yolov8m.pt --epochs 150 --batch 16

# Resume interrupted training
python scripts/train_model.py --resume
```

### Step 3: Evaluate Model

```bash
python scripts/evaluate_model.py --visualize 20
```

The trained model (`best.pt`) will be automatically loaded by the application.

## 📡 API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard UI |
| `/video_feed` | GET | MJPEG live stream |
| `/api/start` | POST | Start monitoring |
| `/api/stop` | POST | Stop monitoring |
| `/api/upload` | POST | Upload video file |
| `/api/stats` | GET | Current statistics |
| `/api/violations` | GET | Violation history |
| `/api/report` | GET | Compliance report |
| `/api/sessions` | GET | Session history |
| `/api/settings` | POST | Update settings |
| `/api/status` | GET | System status |

## 🐳 Docker Deployment

```bash
# Build and run
docker-compose up -d

# With GPU support
docker-compose up -d --build
```

## 📁 Project Structure

```
AI CIA/
├── app.py                  # Flask application
├── data.yaml               # YOLOv8 dataset config
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container config
├── docker-compose.yml      # Docker compose
├── models/
│   ├── detector.py         # PPE detection engine
│   └── database.py         # SQLite manager
├── scripts/
│   ├── download_dataset.py # Dataset downloader
│   ├── train_model.py      # Model training
│   └── evaluate_model.py   # Model evaluation
├── static/
│   ├── index.html          # Dashboard
│   ├── css/style.css       # Dark theme
│   └── js/app.js           # Frontend logic
├── datasets/               # Training data
├── runs/                   # Training outputs
└── uploads/                # Uploaded videos
```

## 🎛️ PPE Classes

| Class | Icon | Description |
|-------|------|-------------|
| Helmet | ⛑️ | Hard hat / safety helmet |
| Vest | 🦺 | High-visibility safety vest |
| Gloves | 🧤 | Protective gloves |
| Goggles | 🥽 | Safety goggles |
| Boots | 🥾 | Safety boots |
| Harness | 🪢 | Full body harness |
| Person | 👤 | Worker detection |

## 📄 License

MIT License — See [LICENSE](LICENSE) for details.
