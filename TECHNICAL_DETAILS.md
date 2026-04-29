# SafetyVision AI: Technical Architecture & Methodology

This document outlines the technical underpinnings of the SafetyVision AI PPE Compliance Monitor, detailing how data flows from capture to analysis to the final real-time dashboard presentation.

## 1. System Architecture Overview

The system is built on a modular architecture to ensure separation of concerns between computer vision inference, asynchronous communication, and the frontend presentation layer.

- **Frontend:** Pure HTML/CSS/JS (Vanilla) avoiding heavy frameworks for maximum performance. Uses `Chart.js` for real-time graphs and `Socket.IO` for real-time event listening.
- **Backend (API & Streaming):** Python `Flask` handles video ingestion, file uploading, and MJPEG stream generation. `Flask-SocketIO` is used for WebSocket push events.
- **Computer Vision Engine:** Built on `Ultralytics YOLOv8`, offering a balance of high-speed inference and precision.
- **Database:** `SQLite` is used for logging violations and compliance snapshots locally.

## 2. Dataset & Data Preparation

### The Dataset
The model relies on a curated dataset targeting construction and industrial environments. It utilizes images annotated in the **YOLOv8 format**. 

- **Target Classes (7):**
  1. `helmet` - Hard hat / safety helmet
  2. `vest` - High-visibility safety vest
  3. `gloves` - Protective gloves
  4. `goggles` - Safety goggles / eye protection
  5. `boots` - Safety boots / footwear
  6. `harness` - Full body harness for height work
  7. `person` - The worker themselves (used as the anchor for compliance logic)

### Data Preparation
The `scripts/download_dataset.py` utilizes the Roboflow API to fetch the dataset. The dataset is split into:
- **Train:** ~70% of images used to update model weights.
- **Valid:** ~20% of images used to monitor over-fitting during training.
- **Test:** ~10% of images used for final, unbiased evaluation.

## 3. Model Training & Algorithms

### The YOLOv8 Algorithm
YOLO (You Only Look Once) is a state-of-the-art, single-stage object detection model. Unlike two-stage detectors (like Faster R-CNN) that first propose regions and then classify them, YOLOv8 processes the entire image in a single forward pass of the neural network. This makes it exceptionally fast and highly suitable for real-time video processing.

### Training Configuration (`scripts/train_model.py`)
- **Base Architecture:** The system defaults to `yolov8s.pt` (Small) or `yolov8m.pt` (Medium) depending on the available GPU VRAM.
- **Hardware Acceleration:** Training leverages NVIDIA CUDA for parallel processing.
- **Augmentation Strategies:** 
  To make the model robust against varied lighting, motion blur, and occlusion on real construction sites, extreme data augmentation is applied during training:
  - **Mosaic & Mixup:** Combines multiple images into one to teach the model to detect objects at different scales and contexts.
  - **HSV Shifts:** Alters hue, saturation, and value to simulate different times of day or indoor/outdoor lighting.
  - **Perspective & Shear:** Simulates different camera angles (e.g., overhead CCTV vs. eye-level cameras).

### Evaluation & Statistics (`scripts/evaluate_model.py`)
The evaluation script generates key metrics:
- **mAP@0.5 (Mean Average Precision):** Measures accuracy considering a bounding box overlap (IoU) of 50%. This is the primary metric for object detection.
- **Precision:** The ratio of true positive detections to total positive detections (How often is the model right when it detects a helmet?).
- **Recall:** The ratio of true positive detections to actual ground truth objects (How many of the actual helmets did the model find?).

## 4. The Inference & Compliance Engine (`models/detector.py`)

The core logic resides in the `PPEDetector` class. It doesn't just detect objects; it applies spatial reasoning to determine compliance.

### Spatial Logic (Intersection over Union)
When the YOLOv8 model processes a frame, it returns a list of bounding boxes. The engine separates these into `person` boxes and `PPE` boxes.

To determine if a specific worker is wearing a specific piece of PPE, the algorithm uses **Bounding Box Overlap (IoU)** or **Box Containment**:
1. It iterates through every detected `person`.
2. For each `person`, it checks if any `PPE` bounding box significantly overlaps with the `person` bounding box.
3. If an overlap is found (e.g., a `helmet` box is inside the upper region of a `person` box), that PPE is assigned to that worker.

### Compliance Calculation
The system maintains a configurable `required_ppe` set (e.g., `{'helmet', 'vest'}`). 
- For each worker, it compares their assigned PPE against the required set.
- If required items are missing, the worker is flagged as `non_compliant`, and a WebSocket alert is triggered.
- A global `compliance_rate` is calculated: `(Compliant Workers / Total Workers) * 100`.

## 5. Video Streaming & Asynchronous Updates

### MJPEG Streaming
Instead of sending raw video files to the browser, the Flask backend utilizes **Motion JPEG (MJPEG)**. 
- The `generate_mjpeg()` function in `app.py` continuously yields JPEG-encoded frames.
- The HTTP response type is set to `multipart/x-mixed-replace`, which tells the browser to constantly replace the previous image with the new one, creating a video stream.
- This is highly efficient and requires zero client-side video decoding logic.

### WebSocket Communication
While the video streams via HTTP, meta-data (FPS, compliance stats, violation alerts) streams over WebSockets via `Socket.IO`. 
- This decoupled approach ensures that heavy video transmission doesn't block lightweight, critical alert messages.

## 6. Static Image Support
The system also supports single static images. When an image is uploaded, the backend detects the file extension. It processes the image exactly once through the YOLOv8 engine, calculates the compliance statistics, emits them to the dashboard, and then continuously serves the static annotated frame to keep the dashboard populated without burning CPU/GPU cycles on redundant processing.
