# quick_seg_check.py
import cv2
from ultralytics import YOLO
import os, urllib.request
from urllib.parse import urlparse

# ensure base folder exists
BASE_DIR = "runs/segment/quickcheck/pred"
os.makedirs(BASE_DIR, exist_ok=True)
def _download_to_runs(url: str) -> str:
    """Download URL to runs/segment/quickcheck/pred folder with sensible name."""
    parsed = urlparse(url)
    fname = os.path.basename(parsed.path) or "download.jpg"
    if not fname.endswith((".jpg", ".png", ".jpeg")):
        fname += ".jpg"
    dest = os.path.join(BASE_DIR, fname)
    urllib.request.urlretrieve(url, dest)
    return dest

def main():
    # --- change this url to test different images----
    source = "https://images.unsplash.com/photo-1505691938895-1758d7feb511"
    model_path = "yolo11n-seg.pt"

    # if URL, download into runs/…/pred
    if source.startswith(("http://", "https://")):
        source = _download_to_runs(source)

    # load YOLO segmentation model
    model = YOLO(model_path)

    # run inference, always write results into the fixed pred folder
    results = model.predict(
        source=source,
        save=True,
        project="runs/segment/quickcheck",
        name="pred",        # fixed folder name
        imgsz=640,
        conf=0.25,
    )
    r = results[0]
    #detections 
    # print(f"[OK] saved to: {r.save_dir}")
    # print(f"detections: {len(r.boxes) if r.boxes is not None else 0}")

    #segement detections and crops
    img = r.orig_img            # H x W x 3 (BGR), dtype=uint8
    H, W = img.shape[:2]
    names = r.names
    
    os.makedirs("runs/crops", exist_ok=True)
    
    if len(r.boxes) == 0:
        print("No detections found.")
        return
    for i, box in enumerate(r.boxes):
        box = r.boxes[i]
        cls_id = int(box.cls[0]) if box.cls is not None else -1
        label = names.get(cls_id, str(cls_id))
        conf   = float(box.conf[0]) if box.conf is not None else 1.0
        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]

    # clamp to image bounds (safety for huge images)
    x1 = max(0, min(x1, W-1)); x2 = max(0, min(x2, W))
    y1 = max(0, min(y1, H-1)); y2 = max(0, min(y2, H))

    crop = img[y1:y2, x1:x2]
    
    #--labeling and saving crop----
    # draw a thin rectangle around full crop (optional)
    cv2.rectangle(crop, (1, 1), (crop.shape[1]-2, crop.shape[0]-2), (0, 255, 0), 1)

    # label text
    text = f"{label} {conf:.2f}"
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale, thickness = 0.6, 2

    # compute text size and draw filled bg for readability
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    bg_tl = (4, 4 + th)                     # top-left of bg rect
    bg_br = (4 + tw + 4, 4 + th + 6)        # bottom-right of bg rect
    cv2.rectangle(crop, (bg_tl[0]-2, bg_tl[1]-th-4), (bg_br[0], bg_br[1]), (0, 0, 0), -1)

    # put text (white)
    cv2.putText(crop, text, (4, 4 + th), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)

    
    out_path = f"runs/crops/{i}_{label}.jpg"
    ok = cv2.imwrite(out_path, crop)
    print(f"Saved: {out_path} (ok={ok}, shape={crop.shape})")


    

if __name__ == "__main__":
    main()
