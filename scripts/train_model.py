"""
YOLOv8 PPE Detection Model Trainer
====================================
Trains a YOLOv8 model for PPE (Personal Protective Equipment) detection.

Features:
- GPU-accelerated training with CUDA
- Comprehensive data augmentation for varied conditions
- Early stopping to prevent overfitting
- Automatic best model selection
- Training metrics logging and visualization

Usage:
    python scripts/train_model.py                     # Default training
    python scripts/train_model.py --epochs 50          # Custom epochs
    python scripts/train_model.py --model yolov8s.pt   # Different model size
    python scripts/train_model.py --resume             # Resume interrupted training
"""

import argparse
import sys
import os
from pathlib import Path

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def check_gpu():
    """Check GPU availability and print info."""
    import torch
    print("\n🖥️  Hardware Check:")
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_mem / (1024**3)
        print(f"  ✓ GPU: {gpu_name} ({gpu_memory:.1f} GB)")
        print(f"  ✓ CUDA Version: {torch.version.cuda}")
        return "0"  # GPU device index
    else:
        print("  ⚠ No GPU detected, using CPU (training will be slow)")
        return "cpu"


def verify_dataset(data_yaml: str):
    """Verify dataset exists before training."""
    import yaml
    
    data_path = Path(data_yaml)
    if not data_path.exists():
        print(f"❌ Dataset config not found: {data_yaml}")
        print("   Run: python scripts/download_dataset.py --sample")
        sys.exit(1)
    
    with open(data_path, 'r') as f:
        config = yaml.safe_load(f)
    
    dataset_root = Path(config.get('path', './datasets/ppe-detection'))
    if not dataset_root.is_absolute():
        dataset_root = PROJECT_ROOT / dataset_root
    
    train_dir = dataset_root / config.get('train', 'train/images')
    if not train_dir.exists() or len(list(train_dir.glob("*"))) == 0:
        print(f"❌ Training images not found in: {train_dir}")
        print("   Run: python scripts/download_dataset.py --sample")
        sys.exit(1)
    
    n_train = len(list(train_dir.glob("*.[jJ][pP][gG]")) + list(train_dir.glob("*.[pP][nN][gG]")))
    print(f"  ✓ Dataset: {n_train} training images")
    print(f"  ✓ Classes: {config.get('nc', '?')} ({', '.join(config.get('names', {}).values())})")
    
    return True


def train(args):
    """Run YOLOv8 training."""
    from ultralytics import YOLO

    print("=" * 60)
    print("  YOLOv8 PPE Detection Model Training")
    print("=" * 60)

    # Check hardware
    device = check_gpu()

    # Verify dataset
    data_yaml = str(PROJECT_ROOT / "data.yaml")
    print("\n📦 Dataset Verification:")
    verify_dataset(data_yaml)

    # Load model
    print(f"\n🤖 Loading base model: {args.model}")
    if args.resume and (PROJECT_ROOT / "runs" / "detect" / "ppe_model" / "weights" / "last.pt").exists():
        print("  → Resuming from last checkpoint")
        model = YOLO(str(PROJECT_ROOT / "runs" / "detect" / "ppe_model" / "weights" / "last.pt"))
    else:
        model = YOLO(args.model)
    
    # Training configuration
    train_args = {
        "data": data_yaml,
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "device": device,
        "project": str(PROJECT_ROOT / "runs" / "detect"),
        "name": "ppe_model",
        "exist_ok": True,
        "patience": args.patience,
        "save": True,
        "save_period": 10,
        "plots": True,
        "verbose": True,
        
        # Optimizer
        "optimizer": "auto",
        "lr0": 0.01,
        "lrf": 0.01,
        "momentum": 0.937,
        "weight_decay": 0.0005,
        "warmup_epochs": 3.0,
        "warmup_momentum": 0.8,
        
        # Data Augmentation — critical for varied lighting/occlusion
        "hsv_h": 0.015,     # HSV hue augmentation (lighting variation)
        "hsv_s": 0.7,       # HSV saturation augmentation
        "hsv_v": 0.4,       # HSV value augmentation
        "degrees": 5.0,     # Rotation (small for construction scenes)
        "translate": 0.1,   # Translation
        "scale": 0.5,       # Scale augmentation
        "shear": 2.0,       # Shear
        "perspective": 0.0005,  # Perspective transform
        "flipud": 0.0,      # No vertical flip (people don't flip)
        "fliplr": 0.5,      # Horizontal flip
        "mosaic": 1.0,      # Mosaic augmentation (great for multi-object)
        "mixup": 0.15,      # Mixup augmentation
        "copy_paste": 0.1,  # Copy-paste augmentation
    }

    print(f"\n🚀 Starting training...")
    print(f"  → Model: {args.model}")
    print(f"  → Epochs: {args.epochs}")
    print(f"  → Image Size: {args.imgsz}")
    print(f"  → Batch Size: {args.batch}")
    print(f"  → Device: {device}")
    print(f"  → Early Stopping Patience: {args.patience}")
    print("-" * 60)

    # Train!
    results = model.train(**train_args)

    # Print results summary
    print("\n" + "=" * 60)
    print("  Training Complete!")
    print("=" * 60)
    
    best_model_path = PROJECT_ROOT / "runs" / "detect" / "ppe_model" / "weights" / "best.pt"
    if best_model_path.exists():
        print(f"\n✅ Best model saved to: {best_model_path}")
        print(f"   File size: {best_model_path.stat().st_size / (1024*1024):.1f} MB")
    
    # Print metrics
    metrics_keys = ['metrics/precision(B)', 'metrics/recall(B)', 
                     'metrics/mAP50(B)', 'metrics/mAP50-95(B)']
    
    print("\n📊 Final Metrics:")
    if hasattr(results, 'results_dict'):
        for key in metrics_keys:
            if key in results.results_dict:
                name = key.split('/')[-1].replace('(B)', '')
                value = results.results_dict[key]
                print(f"  → {name}: {value:.4f}")
    
    print(f"\n📈 Training plots saved to: {PROJECT_ROOT / 'runs' / 'detect' / 'ppe_model'}")
    print(f"\n🔄 Next step: python scripts/evaluate_model.py")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Train YOLOv8 PPE Detection Model")
    parser.add_argument("--model", type=str, default="yolov8s.pt",
                        help="Base model (yolov8n.pt, yolov8s.pt, yolov8m.pt, yolov8l.pt)")
    parser.add_argument("--epochs", type=int, default=100,
                        help="Number of training epochs (default: 100)")
    parser.add_argument("--imgsz", type=int, default=640,
                        help="Input image size (default: 640)")
    parser.add_argument("--batch", type=int, default=-1,
                        help="Batch size (-1 for auto)")
    parser.add_argument("--patience", type=int, default=15,
                        help="Early stopping patience (default: 15)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume training from last checkpoint")
    
    args = parser.parse_args()
    train(args)


if __name__ == "__main__":
    main()
