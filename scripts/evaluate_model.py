"""
YOLOv8 PPE Model Evaluator
============================
Evaluates the trained PPE detection model and generates metrics.

Usage:
    python scripts/evaluate_model.py
    python scripts/evaluate_model.py --model path/to/model.pt
    python scripts/evaluate_model.py --visualize 20
"""

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def find_best_model():
    candidates = [
        PROJECT_ROOT / "runs" / "detect" / "ppe_model" / "weights" / "best.pt",
        PROJECT_ROOT / "best.pt",
        PROJECT_ROOT / "models" / "best.pt",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def visualize_predictions(model, n_samples=10):
    import cv2
    import yaml

    data_yaml = PROJECT_ROOT / "data.yaml"
    with open(data_yaml, 'r') as f:
        config = yaml.safe_load(f)

    dataset_root = Path(config.get('path', './datasets/ppe-detection'))
    if not dataset_root.is_absolute():
        dataset_root = PROJECT_ROOT / dataset_root

    test_dir = dataset_root / "test" / "images"
    if not test_dir.exists():
        test_dir = dataset_root / "valid" / "images"
    if not test_dir.exists():
        print("  Warning: No test/valid images found")
        return

    images = sorted(test_dir.glob("*.[jJ][pP][gG]")) + sorted(test_dir.glob("*.[pP][nN][gG]"))
    images = images[:n_samples]

    output_dir = PROJECT_ROOT / "runs" / "detect" / "ppe_eval" / "predictions"
    output_dir.mkdir(parents=True, exist_ok=True)

    for img_path in images:
        results = model(str(img_path), conf=0.3)
        annotated = results[0].plot()
        cv2.imwrite(str(output_dir / f"pred_{img_path.name}"), annotated)

    print(f"  Saved {len(images)} predictions to {output_dir}")


def evaluate(args):
    from ultralytics import YOLO

    print("=" * 60)
    print("  YOLOv8 PPE Model Evaluation")
    print("=" * 60)

    model_path = args.model or find_best_model()
    if model_path is None:
        print("No trained model found! Run: python scripts/train_model.py")
        sys.exit(1)

    print(f"\nLoading model: {model_path}")
    model = YOLO(model_path)

    data_yaml = str(PROJECT_ROOT / "data.yaml")
    print(f"Dataset config: {data_yaml}")
    print("\nRunning evaluation...")

    results = model.val(
        data=data_yaml, imgsz=640, batch=16, conf=0.25, iou=0.6,
        plots=True, save_json=True,
        project=str(PROJECT_ROOT / "runs" / "detect"),
        name="ppe_eval", exist_ok=True,
    )

    if hasattr(results, 'box'):
        box = results.box
        print(f"\nOverall Metrics:")
        print(f"  mAP@0.5:      {box.map50:.4f}")
        print(f"  mAP@0.5:0.95: {box.map:.4f}")
        print(f"  Precision:     {box.mp:.4f}")
        print(f"  Recall:        {box.mr:.4f}")

        if hasattr(box, 'ap_class_index') and box.ap_class_index is not None:
            class_names = model.names
            print(f"\nPer-Class Performance:")
            print(f"  {'Class':<12} {'P':>8} {'R':>8} {'mAP50':>8} {'mAP50-95':>10}")
            print(f"  {'-'*50}")
            for i, cls_idx in enumerate(box.ap_class_index):
                cls_name = class_names.get(int(cls_idx), f"cls_{cls_idx}")
                p = box.p[i] if i < len(box.p) else 0
                r = box.r[i] if i < len(box.r) else 0
                ap50 = box.ap50[i] if i < len(box.ap50) else 0
                ap = box.ap[i] if i < len(box.ap) else 0
                print(f"  {cls_name:<12} {p:>8.4f} {r:>8.4f} {ap50:>8.4f} {ap:>10.4f}")

    if args.visualize > 0:
        print(f"\nGenerating {args.visualize} sample predictions...")
        visualize_predictions(model, args.visualize)

    report_path = PROJECT_ROOT / "runs" / "detect" / "ppe_eval" / "evaluation_report.json"
    report = {
        "timestamp": datetime.now().isoformat(),
        "model_path": str(model_path),
        "metrics": {
            "mAP50": float(results.box.map50) if hasattr(results, 'box') else None,
            "mAP50_95": float(results.box.map) if hasattr(results, 'box') else None,
            "precision": float(results.box.mp) if hasattr(results, 'box') else None,
            "recall": float(results.box.mr) if hasattr(results, 'box') else None,
        }
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\nReport saved to: {report_path}")
    print("Evaluation complete!")


def main():
    parser = argparse.ArgumentParser(description="Evaluate PPE Detection Model")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--visualize", type=int, default=10)
    args = parser.parse_args()
    evaluate(args)


if __name__ == "__main__":
    main()
