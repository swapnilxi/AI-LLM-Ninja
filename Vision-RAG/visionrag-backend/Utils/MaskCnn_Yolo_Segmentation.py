# ============================================================
# Enhanced PyTorch Instance Segmentation with Gemini Vision API
# - Part A: Inference on room images with Gemini Vision labeling
# - Part B: (Optional) Finetune on a COCO-format dataset
# - Integrates Google's Gemini Vision API for rich object descriptions
# Tested on: Python 3.10+, Torch 2.x, TorchVision 0.17+
# ============================================================

import torch
from torchvision import transforms
from torchvision.models.detection import maskrcnn_resnet50_fpn_v2
from torchvision.ops import nms
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from tqdm import tqdm
import json
import os
from typing import List, Dict, Any, Optional

# Import our Gemini Vision integration
from gemini_vision_labeler import GeminiVisionLabeler, create_gemini_labeler

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Device:", DEVICE)

# ============================================================
# Configuration
# ============================================================

# Update input/output folder paths for new structure
INPUT_IMAGES = "room_dataset/input_images"
OUTPUTS_INFER = "room_dataset/outputs_infer"
ANALYSIS_RESULTS = "room_dataset/analysis_results"

# Gemini Vision API configuration
GEMINI_API_KEY = os.getenv("GOOGLE_AI_API_KEY")
ENABLE_GEMINI_LABELING = GEMINI_API_KEY is not None

if ENABLE_GEMINI_LABELING:
    print("✅ Gemini Vision API enabled - will provide detailed object descriptions")
    gemini_labeler = create_gemini_labeler(GEMINI_API_KEY)
else:
    print("⚠️  Gemini Vision API disabled - set GOOGLE_AI_API_KEY environment variable")
    print("   Will use basic COCO labels only")

# COCO class names for labeling detected objects
COCO_INSTANCE_CATEGORY_NAMES = [
    '__background__', 'person','bicycle','car','motorcycle','airplane','bus','train','truck',
    'boat','traffic light','fire hydrant','N/A','stop sign','parking meter','bench',
    'bird','cat','dog','horse','sheep','cow','elephant','bear','zebra','giraffe','N/A',
    'backpack','umbrella','N/A','N/A','handbag','tie','suitcase','frisbee','skis',
    'snowboard','sports ball','kite','baseball bat','baseball glove','skateboard',
    'surfboard','tennis racket','bottle','N/A','wine glass','cup','fork','knife','spoon',
    'bowl','banana','apple','sandwich','orange','broccoli','carrot','hot dog','pizza',
    'donut','cake','chair','couch','potted plant','bed','N/A','dining table','N/A',
    'N/A','toilet','N/A','tv','laptop','mouse','remote','keyboard','cell phone','microwave',
    'oven','toaster','sink','refrigerator','N/A','book','clock','vase','scissors',
    'teddy bear','hair drier','toothbrush'
]

# ============================================================
# Model Setup
# ============================================================

# Load pre-trained Mask R-CNN
num_classes_coco = 91  # COCO has 91 classes (including background as implicit)
model = maskrcnn_resnet50_fpn_v2(weights="DEFAULT", weights_backbone="DEFAULT")
model.to(DEVICE).eval()

# Simple image transforms
to_tensor = transforms.Compose([
    transforms.ToTensor()
])

# ============================================================
# Enhanced Visualization with Gemini Labels
# ============================================================

def extract_segment_data(outputs, score_thr=0.3, iou_thr=0.5):
    """
    Extract and filter segment data from model outputs.
    
    Args:
        outputs: Model output dictionary
        score_thr: Score threshold for filtering
        iou_thr: IoU threshold for NMS
        
    Returns:
        List of segment dictionaries with masks, labels, scores, and boxes
    """
    boxes = outputs["boxes"].detach().cpu()
    labels = outputs["labels"].detach().cpu()
    scores = outputs["scores"].detach().cpu()
    masks = outputs.get("masks", None)
    if masks is not None:
        masks = masks.detach().cpu()

    # Score filter
    keep = scores >= score_thr
    boxes, labels, scores = boxes[keep], labels[keep], scores[keep]
    if masks is not None:
        masks = masks[keep]

    # NMS
    if len(boxes) > 0:
        keep_idx = nms(boxes, scores, iou_thr)
        boxes, labels, scores = boxes[keep_idx], labels[keep_idx], scores[keep_idx]
        if masks is not None:
            masks = masks[keep_idx]

    # Convert to list of segment dictionaries
    segments = []
    for i in range(len(boxes)):
        segment = {
            'box': boxes[i].tolist(),
            'label': COCO_INSTANCE_CATEGORY_NAMES[int(labels[i])] if int(labels[i]) < len(COCO_INSTANCE_CATEGORY_NAMES) else str(int(labels[i])),
            'label_id': int(labels[i]),
            'score': float(scores[i]),
            'mask': masks[i, 0].numpy() if masks is not None else None
        }
        segments.append(segment)
    
    return segments

