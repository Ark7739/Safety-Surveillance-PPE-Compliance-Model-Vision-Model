"""
PPE Detection Dataset Downloader
================================
Downloads and prepares PPE detection datasets for YOLOv8 training.

Supports two modes:
1. Roboflow API (requires API key) — downloads directly from Roboflow
2. Manual setup — provides instructions and creates directory structure

Usage:
    python scripts/download_dataset.py                    # Interactive mode
    python scripts/download_dataset.py --api-key YOUR_KEY # With Roboflow API
    python scripts/download_dataset.py --manual            # Manual setup only
"""

import os
import sys
import argparse
import shutil
from pathlib import Path

# Project root (one level up from scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = PROJECT_ROOT / "datasets" / "ppe-detection"


def create_directory_structure():
    """Create the required directory structure for YOLOv8 training."""
    dirs = [
        DATASET_DIR / "train" / "images",
        DATASET_DIR / "train" / "labels",
        DATASET_DIR / "valid" / "images",
        DATASET_DIR / "valid" / "labels",
        DATASET_DIR / "test" / "images",
        DATASET_DIR / "test" / "labels",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ Created {d.relative_to(PROJECT_ROOT)}")


def download_from_roboflow(api_key: str):
    """Download PPE dataset from Roboflow using their Python SDK."""
    try:
        from roboflow import Roboflow
    except ImportError:
        print("Installing roboflow SDK...")
        os.system(f"{sys.executable} -m pip install roboflow -q")
        from roboflow import Roboflow

    print("\n🔄 Connecting to Roboflow...")
    rf = Roboflow(api_key=api_key)

    # Primary dataset: Construction Site Safety
    # This dataset includes: helmet, vest, person, goggles, gloves, boots
    print("📦 Downloading 'Construction Site Safety' dataset...")
    
    try:
        # Try the comprehensive PPE dataset first
        project = rf.workspace().project("construction-site-safety")
        version = project.version(1)
        dataset = version.download("yolov8", location=str(DATASET_DIR))
        print(f"  ✓ Dataset downloaded to {DATASET_DIR}")
        return True
    except Exception as e:
        print(f"  ⚠ Primary dataset failed: {e}")
        
    try:
        # Fallback: PPE detection dataset
        project = rf.workspace().project("ppe-detection-dataset")
        version = project.version(1)
        dataset = version.download("yolov8", location=str(DATASET_DIR))
        print(f"  ✓ Fallback dataset downloaded to {DATASET_DIR}")
        return True
    except Exception as e:
        print(f"  ⚠ Fallback dataset also failed: {e}")
        print("  → Falling back to manual setup mode")
        return False


def download_sample_images():
    """Create sample placeholder images for testing the pipeline."""
    try:
        import numpy as np
        import cv2
    except ImportError:
        print("  ⚠ OpenCV not available, skipping sample image generation")
        return

    print("\n🖼️  Generating sample training images for pipeline testing...")
    
    # Create some sample images with synthetic annotations
    colors = {
        'helmet': (0, 255, 255),    # Yellow
        'vest': (0, 165, 255),       # Orange
        'person': (0, 255, 0),       # Green
    }
    
    for split in ['train', 'valid', 'test']:
        n_images = 10 if split == 'train' else 3
        for i in range(n_images):
            # Create a sample construction site-like image
            img = np.random.randint(40, 80, (640, 640, 3), dtype=np.uint8)
            
            # Add some rectangles to simulate workers
            cx, cy = np.random.randint(150, 490), np.random.randint(150, 490)
            
            # Person body
            cv2.rectangle(img, (cx-40, cy-80), (cx+40, cy+120), (100, 100, 150), -1)
            # Helmet area
            cv2.rectangle(img, (cx-25, cy-110), (cx+25, cy-75), (0, 200, 200), -1)
            # Vest area
            cv2.rectangle(img, (cx-38, cy-50), (cx+38, cy+40), (0, 140, 255), -1)
            
            img_path = DATASET_DIR / split / "images" / f"sample_{i:04d}.jpg"
            cv2.imwrite(str(img_path), img)
            
            # Create corresponding YOLO label
            # Format: class_id center_x center_y width height (normalized)
            label_path = DATASET_DIR / split / "labels" / f"sample_{i:04d}.txt"
            with open(label_path, 'w') as f:
                # Person
                f.write(f"6 {cx/640:.4f} {(cy+20)/640:.4f} {80/640:.4f} {200/640:.4f}\n")
                # Helmet
                f.write(f"0 {cx/640:.4f} {(cy-92)/640:.4f} {50/640:.4f} {35/640:.4f}\n")
                # Vest
                f.write(f"1 {cx/640:.4f} {(cy-5)/640:.4f} {76/640:.4f} {90/640:.4f}\n")
    
    print(f"  ✓ Generated sample images in {DATASET_DIR}")
    print("  ⚠ NOTE: These are synthetic samples for pipeline testing only!")
    print("  → Replace with real data from Roboflow for production training")


def print_manual_instructions():
    """Print instructions for manual dataset download."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║              MANUAL DATASET SETUP INSTRUCTIONS                ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  1. Go to https://roboflow.com and create a free account     ║
║                                                              ║
║  2. Search for PPE detection datasets. Recommended:          ║
║     • "Construction Site Safety Image Dataset"               ║
║     • "PPE Detection" by Roboflow Universe                   ║
║     • "Safety Helmet Detection"                              ║
║                                                              ║
║  3. Click "Download Dataset" → Format: "YOLOv8"             ║
║                                                              ║
║  4. Extract the downloaded zip to:                           ║
║     datasets/ppe-detection/                                  ║
║                                                              ║
║  5. Verify the structure matches:                            ║
║     datasets/ppe-detection/                                  ║
║     ├── train/                                               ║
║     │   ├── images/  (training images)                       ║
║     │   └── labels/  (YOLO format .txt files)                ║
║     ├── valid/                                               ║
║     │   ├── images/                                          ║
║     │   └── labels/                                          ║
║     └── test/                                                ║
║         ├── images/                                          ║
║         └── labels/                                          ║
║                                                              ║
║  6. Update data.yaml class names to match your dataset       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """)


