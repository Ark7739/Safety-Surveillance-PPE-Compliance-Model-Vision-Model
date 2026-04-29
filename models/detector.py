"""
PPE Detection Engine
=====================
Core detection engine that wraps YOLOv8 for PPE compliance monitoring.

Features:
- Loads and manages YOLOv8 model
- Runs inference with configurable confidence/IoU thresholds
- Compliance logic: maps detected PPE to nearest person via IoU overlap
- Returns structured detection results with compliance status
"""

import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# Class configuration
PPE_CLASSES = {
    0: {"name": "helmet", "color": (0, 255, 255), "icon": "⛑️"},
    1: {"name": "vest", "color": (0, 165, 255), "icon": "🦺"},
    2: {"name": "gloves", "color": (255, 100, 100), "icon": "🧤"},
    3: {"name": "goggles", "color": (255, 0, 255), "icon": "🥽"},
    4: {"name": "boots", "color": (0, 200, 0), "icon": "🥾"},
    5: {"name": "harness", "color": (255, 255, 0), "icon": "🪢"},
    6: {"name": "person", "color": (0, 255, 0), "icon": "👤"},
}

# Which PPE items are required (can be toggled)
DEFAULT_REQUIRED_PPE = {"helmet", "vest"}

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Detection:
    """Single detection result."""
    class_id: int
    class_name: str
    confidence: float
    bbox: tuple  # (x1, y1, x2, y2)
    color: tuple = (0, 255, 0)


@dataclass
class PersonCompliance:
    """Compliance status for a single person."""
    person_id: int
    person_bbox: tuple
    detected_ppe: list = field(default_factory=list)
    missing_ppe: list = field(default_factory=list)
    is_compliant: bool = False
    confidence: float = 0.0


@dataclass
class FrameResult:
    """Complete detection result for a single frame."""
    detections: list = field(default_factory=list)
    persons: list = field(default_factory=list)
    total_persons: int = 0
    compliant_persons: int = 0
    non_compliant_persons: int = 0
    compliance_rate: float = 0.0
    fps: float = 0.0
    frame_number: int = 0
    detection_counts: dict = field(default_factory=dict)


