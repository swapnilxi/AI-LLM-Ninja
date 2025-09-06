# ============================================================
# PyTorch Instance Segmentation for Indoor Objects (Mask R-CNN)
# - Part A: Inference on your room images (no training required)
# - Part B: (Optional) Finetune on a COCO-format dataset
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

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Device:", DEVICE)


# ============================================================
# Part A. Inference on your room photos (no training needed)
# ============================================================

# 1) Load a pre-trained Mask R-CNN (trained on COCO)
#    This model can segment common indoor objects: bed, chair, couch, tv, dining table, etc.
num_classes_coco = 91  # COCO has 91 classes (including background as implicit)
model = maskrcnn_resnet50_fpn_v2(weights="DEFAULT", weights_backbone="DEFAULT")
model.to(DEVICE).eval()

# 2) Class names for COCO (index = label id). We'll add a minimal list for display.
#    TorchVision uses COCO 2017 mapping. The following list is from common mappings.
#    (Background class is not explicit; model outputs labels 1..90)

# Update input/output folder paths for new structure
INPUT_IMAGES = "room_dataset/input_images"
OUTPUTS_INFER = "room_dataset/outputs_infer"

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

# 3) Simple image transforms
to_tensor = transforms.Compose([
    transforms.ToTensor()
])

# 4) Visualize helper (blend masks + draw boxes/labels)
def visualize_and_save(image_pil, outputs, save_path, score_thr=0.3, iou_thr=0.5):
    """
    - Applies NMS
    - Filters by score
    - Overlays masks and boxes
    - Adds labels to detected objects with highly visible rounded boxes
    """
    boxes = outputs["boxes"].detach().cpu()
    labels = outputs["labels"].detach().cpu()
    scores = outputs["scores"].detach().cpu()
    masks = outputs.get("masks", None)
    if masks is not None:
        masks = masks.detach().cpu()  # [N,1,H,W]

    print(f"[DEBUG] Total detections: {len(boxes)}")

    # Score filter - lowered threshold for more detections
    keep = scores >= score_thr
    boxes, labels, scores = boxes[keep], labels[keep], scores[keep]
    if masks is not None:
        masks = masks[keep]

    print(f"[DEBUG] After score filter ({score_thr}): {len(boxes)}")

    # NMS
    if len(boxes) > 0:
        keep_idx = nms(boxes, scores, iou_thr)
        boxes, labels, scores = boxes[keep_idx], labels[keep_idx], scores[keep_idx]
        if masks is not None:
            masks = masks[keep_idx]

    print(f"[DEBUG] After NMS: {len(boxes)}")

    # Draw
    img = image_pil.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0,0,0,0))
    draw = ImageDraw.Draw(overlay)

    # Load font with multiple fallbacks and larger size
    font_size = 48  # Even larger font
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
            print(f"[DEBUG] Loaded font: {font_path}, size: {font_size}")
            break
        except:
            continue
    
    if font is None:
        font = ImageFont.load_default()
        print("[DEBUG] Using default font")

    # Random colors per instance
    rng = np.random.default_rng(12345)

    table_detections = []
    
    # Process each detection
    for i in range(len(boxes)):
        box = boxes[i].tolist()
        label_id = int(labels[i])
        score = float(scores[i])
        label_name = COCO_INSTANCE_CATEGORY_NAMES[label_id] if label_id < len(COCO_INSTANCE_CATEGORY_NAMES) else str(label_id)

        print(f"[DEBUG] Detection {i}: {label_name} (score: {score:.3f}) at box: {[int(x) for x in box]}")

        # Table tracking: highlight and log
        is_table = label_name.lower() == "dining table" or label_name.lower() == "table"
        centroid = None
        if is_table:
            outline = (255, 0, 0, 255)  # Red outline for tables
        else:
            color = tuple(int(c) for c in rng.integers(64, 255, size=3).tolist()) + (120,)
            outline = (color[0], color[1], color[2], 255)

        # Mask overlay
        if masks is not None and i < masks.shape[0]:
            m = masks[i, 0].numpy()
            m = (m > 0.5).astype(np.uint8) * 255
            m_img = Image.fromarray(m, mode="L").resize(img.size)
            color_img = Image.new("RGBA", img.size, outline if is_table else color)
            overlay = Image.composite(color_img, overlay, m_img)

        # Draw bounding box with thicker outline
        x1, y1, x2, y2 = box
        draw.rectangle([x1, y1, x2, y2], outline=outline, width=5)
        
        # Prepare label text
        text = f"{label_name} {score:.2f}"
        
        # Get text dimensions with better fallback
        try:
            if hasattr(draw, "textbbox"):
                bbox = draw.textbbox((0, 0), text, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
            else:
                tw = len(text) * (font_size // 2)  # Better estimate based on font size
                th = font_size
        except:
            tw = len(text) * 24  # Fallback estimate
            th = 48

        print(f"[DEBUG] Text: '{text}', dimensions: {tw}x{th}")

        # Position label - always place above the bounding box for consistency
        label_x = max(20, min(int(x1), img.size[0] - tw - 40))  # Ensure it's within bounds
        label_y = max(20, int(y1) - th - 30)  # Place above box with margin
        
        # If label would be too high, place it inside the box
        if label_y < 20:
            label_y = max(20, int(y1) + 20)

        print(f"[DEBUG] Label position: ({label_x}, {label_y})")

        # Draw highly visible rounded label background
        padding = 20  # Increased padding
        
        # Draw multiple layers for maximum visibility
        # Layer 1: Large white background with black border
        draw.rounded_rectangle(
            [label_x - padding - 4, label_y - padding - 4, label_x + tw + padding + 4, label_y + th + padding + 4],
            radius=15, fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=4
        )
        
        # Layer 2: Black background
        draw.rounded_rectangle(
            [label_x - padding, label_y - padding, label_x + tw + padding, label_y + th + padding],
            radius=12, fill=(0, 0, 0, 250)
        )

        # Draw text with strong outline for maximum visibility
        outline_size = 4
        for dx in range(-outline_size, outline_size + 1):
            for dy in range(-outline_size, outline_size + 1):
                if dx != 0 or dy != 0:
                    draw.text((label_x + dx, label_y + dy), text, fill=(0, 0, 0, 255), font=font)
        
        # Draw main text in bright white
        draw.text((label_x, label_y), text, fill=(255, 255, 255, 255), font=font)

        # Collect table info for summary
        if is_table:
            table_detections.append({
                "label": label_name,
                "score": score,
                "box": box,
                "centroid": centroid
            })

    print(f"[DEBUG] Processed {len(boxes)} detections")

    # Composite and save
    out = Image.alpha_composite(img, overlay).convert("RGB")
    out.save(save_path)
    print(f"[DEBUG] Saved image to: {save_path}")

    # Print table summary if any
    if table_detections:
        print("\n[SEGMENTED TABLES]")
        print("Label         Score    Box (x1,y1,x2,y2)         Centroid (x,y)")
        print("---------------------------------------------------------------")
        for t in table_detections:
            print(f"{t['label']:<13} {t['score']:.2f}   {str([int(v) for v in t['box']]):<28} {str(t['centroid']) if t['centroid'] else '-'}")

def run_inference_on_folder(input_dir=INPUT_IMAGES, output_dir=OUTPUTS_INFER, score_thr=0.5):

    in_dir = Path(input_dir)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    images = [p for p in sorted(in_dir.glob("*")) if p.suffix.lower() in exts]
    if not images:
        print(f"[INFO] No images found in {in_dir}. Upload room photos first.")
        return

    with torch.no_grad():
        for img_path in tqdm(images, desc="Segmenting"):
            img = Image.open(img_path).convert("RGB")
            x = to_tensor(img).to(DEVICE)
            outputs = model([x])[0]  # dict
            save_path = out_dir / f"{img_path.stem}_seg.jpg"
            visualize_and_save(img, outputs, save_path, score_thr=score_thr)
    print(f"[DONE] Results saved to: {out_dir.resolve()}")

# ---- Run Part A now (put your room photos in room_dataset/input_images/) ----
if __name__ == "__main__":
    Path(INPUT_IMAGES).mkdir(exist_ok=True)
    run_inference_on_folder(INPUT_IMAGES, OUTPUTS_INFER, score_thr=0.6)


# ============================================================
# Part B. (Optional) Finetune on a COCO-format dataset
# - Works with: COCO, your COCO, or ADE20K converted to COCO "instances"
# - Provide paths below; small epochs for demo
# ============================================================

# If you don't have a COCO-format dataset, you can skip this section.
ENABLE_TRAINING = False  # <-- set True to train

if ENABLE_TRAINING:
    from torch.utils.data import Dataset, DataLoader
    from pycocotools.coco import COCO
    import pycocotools.mask as maskUtils
    import random
    import time

    class CocoInstanceSegDataset(Dataset):
        """
        COCO "instances" dataset -> returns image tensor and target dict:
          {
            'boxes': FloatTensor[N,4],
            'labels': Int64Tensor[N],
            'masks': UInt8Tensor[N,H,W],
            'image_id': Tensor[1],
            'area': Tensor[N],
            'iscrowd': UInt8Tensor[N]
          }
        """
        def __init__(self, images_dir, ann_json, transforms=None, keep_cat_names=None, max_images=None):
            self.images_dir = Path(images_dir)
            self.coco = COCO(ann_json)
            # category filtering (optional)
            if keep_cat_names:
                cat_ids = self.coco.getCatIds(catNms=keep_cat_names)
                img_ids = set()
                for cid in cat_ids:
                    img_ids.update(self.coco.getImgIds(catIds=[cid]))
                self.img_ids = sorted(list(img_ids))
            else:
                self.img_ids = self.coco.getImgIds()
            if max_images:
                self.img_ids = self.img_ids[:max_images]
            self.transforms = transforms

            # Build category mapping to consecutive ids (1..K) for the model
            if keep_cat_names:
                cats = self.coco.loadCats(self.coco.getCatIds(catNms=keep_cat_names))
            else:
                cats = self.coco.loadCats(self.coco.getCatIds())
            # name -> new id
            self.cat_name_to_newid = {c['name']: i+1 for i, c in enumerate(sorted(cats, key=lambda x: x['name']))}
            # old id -> new id
            self.cat_old_to_new = {c['id']: self.cat_name_to_newid[c['name']] for c in cats}

            self.new_id_to_name = {v:k for k,v in self.cat_name_to_newid.items()}

        def __len__(self):
            return len(self.img_ids)

        def __getitem__(self, idx):
            img_info = self.coco.loadImgs([self.img_ids[idx]])[0]
            img_path = self.images_dir / img_info['file_name']
            img = Image.open(img_path).convert("RGB")

            ann_ids = self.coco.getAnnIds(imgIds=[img_info['id']], iscrowd=None)
            anns = self.coco.loadAnns(ann_ids)

            boxes = []
            labels = []
            masks = []
            areas = []
            iscrowd = []

            w, h = img.size
            for ann in anns:
                # skip categories that are not in our mapping (if filtered)
                if ann['category_id'] not in self.cat_old_to_new:
                    continue

                # bbox xywh -> xyxy
                x, y, bw, bh = ann['bbox']
                bx1, by1, bx2, by2 = x, y, x + bw, y + bh
                # filter tiny/invalid
                if bw <= 1 or bh <= 1:
                    continue

                boxes.append([bx1, by1, bx2, by2])
                labels.append(self.cat_old_to_new[ann['category_id']])
                areas.append(ann.get('area', bw * bh))
                iscrowd.append(ann.get('iscrowd', 0))

                # segmentation -> mask
                seg = ann.get('segmentation', None)
                if seg is None:
                    continue
                if isinstance(seg, list):  # polygon
                    rles = maskUtils.frPyObjects(seg, h, w)
                    rle = maskUtils.merge(rles)
                elif isinstance(seg, dict):  # RLE
                    rle = seg
                else:
                    continue
                m = maskUtils.decode(rle)  # HxW uint8
                masks.append(m)

            if len(boxes) == 0:
                # Return empty targets if no valid anns
                target = {
                    "boxes": torch.zeros((0,4), dtype=torch.float32),
                    "labels": torch.zeros((0,), dtype=torch.int64),
                    "masks": torch.zeros((0, h, w), dtype=torch.uint8),
                    "image_id": torch.tensor([img_info['id']]),
                    "area": torch.zeros((0,), dtype=torch.float32),
                    "iscrowd": torch.zeros((0,), dtype=torch.uint8),
                }
            else:
                boxes = torch.as_tensor(boxes, dtype=torch.float32)
                labels = torch.as_tensor(labels, dtype=torch.int64)
                masks = torch.as_tensor(np.array(masks, dtype=np.uint8))
                areas = torch.as_tensor(areas, dtype=torch.float32)
                iscrowd = torch.as_tensor(iscrowd, dtype=torch.uint8)

                target = {
                    "boxes": boxes,
                    "labels": labels,
                    "masks": masks,
                    "image_id": torch.tensor([img_info['id']]),
                    "area": areas,
                    "iscrowd": iscrowd,
                }

            if self.transforms:
                img = self.transforms(img)

            return img, target

    def collate_fn(batch):
        imgs, targets = list(zip(*batch))
        return list(imgs), list(targets)

    # ---- CONFIG: point to your COCO-format dataset here ----
    # Example:
    # TRAIN_IMAGES = "/content/merged_coco/train_images"
    # TRAIN_JSON   = "/content/merged_coco/annotations/instances_train.json"
    # VAL_IMAGES   = "/content/merged_coco/val_images"
    # VAL_JSON     = "/content/merged_coco/annotations/instances_val.json"
    TRAIN_IMAGES = "/path/to/your/train/images"
    TRAIN_JSON   = "/path/to/your/annotations/instances_train.json"
    VAL_IMAGES   = "/path/to/your/val/images"
    VAL_JSON     = "/path/to/your/annotations/instances_val.json"

    # Indoor-focused categories (optional filter).
    # If you merged COCO + ADE20K-instances, map their names accordingly.
    keep_names = [
        "bed","chair","couch","dining table","tv","refrigerator","toilet","sink","laptop","microwave","oven","toaster","potted plant","book","clock","vase"
    ]

    train_tfms = transforms.Compose([transforms.ToTensor()])
    val_tfms   = transforms.Compose([transforms.ToTensor()])

    train_ds = CocoInstanceSegDataset(TRAIN_IMAGES, TRAIN_JSON, transforms=train_tfms,
                                      keep_cat_names=keep_names, max_images=None)  # set to a small number for quick tests
    val_ds   = CocoInstanceSegDataset(VAL_IMAGES, VAL_JSON, transforms=val_tfms,
                                      keep_cat_names=keep_names, max_images=None)

    print(f"Train images: {len(train_ds)} | Val images: {len(val_ds)}")
    train_loader = DataLoader(train_ds, batch_size=2, shuffle=True, num_workers=2, collate_fn=collate_fn)
    val_loader   = DataLoader(val_ds, batch_size=2, shuffle=False, num_workers=2, collate_fn=collate_fn)

    # Build a new model with the right number of classes (background + K)
    num_classes = 1 + len(train_ds.new_id_to_name)  # background + your categories
    print("Classes (including background):", num_classes)
    model_ft = maskrcnn_resnet50_fpn_v2(weights=None, weights_backbone="DEFAULT", num_classes=num_classes)
    model_ft.to(DEVICE)

    # Optimizer & LR
    params = [p for p in model_ft.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(params, lr=5e-4, weight_decay=1e-4)
    lr_scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=3, gamma=0.1)

    # Simple training loop (few epochs for demo)
    def train_one_epoch(model, loader):
        model.train()
        running = 0.0
        for imgs, targets in tqdm(loader, desc="Train"):
            imgs = [im.to(DEVICE) for im in imgs]
            targets = [{k: v.to(DEVICE) if torch.is_tensor(v) else v for k,v in t.items()} for t in targets]

            loss_dict = model(imgs, targets)  # returns dict of losses
            loss = sum(loss_dict.values())

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            running += loss.item()
        return running / max(1, len(loader))

    @torch.no_grad()
    def evaluate(model, loader):
        model.eval()
        total = 0.0
        for imgs, targets in tqdm(loader, desc="Val"):
            imgs = [im.to(DEVICE) for im in imgs]
            _ = model(imgs)  # inference forward (for speed demo we won't compute metrics here)
            total += 0.0
        return total

    EPOCHS = 2  # increase to 10–20+ for real training
    for epoch in range(EPOCHS):
        tr = train_one_epoch(model_ft, train_loader)
        lr_scheduler.step()
        print(f"[Epoch {epoch+1}/{EPOCHS}] train loss: {tr:.4f}")
        _ = evaluate(model_ft, val_loader)

    # Save fine-tuned weights
    Path("checkpoints").mkdir(exist_ok=True)
    ckpt_path = f"checkpoints/maskrcnn_indoor.pth"
    torch.save(model_ft.state_dict(), ckpt_path)
    print(f"Saved fine-tuned weights to: {ckpt_path}")

    # Quick inference demo with fine-tuned model on your validation images
    # (reusing the inference visualizer)
    model_ft.eval()
    demo_out = Path("outputs_finetuned")
    demo_out.mkdir(exist_ok=True)
    with torch.no_grad():
        for i in range(min(5, len(val_ds))):
            img, _ = val_ds[i]
            pil = transforms.ToPILImage()(img)
            out = model_ft([img.to(DEVICE)])[0]
            visualize_and_save(pil, out, demo_out / f"val_{i:03d}.jpg", score_thr=0.5)
    print(f"[DONE] Fine-tune preview saved to {demo_out.resolve()}")
