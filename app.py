"""
AI Safety Surveillance — PPE Compliance Monitoring System
==========================================================
Flask application with real-time video streaming and WebSocket alerts.

Features:
- MJPEG live video stream with PPE detection annotations
- Real-time compliance stats via SocketIO
- Video file upload for analysis
- Violation logging to SQLite
- REST API for reports and settings
- Webcam / video file / RTSP support

Usage:
    python app.py                           # Start with webcam
    python app.py --source video.mp4        # Analyze video file
    python app.py --source rtsp://url       # RTSP stream
    python app.py --port 5000               # Custom port
"""

import os
import sys
import time
import json
import argparse
import threading
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
from flask import Flask, Response, request, jsonify, send_from_directory
from flask_socketio import SocketIO

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.detector import PPEDetector, FrameResult
from models.database import ComplianceDB

# ─── Flask App Setup ───────────────────────────────────────────────────

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config['SECRET_KEY'] = 'ppe-surveillance-secret-key'
app.config['UPLOAD_FOLDER'] = str(PROJECT_ROOT / "uploads")
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max upload

socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# ─── Global State ──────────────────────────────────────────────────────

detector = None
db = ComplianceDB()
current_session_id = None
video_capture = None
is_monitoring = False
monitor_thread = None
current_source = None
current_source_path = None
is_image_source = False
latest_result = FrameResult()
frame_lock = threading.Lock()
latest_frame = None
fps_counter = {"count": 0, "start": time.time(), "fps": 0.0}


def init_detector():
    """Initialize the PPE detector."""
    global detector
    print("\n" + "=" * 60)
    print("  AI Safety Surveillance — PPE Compliance Monitor")
    print("=" * 60)
    detector = PPEDetector()
    print("✅ Detector initialized")


# ─── Video Capture Manager ─────────────────────────────────────────────