def visualize_and_save_enhanced(image_pil, outputs, save_path, score_thr=0.3, iou_thr=0.5):
    """
    Enhanced visualization with Gemini Vision API labels.
    
    Args:
        image_pil: PIL Image to process
        outputs: Model outputs
        save_path: Path to save the enhanced image
        score_thr: Score threshold
        iou_thr: IoU threshold for NMS
    """
    # Extract segment data
    segments = extract_segment_data(outputs, score_thr, iou_thr)
    
    if not segments:
        print("[INFO] No segments detected above threshold")
        return segments
    
    print(f"[DEBUG] Processing {len(segments)} segments")
    
    # Analyze with Gemini Vision API if enabled
    gemini_results = []
    if ENABLE_GEMINI_LABELING:
        print("[INFO] Analyzing segments with Gemini Vision API...")
        try:
            gemini_results = gemini_labeler.batch_analyze_segments(image_pil, segments)
            print(f"[INFO] Gemini analysis completed for {len(gemini_results)} segments")
        except Exception as e:
            print(f"[ERROR] Gemini analysis failed: {e}")
            gemini_results = []
    
    # Create enhanced visualization
    img = image_pil.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0,0,0,0))
    draw = ImageDraw.Draw(overlay)
    
    # Load font
    font_size = 48
    font = None
    font_paths = [
        "/System/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ]
    
    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, font_size)
            break
        except:
            continue
    
    if font is None:
        font = ImageFont.load_default()
    
    # Random colors per instance
    rng = np.random.default_rng(12345)
    
    # Process each segment
    for i, segment in enumerate(segments):
        box = segment['box']
        label_name = segment['label']
        score = segment['score']
        
        # Get Gemini description if available
        gemini_desc = ""
        detailed_label = label_name
        if i < len(gemini_results):
            gemini_desc = gemini_results[i].get('gemini_description', '')
            detailed_label = gemini_results[i].get('detailed_label', label_name)
        
        print(f"[DEBUG] Segment {i}: {detailed_label} (score: {score:.3f})")
        
        # Color coding
        is_table = "table" in label_name.lower()
        if is_table:
            outline = (255, 0, 0, 255)  # Red for tables
        else:
            color = tuple(int(c) for c in rng.integers(64, 255, size=3).tolist()) + (120,)
            outline = (color[0], color[1], color[2], 255)
        
        # Mask overlay
        if segment['mask'] is not None:
            m = (segment['mask'] > 0.5).astype(np.uint8) * 255
            m_img = Image.fromarray(m, mode="L").resize(img.size)
            color_img = Image.new("RGBA", img.size, outline if is_table else color)
            overlay = Image.composite(color_img, overlay, m_img)
        
        # Draw bounding box
        x1, y1, x2, y2 = box
        draw.rectangle([x1, y1, x2, y2], outline=outline, width=5)
        
        # Prepare label text (use detailed label from Gemini if available)
        text = f"{detailed_label} {score:.2f}"
        
        # Get text dimensions
        try:
            if hasattr(draw, "textbbox"):
                bbox = draw.textbbox((0, 0), text, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
            else:
                tw = len(text) * (font_size // 2)
                th = font_size
        except:
            tw = len(text) * 24
            th = 48
        
        # Position label
        label_x = max(20, min(int(x1), img.size[0] - tw - 40))
        label_y = max(20, int(y1) - th - 30)
        
        if label_y < 20:
            label_y = max(20, int(y1) + 20)
        
        # Draw label background
        padding = 20
        draw.rounded_rectangle(
            [label_x - padding - 4, label_y - padding - 4, label_x + tw + padding + 4, label_y + th + padding + 4],
            radius=15, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=4
        )
        draw.rounded_rectangle(
            [label_x - padding, label_y - padding, label_x + tw + padding, label_y + th + padding],
            radius=12, fill=(0, 0, 0, 250)
        )
        
        # Draw text
        outline_size = 4
        for dx in range(-outline_size, outline_size + 1):
            for dy in range(-outline_size, outline_size + 1):
                if dx != 0 or dy != 0:
                    draw.text((label_x + dx, label_y + dy), text, fill=(0, 0, 0, 255), font=font)
        
        draw.text((label_x, label_y), text, fill=(255, 255, 255, 255), font=font)
    
    # Composite and save
    out = Image.alpha_composite(img, overlay).convert("RGB")
    out.save(save_path)
    print(f"[DEBUG] Enhanced image saved to: {save_path}")
    
    # Save Gemini analysis results
    if gemini_results:
        results_path = Path(ANALYSIS_RESULTS) / f"{Path(save_path).stem}_analysis.json"
        Path(ANALYSIS_RESULTS).mkdir(parents=True, exist_ok=True)
        
        # Combine segment data with Gemini results
        combined_results = []
        for i, segment in enumerate(segments):
            result = {
                'segment_info': segment,
                'gemini_analysis': gemini_results[i] if i < len(gemini_results) else {}
            }
            combined_results.append(result)
        
        # Add full image analysis
        try:
            full_image_analysis = gemini_labeler.analyze_full_image(image_pil)
            combined_results.append({
                'full_image_analysis': full_image_analysis
            })
        except Exception as e:
            print(f"[WARNING] Full image analysis failed: {e}")
        
        # Save results
        with open(results_path, 'w') as f:
            json.dump(combined_results, f, indent=2, default=str)
        
        print(f"[INFO] Analysis results saved to: {results_path}")
    
    return segments

def run_inference_with_gemini_labeling(input_dir=INPUT_IMAGES, output_dir=OUTPUTS_INFER, score_thr=0.5):
    """
    Run inference with enhanced Gemini Vision API labeling.
    
    Args:
        input_dir: Directory containing input images
        output_dir: Directory to save segmented images
        score_thr: Score threshold for detection
    """
    in_dir = Path(input_dir)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Create analysis results directory
    Path(ANALYSIS_RESULTS).mkdir(parents=True, exist_ok=True)
    
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    images = [p for p in sorted(in_dir.glob("*")) if p.suffix.lower() in exts]
    
    if not images:
        print(f"[INFO] No images found in {in_dir}. Upload room photos first.")
        return
    
    print(f"[INFO] Processing {len(images)} images with Gemini Vision API labeling...")
    
    with torch.no_grad():
        for img_path in tqdm(images, desc="Segmenting with Gemini labeling"):
            img = Image.open(img_path).convert("RGB")
            x = to_tensor(img).to(DEVICE)
            outputs = model([x])[0]
            
            save_path = out_dir / f"{img_path.stem}_enhanced_seg.jpg"
            segments = visualize_and_save_enhanced(img, outputs, save_path, score_thr=score_thr)
            
            if segments:
                print(f"[INFO] {img_path.name}: {len(segments)} objects detected and labeled")
    
    print(f"[DONE] Enhanced segmentation results saved to: {out_dir.resolve()}")
    print(f"[DONE] Analysis results saved to: {Path(ANALYSIS_RESULTS).resolve()}")

# ============================================================
# Main Execution
# ============================================================

if __name__ == "__main__":
    # Create necessary directories
    Path(INPUT_IMAGES).mkdir(exist_ok=True)
    Path(OUTPUTS_INFER).mkdir(exist_ok=True)
    Path(ANALYSIS_RESULTS).mkdir(exist_ok=True)
    
    if not ENABLE_GEMINI_LABELING:
        print("\n⚠️  To enable Gemini Vision API labeling:")
        print("   1. Get your API key from: https://makersuite.google.com/app/apikey")
        print("   2. Set environment variable: export GOOGLE_AI_API_KEY='your_key_here'")
        print("   3. Restart the script")
        print("\n   For now, running with basic COCO labels only...")
    
    # Run enhanced inference
    run_inference_with_gemini_labeling(INPUT_IMAGES, OUTPUTS_INFER, score_thr=0.6)

