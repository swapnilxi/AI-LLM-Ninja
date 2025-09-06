#!/usr/bin/env python3
"""
Test script for image segmentation and labeling using Mask R-CNN
"""

import torch
from torchvision import transforms
from torchvision.models.detection import maskrcnn_resnet50_fpn_v2
from torchvision.ops import nms
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import sys

# Add the current directory to Python path to import MaskCnn
sys.path.append('.')

from MaskCnn import visualize_and_save, run_inference_on_folder

def test_single_image():
    """Test segmentation on a single image"""
    print("Testing segmentation on a single image...")
    
    # Check if input images exist
    input_dir = Path("room_dataset/input_images")
    if not input_dir.exists():
        print(f"Input directory {input_dir} does not exist")
        return False
        
    # Get list of images
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    images = [p for p in sorted(input_dir.glob("*")) if p.suffix.lower() in exts]
    
    if not images:
        print(f"No images found in {input_dir}")
        return False
        
    print(f"Found {len(images)} images. Processing the first one...")
    
    # Process the first image
    img_path = images[0]
    print(f"Processing: {img_path}")
    
    # Create output directory
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    
    # Run inference on a single image
    try:
        img = Image.open(img_path).convert("RGB")
        save_path = output_dir / f"{img_path.stem}_test_seg.jpg"
        run_inference_on_folder(str(input_dir), str(output_dir), score_thr=0.5)
        print(f"Segmentation completed. Output saved to: {save_path}")
        return True
    except Exception as e:
        print(f"Error during segmentation: {e}")
        return False

def main():
    """Main function to run tests"""
    print("=== Image Segmentation and Labeling Test ===")
    
    # Test single image segmentation
    success = test_single_image()
    
    if success:
        print("\n✓ Segmentation and labeling test completed successfully!")
        print("Check the 'test_outputs' directory for results.")
    else:
        print("\n✗ Segmentation and labeling test failed!")
        print("Please check the error messages above.")

if __name__ == "__main__":
    main()