def open_video_source(source=None):
    """Open a video source (webcam, file, or RTSP URL)."""
    global video_capture, current_source, current_source_path, is_image_source

    if video_capture is not None:
        video_capture.release()
        video_capture = None

    is_image_source = False
    current_source_path = source

    if source is None or source == "0" or source == "webcam":
        source = 0
        current_source = "webcam"
    elif os.path.isfile(source):
        current_source = f"file:{os.path.basename(source)}"
        ext = os.path.splitext(source)[1].lower()
        if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.webp']:
            is_image_source = True
            print(f"🖼️ Opening static image source: {current_source}")
            return True
    else:
        current_source = source  # RTSP or URL

    print(f"📹 Opening video source: {current_source}")
    video_capture = cv2.VideoCapture(source)

    if not video_capture.isOpened():
        print(f"❌ Failed to open video source: {source}")
        video_capture = None
        return False

    # Get video properties
    w = int(video_capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(video_capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = video_capture.get(cv2.CAP_PROP_FPS)
    print(f"   Resolution: {w}x{h}, FPS: {fps:.1f}")
    return True


def monitoring_loop():
    """Main monitoring loop running in a background thread."""
    global is_monitoring, latest_result, latest_frame, current_session_id
    global fps_counter, is_image_source, current_source_path

    snapshot_interval = 30  # Log snapshot every 30 frames
    violation_cooldown = {}  # Prevent duplicate violation alerts
    image_processed = False

    while is_monitoring:
        if is_image_source:
            if image_processed:
                # For static images, just sleep and keep serving the same frame
                time.sleep(0.1)
                continue
            else:
                # Load image explicitly with 3 channels
                frame = cv2.imread(current_source_path, cv2.IMREAD_COLOR)
                if frame is None:
                    print(f"❌ Failed to load image: {current_source_path}")
                    break
        else:
            if video_capture is None:
                break
            ret, frame = video_capture.read()
            if not ret:
                # If video file, loop back to beginning
                if current_source and current_source.startswith("file:"):
                    video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    break

        # Ensure frame has 3 channels (strip alpha if needed)
        if len(frame.shape) == 3 and frame.shape[2] == 4:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

        # Resize for performance if needed
        h, w = frame.shape[:2]
        if w > 1280:
            scale = 1280 / w
            frame = cv2.resize(frame, None, fx=scale, fy=scale)

        # Run detection
        result = detector.detect(frame)

        if is_image_source:
            image_processed = True
            result.fps = 0.0
        else:
            # Calculate FPS
            fps_counter["count"] += 1
            elapsed = time.time() - fps_counter["start"]
            if elapsed >= 1.0:
                fps_counter["fps"] = fps_counter["count"] / elapsed
                fps_counter["count"] = 0
                fps_counter["start"] = time.time()
            result.fps = fps_counter["fps"]

        # Annotate frame
        annotated = detector.annotate_frame(frame, result)

        # Update global state
        with frame_lock:
            latest_result = result
            _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
            latest_frame = buffer.tobytes()

        # Emit real-time updates via SocketIO
        stats = {
            "compliance_rate": round(result.compliance_rate, 1),
            "total_persons": result.total_persons,
            "compliant": result.compliant_persons,
            "non_compliant": result.non_compliant_persons,
            "detection_counts": result.detection_counts,
            "fps": round(result.fps, 1),
            "frame_number": result.frame_number,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
        }
        socketio.emit("stats_update", stats)

        # Log violations and emit alerts
        for person in result.persons:
            if not person.is_compliant:
                # Cooldown: don't spam same violation
                key = f"{person.person_id}-{'-'.join(sorted(person.missing_ppe))}"
                now = time.time()
                if key not in violation_cooldown or now - violation_cooldown[key] > 5:
                    violation_cooldown[key] = now

                    alert = {
                        "person_id": person.person_id,
                        "missing_ppe": person.missing_ppe,
                        "confidence": round(person.confidence, 2),
                        "timestamp": datetime.now().strftime("%H:%M:%S"),
                    }
                    socketio.emit("violation_alert", alert)

                    # Log to database
                    if current_session_id:
                        db.log_violation(
                            current_session_id, person.person_id,
                            person.missing_ppe, person.confidence,
                            bbox=list(person.person_bbox),
                            frame_number=result.frame_number
                        )

        # Log compliance snapshot periodically
        if current_session_id and result.frame_number % snapshot_interval == 0:
            db.log_snapshot(
                current_session_id, result.compliance_rate,
                result.total_persons, result.compliant_persons,
                result.frame_number, result.detection_counts
            )

        # Small delay to control frame rate
        time.sleep(0.03)  # ~30 FPS max

    is_monitoring = False
    socketio.emit("monitoring_stopped", {})
    print("⏹️  Monitoring stopped")


def generate_mjpeg():
    """MJPEG stream generator for the video feed."""
    while True:
        with frame_lock:
            frame_bytes = latest_frame

        if frame_bytes is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        else:
            # Send a blank frame if no video
            blank = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(blank, "No Video Feed", (180, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (100, 100, 100), 2)
            _, buffer = cv2.imencode('.jpg', blank)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

        time.sleep(0.033)  # ~30 FPS


# ─── Routes ────────────────────────────────────────────────────────────

@app.route('/')
def index():
    """Serve the main dashboard."""
    return send_from_directory('static', 'index.html')


@app.route('/video_feed')
def video_feed():
    """MJPEG video stream endpoint."""
    return Response(generate_mjpeg(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


# ─── API Endpoints ─────────────────────────────────────────────────────

@app.route('/api/start', methods=['POST'])
def start_monitoring():
    """Start monitoring with a given source."""
    global is_monitoring, monitor_thread, current_session_id

    # If already monitoring, stop previous session cleanly
    if is_monitoring:
        is_monitoring = False
        if video_capture is not None:
            video_capture.release()
        if current_session_id:
            db.end_session(current_session_id, latest_result.frame_number)

    data = request.get_json() or {}
    source = data.get("source", "0")

    if not open_video_source(source):
        return jsonify({"error": f"Failed to open source: {source}"}), 400

    # Create new session
    current_session_id = db.create_session(source=current_source)

    is_monitoring = True
    monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
    monitor_thread.start()

    return jsonify({
        "status": "started",
        "session_id": current_session_id,
        "source": current_source
    })


@app.route('/api/stop', methods=['POST'])
def stop_monitoring():
    """Stop monitoring."""
    global is_monitoring, video_capture, current_session_id

    is_monitoring = False

    if video_capture is not None:
        video_capture.release()
        video_capture = None

    if current_session_id:
        db.end_session(current_session_id, latest_result.frame_number)
        session_id = current_session_id
        current_session_id = None
        return jsonify({"status": "stopped", "session_id": session_id})

    return jsonify({"status": "stopped"})


@app.route('/api/upload', methods=['POST'])
def upload_video():
    """Upload a video file for analysis."""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    # Save file
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    return jsonify({
        "status": "uploaded",
        "filename": filename,
        "filepath": filepath,
        "source": filepath
    })


import base64

@app.route('/api/detect_image', methods=['POST'])
def detect_image():
    """Endpoint for processing a single static image in Manual Mode."""
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400

    # Save file temporarily
    filename = f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    # Read image
    frame = cv2.imread(filepath, cv2.IMREAD_COLOR)
    if frame is None:
        return jsonify({"error": "Failed to decode image"}), 400

    if len(frame.shape) == 3 and frame.shape[2] == 4:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    # Resize for performance if needed
    h, w = frame.shape[:2]
    if w > 1280:
        scale = 1280 / w
        frame = cv2.resize(frame, None, fx=scale, fy=scale)

    # Detect
    result = detector.detect(frame)
    result.fps = 0.0

    # Annotate
    annotated = detector.annotate_frame(frame, result)
    
    # Convert annotated image to base64
    _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
    img_b64 = base64.b64encode(buffer).decode('utf-8')

    # Prepare alerts/violations
    violations = []
    for person in result.persons:
        if not person.is_compliant:
            violations.append({
                "person_id": person.person_id,
                "missing_ppe": person.missing_ppe,
                "confidence": round(person.confidence, 2),
                "timestamp": datetime.now().strftime("%H:%M:%S")
            })
            # Log to DB (standalone mode uses a pseudo session ID of 0)
            db.log_violation(0, person.person_id, person.missing_ppe, person.confidence,
                             bbox=list(person.person_bbox), frame_number=1)

    return jsonify({
        "status": "success",
        "image_b64": f"data:image/jpeg;base64,{img_b64}",
        "stats": {
            "compliance_rate": round(result.compliance_rate, 1),
            "total_persons": result.total_persons,
            "compliant": result.compliant_persons,
            "non_compliant": result.non_compliant_persons,
            "detection_counts": result.detection_counts,
            "fps": 0.0,
            "timestamp": datetime.now().strftime("%H:%M:%S")
        },
        "violations": violations
    })


@app.route('/api/violations', methods=['GET'])
def get_violations():
    """Get violation history."""
    session_id = request.args.get('session_id', type=int)
    limit = request.args.get('limit', default=100, type=int)
    violations = db.get_violations(session_id=session_id, limit=limit)
    return jsonify({"violations": violations})


@app.route('/api/report', methods=['GET'])
def get_report():
    """Generate compliance report for a session."""
    session_id = request.args.get('session_id', type=int)
    if session_id is None:
        session_id = current_session_id
    if session_id is None:
        return jsonify({"error": "No session specified"}), 400

    report = db.generate_report(session_id)
    if report is None:
        return jsonify({"error": "Session not found"}), 404

    return jsonify(report)


@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """Get recent monitoring sessions."""
    limit = request.args.get('limit', default=10, type=int)
    sessions = db.get_recent_sessions(limit=limit)
    return jsonify({"sessions": sessions})


@app.route('/api/settings', methods=['POST'])
def update_settings():
    """Update detection settings."""
    data = request.get_json() or {}

    confidence = data.get('confidence')
    required_ppe = data.get('required_ppe')

    if detector:
        detector.update_settings(
            confidence=confidence,
            required_ppe=required_ppe
        )

    return jsonify({
        "status": "updated",
        "confidence": detector.confidence if detector else None,
        "required_ppe": list(detector.required_ppe) if detector else None,
    })


@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get current stats."""
    result = latest_result
    return jsonify({
        "compliance_rate": round(result.compliance_rate, 1),
        "total_persons": result.total_persons,
        "compliant": result.compliant_persons,
        "non_compliant": result.non_compliant_persons,
        "detection_counts": result.detection_counts,
        "fps": round(result.fps, 1),
        "frame_number": result.frame_number,
        "is_monitoring": is_monitoring,
        "source": current_source,
        "session_id": current_session_id,
    })


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get system status."""
    return jsonify({
        "is_monitoring": is_monitoring,
        "source": current_source,
        "session_id": current_session_id,
        "model_path": detector.model_path if detector else None,
        "required_ppe": list(detector.required_ppe) if detector else [],
        "confidence": detector.confidence if detector else 0.5,
    })


# ─── SocketIO Events ──────────────────────────────────────────────────

@socketio.on('connect')
def handle_connect():
    print("🔌 Client connected")
    socketio.emit("status", {
        "is_monitoring": is_monitoring,
        "source": current_source,
        "session_id": current_session_id,
    })


@socketio.on('disconnect')
def handle_disconnect():
    print("🔌 Client disconnected")


# ─── Main ──────────────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="PPE Compliance Monitor")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--source", type=str, default=None,
                        help="Video source (0=webcam, path=file, rtsp://=stream)")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    init_detector()

    # Auto-start monitoring if source provided
    if args.source:
        if open_video_source(args.source):
            current_session_id = db.create_session(source=current_source)
            is_monitoring = True
            monitor_thread = threading.Thread(target=monitoring_loop, daemon=True)
            monitor_thread.start()

    print(f"\n🌐 Dashboard: http://localhost:{args.port}")
    print(f"📹 Video Feed: http://localhost:{args.port}/video_feed")
    print(f"📊 API: http://localhost:{args.port}/api/status")
    print("-" * 60)

    socketio.run(app, host=args.host, port=args.port,
                 debug=args.debug, allow_unsafe_werkzeug=True)