def verify_dataset():
    """Verify the dataset structure and count files."""
    print("\n🔍 Verifying dataset structure...")
    
    total_images = 0
    for split in ['train', 'valid', 'test']:
        img_dir = DATASET_DIR / split / "images"
        lbl_dir = DATASET_DIR / split / "labels"
        
        if img_dir.exists():
            images = list(img_dir.glob("*.[jJ][pP][gG]")) + \
                     list(img_dir.glob("*.[pP][nN][gG]"))
            labels = list(lbl_dir.glob("*.txt")) if lbl_dir.exists() else []
            total_images += len(images)
            
            status = "✓" if len(images) > 0 else "✗"
            print(f"  {status} {split}: {len(images)} images, {len(labels)} labels")
        else:
            print(f"  ✗ {split}: directory not found")
    
    if total_images > 0:
        print(f"\n✅ Dataset ready! Total: {total_images} images")
        return True
    else:
        print(f"\n❌ No images found. Please add data to {DATASET_DIR}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Download PPE Detection Dataset")
    parser.add_argument("--api-key", type=str, help="Roboflow API key")
    parser.add_argument("--manual", action="store_true", help="Show manual setup instructions only")
    parser.add_argument("--sample", action="store_true", help="Generate sample images for testing")
    args = parser.parse_args()

    print("=" * 60)
    print("  PPE Detection Dataset Downloader")
    print("=" * 60)

    # Create directory structure
    print("\n📁 Creating directory structure...")
    create_directory_structure()

    if args.manual:
        print_manual_instructions()
        return

    if args.api_key:
        success = download_from_roboflow(args.api_key)
        if not success:
            print_manual_instructions()
    elif args.sample:
        download_sample_images()
    else:
        # Interactive mode
        print("\n📋 Choose download method:")
        print("  1. Roboflow API (requires free account)")
        print("  2. Generate sample images (for pipeline testing)")
        print("  3. Manual setup (show instructions)")
        
        choice = input("\nEnter choice [1/2/3]: ").strip()
        
        if choice == "1":
            api_key = input("Enter Roboflow API key: ").strip()
            if api_key:
                success = download_from_roboflow(api_key)
                if not success:
                    download_sample_images()
            else:
                print("No API key provided, generating samples...")
                download_sample_images()
        elif choice == "2":
            download_sample_images()
        else:
            print_manual_instructions()
            return

    # Verify dataset
    verify_dataset()


if __name__ == "__main__":
    main()