def compute_iou(box1, box2):
    """Compute IoU between two bounding boxes (x1, y1, x2, y2)."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - intersection

    return intersection / union if union > 0 else 0


def box_contains(outer, inner, threshold=0.5):
    """Check if inner box is significantly contained within outer box."""
    x1 = max(outer[0], inner[0])
    y1 = max(outer[1], inner[1])
    x2 = min(outer[2], inner[2])
    y2 = min(outer[3], inner[3])

    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    inner_area = (inner[2] - inner[0]) * (inner[3] - inner[1])

    return (intersection / inner_area) >= threshold if inner_area > 0 else False


class PPEDetector:
    """YOLOv8-based PPE detection and compliance engine."""

    def __init__(self, model_path: Optional[str] = None, confidence: float = 0.5,
                 iou_threshold: float = 0.45, required_ppe: Optional[set] = None):
        self.confidence = confidence
        self.iou_threshold = iou_threshold
        self.required_ppe = required_ppe or DEFAULT_REQUIRED_PPE.copy()
        self.model = None
        self.model_path = model_path
        self.frame_count = 0
        self._class_map = {}

        self._load_model(model_path)

    def _load_model(self, model_path: Optional[str] = None):
        """Load YOLOv8 model."""
        from ultralytics import YOLO

        if model_path is None:
            # Auto-detect best model
            candidates = [
                PROJECT_ROOT / "runs" / "detect" / "ppe_model" / "weights" / "best.pt",
                PROJECT_ROOT / "best.pt",
                PROJECT_ROOT / "models" / "best.pt",
            ]
            for path in candidates:
                if path.exists():
                    model_path = str(path)
                    break

        if model_path is None:
            # Fallback to base YOLOv8 for demo
            print("⚠️  No custom PPE model found, using base YOLOv8s for demo")
            print("   Train a custom model: python scripts/train_model.py")
            model_path = "yolov8s.pt"

        print(f"🤖 Loading model: {model_path}")
        self.model = YOLO(model_path)
        self.model_path = model_path

        # Build class map from model
        if hasattr(self.model, 'names'):
            self._class_map = self.model.names
            print(f"   Classes: {list(self._class_map.values())}")

    def detect(self, frame: np.ndarray) -> FrameResult:
        """Run detection on a single frame and return compliance results."""
        self.frame_count += 1
        result = FrameResult(frame_number=self.frame_count)

        if self.model is None or frame is None:
            return result

        # Run YOLOv8 inference
        predictions = self.model(frame, conf=self.confidence, iou=self.iou_threshold,
                                  verbose=False)

        if not predictions or len(predictions) == 0:
            return result

        pred = predictions[0]
        if pred.boxes is None or len(pred.boxes) == 0:
            return result

        # Parse detections
        persons = []
        ppe_items = []
        detection_counts = {}

        for box in pred.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            bbox = (int(x1), int(y1), int(x2), int(y2))

            # Get class name from model or our mapping
            if cls_id in self._class_map:
                cls_name = self._class_map[cls_id].lower()
            elif cls_id in PPE_CLASSES:
                cls_name = PPE_CLASSES[cls_id]["name"]
            else:
                cls_name = f"class_{cls_id}"

            color = PPE_CLASSES.get(cls_id, {}).get("color", (200, 200, 200))

            det = Detection(
                class_id=cls_id, class_name=cls_name,
                confidence=conf, bbox=bbox, color=color
            )
            result.detections.append(det)

            # Count detections
            detection_counts[cls_name] = detection_counts.get(cls_name, 0) + 1

            # Separate persons from PPE items
            if cls_name == "person":
                persons.append(det)
            else:
                ppe_items.append(det)

        result.detection_counts = detection_counts
        result.total_persons = len(persons)

        # Compliance analysis: map PPE items to persons
        for i, person in enumerate(persons):
            pc = PersonCompliance(
                person_id=i,
                person_bbox=person.bbox,
                confidence=person.confidence
            )

            # Find PPE items that overlap with this person
            for ppe in ppe_items:
                if box_contains(person.bbox, ppe.bbox, threshold=0.3) or \
                   compute_iou(person.bbox, ppe.bbox) > 0.1:
                    pc.detected_ppe.append(ppe.class_name)

            # Check which required PPE is missing
            for req in self.required_ppe:
                if req not in pc.detected_ppe:
                    pc.missing_ppe.append(req)

            pc.is_compliant = len(pc.missing_ppe) == 0

            if pc.is_compliant:
                result.compliant_persons += 1
            else:
                result.non_compliant_persons += 1

            result.persons.append(pc)

        # Calculate compliance rate
        if result.total_persons > 0:
            result.compliance_rate = (result.compliant_persons / result.total_persons) * 100
        else:
            result.compliance_rate = 100.0

        return result

    def annotate_frame(self, frame: np.ndarray, result: FrameResult) -> np.ndarray:
        """Draw detection annotations on frame."""
        annotated = frame.copy()

        # Draw PPE detections
        for det in result.detections:
            if det.class_name == "person":
                continue  # Draw persons separately with compliance status
            x1, y1, x2, y2 = det.bbox
            cv2.rectangle(annotated, (x1, y1), (x2, y2), det.color, 2)
            label = f"{det.class_name} {det.confidence:.2f}"
            self._draw_label(annotated, label, (x1, y1 - 5), det.color)

        # Draw persons with compliance status
        for pc in result.persons:
            x1, y1, x2, y2 = pc.person_bbox
            if pc.is_compliant:
                color = (0, 200, 0)  # Green
                status = "COMPLIANT"
            else:
                color = (0, 0, 255)  # Red
                missing = ", ".join(pc.missing_ppe)
                status = f"MISSING: {missing}"

            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)
            self._draw_label(annotated, status, (x1, y1 - 5), color, font_scale=0.5)

        # Draw stats overlay
        self._draw_stats_overlay(annotated, result)

        return annotated

    def _draw_label(self, img, text, pos, color, font_scale=0.5):
        """Draw text label with background."""
        font = cv2.FONT_HERSHEY_SIMPLEX
        thickness = 1
        (tw, th), _ = cv2.getTextSize(text, font, font_scale, thickness)
        x, y = pos
        y = max(y, th + 5)
        cv2.rectangle(img, (x, y - th - 5), (x + tw + 5, y + 2), color, -1)
        cv2.putText(img, text, (x + 2, y - 2), font, font_scale,
                    (0, 0, 0), thickness, cv2.LINE_AA)

    def _draw_stats_overlay(self, img, result: FrameResult):
        """Draw statistics overlay on frame."""
        h, w = img.shape[:2]

        # Semi-transparent background
        overlay = img.copy()
        cv2.rectangle(overlay, (10, 10), (280, 110), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, img, 0.4, 0, img)

        font = cv2.FONT_HERSHEY_SIMPLEX
        y_offset = 30
        cv2.putText(img, f"Workers: {result.total_persons}", (20, y_offset),
                    font, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        y_offset += 25
        rate_color = (0, 200, 0) if result.compliance_rate >= 80 else \
                     (0, 200, 255) if result.compliance_rate >= 50 else (0, 0, 255)
        cv2.putText(img, f"Compliance: {result.compliance_rate:.0f}%", (20, y_offset),
                    font, 0.6, rate_color, 1, cv2.LINE_AA)
        y_offset += 25
        cv2.putText(img, f"Violations: {result.non_compliant_persons}", (20, y_offset),
                    font, 0.6, (0, 0, 255) if result.non_compliant_persons > 0 else (200, 200, 200),
                    1, cv2.LINE_AA)

    def update_settings(self, confidence=None, required_ppe=None):
        """Update detection settings."""
        if confidence is not None:
            self.confidence = confidence
        if required_ppe is not None:
            self.required_ppe = set(required_ppe)
